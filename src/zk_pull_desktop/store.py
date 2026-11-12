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
		self.db.row_factory = sqlite3.Row
		self.db.executescript(SCHEMA)

	def close(self):
		self.db.close()

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

	def save_device(self, d: Device) -> int:
		with self.db:
			if d.id is None:
				cur = self.db.execute(
					"INSERT INTO devices (name, ip, port, comm_key, serial) VALUES (?, ?, ?, ?, ?)",
					(d.name, d.ip, d.port, d.comm_key, d.serial),
				)
				d.id = cur.lastrowid
			else:
				self.db.execute(
					"UPDATE devices SET name = ?, ip = ?, port = ?, comm_key = ?, serial = ? WHERE id = ?",
					(d.name, d.ip, d.port, d.comm_key, d.serial, d.id),
				)
		return d.id

	def delete_device(self, device_id):
		# Punches are kept: they are attendance history, not device configuration.
		with self.db:
			self.db.execute("DELETE FROM devices WHERE id = ?", (device_id,))

	def mark_pulled(self, device_id, serial, when: datetime):
		with self.db:
			self.db.execute(
				"UPDATE devices SET serial = ?, last_pull = ? WHERE id = ?",
				(serial, when.strftime(TS_FORMAT), device_id),
			)

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
			"LEFT JOIN (SELECT serial, min(name) AS name FROM devices WHERE serial != '' GROUP BY serial) d "
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
