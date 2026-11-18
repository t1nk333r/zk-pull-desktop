import socket
import threading
import time
from datetime import date, datetime
from struct import pack, unpack_from

import pytest

from zk_pull_desktop import device

NOW = datetime(2026, 11, 12, 12, 0)

# Every command the app may send. Anything else (clear log, set time, disable device, ...) is a bug.
READ_ONLY = {
	device.CMD_CONNECT,
	device.CMD_EXIT,
	device.CMD_AUTH,
	device.CMD_OPTIONS_RRQ,
	device.CMD_GET_FREE_SIZES,
	device.CMD_PREPARE_BUFFER,
	device.CMD_READ_BUFFER,
	device.CMD_FREE_DATA,
}


def zk_time(dt):
	return ((((dt.year - 2000) * 12 + dt.month - 1) * 31 + dt.day - 1) * 24 + dt.hour) * 3600 + (
		dt.minute * 60 + dt.second
	)


def record40(user_id, raw_time, punch=0, verify=1):
	return pack("<H24sBIB8s", 1, user_id.encode(), verify, raw_time, punch, b"")


def user72(uid, user_id, name):
	return pack("<HB8s24sIx7sx24s", uid, 0, b"", name.encode(), 0, b"1", user_id.encode())


def table(records, size):
	return pack("<I", size * len(records)) + b"".join(records)


class FakeDevice:
	"""A ZK device on localhost that serves a user table and an attendance log, and records every
	command it receives. chunked: answer buffer reads with PREPARE_DATA + DATA frames + ACK."""

	def __init__(
		self, users=b"", log=b"", n_users=0, n_punches=0, serial="SN1", comm_key=0, chunked=True, mute=False
	):
		self.users, self.log, self.n_users, self.n_punches = users, log, n_users, n_punches
		self.serial, self.comm_key, self.chunked, self.mute = serial, comm_key, chunked, mute
		self.commands = []
		self.server = socket.create_server(("127.0.0.1", 0))
		self.port = self.server.getsockname()[1]
		self.thread = threading.Thread(target=self._serve, daemon=True)
		self.thread.start()

	def close(self):
		self.server.close()

	def _frame(self, command, data=b"", session=7, reply=0):
		body = pack("<HHHH", command, 0, session, reply) + data
		body = pack("<HHHH", command, device.checksum(body), session, reply) + data
		return device._MAGIC + pack("<I", len(body)) + body

	def _serve(self):
		try:
			conn, _ = self.server.accept()
		except OSError:
			return
		with conn:
			buffer, authed = b"", self.comm_key == 0
			while True:
				head = self._read(conn, 8)
				if head is None:
					return
				body = self._read(conn, unpack_from("<I", head, 4)[0])
				command, check, _session, reply = unpack_from("<HHHH", body)
				assert device.checksum(body[:2] + b"\0\0" + body[4:]) == check, "bad checksum"
				data = body[8:]
				self.commands.append(command)
				if self.mute:
					continue
				send = lambda c, d=b"", r=reply: conn.sendall(self._frame(c, d, reply=r))  # noqa: E731
				if command == device.CMD_CONNECT:
					send(device.CMD_ACK_OK if authed else device.CMD_ACK_UNAUTH)
				elif command == device.CMD_AUTH:
					authed = data == device.comm_key_token(self.comm_key, 7)
					send(device.CMD_ACK_OK if authed else device.CMD_ACK_UNAUTH)
				elif not authed:
					send(device.CMD_ACK_UNAUTH)
				elif command == device.CMD_OPTIONS_RRQ:
					send(device.CMD_ACK_OK, f"~SerialNumber={self.serial}\0".encode())
				elif command == device.CMD_GET_FREE_SIZES:
					fields = [0] * 20
					fields[4], fields[8] = self.n_users, self.n_punches
					send(device.CMD_ACK_OK, pack("<20i", *fields))
				elif command == device.CMD_PREPARE_BUFFER:
					_, what, _fct, _ext = unpack_from("<bhii", data)
					buffer = self.users if what == device.CMD_USERTEMP_RRQ else self.log
					send(device.CMD_ACK_OK, b"\0" + pack("<I", len(buffer)) + b"\0" * 4)
				elif command == device.CMD_READ_BUFFER:
					start, size = unpack_from("<ii", data)
					chunk = buffer[start : start + size]
					if self.chunked:
						send(device.CMD_PREPARE_DATA, pack("<I", len(chunk)))
						for i in range(0, len(chunk), 1000):
							send(device.CMD_DATA, chunk[i : i + 1000])
						send(device.CMD_ACK_OK)
					else:
						send(device.CMD_DATA, chunk)
				elif command in (device.CMD_FREE_DATA, device.CMD_EXIT):
					send(device.CMD_ACK_OK)
					if command == device.CMD_EXIT:
						return
				else:
					send(device.CMD_ACK_OK)

	@staticmethod
	def _read(conn, size):
		data = b""
		while len(data) < size:
			part = conn.recv(size - len(data))
			if not part:
				return None
			data += part
		return data


