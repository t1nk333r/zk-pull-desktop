import logging
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QDate, QModelIndex, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
	QButtonGroup,
	QComboBox,
	QDateEdit,
	QFileDialog,
	QHBoxLayout,
	QHeaderView,
	QLabel,
	QMessageBox,
	QPushButton,
	QRadioButton,
	QTableView,
	QVBoxLayout,
	QWidget,
)

from . import device as zk
from . import export
from .i18n import is_rtl, isolate, punch_label, tr, verify_label
from .periods import PERIODS, period_range
from .store import PunchRow, Store
from .worker import run_in_background

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

		self.device = QComboBox()
		self.period = QComboBox()
		for p in PERIODS:
			self.period.addItem(tr(f"period_{p}"), p)
		self.start = self._date_edit()
		self.end = self._date_edit()
		self.pull_button = QPushButton(tr("pull"))
		self.pull_button.setDefault(True)
		self.xlsx = QRadioButton("Excel (.xlsx)")
		self.csv = QRadioButton("CSV")
		self.fmt_group = QButtonGroup(self)
		self.fmt_group.addButton(self.xlsx)
		self.fmt_group.addButton(self.csv)
		(self.csv if store.get("format", "xlsx") == "csv" else self.xlsx).setChecked(True)
		self.export_button = QPushButton(tr("export"))

		self.model = PunchModel()
		self.table = QTableView()
		self.table.setModel(self.model)
		self.table.setAlternatingRowColors(True)
		self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
		self.table.verticalHeader().setVisible(False)
		self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
		self.table.horizontalHeader().setStretchLastSection(True)
		self.summary = QLabel()

		filters = QHBoxLayout()
		for label, widget in (
			(tr("device"), self.device),
			(tr("period"), self.period),
			(tr("from"), self.start),
			(tr("to"), self.end),
		):
			filters.addWidget(QLabel(label))
			filters.addWidget(widget)
		filters.addStretch()
		filters.addWidget(self.pull_button)

		actions = QHBoxLayout()
		actions.addWidget(self.summary, 1)
		actions.addWidget(QLabel(tr("format")))
		actions.addWidget(self.xlsx)
		actions.addWidget(self.csv)
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
		self.pull_button.clicked.connect(self.pull)
		self.export_button.clicked.connect(self.export)
		self.fmt_group.buttonClicked.connect(lambda _: store.set("format", self.fmt()))

	def _date_edit(self):
		edit = QDateEdit()
		edit.setCalendarPopup(True)
		edit.setDisplayFormat("yyyy-MM-dd")
		edit.setLayoutDirection(Qt.LayoutDirection.LeftToRight)  # 2026-11-01, not 01-11-2026, in Arabic
		edit.calendarWidget().setFirstDayOfWeek(Qt.DayOfWeek.Sunday)
		return edit

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
		start, end = self.range()
		serials = None  # all devices: every punch, including ones from devices removed since
		if self.device.currentData() is not None:
			serials = [d.serial for d in self.selected_devices() if d.serial]
		return self.store.punches(start, end, serials)

	def refresh(self):
		start, end = self.range()
		if start > end:
			self.model.set_rows([])
			self.summary.setText("")
			return
		self.model.set_rows(self._rows())
		text = tr("shown", count=len(self.model.rows), start=f"{start:%Y-%m-%d}", end=f"{end:%Y-%m-%d}")
		unnamed = len({p.user_id for p in self.model.rows if not p.name})
		if unnamed:
			text += "  ·  " + tr("unnamed_hint", count=unnamed)
		self.summary.setText(text)

	# Pull

	def pull(self):
		self.queue = self.selected_devices()
		if not self.queue:
			QMessageBox.information(self, tr("app_title"), tr("no_devices"))
			return
		self.pull_button.setEnabled(False)
		self._pull_next()

	def _pull_next(self):
		if not self.queue:
			self.pull_button.setEnabled(True)
			self.refresh()
			return
		d = self.queue[0]
		self.status(tr("pulling", device=d.name))
		run_in_background(
			zk.read_punches, d.ip, d.port, d.comm_key, on_done=self._pulled, on_failed=self._pull_failed
		)

	def _pulled(self, result):
		d = self.queue.pop(0)
		serial, punches = result
		new = self.store.add_punches(punches)
		self.store.mark_pulled(d.id, serial, datetime.now())
		log.info("Pulled %s (%s): %d punches, %d new", d.name, serial, len(punches), new)
		self.status(tr("pull_done", device=d.name, total=len(punches), new=new))
		self._pull_next()

	def _pull_failed(self, message):
		d = self.queue.pop(0)
		self.status(tr("pull_failed", device=d.name, error=message))
		QMessageBox.warning(self, tr("error"), tr("pull_failed", device=d.name, error=message))
		self._pull_next()

	# Export

	def export(self):
		start, end = self.range()
		rows = self._rows() if start <= end else []
		if not rows:
			QMessageBox.information(self, tr("app_title"), tr("nothing_to_export"))
			return
		fmt = self.fmt()
		layout = self.store.get("layout", "log")
		folder = Path(self.store.get("export_folder") or Path.home())
		suggested = str(folder / export.default_filename(start, end, layout, fmt))
		filters = "Excel (*.xlsx)" if fmt == "xlsx" else "CSV (*.csv)"
		path, _ = QFileDialog.getSaveFileName(self, tr("export"), suggested, filters)
		if not path:
			return
		path = Path(path)
		if path.suffix.lower() != f".{fmt}":
			path = path.with_name(path.name + f".{fmt}")
		try:
			count = export.write(path, rows, fmt, layout, self.store.get("header_language", "en"))
		except OSError as e:
			log.exception("Export to %s failed", path)
			QMessageBox.warning(self, tr("error"), tr("export_failed", error=e.strerror or e))
			return
		self.store.set("export_folder", str(path.parent))
		box = QMessageBox(self)
		box.setWindowTitle(tr("app_title"))
		box.setText(tr("exported", count=count, path=path))
		open_button = box.addButton(tr("open_folder"), QMessageBox.ButtonRole.ActionRole)
		box.addButton(QMessageBox.StandardButton.Ok)
		box.exec()
		if box.clickedButton() is open_button:
			QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))
