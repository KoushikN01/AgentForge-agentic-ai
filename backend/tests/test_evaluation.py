"""
Tests for evaluation/run_evaluation.py's scoring logic (imports it as a
module, same pattern as test_demo_setup.py for investigate_demo.py).
Doesn't re-run the whole harness end-to-end here - that's exercised for
real by actually running the script, which this repo's BUILD_VERIFICATION
records the output of.
"""

import importlib.util
from pathlib import Path

EVAL_SCRIPT = Path(__file__).resolve().parents[2] / "evaluation" / "run_evaluation.py"


def load_eval_module():
    spec = importlib.util.spec_from_file_location("run_evaluation", EVAL_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scripted_gemini_proposes_the_correct_patch_for_every_incident():
    ev = load_eval_module()
    for key in ev.demo.INCIDENTS:
        client = ev.make_scripted_gemini(key)
        from app.models.agent_outputs import PatchProposal

        patch = client.generate_structured("prompt", response_model=PatchProposal)
        assert patch.target_file == ev._CORRECT_PATCHES[key].target_file


def test_run_one_resolves_each_real_incident_in_mock_mode():
    ev = load_eval_module()
    for key in ev.demo.INCIDENTS:
        result = ev.run_one(key, live_client=None)
        assert result.final_status == "awaiting_approval"
        assert result.root_cause_file_correct is True
        assert result.tests_passed is True
        assert result.error is None
