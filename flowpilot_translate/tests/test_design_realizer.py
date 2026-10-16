import json
from pathlib import Path

import pytest

from flowpilot_translate.design_realizer import realize_executable_design
from flowpilot_translate.main import _build_singlestep_topology
from flowpilot_translate.residence_time_basis import (
    actual_gas_flow_from_stp,
    stp_gas_flow_for_equiv,
)
from flowpilot_translate.inventory_profiles import inventory_profile_from_payload
from flowpilot_translate.topology_compiler import compile_inventory_topology
from flowpilot_translate.schemas import (
    BatchRecord,
    ChemistryPlan,
    FlowProposal,
    LabInventory,
    ProcessStage,
    ReagentRole,
    StreamAssignment,
    StreamLogic,
)


FIXTURES = Path(__file__).parent / "fixtures"


def _case(name: str) -> dict:
    return json.loads((FIXTURES / "synthetic_realizer_cases.json").read_text())[name]


def _realize(name: str, proposal: FlowProposal, plan: ChemistryPlan):
    case = _case(name)
    return realize_executable_design(
        proposal,
        batch_record=BatchRecord(
            raw_text=case["protocol"],
            reaction_description=case["protocol"],
        ),
        chemistry_plan=plan,
        inventory=LabInventory.model_validate(case["inventory"]),
        hard_constraints=case["hard_constraints"],
    )


def test_nitration_realization_solves_each_pump_and_removes_unavailable_bpr():
    proposal = FlowProposal(
        residence_time_min=24,
        flow_rate_mL_min=0.5,
        temperature_C=40,
        concentration_M=0.1,
        BPR_bar=3,
        reactor_volume_mL=12,
        streams=[
            StreamAssignment(
                stream_label="A",
                pump_role="organic substrate",
                contents=["anisole"],
                solvent="acetonitrile",
                concentration_M=0.1,
            ),
            StreamAssignment(
                stream_label="B",
                pump_role="nitric acid feed",
                contents=["Nitric acid", "Water"],
                solvent="Water",
                concentration_M=0.1,
            ),
        ],
    )
    plan = ChemistryPlan(
        reaction_name="Direct dinitration",
        reaction_class="dinitration",
        stream_logic=[
            StreamLogic(stream_label="A", reagents=["anisole"], concentration_M=0.1),
            StreamLogic(stream_label="B", reagents=["Nitric acid"], concentration_M=0.1, molar_equiv=2.0),
        ],
    )

    realized, report, validation = _realize("nitration", proposal, plan)

    assert report["status"] == "complete"
    assert validation["status"] == "ready"
    assert realized.BPR_bar == 0
    assert realized.reactor_volume_mL == 0.4
    assert realized.flow_rate_mL_min == 0.6
    assert realized.residence_time_min == pytest.approx(0.4 / 0.6, rel=1e-5)
    assert [(item.pump_equipment_id, item.flow_rate_mL_min) for item in realized.streams] == [
        ("test_acid_feed_a", 0.2),
        ("test_acid_feed_b", 0.4),
    ]
    assert realized.streams[1].molar_equiv == 2.0


