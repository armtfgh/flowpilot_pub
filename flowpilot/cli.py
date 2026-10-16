"""Small command-line interface; help and checks never invoke a model."""

from __future__ import annotations

import argparse
from importlib import util
import json
import os
from pathlib import Path
import shutil
import sys

from . import __version__


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="flowpilot", description="Inventory-constrained batch-to-flow design.")
    parser.add_argument("--version", action="version", version=f"FlowPilot {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check", help="Check local setup without network requests or data writes.")
    check.add_argument("--json", action="store_true", help="Print a JSON report.")

    serve = commands.add_parser("serve", help="Serve the browser workspace (requires the web extra).")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, help="Port (default: FLOWPILOT_PORT or 8510).")

    index = commands.add_parser("index", help="Import records into user state and index them; may call paid providers.")
    index.add_argument("records_dir", nargs="?", type=Path, help="Directory of process-record JSON files.")

    translate = commands.add_parser("translate", help="Translate a protocol using configured model providers.")
    translate.add_argument("protocol", nargs="?", help="Protocol text (use --file to read a file).")
    translate.add_argument("--file", type=Path, help="UTF-8 protocol text or JSON file.")
    translate.add_argument("--inventory", type=Path, required=True, help="Your confirmed laboratory inventory JSON.")
    translate.add_argument("--output", type=Path, help="Save the result JSON to this file instead of stdout.")
    return parser


