"""Read-only access to a ZKTeco device over the LAN (TCP 4370, the "pull" protocol).

Nothing here writes to the device: the only commands sent are connect, authenticate, read the
serial number, read the record counts, read a buffer and free it, and disconnect. The attendance log
is never cleared, users are never changed, the clock is never set and the device is never disabled,
so a failure part-way cannot leave it locked.

The device is not trusted: every read has a deadline for the whole session and a size limit, frames
are checked before use, and a session can be cancelled from the UI thread at any point, including
while it is still connecting.
"""

import logging
import re
import socket
import threading
import time
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from struct import pack, unpack_from

log = logging.getLogger(__name__)

DEFAULT_PORT = 4370
SESSION_DEADLINE = 300  # seconds for a whole pull; a 12,000-punch log takes a few seconds
MAX_BYTES = 64 * 1024 * 1024  # far above any real device: 1,000,000 punches are 40 MB
MAX_RECORDS = 2_000_000  # real devices hold 100,000 to 1,000,000 punches
MAX_FRAME = 1024 * 1024  # a frame carries at most one 64 KB chunk
CHUNK = 0xFFC0  # bytes asked for per buffer read
EARLIEST = datetime(2000, 1, 1)  # ZK clocks count from 2000

# Commands (ZKTeco standalone protocol). Only reads; see the module docstring.
CMD_CONNECT = 1000
CMD_EXIT = 1001
CMD_AUTH = 1102
CMD_OPTIONS_RRQ = 11
CMD_GET_FREE_SIZES = 50
CMD_USERTEMP_RRQ = 9
CMD_ATTLOG_RRQ = 13
CMD_PREPARE_DATA = 1500
CMD_DATA = 1501
CMD_FREE_DATA = 1502
CMD_PREPARE_BUFFER = 1503
CMD_READ_BUFFER = 1504
CMD_ACK_OK = 2000
CMD_ACK_UNAUTH = 2005
FCT_USER = 5

_MAGIC = b"\x50\x50\x82\x7d"  # start of every TCP frame

# Control characters: a corrupted device can send them, and Excel files cannot hold them.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean(text) -> str:
	return _CONTROL.sub("", str(text or "")).strip()


class DeviceError(Exception):
	"""The device could not be read. reason is one of REASONS; the UI shows a translated message."""

	REASONS = ("unreachable", "comm_key", "timeout", "closed", "too_much", "bad_data", "no_serial")

	def __init__(self, reason, detail=""):
		assert reason in self.REASONS, reason
		super().__init__(f"{reason}: {detail}" if detail else reason)
		self.reason = reason
		self.detail = detail


class Cancelled(Exception):
	pass


@dataclass(frozen=True)
class Punch:
	serial: str
	user_id: str
	timestamp: datetime
	punch: int  # state key pressed: 0 check-in, 1 check-out, 2 break-out, 3 break-in, 4 OT-in, 5 OT-out
	verify: int  # how the user was identified: 0 password, 1 fingerprint, 2 card, 15 face, ...


@dataclass(frozen=True)
class DeviceUser:
	user_id: str
	name: str


@dataclass(frozen=True)
class DeviceInfo:
	serial: str
	punch_count: int
	user_count: int


@dataclass(frozen=True)
class PullResult:
	serial: str
	punches: list[Punch]  # only the punches in the period asked for
	total: int  # punches on the device
	skipped: int  # records with an impossible date, left out


# Sessions in progress, so cancel_all() can close their sockets from the UI thread.
_active: set["_Connection"] = set()
_active_lock = threading.Lock()


def checksum(data: bytes) -> int:
	"""The frame checksum: the one's complement of the one's-complement sum of little-endian words,
	taken with the checksum field zero. Devices drop frames whose checksum is wrong."""
	total = 0
	for i in range(0, len(data) - 1, 2):
		total += data[i] | data[i + 1] << 8
		if total > 0xFFFF:
			total -= 0xFFFF
	if len(data) % 2:
		total += data[-1]
	while total > 0xFFFF:
		total -= 0xFFFF
	return 0xFFFF - total


def comm_key_token(key: int, session: int, ticks: int = 50) -> bytes:
	"""What CMD_AUTH sends for a comm key: the key's bits reversed, plus the session, scrambled."""
	reversed_bits = int(f"{key & 0xFFFFFFFF:032b}"[::-1], 2)
	value = (reversed_bits + session) & 0xFFFFFFFF
	b = bytes(x ^ y for x, y in zip(pack("<I", value), b"ZKSO", strict=True))
	b = b[2:4] + b[0:2]
	t = ticks & 0xFF
	return bytes((b[0] ^ t, b[1] ^ t, t, b[3] ^ t))


