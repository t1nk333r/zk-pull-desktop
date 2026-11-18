"""The Time Card against rows of a real card exported by the ZKTeco software (Daytime 08:00-17:00,
15 minutes grace, overtime from 60 minutes, Friday off)."""

import csv
from datetime import date, datetime, time

from openpyxl import load_workbook

from zk_pull_desktop import export
from zk_pull_desktop.store import PunchRow
from zk_pull_desktop.timecard import Timetable, card_rows, compute_day, hhmm

T = Timetable()
DAY = date(2026, 9, 28)  # a Monday
ON, OFF = datetime.combine(DAY, T.on_duty), datetime.combine(DAY, T.off_duty)


def at(hour, minute, second=0, day=DAY):
	return datetime.combine(day, time(hour, minute, second))


def card(clock_in, clock_out, t=T):
	"""late, early, OT, work, ATT as the device software prints them."""
	d = compute_day(ON, OFF, clock_in, clock_out, t)
	return hhmm(d.late), hhmm(d.early), hhmm(d.overtime), hhmm(d.work), hhmm(d.attended)


def punch(ts, user_id="12"):
	return PunchRow(user_id, "Cris", "", ts, 0, 1, "Gate")


def test_rows_of_the_real_card():
	assert card(at(7, 56, 40), at(18, 18)) == ("", "", "01:18", "09:00", "10:21")
	assert card(at(7, 45), at(17, 45)) == ("", "", "", "09:00", "10:00")  # below the OT threshold
	assert card(at(8, 18, 30), at(17, 0)) == ("00:18", "", "", "08:41", "08:41")  # late from 08:00
	assert card(at(8, 11, 30), at(17, 14)) == ("", "", "", "08:48", "09:02")  # inside the grace
	assert card(at(7, 57, 40), None) == ("", "01:00", "", "08:00", "09:02")  # no clock out


def test_early_leave_missing_clock_in_and_late_with_overtime():
	assert card(at(9, 11), at(15, 5)) == ("01:11", "01:55", "", "05:54", "05:54")
	assert card(None, at(17, 0)) == ("01:00", "", "", "08:00", "09:00")
	assert card(at(9, 0), at(18, 30)) == ("01:00", "", "01:30", "08:00", "09:30")


def test_thresholds_are_inclusive_and_configurable():
	assert card(at(8, 0), at(18, 0))[2] == "01:00"
	assert card(at(8, 0), at(17, 59, 59))[2] == ""
	assert card(at(8, 0), at(16, 45))[1] == ""
	assert card(at(8, 0), at(16, 44))[1] == "00:16"
	assert card(at(8, 0), at(17, 45), Timetable(overtime_after=30))[2] == "00:45"


def test_clock_out_before_clock_in_counts_as_missing():
	d = compute_day(ON, OFF, at(17, 0), at(8, 0), T)
	assert (d.late, d.early, d.work) == (540, 60, 0)


def test_card_rows_mark_absent_days_skip_fridays_and_days_to_come():
	punches = [
		punch(at(7, 45, day=date(2026, 9, 17))),
		punch(at(12, 0, day=date(2026, 9, 17))),  # punches in between are not clock in / out
		punch(at(17, 11, day=date(2026, 9, 17))),
		punch(at(17, 5, day=date(2026, 9, 19))),  # a lone punch late in the day is the clock out
	]
	rows = card_rows(
		punches, [("12", "Cris")], date(2026, 9, 17), date(2026, 9, 30), T, at(18, 0, day=date(2026, 9, 21))
	)
	assert [(r.day.day, r.clock_in, r.clock_out, r.absent) for r in rows] == [
		(17, "07:45", "17:11", False),
		# 18th: Friday, no punches, not on the card
		(19, "", "17:05", False),
		(20, "", "", True),
		(21, "", "", True),
		# the 22nd onwards are after today
	]
	assert rows[1].late == "01:00"  # the missing clock in


