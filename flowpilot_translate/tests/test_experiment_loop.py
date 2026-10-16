"""Software refinement tests using invented inputs, never measured campaigns."""

import pytest

from flowpilot_translate.experiment_loop import (
    ActualConditions,
    ExperimentalOutcomes,
    ExperimentResult,
    calibrate_experimental_campaign,
    extract_experiments_from_text,
    refine_from_experimental_campaign,
    refine_from_experiment,
)


def _base_result():
    return {
        "design_version": 1,
        "confidence": "MEDIUM",
        "explanation": "Initial FlowPilot design.",
        "proposal": {
            "residence_time_min": 10.0,
            "flow_rate_mL_min": 0.2,
            "reactor_volume_mL": 2.0,
            "temperature_C": 40.0,
            "concentration_M": 0.1,
            "BPR_bar": 5.0,
            "reactor_type": "photoreactor coil",
            "tubing_material": "FEP",
            "tubing_ID_mm": 0.8,
            "pre_reactor_steps": ["degas stream A with N2"],
            "post_reactor_steps": [],
            "chemistry_notes": "Photoredox reaction.",
            "safety_flags": [],
            "streams": [
                {
                    "stream_label": "A",
                    "pump_role": "substrate + photocatalyst",
                    "contents": ["substrate", "photocatalyst"],
                    "solvent": "MeCN",
                    "concentration_M": 0.1,
                    "flow_rate_mL_min": 0.1,
                    "phase": "liquid",
                    "reasoning": "Main reaction stream.",
                },
                {
                    "stream_label": "B",
                    "pump_role": "base",
                    "contents": ["base"],
                    "solvent": "MeCN",
                    "concentration_M": 0.1,
                    "flow_rate_mL_min": 0.1,
                    "phase": "liquid",
                    "reasoning": "Separate base stream.",
                },
            ],
            "reasoning_per_field": {},
        },
    }


def _gas_screen_result():
    """Invented gas/liquid starting point, unrelated to a laboratory campaign."""
    result = _base_result()
    result["proposal"].update({
        "residence_time_min": 10.0, "flow_rate_mL_min": 0.04,
        "reactor_volume_mL": 8.0, "temperature_C": 30.0,
        "concentration_M": 0.2, "BPR_bar": 4.0, "tubing_ID_mm": 1.0,
        "streams": [
            {"stream_label": "A", "pump_role": "invented substrate solution",
             "contents": ["compound A"], "solvent": "water", "concentration_M": 0.2,
             "flow_rate_mL_min": 0.04, "phase": "liquid", "reasoning": "Synthetic test input."},
            {"stream_label": "B", "pump_role": "O2", "contents": ["O2"], "solvent": "",
             "concentration_M": None, "flow_rate_mL_min": 0.16, "phase": "gas",
             "gas_flow_actual_mL_min": 0.16, "gas_flow_sccm": 0.76,
             "reasoning": "Synthetic gas-reference test input."},
        ],
    })
    return result


def _synthetic_experiments():
    """Purpose-built arithmetic fixtures; percentages are invented, not measured.

    All rows use a 6 mL volume and gas/liquid ratios of 6.5 at inlet
    and 2 in channel. The distinct time bases test consistent scaling.
    """
    rows = [("synthetic_long", 0.02, 50.0, None),
            ("synthetic_short", 0.10, 10.0, 80.0),
            ("synthetic_fast", 0.16, 5.0, 90.0)]
    return [ExperimentResult(
        run_id=label, design_version=1,
        actual_conditions=ActualConditions(
            residence_time_inlet_min=6.0 / (7.5 * flow),
            residence_time_in_channel_min=6.0 / (3.0 * flow),
            residence_time_basis="in_channel", flow_rate_mL_min=flow,
            substrate_flow_mL_min=flow, gas_flow_in_channel_mL_min=2.0 * flow,
            gas_flow_stp_mL_min=6.5 * flow, gas_equiv_inlet=1.5,
            temperature_C=30.0, concentration_M=0.2, tubing_ID_mm=1.0,
            reactor_volume_mL=6.0, BPR_bar=4.0),
        outcomes=ExperimentalOutcomes(product_pct=product, yield_pct=product,
                                     starting_material_pct=starting))
        for label, flow, product, starting in rows]