def test_hydrogen_realization_reports_stp_actual_and_equivalents():
    proposal = FlowProposal(
        residence_time_min=6,
        flow_rate_mL_min=0.5,
        temperature_C=55,
        concentration_M=0.18,
        BPR_bar=5,
        reactor_type="packed-bed",
        reactor_volume_mL=3,
        streams=[
            StreamAssignment(
                stream_label="A",
                pump_role="substrate H feed",
                contents=["substrate H", "Methanol"],
                solvent="Methanol",
                concentration_M=0.18,
            ),
            StreamAssignment(
                stream_label="G",
                pump_role="Hydrogen reagent gas",
                contents=["H2"],
                phase="gas",
            ),
        ],
    )
    plan = ChemistryPlan(
        reaction_name="Hydrogenolysis",
        stream_logic=[
            StreamLogic(stream_label="A", reagents=["substrate H", "Methanol"], concentration_M=0.18),
            StreamLogic(stream_label="G", reagents=["H2"], phase="gas"),
        ],
    )

    realized, report, validation = _realize("hydrogenolysis", proposal, plan)

    gas = realized.streams[1]
    assert validation["status"] == "ready"
    assert realized.BPR_bar == 12
    assert gas.pump_equipment_id == "test_hydrogen_mfc"
    assert gas.gas_flow_sccm >= 0.2
    assert gas.gas_flow_actual_mL_min < gas.gas_flow_sccm
    assert gas.gas_flow_actual_mL_min == pytest.approx(
        actual_gas_flow_from_stp(gas.gas_flow_sccm, 55.0, 12.0), rel=1e-5
    )
    assert gas.molar_equiv == pytest.approx(1.0, rel=1e-3)
    gas_decision = next(
        item for item in report["decisions"] if item["decision"] == "gas_flow_solution"
    )
    assert gas_decision["target_equiv"] == 1.0
    assert gas_decision["supplied_equiv"] == pytest.approx(1.0, rel=1e-3)
    assert realized.residence_time_min == pytest.approx(
        realized.reactor_volume_mL
        / realized.flow_rate_mL_min,
        rel=1e-5,
    )
    assert realized.residence_time_inlet_min < realized.residence_time_min
    assert "liquid" in realized.residence_time_basis
    assert "273.15 K" in gas.reasoning
    assert report["safety_contract"]["hardware_checks"]["nitrogen_purge_declared"]


def test_multistage_realization_repairs_stage_map_and_closes_cumulative_flows():
    proposal = FlowProposal(
        residence_time_min=180,
        flow_rate_mL_min=0.07,
        temperature_C=74,
        concentration_M=0.3,
        BPR_bar=3,
        streams=[
            StreamAssignment(stream_label="A", contents=["alcohol A"], concentration_M=0.3),
            StreamAssignment(stream_label="B", contents=["H2O2", "NaBr", "H2SO4"], concentration_M=0.3),
            StreamAssignment(stream_label="C", contents=["amine B", "organic peroxide"], concentration_M=0.3),
        ],
    )
    global_streams = [
        StreamLogic(stream_label="A", reagents=["alcohol A"], reasoning="Stage 1 substrate", concentration_M=0.3),
        StreamLogic(stream_label="B", reagents=["H2O2"], reasoning="Stage 1 oxidant", molar_equiv=2, concentration_M=0.3),
        StreamLogic(stream_label="C", reagents=["amine B", "organic peroxide"], reasoning="Stage 2 feed", concentration_M=0.3),
    ]
    placeholder = StreamLogic(stream_label="A", reagents=["placeholder"])
    plan = ChemistryPlan(
        n_stages=2,
        stream_logic=global_streams,
        stages=[
            ProcessStage(stage_number=1, stage_name="Oxidation", temperature_C=62, feed_streams=[placeholder]),
            ProcessStage(stage_number=2, stage_name="Amidation", temperature_C=74, feed_streams=[placeholder]),
        ],
    )

    realized, report, validation = _realize("multistep", proposal, plan)

    stages = realized.stage_parameters
    assert validation["status"] == "ready"
    assert realized.BPR_bar == 0
    assert [item.introduction_stage for item in realized.streams] == [1, 1, 2]
    assert [item["reactor_equipment_id"] for item in stages] == [
        "test_stage_one",
        "test_stage_two",
    ]
    assert stages[0]["Q_liquid_mL_min"] == pytest.approx(0.12)
    assert stages[1]["Q_liquid_mL_min"] == pytest.approx(0.16)
    assert stages[0]["residence_time_min"] == pytest.approx(2.4 / 0.12, rel=1e-4)
    assert stages[1]["residence_time_min"] == pytest.approx(9.6 / 0.16, rel=1e-4)
    assert any(item["decision"] == "repair_stage_feed_map" for item in report["decisions"])


