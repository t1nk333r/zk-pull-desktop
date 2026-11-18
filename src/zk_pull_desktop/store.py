"""Local SQLite database: devices, people (names for device user IDs), pulled punches and settings."""

import ipaddress
import os
import sqlite3
from contextlib import closing, suppress
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from .device import DEFAULT_PORT, Punch

DATE_FORMAT = "%Y-%m-%d"
TS_FORMAT = f"{DATE_FORMAT} %H:%M:%S"

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
	id INTEGER PRIMARY KEY,
	name TEXT NOT NULL,
	ip TEXT NOT NULL,
	port INTEGER NOT NULL DEFAULT 4370,
	comm_key INTEGER NOT NULL DEFAULT 0,
	serial TEXT NOT NULL DEFAULT '',
	last_pull TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS people (
	user_id TEXT PRIMARY KEY,
	name TEXT NOT NULL DEFAULT '',
	department TEXT NOT NULL DEFAULT ''
);
-- The key makes pulling the same period again harmless: a punch is stored once.
CREATE TABLE IF NOT EXISTS punches (
	serial TEXT NOT NULL,
	user_id TEXT NOT NULL,
	ts TEXT NOT NULL,
	punch INTEGER NOT NULL,
	verify INTEGER NOT NULL,
	PRIMARY KEY (serial, user_id, ts)
);
CREATE INDEX IF NOT EXISTS punches_ts ON punches (ts);
-- Every serial number a device has reported. A replaced mainboard brings a new serial, and the
-- punches pulled under the old one still belong to the device.
CREATE TABLE IF NOT EXISTS device_serials (
	device_id INTEGER NOT NULL,
	serial TEXT NOT NULL,
	PRIMARY KEY (device_id, serial)
);
INSERT OR IGNORE INTO device_serials (device_id, serial) SELECT id, serial FROM devices WHERE serial != '';
-- The days each pull was asked for (both included) and when it ran. A day no pull covered shows no
-- punches, which looks the same as everyone being absent, so the app warns about such days. Only
-- days before pulled_at are complete: punches made later in the day, or on days after, were not read.
CREATE TABLE IF NOT EXISTS pulled_ranges (
	device_id INTEGER NOT NULL,
	first_day TEXT NOT NULL,
	last_day TEXT NOT NULL,
	pulled_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS settings (
	key TEXT PRIMARY KEY,
	value TEXT NOT NULL
);
"""


# Arabic-Indic and Persian digits typed or pasted as an employee ID are the same ID as on the device,
# and pasted text can carry invisible direction marks.
_ID_TABLE = str.maketrans(
	{**{0x0660 + i: str(i) for i in range(10)}, **{0x06F0 + i: str(i) for i in range(10)}}
	| dict.fromkeys([0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F), *range(0x2066, 0x206A)])
)


def normalize_id(text: str) -> str:
	return str(text).translate(_ID_TABLE).strip()


def normalize_ip(text: str) -> str | None:
	"""The address as Windows should get it, or None if it is not a device on the office network.

	Leading zeros are dropped: Windows reads 192.168.100.056 as octal and connects to .46."""
	parts = normalize_id(text).split(".")
	if len(parts) != 4 or not all(p.isascii() and p.isdigit() for p in parts):
		return None  # hostnames too: the app is for the LAN, by address
	try:
		address = ipaddress.IPv4Address(".".join(str(int(p)) for p in parts))
	except ValueError:
		return None
	if address.is_global or address.is_multicast or address.is_unspecified:
		return None
	return str(address)


class DamagedError(sqlite3.DatabaseError):
	"""The database file is corrupt, as opposed to locked or unreadable for the moment."""


def is_damaged(e: sqlite3.DatabaseError) -> bool:
	return isinstance(e, DamagedError) or getattr(e, "sqlite_errorname", "") in (
		"SQLITE_CORRUPT",
		"SQLITE_NOTADB",
	)


def check_file(path: Path) -> bool:
	"""True if the database file at path opens and passes a quick check, without writing to it.

	A plain path, not a file: URI: on a mapped drive or a \\\\server\\share folder the URI names a server,
	which SQLite refuses."""
	if not Path(path).is_file():  # connect would create an empty database
		return False
	try:
		with closing(sqlite3.connect(path)) as db:
			db.execute("PRAGMA query_only = ON")
			return db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
	except sqlite3.Error:
		return False


# (device_id, serial) for every serial a device is known by: the ones it was pulled from, and the one
# Test read, which is the only one before its first pull.
KNOWN_SERIALS = (
	"SELECT device_id, serial FROM device_serials UNION SELECT id, serial FROM devices WHERE serial != ''"
)


@dataclass
class Device:
	id: int | None
	name: str
	ip: str
	port: int = DEFAULT_PORT
	comm_key: int = 0
	serial: str = ""
	last_pull: str = ""


@dataclass
class Person:
	user_id: str
	name: str
	department: str = ""


@dataclass(frozen=True)
class PunchRow:
	"""A stored punch joined with the person's name and the device's name."""

	user_id: str
	name: str
	department: str
	timestamp: datetime
	punch: int
	verify: int
	device: str


class Store:
	def __init__(self, path: Path | str):
		self.db = sqlite3.connect(path)
		try:
			self.db.row_factory = sqlite3.Row
			self.check()
			new_ranges = not self._has_table("pulled_ranges")
			self.db.executescript(SCHEMA)
			if new_ranges:
				self._assume_pulled_so_far()
			elif not self._has_column("pulled_ranges", "pulled_at"):
				self._add_pulled_at()
			self._normalize_device_addresses()
		except sqlite3.DatabaseError:
			self.db.close()  # so the damaged file can be moved aside (Windows locks open files)
			raise

	def _has_table(self, name) -> bool:
		sql = "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?"
		return self.db.execute(sql, (name,)).fetchone() is not None

	def _has_column(self, table, column) -> bool:
		return any(r["name"] == column for r in self.db.execute(f"PRAGMA table_info({table})"))

	def _assume_pulled_so_far(self):
		"""Versions before 0.4.1 did not record which days a pull covered. Take each device as pulled
		from its first stored punch (from 2000, when ZK clocks start, if it has none) up to its last pull, as those
		versions showed it, rather than warn about every day pulled before the upgrade."""
		with self.db:
			self.db.execute(
				"INSERT INTO pulled_ranges (device_id, first_day, last_day, pulled_at) "
				"SELECT d.id, coalesce(min(substr(p.ts, 1, 10)), '2000-01-01'), "
				"substr(d.last_pull, 1, 10), d.last_pull "
				f"FROM devices d LEFT JOIN ({KNOWN_SERIALS}) s ON s.device_id = d.id "
				"LEFT JOIN punches p ON p.serial = s.serial WHERE d.last_pull != '' GROUP BY d.id"
			)

	def _add_pulled_at(self):
		"""0.4.1 and 0.5.0 did not record when a pull ran. Its device's last pull is the best guess."""
		with self.db:
			self.db.execute("ALTER TABLE pulled_ranges ADD COLUMN pulled_at TEXT NOT NULL DEFAULT ''")
			self.db.execute(
				"UPDATE pulled_ranges SET pulled_at = "
				"coalesce((SELECT last_pull FROM devices d WHERE d.id = device_id), '')"
			)

	def _normalize_device_addresses(self):
		"""Addresses saved before 0.4.1 were not checked: 192.168.100.056 reaches .46 on Windows."""
		with self.db:
			for row in self.db.execute("SELECT id, ip FROM devices").fetchall():
				ip = normalize_ip(row["ip"])
				if ip and ip != row["ip"]:
					self.db.execute("UPDATE devices SET ip = ? WHERE id = ?", (ip, row["id"]))

	def check(self):
		result = self.db.execute("PRAGMA quick_check").fetchone()[0]
		if result != "ok":
			raise DamagedError(f"database check failed: {result}")

	def close(self):
		self.db.close()

	def backup(self, path: Path):
		"""A consistent copy of the whole database, safe to take while the app runs.

		Written under a temporary name and checked before it takes the final name, so a full disk or
		a crash never leaves a broken file that looks like a good backup."""
		path = Path(path)
		temp = path.with_name(path.name + ".tmp")
		try:
			with closing(sqlite3.connect(temp)) as target:
				self.db.backup(target)
			if not check_file(temp):
				raise DamagedError(f"the copy at {temp} failed its check")
			os.replace(temp, path)
		finally:
			for leftover in (temp, temp.with_name(temp.name + "-journal")):
				with suppress(OSError):
					leftover.unlink(missing_ok=True)

	# Settings

	def get(self, key, default=""):
		row = self.db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
		return row["value"] if row else default

	def set(self, key, value):
		with self.db:
			self.db.execute(
				"INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
				(key, str(value)),
			)

	# Devices

	def devices(self) -> list[Device]:
		return [Device(**dict(r)) for r in self.db.execute("SELECT * FROM devices ORDER BY name, id")]

	def device(self, device_id) -> Device | None:
		row = self.db.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
		return Device(**dict(row)) if row else None

	def serials(self, device_ids) -> list[str]:
		"""Every serial the given devices are known by."""
		ids = list(device_ids)
		rows = self.db.execute(
			f"SELECT serial FROM ({KNOWN_SERIALS}) WHERE device_id IN ({','.join('?' * len(ids))})", ids
		)
		return [r["serial"] for r in rows]

	def serial_owner(self, serial) -> int | None:
		"""The device a serial number belongs to, if any: one it was pulled from, else one whose Test
		read it."""
		row = self.db.execute(
			f"SELECT device_id FROM ({KNOWN_SERIALS}) WHERE serial = ? ORDER BY device_id LIMIT 1", (serial,)
		).fetchone()
		return row[0] if row else None

	def _remember_serial(self, device_id, serial):
		if serial:
			self.db.execute(
				"INSERT OR IGNORE INTO device_serials (device_id, serial) VALUES (?, ?)", (device_id, serial)
			)

	def save_device(self, d: Device) -> int:
		with self.db:
			if d.id is None:
				cur = self.db.execute(
					"INSERT INTO devices (name, ip, port, comm_key, serial) VALUES (?, ?, ?, ?, ?)",
					(d.name, d.ip, d.port, d.comm_key, d.serial),
				)
				d.id = cur.lastrowid
			else:
				# An empty serial means "not tested in the dialog": keep the one the last pull stored.
				self.db.execute(
					"UPDATE devices SET name = ?, ip = ?, port = ?, comm_key = ?, "
					"serial = coalesce(nullif(?, ''), serial) WHERE id = ?",
					(d.name, d.ip, d.port, d.comm_key, d.serial, d.id),
				)
			# A serial read by Test is not added to device_serials: a mistyped IP would claim another
			# device's serial for good. Only a confirmed pull (mark_pulled) does that.
		return d.id

	def delete_device(self, device_id):
		# Punches are kept: they are attendance history, not device configuration.
		with self.db:
			self.db.execute("DELETE FROM devices WHERE id = ?", (device_id,))
			self.db.execute("DELETE FROM device_serials WHERE device_id = ?", (device_id,))
			self.db.execute("DELETE FROM pulled_ranges WHERE device_id = ?", (device_id,))

	def mark_pulled(self, device_id, serial, when: datetime, period: tuple[date, date] | None = None) -> bool:
		"""Record a pull of the days in period; False if the device no longer exists (deleted during
		the pull)."""
		with self.db:
			updated = self.db.execute(
				"UPDATE devices SET serial = ?, last_pull = ? WHERE id = ?",
				(serial, when.strftime(TS_FORMAT), device_id),
			).rowcount
			if updated:
				self._remember_serial(device_id, serial)
				if period is not None:
					start, end = (d.strftime(DATE_FORMAT) for d in period)
					self.db.execute(
						"INSERT INTO pulled_ranges (device_id, first_day, last_day, pulled_at) VALUES (?, ?, ?, ?)",
						(device_id, start, end, when.strftime(TS_FORMAT)),
					)
		return bool(updated)

	def days_not_pulled(self, device_ids, start: date, end: date, today: date) -> dict[int, list[date]]:
		"""Device ID -> the days from start to end, up to today, that no pull of it read in full.

		A pull reads a day in full only if it ran after that day: a pull of "this month" at 09:30
		has not read the afternoon, nor the days after. The day of the pull still counts while it is
		today, as the last pull time shown says how current it is."""
		end = min(end, today)
		if start > end:
			return {}
		days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
		missing = {}
		for device_id in device_ids:
			ranges = self.db.execute(
				"SELECT first_day, last_day, pulled_at FROM pulled_ranges "
				"WHERE device_id = ? AND first_day <= ? AND last_day >= ?",
				(device_id, end.strftime(DATE_FORMAT), start.strftime(DATE_FORMAT)),
			).fetchall()
			covered = []
			for r in ranges:
				first, last = date.fromisoformat(r["first_day"]), date.fromisoformat(r["last_day"])
				ran = date.fromisoformat(r["pulled_at"][:10]) if r["pulled_at"] else last + timedelta(days=1)
				# Complete up to the day before the pull; the pull day itself while it is today.
				covered.append((first, min(last, ran if ran == today else ran - timedelta(days=1))))
			gaps = [day for day in days if not any(a <= day <= b for a, b in covered)]
			if gaps:
				missing[device_id] = gaps
		return missing

	# People

	def people(self) -> list[Person]:
		rows = self.db.execute("SELECT * FROM people ORDER BY length(user_id), user_id")
		return [Person(**dict(r)) for r in rows]

	def save_person(self, p: Person):
		with self.db:
			self.db.execute(
				"INSERT INTO people (user_id, name, department) VALUES (?, ?, ?) "
				"ON CONFLICT (user_id) DO UPDATE SET name = excluded.name, department = excluded.department",
				(normalize_id(p.user_id), p.name.strip(), p.department.strip()),
			)

	def delete_person(self, user_id):
		with self.db:
			self.db.execute("DELETE FROM people WHERE user_id = ?", (user_id,))

	def add_people(self, user_ids):
		"""List IDs in People without a name; IDs already there are left as they are."""
		with self.db:
			self.db.executemany(
				"INSERT OR IGNORE INTO people (user_id) VALUES (?)", [(normalize_id(i),) for i in user_ids]
			)

	def names_replaced(self, names: dict[str, str]) -> int:
		"""How many names already typed in People would change if names were imported over them."""
		current = {p.user_id: p.name for p in self.people() if p.name}
		return sum(
			1
			for user_id, name in names.items()
			if current.get(normalize_id(user_id), name.strip()) != name.strip()
		)

	def import_names(self, names: dict[str, str], overwrite=False) -> int:
		"""Add names for user IDs; existing names are kept unless overwrite. Returns how many changed."""
		changed = 0
		with self.db:
			for user_id, name in names.items():
				user_id, name = normalize_id(user_id), name.strip()
				if not user_id or not name:
					continue
				if overwrite:
					sql = (
						"INSERT INTO people (user_id, name) VALUES (?, ?) "
						"ON CONFLICT (user_id) DO UPDATE SET name = excluded.name WHERE name != excluded.name"
					)
				else:
					sql = (
						"INSERT INTO people (user_id, name) VALUES (?, ?) "
						"ON CONFLICT (user_id) DO UPDATE SET name = excluded.name WHERE name = ''"
					)
				changed += self.db.execute(sql, (user_id, name)).rowcount
		return changed

	def employees(self) -> list[Person]:
		"""Everyone with a name or with punches, by ID: the choices for showing one employee."""
		rows = self.db.execute(
			"SELECT u.user_id, coalesce(n.name, '') AS name, coalesce(n.department, '') AS department "
			"FROM (SELECT user_id FROM people UNION SELECT user_id FROM punches) u "
			"LEFT JOIN people n ON n.user_id = u.user_id ORDER BY length(u.user_id), u.user_id"
		)
		return [Person(**dict(r)) for r in rows]

	def unnamed_user_ids(self) -> list[str]:
		"""User IDs that have punches but no name yet."""
		rows = self.db.execute(
			"SELECT DISTINCT p.user_id FROM punches p LEFT JOIN people n ON n.user_id = p.user_id "
			"WHERE n.name IS NULL OR n.name = '' ORDER BY length(p.user_id), p.user_id"
		)
		return [r["user_id"] for r in rows]

	# Punches

	def add_punches(self, punches: list[Punch]) -> int:
		"""Store punches, skipping ones already stored. Returns how many were new."""
		with self.db:
			before = self.db.total_changes
			self.db.executemany(
				"INSERT OR IGNORE INTO punches (serial, user_id, ts, punch, verify) VALUES (?, ?, ?, ?, ?)",
				[(p.serial, p.user_id, p.timestamp.strftime(TS_FORMAT), p.punch, p.verify) for p in punches],
			)
			return self.db.total_changes - before

	def punches(self, start: date, end: date, serials: list[str] | None = None) -> list[PunchRow]:
		"""Punches from start to end, both days included, oldest first."""
		sql = (
			"SELECT p.user_id, coalesce(n.name, '') AS name, coalesce(n.department, '') AS department, "
			"p.ts, p.punch, p.verify, coalesce(nullif(d.name, ''), p.serial) AS device "
			"FROM punches p "
			"LEFT JOIN people n ON n.user_id = p.user_id "
			f"LEFT JOIN (SELECT s.serial, min(d.name) AS name FROM ({KNOWN_SERIALS}) s "
			"JOIN devices d ON d.id = s.device_id GROUP BY s.serial) d "
			"ON d.serial = p.serial "
			"WHERE p.ts >= ? AND p.ts <= ?"
		)
		# "~" sorts after every digit, so "<end> ~" is after every time on the end day.
		params = [start.strftime(DATE_FORMAT), end.strftime(DATE_FORMAT) + " ~"]
		if serials is not None:
			sql += f" AND p.serial IN ({','.join('?' * len(serials))})"
			params += serials
		sql += " ORDER BY p.ts, length(p.user_id), p.user_id"
		return [
			PunchRow(
				r["user_id"],
				r["name"],
				r["department"],
				datetime.strptime(r["ts"], TS_FORMAT),
				r["punch"],
				r["verify"],
				r["device"],
			)
			for r in self.db.execute(sql, params)
		]
