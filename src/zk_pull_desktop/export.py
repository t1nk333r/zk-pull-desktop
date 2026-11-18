"""Write punches to CSV or XLSX, as a punch log, a daily summary or a time card.

CSV is UTF-8 with a byte order mark so Excel shows Arabic names correctly. XLSX gets real date and
time cells, so sorting and filtering work in Excel.
"""

import csv
import os
import re
from collections import defaultdict
from contextlib import suppress
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path

from openpyxl import Workbook
from openpyxl.cell.cell import ERROR_CODES, ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from .i18n import punch_label, tr, verify_label
from .store import PunchRow
from .timecard import Timetable, card_rows

LAYOUTS = ("log", "daily", "timecard")
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
# As in the ZKTeco software's Time Card export, with its column widths.
CARD_COLUMNS = (
	("col_name", 10),
	("col_date", 17),
	("col_timetable", 16.4),
	("col_on_duty", 13.1),
	("col_off_duty", 13.3),
	("col_clock_in", 13.7),
	("col_clock_out", 16.3),
	("col_late", 9),
	("col_early", 9),
	("col_absent", 11.9),
	("col_ot", 14.4),
	("col_work", 17.7),
	("col_att", 17),
)
CARD_DATE_FORMAT = "m/d/yyyy"  # 9/17/2026, as on the device software's card


@dataclass(frozen=True)
class CardRequest:
	"""What a time card needs besides the punches: who is on it, which days, and the shift."""

	people: list[tuple[str, str]]  # (user ID, name)
	start: date
	end: date
	timetable: Timetable
	now: datetime


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


def _table(punches, layout, lang, card=None):
	"""(headers, rows) with Python date/time values; text is labelled in lang."""
	if layout == "timecard":
		headers = [tr(c, lang) for c, _width in CARD_COLUMNS]
		yes = tr("absent_true", lang)
		rows = [
			[
				r.name, r.day, r.timetable, r.on_duty, r.off_duty, r.clock_in, r.clock_out, r.late,
				r.early, yes if r.absent else "", r.overtime, r.work, r.attended,
			]
			for r in card_rows(punches, card.people, card.start, card.end, card.timetable, card.now)
		]  # fmt: skip
	elif layout == "daily":
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
	# Names are typed by people; Excel must not run one that looks like a formula when opening the CSV,
	# or turn "#N/A" into an error cell that breaks SUM and VLOOKUP over the column.
	if isinstance(value, str) and (
		value[:1] in ("=", "+", "-", "@", "\t", "\r") or value.strip().upper() in ERROR_CODES
	):
		return "'" + value
	return value


def _csv_id(value):
	"""Excel reads a bare 0012 as the number 12, and keeps only 15 digits of a longer one."""
	digits = isinstance(value, str) and value.isascii() and value.isdigit()
	if digits and (len(value) > 15 or (len(value) > 1 and value.startswith("0"))):
		return f'="{value}"'
	return _csv_value(value)


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


class FileInUseError(PermissionError):
	"""The finished file could not take the place of the existing one: it is open in another program."""


def write(
	path: Path, punches: list[PunchRow], fmt="xlsx", layout="log", lang="en", card: CardRequest | None = None
) -> int:
	"""Write the file and return the number of data rows.

	Written next to it under a temporary name first, so a failure part-way (a network share that
	drops, a full disk) leaves an existing file as it was instead of half-written."""
	path = Path(path)
	headers, rows = _table(punches, layout, lang, card)
	temp = path.with_name(path.name + ".tmp")
	try:
		if fmt == "csv":
			with open(temp, "w", newline="", encoding="utf-8-sig") as f:
				writer = csv.writer(f)
				writer.writerow(headers)
				writer.writerows([_csv_id(row[0]), *(_csv_value(v) for v in row[1:])] for row in rows)
		else:
			_write_xlsx(temp, headers, rows, layout, lang, card)
		try:
			os.replace(temp, path)
		except PermissionError as e:
			raise FileInUseError(*e.args) from e
	finally:
		with suppress(OSError):
			temp.unlink(missing_ok=True)
	return len(rows)


def _sheet_title(layout, lang, card):
	"""31 characters at most, none of []:*?/\\. A one-person time card is named after the person."""
	if layout == "timecard" and card and len(card.people) == 1:
		user_id, name = card.people[0]
		title = re.sub(r"[\[\]:*?/\\]", " ", name or user_id).strip()[:31]
		if title:
			return title
	key = {"daily": "layout_daily_short", "timecard": "layout_timecard_short"}.get(layout, "tab_attendance")
	return tr(key, lang)


def _write_xlsx(path, headers, rows, layout, lang, card=None):
	wb = Workbook()
	ws = wb.active
	ws.title = _sheet_title(layout, lang, card)
	ws.sheet_view.rightToLeft = lang == "ar"
	ws.append(headers)
	for cell in ws[1]:
		cell.font = Font(bold=True)
	for row in rows:
		ws.append([_clean(v) for v in row])
		for cell in ws[ws.max_row]:
			# openpyxl turns text starting with "=" into a formula, and "#N/A" or "#REF!" into an error
			# cell; keep names as text, unchanged.
			if cell.data_type in ("f", "e"):
				cell.data_type = "s"

	formats = {date: CARD_DATE_FORMAT if layout == "timecard" else "yyyy-mm-dd", time: "hh:mm:ss"}
	for column in ws.iter_cols(min_row=2):
		for cell in column:
			for kind, number_format in formats.items():
				if isinstance(cell.value, kind) and not isinstance(cell.value, datetime):
					cell.number_format = number_format

	for i, header in enumerate(headers, start=1):
		if layout == "timecard":
			width = CARD_COLUMNS[i - 1][1]
		else:
			width = max([len(header)] + [len(str(_csv_value(r[i - 1]))) for r in rows[:500]])
			width = min(max(width + 2, 10), 40)
		ws.column_dimensions[get_column_letter(i)].width = width
	ws.freeze_panes = "A2"
	ws.auto_filter.ref = ws.dimensions
	wb.save(path)


def default_filename(start: date, end: date, layout, fmt):
	kind = {"daily": "daily", "timecard": "timecard"}.get(layout, "attendance")
	return f"{kind}_{start:%Y-%m-%d}_to_{end:%Y-%m-%d}.{fmt}"
