"""Versioned icon diagrams shared by both GUIs, without changing archives."""

from flowpilot.paths import OUTPUTS_DIR

from copy import deepcopy
import hashlib
import json
import marshal
from pathlib import Path
import sys

from filelock import FileLock

from flowpilot_translate.diagram_artifacts import render_topology_artifacts, topology_sha256
from flowpilot_translate.schemas import ProcessTopology


CACHE = OUTPUTS_DIR / "diagram_views"


def _module_content(module) -> bytes:
    """Fingerprint source installs and frozen applications without assuming .py files."""
    try:
        return Path(module.__file__).read_bytes()
    except (AttributeError, OSError, TypeError):
        loader = getattr(module, "__loader__", None)
        get_code = getattr(loader, "get_code", None)
        if get_code is not None:
            code = get_code(module.__name__)
            if code is not None:
                return marshal.dumps(code)
        from flowpilot import __version__
        return f"{module.__name__}:{__version__}".encode()


def current_diagram(result: dict, kind: str) -> Path | None:
    if kind not in {"process-svg", "process-png"} or (result.get("final_design") or {}).get("status") != "executable":
        return None
    topology = ((result["final_design"].get("process_graph") or {}).get("topology") or result.get("process_topology"))
    if not topology:
        return None
    from flowpilot_design.visualizer import flowsheet_builder

    source_hash = topology_sha256(topology)
    display = deepcopy(topology)
    streams = {str(s.get("stream_label", "")).casefold(): s for s in result["final_design"].get("streams", [])}
    for operation in display.get("unit_operations", []):
        params = operation.get("parameters") or {}
        stream = streams.get(str(params.get("stream", "")).casefold())
        if stream and stream.get("phase") == "gas":
            params["molar_equiv"] = stream.get("molar_equiv")
    fingerprint = hashlib.sha256(_module_content(flowsheet_builder) + _module_content(sys.modules[__name__])
                                 + json.dumps(display, sort_keys=True).encode()).hexdigest()
    folder = CACHE / fingerprint
    folder.mkdir(parents=True, exist_ok=True)
    index = folder / "view.json"
    with FileLock(str(folder / "render.lock"), timeout=90):
        artifacts = None
        if index.is_file():
            try:
                cached = json.loads(index.read_text())
                if isinstance(cached, dict) and all(
                    isinstance(cached.get(key), str) and Path(cached[key]).is_file()
                    for key in ("svg_path", "png_path")
                ):
                    artifacts = cached
            except (OSError, ValueError):
                pass
        if artifacts is None:
            artifacts = render_topology_artifacts(ProcessTopology.model_validate(display), base_dir=folder)
            artifacts["source_topology_sha256"] = source_hash
            artifacts["caption_source"] = "final_design.streams for gas equivalents; original topology for setpoints"
            temporary = index.with_suffix(".tmp")
            temporary.write_text(json.dumps(artifacts, indent=2))
            temporary.replace(index)
    path = Path(artifacts["svg_path" if kind.endswith("svg") else "png_path"])
    return path if path.is_file() else None
