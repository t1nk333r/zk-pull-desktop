import time
from datetime import datetime
from struct import pack

import pytest

from zk_pull_desktop import device

NOW = datetime(2026, 11, 12, 12, 0)


class FakeSocket:
	closed = False

	def __init__(self, chunks=()):
		self.chunks = list(chunks)
		self.timeout = 3

	def recv(self, size):
		return self.chunks.pop(0) if self.chunks else b""

	def settimeout(self, value):
		self.timeout = value

	def gettimeout(self):
		return self.timeout

	def close(self):
		self.closed = True


class FakeZK:
	"""Times out mid-read, then fails CMD_EXIT, like a device whose stream is out of step."""

	last = None

	def __init__(self, *args, deadline, **kwargs):
		self._ZK__sock = FakeSocket()
		self.guard = device._GuardedSocket(self._ZK__sock, deadline)
		FakeZK.last = self

	def connect(self):
		return self

	def get_serialnumber(self):
		return "SN1"

	def read_sizes(self):
		raise TimeoutError("timed out")

	def disconnect(self):
		raise RuntimeError("TCP packet invalid")


def test_read_error_is_not_hidden_by_disconnect_and_socket_is_closed(monkeypatch):
	monkeypatch.setattr(device, "_ZK", FakeZK)
	with pytest.raises(TimeoutError):
		device.read_punches("10.0.0.5")
	assert FakeZK.last._ZK__sock.closed


def test_closed_connection_is_an_error_not_an_endless_loop():
	guard = device._GuardedSocket(FakeSocket([b"abc"]), time.monotonic() + 60)
	assert guard.recv(100) == b"abc"
	with pytest.raises(device.DeviceError, match="closed"):
		guard.recv(100)


def test_session_deadline_and_size_limit(monkeypatch):
	slow = device._GuardedSocket(FakeSocket([b"x"] * 10), time.monotonic() - 1)
	with pytest.raises(device.DeviceError, match="too long"):
		slow.recv(1)
	monkeypatch.setattr(device, "MAX_BYTES", 10)
	big = device._GuardedSocket(FakeSocket([b"x" * 8, b"x" * 8]), time.monotonic() + 60)
	big.recv(8)
	with pytest.raises(device.DeviceError, match="more data"):
		big.recv(8)


def test_recv_size_is_capped():
	sizes = []

	class Recording(FakeSocket):
		def recv(self, size):
			sizes.append(size)
			return b"x"

	device._GuardedSocket(Recording(), time.monotonic() + 60).recv(0xFFFFFFF0)  # size claimed by a device
	assert sizes == [device.MAX_RECV]


def test_cancel_closes_the_socket():
	sock = FakeSocket([b"abc"])
	guard = device._GuardedSocket(sock, time.monotonic() + 60)
	guard.cancel()
	assert sock.closed
	with pytest.raises(device.Cancelled):
		guard.recv(10)


def zk_time(dt):
	return ((((dt.year - 2000) * 12 + dt.month - 1) * 31 + dt.day - 1) * 24 + dt.hour) * 3600 + (
		dt.minute * 60 + dt.second
	)


def record40(user_id, raw_time, punch=0, verify=1):
	return pack("<H24sBIB8s", 1, user_id.encode(), verify, raw_time, punch, b"")


def attendance(records, size=40):
	return pack("<I", size * len(records)) + b"".join(records)


def test_decode_time_matches_the_device_format():
	assert device.decode_time(zk_time(datetime(2026, 11, 12, 8, 40, 18))) == datetime(2026, 11, 12, 8, 40, 18)
	feb_31 = ((26 * 12 + 1) * 31 + 30) * 86400
	assert device.decode_time(feb_31) is None


def test_impossible_and_future_dates_are_left_out_not_fatal():
	feb_31 = ((26 * 12 + 1) * 31 + 30) * 86400
	data = attendance([
		record40("7", zk_time(datetime(2026, 11, 1, 8))),
		record40("7", feb_31),  # one bad record must not fail the whole pull
		record40("8", 0xFFFFFFFF),  # year 2133
		record40("9", zk_time(datetime(2026, 11, 1, 17)), punch=1),
	])  # fmt: skip
	punches, skipped = device.parse_attendance(data, 4, {}, "SN1", NOW)
	assert [(p.user_id, p.timestamp.hour, p.punch) for p in punches] == [("7", 8, 0), ("9", 17, 1)]
	assert skipped == 2


def test_old_8_byte_records_use_the_user_list():
	data = attendance([pack("<HBIB", 3, 1, zk_time(datetime(2026, 11, 1, 8)), 0)], size=8)
	punches, _ = device.parse_attendance(data, 1, {3: "1001"}, "SN1", NOW)
	assert punches[0].user_id == "1001"


def test_parsing_is_linear():
	data = attendance([record40(str(i % 500), zk_time(datetime(2026, 1, 1, 8))) for i in range(200_000)])
	started = time.monotonic()
	punches, _ = device.parse_attendance(data, 200_000, {}, "SN1", NOW)
	assert len(punches) == 200_000
	assert time.monotonic() - started < 5  # pyzk's slicing needs minutes for this


def test_parse_users_72_and_28_bytes():
	user72 = pack("<HB8s24sIx7sx24s", 5, 0, b"", b"Sa\x02ra", 0, b"1", b"1005")
	users, uids = device.parse_users(pack("<I", 72) + user72, 1)
	assert users == [device.DeviceUser("1005", "Sara")] and uids == {5: "1005"}
	user28 = pack("<HB5s8sIxBhI", 6, 0, b"", b"Omar", 0, 1, 0, 1006)
	users, uids = device.parse_users(pack("<I", 28) + user28, 1)
	assert users == [device.DeviceUser("1006", "Omar")] and uids == {6: "1006"}


def test_clean_removes_control_characters():
	assert device.clean(" Sa\x02ra \x7f") == "Sara"
	assert device.clean(None) == ""
