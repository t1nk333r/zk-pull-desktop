import hashlib
import io

import pytest

from zk_pull_desktop import updater

URL = "https://github.com/t1nk333r/zk-pull-desktop/releases/download/v0.2.0/ZK-Pull-Setup-0.2.0.exe"
PAYLOAD = b"installer bytes"
DIGEST = "sha256:" + hashlib.sha256(PAYLOAD).hexdigest()


def api(digest=DIGEST):
	return {
		"tag_name": "v0.2.0",
		"html_url": "https://github.com/t1nk333r/zk-pull-desktop/releases/tag/v0.2.0",
		"assets": [
			{"name": "ZK-Pull-Portable-0.2.0.zip", "browser_download_url": "x", "size": 9},
			{
				"name": "ZK-Pull-Setup-0.2.0.exe",
				"browser_download_url": URL,
				"size": len(PAYLOAD),
				"digest": digest,
			},
		],
	}


def test_versions():
	assert updater.is_newer("0.2.0", "0.1.0")
	assert updater.is_newer("0.10.0", "0.9.9")  # compared as numbers, not text
	assert not updater.is_newer("0.1.0", "0.1.0")
	assert not updater.is_newer("v0.1.0", "0.2.0")


def test_release_picks_the_installer_and_its_digest():
	release = updater.release_from_api(api())
	assert (release.version, release.setup_url, release.setup_size) == ("0.2.0", URL, len(PAYLOAD))
	assert release.setup_sha256 == hashlib.sha256(PAYLOAD).hexdigest()


@pytest.fixture
def serve(monkeypatch):
	monkeypatch.setattr(updater, "_get", lambda url, timeout: io.BytesIO(PAYLOAD))


def test_download_checks_the_digest(tmp_path, serve):
	path = updater.download_setup(updater.release_from_api(api()), tmp_path)
	assert path.read_bytes() == PAYLOAD


def test_download_rejects_a_tampered_file(tmp_path, serve):
	release = updater.release_from_api(api(digest="sha256:" + "0" * 64))
	with pytest.raises(updater.UpdateError) as e:
		updater.download_setup(release, tmp_path)
	assert e.value.reason == "checksum"
	assert not list(tmp_path.iterdir())


def test_download_only_from_this_repository(tmp_path, serve):
	data = api()
	data["assets"][1]["browser_download_url"] = "https://example.com/ZK-Pull-Setup-0.2.0.exe"
	with pytest.raises(updater.UpdateError) as e:
		updater.download_setup(updater.release_from_api(data), tmp_path)
	assert e.value.reason == "bad_address"


def test_download_requires_a_published_checksum(tmp_path, serve):
	with pytest.raises(updater.UpdateError) as e:
		updater.download_setup(updater.release_from_api(api(digest=None)), tmp_path)
	assert e.value.reason == "no_checksum"


def test_download_stops_when_larger_than_published(tmp_path, monkeypatch):
	monkeypatch.setattr(updater, "_get", lambda url, timeout: io.BytesIO(PAYLOAD * 10_000))
	with pytest.raises(updater.UpdateError, match="too_large"):
		updater.download_setup(updater.release_from_api(api()), tmp_path)
	assert not list(tmp_path.iterdir())  # nothing half-downloaded is left behind


def test_download_refuses_a_redirect_elsewhere(tmp_path, monkeypatch):
	class Redirected(io.BytesIO):
		url = "http://evil.example/ZK-Pull-Setup-0.2.0.exe"

	monkeypatch.setattr(updater, "_get", lambda url, timeout: Redirected(PAYLOAD))
	with pytest.raises(updater.UpdateError, match="redirect"):
		updater.download_setup(updater.release_from_api(api()), tmp_path)


def test_errors_are_translated(monkeypatch):
	from zk_pull_desktop import i18n
	from zk_pull_desktop.worker import error_message

	monkeypatch.setattr(i18n, "_current", "ar")
	assert error_message(updater.UpdateError("http", code=503)) == "أجاب GitHub بالخطأ \u2068503\u2069"
	monkeypatch.setattr(i18n, "_current", "en")
	assert (
		error_message(updater.UpdateError("offline", "Name or service not known"))
		== "no connection to GitHub"
	)


def test_installer_runs_per_user_and_relaunches(monkeypatch):
	calls = []
	monkeypatch.setattr(updater.subprocess, "Popen", lambda args, **kwargs: calls.append(args))
	updater.run_installer(updater.Path("setup.exe"))
	assert "/CURRENTUSER" in calls[0] and "/ZKUPDATE=1" in calls[0]


def test_download_errors_name_their_cause(tmp_path, monkeypatch):
	import urllib.error

	def missing(url, timeout):
		raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

	monkeypatch.setattr(updater, "_get", missing)
	with pytest.raises(updater.UpdateError) as e:
		updater.download_setup(updater.release_from_api(api()), tmp_path)
	assert (e.value.reason, e.value.values) == ("http", {"code": 404})

	monkeypatch.setattr(updater, "_get", lambda url, timeout: io.BytesIO(PAYLOAD))
	with pytest.raises(updater.UpdateError) as e:
		updater.download_setup(updater.release_from_api(api()), tmp_path / "no such folder")
	assert e.value.reason == "disk"


def test_installer_writes_a_log_when_asked(monkeypatch):
	calls = []
	monkeypatch.setattr(updater.subprocess, "Popen", lambda args, **kwargs: calls.append(args))
	updater.run_installer(updater.Path("setup.exe"), updater.Path("C:/data/update.log"))
	assert calls[0][-1] == f"/LOG={updater.Path('C:/data/update.log')}"