@pytest.fixture
def fake():
	devices = []

	def make(**kwargs):
		d = FakeDevice(**kwargs)
		devices.append(d)
		return d

	yield make
	for d in devices:
		d.close()


def office_log(n):
	return table(
		[record40(str(i % 50 + 1), zk_time(datetime(2026, 1 + i % 10, 1 + i % 28, 8))) for i in range(n)], 40
	)


@pytest.mark.parametrize("chunked", [True, False])
def test_pull_reads_users_and_log_and_sends_only_read_commands(fake, chunked):
	n = 5000  # 200 KB: several 64 KB chunks
	users = table([user72(1, "1001", "Sara"), user72(2, "1002", "Omar")], 72)
	d = fake(users=users, log=office_log(n), n_users=2, n_punches=n, chunked=chunked)
	result = device.read_punches("127.0.0.1", d.port)
	assert result.serial == "SN1" and result.total == n and len(result.punches) == n and result.skipped == 0
	assert device.read_users("127.0.0.1", fake(users=users, n_users=2).port) == [
		device.DeviceUser("1001", "Sara"),
		device.DeviceUser("1002", "Omar"),
	]
	assert set(d.commands) <= READ_ONLY
	assert d.commands[-1] == device.CMD_EXIT


def test_period_is_applied_on_the_worker_thread(fake):
	d = fake(log=office_log(1000), n_punches=1000)
	result = device.read_punches("127.0.0.1", d.port, period=(date(2026, 3, 1), date(2026, 3, 31)))
	assert result.total == 1000
	assert result.punches and all(p.timestamp.month == 3 for p in result.punches)


def test_comm_key(fake):
	d = fake(comm_key=123456)
	assert device.probe("127.0.0.1", d.port, comm_key=123456).serial == "SN1"
	with pytest.raises(device.DeviceError) as e:
		device.probe("127.0.0.1", fake(comm_key=123456).port, comm_key=1)
	assert e.value.reason == "comm_key"


def test_comm_key_token_known_values():
	# Checked against the token devices accept; the key's bits are reversed and scrambled with "ZKSO".
	assert device.comm_key_token(0, 0).hex() == "617d3279"
	assert device.comm_key_token(123, 0x1234).hex() == "61a3326b"
	assert device.comm_key_token(999999, 40000).hex() == "228132f5"


def test_checksum_is_ones_complement():
	assert device.checksum(pack("<HHHH", 1000, 0, 0, 0)) == 0xFC17  # what a device accepts for connect


def test_refused_connection_is_unreachable():
	free = socket.create_server(("127.0.0.1", 0))
	port = free.getsockname()[1]
	free.close()
	with pytest.raises(device.DeviceError) as e:
		device.probe("127.0.0.1", port)
	assert e.value.reason == "unreachable"


def test_cancel_works_while_the_device_does_not_answer_the_connect(fake):
	d = fake(mute=True)
	errors = []

	def pull():
		try:
			device.probe("127.0.0.1", d.port, timeout=30)
		except Exception as e:
			errors.append(e)

	thread = threading.Thread(target=pull)
	thread.start()
	while not device._active:
		time.sleep(0.01)
	time.sleep(0.1)
	device.cancel_all()
	thread.join(5)
	assert not thread.is_alive()
	assert isinstance(errors[0], device.Cancelled)


def test_session_deadline(fake, monkeypatch):
	monkeypatch.setattr(device, "SESSION_DEADLINE", 0.3)
	with pytest.raises(device.DeviceError) as e:
		device.probe("127.0.0.1", fake(mute=True).port, timeout=30)
	assert e.value.reason == "timeout"


def test_size_limit(fake, monkeypatch):
	monkeypatch.setattr(device, "MAX_BYTES", 50_000)
	d = fake(log=office_log(5000), n_punches=5000)
	with pytest.raises(device.DeviceError) as e:
		device.read_punches("127.0.0.1", d.port)
	assert e.value.reason == "too_much"


def test_decode_time_matches_the_device_format():
	assert device.decode_time(zk_time(datetime(2026, 11, 12, 8, 40, 18))) == datetime(2026, 11, 12, 8, 40, 18)
	feb_31 = ((26 * 12 + 1) * 31 + 30) * 86400
	assert device.decode_time(feb_31) is None


