"""Check GitHub Releases for a newer version and install it.

The installer is downloaded over HTTPS from the project's own releases and checked against the
SHA-256 digest GitHub publishes for it, then run silently; it closes the app, upgrades it in place
(data in %LOCALAPPDATA% is untouched) and starts the new version.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import __version__

REPO = "t1nk333r/zk-pull-desktop"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"
SETUP_ASSET = re.compile(r"^ZK-Pull-Setup-[\d.]+\.exe$")


@dataclass(frozen=True)
class Release:
	version: str
	page_url: str
	setup_url: str  # empty when the release has no installer
	setup_sha256: str  # empty when GitHub gave no digest
	setup_size: int


def parse_version(text) -> tuple[int, ...]:
	return tuple(int(part) for part in re.findall(r"\d+", text)[:3])


def is_newer(latest: str, current: str = __version__) -> bool:
	return parse_version(latest) > parse_version(current)


def _get(url, timeout):
	request = urllib.request.Request(
		url, headers={"User-Agent": f"ZK-Pull/{__version__}", "Accept": "application/vnd.github+json"}
	)
	return urllib.request.urlopen(request, timeout=timeout)


def release_from_api(data: dict) -> Release:
	setup = next((a for a in data.get("assets", []) if SETUP_ASSET.match(a.get("name", ""))), None)
	digest = (setup or {}).get("digest") or ""
	return Release(
		version=data["tag_name"].lstrip("v"),
		page_url=data.get("html_url") or RELEASES_URL,
		setup_url=(setup or {}).get("browser_download_url", ""),
		setup_sha256=digest.removeprefix("sha256:") if digest.startswith("sha256:") else "",
		setup_size=(setup or {}).get("size", 0),
	)


class UpdateError(Exception):
	"""Raised with a message for the user; network errors are not about a device."""


def _network_error(e):
	reason = getattr(e, "reason", None) or getattr(e, "strerror", None) or e
	return UpdateError(f"no connection to GitHub ({reason})")


def latest_release(timeout=15) -> Release:
	try:
		with _get(API_URL, timeout) as response:
			return release_from_api(json.load(response))
	except urllib.error.HTTPError as e:
		raise UpdateError(f"GitHub answered HTTP {e.code}") from e
	except OSError as e:
		raise _network_error(e) from e
	except (ValueError, KeyError) as e:
		raise UpdateError("GitHub sent an unexpected answer") from e


# Where GitHub serves release files from, after the redirect from github.com.
DOWNLOAD_HOSTS = ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com")
DOWNLOAD_DEADLINE = 15 * 60  # seconds for the whole download, not per read
TEMP_PREFIX = "zk-pull-update-"


def download_setup(release: Release, folder: Path | None = None, timeout=60) -> Path:
	"""Download the installer and check it against GitHub's published SHA-256; returns its path."""
	if not release.setup_url.startswith(f"https://github.com/{REPO}/releases/download/"):
		raise UpdateError(f"unexpected download address: {release.setup_url!r}")
	if not release.setup_sha256 or not release.setup_size:
		raise UpdateError("the release has no published checksum")
	folder = Path(folder or tempfile.mkdtemp(prefix=TEMP_PREFIX))
	path = folder / f"ZK-Pull-Setup-{release.version}.exe"
	sha, size, started = hashlib.sha256(), 0, time.monotonic()
	try:
		with _get(release.setup_url, timeout) as response, open(path, "wb") as f:
			final = urllib.parse.urlsplit(getattr(response, "url", release.setup_url) or release.setup_url)
			if final.scheme != "https" or final.hostname not in DOWNLOAD_HOSTS:
				raise UpdateError(f"redirected to an unexpected address: {final.hostname}")
			while chunk := response.read(1 << 16):
				size += len(chunk)
				if size > release.setup_size:
					raise UpdateError("the download is larger than published")
				if time.monotonic() - started > DOWNLOAD_DEADLINE:
					raise UpdateError("the download is too slow")
				sha.update(chunk)
				f.write(chunk)
		if size != release.setup_size:
			raise UpdateError("the download is incomplete")
		if sha.hexdigest() != release.setup_sha256.lower():
			raise UpdateError("the download does not match the published checksum")
	except OSError as e:
		path.unlink(missing_ok=True)
		raise _network_error(e) from e
	except UpdateError:
		path.unlink(missing_ok=True)
		raise
	return path


def remove_old_downloads(keep: Path | None = None):
	"""Delete installers left in %TEMP% by earlier updates (about 35 MB each)."""
	for old in Path(tempfile.gettempdir()).glob(f"{TEMP_PREFIX}*"):
		if keep is not None and old == keep:
			continue
		shutil.rmtree(old, ignore_errors=True)


def installed() -> bool:
	"""True for the installed app; False for the portable zip and when running from source."""
	return bool(getattr(sys, "frozen", False)) and (Path(sys.executable).parent / "unins000.exe").exists()


def per_user_install() -> bool:
	"""The updater installs without admin rights, which only works for a per-user installation.

	Installed "for all users" (under Program Files), the silent installer would need a UAC prompt
	an HR account cannot approve; IT has to run the new installer instead.
	"""
	local = os.environ.get("LOCALAPPDATA")
	return bool(local) and Path(sys.executable).resolve().is_relative_to(Path(local).resolve())


def run_installer(path: Path):
	"""Start the installer and return at once; the caller must quit so the files can be replaced."""
	flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
	subprocess.Popen(
		[str(path), "/SP-", "/SILENT", "/NOCANCEL", "/CLOSEAPPLICATIONS", "/NORESTART"],
		creationflags=flags,
		close_fds=True,
	)
