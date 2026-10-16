from pathlib import Path

import pytest

from flowpilot_translate.intake_agent import historical_text_from_package
from flowpilot_translate.main import _inventory_from_intake_or_path, translate
from flowpilot_translate.schemas import DesignInputPackage


def test_translate_rejects_non_ready_intake_package_before_model_calls():
    package = DesignInputPackage(
        raw_protocol="A to B.",
        missing_question_ids=["Q-OBJ-001"],
        ready_for_design=False,
    )

    with pytest.raises(ValueError, match="Q-OBJ-001"):
        translate("A to B.", intake_package=package)


def test_intake_inventory_payload_converts_to_lab_inventory():
    package = DesignInputPackage(
        raw_protocol="A to B.",
        objective="screen",
        inventory_constraints={
            "pumps": [],
            "tubing": [],
            "BPR_available": [0, 6],
            "light_sources": [
                {
                    "name": "450 nm LED",
                    "wavelength_nm": 450,
                    "power_W": 10,
                    "compatible_reactor": "coil",
                }
            ],
            "reactors": [
                {
                    "type": "coil",
                    "material": "FEP",
                    "volume_mL": 10,
                    "ID_mm": 1.0,
                    "name": "10 mL coil",
                    "system": "test",
                }
            ],
        },
        ready_for_design=True,
    )

    inventory = _inventory_from_intake_or_path(package, str(Path(__file__).parent / "fixtures/synthetic_inventory_limits.json"))

    assert inventory.reactors[0].volume_mL == 10
    assert inventory.reactors[0].ID_mm == 1.0
    assert inventory.BPR_available == [0, 6]


def test_free_text_intake_inventory_converts_to_lab_inventory():
    package = DesignInputPackage(
        raw_protocol="A to B.",
        objective="maximize conversion",
        inventory_constraints="""## Lab Inventory - hard constraints
Available reactors. Final reactor design must use one of these exactly:
- System A Synthetic coil: 6 mL, 0.8 mm ID, FEP (T 20.0-60.0 deg C; C 0.1-0.3 M; P 0.0-9.0 bar; lambda 460 nm; 20 mW/cm2)
- System B Synthetic coil: 12 mL, 0.8 mm ID, FEP (T in [30.0, 45.0] deg C; C 0.1-0.3 M; P 0.0-9.0 bar; lambda 460 nm; 20 mW/cm2)
Available BPR/pressure settings: [0.0, 3.0, 5.0] bar
Available light sources:
- Synthetic blue lamp: 460 nm, 20 mW/cm2""",
        ready_for_design=True,
    )

    inventory = _inventory_from_intake_or_path(package, "flowpilot_translate/data/lab_inventory.json")
    volumes = {reactor.volume_mL for reactor in inventory.reactors}

    assert volumes == {6.0, 12.0}
    assert {reactor.ID_mm for reactor in inventory.reactors} == {0.8}
    assert inventory.BPR_available == [0.0, 3.0, 5.0]
    assert any(source.wavelength_nm == 460.0 for source in inventory.light_sources)


def test_historical_text_from_package_preserves_measured_feedback_only():
    package = DesignInputPackage(
        raw_protocol="A to B.",
        objective="screen",
        historical_data=(
            "Synthetic run A: t in-channel = 10 min, product = 20%. "
            "Synthetic run B: t in-channel = 15 min, product = 30%."
        ),
        hypotheses=["reaction may need longer residence time"],
        ready_for_design=True,
    )

    text = historical_text_from_package(package)

    assert "Synthetic run A" in text
    assert "product = 20%" in text
    assert "longer residence" not in text
