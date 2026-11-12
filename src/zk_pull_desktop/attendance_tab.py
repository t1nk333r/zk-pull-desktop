import logging
import re
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QDate, QModelIndex, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
	QButtonGroup,
	QCheckBox,
	QComboBox,
	QDateEdit,
	QFileDialog,
	QHBoxLayout,
	QHeaderView,
	QLabel,
	QLineEdit,
	QMessageBox,
	QPushButton,
	QRadioButton,
	QTableView,
	QVBoxLayout,
	QWidget,
)

from . import device as zk
from . import export, messages
from .i18n import is_rtl, isolate, punch_label, tr, verify_label
from .periods import PERIODS, period_range
from .store import PunchRow, Store
from .worker import busy, run_in_background

log = logging.getLogger(__name__)

COLUMNS = ("col_user_id", "col_name", "col_date", "col_time", "col_punch", "col_verify", "col_device")


_ROOT = QModelIndex()


class PunchModel(QAbstractTableModel):
	def __init__(self):
		super().__init__()
		self.rows: list[PunchRow] = []

	def set_rows(self, rows):
		self.beginResetModel()
		self.rows = rows
		self.endResetModel()

	def rowCount(self, parent=_ROOT):
		return 0 if parent.isValid() else len(self.rows)

	def columnCount(self, parent=_ROOT):
		return 0 if parent.isValid() else len(COLUMNS)

	def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
		if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
			return tr(COLUMNS[section])
		return None

	def data(self, index, role=Qt.ItemDataRole.DisplayRole):
		if role != Qt.ItemDataRole.DisplayRole:
			return None
		p = self.rows[index.row()]
		return (
			p.user_id,
			isolate(p.name) if is_rtl() else p.name,
			f"{p.timestamp:%Y-%m-%d}",
			f"{p.timestamp:%H:%M:%S}",
			punch_label(p.punch),
			verify_label(p.verify),
			isolate(p.device) if is_rtl() else p.device,
		)[index.column()]


def _qdate(d: date):
	return QDate(d.year, d.month, d.day)


