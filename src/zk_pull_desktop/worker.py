"""Run device I/O off the UI thread. Results come back on the UI thread; the database is only used there."""

import logging
import socket

import shiboken6
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from .i18n import tr

log = logging.getLogger(__name__)

_jobs = set()  # keeps each _Job alive until its result is delivered
# A pool of our own: Qt waits for the global pool when the app quits, which would keep a hidden
# process running for as long as a device socket takes to time out.
_pool = QThreadPool()


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
		owner = getattr(callback, "__self__", None)
		if isinstance(owner, QObject) and not shiboken6.isValid(owner):
			log.warning("Result of a background task dropped: its window was closed")
			return
		callback(value)


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


def running() -> bool:
	"""True while any background task is running."""
	return bool(_jobs)


def error_message(e: Exception) -> str:
	"""A message HR can act on, instead of a Python exception."""
	from .device import Cancelled, DeviceError  # here: device imports nothing from the UI side

	text = str(e)
	if isinstance(e, Cancelled):
		return tr("cancelled")
	if isinstance(e, DeviceError):
		return tr("err_device", detail=text)
	if "Unauthenticated" in text:
		return tr("err_comm_key")
	if (
		isinstance(e, TimeoutError | socket.timeout | ConnectionError)
		or "timed out" in text
		or "can't reach" in text
	):
		return tr("err_unreachable")
	if isinstance(e, OSError):
		return tr("err_unreachable") + f" ({e.strerror or text})"
	return text or type(e).__name__