def test_hydrogen_peroxide_name_does_not_require_hydrogen_hardware():
    case = _case("multistep")
    proposal = FlowProposal(
        residence_time_min=180,
        flow_rate_mL_min=0.07,
        temperature_C=74,
        concentration_M=0.3,
        BPR_bar=0,
        streams=[
            StreamAssignment(stream_label="A", contents=["alcohol A"], concentration_M=0.3),
            StreamAssignment(stream_label="B", contents=["Hydrogen peroxide"], concentration_M=0.3),
            StreamAssignment(stream_label="C", contents=["amine B", "organic peroxide"], concentration_M=0.3),
        ],
    )
    plan = ChemistryPlan(
        n_stages=2,
        stream_logic=[
            StreamLogic(stream_label="A", reagents=["alcohol A"], concentration_M=0.3),
            StreamLogic(
                stream_label="B",
                reagents=["Hydrogen peroxide"],
                molar_equiv=2,
                concentration_M=0.3,
            ),
            StreamLogic(stream_label="C", reagents=["amine B", "organic peroxide"], concentration_M=0.3),
        ],
        stages=[
            ProcessStage(stage_number=1, stage_name="Oxidation", temperature_C=62),
            ProcessStage(stage_number=2, stage_name="Amidation", temperature_C=74),
        ],
    )

    _, report, validation = realize_executable_design(
        proposal,
        batch_record=BatchRecord(
            raw_text=case["protocol"],
            reaction_description="Oxidation with hydrogen peroxide followed by amidation",
        ),
        chemistry_plan=plan,
        inventory=LabInventory.model_validate(case["inventory"]),
        hard_constraints=case["hard_constraints"],
    )

    checks = report["safety_contract"]["hardware_checks"]
    assert "hydrogen_mfc_declared" not in checks
    assert "nitrogen_purge_declared" not in checks
    assert report["safety_contract"]["complete"]
    assert validation["checks"]["safety_contract_complete"]


def test_stage_summary_cannot_reclassify_global_peroxide_liquid_as_gas():
    plan = ChemistryPlan(
        stream_logic=[
            StreamLogic(
                stream_label="B",
                reagents=["aqueous hydrogen peroxide", "sodium bromide"],
                phase="liquid",
                molar_equiv=2.0,
            )
        ],
        stages=[
            ProcessStage(
                stage_number=1,
                feed_streams=[
                    StreamLogic(
                        stream_label="B",
                        reagents=["aqueous hydrogen peroxide", "sodium bromide"],
                        phase="gas",
                    )
                ],
            )
        ],
    )

    assert plan.stream_logic[0].phase == "liquid"
    assert plan.stages[0].feed_streams[0].phase == "liquid"
    assert plan.stages[0].feed_streams[0].molar_equiv == 2.0


def test_global_stream_logic_quantities_override_incomplete_stage_summaries():
    proposal = FlowProposal(
        flow_rate_mL_min=1.3,
        concentration_M=1.45,
        temperature_C=40,
        streams=[
            StreamAssignment(
                stream_label="A",
                contents=["anisole"],
                concentration_M=1.45,
            ),
            StreamAssignment(
                stream_label="B",
                contents=["aqueous nitric acid"],
                concentration_M=1.45,
                molar_equiv=1.0,
            ),
        ],
    )
    plan = ChemistryPlan(
        reaction_name="Dinitration",
        stream_logic=[
            StreamLogic(
                stream_label="A",
                reagents=["anisole"],
                concentration_M=1.45,
                molar_equiv=1.0,
            ),
            StreamLogic(
                stream_label="B",
                reagents=["aqueous nitric acid"],
                concentration_M=10.0,
                molar_equiv=2.2,
            ),
        ],
        stages=[
            ProcessStage(
                stage_number=1,
                feed_streams=[
                    StreamLogic(stream_label="A", reagents=["anisole"]),
                    StreamLogic(stream_label="B", reagents=["aqueous nitric acid"]),
                ],
            )
        ],
    )

    realized, report, _ = _realize("nitration", proposal, plan)

    acid = next(item for item in realized.streams if item.stream_label == "B")
    assert acid.concentration_M == 10.0
    assert acid.concentration_basis == "chemistry_plan"
    assert acid.molar_equiv == 2.2
    assert acid.molar_equiv_basis == "chemistry_plan"
    assert acid.flow_rate_mL_min >= 0.2
    assert report["status"] == "complete"


