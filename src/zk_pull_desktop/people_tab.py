import codecs
import csv
import io
import logging
import re
import zipfile
from itertools import islice
from pathlib import Path

from openpyxl import load_workbook
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
	QApplication,
	QFileDialog,
	QHBoxLayout,
	QHeaderView,
	QInputDialog,
	QLineEdit,
	QPushButton,
	QTableWidget,
	QTableWidgetItem,
	QVBoxLayout,
	QWidget,
)

from . import device as zk
from . import messages
from .i18n import tr
from .store import Person, Store, normalize_id
from .worker import busy, run_in_background

log = logging.getLogger(__name__)


ID_WORDS = ("id", "no", "code", "emp", "رقم", "كود", "الرقم", "الموظف")
NAME_WORDS = ("name", "اسم")  # "الاسم" and "اسم الموظف" too


def _line_of(data: bytes, offset: int) -> int:
	return data.count(b"\n", 0, offset) + 1


def _csv_text(path: Path) -> str:
	"""UTF-8 first; Excel's "CSV (Comma delimited)" on Arabic Windows saves Windows-1256.

	Windows-1256 only when the file is not UTF-8 at all: one bad byte in a UTF-8 file must not turn
	every name into mojibake, which the import would then save over the good names."""
	data = path.read_bytes()
	if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):  # Excel's "Unicode Text"
		text = data.decode("utf-16")
	else:
		try:
			text = data.decode("utf-8-sig")
		except UnicodeDecodeError as e:
			loose = data.decode("utf-8", errors="replace")
			bad = loose.count("�")
			if data.startswith(codecs.BOM_UTF8) or sum(ord(c) > 127 for c in loose) - bad > bad:
				raise NamesFileError(tr("bad_encoding", line=_line_of(data, e.start))) from e
			text = data.decode("cp1256")
	if "\x00" in text:  # UTF-16 without a byte order mark, or not a text file
		raise NamesFileError(tr("no_names_found"))
	return text


def _is_header(first, rest) -> bool:
	"""A first row is a header if it names its columns, or if it is the only one without a numeric ID.

	A cell with a digit is an ID ("E001", "NO123"), never a header, even if it contains "no" or "id"."""
	cells = [c.casefold() for c in first]
	if not cells or any(ch.isdigit() for c in cells for ch in c):
		return False
	named = any(word in c for c in cells for word in ID_WORDS + NAME_WORDS)
	return named or any(r and r[0].isdigit() for r in rest)


def _columns(header) -> tuple[int, int]:
	"""(ID column, name column) from a header row: a sheet may start with a serial number (م) or have
	the name first. Without headers that say, the first two columns."""
	cells = [c.casefold() for c in header]
	names = [i for i, c in enumerate(cells) if any(w in c for w in NAME_WORDS)]
	ids = [i for i, c in enumerate(cells) if any(w in c for w in ID_WORDS) and i not in names]
	id_col = ids[0] if ids else 0
	name_col = next((i for i in names if i != id_col), id_col + 1 if id_col + 1 < len(cells) else 0)
	return id_col, name_col


def _delimiter(text: str) -> str:
	"""The separator that splits the first lines into the same number of columns, two or more, with no
	stray quotes. A separator inside a quoted name ("Al-Ahmad, Mohammed") is not counted, and on a tie
	";" and tab win over ",", which names contain more often."""
	lines = [line for line in text.splitlines() if line.strip()][:20]

	def score(delimiter):
		rows = list(csv.reader(lines, delimiter=delimiter))
		widths = [len(r) for r in rows if len(r) >= 2]
		if not widths:
			return (0, 0)
		common = max(set(widths), key=widths.count)
		stray_quotes = sum('"' in cell for r in rows for cell in r)
		return (widths.count(common), -stray_quotes)

	return max(";\t,", key=score)  # max keeps the first of equal scores


def _csv_rows(text: str) -> list[list[str]]:
	"""Rows of a CSV with comma, semicolon or tab between columns (Excel uses ";" in many regions).

	csv.Sniffer is not used because its result differs between Python patch releases (3.12.10, which
	the Windows build bundles, gives up on files that later releases read).

	A quote left open would swallow the lines after it into one name, so that is refused with the
	line where it starts: a cell may span lines (a name with a line break), but not hold the
	separator and a line break both."""
	delimiter = _delimiter(text)
	reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
	rows = []
	line = 1
	try:
		for row in islice(reader, MAX_ROWS):
			if any("\n" in cell and delimiter in cell for cell in row):
				raise NamesFileError(tr("bad_csv", line=line))
			rows.append(row)
			line = reader.line_num + 1
	except csv.Error as e:
		raise NamesFileError(tr("bad_csv", line=line)) from e
	return rows


def _xlsx_id(cell) -> str:
	"""An ID cell as text. Excel keeps "0012" typed into a cell formatted "0000" as the number 12."""
	value = cell.value
	if value is None:
		return ""
	if isinstance(value, float) and value.is_integer():
		value = int(value)
	if isinstance(value, int):
		number_format = getattr(cell, "number_format", "") or ""
		width = len(number_format) if re.fullmatch(r"0+", number_format) else 0
		return str(value).zfill(width)
	return str(value)


MAX_FILE = 20 * 1024 * 1024  # a names list is a few KB; anything this big is not one
MAX_UNPACKED = 100 * 1024 * 1024  # XLSX is a zip: limit what it expands to
MAX_ROWS = 100_000


class NamesFileError(ValueError):
	pass


