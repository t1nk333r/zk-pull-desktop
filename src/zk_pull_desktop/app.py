import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QLocale, QStandardPaths, Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QTabWidget

from . import __version__, i18n
from .attendance_tab import AttendanceTab
from .dialogs import FirstRunWizard, LanguageDialog
from .i18n import tr
from .people_tab import PeopleTab
from .settings_tab import SettingsTab
from .store import Store

log = logging.getLogger(__name__)

# Arabic (UAE) is Arabic with Western digits (0-9) and the usual Gregorian month names.
LOCALES = {"en": "en_US", "ar": "ar_AE"}


class MainWindow(QMainWindow):
	def __init__(self, store: Store, data_dir: Path, on_language_changed):
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

	def apply_language(self, code):
		i18n.set_language(code)
		QLocale.setDefault(QLocale(LOCALES[i18n.language()]))
		self.qt_app.setLayoutDirection(
			Qt.LayoutDirection.RightToLeft if i18n.is_rtl() else Qt.LayoutDirection.LeftToRight
		)

	def show_main(self):
		old = self.window
		self.window = MainWindow(self.store, self.data_dir, self.change_language)
		if old is not None:
			self.window.setGeometry(old.geometry())
			old.close()
			old.deleteLater()
		self.window.show()

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
		return self.qt_app.exec()


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
	data_dir = data_directory()
	setup_logging(data_dir)
	log.info("ZK Pull %s starting, data in %s", __version__, data_dir)
	store = Store(data_dir / "zk_pull.db")
	try:
		return App(qt_app, store, data_dir).run()
	finally:
		store.close()


if __name__ == "__main__":
	sys.exit(main())
