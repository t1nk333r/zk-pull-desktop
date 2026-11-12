import csv
import logging
from pathlib import Path

from openpyxl import load_workbook
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
	QFileDialog,
	QHBoxLayout,
	QHeaderView,
	QInputDialog,
	QLineEdit,
	QMessageBox,
	QPushButton,
	QTableWidget,
	QTableWidgetItem,
	QVBoxLayout,
	QWidget,
)

from . import device as zk
from .i18n import tr
from .store import Person, Store
from .worker import busy, run_in_background

log = logging.getLogger(__name__)


HEADER_WORDS = ("id", "no", "code", "emp", "رقم", "كود", "الرقم", "الموظف")


def _csv_text(path: Path) -> str:
	"""UTF-8 first; Excel's "CSV (Comma delimited)" on Arabic Windows saves Windows-1256."""
	data = path.read_bytes()
	try:
		return data.decode("utf-8-sig")
	except UnicodeDecodeError:
		return data.decode("cp1256")


def _is_header(first, rest) -> bool:
	"""A first row is a header if it names its columns, or if it is the only one without a numeric ID."""
	cell = first[0].casefold() if first else ""
	if cell.isdigit():
		return False
	return any(word in cell for word in HEADER_WORDS) or any(r and r[0].isdigit() for r in rest)


def read_names_file(path: Path) -> dict[str, str]:
	"""Employee ID -> name from the first two columns of a CSV or XLSX file, skipping a header row."""
	if path.suffix.lower() == ".xlsx":
		wb = load_workbook(path, read_only=True, data_only=True)
		rows = [
			[("" if v is None else str(v)) for v in row[:2]] for row in wb.active.iter_rows(values_only=True)
		]
		wb.close()
	else:
		rows = [row[:2] for row in csv.reader(_csv_text(path).splitlines())]
	rows = [[cell.strip() for cell in row] for row in rows if any(cell.strip() for cell in row)]
	if rows and _is_header(rows[0], rows[1:]):
		rows = rows[1:]
	names = {}
	for row in rows:
		if len(row) < 2:
			continue
		user_id, name = row[0], row[1]
		if user_id.endswith(".0") and user_id[:-2].isdigit():  # Excel stored the ID as a number
			user_id = user_id[:-2]
		if user_id and name:
			names[user_id] = name
	return names


