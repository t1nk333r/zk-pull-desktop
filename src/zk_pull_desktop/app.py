import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QLocale, QLockFile, QStandardPaths, Qt, QTimer, QTranslator, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QTabWidget

from . import __version__, i18n, updater, worker
from .attendance_tab import AttendanceTab
from .dialogs import FirstRunWizard, LanguageDialog
from .i18n import tr
from .people_tab import PeopleTab
from .settings_tab import SettingsTab
from .store import Store
from .worker import run_in_background

log = logging.getLogger(__name__)

# Arabic (UAE) is Arabic with Western digits (0-9) and the usual Gregorian month names.
LOCALES = {"en": "en_US", "ar": "ar_AE"}

ICON = Path(__file__).parent / "assets" / "icon.png"


class MainWindow(QMainWindow):
	def __init__(self, store: Store, data_dir: Path, on_language_changed, on_check_updates):
		super().__init__()
		self.setWindowTitle(f"{tr('app_title')} {__version__}")
		self.resize(1000, 640)
		status = self.statusBar().showMessage

		self.attendance = AttendanceTab(store, status)
		self.people = PeopleTab(store, status, on_change=self.attendance.refresh)
		self.settings = SettingsTab(
			store,
			data_dir,
			on_devices_changed=self.attendance.reload_devices,
			on_language_changed=on_language_changed,
			on_check_updates=on_check_updates,
		)
		tabs = QTabWidget()
		tabs.addTab(self.attendance, tr("tab_attendance"))
		tabs.addTab(self.people, tr("tab_people"))
		tabs.addTab(self.settings, tr("tab_settings"))
		tabs.currentChanged.connect(lambda i: tabs.widget(i) is self.people and self.people.reload())
		self.setCentralWidget(tabs)


class App:
	def __init__(self, qt_app: QApplication, store: Store, data_dir: Path):
		self.qt_app = qt_app
		self.store = store
		self.data_dir = data_dir
		self.window = None
		self.translator = None
		self.checking = False

	def apply_language(self, code):
		i18n.set_language(code)
		QLocale.setDefault(QLocale(LOCALES[i18n.language()]))
		# Qt's own texts: Yes/No/OK/Cancel buttons and the right-click menu of text fields.
		if self.translator is not None:
			self.qt_app.removeTranslator(self.translator)
			self.translator = None
		if i18n.language() != "en":
			translator = QTranslator(self.qt_app)
			path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
			if translator.load(f"qtbase_{i18n.language()}", path):
				self.qt_app.installTranslator(translator)
				self.translator = translator
			else:
				log.warning("No Qt translation for %s in %s", i18n.language(), path)
		self.qt_app.setLayoutDirection(
			Qt.LayoutDirection.RightToLeft if i18n.is_rtl() else Qt.LayoutDirection.LeftToRight
		)

	def show_main(self):
		old = self.window
		self.window = MainWindow(self.store, self.data_dir, self.change_language, self.check_for_updates)
		if old is not None:
			self.window.setGeometry(old.geometry())
		self.window.show()  # before closing the old one, or Qt quits when its last window closes
		if old is not None:
			old.close()
			old.deleteLater()

	def change_language(self, code):
		self.apply_language(code)
		self.show_main()  # every text is set when a widget is built, so rebuild the window

	def run(self):
		if not self.store.get("language"):
			dialog = LanguageDialog()
			dialog.exec()
			self.store.set("language", dialog.choice)
		self.apply_language(self.store.get("language"))
		if not self.store.get("first_run_done"):
			FirstRunWizard(self.store).exec()  # every step can be skipped
			self.store.set("first_run_done", "1")
		self.show_main()
		if self.store.get("check_updates", "1") == "1":
			QTimer.singleShot(3000, lambda: self.check_for_updates(silent=True))
		return self.qt_app.exec()

	# Updates

	def check_for_updates(self, silent=False):
		"""silent: the startup check, which only speaks up when there is a new version."""
		if self.checking:
			return
		self.checking = True
		run_in_background(
			updater.latest_release,
			on_done=lambda release: self._checked(release, silent),
			on_failed=lambda message: self._check_failed(message, silent),
			device=False,
		)

	def _check_failed(self, message, silent):
		self.checking = False
		log.warning("Update check failed: %s", message)
		if not silent:
			QMessageBox.warning(self.window, tr("error"), tr("update_failed", error=message))

	def _checked(self, release: updater.Release, silent):
		self.checking = False
		log.info("Latest release: %s (this is %s)", release.version, __version__)
		if not updater.is_newer(release.version):
			if not silent:
				QMessageBox.information(self.window, tr("app_title"), tr("update_none", version=__version__))
			return
		values = {"version": release.version, "current": __version__}
		if not updater.installed() or not release.setup_url:
			# Portable copy or running from source: the installer would not update this folder.
			answer = QMessageBox.question(self.window, tr("updates"), tr("update_portable", **values))
			if answer == QMessageBox.StandardButton.Yes:
				QDesktopServices.openUrl(QUrl(release.page_url))
			return
		box = QMessageBox(self.window)
		box.setWindowTitle(tr("updates"))
		box.setText(tr("update_available", **values))
		install = box.addButton(tr("install"), QMessageBox.ButtonRole.AcceptRole)
		box.addButton(tr("later"), QMessageBox.ButtonRole.RejectRole)
		box.exec()
		if box.clickedButton() is not install:
			return
		if worker.busy():
			QMessageBox.information(self.window, tr("app_title"), tr("busy"))
			return
		self.window.statusBar().showMessage(tr("update_downloading", version=release.version))
		run_in_background(
			updater.download_setup,
			release,
			on_done=self._downloaded,
			on_failed=lambda message: self._check_failed(message, silent=False),
			device=False,
		)

	def _downloaded(self, path):
		if worker.busy():  # a pull started during the download; let it finish
			QMessageBox.information(self.window, tr("app_title"), tr("busy"))
			return
		log.info("Running installer %s", path)
		updater.run_installer(path)
		self.qt_app.quit()


