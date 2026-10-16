"""Synthetic inventory limits; numbers are invented test coordinates."""

from pathlib import Path

import pytest

from flowpilot_translate.engine.design_space import DesignSpaceSearch
from flowpilot_translate.inventory_constraints import enforce_reactor_inventory, inventory_prompt_block
from flowpilot_translate.residence_time_basis import gas_equiv_from_stp_flow
from flowpilot_translate.schemas import BatchRecord, ChemistryPlan, FlowProposal, LabInventory, StreamAssignment


TEST_INVENTORY = Path(__file__).parent / "fixtures/synthetic_inventory_limits.json"


class _StubCalc:
    is_gas_liquid = True
    residence_time_min = 45.0
    tau_analogy_min = None
    tau_class_min = None
    tau_kinetics_min = 45.0
    rate_constant = None
    intensification_factor = 2.0
    concentration_M = 0.2
    bpr_pressure_bar = 5.0
    extinction_coefficient_M_cm = None


def _proposal(**overrides) -> FlowProposal:
    values = dict(
        residence_time_min=50,
        residence_time_inlet_min=50,
        residence_time_in_channel_min=100,
        residence_time_basis="inlet/STP apparent residence time",
        flow_rate_mL_min=0.01,
        reactor_volume_mL=6,
        temperature_C=30,
        concentration_M=0.2,
        BPR_bar=5,
        tubing_ID_mm=0.8,
        tubing_material="FEP",
        wavelength_nm=460,
        streams=[
            StreamAssignment(stream_label="A", contents=["test solute"], solvent="water",
                             concentration_M=0.2, flow_rate_mL_min=0.01),
            StreamAssignment(stream_label="G", contents=["O2"], phase="gas",
                             gas_flow_sccm=0.09, gas_flow_actual_mL_min=0.02),
        ],
    )
    values.update(overrides)
    return FlowProposal(**values)


def test_design_space_uses_only_declared_synthetic_reactor_volumes():
    inventory = LabInventory.from_json(str(TEST_INVENTORY))
    batch = BatchRecord(reaction_description="Synthetic photochemical oxygen test.",
                        solvent="water", temperature_C=30, reaction_time_h=2,
                        concentration_M=0.2, scale_mmol=0.1, atmosphere="O2", wavelength_nm=460)
    plan = ChemistryPlan(reaction_class="photochemical", o2_is_reagent=True,
                         recommended_wavelength_nm=460)
    candidates = DesignSpaceSearch().run(batch_record=batch, chemistry_plan=plan,
        calculations=_StubCalc(), inventory=inventory, reaction_class="photochemical")

    assert candidates
    assert {round(c.V_R_mL) for c in candidates} <= {6, 12, 18}
    assert {round(c.d_mm, 3) for c in candidates} == {0.8}
    assert all(c.inventory_reactor_name for c in candidates)


def test_inventory_enforcement_snaps_off_inventory_geometry():
    inventory = LabInventory.from_json(str(TEST_INVENTORY))
    proposal = _proposal(reactor_volume_mL=6.7, tubing_ID_mm=0.6,
                         residence_time_min=55, residence_time_in_channel_min=55,
                         residence_time_inlet_min=20,
                         residence_time_basis="in-channel total actual flow",
                         flow_rate_mL_min=0.03)
    proposal.streams[0].flow_rate_mL_min = 0.03
    proposal.streams[1].gas_flow_sccm = 0.3
    proposal.streams[1].gas_flow_actual_mL_min = 0.08

    revised, report = enforce_reactor_inventory(proposal, inventory)

    assert report["applied"]
    assert revised.reactor_volume_mL == 6
    assert revised.tubing_ID_mm == 0.8
    assert revised.inventory_selection["system"] == "System A"
    assert revised.residence_time_basis == "inlet/STP apparent residence time"
    assert revised.residence_time_min == revised.residence_time_inlet_min == 20
    assert revised.residence_time_in_channel_min > revised.residence_time_inlet_min
    assert revised.flow_rate_mL_min < proposal.flow_rate_mL_min
    assert revised.streams[1].gas_flow_sccm > 0