class _Connection:
	"""One TCP session. Every receive is bounded by the session deadline and MAX_BYTES."""

	def __init__(self, ip, port, timeout, deadline):
		self.ip, self.port, self.timeout, self.deadline = ip, port, timeout, deadline
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.session = 0
		self.reply = 0xFFFE
		self.received = 0
		self.cancelled = False

	def cancel(self):
		self.cancelled = True
		with suppress(OSError):
			self.sock.shutdown(socket.SHUT_RDWR)
		with suppress(OSError):
			self.sock.close()

	def close(self):
		with suppress(OSError):
			self.sock.close()

	def _check(self):
		if self.cancelled:
			raise Cancelled()
		remaining = self.deadline - time.monotonic()
		if remaining <= 0:
			raise DeviceError("timeout")
		self.sock.settimeout(min(self.timeout, remaining))

	def open(self):
		self._check()
		try:
			self.sock.connect((self.ip, self.port))
		except OSError as e:
			if self.cancelled:
				raise Cancelled() from e
			if isinstance(e, TimeoutError | socket.timeout):
				raise DeviceError("unreachable", "timed out") from e
			raise DeviceError("unreachable", e.strerror or str(e)) from e

	def _recv_exactly(self, size) -> bytes:
		parts, left = [], size
		while left:
			self._check()
			try:
				data = self.sock.recv(min(left, 65536))
			except OSError as e:
				if self.cancelled:
					raise Cancelled() from e
				if isinstance(e, TimeoutError | socket.timeout):
					raise DeviceError("timeout") from e
				raise DeviceError("closed", e.strerror or str(e)) from e
			if not data:
				if self.cancelled:
					raise Cancelled()
				raise DeviceError("closed")
			self.received += len(data)
			if self.received > MAX_BYTES:
				raise DeviceError("too_much")
			parts.append(data)
			left -= len(data)
		return b"".join(parts)

	def send(self, command, data=b""):
		self._check()
		self.reply = (self.reply + 1) % 0xFFFF
		body = pack("<HHHH", command, 0, self.session, self.reply) + data
		body = pack("<HHHH", command, checksum(body), self.session, self.reply) + data
		try:
			self.sock.sendall(_MAGIC + pack("<I", len(body)) + body)
		except OSError as e:
			if self.cancelled:
				raise Cancelled() from e
			raise DeviceError("closed", e.strerror or str(e)) from e

	def receive(self) -> tuple[int, bytes]:
		"""(command, data) of the next frame."""
		head = self._recv_exactly(8)
		if head[:4] != _MAGIC:
			raise DeviceError("bad_data", "not a ZK frame")
		length = unpack_from("<I", head, 4)[0]
		if not 8 <= length <= MAX_FRAME:
			raise DeviceError("bad_data", f"frame of {length} bytes")
		body = self._recv_exactly(length)
		command, _checksum, session, _reply = unpack_from("<HHHH", body)
		if command in (CMD_ACK_OK, CMD_ACK_UNAUTH) and not self.session:
			self.session = session
		return command, body[8:]

	def ask(self, command, data=b"", expect=(CMD_ACK_OK,)) -> tuple[int, bytes]:
		self.send(command, data)
		reply, payload = self.receive()
		if reply == CMD_ACK_UNAUTH:
			raise DeviceError("comm_key")
		if reply not in expect:
			raise DeviceError("bad_data", f"answer {reply} to command {command}")
		return reply, payload

	def connect(self, comm_key):
		self.open()
		self.send(CMD_CONNECT)
		reply, _ = self.receive()
		if reply == CMD_ACK_UNAUTH:
			self.ask(CMD_AUTH, comm_key_token(comm_key, self.session))
		elif reply != CMD_ACK_OK:
			raise DeviceError("bad_data", f"answer {reply} to connect")

	def disconnect(self):
		self.send(CMD_EXIT)
		self.receive()

	def serial(self) -> str:
		_, data = self.ask(CMD_OPTIONS_RRQ, b"~SerialNumber\x00")
		value = data.split(b"\x00")[0].partition(b"=")[2]
		serial = clean(value.decode("ascii", errors="ignore"))
		if not serial:
			raise DeviceError("no_serial")
		return serial

	def sizes(self) -> tuple[int, int]:
		"""(users, punches) stored on the device."""
		_, data = self.ask(CMD_GET_FREE_SIZES)
		if len(data) < 36:
			raise DeviceError("bad_data", "short size reply")
		users, punches = unpack_from("<i", data, 16)[0], unpack_from("<i", data, 32)[0]
		if not 0 <= users <= MAX_RECORDS or not 0 <= punches <= MAX_RECORDS:
			raise DeviceError("bad_data", f"{users} users, {punches} punches")
		return users, punches

	def read_buffer(self, command, fct=0) -> bytes:
		"""A whole table (users or attendance log), read in chunks and then freed on the device.

		Freeing releases the device's copy of the buffer; the table itself is untouched."""
		reply, data = self.ask(
			CMD_PREPARE_BUFFER, pack("<bhii", 1, command, fct, 0), expect=(CMD_ACK_OK, CMD_DATA)
		)
		if reply == CMD_DATA:  # small tables come back at once
			return data
		if len(data) < 5:
			raise DeviceError("bad_data", "short buffer reply")
		size = unpack_from("<I", data, 1)[0]
		if size > MAX_BYTES:
			raise DeviceError("too_much")
		parts = []
		for start in range(0, size, CHUNK):
			parts.append(self._read_chunk(start, min(CHUNK, size - start)))
		self.ask(CMD_FREE_DATA)
		return b"".join(parts)

	def _read_chunk(self, start, size) -> bytes:
		reply, data = self.ask(CMD_READ_BUFFER, pack("<ii", start, size), expect=(CMD_DATA, CMD_PREPARE_DATA))
		if reply == CMD_PREPARE_DATA:  # the chunk follows in one or more data frames, then an ACK
			if len(data) < 4 or unpack_from("<I", data)[0] != size:
				raise DeviceError("bad_data", "chunk size")
			parts, got = [], 0
			while got < size:
				reply, part = self.receive()
				if reply != CMD_DATA:
					raise DeviceError("bad_data", f"answer {reply} inside a chunk")
				parts.append(part)
				got += len(part)
			reply, _ = self.receive()
			if reply != CMD_ACK_OK:
				raise DeviceError("bad_data", f"answer {reply} after a chunk")
			data = b"".join(parts)
		if len(data) != size:
			raise DeviceError("bad_data", f"chunk of {len(data)} bytes, {size} asked")
		return data