def data_directory() -> Path:
	path = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
	path.mkdir(parents=True, exist_ok=True)
	return path


def setup_logging(data_dir: Path):
	handler = RotatingFileHandler(
		data_dir / "zk_pull.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
	)
	handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
	logging.basicConfig(level=logging.INFO, handlers=[handler])

	def excepthook(kind, value, tb):
		log.critical("Unhandled error", exc_info=(kind, value, tb))
		QMessageBox.critical(None, tr("error"), f"{value}\n\n{data_dir / 'zk_pull.log'}")

	sys.excepthook = excepthook


def main():
	qt_app = QApplication(sys.argv)
	qt_app.setApplicationName("ZK Pull")
	qt_app.setOrganizationName("")
	qt_app.setApplicationVersion(__version__)
	qt_app.setWindowIcon(QIcon(str(ICON)))  # every window and dialog, and the taskbar
	data_dir = data_directory()
	setup_logging(data_dir)
	lock = QLockFile(str(data_dir / "zk_pull.lock"))
	if not lock.tryLock(100):
		# HR, Admin and IT share the PC: two copies would share one database.
		QMessageBox.information(None, "ZK Pull", "ZK Pull is already running.\nZK Pull يعمل بالفعل.")
		return 0
	log.info("ZK Pull %s starting, data in %s", __version__, data_dir)
	store = Store(data_dir / "zk_pull.db")
	try:
		code = App(qt_app, store, data_dir).run()
	finally:
		store.close()
		lock.unlock()
	if worker.running():
		# A device read is still waiting on its socket timeout (up to 30 s). Nothing is left to
		# save, so leave now instead of running on as a hidden process.
		log.info("Exiting while a background task is still running")
		logging.shutdown()
		os._exit(code)
	return code


if __name__ == "__main__":
	sys.exit(main())
