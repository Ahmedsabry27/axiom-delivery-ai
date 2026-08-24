from types import SimpleNamespace

from app.ceremony_intelligence.service import checklist_scores, effectiveness


def item(status, weight=1, evidence_required=False, evidence_refs=None):
    return SimpleNamespace(
        status=status,
        weight=weight,
        evidence_required=evidence_required,
        evidence_refs=evidence_refs or [],
    )


def test_checklist_excludes_not_applicable_weight_and_keeps_missing_evidence_incomplete():
    result = checklist_scores(
        [
            item("COMPLETED", 2),
            item("NOT_APPLICABLE", 5),
            item("EVIDENCE_REQUIRED", 3, True),
        ]
    )
    assert result["checklistCompletion"] == {
        "value": 40.0,
        "completedWeight": 2,
        "eligibleWeight": 5,
    }
    assert result["evidenceCoverage"] == {"value": 0.0, "covered": 0, "eligible": 1}


def test_authorized_evidence_coverage_requires_completed_item():
    result = checklist_scores(
        [
            item("COMPLETED", 1, True, [{"id": "e-1", "authorized": True}]),
            item("IN_PROGRESS", 1, True, [{"id": "e-2"}]),
        ]
    )
    assert result["evidenceCoverage"]["value"] == 50.0


def test_effectiveness_is_unknown_until_half_of_configured_weight_is_available():
    result = effectiveness(
        {
            "preparation": 80,
            "evidence": 70,
            "decision_completion": None,
            "action_quality": None,
            "previous_action_closure": None,
            "outcome_achievement": None,
        }
    )
    assert result["value"] is None
    assert result["sufficientData"] is False
    assert "decision_completion" in result["missingDimensions"]


def test_effectiveness_returns_version_weights_inputs_and_missing_dimensions():
    result = effectiveness(
        {
            "preparation": 80,
            "evidence": 60,
            "decision_completion": 90,
            "action_quality": 70,
            "previous_action_closure": None,
            "outcome_achievement": None,
        }
    )
    assert result["value"] == 76.43
    assert result["version"] == "ceremony-effectiveness-v1"
    assert result["sufficientData"] is True
    assert result["weights"]["preparation"] == 0.2
