from datetime import date, datetime

import pytest

from zk_pull_desktop.device import Punch
from zk_pull_desktop.store import Device, Person, Store


@pytest.fixture
def store(tmp_path):
	s = Store(tmp_path / "test.db")
	yield s
	s.close()


def punch(user_id, ts, serial="SN1", kind=0):
	return Punch(serial, user_id, datetime.fromisoformat(ts), kind, 1)


def test_pulling_twice_stores_each_punch_once(store):
	punches = [punch("1", "2026-11-01 08:00:00"), punch("1", "2026-11-01 17:00:00")]
	assert store.add_punches(punches) == 2
	assert store.add_punches(punches + [punch("2", "2026-11-02 08:00:00")]) == 1
	assert len(store.punches(date(2026, 11, 1), date(2026, 11, 30))) == 3


def test_same_punch_on_two_devices_is_kept_for_each(store):
	assert (
		store.add_punches(
			[punch("1", "2026-11-01 08:00:00", "SN1"), punch("1", "2026-11-01 08:00:00", "SN2")]
		)
		== 2
	)


def test_range_includes_both_end_days(store):
	store.add_punches(
		[
			punch("1", "2026-10-31 23:59:59"),
			punch("1", "2026-11-01 00:00:00"),
			punch("1", "2026-11-30 23:59:59"),
			punch("1", "2026-12-01 00:00:00"),
		]
	)
	rows = store.punches(date(2026, 11, 1), date(2026, 11, 30))
	assert [r.timestamp.isoformat(" ") for r in rows] == ["2026-11-01 00:00:00", "2026-11-30 23:59:59"]


def test_rows_carry_person_and_device_names(store):
	store.save_device(Device(None, "Main gate", "192.168.1.201", serial="SN1"))
	store.save_person(Person("7", "Sara", "HR"))
	store.add_punches([punch("7", "2026-11-01 08:00:00"), punch("8", "2026-11-01 08:01:00", serial="SN9")])
	sara, unknown = store.punches(date(2026, 11, 1), date(2026, 11, 1))
	assert (sara.name, sara.department, sara.device) == ("Sara", "HR", "Main gate")
	assert (unknown.name, unknown.device) == ("", "SN9")  # no person, device not configured


def test_filter_by_serial(store):
	store.add_punches([punch("1", "2026-11-01 08:00:00", "SN1"), punch("1", "2026-11-01 08:00:00", "SN2")])
	assert [r.device for r in store.punches(date(2026, 11, 1), date(2026, 11, 1), ["SN2"])] == ["SN2"]
	assert store.punches(date(2026, 11, 1), date(2026, 11, 1), []) == []


def test_import_names_keeps_existing_unless_overwrite(store):
	store.save_person(Person("1", "Edited by HR"))
	assert store.import_names({"1": "From device", "2": "Omar", "3": ""}) == 1
	assert {p.user_id: p.name for p in store.people()} == {"1": "Edited by HR", "2": "Omar"}
	assert store.import_names({"1": "From file", "2": "Omar"}, overwrite=True) == 1
	assert store.people()[0].name == "From file"


def test_unnamed_user_ids(store):
	store.save_person(Person("1", "Ali"))
	store.save_person(Person("2", ""))
	store.add_punches([punch(u, "2026-11-01 08:00:00") for u in ("1", "2", "10", "3")])
	assert store.unnamed_user_ids() == ["2", "3", "10"]


def test_deleting_a_device_keeps_its_punches(store):
	device_id = store.save_device(Device(None, "Gate", "10.0.0.5", serial="SN1"))
	store.add_punches([punch("1", "2026-11-01 08:00:00")])
	store.delete_device(device_id)
	assert [r.device for r in store.punches(date(2026, 11, 1), date(2026, 11, 1))] == ["SN1"]


def test_settings_round_trip(store):
	assert store.get("layout", "log") == "log"
	store.set("layout", "daily")
	store.set("layout", "log")
	assert store.get("layout") == "log"


def test_device_keeps_punches_from_an_earlier_serial(store):
	device_id = store.save_device(Device(None, "Main", "10.0.0.5"))
	store.mark_pulled(device_id, "SN1", datetime(2026, 11, 1, 9))
	store.add_punches([punch("1", "2026-11-01 08:00:00", "SN1")])
	store.mark_pulled(device_id, "SN2", datetime(2026, 11, 2, 9))  # mainboard replaced
	store.add_punches([punch("1", "2026-11-02 08:00:00", "SN2")])
	rows = store.punches(date(2026, 11, 1), date(2026, 11, 2), store.serials([device_id]))
	assert [r.device for r in rows] == ["Main", "Main"]


