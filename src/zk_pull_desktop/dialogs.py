from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
	QDialog,
	QDialogButtonBox,
	QFormLayout,
	QHBoxLayout,
	QLabel,
	QLineEdit,
	QPushButton,
	QSpinBox,
	QVBoxLayout,
	QWizard,
	QWizardPage,
)

from . import device as zk
from . import messages
from .i18n import LANGUAGES, tr
from .store import Device, Store, normalize_ip
from .worker import busy, run_in_background


class LanguageDialog(QDialog):
	"""Shown once, before anything else, so the rest of the first run is in the right language."""

	def __init__(self):
		super().__init__()
		self.setWindowTitle("ZK Pull")
		self.choice = "en"
		layout = QVBoxLayout(self)
		label = QLabel("Choose a language\nاختر اللغة")
		label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		layout.addWidget(label)
		row = QHBoxLayout()
		for code, name in LANGUAGES.items():
			button = QPushButton(name)
			button.setMinimumSize(140, 44)
			button.clicked.connect(lambda _=False, c=code: self._pick(c))
			row.addWidget(button)
		layout.addLayout(row)

	def _pick(self, code):
		self.choice = code
		self.accept()


class DeviceForm(QFormLayout):
	"""Name, IP, port and comm key fields with a Test button; shared by the dialog and the wizard."""

	def __init__(self, device: Device | None = None):
		super().__init__()
		self.serial = device.serial if device else ""
		self.testing = None  # the address being tested
		self.name = QLineEdit(device.name if device else "")
		self.ip = QLineEdit(device.ip if device else "")
		self.ip.setPlaceholderText("192.168.1.201")
		self.port = QSpinBox()
		self.port.setRange(1, 65535)
		self.port.setValue(device.port if device else zk.DEFAULT_PORT)
		self.comm_key = QSpinBox()
		self.comm_key.setRange(0, 999999)
		self.comm_key.setValue(device.comm_key if device else 0)
		self.test_button = QPushButton(tr("test"))
		self.test_button.clicked.connect(self.test)
		self.result = QLabel()
		self.result.setWordWrap(True)
		self.result.setTextFormat(Qt.TextFormat.PlainText)  # shows device data and errors
		self.addRow(tr("device_name"), self.name)
		self.addRow(tr("ip"), self.ip)
		self.addRow(tr("port"), self.port)
		self.addRow(tr("comm_key"), self.comm_key)
		self.addRow(self.test_button, self.result)
		# A serial read by Test belongs to the address tested; another address needs a new Test.
		self.ip.textChanged.connect(self._address_changed)
		self.port.valueChanged.connect(self._address_changed)

	def _address_changed(self):
		self.serial = ""  # saving an existing device without a Test keeps the serial it has
		self.result.clear()

	def is_empty(self):
		return not self.name.text().strip() and not self.ip.text().strip()

	def is_valid(self):
		return bool(self.name.text().strip() and self.ip.text().strip())

	def problem(self) -> str:
		"""Why the form cannot be saved, or ""."""
		if not self.is_valid():
			return tr("invalid_device")
		if normalize_ip(self.ip.text()) is None:
			return tr("invalid_ip")
		return ""

	def device(self, device_id=None) -> Device:
		return Device(
			device_id,
			self.name.text().strip(),
			normalize_ip(self.ip.text()) or self.ip.text().strip(),
			self.port.value(),
			self.comm_key.value(),
			self.serial,
		)

	def test(self):
		if busy():  # the device answers one connection at a time
			self.result.setText(tr("busy"))
			return
		if normalize_ip(self.ip.text()) is None:
			self.result.setText(tr("invalid_ip"))
			return
		self.test_button.setEnabled(False)
		self.result.setText("…")
		self.testing = self._address()
		run_in_background(
			zk.probe,
			*self.testing,
			self.comm_key.value(),
			on_done=self._tested,
			on_failed=self._test_failed,
		)

	def _address(self):
		return normalize_ip(self.ip.text()) or self.ip.text().strip(), self.port.value()

	def _tested(self, info: zk.DeviceInfo):
		if self.testing != self._address():
			self.test_button.setEnabled(True)
			return  # the address changed while testing: this serial is not the new address's
		self.serial = info.serial
		self.test_button.setEnabled(True)
		self.result.setText(
			tr("test_ok", serial=info.serial, punches=info.punch_count, users=info.user_count)
		)

	def _test_failed(self, message):
		self.test_button.setEnabled(True)
		self.result.setText(tr("test_failed", error=message))


