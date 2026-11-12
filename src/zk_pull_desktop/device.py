"""Read-only access to a ZKTeco device over the LAN (TCP 4370, the "pull" protocol).

Nothing here writes to the device: the attendance log is never cleared and the clock is never set.
"""

from dataclasses import dataclass
from datetime import datetime

from zk import ZK

DEFAULT_PORT = 4370


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


def _connect(ip, port, comm_key, timeout):
	return ZK(ip, port=port, timeout=timeout, password=comm_key, ommit_ping=True).connect()


def read_punches(ip, port=DEFAULT_PORT, comm_key=0, timeout=30) -> tuple[str, list[Punch]]:
	"""The device's serial number and its whole attendance log."""
	conn = _connect(ip, port, comm_key, timeout)
	try:
		serial = conn.get_serialnumber()
		records = conn.get_attendance()
	finally:
		conn.disconnect()
	return serial, [Punch(serial, str(r.user_id), r.timestamp, int(r.punch), int(r.status)) for r in records]


def read_users(ip, port=DEFAULT_PORT, comm_key=0, timeout=30) -> list[DeviceUser]:
	conn = _connect(ip, port, comm_key, timeout)
	try:
		users = conn.get_users()
	finally:
		conn.disconnect()
	return [DeviceUser(str(u.user_id), (u.name or "").strip()) for u in users]


def probe(ip, port=DEFAULT_PORT, comm_key=0, timeout=10) -> DeviceInfo:
	conn = _connect(ip, port, comm_key, timeout)
	try:
		serial = conn.get_serialnumber()
		conn.read_sizes()
		return DeviceInfo(serial, conn.records, conn.users)
	finally:
		conn.disconnect()