def test_air_identity_binds_air_mfc_and_uses_liquid_contact_time():
    case = _case("photochemical_oxidation")
    inventory = LabInventory.model_validate(case["inventory"])
    proposal = FlowProposal(
        flow_rate_mL_min=0.2,
        concentration_M=0.1,
        temperature_C=29,
        BPR_bar=3,
        reactor_type="photochemical coil",
        reactor_volume_mL=1,
        streams=[
            StreamAssignment(
                stream_label="A",
                contents=["thioanisole", "photocatalyst"],
                solvent="acetonitrile",
                concentration_M=0.1,
            ),
            StreamAssignment(
                stream_label="B",
                contents=["air (21 mol% oxygen, stale 0.60 sccm)"],
                pump_role="oxidant gas",
                phase="gas",
                molar_equiv=2.0,
            ),
        ],
    )
    plan = ChemistryPlan(
        reaction_name="Aerobic photooxidation",
        stream_logic=[
            StreamLogic(stream_label="A", reagents=["thioanisole"], concentration_M=0.1),
            StreamLogic(stream_label="B", reagents=["air"], phase="gas", molar_equiv=2.0),
        ],
    )

    realized, report, validation = realize_executable_design(
        proposal,
        batch_record=BatchRecord(raw_text=case["protocol"], reaction_description=case["protocol"]),
        chemistry_plan=plan,
        inventory=inventory,
        hard_constraints=case["hard_constraints"],
    )

    gas = next(item for item in realized.streams if item.phase == "gas")
    assert gas.pump_equipment_id == "test_air_mfc"
    assert gas.contents == ["air"]
    assert validation["checks"]["pump_flow_feasible"]
    assert report["status"] == "complete"
    assert realized.pressure_absolute_bar == pytest.approx(5.01325)
    assert realized.residence_time_min == pytest.approx(
        realized.reactor_volume_mL
        / realized.flow_rate_mL_min
    )
    assert realized.residence_time_inlet_min < realized.residence_time_min
    assert realized.residence_time_basis == "liquid-only reactor volume / liquid flow"
    assert "sccm" not in " ".join(gas.contents).lower()


def test_air_to_inventory_o2_substitution_recomputes_on_pure_gas_basis():
    case = _case("photochemical_oxidation")
    inventory = LabInventory.model_validate(case["inventory"])
    for index, item in enumerate(inventory.gas_hardware):
        item.equipment_id = f"o2_device_{index}"
        item.gas = "O2"
    proposal = FlowProposal(
        flow_rate_mL_min=0.2,
        concentration_M=0.1,
        temperature_C=29,
        BPR_bar=3,
        reactor_type="photochemical coil",
        reactor_volume_mL=1,
        streams=[
            StreamAssignment(
                stream_label="A",
                contents=["thioanisole", "photocatalyst"],
                solvent="acetonitrile",
                concentration_M=0.1,
            ),
            StreamAssignment(
                stream_label="G",
                contents=["air"],
                pump_role="aerobic oxidant feed",
                phase="gas",
                gas_reagent_mole_fraction=0.21,
                molar_equiv=2.0,
                feed_group="ST1-GAS-AIR",
            ),
        ],
    )
    plan = ChemistryPlan(
        stream_logic=[
            StreamLogic(stream_label="A", reagents=["thioanisole"], concentration_M=0.1),
            StreamLogic(
                stream_label="G",
                reagents=["air"],
                phase="gas",
                gas_reagent_mole_fraction=0.21,
                molar_equiv=2.0,
            ),
        ]
    )

    realized, report, validation = realize_executable_design(
        proposal,
        batch_record=BatchRecord(raw_text=case["protocol"]),
        chemistry_plan=plan,
        inventory=inventory,
        hard_constraints=case["hard_constraints"],
    )

    gas = next(item for item in realized.streams if item.phase == "gas")
    expected_sccm = stp_gas_flow_for_equiv(
        realized.flow_rate_mL_min,
        realized.concentration_M,
        2.0,
        1.0,
    )
    assert report["status"] == "complete"
    assert validation["status"] == "ready"
    assert gas.contents == ["O2"]
    assert gas.gas_reagent_mole_fraction == 1.0
    assert gas.feed_group == "ST1-GAS-O2"
    assert gas.gas_flow_sccm == pytest.approx(expected_sccm, rel=1e-5)
    assert gas.molar_equiv == pytest.approx(2.0, rel=1e-3)


