"""Read-only access to a ZKTeco device over the LAN (TCP 4370, the "pull" protocol).

Nothing here writes to the device: the attendance log is never cleared, users are never changed, the
clock is never set and the device is never disabled, so a failure part-way cannot leave it locked.

The device is not trusted. pyzk loops forever when the connection drops mid-transfer and has no
limit on how much a device may send, so its socket is wrapped (_GuardedSocket) with a deadline for
the whole session, a size limit and cancellation. Records are parsed here rather than by pyzk:
pyzk takes quadratic time on large logs and fails the whole pull on one invalid date.
"""

import logging
import re
import threading
import time
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from struct import unpack_from

from zk import ZK, const

log = logging.getLogger(__name__)

DEFAULT_PORT = 4370
SESSION_DEADLINE = 300  # seconds for a whole pull; a 12,000-punch log takes a few seconds
MAX_BYTES = 64 * 1024 * 1024  # far above any real device: 1,000,000 punches are 40 MB
MAX_RECV = 1024 * 1024  # per read; pyzk asks for whatever size the device claims
EARLIEST = datetime(2000, 1, 1)  # ZK clocks count from 2000

# Control characters: a corrupted device can send them, and Excel files cannot hold them.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean(text) -> str:
	return _CONTROL.sub("", str(text or "")).strip()


class DeviceError(Exception):
	"""The device sent something unusable or stopped answering; the message is for the user."""


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
	punches: list[Punch]
	skipped: int  # records with an impossible date, left out


# Sessions in progress, so cancel_all() can close their sockets from the UI thread.
_active: set["_GuardedSocket"] = set()
_active_lock = threading.Lock()


class _GuardedSocket:
	def __init__(self, sock, deadline):
		self._sock = sock
		self._deadline = deadline
		self._received = 0
		self.cancelled = False

	def recv(self, size):
		if self.cancelled:
			raise Cancelled()
		remaining = self._deadline - time.monotonic()
		if remaining <= 0:
			raise DeviceError("the device took too long")
		self._sock.settimeout(min(self._sock.gettimeout() or remaining, remaining))
		data = self._sock.recv(max(1, min(size, MAX_RECV)))
		if not data:
			if self.cancelled:
				raise Cancelled()
			raise DeviceError("the device closed the connection")
		self._received += len(data)
		if self._received > MAX_BYTES:
			raise DeviceError("the device sent far more data than a device holds")
		return data

	def cancel(self):
		self.cancelled = True
		with suppress(OSError):
			self._sock.close()

	def __getattr__(self, name):  # send, sendto, settimeout, close, ...
		return getattr(self._sock, name)


class _ZK(ZK):
	"""pyzk's ZK with its socket wrapped as soon as it is created."""

	def __init__(self, *args, deadline, **kwargs):
		self._deadline = deadline
		super().__init__(*args, **kwargs)

	def _ZK__create_socket(self):  # name-mangled override of ZK.__create_socket
		super()._ZK__create_socket()
		self.guard = _GuardedSocket(self._ZK__sock, self._deadline)
		self._ZK__sock = self.guard


def cancel_all():
	"""Stop every device session in progress; each fails with Cancelled."""
	with _active_lock:
		for guard in list(_active):
			guard.cancel()


@contextmanager
def _session(ip, port, comm_key, timeout):
	zk = _ZK(
		ip,
		port=port,
		timeout=timeout,
		password=comm_key,
		ommit_ping=True,
		deadline=time.monotonic() + SESSION_DEADLINE,
	)
	guard = None
	try:
		zk.connect()
		guard = zk.guard
		with _active_lock:
			_active.add(guard)
		yield zk
	except Exception as e:
		if guard is not None and guard.cancelled:
			raise Cancelled() from e
		raise
	finally:
		if guard is not None:
			with _active_lock:
				_active.discard(guard)
		# After a timeout the stream is out of step and CMD_EXIT fails; that must not hide the real
		# error. pyzk only closes the socket when CMD_EXIT succeeds, so close it here either way.
		if guard is None or not guard.cancelled:
			try:
				zk.disconnect()
			except Exception as e:
				log.warning("Disconnect from %s failed: %r", ip, e)
		sock = getattr(zk, "_ZK__sock", None)
		if sock is not None:
			sock.close()


