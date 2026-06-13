from lifechoice_engine import (
    MODEL_PARAMETERS_B,
    cascade_for,
    choose,
    compact_context,
    current_node,
    environment_state,
    narrative_respects_state,
    start_session,
)


def make_session():
    return start_session(
        "Artist vs Software Engineer",
        "A",
        "Rent matters, but I already have two paying design clients and family pressure.",
        "Mentor",
    )


def test_model_is_small():
    assert MODEL_PARAMETERS_B < 32


def test_context_is_bounded():
    session = make_session()
    for index in range(7):
        result = choose(session, index % 3)
        if result["complete"]:
            break
    context = compact_context(session)
    assert len(context["recent_choices"]) <= 3
    assert len(context["facts"]) <= 8
    assert len(context["obligations"]) <= 5
    assert len(context["closed_options"]) <= 5


def test_choices_create_divergent_state_and_facts():
    left = make_session()
    right = make_session()
    choose(left, 0)
    choose(right, 1)
    assert left.world_state != right.world_state
    assert left.facts != right.facts
    assert left.obligations != right.obligations


def test_world_state_is_clamped():
    session = make_session()
    for _ in range(8):
        result = choose(session, 0)
        if result["complete"]:
            break
    assert all(0 <= value <= 100 for value in session.world_state.values())


def test_critical_state_requires_narrative_acknowledgement():
    state = {
        "financial_security": 10,
        "creative_fulfillment": 70,
        "social_validation": 50,
        "stress": 90,
        "family_satisfaction": 50,
    }
    assert not narrative_respects_state("A pleasant opportunity arrives and everything feels normal.", state)
    assert narrative_respects_state("Rent is urgent and exhaustion is affecting the deadline.", state)


def test_environment_responds_to_metrics():
    healthy = dict(financial_security=80, creative_fulfillment=80, social_validation=75, stress=20, family_satisfaction=75)
    crisis = dict(financial_security=12, creative_fulfillment=55, social_validation=35, stress=90, family_satisfaction=30)
    assert environment_state(healthy) == "thriving"
    assert environment_state(crisis) == "struggling"


def test_three_cascade_moments():
    session = make_session()
    cascades = []
    for _ in range(8):
        result = choose(session, 1)
        if result.get("cascade"):
            cascades.append(result["cascade"]["label"])
        if result["complete"]:
            break
    assert cascades == ["A small echo", "The delayed consequence", "The final payoff"]


def test_opening_scene_is_immediate_and_deterministic():
    session = make_session()
    node = current_node(session)
    assert node["generation_source"] == "deterministic"
    assert len(node["choices"]) == 3