def test_protocol_air_collapses_duplicate_air_and_pure_oxygen_feeds():
    case = _case("photochemical_oxidation")
    inventory = LabInventory.model_validate(case["inventory"])
    batch = BatchRecord(
        raw_text=case["protocol"],
        reaction_description=case["protocol"],
        atmosphere="air",
    )
    proposal = FlowProposal(
        flow_rate_mL_min=0.2,
        concentration_M=0.1,
        temperature_C=29,
        BPR_bar=3,
        reactor_type="photochemical coil",
        reactor_volume_mL=1,
        streams=[
            StreamAssignment(
                stream_label="A",
                contents=["thioanisole", "photocatalyst"],
                solvent="acetonitrile",
                concentration_M=0.1,
            ),
            StreamAssignment(
                stream_label="B",
                contents=["air"],
                pump_role="air oxidant feed",
                phase="gas",
                molar_equiv=1.0,
            ),
            StreamAssignment(
                stream_label="G",
                contents=["O2"],
                pump_role="oxygen reagent feed",
                phase="gas",
                molar_equiv=1.0,
            ),
        ],
    )
    plan = ChemistryPlan(
        reaction_name="Aerobic photooxidation",
        o2_is_reagent=True,
        stream_logic=[
            StreamLogic(stream_label="A", reagents=["thioanisole"], concentration_M=0.1),
            StreamLogic(stream_label="B", reagents=["air"], phase="gas", molar_equiv=1.0),
            StreamLogic(stream_label="G", reagents=["O2"], phase="gas", molar_equiv=1.0),
        ],
    )

    realized, report, validation = realize_executable_design(
        proposal,
        batch_record=batch,
        chemistry_plan=plan,
        inventory=inventory,
        hard_constraints=case["hard_constraints"],
    )

    gas_streams = [stream for stream in realized.streams if stream.phase == "gas"]
    assert len(gas_streams) == 1
    assert gas_streams[0].contents == ["air"]
    assert gas_streams[0].pump_equipment_id == "test_air_mfc"
    assert realized.multiphase_metrics["gas_species"] == "air"
    assert len(realized.multiphase_metrics["gas_streams"]) == 1
    assert validation["status"] == "ready"
    assert any(
        item["decision"] == "remove_duplicate_oxidant_feed"
        for item in report["decisions"]
    )


def test_gas_mfc_max_is_solved_jointly_with_liquid_flow():
    case = _case("photochemical_oxidation")
    inventory = LabInventory.model_validate(case["inventory"])
    proposal = FlowProposal(
        flow_rate_mL_min=1.0,
        concentration_M=0.1,
        temperature_C=29,
        BPR_bar=3,
        reactor_type="photochemical coil",
        streams=[
            StreamAssignment(
                stream_label="A",
                contents=["thioanisole"],
                concentration_M=0.1,
            ),
            StreamAssignment(
                stream_label="G",
                contents=["air"],
                phase="gas",
                molar_equiv=1.0,
            ),
        ],
    )
    plan = ChemistryPlan(
        stream_logic=[
            StreamLogic(stream_label="A", reagents=["thioanisole"], concentration_M=0.1),
            StreamLogic(stream_label="G", reagents=["air"], phase="gas", molar_equiv=1.0),
        ]
    )

    realized, report, validation = realize_executable_design(
        proposal,
        batch_record=BatchRecord(raw_text=case["protocol"]),
        chemistry_plan=plan,
        inventory=inventory,
        hard_constraints=case["hard_constraints"],
    )

    gas = next(item for item in realized.streams if item.phase == "gas")
    assert validation["status"] == "ready"
    assert gas.gas_flow_sccm == 6.0
    assert realized.flow_rate_mL_min < 1.0
    assert gas.molar_equiv == pytest.approx(1.0, abs=1e-3)
    assert any(
        item["decision"] == "coupled_gas_liquid_flow_solution"
        for item in report["decisions"]
    )


