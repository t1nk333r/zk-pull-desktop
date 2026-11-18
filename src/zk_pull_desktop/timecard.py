"""The Time Card of the ZKTeco attendance software: per employee per working day, on / off duty,
clock in / out, Late, Early, Absent, OT Time, Work Time and ATT_Time.

The rules were read off a real Time Card export (the same as in the zk_push ERP app). All figures
are whole minutes, worked out from the punches with their seconds and then truncated, as on the
device software's report (08:18:30 gives Late 18 and Work 08:41):
- Late: clock in after on duty + grace, counted from on duty (08:18 with 15 min grace = 18).
- Early: clock out before off duty - grace, counted to off duty. Neither is more than the shift.
- OT: time after off duty (or after the clock in, if that was later), counted in full once it
  reaches overtime_after minutes (with 60: 17:45 gives no OT, 18:18 gives 78). Arriving early is
  not overtime.
- Work: the part of on duty .. off duty that was attended. Minutes inside a grace period are not
  Late / Early but are not Work either.
- ATT: clock in to clock out.
- A missing clock in or out counts as missing_punch minutes Late / Early, taken off Work; the shift
  start / end stands in for it in ATT. A clock out at or before the clock in counts as missing.
- Clock in is the day's first punch and clock out its last; a lone punch after the middle of the
  shift is a clock out (the first punch was forgotten).
- A working day with no punches is Absent; a weekend day shows only if there are punches on it.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from .store import PunchRow


@dataclass(frozen=True)
class Timetable:
	name: str = "Daytime"
	on_duty: time = time(8)
	off_duty: time = time(17)
	late_grace: int = 15
	early_grace: int = 15
	overtime_after: int = 60
	missing_punch: int = 60
	weekend: frozenset[int] = field(default_factory=lambda: frozenset({4}))  # date.weekday(): Friday

	@classmethod
	def load(cls, get) -> "Timetable":
		"""From settings; get(key, default) is Store.get. A value that does not read falls back."""
		d = cls()

		def minutes(key, default):
			try:
				return min(max(int(get(key, default)), 0), 24 * 60)
			except ValueError:
				return default

		def clock(key, default):
			try:
				return time.fromisoformat(get(key, "") or default.isoformat("minutes"))
			except ValueError:
				return default

		weekend = get("tc_weekend", None)
		on, off = clock("tc_on", d.on_duty), clock("tc_off", d.off_duty)
		if off <= on:  # a night shift would need punches grouped across midnight
			on, off = d.on_duty, d.off_duty
		return cls(
			name=get("tc_name", "") or d.name,
			on_duty=on,
			off_duty=off,
			late_grace=minutes("tc_late", d.late_grace),
			early_grace=minutes("tc_early", d.early_grace),
			overtime_after=minutes("tc_ot", d.overtime_after),
			missing_punch=minutes("tc_missing", d.missing_punch),
			weekend=d.weekend
			if weekend is None
			else frozenset(int(x) for x in weekend.split(",") if x.isdigit() and int(x) < 7),
		)

	def save(self, set_):
		set_("tc_name", self.name)
		set_("tc_on", self.on_duty.isoformat("minutes"))
		set_("tc_off", self.off_duty.isoformat("minutes"))
		set_("tc_late", self.late_grace)
		set_("tc_early", self.early_grace)
		set_("tc_ot", self.overtime_after)
		set_("tc_missing", self.missing_punch)
		set_("tc_weekend", ",".join(str(d) for d in sorted(self.weekend)))


@dataclass
class Day:
	late: int = 0
	early: int = 0
	overtime: int = 0
	work: int = 0
	attended: int = 0


def minutes(delta: timedelta) -> int:
	return max(0, int(delta.total_seconds() // 60))


def place_single_punch(punch: datetime, on_duty: datetime, off_duty: datetime):
	"""(clock_in, clock_out) for a day with one punch."""
	if punch >= on_duty + (off_duty - on_duty) / 2:
		return None, punch
	return punch, None


def compute_day(on_duty, off_duty, clock_in, clock_out, t: Timetable) -> Day:
	day = Day()
	if clock_in and clock_out and clock_out <= clock_in:
		clock_out = None
	if not clock_in and not clock_out:
		return day

	shift = minutes(off_duty - on_duty)
	missing = min(t.missing_punch, shift)

	if not clock_in:
		day.late = missing
	elif clock_in > on_duty + timedelta(minutes=t.late_grace):
		day.late = minutes(min(clock_in, off_duty) - on_duty)

	if not clock_out:
		day.early = missing
	else:
		if clock_out < off_duty - timedelta(minutes=t.early_grace):
			day.early = minutes(off_duty - max(clock_out, on_duty))
		extra = minutes(clock_out - max(off_duty, clock_in or off_duty))
		if extra and extra >= t.overtime_after:
			day.overtime = extra

	start, end = clock_in or on_duty, clock_out or off_duty
	day.work = minutes(min(end, off_duty) - max(start, on_duty))
	if not clock_in or not clock_out:
		day.work = max(0, day.work - missing)
	day.attended = minutes(end - start)
	return day


def hhmm(total: int) -> str:
	"""78 -> "01:18"; 0 -> "" (blank, as on the device software's report)."""
	return f"{total // 60:02d}:{total % 60:02d}" if total else ""


@dataclass(frozen=True)
class CardRow:
	name: str
	day: date
	timetable: str
	on_duty: str
	off_duty: str
	clock_in: str
	clock_out: str
	late: str
	early: str
	absent: bool
	overtime: str
	work: str
	attended: str


def card_rows(
	punches: list[PunchRow],
	people: list[tuple[str, str]],
	start: date,
	end: date,
	t: Timetable,
	today: date,
) -> list[CardRow]:
	"""The Time Card of each of people ((user ID, name), in that order), day by day from start to
	end, up to today: there is nothing to show for days still to come."""
	by_day: dict[tuple[str, date], list[datetime]] = defaultdict(list)
	for p in punches:
		by_day[(p.user_id, p.timestamp.date())].append(p.timestamp)
	last = min(end, today)
	days = [start + timedelta(days=i) for i in range((last - start).days + 1)] if start <= last else []
	on_text, off_text = t.on_duty.strftime("%H:%M"), t.off_duty.strftime("%H:%M")
	rows = []
	for user_id, name in people:
		for day in days:
			stamps = sorted(by_day.get((user_id, day), []))
			if not stamps and day.weekday() in t.weekend:
				continue
			on, off = datetime.combine(day, t.on_duty), datetime.combine(day, t.off_duty)
			if len(stamps) == 1:
				clock_in, clock_out = place_single_punch(stamps[0], on, off)
			elif stamps:
				clock_in, clock_out = stamps[0], stamps[-1]
			else:
				clock_in = clock_out = None
			figures = compute_day(on, off, clock_in, clock_out, t)
			rows.append(
				CardRow(
					name=name or user_id,
					day=day,
					timetable=t.name,
					on_duty=on_text,
					off_duty=off_text,
					clock_in=clock_in.strftime("%H:%M") if clock_in else "",
					clock_out=clock_out.strftime("%H:%M") if clock_out else "",
					late=hhmm(figures.late),
					early=hhmm(figures.early),
					absent=not stamps,
					overtime=hhmm(figures.overtime),
					work=hhmm(figures.work),
					attended=hhmm(figures.attended),
				)
			)
	return rows
