"""harness/report.py: self-contained HTML episode report."""
import json

from kaggle_environments import make

from harness.report import build_report_data, load_receipts, load_replay, render_html, write_report

PASS = {"farmer": ["PASS"], "hands": [], "market": []}


def _finish(env, first_action=PASS):
    actions = [first_action, PASS]
    while not env.done:
        env.step(actions)
        actions = [PASS, PASS]
    return env.toJSON()


def _replay():
    env = make("kaggriculture", configuration={"seed": 0, "episodeSteps": 6, "turnsPerDay": 3})
    return _finish(env)


def test_build_report_data_has_all_required_sections():
    replay = _replay()
    data = build_report_data(replay, seat=0)
    assert data["seat"] == 0
    assert "bank_curve" in data["metrics"]
    assert "opponent_bank_curve" in data["metrics"]
    assert data["timeline"]["units"] >= 1
    assert len(data["timeline"]["grid"][0]) == len(replay["steps"])
    assert len(data["heatmaps"]) >= 1
    assert isinstance(data["sell_prices"], list)


def test_build_report_data_unexplained_noops_not_measured_without_diagnostics():
    data = build_report_data(_replay(), seat=0)
    assert data["metrics"]["unexplained_noops"] is None


def test_build_report_data_unexplained_noops_measured_with_diagnostics():
    data = build_report_data(_replay(), seat=0, diagnostics=[
        {"seat": 0, "kind": "reconciliation", "ok": False},
    ])
    assert data["metrics"]["unexplained_noops"] == 1


def test_render_html_is_self_contained_and_embeds_data():
    """No external CDN/script references — the whole point is an offline-openable file."""
    data = build_report_data(_replay(), seat=0)
    html = render_html(data)
    assert "<html" in html.lower()
    assert "http://" not in html and "https://" not in html
    assert "const DATA = " in html


def test_write_report_produces_readable_file(tmp_path):
    replay = _replay()
    out_path = write_report(replay, tmp_path / "report.html", seat=0)
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "kaggriculture episode report" in content


def test_load_replay_roundtrips_gzip_and_plain(tmp_path):
    replay = _replay()

    gz_path = tmp_path / "replay.json.gz"
    import gzip
    with gzip.open(gz_path, "wt", encoding="utf-8") as f:
        json.dump(replay, f)
    assert load_replay(gz_path)["rewards"] == replay["rewards"]

    json_path = tmp_path / "replay.json"
    json_path.write_text(json.dumps(replay), encoding="utf-8")
    assert load_replay(json_path)["rewards"] == replay["rewards"]


def test_load_receipts_none_when_missing_file_present_when_written(tmp_path):
    missing = tmp_path / "receipts_missing.jsonl"
    assert load_receipts(missing) is None

    present = tmp_path / "receipts_present.jsonl"
    present.write_text(
        json.dumps({"seat": 0, "kind": "reconciliation", "ok": True}) + "\n",
        encoding="utf-8",
    )
    rows = load_receipts(present)
    assert rows == [{"seat": 0, "kind": "reconciliation", "ok": True}]