def _synthetic_inlet_basis_experiments():
    experiments = _synthetic_experiments()[1:]
    for experiment in experiments:
        experiment.actual_conditions.residence_time_basis = "inlet_stp"
    return experiments


def test_low_conversion_increases_residence_time_and_preserves_volume():
    experiment = ExperimentResult(
        run_id="run_01",
        design_version=1,
        actual_conditions=ActualConditions(
            residence_time_min=10.0,
            flow_rate_mL_min=0.2,
            reactor_volume_mL=2.0,
            temperature_C=40.0,
            concentration_M=0.1,
        ),
        outcomes=ExperimentalOutcomes(
            yield_pct=28.0,
            conversion_pct=45.0,
            selectivity_pct=92.0,
        ),
    )

    closed_loop = refine_from_experiment(_base_result(), experiment)

    assert closed_loop.decision.failure_modes == ["kinetic_underconversion"]
    proposal = closed_loop.refined_result["proposal"]
    assert proposal["residence_time_min"] == 38.515
    assert proposal["reactor_volume_mL"] == 2.0
    assert proposal["flow_rate_mL_min"] == 0.05193
    assert closed_loop.refined_result["design_version"] == 2


def test_precipitation_and_pressure_drift_add_screening_controls():
    experiment = ExperimentResult(
        run_id="run_01",
        design_version=1,
        actual_conditions=ActualConditions(
            residence_time_min=10.0,
            flow_rate_mL_min=0.2,
            reactor_volume_mL=2.0,
            temperature_C=40.0,
            concentration_M=0.1,
            BPR_bar=5.0,
        ),
        outcomes=ExperimentalOutcomes(
            yield_pct=42.0,
            conversion_pct=88.0,
            selectivity_pct=62.0,
            pressure_bar=9.0,
            pressure_drift_bar=4.0,
            precipitation_observed=True,
        ),
    )

    closed_loop = refine_from_experiment(_base_result(), experiment)
    proposal = closed_loop.refined_result["proposal"]

    assert "selectivity_loss" in closed_loop.decision.failure_modes
    assert "solubility_or_fouling" in closed_loop.decision.failure_modes
    assert "pressure_instability" in closed_loop.decision.failure_modes
    assert proposal["temperature_C"] == 30.0
    assert proposal["concentration_M"] == 0.07
    assert proposal["BPR_bar"] == 7.0
    assert "inline 2 um filter before reactor" in proposal["pre_reactor_steps"]
    assert closed_loop.decision.status == "screen_required"
    assert any("pressure instability" in flag for flag in proposal["safety_flags"])


def test_three_cycle_case_reaches_converged_design_version():
    result = _base_result()
    cycles = [
        ExperimentalOutcomes(yield_pct=30.0, conversion_pct=48.0, selectivity_pct=90.0),
        ExperimentalOutcomes(yield_pct=58.0, conversion_pct=90.0, selectivity_pct=74.0),
        ExperimentalOutcomes(yield_pct=84.0, conversion_pct=94.0, selectivity_pct=91.0),
    ]
    last = None
    for idx, outcomes in enumerate(cycles, 1):
        proposal = result["proposal"]
        experiment = ExperimentResult(
            run_id=f"run_{idx:02d}",
            design_version=result["design_version"],
            actual_conditions=ActualConditions(
                residence_time_min=proposal["residence_time_min"],
                flow_rate_mL_min=proposal["flow_rate_mL_min"],
                reactor_volume_mL=proposal["reactor_volume_mL"],
                temperature_C=proposal["temperature_C"],
                concentration_M=proposal["concentration_M"],
                BPR_bar=proposal["BPR_bar"],
            ),
            outcomes=outcomes,
        )
        last = refine_from_experiment(result, experiment)
        result = last.refined_result

    assert last is not None
    assert last.decision.status == "converged"
    assert result["design_version"] == 4
    assert result["proposal"]["confidence"] == "MEDIUM"


