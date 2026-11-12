"""Run device I/O off the UI thread. Results come back on the UI thread; the database is only used there."""

import logging
import socket

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from .i18n import tr

log = logging.getLogger(__name__)

_jobs = set()  # keeps each _Job alive until its result is delivered


class _Job(QObject):
	finished = Signal(bool, object)

	def __init__(self, on_done, on_failed):
		super().__init__()  # created on the UI thread, so _deliver runs there
		self.on_done = on_done
		self.on_failed = on_failed
		self.finished.connect(self._deliver)

	@Slot(bool, object)
	def _deliver(self, ok, value):
		_jobs.discard(self)
		(self.on_done if ok else self.on_failed)(value)


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


def run_in_background(fn, *args, on_done, on_failed, **kwargs):
	"""Call fn(*args, **kwargs) on a worker thread; then on_done(result) or on_failed(message) on the UI thread."""
	job = _Job(on_done, on_failed)
	_jobs.add(job)
	QThreadPool.globalInstance().start(_Task(job, fn, args, kwargs))


def error_message(e: Exception) -> str:
	"""A message HR can act on, instead of a Python exception."""
	text = str(e)
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
