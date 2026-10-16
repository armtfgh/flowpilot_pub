import json
from pathlib import Path

import pytest

from flowpilot_translate.diagram_views import current_diagram
from flowpilot_translate.diagram_artifacts import topology_sha256


@pytest.fixture
def result():
    """Small, synthetic result; no local experiment archives are required."""
    from flowpilot_translate.tests.test_result_reporting import result_fixture
    source = Path(__file__).resolve().parents[2] / "flowpilot_translate/tests/fixtures/diagram_stage0_topologies.json"
    topology = json.loads(source.read_text())[1]["topology"]
    topology["unit_operations"][1]["parameters"]["stream"] = "G"
    value = result_fixture()
    value["final_design"]["schema_version"] = "flowpilot_final_design_v2.0"
    value["final_design"]["streams"][1]["molar_equiv"] = 2
    value["final_design"]["process_graph"] = {"topology": topology}
    return value


def test_diagram_cache_preserves_original_source_and_embeds_icons(result, tmp_path, monkeypatch):
    import flowpilot_translate.diagram_views as view
    monkeypatch.setattr(view, "CACHE", tmp_path)
    before = json.dumps(result, sort_keys=True)
    path = current_diagram(result, "process-svg")
    assert path and path.is_file()
    assert path == current_diagram(result, "process-svg")
    text = path.read_text()
    assert "mL/min at STP" in text and "2 equiv" in text
    assert "data:image/png;base64," in text
    assert "sccm" not in text and "\u2026" not in text
    assert json.dumps(result, sort_keys=True) == before
    stored = json.loads(next(tmp_path.glob("*/view.json")).read_text())
    source = result["final_design"]["process_graph"]["topology"]
    assert stored["source_topology_sha256"] == topology_sha256(source)


def test_no_executable_view_for_blocked_result(result):
    result["final_design"]["status"] = "blocked"
    assert current_diagram(result, "process-svg") is None


@pytest.mark.parametrize("damage", ["corrupt_index", "missing_svg", "missing_png", "invalid_index"])
def test_diagram_cache_self_repairs_from_unchanged_canonical_source(result, tmp_path, monkeypatch, damage):
    import flowpilot_translate.diagram_views as view
    monkeypatch.setattr(view, "CACHE", tmp_path)
    path = current_diagram(result, "process-svg")
    index = next(tmp_path.glob("*/view.json"))
    saved = json.loads(index.read_text())
    if damage == "corrupt_index":
        index.write_text('{"svg_path":')
    elif damage == "invalid_index":
        index.write_text("[]")
    else:
        Path(saved["svg_path" if damage == "missing_svg" else "png_path"]).unlink()
    repaired = current_diagram(result, "process-svg")
    assert repaired.is_file()
    assert repaired.parent.parent == path.parent.parent
    assert repaired == current_diagram(result, "process-svg")
    assert current_diagram(result, "process-png").is_file()
    assert json.loads(index.read_text())["source_topology_sha256"] == saved["source_topology_sha256"]


def test_streamlit_result_page_renders_shared_stage_summary_and_responses(result):
    from streamlit.testing.v1 import AppTest
    code = (
        "import json\nfrom pages.flowpilot_design_unified import _render_result\n"
        f"result=json.loads({json.dumps(result)!r})\n_render_result(result, key_prefix='stage_reporting_test')"
    )
    app = AppTest.from_string(code).run(timeout=90)
    assert not app.exception, [e.message for e in app.exception]
    assert {"Process summary", "Responses", "Engineering Design"} <= {t.label for t in app.tabs}
    assert not any(m.label == "Residence Time (in-channel)" for m in app.metric)
    assert not any("in-channel" in i.label or "sccm" in i.label.lower() for i in app.number_input)
    tables = [table.value for table in app.dataframe]
    stage_tables = [t for t in tables if "Gas flow at STP (mL/min)" in t.columns]
    assert stage_tables
    assert stage_tables[0]["Time (min)"].tolist() == [100.0, 40.0]
