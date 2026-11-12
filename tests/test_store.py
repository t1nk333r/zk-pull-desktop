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
