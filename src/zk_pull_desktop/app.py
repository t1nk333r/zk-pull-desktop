import logging
import os
import shutil
import sqlite3
import sys
from datetime import date, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import (
	QByteArray,
	QLibraryInfo,
	QLocale,
	QLockFile,
	QStandardPaths,
	Qt,
	QTimer,
	QTranslator,
	QUrl,
)
from PySide6.QtGui import QDesktopServices, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QTabWidget

from . import __version__, i18n, messages, updater, worker
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
		self.store = store
		self.tabs = tabs = QTabWidget()
		tabs.addTab(self.attendance, tr("tab_attendance"))
		tabs.addTab(self.people, tr("tab_people"))
		tabs.addTab(self.settings, tr("tab_settings"))
		self.setCentralWidget(tabs)

		geometry = store.get("window_geometry")
		if geometry:
			self.restoreGeometry(QByteArray.fromBase64(geometry.encode()))
		tabs.setCurrentIndex(int(store.get("tab", "0") or 0))
		tabs.currentChanged.connect(self._tab_changed)

		for keys, action in (
			("F5", self.attendance.pull),
			("Ctrl+E", self.attendance.export),
			("Ctrl+F", self._focus_search),
		):
			QShortcut(QKeySequence(keys), self, activated=action)

	def _tab_changed(self, index):
		self.store.set("tab", index)
		if self.tabs.widget(index) is self.people:
			self.people.reload()

	def _focus_search(self):
		page = self.tabs.currentWidget()
		search = getattr(page, "search", None)
		if search is not None:
			search.setFocus()
			search.selectAll()

	def closeEvent(self, event):
		self.store.set("window_geometry", self.saveGeometry().toBase64().data().decode())
		super().closeEvent(event)


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
			self.window.tabs.setCurrentIndex(old.tabs.currentIndex())
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
			messages.warn(self.window, tr("error"), tr("update_failed", error=message))

	def _checked(self, release: updater.Release, silent):
		self.checking = False
		updater.remove_old_downloads()
		log.info("Latest release: %s (this is %s)", release.version, __version__)
		if not updater.is_newer(release.version):
			if not silent:
				messages.info(self.window, tr("app_title"), tr("update_none", version=__version__))
			return
		values = {"version": release.version, "current": __version__}
		if not updater.installed() or not release.setup_url:
			# Portable copy or running from source: the installer would not update this folder.
			if messages.ask(self.window, tr("updates"), tr("update_portable", **values)):
				QDesktopServices.openUrl(QUrl(release.page_url))
			return
		if not updater.per_user_install():
			messages.info(self.window, tr("updates"), tr("update_ask_it", **values))
			return
		box = messages.box(self.window, QMessageBox.Icon.Information, tr("app_title"), "")
		box.setWindowTitle(tr("updates"))
		box.setText(tr("update_available", **values))
		install = box.addButton(tr("install"), QMessageBox.ButtonRole.AcceptRole)
		box.addButton(tr("later"), QMessageBox.ButtonRole.RejectRole)
		box.exec()
		if box.clickedButton() is not install:
			return
		if worker.busy():
			messages.info(self.window, tr("app_title"), tr("busy"))
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
			messages.info(self.window, tr("app_title"), tr("busy"))
			return
		log.info("Running installer %s", path)
		updater.run_installer(path)
		self.qt_app.quit()


BACKUPS_KEPT = 7


def daily_backup(store: Store, data_dir: Path):
	"""One copy of the database per day in data_dir/backups, the last BACKUPS_KEPT days kept."""
	folder = data_dir / "backups"
	target = folder / f"zk_pull_{date.today():%Y-%m-%d}.db"
	try:
		folder.mkdir(exist_ok=True)
		if not target.exists():
			store.backup(target)
		for old in sorted(folder.glob("zk_pull_*.db"))[:-BACKUPS_KEPT]:
			old.unlink()
	except (OSError, sqlite3.Error):
		log.exception("Daily backup failed")


def open_store(data_dir: Path) -> Store:
	"""The database; a damaged one is moved aside and the latest daily backup offered instead."""
	path = data_dir / "zk_pull.db"
	try:
		return Store(path)
	except sqlite3.DatabaseError:
		log.exception("Database %s is damaged", path)
	damaged = path.with_name(f"zk_pull.damaged-{datetime.now():%Y%m%d-%H%M%S}.db")
	path.rename(damaged)
	backups = sorted((data_dir / "backups").glob("zk_pull_*.db"))
	# Before the database opens the language is unknown, so both are shown.
	if backups and messages.ask(
		None,
		"ZK Pull",
		f"The database was damaged and has been kept as {damaged.name}.\n"
		f"Restore the backup of {backups[-1].stem.removeprefix('zk_pull_')}?\n\n"
		f"قاعدة البيانات تالفة، وحُفظت باسم {damaged.name}.\n"
		f"هل تريد استعادة النسخة الاحتياطية بتاريخ {backups[-1].stem.removeprefix('zk_pull_')}؟",
	):
		shutil.copyfile(backups[-1], path)
		log.info("Restored %s", backups[-1])
	else:
		messages.warn(
			None,
			"ZK Pull",
			f"The database was damaged and has been kept as {damaged.name}. ZK Pull starts empty.\n\n"
			f"قاعدة البيانات تالفة، وحُفظت باسم {damaged.name}. سيبدأ ZK Pull بقاعدة بيانات فارغة.",
		)
	return Store(path)


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
		messages.error(None, tr("error"), f"{value}\n\n{data_dir / 'zk_pull.log'}")

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
		messages.info(None, "ZK Pull", "ZK Pull is already running.\nZK Pull يعمل بالفعل.")
		return 0
	log.info("ZK Pull %s starting, data in %s", __version__, data_dir)
	store = open_store(data_dir)
	daily_backup(store, data_dir)
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