def cancel_all():
	"""Stop every device session in progress, connecting or reading; each fails with Cancelled."""
	with _active_lock:
		for conn in list(_active):
			conn.cancel()


@contextmanager
def _session(ip, port, comm_key, timeout):
	conn = _Connection(ip, port, timeout, time.monotonic() + SESSION_DEADLINE)
	with _active_lock:  # before connecting, so Cancel works while the device does not answer
		_active.add(conn)
	try:
		conn.connect(int(comm_key or 0))
		yield conn
		with suppress(DeviceError, Cancelled):  # the data is read; a failed goodbye changes nothing
			conn.disconnect()
	except Exception as e:
		if conn.cancelled and not isinstance(e, Cancelled):
			raise Cancelled() from e
		raise
	finally:
		with _active_lock:
			_active.discard(conn)
		conn.close()


def decode_time(raw: int) -> datetime | None:
	"""ZK packed time (seconds since 2000 in 31-day months); None for an impossible date."""
	second, raw = raw % 60, raw // 60
	minute, raw = raw % 60, raw // 60
	hour, raw = raw % 24, raw // 24
	day, raw = raw % 31 + 1, raw // 31
	month, raw = raw % 12 + 1, raw // 12
	try:
		return datetime(raw + 2000, month, day, hour, minute, second)
	except ValueError:  # 31 February and the like
		return None


def _text(raw: bytes) -> str:
	return clean(raw.split(b"\x00")[0].decode("utf-8", errors="ignore"))