def test_editing_a_device_keeps_the_serial_from_the_last_pull(store):
	device_id = store.save_device(Device(None, "Main", "10.0.0.5"))
	store.mark_pulled(device_id, "SN1", datetime(2026, 11, 1, 9))
	store.save_device(Device(device_id, "Main gate", "10.0.0.6"))  # edited without Test
	d = store.device(device_id)
	assert (d.name, d.ip, d.serial, d.last_pull) == ("Main gate", "10.0.0.6", "SN1", "2026-11-01 09:00:00")


def test_a_device_deleted_during_a_pull_leaves_no_serial_behind(store):
	gate = store.save_device(Device(None, "Gate", "10.0.0.5"))
	store.delete_device(gate)
	assert store.mark_pulled(gate, "SN1", datetime(2026, 11, 1, 9)) is False  # the pull finished late
	other = store.save_device(Device(None, "Other", "10.0.0.6"))  # SQLite may reuse the id
	assert store.serial_owner("SN1") is None
	assert store.serials([other]) == []


def test_a_serial_read_by_test_is_not_claimed_for_good(store):
	a = store.save_device(Device(None, "A", "10.0.0.1", serial="S1"))
	store.mark_pulled(a, "S1", datetime(2026, 11, 1, 9))
	store.save_device(Device(a, "A", "10.0.0.2", serial="S2"))  # mistyped IP, Test read B's serial
	store.save_device(Device(a, "A", "10.0.0.1", serial="S1"))  # corrected
	assert store.serial_owner("S2") is None
	assert store.serials([a]) == ["S1"]


def test_a_tested_serial_counts_before_the_first_pull(store):
	a = store.save_device(Device(None, "A", "10.0.0.1", serial="S1"))
	assert store.serial_owner("S1") == a and store.serials([a]) == ["S1"]


def test_the_last_possible_end_date_works(store):
	store.add_punches([punch("1", "2026-11-01 08:00:00")])
	assert len(store.punches(date(2000, 1, 1), date(9999, 12, 31))) == 1


def test_ids_with_arabic_digits_and_direction_marks_are_normalized(store):
	store.save_person(Person("‏١٢", "Sara"))
	store.import_names({"۷": "Omar"})
	assert [p.user_id for p in store.people()] == ["7", "12"]


def test_backup_is_checked_before_it_takes_its_name(store, tmp_path, monkeypatch):
	from zk_pull_desktop import store as store_module

	good = tmp_path / "good.db"
	store.backup(good)
	assert store_module.check_file(good)
	monkeypatch.setattr(store_module, "check_file", lambda path: False)
	bad = tmp_path / "bad.db"
	with pytest.raises(store_module.DamagedError):
		store.backup(bad)
	assert sorted(p.name for p in tmp_path.iterdir()) == ["good.db", "test.db"]


def test_days_never_pulled_are_reported(store):
	gate = store.save_device(Device(None, "Gate", "10.0.0.5"))
	store.mark_pulled(gate, "SN1", datetime(2026, 11, 10, 9), (date(2026, 11, 1), date(2026, 11, 3)))
	store.mark_pulled(gate, "SN1", datetime(2026, 11, 10, 9), (date(2026, 11, 5), date(2026, 11, 10)))
	missing = store.days_not_pulled([gate], date(2026, 10, 30), date(2026, 11, 30), date(2026, 11, 10))
	# Days after today are not counted: there can be no punches for them yet.
	assert missing == {gate: [date(2026, 10, 30), date(2026, 10, 31), date(2026, 11, 4)]}
	assert store.days_not_pulled([gate], date(2026, 11, 5), date(2026, 11, 9), date(2026, 11, 10)) == {}


def test_upgrade_takes_earlier_pulls_as_covering_until_the_last_pull(tmp_path):
	import sqlite3

	path = tmp_path / "old.db"
	s = Store(path)
	gate = s.save_device(Device(None, "Gate", "10.0.0.5"))
	s.add_punches([punch("1", "2026-10-20 08:00:00")])
	s.mark_pulled(gate, "SN1", datetime(2026, 11, 10, 9))
	s.close()
	with sqlite3.connect(path) as db:  # as a database from 0.4.0 has it
		db.execute("DROP TABLE pulled_ranges")
	s = Store(path)
	assert s.days_not_pulled([gate], date(2026, 10, 20), date(2026, 11, 10), date(2026, 11, 10)) == {}
	assert gate in s.days_not_pulled([gate], date(2026, 10, 1), date(2026, 11, 10), date(2026, 11, 10))
	s.close()


