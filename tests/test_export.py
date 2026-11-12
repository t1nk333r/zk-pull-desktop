import csv
import re
from datetime import date, datetime, time

from openpyxl import load_workbook

from zk_pull_desktop import export, i18n
from zk_pull_desktop.people_tab import read_names_file
from zk_pull_desktop.periods import period_range
from zk_pull_desktop.store import PunchRow


def row(user_id, ts, name="", kind=0):
	return PunchRow(user_id, name, "", datetime.fromisoformat(ts), kind, 1, "Gate")


PUNCHES = [
	row("2", "2026-11-01 08:00:00", "سارة"),
	row("2", "2026-11-01 12:30:00", "سارة", 2),
	row("2", "2026-11-01 17:15:00", "سارة", 1),
	row("10", "2026-11-01 09:00:00", "=HYPERLINK(1)"),
]


def test_daily_rows_first_last_hours():
	sara, other = export.daily_rows(PUNCHES)
	assert (sara.user_id, sara.first, sara.last, sara.hours, sara.count) == (
		"2",
		time(8),
		time(17, 15),
		9.25,
		3,
	)
	assert (other.user_id, other.hours, other.count) == ("10", None, 1)


def test_csv_log_has_bom_and_escapes_formulas(tmp_path):
	path = tmp_path / "out.csv"
	assert export.write(path, PUNCHES, "csv", "log", "en") == 4
	assert path.read_bytes().startswith(b"\xef\xbb\xbf")
	with open(path, encoding="utf-8-sig", newline="") as f:
		rows = list(csv.reader(f))
	assert rows[0] == [
		"Employee ID",
		"Name",
		"Department",
		"Date",
		"Time",
		"Punch type",
		"Verified by",
		"Device",
	]
	assert rows[1] == ["2", "سارة", "", "2026-11-01", "08:00:00", "Check-in", "Fingerprint", "Gate"]
	assert rows[4][1] == "'=HYPERLINK(1)"


def test_xlsx_daily_has_real_dates_and_arabic_headers(tmp_path):
	path = tmp_path / "out.xlsx"
	export.write(path, PUNCHES, "xlsx", "daily", "ar")
	ws = load_workbook(path).active
	assert ws.sheet_view.rightToLeft
	assert ws["A1"].value == "رقم الموظف"
	assert ws["D2"].value.date() == date(2026, 11, 1)
	assert ws["D2"].number_format == "yyyy-mm-dd"
	assert ws["E2"].value == time(8) and ws["F2"].value == time(17, 15)
	assert ws["B3"].value == "=HYPERLINK(1)" and ws["B3"].data_type == "s"  # text, not a formula
	assert ws.freeze_panes == "A2"


def test_xlsx_keeps_names_as_typed_and_drops_control_characters(tmp_path):
	path = tmp_path / "out.xlsx"
	rows = [row("1", "2026-11-01 08:00:00", "-Ali-"), row("2\x01", "2026-11-01 08:00:00", "Sa\x02ra")]
	export.write(path, rows, "xlsx", "log", "en")
	ws = load_workbook(path).active
	assert ws["B2"].value == "-Ali-"  # no visible apostrophe: only "=" can start a formula in XLSX
	assert (ws["A3"].value, ws["B3"].value) == ("2", "Sara")


def test_arabic_export_has_no_hidden_direction_marks(tmp_path):
	path = tmp_path / "out.csv"
	export.write(path, [row("1", "2026-11-01 08:00:00", kind=255)], "csv", "log", "ar")
	text = path.read_text(encoding="utf-8-sig")
	assert "أخرى (255)" in text
	assert "\u2068" not in text and "\u2069" not in text


def test_default_filename():
	assert export.default_filename(date(2026, 11, 1), date(2026, 11, 30), "log", "csv") == (
		"attendance_2026-11-01_to_2026-11-30.csv"
	)


def test_every_text_has_both_languages_with_the_same_placeholders():
	for key, (en, ar) in i18n.TEXTS.items():
		assert en and ar, key
		assert set(re.findall(r"{(\w+)}", en)) == set(re.findall(r"{(\w+)}", ar)), key
		assert not re.search("[٠-٩]", ar), f"{key} uses Arabic-Indic digits"


def test_unknown_codes_are_labelled():
	assert i18n.punch_label(9, "en") == "Other (9)"
	assert i18n.verify_label(15, "ar") == "بصمة الوجه"


def test_periods():
	wednesday = date(2026, 11, 11)
	assert period_range("this_week", wednesday) == (date(2026, 11, 8), wednesday)  # from Sunday
	assert period_range("this_week", date(2026, 11, 8)) == (date(2026, 11, 8), date(2026, 11, 8))
	assert period_range("last_month", date(2026, 1, 15)) == (date(2025, 12, 1), date(2025, 12, 31))
	assert period_range("this_month", wednesday) == (date(2026, 11, 1), wednesday)
	assert period_range("yesterday", date(2026, 3, 1)) == (date(2026, 2, 28), date(2026, 2, 28))


def test_read_names_file_csv_and_xlsx(tmp_path):
	csv_path = tmp_path / "names.csv"
	csv_path.write_text("ID,Name\n1,Ali\n002,Sara\n,nobody\n", encoding="utf-8-sig")
	assert read_names_file(csv_path) == {"1": "Ali", "002": "Sara"}

	from openpyxl import Workbook

	wb = Workbook()
	wb.active.append([5, "Omar"])  # no header, ID typed as a number
	wb.active.append([6.0, "Huda"])
	xlsx_path = tmp_path / "names.xlsx"
	wb.save(xlsx_path)
	assert read_names_file(xlsx_path) == {"5": "Omar", "6": "Huda"}


def test_read_names_file_arabic_excel_csv(tmp_path):
	path = tmp_path / "names.csv"
	path.write_bytes("رقم الموظف,الاسم\n101,محمد\n".encode("cp1256"))  # Excel on Arabic Windows
	assert read_names_file(path) == {"101": "محمد"}


def test_read_names_file_header_detection(tmp_path):
	path = tmp_path / "names.csv"
	path.write_text("A101,Ali\nA102,Omar\n", encoding="utf-8")  # letter IDs, no header
	assert read_names_file(path) == {"A101": "Ali", "A102": "Omar"}
	path.write_text("\n,\nEmployee ID,Name\n7,Huda\n", encoding="utf-8")  # blank rows, then the header
	assert read_names_file(path) == {"7": "Huda"}
