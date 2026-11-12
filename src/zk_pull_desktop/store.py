"""Local SQLite database: devices, people (names for device user IDs), pulled punches and settings."""

import sqlite3
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
CREATE TABLE IF NOT EXISTS settings (
	key TEXT PRIMARY KEY,
	value TEXT NOT NULL
);
"""


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
			self.db.executescript(SCHEMA)
		except sqlite3.DatabaseError:
			self.db.close()  # so the damaged file can be moved aside (Windows locks open files)
			raise

	def check(self):
		result = self.db.execute("PRAGMA quick_check").fetchone()[0]
		if result != "ok":
			raise sqlite3.DatabaseError(f"database check failed: {result}")

	def close(self):
		self.db.close()

	def backup(self, path: Path):
		"""A consistent copy of the whole database, safe to take while the app runs."""
		target = sqlite3.connect(path)
		try:
			self.db.backup(target)
		finally:
			target.close()

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
		"""Every serial the given devices have reported."""
		ids = list(device_ids)
		rows = self.db.execute(
			f"SELECT serial FROM device_serials WHERE device_id IN ({','.join('?' * len(ids))})", ids
		)
		return [r["serial"] for r in rows]

	def serial_owner(self, serial) -> int | None:
		"""The device a serial number belongs to, if any."""
		row = self.db.execute("SELECT device_id FROM device_serials WHERE serial = ?", (serial,)).fetchone()
		return row["device_id"] if row else None

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
			self._remember_serial(d.id, d.serial)
		return d.id

	def delete_device(self, device_id):
		# Punches are kept: they are attendance history, not device configuration.
		with self.db:
			self.db.execute("DELETE FROM devices WHERE id = ?", (device_id,))
			self.db.execute("DELETE FROM device_serials WHERE device_id = ?", (device_id,))

	def mark_pulled(self, device_id, serial, when: datetime):
		with self.db:
			self.db.execute(
				"UPDATE devices SET serial = ?, last_pull = ? WHERE id = ?",
				(serial, when.strftime(TS_FORMAT), device_id),
			)
			self._remember_serial(device_id, serial)

	# People

	def people(self) -> list[Person]:
		rows = self.db.execute("SELECT * FROM people ORDER BY length(user_id), user_id")
		return [Person(**dict(r)) for r in rows]

	def save_person(self, p: Person):
		with self.db:
			self.db.execute(
				"INSERT INTO people (user_id, name, department) VALUES (?, ?, ?) "
				"ON CONFLICT (user_id) DO UPDATE SET name = excluded.name, department = excluded.department",
				(p.user_id.strip(), p.name.strip(), p.department.strip()),
			)

	def delete_person(self, user_id):
		with self.db:
			self.db.execute("DELETE FROM people WHERE user_id = ?", (user_id,))

	def import_names(self, names: dict[str, str], overwrite=False) -> int:
		"""Add names for user IDs; existing names are kept unless overwrite. Returns how many changed."""
		changed = 0
		with self.db:
			for user_id, name in names.items():
				user_id, name = user_id.strip(), name.strip()
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
			"LEFT JOIN (SELECT s.serial, min(d.name) AS name FROM device_serials s "
			"JOIN devices d ON d.id = s.device_id GROUP BY s.serial) d "
			"ON d.serial = p.serial "
			"WHERE p.ts >= ? AND p.ts < ?"
		)
		params = [start.strftime(DATE_FORMAT), (end + timedelta(days=1)).strftime(DATE_FORMAT)]
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
