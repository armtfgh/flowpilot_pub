# Contributing to FlowPilot

Changes should preserve the connection between chemistry, engineering calculations, inventory and the final process record. A clear issue report or focused pull request is useful even when it addresses only one part of that workflow.

The repository's license is still undecided. No contributor agreement or broader license grant is implied by this guide.

## Development setup

Use Python 3.11+ and Node.js 22.12+ for frontend development:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[web,dev]"
npm --prefix flowpilot_webapp/frontend ci
npm --prefix flowpilot_webapp/frontend run build
flowpilot check
```

Keep credentials in your environment or an ignored `.env`. Put local indices, generated outputs and private records in a separate runtime home. Do not add literature PDFs, extracted handbook prose, private laboratory records or model credentials to a contribution.

## Working on a change

Describe the concrete input or behavior being fixed and the expected result. For numerical changes, state units, reference conditions and assumptions. Add a focused regression test when it protects meaningful behavior; use synthetic data or a minimal fixture you are entitled to share.

Run tests relevant to the change. For example:

```bash
python -m pytest flowpilot_translate/tests/test_final_design_contract.py
python -m pytest flowpilot_webapp/tests
npm --prefix flowpilot_webapp/frontend run build
```

Some research-oriented or integration paths require additional data or configured services. Do not silently make provider calls during an offline test. When reporting a live-model test, identify the model, configuration and data used without including credentials or private source text.

## Before opening a pull request

- Explain the problem, the resulting behavior and the checks you ran.
- Keep protocol facts, user objectives and inferred chemistry distinct.
- Preserve the canonical final-design contract across outputs and views.
- Label measured results separately from computed estimates and model claims.
- Exclude generated build folders, local state and unrelated research artifacts.

For a bug report, include the source revision, platform, relevant package versions, a minimal shareable input and the error or discrepancy. Remove private content before posting logs.