def _import_records(source: Path, destination: Path) -> Path:
    """Copy corpus records after validating every filename conflict.

    The original files remain unchanged. Identical records already in user
    state are reused; different content with the same name is rejected before
    creating directories, copying files, or starting provider work.
    """
    source, destination = source.resolve(), destination.resolve()
    if not source.is_dir():
        raise ValueError("The records directory does not exist.")
    records = sorted(source.glob("*.json"))
    if not records:
        raise ValueError("The records directory must contain process-record JSON files.")
    for record in records:
        if not record.is_file():
            raise ValueError(f"Record is not a regular file: {record.name}")
        try:
            payload = json.loads(record.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"Invalid JSON record: {record.name}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"A process record must be a JSON object: {record.name}")
        target = destination / record.name
        if target.exists() and (not target.is_file() or record.read_bytes() != target.read_bytes()):
            raise ValueError(f"A different record named {record.name} already exists in user state; rename or reconcile it before indexing.")
    if source == destination:
        return destination
    destination.mkdir(parents=True, exist_ok=True)
    for record in records:
        target = destination / record.name
        if not target.exists():
            # Exclusive creation also prevents overwriting a concurrent import.
            with target.open("xb") as output:
                output.write(record.read_bytes())
    return destination


def _check() -> dict:
    from .paths import HOME, RECORDS_DIR, CHROMA_DIR, OUTPUTS_DIR, INVENTORY_PROFILE_DIR
    from flowpilot_translate.config import LAB_INVENTORY_PATH, PROMPTS_DIR

    package_root = Path(__file__).resolve().parent.parent
    icons = package_root / "flowpilot_design" / "visualizer" / "icons"
    frontend = package_root / "flowpilot_webapp" / "frontend" / "dist"
    modules = ("pydantic", "openai", "anthropic", "httpx", "chromadb", "numpy",
               "scipy", "filelock", "graphviz", "cairosvg", "PIL", "fitz", "openpyxl")
    dependencies = {module: util.find_spec(module) is not None for module in modules}
    assets = {
        "translation_prompts": all((PROMPTS_DIR / name).is_file() for name in (
            "translate_system.txt", "translate_user.txt", "intake_system.txt",
            "intake_user.txt", "inventory_extract_system.txt", "inventory_extract_user.txt")),
        "design_prompts": all((package_root / "flowpilot_design" / "prompts" / name).is_file()
                              for name in ("classify_system.txt", "classify_user.txt",
                                           "topology_system.txt", "topology_user.txt")),
        "equipment_icons": all((icons / name).is_file() for name in (
            "syringe_pump.png", "coil_reactor.png", "bpr.png", "vial.png")),
        "example_inventory": LAB_INVENTORY_PATH.is_file(),
    }
    cairo_error = None
    try:
        import cairosvg  # Validate the native Cairo dependency without rendering.
    except (ImportError, OSError) as exc:
        cairo_error = type(exc).__name__
    return {
        "version": __version__,
        "python": sys.version.split()[0],
        "core_ready": all(dependencies.values()) and all(assets.values()) and cairo_error is None,
        "dependencies": dependencies,
        "assets": assets,
        "rendering": {"graphviz_dot": shutil.which("dot") is not None, "cairo_available": cairo_error is None},
        "web": {"fastapi": util.find_spec("fastapi") is not None,
                "uvicorn": util.find_spec("uvicorn") is not None,
                "frontend_built": (frontend / "index.html").is_file()},
        "credentials": {name: bool(os.environ.get(name, "").strip())
                        for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")},
        "paths": {"home": str(HOME), "records": str(RECORDS_DIR), "chroma": str(CHROMA_DIR),
                  "outputs": str(OUTPUTS_DIR), "inventory_profiles": str(INVENTORY_PROFILE_DIR)},
        "note": "No network requests or data writes. Provider access is not validated.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    from .environment import load_environment

    try:
        load_environment()
        if args.command == "check":
            report = _check()
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                print(f"FlowPilot {__version__} · Python {report['python']}")
                print(f"User state: {report['paths']['home']}")
                for group in ("dependencies", "assets", "rendering", "web", "credentials"):
                    for name, present in report[group].items():
                        print(f"  {group}.{name}: {'available' if present else 'not available'}")
                print(report["note"])
            return 0 if report["core_ready"] else 1

        if args.command == "serve":
            if args.port is None:
                args.port = int(os.environ.get("FLOWPILOT_PORT", "8510"))
            if not 1 <= args.port <= 65535:
                parser.error("--port must be between 1 and 65535")
            try:
                import uvicorn
                import fastapi
            except ImportError:
                parser.error("The web extra is required; install '.[web]' from the source checkout.")
            frontend = Path(__file__).resolve().parent.parent / "flowpilot_webapp/frontend/dist/index.html"
            if not frontend.is_file():
                parser.error("The frontend is not built. Run npm ci and npm run build in flowpilot_webapp/frontend, then rebuild your wheel if installed from a wheel.")
            from .paths import ensure_runtime_dirs
            ensure_runtime_dirs()
            uvicorn.run("flowpilot_webapp.backend.app:app", host=args.host, port=args.port)
            return 0

        if args.command == "translate":
            if bool(args.protocol) == bool(args.file):
                parser.error("Provide protocol text or --file, but not both.")
            if not args.inventory.expanduser().is_file():
                parser.error("--inventory must point to an existing laboratory inventory JSON file.")
            protocol = args.file.expanduser().read_text(encoding="utf-8") if args.file else args.protocol
            from .paths import ensure_runtime_dirs
            from flowpilot_translate.main import translate
            ensure_runtime_dirs()
            result = translate(protocol, inventory_path=str(args.inventory.expanduser().resolve()))
            rendered = json.dumps(result, indent=2, ensure_ascii=False, default=str) + "\n"
            if args.output:
                output = args.output.expanduser()
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(rendered, encoding="utf-8")
                print(f"Saved result: {output.resolve()}")
            else:
                print(rendered, end="")
            return 0

        if args.command == "index":
            from .paths import RECORDS_DIR, ensure_runtime_dirs
            folder = (args.records_dir or RECORDS_DIR).expanduser().resolve()
            destination = _import_records(folder, RECORDS_DIR)
            from flowpilot_translate.main import index_records
            ensure_runtime_dirs()
            count = index_records(str(destination))
            print(f"Indexed {count} records.")
            return 0
    except (OSError, ValueError) as exc:
        parser.exit(1, f"flowpilot: {exc}\n")
    return 0