def test_impossible_and_future_dates_are_left_out_not_fatal():
	feb_31 = ((26 * 12 + 1) * 31 + 30) * 86400
	data = table(
		[
			record40("7", zk_time(datetime(2026, 11, 1, 8))),
			record40("7", feb_31),  # one bad record must not fail the whole pull
			record40("8", 0xFFFFFFFF),  # year 2133
			record40("9", zk_time(datetime(2026, 11, 1, 17)), punch=1),
		],
		40,
	)
	punches, records, skipped = device.parse_attendance(data, 4, {}, "SN1", NOW)
	assert [(p.user_id, p.timestamp.hour, p.punch) for p in punches] == [("7", 8, 0), ("9", 17, 1)]
	assert records == 4 and skipped == 2


def test_old_8_byte_records_use_the_user_list():
	data = table([pack("<HBIB", 3, 1, zk_time(datetime(2026, 11, 1, 8)), 0)], 8)
	punches, _, _ = device.parse_attendance(data, 1, {3: "1001"}, "SN1", NOW)
	assert punches[0].user_id == "1001"


def test_16_byte_records():
	data = table([pack("<IIBB6x", 1005, zk_time(datetime(2026, 11, 1, 8)), 1, 1)], 16)
	punches, _, _ = device.parse_attendance(data, 1, {}, "SN1", NOW)
	assert (punches[0].user_id, punches[0].punch) == ("1005", 1)


def test_record_size_comes_from_the_byte_total_not_a_stale_count():
	# 10 records of 16 bytes, but the count of 8 was read before 2 more punches were made, so
	# 160 bytes / 8 = 20 suggests no size; 16 bytes gives the count closest to 8.
	records = [pack("<IIBB6x", 1000 + i, zk_time(datetime(2026, 11, 1, 8, i)), 1, 0) for i in range(10)]
	punches, total, _ = device.parse_attendance(table(records, 16), 8, {}, "SN1", NOW)
	assert total == 10 and [p.user_id for p in punches] == [str(1000 + i) for i in range(10)]


def test_unknown_record_size_is_an_error():
	with pytest.raises(device.DeviceError):
		device.parse_attendance(pack("<I", 7) + b"x" * 7, 1, {}, "SN1", NOW)


def test_parsing_is_linear():
	data = table([record40(str(i % 500), zk_time(datetime(2026, 1, 1, 8))) for i in range(200_000)], 40)
	started = time.monotonic()
	punches, _, _ = device.parse_attendance(data, 200_000, {}, "SN1", NOW)
	assert len(punches) == 200_000
	assert time.monotonic() - started < 5


def test_parse_users_72_and_28_bytes():
	users, uids = device.parse_users(table([user72(5, "1005", "Sa\x02ra")], 72), 1)
	assert users == [device.DeviceUser("1005", "Sara")] and uids == {5: "1005"}
	user28 = pack("<HB5s8sIxBhI", 6, 0, b"", b"Omar", 0, 1, 0, 1006)
	users, uids = device.parse_users(table([user28], 28), 1)
	assert users == [device.DeviceUser("1006", "Omar")] and uids == {6: "1006"}


def test_clean_removes_control_characters():
	assert device.clean(" Sa\x02ra \x7f") == "Sara"
	assert device.clean(None) == ""


def test_device_errors_are_translated(monkeypatch):
	from zk_pull_desktop import i18n
	from zk_pull_desktop.worker import error_message

	monkeypatch.setattr(i18n, "_current", "ar")
	assert error_message(device.DeviceError("timeout")) == i18n.TEXTS["err_timeout"][1]
	assert (
		error_message(device.DeviceError("unreachable", "Connection refused"))
		== i18n.TEXTS["err_unreachable"][1]
	)
	assert error_message(device.Cancelled()) == i18n.TEXTS["cancelled"][1]


def test_old_8_byte_records_of_a_deleted_user_are_kept_apart():
	# uid 7 has no user any more; "7" is another employee's ID, who must not get these punches.
	data = table([pack("<HBIB", 7, 1, zk_time(datetime(2026, 11, 1, 8)), 0)], 8)
	punches, _, _ = device.parse_attendance(data, 1, {3: "7"}, "SN1", NOW)
	assert punches[0].user_id == "uid:7"


def test_an_address_older_versions_saved_unchecked_is_not_dialled():
	for bad in ("192.168.100.056", "device.local", "8.8.8.8"):
		with pytest.raises(device.DeviceError) as e:
			device.probe(bad, 4370)
		assert e.value.reason == "invalid_ip"
