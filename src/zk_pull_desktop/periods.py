"""Quick date ranges for the Attendance tab."""

from datetime import date, timedelta

PERIODS = ("today", "yesterday", "this_week", "this_month", "last_month", "custom")


def period_range(period, today: date) -> tuple[date, date]:
	"""First and last day (both included). The week starts on Sunday, as the Saudi work week does."""
	if period == "yesterday":
		day = today - timedelta(days=1)
		return day, day
	if period == "this_week":
		return today - timedelta(days=(today.weekday() + 1) % 7), today
	if period == "this_month":
		return today.replace(day=1), today
	if period == "last_month":
		last = today.replace(day=1) - timedelta(days=1)
		return last.replace(day=1), last
	return today, today