def _check_size(path: Path):
	if path.stat().st_size > MAX_FILE:
		raise NamesFileError(tr("file_too_large"))
	if path.suffix.lower() == ".xlsx":
		with zipfile.ZipFile(path) as z:
			if sum(i.file_size for i in z.infolist()) > MAX_UNPACKED:
				raise NamesFileError(tr("file_too_large"))


class Names(dict):
	"""Employee ID -> name, and how many IDs the file gave more than one name (the last row wins)."""

	duplicates = 0


MAX_COLUMNS = 20


def read_names_file(path: Path) -> Names:
	"""Employee ID -> name from a CSV or XLSX file: the columns a header row names (ID / رقم, name /
	الاسم), else the first two.

	A file whose columns are shifted or swapped (names that are all numbers, IDs without a digit) is
	refused instead of saved over the names: the import replaces names already typed."""
	_check_size(path)
	if path.suffix.lower() == ".xlsx":
		wb = load_workbook(path, read_only=True, data_only=True)
		rows = [
			[_xlsx_id(c) for c in row] for row in islice(wb.active.iter_rows(max_col=MAX_COLUMNS), MAX_ROWS)
		]
		wb.close()
	else:
		rows = [row[:MAX_COLUMNS] for row in _csv_rows(_csv_text(path))]
	# A line break inside a cell, or several spaces, become one space.
	rows = [[" ".join(cell.split()) for cell in row] for row in rows if any(cell.strip() for cell in row)]
	id_col, name_col = 0, 1
	if rows and _is_header(rows[0], rows[1:]):
		id_col, name_col = _columns(rows[0])
		rows = rows[1:]
	names = Names()
	for row in rows:
		if len(row) <= max(id_col, name_col):
			continue
		user_id, name = normalize_id(row[id_col]), row[name_col]
		if user_id.endswith(".0") and user_id[:-2].isdigit():  # Excel stored the ID as a number
			user_id = user_id[:-2]
		if user_id and name:
			if names.get(user_id, name) != name:
				names.duplicates += 1
			names[user_id] = name
	if rows and not names:  # a file with content but no ID/name pairs is the wrong file or layout
		raise NamesFileError(tr("no_names_found"))
	numeric_names = sum(normalize_id(n).isdigit() for n in names.values())
	ids_without_digits = sum(not any(ch.isdigit() for ch in i) for i in names)
	if max(numeric_names, ids_without_digits) * 2 > len(names):
		raise NamesFileError(tr("names_wrong_columns"))
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

	def _commit_edit(self):
		"""Save a name being typed: rebuilding the rows would close its editor without saving it."""
		editor = QApplication.focusWidget()
		if editor is not None and self.table.isAncestorOf(editor):
			editor.clearFocus()  # the delegate commits on focus out, and _edited saves it

	def reload(self):
		self._commit_edit()
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
		needle = normalize_id(self.search.text()).casefold()
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
		user_id = normalize_id(user_id)
		if not ok or not user_id:
			return
		if any(p.user_id == user_id for p in self.store.people()):
			messages.info(self, tr("app_title"), tr("duplicate_id"))
			return
		self.store.save_person(Person(user_id, ""))
		self.search.clear()  # the new row must be visible to type its name
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
		if messages.ask(self, tr("delete"), tr("confirm_delete_person", name=name)):
			self.store.delete_person(user_id)
			self.reload()
			self.on_change()

	def add_unnamed(self):
		missing = self.store.unnamed_user_ids()
		self.store.add_people(missing)  # IDs already listed keep their department
		if missing:
			self.search.clear()
		self.reload()
		self.status(tr("unnamed_added", count=len(missing)))
		if missing:
			self._edit_name_of(missing[0])

	def import_device(self):
		if busy():
			self.status(tr("busy"))
			return
		devices = self.store.devices()
		if not devices:
			messages.info(self, tr("app_title"), tr("no_devices"))
			return
		d = devices[0]
		if len(devices) > 1:
			# With the address, so two devices with the same name can be told apart.
			labels = [f"{x.name} ({x.ip})" for x in devices]
			label, ok = QInputDialog.getItem(self, tr("import_device"), tr("choose_device"), labels, 0, False)
			if not ok:
				return
			d = devices[labels.index(label)]
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
		messages.warn(self, tr("error"), tr("import_failed", error=message))

	def import_file(self):
		if not self.store.get("import_hint_shown"):  # once is enough
			messages.info(self, tr("import_file"), tr("import_file_hint"))
			self.store.set("import_hint_shown", "1")
		path, _ = QFileDialog.getOpenFileName(
			self, tr("import_file"), str(Path.home()), "Excel / CSV (*.xlsx *.csv)"
		)
		if not path:
			return
		self.buttons["import_file"].setEnabled(False)
		# Off the UI thread: a large file must not freeze the window.
		run_in_background(
			read_names_file, Path(path), on_done=self._file_names, on_failed=self._file_failed, device=False
		)

	def _file_names(self, names: Names):
		replaced = self.store.names_replaced(names)
		if (replaced or names.duplicates) and not messages.ask(
			self, tr("import_file"), tr("confirm_import", replaced=replaced, duplicates=names.duplicates)
		):
			self.buttons["import_file"].setEnabled(True)
			return
		count = self.store.import_names(names, overwrite=True)
		self.buttons["import_file"].setEnabled(True)
		self._changed(count)

	def _file_failed(self, message):
		self.buttons["import_file"].setEnabled(True)
		messages.warn(self, tr("error"), tr("import_failed", error=message))
