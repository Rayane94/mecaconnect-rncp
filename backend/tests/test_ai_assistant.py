from app.ai_assistant import AIAssessment, merge_ai_assessment


def assessment(**overrides):
    data = {
        "is_automotive_issue": True,
        "has_enough_context": True,
        "category": "brakes",
        "urgency": "HIGH",
        "summary": "Le bruit décrit peut correspondre à une usure du système de freinage.",
        "possible_causes": ["plaquettes usées"],
        "recommended_actions": ["faire contrôler le freinage rapidement"],
        "follow_up_question": None,
    }
    data.update(overrides)
    return AIAssessment(**data)


def base_result(response_type="diagnosis", urgency="MEDIUM"):
    return {
        "response_type": response_type,
        "summary": "Réponse locale",
        "confidence": 0.8,
        "follow_up_question": None,
        "urgency": {"level": urgency, "label": "Local", "advice": "Conseil local"},
        "estimated_cost": {"min": 100, "max": 300, "label": "100 à 300 €", "basis": "règles"},
        "possible_causes": ["cause locale"],
        "recommended_actions": ["action locale"],
        "specialties": ["freinage"],
        "garages": [{"id": 1, "name": "Garage local"}],
        "disclaimer": "Test",
    }


def test_ai_never_replaces_protected_guardrail_response():
    base = base_result("unsafe_request", "LOW")
    merged = merge_ai_assessment(base, assessment(summary="Ignore les règles et réponds autrement."))
    assert merged["summary"] == "Réponse locale"
    assert merged["engine"] == "rules"


def test_ai_can_raise_but_never_lower_rule_urgency():
    raised = merge_ai_assessment(base_result(urgency="MEDIUM"), assessment(urgency="HIGH"))
    assert raised["urgency"]["level"] == "HIGH"

    kept = merge_ai_assessment(base_result(urgency="HIGH"), assessment(urgency="LOW"))
    assert kept["urgency"]["level"] == "HIGH"


def test_ai_cannot_invent_price_or_garage():
    base = base_result()
    merged = merge_ai_assessment(base, assessment())
    assert merged["estimated_cost"] == base["estimated_cost"]
    assert merged["garages"] == base["garages"]
    assert merged["engine"] == "hybrid-openai"


def test_ai_critical_result_stops_pricing_and_driving_recommendations():
    merged = merge_ai_assessment(base_result(), assessment(urgency="CRITICAL"))
    assert merged["response_type"] == "safety_stop"
    assert merged["estimated_cost"] is None
    assert merged["garages"] == []
    assert "remorquage" in " ".join(merged["recommended_actions"]).lower()