def decode_time(raw: int) -> datetime | None:
	"""ZK packed time (see zkemsdk DecodeTime); None for an impossible date."""
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


def parse_users(data: bytes, count: int) -> tuple[list[DeviceUser], dict[int, str]]:
	"""Users from CMD_USERTEMP_RRQ data (28 bytes each on old firmware, else 72), and the device's
	internal uid -> user ID, which old 8-byte punch records need."""
	if len(data) <= 4 or count <= 0:
		return [], {}
	size = unpack_from("<I", data, 0)[0] / count
	users, uids = [], {}
	if size == 28:
		for offset in range(4, len(data) - 27, 28):
			uid, _priv, _pw, name, _card, _group, _tz, number = unpack_from("<HB5s8sIxBhI", data, offset)
			users.append(DeviceUser(str(number), _text(name)))
			uids[uid] = str(number)
	else:
		for offset in range(4, len(data) - 71, 72):
			uid, _priv, _pw, name, _card, _group, raw_id = unpack_from("<HB8s24sIx7sx24s", data, offset)
			users.append(DeviceUser(_text(raw_id), _text(name)))
			uids[uid] = _text(raw_id)
	return users, uids


def parse_attendance(data: bytes, count: int, uid_to_user_id: dict[int, str], serial: str, now: datetime):
	"""(punches, skipped) from CMD_ATTLOG_RRQ data: 8, 16 or 40 bytes per record."""
	if len(data) < 4 or count <= 0:
		return [], 0
	size = unpack_from("<I", data, 0)[0] / count
	latest = now + timedelta(days=1)  # a little room for a device clock that runs ahead
	punches, skipped = [], 0
	step = 8 if size == 8 else 16 if size == 16 else 40
	for offset in range(4, len(data) - step + 1, step):
		if step == 8:
			uid, verify, raw_time, punch = unpack_from("<HBIB", data, offset)
			user_id = uid_to_user_id.get(uid, str(uid))
		elif step == 16:
			number, raw_time, verify, punch = unpack_from("<IIBB", data, offset)
			user_id = str(number)
		else:
			_uid, raw_user_id, verify, raw_time, punch = unpack_from("<H24sBIB", data, offset)
			user_id = _text(raw_user_id)
		timestamp = decode_time(raw_time)
		if timestamp is None or not EARLIEST <= timestamp <= latest or not user_id:
			skipped += 1
			continue
		punches.append(Punch(serial, user_id, timestamp, punch, verify))
	return punches, skipped


def _read_users(conn) -> tuple[list[DeviceUser], dict[int, str]]:
	conn.read_sizes()
	if not conn.users:
		return [], {}
	data, _size = conn.read_with_buffer(const.CMD_USERTEMP_RRQ, const.FCT_USER)
	return parse_users(data, conn.users)


def _serial(conn) -> str:
	serial = clean(conn.get_serialnumber())
	if not serial:
		raise DeviceError("the device did not report a serial number")
	return serial


def read_punches(ip, port=DEFAULT_PORT, comm_key=0, timeout=30) -> PullResult:
	"""The device's serial number and its whole attendance log."""
	with _session(ip, port, comm_key, timeout) as conn:
		serial = _serial(conn)
		_users, uids = _read_users(conn)
		conn.read_sizes()
		if not conn.records:
			return PullResult(serial, [], 0)
		data, _size = conn.read_with_buffer(const.CMD_ATTLOG_RRQ)
		count = conn.records
	punches, skipped = parse_attendance(data, count, uids, serial, datetime.now())
	if skipped:
		log.warning("%s (%s): %d records with an impossible date left out", ip, serial, skipped)
	return PullResult(serial, punches, skipped)


def read_users(ip, port=DEFAULT_PORT, comm_key=0, timeout=30) -> list[DeviceUser]:
	with _session(ip, port, comm_key, timeout) as conn:
		users, _uids = _read_users(conn)
	return [u for u in users if u.user_id]


def probe(ip, port=DEFAULT_PORT, comm_key=0, timeout=10) -> DeviceInfo:
	with _session(ip, port, comm_key, timeout) as conn:
		serial = _serial(conn)
		conn.read_sizes()
		return DeviceInfo(serial, conn.records, conn.users)
