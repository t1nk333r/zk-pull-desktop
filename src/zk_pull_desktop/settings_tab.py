from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
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

from . import __version__
from .dialogs import DeviceDialog
from .i18n import LANGUAGES, language, tr
from .store import Store


class SettingsTab(QWidget):
	def __init__(self, store: Store, data_dir: Path, on_devices_changed, on_language_changed):
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
		self.layout_choice = QComboBox()
		self.layout_choice.addItem(tr("layout_log"), "log")
		self.layout_choice.addItem(tr("layout_daily"), "daily")
		self.layout_choice.setCurrentIndex(self.layout_choice.findData(store.get("layout", "log")))
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
		data_button = QPushButton(str(data_dir))
		data_button.setFlat(True)
		data_button.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
		data_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir))))

		general_box = QGroupBox(tr("general"))
		form = QFormLayout(general_box)
		form.addRow(tr("language"), self.language)
		form.addRow(tr("export_layout"), self.layout_choice)
		form.addRow(tr("header_language"), self.header_language)
		form.addRow(tr("export_folder"), folder_row)
		form.addRow(tr("data_folder"), data_button)
		form.addRow("", QLabel(f"ZK Pull {__version__}"))

		layout = QVBoxLayout(self)
		layout.addWidget(devices_box, 1)
		layout.addWidget(general_box)

		self.reload_devices()
		self.language.currentIndexChanged.connect(self._language_changed)
		self.layout_choice.currentIndexChanged.connect(
			lambda: store.set("layout", self.layout_choice.currentData())
		)
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
		if dialog.exec():
			self.store.save_device(dialog.device())
			self._devices_changed()

	def edit_device(self):
		d = self._selected()
		if d is None:
			return
		dialog = DeviceDialog(self, d)
		if dialog.exec():
			edited = dialog.device()
			edited.last_pull = d.last_pull
			self.store.save_device(edited)
			self._devices_changed()

	def delete_device(self):
		d = self._selected()
		if d is None:
			return
		answer = QMessageBox.question(self, tr("delete"), tr("confirm_delete_device", name=d.name))
		if answer == QMessageBox.StandardButton.Yes:
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

	def _language_changed(self):
		code = self.language.currentData()
		self.store.set("language", code)
		self.on_language_changed(code)
