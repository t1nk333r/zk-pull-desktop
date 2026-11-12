import pytest

from zk_pull_desktop import device


class FakeSocket:
	closed = False

	def close(self):
		self.closed = True


class FakeZK:
	"""Times out mid-read, then fails CMD_EXIT, like a device whose stream is out of step."""

	last = None

	def __init__(self, *args, **kwargs):
		self._ZK__sock = FakeSocket()
		FakeZK.last = self

	def connect(self):
		return self

	def get_serialnumber(self):
		return "SN1"

	def get_attendance(self):
		raise TimeoutError("timed out")

	def disconnect(self):
		raise RuntimeError("TCP packet invalid")


def test_read_error_is_not_hidden_by_disconnect_and_socket_is_closed(monkeypatch):
	monkeypatch.setattr(device, "ZK", FakeZK)
	with pytest.raises(TimeoutError):
		device.read_punches("10.0.0.5")
	assert FakeZK.last._ZK__sock.closed


def test_clean_removes_control_characters():
	assert device.clean(" Sa\x02ra \x7f") == "Sara"
	assert device.clean(None) == ""
