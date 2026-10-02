"""The `st-vtt` command: validate, schema and serve, without starting a real server."""

import json

import pytest
import uvicorn

from conftest import ROOT
from st_vtt.cli import main
from st_vtt.main import create_app

PACK = ROOT / "content" / "example"


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    """A good config in an empty working directory, as config.json."""
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "users": [{"name": "Gm", "role": "gm"}],
                "content_pack": str(PACK),
                "host": "127.0.0.1",
                "port": 8123,
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def served(monkeypatch):
    """What `serve` handed to uvicorn, instead of running it."""
    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: calls.append((app, kwargs)))
    yield calls
    for app, _ in calls:
        if not isinstance(app, str):
            app.state.db.close()


def test_validate_a_pack(capsys):
    assert main(["validate", str(PACK)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("OK: Example Pack (example)\n")
    assert "  playbooks: wanderer\n" in out


def test_validate_the_configs_pack(config_file, capsys):
    assert main(["validate"]) == 0
    assert capsys.readouterr().out.startswith("OK: Example Pack (example)")


@pytest.mark.parametrize(
    "argv, error",
    [
        (["validate", "/no/such/pack"], "error: content pack not found: /no/such/pack"),
        (["validate", "-c", "/no/config.json"], "error: config file not found: /no/config.json"),
    ],
)
def test_validate_reports_what_is_wrong(capsys, argv, error):
    assert main(argv) == 1
    captured = capsys.readouterr()
    assert captured.err.startswith(error) and captured.out == ""


def test_schema_to_stdout_and_to_a_file(tmp_path, capsys):
    assert main(["schema"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert "pack" in printed["properties"]
    out = tmp_path / "schema.json"
    assert main(["schema", "-o", str(out)]) == 0
    assert capsys.readouterr().out == f"wrote {out}\n"
    assert json.loads(out.read_text(encoding="utf-8")) == printed


@pytest.mark.parametrize("argv", [[], ["serve"]])
def test_serve_is_the_default(config_file, served, argv):
    assert main(argv) == 0
    [(app, kwargs)] = served
    assert app.state.config.port == 8123
    assert kwargs == {"host": "127.0.0.1", "port": 8123}


def test_serve_with_reload_hands_uvicorn_a_factory_that_finds_the_config(config_file, served, monkeypatch, tmp_path):
    monkeypatch.delenv("ST_VTT_CONFIG", raising=False)
    (tmp_path / "elsewhere").mkdir()
    monkeypatch.chdir(tmp_path / "elsewhere")
    assert main(["serve", "--reload", "-c", "../config.json"]) == 0
    [(target, kwargs)] = served
    assert target == "st_vtt.main:create_app"
    assert kwargs == {"factory": True, "host": "127.0.0.1", "port": 8123, "reload": True}
    # The factory, called in uvicorn's worker, loads the same config, not ./config.json.
    app = create_app()
    try:
        assert app.state.config.port == 8123
    finally:
        app.state.db.close()


def test_serve_refuses_a_bad_config_before_starting(tmp_path, served, capsys):
    (tmp_path / "config.json").write_text('{"users": []}', encoding="utf-8")
    assert main(["serve", "-c", str(tmp_path / "config.json")]) == 1
    assert "users: List should have at least 1 item" in capsys.readouterr().err
    assert served == []


@pytest.mark.parametrize("argv", [["serve"], ["serve", "--reload"]])
def test_serve_refuses_a_bad_pack_before_starting(config_file, served, capsys, monkeypatch, argv):
    # With --reload, uvicorn gets only a factory's name, so without this check the error
    # would turn up later, in the worker.
    monkeypatch.delenv("ST_VTT_CONFIG", raising=False)
    config_file.write_text(json.dumps({"users": [{"name": "Gm"}], "content_pack": "nowhere"}), encoding="utf-8")
    assert main(argv) == 1
    assert capsys.readouterr().err.startswith("error: content pack not found:")
    assert served == []


def test_an_unknown_command_is_an_argparse_error(capsys):
    with pytest.raises(SystemExit) as e:
        main(["frobnicate"])
    assert e.value.code == 2
    assert "invalid choice: 'frobnicate'" in capsys.readouterr().err
