from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
	QCheckBox,
	QComboBox,
	QFileDialog,
	QFormLayout,
	QGroupBox,
	QHBoxLayout,
	QHeaderView,
	QLabel,
	QLineEdit,
	QMessageBox,
	QPushButton,
	QTableWidget,
	QTableWidgetItem,
	QVBoxLayout,
	QWidget,
)

from . import __version__, messages
from .dialogs import DeviceDialog
from .i18n import LANGUAGES, language, tr
from .store import Store
from .worker import busy


class SettingsTab(QWidget):
	def __init__(
		self, store: Store, data_dir: Path, on_devices_changed, on_language_changed, on_check_updates
	):
		super().__init__()
		self.store = store
		self.on_devices_changed = on_devices_changed
		self.on_language_changed = on_language_changed

		# Devices
		self.devices = QTableWidget(0, 5)
		self.devices.setHorizontalHeaderLabels(
			[tr("device_name"), tr("ip"), tr("port"), tr("serial"), tr("last_pull")]
		)
		self.devices.verticalHeader().setVisible(False)
		self.devices.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
		self.devices.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
		self.devices.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
		self.devices.doubleClicked.connect(self.edit_device)
		device_buttons = QHBoxLayout()
		for key, slot in (
			("add", self.add_device),
			("edit", self.edit_device),
			("delete", self.delete_device),
		):
			button = QPushButton(tr(key))
			button.clicked.connect(slot)
			device_buttons.addWidget(button)
		device_buttons.addStretch()
		devices_box = QGroupBox(tr("devices"))
		devices_layout = QVBoxLayout(devices_box)
		devices_layout.addWidget(self.devices)
		devices_layout.addLayout(device_buttons)

		# General
		self.language = QComboBox()
		for code, name in LANGUAGES.items():
			self.language.addItem(name, code)
		self.language.setCurrentIndex(self.language.findData(language()))
		self.header_language = QComboBox()
		for code, name in LANGUAGES.items():
			self.header_language.addItem(name, code)
		self.header_language.setCurrentIndex(
			self.header_language.findData(store.get("header_language", "en"))
		)
		self.folder = QLineEdit(store.get("export_folder") or str(Path.home()))
		self.folder.setReadOnly(True)
		self.folder.setLayoutDirection(Qt.LayoutDirection.LeftToRight)  # paths read left to right
		browse = QPushButton(tr("browse"))
		browse.clicked.connect(self.browse)
		folder_row = QHBoxLayout()
		folder_row.addWidget(self.folder, 1)
		folder_row.addWidget(browse)
		self.data_dir = data_dir
		data_row = QHBoxLayout()
		for key, slot in (
			("open_data_folder", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir)))),
			("open_log", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir / "zk_pull.log")))),
			("backup", self.backup),
		):
			button = QPushButton(tr(key))
			button.clicked.connect(slot)
			data_row.addWidget(button)
		data_row.addStretch()

		general_box = QGroupBox(tr("general"))
		form = QFormLayout(general_box)
		form.addRow(tr("language"), self.language)
		form.addRow(tr("header_language"), self.header_language)
		form.addRow(tr("export_folder"), folder_row)
		form.addRow(tr("data_folder"), data_row)
		self.check_updates = QCheckBox(tr("check_updates_startup"))
		self.check_updates.setChecked(store.get("check_updates", "1") == "1")
		self.check_updates.toggled.connect(lambda on: store.set("check_updates", "1" if on else "0"))
		check_now = QPushButton(tr("check_updates_now"))
		check_now.clicked.connect(lambda: on_check_updates(silent=False))
		updates_row = QHBoxLayout()
		updates_row.addWidget(QLabel(f"ZK Pull {__version__}"))
		updates_row.addWidget(self.check_updates)
		updates_row.addStretch()
		updates_row.addWidget(check_now)
		about = QPushButton(tr("about"))
		about.clicked.connect(self.about)
		updates_row.addWidget(about)
		form.addRow(tr("updates"), updates_row)

		layout = QVBoxLayout(self)
		layout.addWidget(devices_box, 1)
		layout.addWidget(general_box)

		self.reload_devices()
		self.language.currentIndexChanged.connect(self._language_changed)
		self.header_language.currentIndexChanged.connect(
			lambda: store.set("header_language", self.header_language.currentData())
		)

	def reload_devices(self):
		self._devices = self.store.devices()
		self.devices.setRowCount(len(self._devices))
		for row, d in enumerate(self._devices):
			for column, value in enumerate((d.name, d.ip, str(d.port), d.serial, d.last_pull)):
				self.devices.setItem(row, column, QTableWidgetItem(value))

	def _selected(self):
		row = self.devices.currentRow()
		return self._devices[row] if 0 <= row < len(self._devices) else None

	def add_device(self):
		dialog = DeviceDialog(self)
		if dialog.exec() and self._serial_free(dialog.device()):
			self.store.save_device(dialog.device())
			self._devices_changed()
		dialog.deleteLater()

	def _serial_free(self, d) -> bool:
		"""A tested serial that already belongs to another device would merge their punches."""
		owner = self.store.serial_owner(d.serial) if d.serial else None
		if owner is None or owner == d.id:
			return True
		other = self.store.device(owner)
		messages.warn(
			self, tr("error"), tr("serial_taken", serial=d.serial, other=other.name if other else owner)
		)
		return False

	def edit_device(self):
		d = self._selected()
		if d is None:
			return
		d = self.store.device(d.id)  # fresh: a pull may have set the serial since the list was shown
		dialog = DeviceDialog(self, d)
		if dialog.exec() and self._serial_free(dialog.device()):
			self.store.save_device(dialog.device())
			self._devices_changed()
		dialog.deleteLater()

	def delete_device(self):
		d = self._selected()
		if d is None:
			return
		if messages.ask(self, tr("delete"), tr("confirm_delete_device", name=d.name)):
			self.store.delete_device(d.id)
			self._devices_changed()

	def _devices_changed(self):
		self.reload_devices()
		self.on_devices_changed()

	def browse(self):
		folder = QFileDialog.getExistingDirectory(self, tr("export_folder"), self.folder.text())
		if folder:
			self.folder.setText(folder)
			self.store.set("export_folder", folder)

	def showEvent(self, event):
		super().showEvent(event)
		self.reload_devices()  # serial and last pull change with every pull

	def _language_changed(self):
		code = self.language.currentData()
		if busy():
			# The window is rebuilt in the new language; a running pull would lose its window.
			self.language.blockSignals(True)
			self.language.setCurrentIndex(self.language.findData(language()))
			self.language.blockSignals(False)
			messages.info(self, tr("app_title"), tr("busy"))
			return
		self.store.set("language", code)
		self.on_language_changed(code)

	def backup(self):
		suggested = (
			Path(self.store.get("export_folder") or Path.home())
			/ f"zk_pull_backup_{date.today():%Y-%m-%d}.db"
		)
		path, _ = QFileDialog.getSaveFileName(self, tr("backup"), str(suggested), "SQLite (*.db)")
		if not path:
			return
		try:
			self.store.backup(Path(path))
		except Exception as e:
			messages.warn(self, tr("error"), tr("backup_failed", error=e))
			return
		messages.info(self, tr("backup"), tr("backup_done", path=path))

	def about(self):
		box = messages.box(self, QMessageBox.Icon.Information, tr("app_title"), "")
		box.setWindowTitle(tr("about"))
		box.setTextFormat(Qt.TextFormat.RichText)  # fixed text with links, nothing from a device or file
		box.setText(
			f"<b>ZK Pull {__version__}</b><br>{tr('about_text')}<br><br>"
			f'<a href="https://github.com/t1nk333r/zk-pull-desktop">github.com/t1nk333r/zk-pull-desktop</a>'
			f"<br>MIT License<br><br>{tr('about_icon')} "
			f'<a href="https://icons8.com">Icons8</a>'
		)
		box.exec()