def test_a_weekend_day_with_punches_is_on_the_card():
	friday = date(2026, 9, 18)
	rows = card_rows(
		[punch(at(9, 0, day=friday)), punch(at(13, 0, day=friday))],
		[("12", "Cris")],
		friday,
		friday,
		T,
		at(18, 0, day=friday),
	)
	assert [(r.clock_in, r.clock_out) for r in rows] == [("09:00", "13:00")]


def test_unnamed_employee_is_shown_by_id():
	rows = card_rows([], [("0012", "")], DAY, DAY, T, at(18, 0))
	assert (rows[0].name, rows[0].absent) == ("0012", True)


def test_timetable_settings_round_trip_and_bad_values_fall_back():
	saved = {}
	t = Timetable("Morning", time(7, 30), time(15, 30), 10, 5, 30, 45, frozenset({4, 5}))
	t.save(lambda key, value: saved.__setitem__(key, str(value)))
	assert Timetable.load(lambda key, default="": saved.get(key, default)) == t
	assert Timetable.load(lambda key, default="": default) == Timetable()
	broken = {"tc_on": "18:00", "tc_off": "06:00", "tc_late": "soon"}
	loaded = Timetable.load(lambda key, default="": broken.get(key, default))
	assert (loaded.on_duty, loaded.off_duty, loaded.late_grace) == (time(8), time(17), 15)


def card_request(people=(("12", "Cris"),)):
	return export.CardRequest(
		list(people), date(2026, 9, 17), date(2026, 9, 21), T, datetime(2026, 11, 18, 12)
	)


PUNCHES = [punch(at(7, 45, 40, date(2026, 9, 17))), punch(at(17, 11, 0, date(2026, 9, 17)))]


def test_xlsx_time_card_is_laid_out_like_the_device_softwares(tmp_path):
	path = tmp_path / "card.xlsx"
	assert export.write(path, PUNCHES, "xlsx", "timecard", "en", card_request()) == 4  # 17, 19, 20, 21
	ws = load_workbook(path).active
	assert ws.title == "Cris"
	assert [c.value for c in ws[1]] == [
		"Name", "Date", "Timetable", "On duty", "Off duty", "Clock In", "Clock Out", "Late", "Early",
		"Absent", "OT Time", "Work Time", "ATT_Time",
	]  # fmt: skip
	assert [c.value for c in ws[2]][2:] == ["Daytime", "08:00", "17:00", "07:45", "17:11"] + [None] * 4 + [
		"09:00",
		"09:25",
	]
	assert ws["B2"].value.date() == date(2026, 9, 17) and ws["B2"].number_format == "m/d/yyyy"
	assert ws["J4"].value == "True"  # the 20th
	assert ws.column_dimensions["B"].width == 17


def test_csv_time_card_has_iso_dates_and_arabic_headers(tmp_path):
	# Excel reads 10/5/2026 as 10 May on Arabic and UK Windows; 2026-10-05 reads the same everywhere.
	path = tmp_path / "card.csv"
	export.write(path, PUNCHES, "csv", "timecard", "ar", card_request([("0012", "")]))
	with open(path, encoding="utf-8-sig", newline="") as f:
		rows = list(csv.reader(f))
	assert rows[0][0] == "الاسم" and rows[0][9] == "غائب"
	assert rows[1][:2] == ['="0012"', "2026-09-17"] and rows[1][9] == "نعم"  # no punches for 0012


def test_a_finger_pressed_twice_is_one_punch():
	rows = card_rows([punch(at(8, 0, 5)), punch(at(8, 0, 40))], [("12", "Cris")], DAY, DAY, T, at(18, 0))
	assert (rows[0].clock_in, rows[0].clock_out, rows[0].early) == ("08:00", "", "01:00")
	rows = card_rows([punch(at(17, 30)), punch(at(17, 31))], [("12", "Cris")], DAY, DAY, T, at(18, 0))
	assert (rows[0].clock_in, rows[0].clock_out, rows[0].late) == ("", "17:30", "01:00")


def test_today_is_left_out_until_off_duty():
	punches = [punch(at(7, 50))]
	assert card_rows(punches, [("12", "Cris")], DAY, DAY, T, at(11, 0)) == []
	assert len(card_rows(punches, [("12", "Cris")], DAY, DAY, T, at(17, 0))) == 1