def test_campaign_calibration_builds_synthetic_residence_time_ladder():
    calibration = calibrate_experimental_campaign(
        _synthetic_experiments(), target_yield_pct=75.0, target_conversion_pct=75.0)

    assert calibration.n_usable == 3
    assert calibration.best_run_id == "synthetic_long"
    assert calibration.primary_residence_time_basis == "inlet/STP apparent residence time"
    assert calibration.best_tau_inlet_min == 40.0
    assert calibration.best_tau_in_channel_min == 100.0
    assert calibration.recommended_tau_inlet_min == 70.0
    assert calibration.recommended_tau_in_channel_min == pytest.approx(175.0, abs=0.05)
    # With the idealized first-order assumption, going from 50% to 75%
    # requires two half-lives. This is an analytic oracle, not lab evidence.
    assert calibration.target_tau_inlet_min == 80.0
    assert calibration.target_tau_in_channel_min == pytest.approx(200.0, abs=0.05)
    assert calibration.design_ladder[0]["label"] == "best_observed_anchor"
    assert calibration.design_ladder[-1]["label"] == "target_estimate"


def test_campaign_refinement_overrides_short_intensification_design():
    closed_loop = refine_from_experimental_campaign(
        _gas_screen_result(), _synthetic_experiments(),
        target_yield_pct=75.0, target_conversion_pct=75.0)
    proposal = closed_loop.refined_result["proposal"]
    next_exp = closed_loop.decision.next_experiment
    assert proposal["residence_time_min"] == 70.0
    assert proposal["residence_time_min"] == proposal["residence_time_inlet_min"]
    assert proposal["residence_time_in_channel_min"] == pytest.approx(175.0, abs=0.05)
    assert proposal["residence_time_basis"] == "inlet/STP apparent residence time"
    assert proposal["flow_rate_mL_min"] < 0.02
    assert next_exp["evidence_calibration"]["best_tau_in_channel_min"] == 100.0
    assert next_exp["evidence_calibration"]["target_tau_in_channel_min"] == pytest.approx(200.0, abs=0.05)
    assert "experiment_calibrated_kinetics" in closed_loop.decision.failure_modes


def test_short_campaign_can_calibrate_on_inlet_stp_basis():
    calibration = calibrate_experimental_campaign(
        _synthetic_inlet_basis_experiments(), target_yield_pct=75.0, target_conversion_pct=75.0)
    assert calibration.n_usable == 2
    assert calibration.primary_residence_time_basis == "inlet/STP apparent residence time"
    assert calibration.best_run_id == "synthetic_short"
    assert calibration.best_tau_min == calibration.best_tau_inlet_min == 8.0
    assert calibration.best_tau_in_channel_min == pytest.approx(20.0)
    assert calibration.recommended_tau_inlet_min == 38.0
    assert calibration.target_tau_inlet_min > calibration.recommended_tau_inlet_min
    recommended = calibration.recommended_conditions
    assert recommended["residence_time_min"] == recommended["residence_time_inlet_min"]
    assert recommended["residence_time_in_channel_min"] == pytest.approx(95.0, abs=0.05)
    assert recommended["gas_flow_stp_mL_min"] > recommended["gas_flow_in_channel_mL_min"]
    assert recommended["gas_flow_stp_mL_min"] / recommended["substrate_flow_mL_min"] == pytest.approx(6.5, abs=0.01)


def test_campaign_refinement_preserves_inlet_basis_for_short_feedback():
    result = _gas_screen_result()
    result["proposal"].update({"residence_time_basis": "inlet/STP apparent residence time",
        "residence_time_min": 8.0, "residence_time_inlet_min": 8.0,
        "residence_time_in_channel_min": 20.0})
    closed_loop = refine_from_experimental_campaign(
        result, _synthetic_inlet_basis_experiments(),
        target_yield_pct=75.0, target_conversion_pct=75.0)
    proposal = closed_loop.refined_result["proposal"]
    assert proposal["residence_time_basis"] == "inlet/STP apparent residence time"
    assert proposal["residence_time_min"] == proposal["residence_time_inlet_min"] == 38.0
    assert proposal["residence_time_in_channel_min"] == pytest.approx(95.0, abs=0.05)
    assert proposal["gas_flow_sccm"] > proposal["gas_flow_actual_mL_min"]
    assert "experiment_calibrated_kinetics" in closed_loop.decision.failure_modes