def test_inventory_enforcement_preserves_inlet_stp_residence_basis():
    inventory = LabInventory.from_json(str(TEST_INVENTORY))
    revised, report = enforce_reactor_inventory(_proposal(), inventory)

    assert report["applied"]
    assert revised.reactor_volume_mL == 6
    assert revised.residence_time_basis == "inlet/STP apparent residence time"
    assert revised.residence_time_min == revised.residence_time_inlet_min == 50
    assert revised.residence_time_in_channel_min > 50
    assert revised.streams[1].gas_flow_sccm > revised.streams[1].gas_flow_actual_mL_min


def test_inventory_enforcement_recomputes_o2_from_target_equiv():
    inventory = LabInventory.from_json(str(TEST_INVENTORY))
    proposal = _proposal(residence_time_min=48, residence_time_inlet_min=48,
        evidence_calibration={"recommended_conditions": {
            "residence_time_inlet_min": 48, "gas_equiv_inlet": 2}})
    # Deliberately inconsistent input delivery must be replaced by the target ratio.
    proposal.streams[1].gas_flow_sccm = 0.02

    revised, report = enforce_reactor_inventory(proposal, inventory)
    gas = revised.streams[1]
    supplied = gas_equiv_from_stp_flow(gas.gas_flow_sccm, revised.flow_rate_mL_min,
                                     revised.concentration_M, 1.0)

    assert report["applied"]
    assert revised.residence_time_inlet_min == 48
    assert supplied == pytest.approx(2, abs=0.02)
    assert gas.gas_flow_sccm > gas.gas_flow_actual_mL_min
    assert gas.molar_equiv == 2


def test_small_reactor_clamps_to_pump_minimum_and_preserves_pressure():
    inventory = LabInventory.from_json(str(TEST_INVENTORY))
    inventory.reactors = [r for r in inventory.reactors if r.system == "System B" and r.volume_mL == 12]
    proposal = _proposal(reactor_volume_mL=12, residence_time_min=75,
        residence_time_inlet_min=75, BPR_bar=3,
        evidence_calibration={"recommended_conditions": {
            "residence_time_inlet_min": 75, "gas_equiv_inlet": 2}})

    revised, report = enforce_reactor_inventory(proposal, inventory)
    flow_report = revised.inventory_constraints["flow_recalculation"]

    assert report["applied"]
    assert revised.inventory_selection["system"] == "System B"
    assert revised.flow_rate_mL_min == 0.02
    assert revised.BPR_bar == 3
    assert 50 < revised.residence_time_inlet_min < 75
    assert flow_report["pump_flow_clamped"] is True
    assert flow_report["pump_min_flow_rate_mL_min"] == 0.02
    assert flow_report["o2_equiv_supplied"] == 2


def test_declared_serial_reactor_makes_target_time_pump_feasible():
    inventory = LabInventory.from_json(str(TEST_INVENTORY))
    proposal = _proposal(reactor_volume_mL=12, residence_time_min=75,
        residence_time_inlet_min=75, BPR_bar=3,
        evidence_calibration={"anchor_conditions": {"reactor_volume_mL": 12},
            "recommended_conditions": {"residence_time_inlet_min": 75, "gas_equiv_inlet": 2}})

    revised, report = enforce_reactor_inventory(proposal, inventory)
    flow_report = revised.inventory_constraints["flow_recalculation"]

    assert report["applied"]
    assert revised.reactor_volume_mL == 18
    assert revised.inventory_selection["system"] == "System B"
    assert revised.inventory_selection["component_volumes_mL"] == [12, 6]
    assert revised.residence_time_inlet_min == 75
    assert revised.flow_rate_mL_min > 0.02
    assert revised.BPR_bar == 3
    assert flow_report["pump_flow_clamped"] is False
    assert flow_report["o2_equiv_supplied"] == 2


def test_inventory_prompt_exposes_pump_flow_limits():
    inventory = LabInventory.from_json(str(TEST_INVENTORY))
    prompt = inventory_prompt_block(inventory)

    assert "Synthetic coarse pump: 0.02-2 mL/min" in prompt
    assert "systems: System B" in prompt
