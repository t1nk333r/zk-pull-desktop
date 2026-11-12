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
	with pytest.raises(updater.UpdateError, match="checksum"):
		updater.download_setup(release, tmp_path)
	assert not list(tmp_path.iterdir())


def test_download_only_from_this_repository(tmp_path, serve):
	data = api()
	data["assets"][1]["browser_download_url"] = "https://example.com/ZK-Pull-Setup-0.2.0.exe"
	with pytest.raises(updater.UpdateError, match="unexpected"):
		updater.download_setup(updater.release_from_api(data), tmp_path)