def test_extract_experiments_from_prompt_text():
    # Entirely invented rows exercising verbose parser labels and missing SM.
    prompt = """
Entry 1, Synthetic long:
T = 30 C
c = 0.2 M
P = 4 bar
substrate flow = 0.02 mL/min
O2 in-channel = 0.04 mL/min
O2 inlet/STP = 0.13 mL/min
O2 equiv inlet = 1.5
t inlet = 40 min
t in-channel = 100 min
reactor volume = 6 mL
product = 50%
tubing ID = 1 mm

Entry 2, Synthetic fast:
T = 30 C
c = 0.2 M
P = 4 bar
substrate flow = 0.16 mL/min
O2 in-channel = 0.32 mL/min
O2 inlet/STP = 1.04 mL/min
O2 equiv inlet = 1.5
t inlet = 5 min
t in-channel = 12.5 min
reactor volume = 6 mL
starting material = 90%
product = 5%
tubing ID = 1 mm
"""
    experiments = extract_experiments_from_text(prompt)
    assert len(experiments) == 2
    assert experiments[0].run_id == "entry_01_synthetic_long"
    assert experiments[0].actual_conditions.residence_time_in_channel_min == 100.0
    assert experiments[0].actual_conditions.residence_time_basis == "inlet_stp"
    assert experiments[0].outcomes.yield_pct == 50.0
    assert experiments[1].outcomes.conversion_pct == 10.0


def test_extract_compact_synthetic_rows_and_calibrate_longer_inlet_screen():
    # Fictional text tests compact rows, unicode oxygen, optional values and ~.
    prompt = """
1- Entry 3: Note Synthetic short, T 30, c 0.2, P 4.0 (3+1), Substrate 0.1, O₂ In-channel 0.2, O₂ Inlet/STP 0.65, O₂ equiv 1.5, t inlet 8, t in-channel 20, Reactor Volume 6, Starting Material 80, Product 10, Tubing ID 1

2- Entry 4: Note Synthetic fast, T 30, c 0.2, P 4.0 (3+1), Substrate 0.16, O₂ In-channel 0.32, O₂ Inlet/STP 1.04, O₂ equiv 1.5, t inlet 5, t in-channel 12.5, Reactor Volume 6, Starting Material 90, Product 5, Tubing ID 1

3- Entry 5: Note Synthetic long, T 30, c 0.2, P 4.0 (3+1), Substrate 0.02, O₂ In-channel 0.04, O₂ Inlet/STP 0.13, O₂ equiv ~1.5, t inlet 40, t in-channel 100, Reactor Volume 6, Starting Material -, Product 50, Tubing ID 1
"""
    experiments = extract_experiments_from_text(prompt)
    assert len(experiments) == 3
    best = experiments[-1]
    assert best.run_id == "entry_05_synthetic_long"
    assert best.actual_conditions.substrate_flow_mL_min == 0.02
    assert best.actual_conditions.gas_flow_stp_mL_min == 0.13
    assert best.actual_conditions.gas_flow_in_channel_mL_min == 0.04
    assert best.actual_conditions.residence_time_inlet_min == 40.0
    assert best.actual_conditions.residence_time_in_channel_min == 100.0
    assert best.outcomes.product_pct == 50.0
    calibration = calibrate_experimental_campaign(
        experiments, target_yield_pct=75.0, target_conversion_pct=75.0,
        residence_time_basis="inlet_stp")
    assert calibration.best_run_id == best.run_id
    assert calibration.best_tau_inlet_min == 40.0
    assert calibration.recommended_tau_inlet_min == 70.0
    assert calibration.target_tau_inlet_min == 80.0
    assert calibration.recommended_conditions["residence_time_in_channel_min"] == pytest.approx(175.0, abs=0.05)
    assert calibration.recommended_conditions["gas_flow_stp_mL_min"] > calibration.recommended_conditions["gas_flow_in_channel_mL_min"]