def test_unknown_cofeed_concentration_is_not_copied_from_substrate():
    case = _case("nitration")
    inventory = LabInventory.model_validate(case["inventory"])
    proposal = FlowProposal(
        flow_rate_mL_min=1.0,
        concentration_M=1.45,
        temperature_C=40,
        streams=[
            StreamAssignment(
                stream_label="A",
                contents=["substrate"],
                concentration_M=1.45,
                concentration_basis="protocol_fact",
            ),
            StreamAssignment(
                stream_label="B",
                contents=["aqueous nitric acid"],
                concentration_M=None,
                molar_equiv=2.0,
            ),
        ],
    )
    plan = ChemistryPlan(
        reaction_name="Dinitration",
        stream_logic=[
            StreamLogic(stream_label="A", reagents=["substrate"], concentration_M=1.45),
            StreamLogic(stream_label="B", reagents=["aqueous nitric acid"], molar_equiv=2.0),
        ],
    )

    realized, report, _ = realize_executable_design(
        proposal,
        batch_record=BatchRecord(raw_text="Dinitration with aqueous nitric acid."),
        chemistry_plan=plan,
        inventory=inventory,
        hard_constraints=case["hard_constraints"],
    )

    acid = next(item for item in realized.streams if item.stream_label == "B")
    assert acid.concentration_M != pytest.approx(1.45)
    assert acid.concentration_basis.startswith("screening_assumption")
    assert any(
        item["decision"] == "cofeed_concentration_assumption"
        for item in report["decisions"]
    )


def test_packed_bed_single_feed_uses_exact_cartridge_and_pressure_setpoint():
    proposal = FlowProposal(
        residence_time_min=3,
        flow_rate_mL_min=0.1,
        temperature_C=110,
        concentration_M=0.3,
        BPR_bar=12,
        reactor_type="packed-bed",
        streams=[
            StreamAssignment(
                stream_label="A",
                pump_role="premixed CuAAC feed",
                contents=["azide A", "alkyne B", "Acetone"],
                solvent="Acetone",
                concentration_M=0.3,
            )
        ],
    )
    plan = ChemistryPlan(
        reaction_name="CuAAC",
        stream_logic=[
            StreamLogic(
                stream_label="A",
                reagents=["azide A", "alkyne B", "Acetone"],
                concentration_M=0.3,
            )
        ],
    )

    realized, _, validation = _realize("cuaac", proposal, plan)

    assert validation["status"] == "ready"
    assert realized.inventory_selection["equipment_id"] == "test_copper_cartridge"
    assert realized.streams[0].pump_equipment_id == "test_cartridge_pump"
    assert realized.BPR_bar == 15
    assert realized.reactor_volume_mL == 0.6
    assert realized.residence_time_min == pytest.approx(
        realized.reactor_volume_mL / realized.flow_rate_mL_min, rel=1e-5
    )


