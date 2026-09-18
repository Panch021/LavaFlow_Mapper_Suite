import os

from lavaflow_suite import __version__
from lavaflow_suite import common as lfc
from lavaflow_suite import mapper, report, speed


def test_generate_report(project):
    cfg = lfc.load_global_config()
    mapper.run_filter(cfg, project)
    speed.process_speed_data(project)
    out = report.report_path(project, cfg)
    ok, msg = report.generate_report(out, ["anomalies", "mapper", "speed"], embed_video=False)
    assert ok, msg
    html = open(out, encoding="utf-8").read()
    assert "LavaFlow Mapper Suite — Testvolcano" in html
    assert "01/03/2024 — 20/03/2024" in html
    assert "https://doi.org/10.3390/rs14143483" in html
    assert "https://github.com/Panch021/LavaFlow_Mapper_Suite" in html
    assert "could not be generated" not in html
    assert "opentopomap" in html.lower()


def test_report_without_project(workdir):
    ok, msg = report.generate_report(str(workdir / "r.html"))
    assert not ok and "No active project" in msg


def test_app_builds(project):
    from lavaflow_suite import app
    assert app.app.title == "LavaFlow Suite"
    assert len(app.gvp_options) > 1000
    assert len(app.app.callback_map) > 10
    assert "Testvolcano" in app.header_display


def test_cli_version(capsys, workdir):
    from lavaflow_suite import cli
    import pytest
    with pytest.raises(SystemExit):
        cli.main(["--version"])
    assert __version__ in capsys.readouterr().out


def test_cli_workdir(tmp_path, monkeypatch):
    from lavaflow_suite import cli, app
    called = {}
    monkeypatch.setattr(app, "main", lambda argv: called.setdefault("argv", argv))
    target = tmp_path / "ws"
    cli.main(["--workdir", str(target), "--no-browser"])
    assert os.path.samefile(os.getcwd(), target)
    assert called["argv"] == ["--workdir", str(target), "--no-browser"]
