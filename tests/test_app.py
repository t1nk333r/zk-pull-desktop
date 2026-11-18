"""Opening the database at startup: damaged, locked, and bad backups."""

import sqlite3

import pytest

from zk_pull_desktop import app, messages
from zk_pull_desktop.store import Store


@pytest.fixture
def answers(monkeypatch):
	asked = []
	monkeypatch.setattr(messages, "ask", lambda parent, title, text: asked.append(text) or True)
	monkeypatch.setattr(messages, "warn", lambda parent, title, text: asked.append(text))
	return asked


def make_db(path, name="Sara"):
	s = Store(path)
	s.set("marker", name)
	s.close()


def test_damaged_database_restores_the_newest_good_backup(tmp_path, answers):
	(tmp_path / "zk_pull.db").write_bytes(b"not a database" * 100)
	backups = tmp_path / "backups"
	backups.mkdir()
	make_db(backups / "zk_pull_2026-11-14.db", "good")
	(backups / "zk_pull_2026-11-15.db").write_bytes(b"cut short")  # newest, but broken
	store = app.open_store(tmp_path)
	assert store.get("marker") == "good"
	assert "2026-11-14" in answers[0]
	assert len(list(tmp_path.glob("zk_pull.damaged-*.db"))) == 1
	store.close()


def test_damaged_database_without_backups_starts_empty(tmp_path, answers):
	(tmp_path / "zk_pull.db").write_bytes(b"not a database" * 100)
	store = app.open_store(tmp_path)
	assert store.get("marker") == "" and store.devices() == []
	store.close()


def test_a_locked_database_is_left_alone(tmp_path, answers, monkeypatch):
	make_db(tmp_path / "zk_pull.db")

	def locked(path):
		raise sqlite3.OperationalError("database is locked")

	monkeypatch.setattr(app, "Store", locked)
	with pytest.raises(app.StartupError):
		app.open_store(tmp_path)
	assert not list(tmp_path.glob("zk_pull.damaged-*.db"))
	assert answers == []


def test_daily_backup_keeps_seven_good_copies(tmp_path):
	store = Store(tmp_path / "zk_pull.db")
	backups = tmp_path / "backups"
	backups.mkdir()
	for day in range(1, 10):
		(backups / f"zk_pull_2026-10-{day:02d}.db").write_bytes(b"")
	app.daily_backup(store, tmp_path)
	kept = sorted(p.name for p in backups.iterdir())
	assert len(kept) == app.BACKUPS_KEPT and kept[-1].startswith("zk_pull_20")
	store.close()


def test_device_addresses_are_checked_and_normalized():
	from zk_pull_desktop.store import normalize_ip

	assert normalize_ip(" 192.168.100.056 ") == "192.168.100.56"  # Windows would read 056 as octal
	assert normalize_ip("١٩٢.١٦٨.١.٢٠١") == "192.168.1.201"
	assert normalize_ip("10.0.0.5") == "10.0.0.5"
	for bad in ("8.8.8.8", "device.local", "192.168.1", "192.168.1.300", "0.0.0.0", "224.0.0.1", ""):
		assert normalize_ip(bad) is None, bad


def test_background_callbacks_of_a_window_are_found_through_partial():
	from functools import partial

	from PySide6.QtCore import QObject

	from zk_pull_desktop import worker

	class Owner(QObject):
		def done(self, device, result):
			pass

	owner = Owner()
	assert worker._owner(partial(owner.done, "Gate")) is owner
	assert worker._owner(owner.done) is owner
	assert worker._owner(lambda result: None) is None


def test_smoke_test_starts_the_app_and_quits():
	assert app.smoke_test() == 0


def test_export_name_carries_the_employee_id_and_name(tmp_path):
	from datetime import date

	from PySide6.QtWidgets import QApplication

	from zk_pull_desktop.attendance_tab import AttendanceTab

	QApplication.instance() or QApplication([])
	s = Store(tmp_path / "db.sqlite")
	s.import_names({"12": "كريس Smith"})
	tab = AttendanceTab(s, lambda message: None)
	tab.reload_employees()
	tab.employee.setCurrentIndex(tab.employee.findData("12"))
	name = tab._export_name(date(2026, 9, 1), date(2026, 9, 30), "timecard", "xlsx")
	assert name == "timecard_12_كريس_Smith_2026-09-01_to_2026-09-30.xlsx"
	s.close()