class PeopleTab(QWidget):
	ID, NAME, DEPARTMENT = range(3)

	def __init__(self, store: Store, status, on_change):
		super().__init__()
		self.store = store
		self.status = status
		self.on_change = on_change  # called after names change, so the Attendance tab can refresh

		self.search = QLineEdit()
		self.search.setPlaceholderText(tr("search"))
		self.search.setClearButtonEnabled(True)
		self.table = QTableWidget(0, 3)
		self.table.setHorizontalHeaderLabels([tr("col_user_id"), tr("col_name"), tr("col_department")])
		self.table.verticalHeader().setVisible(False)
		self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
		header = self.table.horizontalHeader()
		header.setSectionResizeMode(self.ID, QHeaderView.ResizeMode.ResizeToContents)
		header.setSectionResizeMode(self.NAME, QHeaderView.ResizeMode.Stretch)
		header.setSectionResizeMode(self.DEPARTMENT, QHeaderView.ResizeMode.Stretch)

		buttons = QHBoxLayout()
		self.buttons = {}
		for key, slot in (
			("add", self.add),
			("delete", self.delete),
			("add_unnamed", self.add_unnamed),
			("import_device", self.import_device),
			("import_file", self.import_file),
		):
			button = QPushButton(tr(key))
			button.clicked.connect(slot)
			buttons.addWidget(button)
			self.buttons[key] = button
			if key == "delete":
				buttons.addStretch()

		layout = QVBoxLayout(self)
		layout.addWidget(self.search)
		layout.addWidget(self.table, 1)
		layout.addLayout(buttons)

		self.reload()
		self.table.itemChanged.connect(self._edited)
		self.search.textChanged.connect(self._filter)

	def reload(self):
		self.table.blockSignals(True)
		self.table.setRowCount(0)
		for p in self.store.people():
			row = self.table.rowCount()
			self.table.insertRow(row)
			id_item = QTableWidgetItem(p.user_id)
			id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
			self.table.setItem(row, self.ID, id_item)
			self.table.setItem(row, self.NAME, QTableWidgetItem(p.name))
			self.table.setItem(row, self.DEPARTMENT, QTableWidgetItem(p.department))
		self.table.blockSignals(False)
		self._filter()

	def _filter(self):
		needle = self.search.text().strip().casefold()
		for row in range(self.table.rowCount()):
			text = " ".join(self.table.item(row, c).text() for c in range(3)).casefold()
			self.table.setRowHidden(row, bool(needle) and needle not in text)

	def _edited(self, item):
		row = item.row()
		person = Person(
			self.table.item(row, self.ID).text(),
			self.table.item(row, self.NAME).text(),
			self.table.item(row, self.DEPARTMENT).text(),
		)
		self.store.save_person(person)
		self.on_change()

	def _changed(self, count):
		self.reload()
		self.status(tr("imported", count=count))
		self.on_change()

	def add(self):
		user_id, ok = QInputDialog.getText(self, tr("add"), tr("new_user_id"))
		user_id = user_id.strip()
		if not ok or not user_id:
			return
		if any(p.user_id == user_id for p in self.store.people()):
			QMessageBox.information(self, tr("app_title"), tr("duplicate_id"))
			return
		self.store.save_person(Person(user_id, ""))
		self.reload()
		self._edit_name_of(user_id)

	def _edit_name_of(self, user_id):
		for row in range(self.table.rowCount()):
			if self.table.item(row, self.ID).text() == user_id:
				self.table.setCurrentCell(row, self.NAME)
				self.table.editItem(self.table.item(row, self.NAME))
				return

	def delete(self):
		row = self.table.currentRow()
		if row < 0 or self.table.isRowHidden(row):  # the selection may be hidden by the search filter
			return
		user_id = self.table.item(row, self.ID).text()
		name = self.table.item(row, self.NAME).text() or user_id
		answer = QMessageBox.question(self, tr("delete"), tr("confirm_delete_person", name=name))
		if answer == QMessageBox.StandardButton.Yes:
			self.store.delete_person(user_id)
			self.reload()
			self.on_change()

	def add_unnamed(self):
		missing = self.store.unnamed_user_ids()
		for user_id in missing:
			self.store.save_person(Person(user_id, ""))
		self.reload()
		if missing:
			self._edit_name_of(missing[0])

	def import_device(self):
		if busy():
			self.status(tr("busy"))
			return
		devices = self.store.devices()
		if not devices:
			QMessageBox.information(self, tr("app_title"), tr("no_devices"))
			return
		d = devices[0]
		if len(devices) > 1:
			names = [x.name for x in devices]
			name, ok = QInputDialog.getItem(self, tr("import_device"), tr("choose_device"), names, 0, False)
			if not ok:
				return
			d = devices[names.index(name)]
		self.buttons["import_device"].setEnabled(False)
		self.status(tr("pulling", device=d.name))
		run_in_background(
			zk.read_users, d.ip, d.port, d.comm_key, on_done=self._device_users, on_failed=self._device_failed
		)

	def _device_users(self, users):
		count = self.store.import_names({u.user_id: u.name for u in users})  # save first, then update the UI
		self.buttons["import_device"].setEnabled(True)
		self._changed(count)

	def _device_failed(self, message):
		self.buttons["import_device"].setEnabled(True)
		QMessageBox.warning(self, tr("error"), tr("import_failed", error=message))

	def import_file(self):
		QMessageBox.information(self, tr("import_file"), tr("import_file_hint"))
		path, _ = QFileDialog.getOpenFileName(
			self, tr("import_file"), str(Path.home()), "Excel / CSV (*.xlsx *.csv)"
		)
		if not path:
			return
		try:
			names = read_names_file(Path(path))
		except Exception as e:  # a damaged or unexpected file; show why instead of crashing
			log.exception("Importing names from %s failed", path)
			QMessageBox.warning(self, tr("error"), tr("import_failed", error=e))
			return
		self._changed(self.store.import_names(names, overwrite=True))
