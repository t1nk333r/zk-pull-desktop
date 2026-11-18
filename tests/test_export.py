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


def test_xlsx_keeps_error_like_names_as_text_and_names_the_daily_sheet(tmp_path):
	path = tmp_path / "out.xlsx"
	export.write(
		path,
		[row("1", "2026-11-01 08:00:00", "#N/A"), row("2", "2026-11-01 08:00:00", "#REF!")],
		"xlsx",
		"daily",
		"en",
	)
	ws = load_workbook(path).active
	assert ws.title == "Daily summary"
	assert [(c.value, c.data_type) for c in (ws["B2"], ws["B3"])] == [("#N/A", "s"), ("#REF!", "s")]


def test_names_file_ids_with_letters_are_not_taken_for_a_header(tmp_path):
	path = tmp_path / "names.csv"
	path.write_text("NO101,Sara\nID102,Omar\n", encoding="utf-8")
	assert read_names_file(path) == {"NO101": "Sara", "ID102": "Omar"}


def test_names_file_with_semicolons_arabic_digits_and_line_breaks(tmp_path):
	path = tmp_path / "names.csv"
	path.write_text('رقم;الاسم\n١٢;"سارة\nأحمد"\n‏7;Omar\n', encoding="utf-8")
	assert read_names_file(path) == {"12": "سارة أحمد", "7": "Omar"}


def test_names_file_without_names_is_an_error(tmp_path):
	import pytest

	from zk_pull_desktop.people_tab import NamesFileError

	path = tmp_path / "names.csv"
	path.write_text("just one column\nand another line\n", encoding="utf-8")
	with pytest.raises(NamesFileError):
		read_names_file(path)


def test_csv_keeps_leading_zero_and_long_ids_and_escapes_error_literals(tmp_path):
	path = tmp_path / "out.csv"
	rows = [
		row("0012", "2026-11-01 08:00:00", "#N/A"),
		row("1234567890123456", "2026-11-01 08:00:00"),
		row("12", "2026-11-01 08:00:00"),
	]
	export.write(path, rows, "csv", "log", "en")
	with open(path, encoding="utf-8-sig", newline="") as f:
		data = list(csv.reader(f))[1:]
	assert [r[0] for r in data] == ['="0012"', '="1234567890123456"', "12"]
	assert data[0][1] == "'#N/A"


def test_a_failed_export_leaves_the_existing_file(tmp_path, monkeypatch):
	import pytest

	path = tmp_path / "out.xlsx"
	path.write_bytes(b"the export from yesterday")

	def broken(*args):
		raise OSError("network share dropped")

	monkeypatch.setattr(export, "_write_xlsx", broken)
	with pytest.raises(OSError):
		export.write(path, PUNCHES, "xlsx", "log", "en")
	assert path.read_bytes() == b"the export from yesterday"
	assert list(tmp_path.iterdir()) == [path]  # no temporary file left


def test_replacing_a_file_open_in_excel_is_reported_as_in_use(tmp_path, monkeypatch):
	import pytest

	def locked(src, dst):
		raise PermissionError(13, "Permission denied")

	monkeypatch.setattr(export.os, "replace", locked)
	with pytest.raises(export.FileInUseError):
		export.write(tmp_path / "out.csv", PUNCHES, "csv", "log", "en")


def test_one_bad_byte_in_a_utf8_names_file_is_an_error_not_mojibake(tmp_path):
	import pytest

	from zk_pull_desktop.people_tab import NamesFileError

	path = tmp_path / "names.csv"
	path.write_bytes("1,سارة\n2,محمد\n3,Ren".encode() + b"\xe9\n")  # one cp1252 byte, line 3
	with pytest.raises(NamesFileError, match="3"):
		read_names_file(path)
	path.write_bytes(b"\xef\xbb\xbf1,Ali\n2,Ren\xe9\n")  # a UTF-8 BOM says what the file is
	with pytest.raises(NamesFileError):
		read_names_file(path)


def test_names_file_in_utf16(tmp_path):
	import pytest

	from zk_pull_desktop.people_tab import NamesFileError

	path = tmp_path / "names.csv"
	path.write_bytes("1\tسارة\n2\tOmar\n".encode("utf-16"))  # Excel's "Unicode Text", with a BOM
	assert read_names_file(path) == {"1": "سارة", "2": "Omar"}
	path.write_bytes("1,Sara\n".encode("utf-16-le"))  # no BOM: refused, not read as junk
	with pytest.raises(NamesFileError):
		read_names_file(path)


def test_names_file_separator_inside_quotes_does_not_count(tmp_path):
	path = tmp_path / "names.csv"
	path.write_text('1;"Al-Ahmad, Mohammed"\n2;Sara\n', encoding="utf-8")
	assert read_names_file(path) == {"1": "Al-Ahmad, Mohammed", "2": "Sara"}
	path.write_text('1,"Ahmed; Jr"\n2,Sara\n', encoding="utf-8")
	assert read_names_file(path) == {"1": "Ahmed; Jr", "2": "Sara"}


def test_names_xlsx_keeps_leading_zeros_of_a_zero_padded_number(tmp_path):
	from openpyxl import Workbook

	wb = Workbook()
	wb.active.append([12, "Sara"])
	wb.active["A1"].number_format = "0000"  # shows 0012
	wb.active.append([7, "Omar"])
	path = tmp_path / "names.xlsx"
	wb.save(path)
	assert read_names_file(path) == {"0012": "Sara", "7": "Omar"}


def test_names_file_columns_are_found_by_their_headers(tmp_path):
	path = tmp_path / "names.csv"
	path.write_text("م,الرقم,الاسم\n1,1001,سارة\n2,1002,Omar\n", encoding="utf-8")  # serial first
	assert read_names_file(path) == {"1001": "سارة", "1002": "Omar"}
	path.write_text("Name,ID\nAli,7\nHuda,8\n", encoding="utf-8")  # name first
	assert read_names_file(path) == {"7": "Ali", "8": "Huda"}


def test_names_file_with_shifted_columns_is_refused(tmp_path):
	import pytest

	from zk_pull_desktop.people_tab import NamesFileError

	path = tmp_path / "names.csv"
	path.write_text("1,1001,Sara\n2,1002,Omar\n", encoding="utf-8")  # a serial column, no header
	with pytest.raises(NamesFileError):
		read_names_file(path)
	path.write_text("Ali,7\nHuda,8\n", encoding="utf-8")  # swapped, no header
	with pytest.raises(NamesFileError):
		read_names_file(path)


def test_names_file_with_an_open_quote_is_refused(tmp_path):
	import pytest

	from zk_pull_desktop.people_tab import NamesFileError

	path = tmp_path / "names.csv"
	path.write_text('1,Ali\n2,"Omar\n3,Saleh\n4,Fahd\n', encoding="utf-8")
	with pytest.raises(NamesFileError, match="2"):
		read_names_file(path)


def test_names_file_counts_ids_given_two_names(tmp_path):
	path = tmp_path / "names.csv"
	path.write_text("1,Ali\n2,Omar\n1,Ali Hassan\n2,Omar\n", encoding="utf-8")
	names = read_names_file(path)
	assert names == {"1": "Ali Hassan", "2": "Omar"} and names.duplicates == 1
