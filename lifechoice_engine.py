from __future__ import annotations

import copy
import json
import os
import re
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
MODEL_PARAMETERS_B = 7
METRICS = (
    "financial_security",
    "creative_fulfillment",
    "social_validation",
    "stress",
    "family_satisfaction",
)
MONTHS = ("Month 1", "Month 2", "Month 3", "Month 4", "Month 5", "Month 6", "Month 8", "Month 10")
THEMES = (
    "first commitment",
    "money pressure",
    "social comparison",
    "identity friction",
    "family pressure",
    "delayed consequence",
    "survival versus meaning",
    "final reckoning",
)
EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="lifechoice")


@dataclass
class SimulationSession:
    dilemma: str
    chosen_path: str
    unchosen_path: str
    calibration: str
    persona: str
    environment_category: str
    world_state: dict[str, int]
    characters: dict[str, dict[str, str]]
    current_node: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)
    obligations: list[str] = field(default_factory=list)
    closed_options: list[str] = field(default_factory=list)
    generated_nodes: dict[int, dict[str, Any]] = field(default_factory=dict)
    pending_nodes: dict[int, Future] = field(default_factory=dict, repr=False)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


def split_dilemma(dilemma: str) -> tuple[str, str]:
    text = " ".join(dilemma.strip().split())
    for pattern in (r"\s+vs\.?\s+", r"\s+versus\s+", r"\s*/\s*", r"\s+or\s+"):
        parts = re.split(pattern, text, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2 and all(parts):
            return _label(parts[0]), _label(parts[1])
    return _label(text) or "Path A", "Safer Alternative"


def start_session(
    dilemma: str,
    chosen_key: str,
    calibration: str,
    persona: str,
) -> SimulationSession:
    path_a, path_b = split_dilemma(dilemma)
    chosen, unchosen = (path_b, path_a) if chosen_key == "B" else (path_a, path_b)
    session = SimulationSession(
        dilemma=dilemma.strip(),
        chosen_path=chosen,
        unchosen_path=unchosen,
        calibration=calibration.strip(),
        persona=persona,
        environment_category=infer_environment(chosen),
        world_state=derive_initial_world_state(dilemma, calibration),
        characters=_characters(chosen, unchosen),
    )
    session.generated_nodes[0] = build_node(session, 0, use_llm=False)
    prefetch_node(session, 1)
    return session


def choose(session: SimulationSession, choice_index: int, custom_text: str = "") -> dict[str, Any]:
    node = current_node(session)
    if custom_text.strip():
        choice = _custom_choice(node, custom_text.strip())
        choice_index = -1
    else:
        choice_index = max(0, min(choice_index, len(node["choices"]) - 1))
        choice = node["choices"][choice_index]

    for key in METRICS:
        session.world_state[key] = _clamp(session.world_state[key] + int(choice["delta"].get(key, 0)))

    record = {
        "node_index": session.current_node,
        "month_label": node["month_label"],
        "theme": node["node_theme"],
        "scenario": node["scenario"],
        "choice_index": choice_index,
        "choice_text": choice["text"],
        "delta": copy.deepcopy(choice["delta"]),
        "world_state_after": copy.deepcopy(session.world_state),
    }
    session.history.append(record)
    _merge_unique(session.facts, choice.get("facts_created", []), limit=10)
    _merge_unique(session.obligations, choice.get("obligations", []), limit=6)
    _merge_unique(session.closed_options, choice.get("closed_options", []), limit=6)
    session.current_node += 1

    reaction = persona_reaction(session, record)
    cascade = cascade_for(session, record)
    if session.current_node >= len(MONTHS):
        return {"complete": True, "record": record, "reaction": reaction, "cascade": cascade, "report": build_report(session)}

    next_node = _consume_or_build(session, session.current_node)
    prefetch_node(session, session.current_node + 1)
    return {
        "complete": False,
        "record": record,
        "reaction": reaction,
        "cascade": cascade,
        "node": next_node,
    }


def current_node(session: SimulationSession) -> dict[str, Any]:
    return session.generated_nodes[session.current_node]


def prefetch_node(session: SimulationSession, index: int) -> None:
    if index >= len(MONTHS) or index in session.generated_nodes or index in session.pending_nodes:
        return
    snapshot = compact_context(session)
    session.pending_nodes[index] = EXECUTOR.submit(build_node_from_context, snapshot, index, True)


def compact_context(session: SimulationSession) -> dict[str, Any]:
    return {
        "dilemma": session.dilemma,
        "chosen_path": session.chosen_path,
        "unchosen_path": session.unchosen_path,
        "calibration": session.calibration[:360],
        "persona": session.persona,
        "world_state": copy.deepcopy(session.world_state),
        "characters": copy.deepcopy(session.characters),
        "facts": session.facts[-8:],
        "obligations": session.obligations[-5:],
        "closed_options": session.closed_options[-5:],
        "recent_choices": [
            {"month": item["month_label"], "choice": item["choice_text"]}
            for item in session.history[-3:]
        ],
    }


def build_node(session: SimulationSession, index: int, use_llm: bool = True) -> dict[str, Any]:
    return build_node_from_context(compact_context(session), index, use_llm)


def build_node_from_context(context: dict[str, Any], index: int, use_llm: bool = True) -> dict[str, Any]:
    fallback = deterministic_node(context, index)
    if not use_llm:
        return fallback
    generated = _generate_node_with_hf(context, index)
    return validate_node(generated, fallback, context)


def deterministic_node(context: dict[str, Any], index: int) -> dict[str, Any]:
    chosen = context["chosen_path"]
    unchosen = context["unchosen_path"]
    state = context["world_state"]
    pressure = state_facts(state)
    prior = context.get("recent_choices", [])
    prior_text = prior[-1]["choice"] if prior else f"step into {chosen}"
    facts = context.get("facts") or ["your first commitment"]
    fact = facts[-1]

    scenarios = (
        f"A real opening appears on the {chosen} path. Taking it makes your decision visible to people who still expect {unchosen}. {pressure[0]}",
        f"The first bill and deadline arrive together. Your choice to {prior_text.lower()} now has a practical cost. {pressure[0]}",
        f"A peer posts a polished update from {unchosen} while your progress stays private. {pressure[1]}",
        f"An easier offer would protect your routine but blur the identity you wanted from {chosen}. {pressure[0]}",
        f"Your family asks for proof that {chosen} can become sustainable. The conversation is shaped by {fact}. {pressure[1]}",
        f"An earlier commitment returns as an opportunity with conditions attached. You cannot accept it without paying a cost created months ago. {pressure[0]}",
        f"You are no longer choosing only between paths. You are choosing what structure makes {chosen} survivable. {pressure[1]}",
        f"Ten months in, the outside decision is clearer. The final choice is whether your version of {chosen} can carry both meaning and responsibility. {pressure[0]}",
    )
    choices = _choice_templates(chosen, unchosen, index)
    return {
        "month_label": MONTHS[index],
        "node_theme": THEMES[index],
        "scenario": scenarios[index],
        "choices": choices,
        "generation_source": "deterministic",
    }


def _choice_templates(chosen: str, unchosen: str, index: int) -> list[dict[str, Any]]:
    templates = (
        (
            (f"Accept the first concrete {chosen} opportunity and tell people you are committed", _delta(-7, 12, 5, 9, -3), ["publicly_committed"], ["prove_progress"], []),
            (f"Negotiate a smaller {chosen} commitment while keeping income or study stability", _delta(5, 5, 1, 2, 3), ["built_a_safety_floor"], ["maintain_two_tracks"], []),
            (f"Delay the move and keep {unchosen} fully available for another month", _delta(6, -7, -3, 7, 4), ["delayed_commitment"], ["make_a_deadline"], []),
        ),
        (
            ("Cut optional spending and protect time for the path you chose", _delta(-4, 8, -2, 7, -4), ["protected_the_bold_path"], ["tight_budget"], []),
            ("Take paid side work and reduce the pace of the main path", _delta(10, -3, 3, 5, 4), ["added_paid_work"], ["less_time_for_core_path"], []),
            (f"Pause {chosen} until savings recover, even if momentum disappears", _delta(12, -11, 4, -5, 7), ["paused_for_money"], [], ["current_momentum"]),
        ),
        (
            ("Share unfinished work publicly and accept comparison as part of growth", _delta(-1, 6, 11, 8, -1), ["became_visible"], ["respond_to_feedback"], []),
            ("Ignore the comparison and protect a private building phase", _delta(1, 8, -5, 2, 0), ["chose_private_progress"], [], []),
            (f"Ask someone on {unchosen} for an honest comparison of both paths", _delta(3, 1, 5, 4, 3), ["sought_cross_path_advice"], ["face_comparison"], []),
        ),
        (
            ("Reject the easier offer because it changes what the work means to you", _delta(-10, 13, -2, 8, -3), ["protected_identity"], ["replace_lost_income"], ["easy_offer"]),
            ("Accept the compromise and use the stability to recover", _delta(13, -7, 5, -6, 7), ["accepted_compromise"], [], []),
            ("Negotiate narrower terms that preserve both income and ownership", _delta(6, 6, 3, 4, 2), ["negotiated_middle_path"], ["deliver_negotiated_terms"], []),
        ),
        (
            ("Show your family the real plan, including risks and deadlines", _delta(2, 2, 3, -3, 11), ["shared_full_plan"], ["report_progress"], []),
            ("Hide the uncertainty until results become visible", _delta(0, 4, -2, 9, -9), ["hid_the_messy_parts"], ["maintain_the_story"], []),
            ("Let family concern change the next move toward stability", _delta(8, -8, 5, -3, 12), ["family_changed_direction"], [], ["unrestricted_risk"]),
        ),
        (
            ("Accept the returning opportunity and absorb its delayed cost", _delta(-11, 13, 9, 12, -4), ["accepted_delayed_payoff"], ["pay_delayed_cost"], []),
            ("Decline because the earlier choice made the cost unsustainable", _delta(8, -10, -2, -7, 6), ["declined_delayed_payoff"], [], ["returning_opportunity"]),
            ("Redesign the opportunity around the obligations you already created", _delta(4, 7, 5, 3, 4), ["redesigned_consequence"], ["honor_existing_obligations"], []),
        ),
        (
            ("Build a financial and time floor around the meaningful work", _delta(12, 6, 2, -9, 5), ["built_sustainable_structure"], ["follow_weekly_limits"], []),
            ("Push harder for visible progress and accept another intense season", _delta(-6, 10, 8, 14, -5), ["chose_intensity"], ["recover_after_push"], []),
            (f"Return to {unchosen} as the main path and keep this work secondary", _delta(14, -12, 7, -5, 9), ["returned_to_alternative"], [], ["chosen_path_as_primary"]),
        ),
        (
            ("Commit to the chosen path with explicit money, health, and relationship boundaries", _delta(8, 11, 6, -10, 7), ["committed_with_boundaries"], [], []),
            (f"Choose {unchosen} and preserve the meaningful parts as a serious side practice", _delta(14, -7, 8, -7, 10), ["chose_stability_with_meaning"], [], ["chosen_path_as_primary"]),
            ("Run a measured three-month experiment before using a permanent label", _delta(5, 5, 1, -2, 2), ["chose_measured_experiment"], ["define_success_metrics"], []),
        ),
    )
    result = []
    for text, delta, facts, obligations, closed in templates[index]:
        result.append(
            {
                "text": text,
                "delta": delta,
                "facts_created": facts,
                "obligations": obligations,
                "closed_options": closed,
            }
        )
    return result


def validate_node(data: Any, fallback: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict) or not isinstance(data.get("choices"), list) or len(data["choices"]) != 3:
        return fallback
    scenario = " ".join(str(data.get("scenario", "")).split())[:420]
    if len(scenario) < 50 or not narrative_respects_state(scenario, context["world_state"]):
        return fallback
    choices = []
    for index, raw in enumerate(data["choices"]):
        if not isinstance(raw, dict) or len(str(raw.get("text", ""))) < 12:
            return fallback
        base = fallback["choices"][index]
        choices.append(
            {
                "text": " ".join(str(raw["text"]).split())[:150],
                "delta": _normalize_delta(raw.get("delta")),
                "facts_created": _clean_list(raw.get("facts_created")) or base["facts_created"],
                "obligations": _clean_list(raw.get("obligations")),
                "closed_options": _clean_list(raw.get("closed_options")),
            }
        )
    return {**fallback, "scenario": scenario, "choices": choices, "generation_source": "hf_llm"}


def narrative_respects_state(text: str, state: dict[str, int]) -> bool:
    lower = text.lower()
    if state["stress"] >= 80 and not any(word in lower for word in ("stress", "tired", "exhaust", "pressure", "overwhelm", "sleep")):
        return False
    if state["financial_security"] <= 25 and not any(word in lower for word in ("money", "rent", "bill", "saving", "income", "cost", "financial")):
        return False
    if state["family_satisfaction"] <= 25 and not any(word in lower for word in ("family", "home", "parent", "trust", "conversation")):
        return False
    return True


def state_facts(state: dict[str, int]) -> list[str]:
    facts = []
    if state["financial_security"] <= 25:
        facts.append("Money is now urgent enough to constrain the available choices.")
    elif state["financial_security"] >= 75:
        facts.append("Savings provide room to choose without immediate panic.")
    if state["stress"] >= 80:
        facts.append("Exhaustion is visible and cannot be treated as background noise.")
    elif state["stress"] <= 30:
        facts.append("You have enough emotional room to think beyond survival.")
    if state["family_satisfaction"] <= 30:
        facts.append("Trust at home is strained and affects the next decision.")
    if state["creative_fulfillment"] >= 75:
        facts.append("The work feels meaningful enough that walking away has a real emotional cost.")
    if state["social_validation"] <= 30:
        facts.append("Progress is difficult to explain publicly, increasing isolation.")
    while len(facts) < 2:
        facts.append("The trade-off remains real: every available move protects one value by spending another.")
    return facts[:2]


def persona_reaction(session: SimulationSession, record: dict[str, Any]) -> str:
    index = record["node_index"]
    if index not in {0, 1, 3, 5, 7} and not _threshold_crossed(record):
        return ""
    choice = record["choice_text"]
    state = session.world_state
    if session.persona == "Inner Voice":
        return f"I chose to {choice.lower()}, and I can feel which cost I am pretending not to notice."
    if session.persona == "Friend":
        return f"I understand why you chose to {choice.lower()}. Just do not confuse momentum with proof that the pressure is sustainable."
    if session.persona == "Mentor":
        return f"What does choosing to {choice.lower()} protect that the safer option cannot, and what obligation did it create?"
    if session.persona == "Partner":
        return f"I support the reason behind this choice, but stress is at {state['stress']}; our shared plan has to include that cost."
    return f"I see why you chose to {choice.lower()}, but stability and family trust are part of the decision too, not enemies of it."


def cascade_for(session: SimulationSession, record: dict[str, Any]) -> dict[str, str] | None:
    index = record["node_index"]
    if index not in {2, 5, 7} or not session.history:
        return None
    source_index = 0 if index in {2, 5} else min(3, len(session.history) - 1)
    source = session.history[source_index]
    labels = {2: "A small echo", 5: "The delayed consequence", 7: "The final payoff"}
    return {
        "label": labels[index],
        "memory": f"In {source['month_label']}, you chose: {source['choice_text']}",
        "effect": "That decision changed the constraints and obligations shaping this moment.",
    }


def build_report(session: SimulationSession) -> dict[str, Any]:
    state = session.world_state
    risk_count = sum(1 for item in session.history if item["delta"].get("stress", 0) >= 7)
    structure_count = sum(1 for item in session.history if item["delta"].get("financial_security", 0) >= 5)
    meaning_count = sum(1 for item in session.history if item["delta"].get("creative_fulfillment", 0) >= 5)
    if meaning_count > structure_count:
        archetype = "Meaning Builder"
    elif structure_count > meaning_count:
        archetype = "Practical Architect"
    else:
        archetype = "Measured Explorer"
    return {
        "archetype": archetype,
        "summary": (
            f"You made {meaning_count} meaning-protecting moves, {structure_count} stabilizing moves, "
            f"and {risk_count} high-pressure moves while testing {session.chosen_path}."
        ),
        "honest_mirror": (
            f"Your choices show that {session.chosen_path} is attractive only when it can become livable. "
            f"You did not simply choose courage or safety; you repeatedly negotiated between identity, money, and relationships. "
            f"The causal record matters: {', '.join(session.facts[-3:]) or 'you kept options open'}. "
            f"Your next real-world experiment should test those obligations without treating this simulation as a prediction."
        ),
        "world_state": copy.deepcopy(state),
        "facts": session.facts,
        "obligations": session.obligations,
        "model": MODEL_ID,
    }


def environment_image(session: SimulationSession) -> str:
    state = environment_state(session.world_state)
    path = Path(__file__).parent / "assets" / "environments"
    return str(path / f"{session.environment_category}_{state}.png")


def environment_state(state: dict[str, int]) -> str:
    wellbeing = (
        state["financial_security"]
        + state["creative_fulfillment"]
        + state["social_validation"]
        + state["family_satisfaction"]
        + (100 - state["stress"])
    ) / 5
    if state["stress"] >= 82 or state["financial_security"] <= 18 or wellbeing < 38:
        return "struggling"
    if wellbeing >= 67 and state["stress"] <= 55:
        return "thriving"
    return "stable"


def infer_environment(path: str) -> str:
    text = path.lower()
    mapping = (
        (("artist", "art", "music", "design", "film", "creative", "writer"), "studio_creative"),
        (("startup", "founder", "business"), "startup_chaotic"),
        (("phd", "mtech", "college", "study", "masters", "research"), "campus_academic"),
        (("doctor", "medical", "neet", "hospital"), "medical_clinical"),
        (("corporate", "manager", "consulting", "mba"), "corporate"),
    )
    for words, category in mapping:
        if any(word in text for word in words):
            return category
    return "tech_office"


def derive_initial_world_state(dilemma: str, calibration: str) -> dict[str, int]:
    state = {
        "financial_security": 58,
        "creative_fulfillment": 58,
        "social_validation": 50,
        "stress": 42,
        "family_satisfaction": 50,
    }
    text = f"{dilemma} {calibration}".lower()
    if any(word in text for word in ("rent", "loan", "salary", "money", "saving", "fees")):
        state["financial_security"] -= 13
        state["stress"] += 9
    if any(word in text for word in ("family", "parent", "approval", "relatives")):
        state["family_satisfaction"] -= 11
        state["stress"] += 6
    if any(word in text for word in ("passion", "meaning", "creative", "research", "freedom")):
        state["creative_fulfillment"] += 10
    if any(word in text for word in ("offer", "admitted", "selected", "client", "revenue")):
        state["social_validation"] += 8
        state["stress"] -= 3
    return {key: _clamp(value) for key, value in state.items()}


def _consume_or_build(session: SimulationSession, index: int) -> dict[str, Any]:
    fallback = build_node(session, index, use_llm=False)
    context = compact_context(session)
    future = session.pending_nodes.pop(index, None)
    if future and future.done():
        try:
            node = validate_node(future.result(), fallback, context)
        except Exception:
            node = fallback
    else:
        node = fallback
    session.generated_nodes[index] = node
    return node


def _generate_node_with_hf(context: dict[str, Any], index: int) -> Any:
    token = os.getenv("HF_TOKEN")
    try:
        from huggingface_hub import InferenceClient

        client = InferenceClient(model=MODEL_ID, token=token, timeout=12)
        prompt = {
            "task": "Generate one LifeChoice Simulator decision node as strict JSON.",
            "rules": [
                "Exactly three materially different choices.",
                "Each choice must create a fact and use all five integer delta keys from -15 to 15.",
                "Respect metric constraints and causal facts. Never contradict closed options.",
                "No advice, diagnosis, certainty, or prediction.",
            ],
            "month": MONTHS[index],
            "theme": THEMES[index],
            "context": context,
            "schema": {
                "scenario": "string",
                "choices": [
                    {
                        "text": "string",
                        "delta": {key: 0 for key in METRICS},
                        "facts_created": ["string"],
                        "obligations": ["string"],
                        "closed_options": ["string"],
                    }
                ],
            },
        }
        response = client.chat_completion(
            messages=[{"role": "user", "content": json.dumps(prompt, ensure_ascii=True)}],
            max_tokens=850,
            temperature=0.55,
        )
        text = response.choices[0].message.content
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        return json.loads(match.group(0)) if match else None
    except Exception:
        return None


def _custom_choice(node: dict[str, Any], text: str) -> dict[str, Any]:
    totals = {key: 0 for key in METRICS}
    for choice in node["choices"]:
        for key in METRICS:
            totals[key] += int(choice["delta"].get(key, 0))
    return {
        "text": text[:150],
        "delta": {key: round(value / len(node["choices"])) for key, value in totals.items()},
        "facts_created": [f"custom_choice_{_slug(text)[:40]}"],
        "obligations": ["review_custom_choice_consequences"],
        "closed_options": [],
    }


def _characters(chosen: str, unchosen: str) -> dict[str, dict[str, str]]:
    return {
        "family": {"name": "Family", "context": f"Wants {chosen} to have a credible safety floor."},
        "friend": {"name": "Friend", "context": f"Chose {unchosen} and provides a living comparison."},
        "mentor": {"name": "Mentor", "context": f"Five years ahead on {chosen}, including its difficult middle."},
    }


def _threshold_crossed(record: dict[str, Any]) -> bool:
    state = record["world_state_after"]
    return state["stress"] >= 80 or state["financial_security"] <= 20 or state["family_satisfaction"] <= 25


def _delta(financial: int, creative: int, social: int, stress: int, family: int) -> dict[str, int]:
    return dict(
        financial_security=financial,
        creative_fulfillment=creative,
        social_validation=social,
        stress=stress,
        family_satisfaction=family,
    )


def _normalize_delta(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        value = {}
    return {key: max(-15, min(15, int(value.get(key, 0)))) for key in METRICS}


def _clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_slug(str(item))[:60] for item in value[:3] if str(item).strip()]


def _merge_unique(target: list[str], values: list[str], limit: int) -> None:
    for value in values:
        if value and value not in target:
            target.append(value)
    del target[:-limit]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _label(value: str) -> str:
    cleaned = re.sub(r"^(?:i am |i'm |should i |choose |between )", "", value.strip(), flags=re.IGNORECASE)
    return " ".join(word if word.isupper() else word.capitalize() for word in cleaned.strip(" ?.,").split())


def _clamp(value: int) -> int:
    return max(0, min(100, int(value)))
