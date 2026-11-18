"""Run device I/O off the UI thread. Results come back on the UI thread; the database is only used there."""

import logging

import shiboken6
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from .i18n import tr

log = logging.getLogger(__name__)

_jobs = set()  # keeps each _Job alive until its result is delivered
# A pool of our own: Qt waits for the global pool when the app quits, which would keep a hidden
# process running for as long as a device socket takes to time out.
_pool = QThreadPool()


def _owner(callback) -> QObject | None:
	"""The widget a callback is a method of, also through functools.partial."""
	owner = getattr(getattr(callback, "func", callback), "__self__", None)
	return owner if isinstance(owner, QObject) else None


class _Job(QObject):
	finished = Signal(bool, object)

	def __init__(self, on_done, on_failed, device):
		super().__init__()  # created on the UI thread, so _deliver runs there
		self.on_done = on_done
		self.on_failed = on_failed
		self.device = device
		self.finished.connect(self._deliver)

	@Slot(bool, object)
	def _deliver(self, ok, value):
		_jobs.discard(self)
		callback = self.on_done if ok else self.on_failed
		owner = _owner(callback)
		if owner is not None and not shiboken6.isValid(owner):
			log.warning("Result of a background task dropped: its window was closed")
			return
		try:
			callback(value)
		except Exception as e:
			# Saving a result can fail (disk full); the caller must still hear about it, or a
			# multi-device pull would stop half-way with its Cancel button still showing.
			log.exception("Handling the result of a background task failed")
			if ok:
				self.on_failed(error_message(e))
			else:
				raise


class _Task(QRunnable):
	def __init__(self, job, fn, args, kwargs):
		super().__init__()
		self.job, self.fn, self.args, self.kwargs = job, fn, args, kwargs

	def run(self):
		try:
			result = self.fn(*self.args, **self.kwargs)
		except Exception as e:
			log.exception("Background task %s failed", getattr(self.fn, "__name__", self.fn))
			self.job.finished.emit(False, error_message(e))
		else:
			self.job.finished.emit(True, result)


def run_in_background(fn, *args, on_done, on_failed, device=True, **kwargs):
	"""Call fn(*args, **kwargs) on a worker thread; then on_done(result) or on_failed(message) on the UI thread.

	device=False for work that does not talk to a device (update checks), so it never blocks a pull.
	"""
	job = _Job(on_done, on_failed, device)
	_jobs.add(job)
	_pool.start(_Task(job, fn, args, kwargs))


def busy() -> bool:
	"""True while a device operation is running. The device answers one connection at a time."""
	return any(job.device for job in _jobs)


def window_busy() -> bool:
	"""True while a task whose result goes to a window is running, such as a names-file import.
	Rebuilding the window then would drop that result."""
	return any(_owner(job.on_done) is not None for job in _jobs)


def running() -> bool:
	"""True while any background task is running."""
	return bool(_jobs)


DEVICE_MESSAGES = {
	"unreachable": "err_unreachable",
	"comm_key": "err_comm_key",
	"timeout": "err_timeout",
	"closed": "err_closed",
	"too_much": "err_too_much",
	"no_serial": "err_no_serial",
	"invalid_ip": "invalid_ip",
}


def error_message(e: Exception) -> str:
	"""A message HR can act on, in their language, instead of a Python exception."""
	# Imported here: device and updater import nothing from the UI side.
	from .device import Cancelled, DeviceError
	from .updater import UpdateError

	if isinstance(e, Cancelled):
		return tr("cancelled")
	if isinstance(e, DeviceError):
		if e.reason in DEVICE_MESSAGES:
			return tr(DEVICE_MESSAGES[e.reason])
		return tr("err_device", detail=e.detail or e.reason)
	if isinstance(e, UpdateError):
		return tr(f"upd_{e.reason}", **e.values)
	if isinstance(e, OSError):
		return f"{e.strerror or e}"
	return str(e) or type(e).__name__
