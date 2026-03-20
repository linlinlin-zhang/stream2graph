from __future__ import annotations

from typing import Any

from tools.eval.common import utc_iso
from tools.incremental_system.algorithm import DeterministicAlgorithmLayer, graph_exact_match, graph_metrics
from tools.incremental_system.models import GateModel, PlannerModel
from tools.incremental_system.schema import RuntimeSample


class IncrementalSystemRunner:
    def __init__(
        self,
        algorithm_layer: DeterministicAlgorithmLayer,
        gate_model: GateModel,
        planner_model: PlannerModel,
    ) -> None:
        self.algorithm_layer = algorithm_layer
        self.gate_model = gate_model
        self.planner_model = planner_model

    def run_sample(self, sample: RuntimeSample) -> dict[str, Any]:
        state = self.algorithm_layer.bootstrap_state(sample)
        observed_turns = []
        events: list[dict[str, Any]] = []
        updates_emitted = 0

        for turn in sample.turns:
            observed_turns.append(turn)
            if state.current_stage_index >= sample.total_stages:
                events.append(
                    {
                        "turn": turn.to_payload(),
                        "gate": {
                            "action": "WAIT",
                            "target_stage_index": sample.total_stages,
                            "reason": "all stages already applied",
                            "confidence": 1.0,
                            "metadata": {"runtime_short_circuit": True},
                        },
                        "state_before": self.algorithm_layer.summarize_state(state),
                    }
                )
                continue
            gate_decision = self.gate_model.decide(sample, state, observed_turns)
            expected_stage_index = state.current_stage_index + 1
            if gate_decision.action == "EMIT_UPDATE":
                raw_target = gate_decision.target_stage_index
                if raw_target != expected_stage_index:
                    gate_decision.target_stage_index = expected_stage_index
                    gate_decision.metadata = {
                        **dict(gate_decision.metadata),
                        "normalized_target_stage_index": expected_stage_index,
                        "raw_target_stage_index": raw_target,
                    }
            event: dict[str, Any] = {
                "turn": turn.to_payload(),
                "gate": gate_decision.to_payload(),
                "state_before": self.algorithm_layer.summarize_state(state),
            }

            if gate_decision.action == "EMIT_UPDATE":
                requested_stage_index = gate_decision.target_stage_index or expected_stage_index
                if requested_stage_index <= state.current_stage_index or requested_stage_index > sample.total_stages:
                    event["update"] = {
                        "ignored": True,
                        "reason": "gate requested an invalid or non-advancing stage",
                    }
                    events.append(event)
                    continue
                planner_output = self.planner_model.plan(sample, state, observed_turns, gate_decision)
                if planner_output.target_stage_index != expected_stage_index:
                    planner_output.target_stage_index = expected_stage_index
                    planner_output.metadata = {
                        **dict(planner_output.metadata),
                        "normalized_target_stage_index": expected_stage_index,
                    }
                if planner_output.target_stage_index > state.current_stage_index:
                    state, update_payload = self.algorithm_layer.apply_planner_output(sample, state, planner_output)
                    updates_emitted += 1
                    event["planner"] = planner_output.to_payload()
                    event["update"] = update_payload
                    event["state_after"] = self.algorithm_layer.summarize_state(state)
                else:
                    event["planner"] = planner_output.to_payload()
                    event["update"] = {
                        "ignored": True,
                        "reason": "planner requested a non-advancing stage",
                    }
            events.append(event)

        final_reference = sample.stages[-1].graph_ir if sample.stages else None
        final_match = graph_exact_match(state.current_graph_ir, final_reference)
        return {
            "sample_id": sample.sample_id,
            "diagram_type": sample.diagram_type,
            "generated_at_utc": utc_iso(),
            "system": {
                "algorithm_layer": self.algorithm_layer.name,
                "gate_model": getattr(self.gate_model, "name", self.gate_model.__class__.__name__),
                "planner_model": getattr(self.planner_model, "name", self.planner_model.__class__.__name__),
            },
            "summary": {
                "turn_count": len(sample.turns),
                "total_stages": sample.total_stages,
                "updates_emitted": updates_emitted,
                "final_stage_index": state.current_stage_index,
                "applied_stage_indices": list(state.applied_stage_indices),
                "completed_all_stages": state.current_stage_index == sample.total_stages,
                "final_matches_reference": final_match,
                "final_graph_metrics": graph_metrics(state.current_graph_ir) if state.current_graph_ir else {},
                "reference_graph_metrics": graph_metrics(final_reference) if final_reference else {},
            },
            "final_state": state.to_payload(),
            "events": events,
        }
