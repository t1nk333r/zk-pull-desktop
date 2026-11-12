"""Read-only access to a ZKTeco device over the LAN (TCP 4370, the "pull" protocol).

Nothing here writes to the device: the attendance log is never cleared, users are never changed, the
clock is never set and the device is never disabled, so a failure part-way cannot leave it locked.
"""

import logging
import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

from zk import ZK

log = logging.getLogger(__name__)

DEFAULT_PORT = 4370

# Control characters: a corrupted device can send them, and Excel files cannot hold them.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean(text) -> str:
	return _CONTROL.sub("", str(text or "")).strip()


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


@contextmanager
def _session(ip, port, comm_key, timeout):
	zk = ZK(ip, port=port, timeout=timeout, password=comm_key, ommit_ping=True)
	try:
		yield zk.connect()
	finally:
		# After a timeout the stream is out of step and CMD_EXIT fails; that must not hide the real
		# error. pyzk only closes the socket when CMD_EXIT succeeds, so close it here either way.
		try:
			zk.disconnect()
		except Exception as e:
			log.warning("Disconnect from %s failed: %r", ip, e)
		sock = getattr(zk, "_ZK__sock", None)
		if sock is not None:
			sock.close()


def read_punches(ip, port=DEFAULT_PORT, comm_key=0, timeout=30) -> tuple[str, list[Punch]]:
	"""The device's serial number and its whole attendance log."""
	with _session(ip, port, comm_key, timeout) as conn:
		serial = clean(conn.get_serialnumber())
		records = conn.get_attendance()
	return serial, [
		Punch(serial, clean(r.user_id), r.timestamp, int(r.punch), int(r.status)) for r in records
	]


def read_users(ip, port=DEFAULT_PORT, comm_key=0, timeout=30) -> list[DeviceUser]:
	with _session(ip, port, comm_key, timeout) as conn:
		users = conn.get_users()
	return [DeviceUser(clean(u.user_id), clean(u.name)) for u in users]


def probe(ip, port=DEFAULT_PORT, comm_key=0, timeout=10) -> DeviceInfo:
	with _session(ip, port, comm_key, timeout) as conn:
		serial = clean(conn.get_serialnumber())
		conn.read_sizes()
		return DeviceInfo(serial, conn.records, conn.users)