class AttendanceTab(QWidget):
	def __init__(self, store: Store, status):
		super().__init__()
		self.store = store
		self.status = status  # callable(message) that shows a line in the status bar
		self.queue = []  # devices still to pull in the current run
		# (device name, new punches or None on failure, punches in the period or the error) per device
		self.results = []
		self.pull_range = (date.today(), date.today())
		self.notes = []

		self.device = QComboBox()
		self.last_pull = QLabel()
		self.last_pull.setEnabled(False)  # greyed: information, not a control
		self.period = QComboBox()
		for p in PERIODS:
			self.period.addItem(tr(f"period_{p}"), p)
		self.start = self._date_edit()
		self.end = self._date_edit()
		self.search = QLineEdit()
		self.search.setPlaceholderText(tr("search_punches"))
		self.search.setClearButtonEnabled(True)
		self.pull_button = QPushButton(tr("pull") + "  (F5)")
		self.layout_choice = QComboBox()
		self.layout_choice.addItem(tr("layout_log_short"), "log")
		self.layout_choice.addItem(tr("layout_daily_short"), "daily")
		self.layout_choice.setToolTip(tr("layout_log") + "\n" + tr("layout_daily"))
		self.layout_choice.setCurrentIndex(max(self.layout_choice.findData(store.get("layout", "log")), 0))
		self.xlsx = QRadioButton("Excel (.xlsx)")
		self.csv = QRadioButton("CSV")
		self.fmt_group = QButtonGroup(self)
		self.fmt_group.addButton(self.xlsx)
		self.fmt_group.addButton(self.csv)
		(self.csv if store.get("format", "xlsx") == "csv" else self.xlsx).setChecked(True)
		self.export_button = QPushButton(tr("export") + "  (Ctrl+E)")
		self.open_after = QCheckBox(tr("open_after_export"))
		self.open_after.setChecked(store.get("open_after_export", "1") == "1")

		self.model = PunchModel()
		self.table = QTableView()
		self.table.setModel(self.model)
		self.table.setAlternatingRowColors(True)
		self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
		self.table.verticalHeader().setVisible(False)
		self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
		self.table.horizontalHeader().setStretchLastSection(True)
		self.summary = QLabel()
		self.summary.setWordWrap(True)
		for label in (self.summary, self.last_pull):
			label.setTextFormat(Qt.TextFormat.PlainText)

		filters = QHBoxLayout()
		filters.addWidget(QLabel(tr("device")))
		filters.addWidget(self.device)
		filters.addWidget(self.last_pull)
		filters.addSpacing(12)
		for label, widget in ((tr("period"), self.period), (tr("from"), self.start), (tr("to"), self.end)):
			filters.addWidget(QLabel(label))
			filters.addWidget(widget)
		filters.addSpacing(12)
		filters.addWidget(self.search, 1)
		filters.addWidget(self.pull_button)

		actions = QHBoxLayout()
		actions.addWidget(self.summary, 1)
		actions.addSpacing(24)
		actions.addWidget(QLabel(tr("export_layout")))
		actions.addWidget(self.layout_choice)
		actions.addSpacing(12)
		actions.addWidget(QLabel(tr("format")))
		actions.addWidget(self.xlsx)
		actions.addWidget(self.csv)
		actions.addSpacing(12)
		actions.addWidget(self.open_after)
		actions.addWidget(self.export_button)

		layout = QVBoxLayout(self)
		layout.addLayout(filters)
		layout.addWidget(self.table, 1)
		layout.addLayout(actions)

		self.reload_devices()
		self.period.setCurrentIndex(PERIODS.index(store.get("period", "this_month")))
		self._apply_period()
		self.period.currentIndexChanged.connect(self._apply_period)
		self.start.dateChanged.connect(self._dates_edited)
		self.end.dateChanged.connect(self._dates_edited)
		self.device.currentIndexChanged.connect(self.refresh)
		self.search.textChanged.connect(self.refresh)
		self.pull_button.clicked.connect(self._pull_clicked)
		self.export_button.clicked.connect(self.export)
		self.open_after.toggled.connect(lambda on: store.set("open_after_export", "1" if on else "0"))
		self.fmt_group.buttonClicked.connect(lambda _: store.set("format", self.fmt()))
		self.layout_choice.currentIndexChanged.connect(
			lambda: store.set("layout", self.layout_choice.currentData())
		)

	def _date_edit(self):
		edit = QDateEdit()
		# Left to right before the format is set: Qt reorders the fields of a right-to-left date edit,
		# so in Arabic it would show 01-11-2026.
		edit.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
		edit.setCalendarPopup(True)
		edit.setDisplayFormat("yyyy-MM-dd")
		edit.calendarWidget().setFirstDayOfWeek(Qt.DayOfWeek.Sunday)
		return edit

	def showEvent(self, event):
		super().showEvent(event)
		# "Today" must move on when the app stays open past midnight.
		if self.period.currentData() != "custom":
			self._apply_period()

	def fmt(self):
		return "csv" if self.csv.isChecked() else "xlsx"

	def range(self) -> tuple[date, date]:
		return self.start.date().toPython(), self.end.date().toPython()

	def reload_devices(self):
		current = self.device.currentData()
		self.device.blockSignals(True)
		self.device.clear()
		self.device.addItem(tr("all_devices"), None)
		for d in self.store.devices():
			self.device.addItem(d.name, d.id)
		index = self.device.findData(current)
		self.device.setCurrentIndex(max(index, 0))
		self.device.blockSignals(False)
		self.refresh()

	def selected_devices(self):
		devices = self.store.devices()
		chosen = self.device.currentData()
		return [d for d in devices if chosen is None or d.id == chosen]

	def _apply_period(self):
		period = self.period.currentData()
		self.store.set("period", period)
		if period == "custom":
			return
		start, end = period_range(period, date.today())
		for edit, value in ((self.start, start), (self.end, end)):
			edit.blockSignals(True)
			edit.setDate(_qdate(value))
			edit.blockSignals(False)
		self.refresh()

	def _dates_edited(self):
		self.period.blockSignals(True)
		self.period.setCurrentIndex(PERIODS.index("custom"))
		self.period.blockSignals(False)
		self.store.set("period", "custom")
		self.refresh()

	def _rows(self):
		"""The punches shown, and exported: period, device and search applied."""
		start, end = self.range()
		serials = None  # all devices: every punch, including ones from devices removed since
		if self.device.currentData() is not None:
			serials = self.store.serials([self.device.currentData()])  # every serial it has reported
		rows = self.store.punches(start, end, serials)
		needle = self.search.text().strip().casefold()
		if needle:
			rows = [p for p in rows if needle in f"{p.user_id} {p.name} {p.department}".casefold()]
		return rows

	def _show_last_pull(self):
		devices = self.selected_devices()
		if not devices:
			self.last_pull.setText("")
			return
		pulls = [d.last_pull for d in devices]
		# For all devices, the oldest one: that is how current the whole view is.
		when = "" if "" in pulls else min(pulls)
		self.last_pull.setText(tr("last_pull_label", when=when[:16]) if when else tr("never_pulled"))

	def refresh(self):
		self._show_last_pull()
		start, end = self.range()
		if start > end:
			self.model.set_rows([])
			self.summary.setText(tr("from_after_to"))
			return
		self.model.set_rows(self._rows())
		if not self.store.devices() and not self.model.rows:
			self.summary.setText(tr("empty_no_devices"))
			return
		if not self.model.rows:
			self.summary.setText(tr("empty_no_punches"))
			return
		text = tr("shown", count=len(self.model.rows), start=f"{start:%Y-%m-%d}", end=f"{end:%Y-%m-%d}")
		unnamed = len({p.user_id for p in self.model.rows if not p.name})
		if unnamed:
			text += "  ·  " + tr("unnamed_hint", count=unnamed)
		self.summary.setText(text)

	# Pull

	def _pull_clicked(self):
		if self.queue:
			self.cancel_pull()
		else:
			self.pull()

	def pull(self):
		if busy():
			self.status(tr("busy"))
			return
		if self.period.currentData() != "custom":
			self._apply_period()
		self.queue = self.selected_devices()
		self.results = []
		self.notes = []  # warnings that are not failures (records left out)
		# Only punches in the period chosen are saved; fixed now, so editing the dates mid-pull
		# does not change what this pull keeps.
		self.pull_range = self.range()
		if not self.queue:
			messages.info(self, tr("app_title"), tr("no_devices"))
			return
		self.pull_button.setText(tr("cancel"))
		self._pull_next()

	def cancel_pull(self):
		"""Stop the device being read and skip the rest; what was already saved stays."""
		self.queue = self.queue[:1]  # the current one ends with Cancelled and is removed then
		zk.cancel_all()

	def _pull_next(self):
		if not self.queue:
			self.pull_button.setText(tr("pull") + "  (F5)")
			self.refresh()
			self._report()
			return
		d = self.queue[0]
		self.status(tr("pulling", device=d.name))
		run_in_background(
			zk.read_punches, d.ip, d.port, d.comm_key, on_done=self._pulled, on_failed=self._pull_failed
		)

	def _accept_serial(self, d, serial) -> str:
		"""An error message if the punches must not be saved under this device, else ""."""
		owner = self.store.serial_owner(serial)
		if owner is not None and owner != d.id:
			# Another device's serial at this IP: addresses swapped, or a device pretending.
			other = self.store.device(owner)
			return tr("serial_taken", serial=serial, other=other.name if other else owner)
		known = self.store.serials([d.id])
		if known and serial not in known:
			# A new mainboard brings a new serial; so does a different device at this address.
			question = tr("serial_changed", device=d.name, old=d.serial or known[-1], new=serial)
			if not messages.ask(self, tr("app_title"), question):
				return tr("serial_refused", serial=serial)
		return ""

	def _pulled(self, result: zk.PullResult):
		d = self.queue[0]
		refused = self._accept_serial(d, result.serial)
		self.queue.pop(0)
		if refused:
			log.warning("Pull from %s: %s", d.name, refused)
			self.results.append((d.name, None, refused))
			self._pull_next()
			return
		start, end = self.pull_range
		in_period = [p for p in result.punches if start <= p.timestamp.date() <= end]
		new = self.store.add_punches(in_period)
		self.store.mark_pulled(d.id, result.serial, datetime.now())
		log.info(
			"Pulled %s (%s): %d punches on the device, %d in %s..%s, %d new",
			d.name, result.serial, len(result.punches), len(in_period), start, end, new,
		)  # fmt: skip
		if result.skipped:
			self.notes.append(tr("skipped_records", device=d.name, count=result.skipped))
		self.results.append((d.name, new, len(in_period)))
		self._pull_next()

	def _pull_failed(self, message):
		# No dialog here: with several devices, one that is off must not stop the others.
		d = self.queue.pop(0)
		log.warning("Pull from %s failed: %s", d.name, message)
		self.results.append((d.name, None, message))
		self._pull_next()

	def _report(self):
		ok = [r for r in self.results if r[1] is not None]
		failed = [r for r in self.results if r[1] is None]
		start, end = (f"{d:%Y-%m-%d}" for d in self.pull_range)
		if len(self.results) == 1 and ok:
			name, new, kept = ok[0]
			self.status(tr("pull_done_one", device=name, kept=kept, new=new, start=start, end=end))
		elif ok:
			self.status(
				tr(
					"pull_summary", ok=len(ok), total=len(self.results), kept=sum(r[2] for r in ok),
					new=sum(r[1] for r in ok), start=start, end=end,
				)
			)  # fmt: skip
		else:
			self.status("")
		problems = [f"• {name}: {error}" for name, _new, error in failed] + [
			f"• {note}" for note in self.notes
		]
		if problems:
			messages.warn(
				self,
				tr("error") if failed else tr("app_title"),
				tr("pull_failures", devices="\n".join(problems)),
			)

	# Export

	def _export_name(self, start, end, layout, fmt):
		name = export.default_filename(start, end, layout, fmt)
		if self.device.currentData() is not None:
			device = re.sub(r"[^\w\-]+", "_", self.device.currentText()).strip("_")
			if device:
				name = name.replace("_", f"_{device}_", 1)
		return name

	def export(self):
		start, end = self.range()
		if start > end:
			messages.info(self, tr("app_title"), tr("from_after_to"))
			return
		rows = self._rows()
		if not rows:
			messages.info(self, tr("app_title"), tr("nothing_to_export"))
			return
		fmt = self.fmt()
		layout = self.layout_choice.currentData()
		folder = Path(self.store.get("export_folder") or Path.home())
		suggested = str(folder / self._export_name(start, end, layout, fmt))
		filters = "Excel (*.xlsx)" if fmt == "xlsx" else "CSV (*.csv)"
		path, _ = QFileDialog.getSaveFileName(self, tr("export"), suggested, filters)
		if not path:
			return
		path = Path(path)
		if path.suffix.lower() != f".{fmt}":
			path = path.with_name(path.name + f".{fmt}")
			# The save dialog asked about the name typed, not this one.
			if path.exists() and not messages.ask(self, tr("export"), tr("confirm_overwrite", path=path)):
				return
		try:
			count = export.write(path, rows, fmt, layout, self.store.get("header_language", "en"))
		except PermissionError:
			log.exception("Export to %s failed", path)
			messages.warn(self, tr("error"), tr("export_in_use", path=path))
			return
		except OSError as e:
			log.exception("Export to %s failed", path)
			messages.warn(self, tr("error"), tr("export_failed", error=e.strerror or e))
			return
		except Exception as e:  # never lose the window over one bad value
			log.exception("Export to %s failed", path)
			messages.warn(self, tr("error"), tr("export_failed", error=e))
			return
		self.store.set("export_folder", str(path.parent))
		log.info("Exported %d rows to %s", count, path)
		if self.open_after.isChecked() and QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
			self.status(tr("exported", count=count, path=path))
			return
		box = messages.box(self, QMessageBox.Icon.Information, tr("app_title"), "")
		box.setWindowTitle(tr("app_title"))
		box.setText(tr("exported", count=count, path=path))
		open_button = box.addButton(tr("open_folder"), QMessageBox.ButtonRole.ActionRole)
		box.addButton(QMessageBox.StandardButton.Ok)
		box.exec()
		if box.clickedButton() is open_button:
			QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))