def test_check_file_does_not_create_a_missing_file(tmp_path):
	from zk_pull_desktop import store as store_module

	assert not store_module.check_file(tmp_path / "missing.db")
	assert not (tmp_path / "missing.db").exists()


def test_employees_are_people_and_ids_seen_in_punches(store):
	store.save_person(Person("12", "Sara", "HR"))
	store.save_person(Person("3", ""))
	store.add_punches([punch("7", "2026-11-01 08:00:00"), punch("12", "2026-11-01 08:00:00")])
	assert [(p.user_id, p.name) for p in store.employees()] == [("3", ""), ("7", ""), ("12", "Sara")]


def test_a_pull_covers_only_what_it_could_read(store):
	gate = store.save_device(Device(None, "Gate", "10.0.0.5"))
	store.mark_pulled(gate, "SN1", datetime(2026, 11, 18, 9, 30), (date(2026, 11, 1), date(2026, 11, 30)))
	# Still the 18th: the pull day counts, as "last pull 09:30" says how current it is.
	assert store.days_not_pulled([gate], date(2026, 11, 1), date(2026, 11, 30), date(2026, 11, 18)) == {}
	# On 1 December the 18th afternoon and the days after were never read.
	missing = store.days_not_pulled([gate], date(2026, 11, 1), date(2026, 11, 30), date(2026, 12, 1))
	assert missing[gate][0] == date(2026, 11, 18) and missing[gate][-1] == date(2026, 11, 30)
	store.mark_pulled(gate, "SN1", datetime(2026, 12, 1, 8), (date(2026, 11, 1), date(2026, 11, 30)))
	assert store.days_not_pulled([gate], date(2026, 11, 1), date(2026, 11, 30), date(2026, 12, 1)) == {}


def test_upgrade_seeds_a_pulled_device_without_punches_and_adds_the_pull_time(tmp_path):
	import sqlite3

	path = tmp_path / "old.db"
	s = Store(path)
	gate = s.save_device(Device(None, "Gate", "10.0.0.5"))
	s.mark_pulled(gate, "SN1", datetime(2026, 11, 10, 9))  # pulled, nothing stored
	s.close()
	with sqlite3.connect(path) as db:
		db.execute("DROP TABLE pulled_ranges")
	s = Store(path)
	assert s.days_not_pulled([gate], date(2026, 11, 9), date(2026, 11, 9), date(2026, 11, 20)) == {}
	s.close()

	with sqlite3.connect(path) as db:  # a table from 0.4.1 / 0.5.0, without pulled_at
		db.execute("DROP TABLE pulled_ranges")
		db.execute("CREATE TABLE pulled_ranges (device_id INTEGER, first_day TEXT, last_day TEXT)")
		db.execute("INSERT INTO pulled_ranges VALUES (?, '2026-11-01', '2026-11-30')", (gate,))
	s = Store(path)
	missing = s.days_not_pulled([gate], date(2026, 11, 1), date(2026, 11, 30), date(2026, 12, 1))
	assert missing[gate][0] == date(2026, 11, 10)  # the last pull, 10 Nov 09:00, is the best guess
	s.close()


def test_addresses_saved_by_older_versions_are_fixed(tmp_path):
	path = tmp_path / "db"
	s = Store(path)
	gate = s.save_device(Device(None, "Gate", "192.168.100.056"))
	s.close()
	s = Store(path)
	assert s.device(gate).ip == "192.168.100.56"
	s.close()


def test_adding_unnamed_ids_keeps_existing_departments(store):
	store.save_person(Person("7", "", "Warehouse"))
	store.add_people(["7", "8"])
	assert [(p.user_id, p.department) for p in store.people()] == [("7", "Warehouse"), ("8", "")]


def test_names_replaced_counts_only_changes(store):
	store.save_person(Person("1", "Ali"))
	store.save_person(Person("2", "Sara"))
	store.save_person(Person("3", ""))
	assert store.names_replaced({"1": "Ali", "2": "Sarah", "3": "Omar", "4": "Huda"}) == 1
