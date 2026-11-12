"""Write punches to CSV or XLSX, as a punch log or a daily summary.

CSV is UTF-8 with a byte order mark so Excel shows Arabic names correctly. XLSX gets real date and
time cells, so sorting and filtering work in Excel.
"""

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from .i18n import punch_label, tr, verify_label
from .store import PunchRow

LAYOUTS = ("log", "daily")
FORMATS = ("xlsx", "csv")

LOG_COLUMNS = (
	"col_user_id",
	"col_name",
	"col_department",
	"col_date",
	"col_time",
	"col_punch",
	"col_verify",
	"col_device",
)
DAILY_COLUMNS = (
	"col_user_id",
	"col_name",
	"col_department",
	"col_date",
	"col_first",
	"col_last",
	"col_hours",
	"col_count",
)


@dataclass(frozen=True)
class DailyRow:
	user_id: str
	name: str
	department: str
	day: date
	first: time
	last: time
	hours: float | None  # None when there is a single punch that day
	count: int


def daily_rows(punches: list[PunchRow]) -> list[DailyRow]:
	"""One row per person per day with the first and last punch, by date then employee ID."""
	groups: dict[tuple[str, date], list[PunchRow]] = defaultdict(list)
	for p in punches:
		groups[(p.user_id, p.timestamp.date())].append(p)
	rows = []
	for (user_id, day), items in groups.items():
		first = min(p.timestamp for p in items)
		last = max(p.timestamp for p in items)
		hours = round((last - first).total_seconds() / 3600, 2) if len(items) > 1 else None
		rows.append(
			DailyRow(
				user_id, items[0].name, items[0].department, day, first.time(), last.time(), hours, len(items)
			)
		)
	rows.sort(key=lambda r: (r.day, len(r.user_id), r.user_id))
	return rows


def _table(punches, layout, lang):
	"""(headers, rows) with Python date/time values; text is labelled in lang."""
	if layout == "daily":
		headers = [tr(c, lang) for c in DAILY_COLUMNS]
		rows = [
			[r.user_id, r.name, r.department, r.day, r.first, r.last, r.hours, r.count]
			for r in daily_rows(punches)
		]
	else:
		headers = [tr(c, lang) for c in LOG_COLUMNS]
		rows = [
			[
				p.user_id,
				p.name,
				p.department,
				p.timestamp.date(),
				p.timestamp.time(),
				punch_label(p.punch, lang, plain=True),
				verify_label(p.verify, lang, plain=True),
				p.device,
			]
			for p in punches
		]
	return headers, rows


def _clean(value):
	return ILLEGAL_CHARACTERS_RE.sub("", value) if isinstance(value, str) else value


def _safe_csv_text(value):
	# Names are typed by people; Excel must not run one that looks like a formula when opening the CSV.
	if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
		return "'" + value
	return value


def _csv_value(value):
	if isinstance(value, datetime):
		return value.strftime("%Y-%m-%d %H:%M:%S")
	if isinstance(value, date):
		return value.strftime("%Y-%m-%d")
	if isinstance(value, time):
		return value.strftime("%H:%M:%S")
	if value is None:
		return ""
	return _safe_csv_text(_clean(value))


def write(path: Path, punches: list[PunchRow], fmt="xlsx", layout="log", lang="en") -> int:
	"""Write the file and return the number of data rows."""
	headers, rows = _table(punches, layout, lang)
	if fmt == "csv":
		with open(path, "w", newline="", encoding="utf-8-sig") as f:
			writer = csv.writer(f)
			writer.writerow(headers)
			writer.writerows([_csv_value(v) for v in row] for row in rows)
	else:
		_write_xlsx(path, headers, rows, layout, lang)
	return len(rows)


def _write_xlsx(path, headers, rows, layout, lang):
	wb = Workbook()
	ws = wb.active
	ws.title = tr("layout_daily" if layout == "daily" else "tab_attendance", lang)[:31]
	ws.sheet_view.rightToLeft = lang == "ar"
	ws.append(headers)
	for cell in ws[1]:
		cell.font = Font(bold=True)
	for row in rows:
		ws.append([_clean(v) for v in row])
		for cell in ws[ws.max_row]:
			# openpyxl turns text starting with "=" into a formula; keep names as text, unchanged.
			if cell.data_type == "f":
				cell.data_type = "s"

	formats = {date: "yyyy-mm-dd", time: "hh:mm:ss"}
	for column in ws.iter_cols(min_row=2):
		for cell in column:
			for kind, number_format in formats.items():
				if isinstance(cell.value, kind) and not isinstance(cell.value, datetime):
					cell.number_format = number_format

	for i, header in enumerate(headers, start=1):
		width = max([len(header)] + [len(str(_csv_value(r[i - 1]))) for r in rows[:500]])
		ws.column_dimensions[get_column_letter(i)].width = min(max(width + 2, 10), 40)
	ws.freeze_panes = "A2"
	ws.auto_filter.ref = ws.dimensions
	wb.save(path)


def default_filename(start: date, end: date, layout, fmt):
	kind = "daily" if layout == "daily" else "attendance"
	return f"{kind}_{start:%Y-%m-%d}_to_{end:%Y-%m-%d}.{fmt}"