def test_packed_bed_catalyst_and_negated_deoxygenation_compile_without_false_block():
    case = _case("cuaac")
    inventory = LabInventory.model_validate(case["inventory"])
    batch = BatchRecord(raw_text=case["protocol"], reaction_description=case["protocol"])
    catalyst_text = (
        "Cu/C heterogeneous catalyst (10 mol% Cu, pre-packed in "
        "test_copper_cartridge - not in solution)"
    )
    proposal = FlowProposal(
        residence_time_min=2.8,
        flow_rate_mL_min=0.1,
        temperature_C=110,
        concentration_M=0.3,
        BPR_bar=20,
        reactor_type="packed-bed",
        deoxygenation_method=(
            "N2 blanket on feed reservoir; deoxygenation not required"
        ),
        streams=[
            StreamAssignment(
                stream_label="A",
                pump_role="premixed CuAAC feed",
                contents=[
                    "azide A (0.3 M, 1.0 equiv)",
                    "alkyne B (0.33 M, 1.1 equiv)",
                    catalyst_text,
                ],
                solvent="Acetone",
                concentration_M=0.3,
            )
        ],
    )
    plan = ChemistryPlan(
        reaction_name="CuAAC",
        deoxygenation_required=False,
        reagents=[
            ReagentRole(
                name="Cu/C heterogeneous catalyst",
                role="heterogeneous catalyst",
                equiv_or_loading="10 mol% Cu",
            )
        ],
        stream_logic=[
            StreamLogic(
                stream_label="A",
                reagents=[
                    "azide A (0.3 M, 1.0 equiv)",
                    "alkyne B (0.33 M, 1.1 equiv)",
                    catalyst_text,
                ],
                concentration_M=0.3,
            )
        ],
    )

    realized, report, validation = realize_executable_design(
        proposal,
        batch_record=batch,
        chemistry_plan=plan,
        inventory=inventory,
        hard_constraints=case["hard_constraints"],
    )
    topology = _build_singlestep_topology(realized, plan, batch, inventory)
    _, allocation = compile_inventory_topology(
        topology,
        proposal=realized,
        inventory=inventory,
    )

    assert validation["status"] == "ready"
    assert realized.deoxygenation_method == ""
    assert catalyst_text not in realized.streams[0].contents
    stationary = realized.inventory_constraints["stationary_components"]
    assert stationary[0]["placement"] == "stationary_reactor_phase"
    assert not any(op.op_type == "deoxygenation_unit" for op in topology.unit_operations)
    assert allocation["checks"]["all_required_operations_assigned"]
    assert not allocation["unresolved_requirements"]
    assert any(
        item["decision"] == "move_component_to_stationary_reactor_phase"
        for item in report["decisions"]
    )


@pytest.mark.parametrize("role", [
    "heterogeneous copper catalyst packed in cartridge",
    "heterogeneous precatalyst",
    "immobilized pre-catalyst",
    "fixed-bed catalytic material",
])
def test_packed_bed_removes_stationary_catalyst_with_variable_role_wording(role):
    case = _case("cuaac")
    inventory = LabInventory.model_validate(case["inventory"])
    batch = BatchRecord(raw_text=case["protocol"], reaction_description=case["protocol"])
    proposal = FlowProposal(
        residence_time_min=3.0,
        flow_rate_mL_min=0.1,
        temperature_C=110,
        concentration_M=0.3,
        BPR_bar=20,
        reactor_type="packed-bed",
        streams=[
            StreamAssignment(
                stream_label="A",
                pump_role="premixed CuAAC feed",
                contents=[
                    "azide A (0.3 M, 1.0 equiv)",
                    "alkyne B (0.33 M, 1.1 equiv)",
                    "copper on carbon (0.025 M screening assumption)",
                ],
                solvent="acetone",
                concentration_M=0.3,
            )
        ],
    )
    plan = ChemistryPlan(
        reaction_name="CuAAC",
        reagents=[
            ReagentRole(
                name="copper on carbon",
                role=role,
                notes="Use the installed cartridge.",
            )
        ],
    )

    realized, _, validation = realize_executable_design(
        proposal,
        batch_record=batch,
        chemistry_plan=plan,
        inventory=inventory,
        hard_constraints=case["hard_constraints"],
    )

    assert validation["status"] == "ready"
    assert all(
        "copper on carbon" not in item.lower()
        for item in realized.streams[0].contents
    )
    assert (
        realized.inventory_constraints["stationary_components"][0]["name"]
        == "copper on carbon"
    )


