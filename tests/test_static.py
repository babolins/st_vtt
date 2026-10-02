"""The built frontend is served, and nothing else on disk is."""

import pytest
from fastapi.testclient import TestClient

from st_vtt.main import create_app


@pytest.fixture
def client(config, tmp_path):
    dist = tmp_path / "site" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("INDEX")
    (dist / "favicon.svg").write_text("ICON")
    (tmp_path / "site" / "config.json").write_text("SECRET")
    config.static_dir = str(dist)
    with TestClient(create_app(config)) as c:
        yield c


def test_serves_files_in_the_build(client):
    r = client.get("/favicon.svg")
    assert r.text == "ICON"
    assert r.headers["cache-control"] == "no-cache"


def test_unknown_paths_get_the_app(client):
    assert client.get("/c/abc123").text == "INDEX"


@pytest.mark.parametrize(
    "path", ["/%2e%2e/config.json", "/..%2fconfig.json", "/assets%2f..%2f..%2fconfig.json", "/%2e%2e%2fconfig.json"]
)
def test_never_serves_files_outside_the_build(client, path):
    r = client.get(path)
    assert "SECRET" not in r.text