def record_size(data: bytes, count: int, sizes: tuple[int, ...]) -> int:
	"""The record size from the buffer's own byte total: the size that divides it into a count
	closest to the one read before (a punch made in between changes the count, not the size)."""
	if len(data) < 4:
		raise DeviceError("bad_data", "empty buffer")
	total = min(unpack_from("<I", data, 0)[0], len(data) - 4)
	fits = [s for s in sizes if total % s == 0 and total // s <= MAX_RECORDS]
	if not fits:
		raise DeviceError("bad_data", f"{total} bytes for {count} records")
	return min(fits, key=lambda s: abs(total // s - count))


def parse_users(data: bytes, count: int) -> tuple[list[DeviceUser], dict[int, str]]:
	"""Users from CMD_USERTEMP_RRQ data (28 bytes each on old firmware, else 72), and the device's
	internal uid -> user ID, which old 8-byte punch records need."""
	if len(data) <= 4 or count <= 0:
		return [], {}
	size = record_size(data, count, (72, 28))
	end = 4 + min(unpack_from("<I", data, 0)[0], len(data) - 4)
	users, uids = [], {}
	for offset in range(4, end - size + 1, size):
		if size == 28:
			uid, _priv, _pw, name, _card, _group, _tz, number = unpack_from("<HB5s8sIxBhI", data, offset)
			user_id = str(number)
		else:
			uid, _priv, _pw, name, _card, _group, raw_id = unpack_from("<HB8s24sIx7sx24s", data, offset)
			user_id = _text(raw_id)
		users.append(DeviceUser(user_id, _text(name)))
		uids[uid] = user_id
	return users, uids


def parse_attendance(
	data: bytes,
	count: int,
	uid_to_user_id: dict[int, str],
	serial: str,
	now: datetime,
	period: tuple[date, date] | None = None,
) -> tuple[list[Punch], int, int]:
	"""(punches, records, skipped) from CMD_ATTLOG_RRQ data: 8, 16 or 40 bytes per record.

	With a period, only punches on those days (both included) are returned; records counts all."""
	if len(data) <= 4 or count <= 0:
		return [], 0, 0
	size = record_size(data, count, (40, 16, 8))
	end = 4 + min(unpack_from("<I", data, 0)[0], len(data) - 4)
	latest = now + timedelta(days=1)  # a little room for a device clock that runs ahead
	punches, records, skipped = [], 0, 0
	for offset in range(4, end - size + 1, size):
		records += 1
		if size == 8:
			uid, verify, raw_time, punch = unpack_from("<HBIB", data, offset)
			# A uid with no user is a deleted user's slot. Its bare number would be some other
			# employee's ID, so it is kept apart under "uid:".
			user_id = uid_to_user_id.get(uid, f"uid:{uid}")
		elif size == 16:
			number, raw_time, verify, punch = unpack_from("<IIBB", data, offset)
			user_id = str(number)
		else:
			_uid, raw_user_id, verify, raw_time, punch = unpack_from("<H24sBIB", data, offset)
			user_id = _text(raw_user_id)
		timestamp = decode_time(raw_time)
		if timestamp is None or not EARLIEST <= timestamp <= latest or not user_id:
			skipped += 1
			continue
		if period is None or period[0] <= timestamp.date() <= period[1]:
			punches.append(Punch(serial, user_id, timestamp, punch, verify))
	return punches, records, skipped


def _read_users(conn, count) -> tuple[list[DeviceUser], dict[int, str]]:
	if not count:
		return [], {}
	return parse_users(conn.read_buffer(CMD_USERTEMP_RRQ, FCT_USER), count)


def read_punches(ip, port=DEFAULT_PORT, comm_key=0, timeout=30, period=None) -> PullResult:
	"""The device's serial number and its attendance log; with a period, only the punches in it.

	The device always sends its whole log (it cannot send part of it); the period is applied here,
	on the worker thread, so a huge log never becomes a huge list."""
	with _session(ip, port, comm_key, timeout) as conn:
		serial = conn.serial()
		users, records = conn.sizes()
		_users, uids = _read_users(conn, users)
		data = conn.read_buffer(CMD_ATTLOG_RRQ) if records else b""
	punches, total, skipped = parse_attendance(data, records, uids, serial, datetime.now(), period)
	if skipped:
		log.warning("%s (%s): %d records with an impossible date left out", ip, serial, skipped)
	return PullResult(serial, punches, total, skipped)


def read_users(ip, port=DEFAULT_PORT, comm_key=0, timeout=30) -> list[DeviceUser]:
	with _session(ip, port, comm_key, timeout) as conn:
		count, _records = conn.sizes()
		users, _uids = _read_users(conn, count)
	return [u for u in users if u.user_id]


def probe(ip, port=DEFAULT_PORT, comm_key=0, timeout=10) -> DeviceInfo:
	with _session(ip, port, comm_key, timeout) as conn:
		serial = conn.serial()
		users, records = conn.sizes()
	return DeviceInfo(serial, records, users)