class DeviceDialog(QDialog):
	def __init__(self, parent, device: Device | None = None):
		super().__init__(parent)
		self.device_id = device.id if device else None
		self.setWindowTitle(tr("edit_device") if device else tr("add_device"))
		self.setMinimumWidth(420)
		layout = QVBoxLayout(self)
		self.form = DeviceForm(device)
		layout.addLayout(self.form)
		buttons = QDialogButtonBox(
			QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
		)
		buttons.button(QDialogButtonBox.StandardButton.Save).setText(tr("save"))
		buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("cancel"))
		buttons.accepted.connect(self._save)
		buttons.rejected.connect(self.reject)
		layout.addWidget(buttons)

	def _save(self):
		problem = self.form.problem()
		if problem:
			messages.warn(self, tr("error"), problem)
			return
		self.accept()

	def device(self) -> Device:
		return self.form.device(self.device_id)


class _DevicePage(QWizardPage):
	def __init__(self, store: Store):
		super().__init__()
		self.store = store
		self.setTitle(tr("first_device"))
		self.setSubTitle(tr("welcome_text"))
		layout = QVBoxLayout(self)
		self.form = DeviceForm()
		layout.addLayout(self.form)

	def validatePage(self):
		if busy():  # wait for Test, so the serial it reads is saved with the device
			messages.info(self, tr("app_title"), tr("busy"))
			return False
		if self.form.is_empty():
			return True  # skipped
		problem = self.form.problem()
		if problem:
			messages.warn(self, tr("error"), problem)
			return False
		self.store.save_device(self.form.device())
		return True


class _NamesPage(QWizardPage):
	def __init__(self, store: Store):
		super().__init__()
		self.store = store
		self.setTitle(tr("first_names"))
		layout = QVBoxLayout(self)
		text = QLabel(tr("first_names_text"))
		text.setWordWrap(True)
		layout.addWidget(text)
		self.button = QPushButton(tr("import_device"))
		self.button.clicked.connect(self._import)
		layout.addWidget(self.button)
		self.result = QLabel()
		self.result.setWordWrap(True)
		self.result.setTextFormat(Qt.TextFormat.PlainText)  # shows device data and errors
		layout.addWidget(self.result)
		layout.addStretch()

	def initializePage(self):
		self.button.setEnabled(bool(self.store.devices()))

	def _import(self):
		d = self.store.devices()[0]
		self.button.setEnabled(False)
		self.result.setText("…")
		run_in_background(
			zk.read_users, d.ip, d.port, d.comm_key, on_done=self._imported, on_failed=self._failed
		)

	def _imported(self, users):
		count = self.store.import_names({u.user_id: u.name for u in users})
		self.result.setText(tr("imported", count=count))

	def _failed(self, message):
		self.button.setEnabled(True)
		self.result.setText(tr("import_failed", error=message))


class FirstRunWizard(QWizard):
	def __init__(self, store: Store):
		super().__init__()
		self.setWindowTitle(tr("welcome_title"))
		self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
		self.setMinimumWidth(520)
		self.addPage(_DevicePage(store))
		self.addPage(_NamesPage(store))
		self.setButtonText(QWizard.WizardButton.NextButton, tr("next"))
		self.setButtonText(QWizard.WizardButton.FinishButton, tr("finish"))
		self.setButtonText(QWizard.WizardButton.CancelButton, tr("skip"))
		self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage)
		self.setOption(QWizard.WizardOption.NoBackButtonOnLastPage)

	def done(self, result):
		# Finish, Skip and the close button all end here. A device read still running is stopped,
		# so a device that never answers cannot keep the wizard, and the app, from closing.
		if busy():
			zk.cancel_all()
		super().done(result)
