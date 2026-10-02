"""Loading the config file. A bad one stops the server from starting, so its errors must
say what to fix."""

import json

import pytest

from conftest import ROOT
from st_vtt.config import ConfigError, load_config
from st_vtt.content import load_content


def write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw if isinstance(raw, str) else json.dumps(raw), encoding="utf-8")
    return path


def error_of(path):
    with pytest.raises(ConfigError) as e:
        load_config(path)
    return str(e.value)


def test_the_example_config_loads_and_points_at_a_real_pack():
    cfg = load_config(ROOT / "config.example.json")
    assert cfg.content_path == ROOT / "content" / "example"
    load_content(cfg.content_path)


def test_a_missing_file_says_how_to_make_one(tmp_path):
    msg = error_of(tmp_path / "config.json")
    assert msg.startswith(f"config file not found: {tmp_path / 'config.json'}")
    assert "Copy config.example.json to config.json" in msg


def test_invalid_json_names_the_line(tmp_path):
    path = write(tmp_path / "config.json", '{\n  "users": [\n    {"name": "Gm",}\n  ]\n}\n')
    assert error_of(path).startswith(f"{path}: invalid JSON at line 3:")


@pytest.mark.parametrize("raw, where, what", [
    ({}, "users", "Field required"),
    ({"users": []}, "users", "at least 1 item"),
    ({"users": [{"name": "Gm"}, {"name": "gm "}]}, "users", "duplicate user name: 'gm '"),
    ({"users": [{"name": "  "}]}, "users", "user name must not be empty"),
    ({"users": [{"name": "Gm", "role": "admin"}]}, "users.0.role", "'gm' or 'player'"),
    ({"users": [{"name": "Gm"}], "port": "eighty"}, "port", "valid integer"),
])
def test_each_problem_is_reported_where_it_is(tmp_path, raw, where, what):
    path = write(tmp_path / "config.json", raw)
    first, *problems = error_of(path).split("\n")
    assert first == f"{path}: invalid config"
    assert any(p.startswith(f"  {where}: ") and what in p for p in problems), problems


def test_every_problem_is_reported_at_once(tmp_path):
    path = write(tmp_path / "config.json", {"users": [{"name": "Gm", "role": "admin"}], "port": "eighty"})
    problems = error_of(path).split("\n")[1:]
    assert [p.split(":")[0].strip() for p in problems] == ["port", "users.0.role"]


def test_relative_paths_are_relative_to_the_config_file(tmp_path, monkeypatch):
    path = write(tmp_path / "table" / "config.json", {
        "users": [{"name": "Gm"}], "database": "data/campaign.db", "content_pack": str(ROOT / "content" / "example"),
    })
    monkeypatch.chdir(tmp_path)
    cfg = load_config("table/config.json")
    assert cfg.database_path == tmp_path / "table" / "data" / "campaign.db"
    assert cfg.static_path == tmp_path / "table" / "frontend" / "dist"
    assert cfg.content_path == ROOT / "content" / "example"  # absolute stays as written