def test_connected_photo_sequence_resolves_pressure_pump_gas_lights_and_stages():
    profile = inventory_profile_from_payload(
        json.loads((FIXTURES / "synthetic_connected_inventory.json").read_text())
    )
    protocol = (
        "Synthetic fixture: substrate P and alkene Q undergo a light-driven step "
        "at 34 C under argon, then an aerobic transformation at 44 C. "
        "Use 455 nm light and organic photocatalyst PC at 0.4 mol%. No outcomes are provided."
    )
    proposal = FlowProposal(
        residence_time_min=25,
        flow_rate_mL_min=0.4,
        temperature_C=34,
        concentration_M=0.1,
        BPR_bar=2.5,
        reactor_volume_mL=20,
        wavelength_nm=455,
        streams=[
            StreamAssignment(
                stream_label="A",
                pump_role="Substrate and photocatalyst feed",
                contents=[
                    "substrate P (1.0 equiv)",
                    "alkene Q (2.0 equiv)",
                    "organic photocatalyst PC (0.4 mol%)",
                ],
                concentration_M=0.1,
                introduction_stage=1,
            ),
            StreamAssignment(
                stream_label="B",
                pump_role="Oxygen source for aerobic oxidation",
                contents=["air"],
                phase="gas",
                molar_equiv=1.0,
                introduction_stage=2,
            ),
        ],
    )
    plan = ChemistryPlan(
        n_stages=2,
        stream_logic=[
            StreamLogic(
                stream_label="A",
                reagents=[
                    "substrate P (1.0 equiv)",
                    "alkene Q (2.0 equiv)",
                    "organic photocatalyst PC (0.4 mol%)",
                ],
                concentration_M=0.1,
                introduction_stage=1,
            ),
            StreamLogic(
                stream_label="B",
                reagents=["air"],
                phase="gas",
                molar_equiv=1.0,
                introduction_stage=2,
            ),
        ],
        stages=[
            ProcessStage(
                stage_number=1,
                stage_name="Synthetic light-driven transformation",
                reaction_type="photoredox catalysis",
                temperature_C=34,
                requires_light=True,
                wavelength_nm=455,
                batch_time_h=2,
                feed_streams=[
                    StreamLogic(
                        stream_label="A",
                        reagents=["substrate P", "alkene Q", "photocatalyst"],
                        introduction_stage=1,
                    )
                ],
            ),
            ProcessStage(
                stage_number=2,
                stage_name="Aerobic oxidation",
                reaction_type="oxidation",
                temperature_C=44,
                requires_light=True,
                wavelength_nm=455,
                batch_time_h=3,
                feed_streams=[
                    StreamLogic(
                        stream_label="B",
                        reagents=["air"],
                        phase="gas",
                        introduction_stage=2,
                    )
                ],
            ),
        ],
    )

    realized, report, validation = realize_executable_design(
        proposal,
        batch_record=BatchRecord(raw_text=protocol, reaction_description=protocol),
        chemistry_plan=plan,
        inventory=profile.lab_inventory,
        hard_constraints=profile.operating_constraints,
        operating_limits=profile.design_operating_limits(),
    )

    liquid, gas = realized.streams
    assert report["status"] == "complete"
    assert validation["status"] == "ready"
    assert realized.BPR_bar == 4.0
    assert liquid.pump_equipment_id == "test_dual_stage_pump"
    assert gas.pump_equipment_id == "test_oxygen_mfc"
    assert gas.contents == ["O2"]
    assert gas.gas_flow_sccm <= 3.0
    assert gas.gas_flow_actual_mL_min == pytest.approx(
        actual_gas_flow_from_stp(gas.gas_flow_sccm, 44.0, 4.0), rel=1e-5
    )
    assert [stage["light_equipment_id"] for stage in realized.stage_parameters] == [
        "test_blue_light_one",
        "test_blue_light_two",
    ]
    assert len({stage["reactor_equipment_id"] for stage in realized.stage_parameters}) == 2
    assert realized.residence_time_min == pytest.approx(
        sum(stage["residence_time_inlet_min"] for stage in realized.stage_parameters),
        rel=1e-4,
    )
    assert realized.residence_time_min == realized.residence_time_inlet_min
    assert "inlet/STP" in realized.residence_time_basis
    assert not report["safety_contract"]["hazards"]
    assert not any(
        item["decision"] == "component_quantity_screening_assumption"
        and item.get("component", "").startswith("organic photocatalyst PC")
        for item in report["decisions"]
    )
