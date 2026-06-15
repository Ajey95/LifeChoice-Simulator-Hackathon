from __future__ import annotations

import base64
import html
import json
import mimetypes
from functools import lru_cache
from pathlib import Path
from typing import Any

import gradio as gr

from lifechoice_engine import (
    METRICS,
    MODEL_ID,
    SimulationSession,
    choose,
    current_node,
    character_expression,
    environment_image,
    environment_state,
    prefetch_node,
    split_dilemma,
    start_session,
)

ROOT = Path(__file__).parent
PERSONA_ASSETS = {
    "Family": ROOT / "assets" / "personas" / "family.webp",
    "Friend": ROOT / "assets" / "personas" / "friend.webp",
    "Mentor": ROOT / "assets" / "personas" / "mentor.webp",
    "Partner": ROOT / "assets" / "personas" / "friend.webp",
    "Inner Voice": ROOT / "assets" / "personas" / "mentor.webp",
}

CSS = """
:root {
  --night: #070a12;
  --panel: rgba(9, 13, 24, .90);
  --line: rgba(255, 255, 255, .14);
  --cream: #fff7df;
  --muted: #bbb7aa;
  --gold: #ffc857;
  --coral: #ff6b5f;
  --cyan: #5ce1e6;
  --green: #74e59b;
}
* { box-sizing: border-box; }
body, .gradio-container {
  background:
    radial-gradient(circle at 12% -8%, rgba(65, 71, 150, .34), transparent 32rem),
    linear-gradient(180deg, #11162a 0%, var(--night) 48%, #05070c 100%) !important;
  color: var(--cream) !important;
}
.gradio-container {
  max-width: 1180px !important;
  padding: 22px 22px 34px !important;
  font-family: Inter, ui-sans-serif, system-ui, sans-serif !important;
}
footer { display: none !important; }
.app-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin: 5px 2px 18px;
}
.brand-lockup h1 {
  color: #fff !important;
  font-family: "Arial Black", Impact, sans-serif;
  font-size: clamp(2rem, 6vw, 4.7rem);
  line-height: .84;
  letter-spacing: -.075em;
  margin: 7px 0 9px;
  text-transform: uppercase;
}
.brand-lockup h1 span { color: var(--gold); }
.brand-lockup p { color: var(--muted) !important; margin: 0; max-width: 670px; }
.eyebrow {
  color: var(--cyan) !important;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: .72rem;
  font-weight: 800;
  letter-spacing: .14em;
  text-transform: uppercase;
}
.model-chip {
  border: 1px solid rgba(92, 225, 230, .4);
  border-radius: 999px;
  color: var(--cyan);
  flex: 0 0 auto;
  font: 700 .72rem ui-monospace, monospace;
  padding: 9px 12px;
}
.setup-card {
  background: linear-gradient(145deg, rgba(22, 27, 48, .98), rgba(8, 11, 21, .98));
  border: 1px solid var(--line);
  border-radius: 22px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, .36);
  overflow: hidden;
  padding: 10px;
}
.setup-intro {
  min-height: 100%;
  padding: 26px 22px;
  background:
    linear-gradient(180deg, rgba(7, 10, 18, .08), rgba(7, 10, 18, .92)),
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='80' height='80'%3E%3Cpath d='M0 40h80M40 0v80' stroke='%23ffffff' stroke-opacity='.035'/%3E%3C/svg%3E");
  border-radius: 15px;
}
.setup-intro h2 {
  color: #fff !important;
  font-family: "Arial Black", Impact, sans-serif;
  font-size: clamp(1.8rem, 4vw, 3.2rem);
  letter-spacing: -.05em;
  line-height: .95;
  margin: 24px 0 14px;
  text-transform: uppercase;
}
.setup-intro p { color: var(--muted) !important; line-height: 1.65; }
.feature-list { display: grid; gap: 11px; margin-top: 26px; }
.feature {
  align-items: center;
  border-top: 1px solid rgba(255,255,255,.09);
  color: #ddd8ca;
  display: flex;
  font-size: .88rem;
  gap: 10px;
  padding-top: 11px;
}
.feature b { color: var(--gold); font: 800 .72rem ui-monospace, monospace; }
.form-panel { padding: 18px 14px 12px; }
.gradio-container label span { color: #d9d5c8 !important; font-weight: 700 !important; }
.gradio-container textarea,
.gradio-container input {
  color: #fff !important;
}
.gradio-container .block {
  border-color: rgba(255,255,255,.12) !important;
}
#begin-button, #commit-button {
  background: linear-gradient(135deg, var(--gold), #ff9f43) !important;
  border: 0 !important;
  box-shadow: 0 10px 30px rgba(255, 159, 67, .22);
  color: #17120a !important;
  font-family: "Arial Black", Impact, sans-serif !important;
  letter-spacing: .04em;
  min-height: 50px;
  text-transform: uppercase;
}
#begin-button:hover, #commit-button:hover { filter: brightness(1.08); transform: translateY(-1px); }
.microcopy { color: #8f8b80 !important; font-size: .75rem; line-height: 1.5; margin: 9px 2px 0; }
.game-frame {
  aspect-ratio: 16 / 9;
  background: #111;
  border: 1px solid rgba(255,255,255,.18);
  border-radius: 22px;
  box-shadow: 0 26px 90px rgba(0,0,0,.52);
  isolation: isolate;
  min-height: 530px;
  overflow: hidden;
  position: relative;
}
.world-bg {
  background-position: center;
  background-size: cover;
  filter: saturate(.9) contrast(1.04);
  inset: 0;
  position: absolute;
  transform: scale(1.015);
  z-index: -3;
}
.world-shade {
  background:
    linear-gradient(90deg, rgba(3,5,10,.88) 0%, rgba(3,5,10,.34) 57%, rgba(3,5,10,.72) 100%),
    linear-gradient(0deg, rgba(3,5,10,.94) 0%, transparent 38%, rgba(3,5,10,.25) 100%);
  inset: 0;
  position: absolute;
  z-index: -2;
}
.scanlines {
  background: repeating-linear-gradient(0deg, transparent 0, transparent 3px, rgba(0,0,0,.08) 4px);
  inset: 0;
  pointer-events: none;
  position: absolute;
  z-index: 5;
}
.stage-top {
  align-items: flex-start;
  display: flex;
  justify-content: space-between;
  padding: clamp(16px, 3vw, 28px);
}
.scenario-card {
  backdrop-filter: blur(12px);
  background: var(--panel);
  border: 1px solid rgba(255,255,255,.17);
  border-left: 4px solid var(--gold);
  border-radius: 6px 16px 16px 6px;
  box-shadow: 0 18px 55px rgba(0,0,0,.34);
  max-width: 64%;
  padding: clamp(15px, 2.5vw, 25px);
}
.scene-meta {
  color: var(--cyan);
  font: 800 .68rem ui-monospace, monospace;
  letter-spacing: .12em;
  text-transform: uppercase;
}
.scenario-card h2 {
  color: #fff !important;
  font-family: "Arial Black", Impact, sans-serif;
  font-size: clamp(1.25rem, 3vw, 2.15rem);
  letter-spacing: -.035em;
  line-height: 1;
  margin: 9px 0 12px;
  text-transform: uppercase;
}
.scenario-card p { color: #f0ecdf !important; font-size: clamp(.87rem, 1.5vw, 1rem); line-height: 1.58; margin: 0; }
.source-line { color: #8f8b80; display: block; font: .64rem ui-monospace, monospace; margin-top: 14px; }
.hud {
  backdrop-filter: blur(10px);
  background: rgba(7,10,18,.84);
  border: 1px solid rgba(255,255,255,.14);
  border-radius: 14px;
  min-width: 210px;
  padding: 13px;
  width: 25%;
}
.hud-title { color: var(--gold); font: 900 .68rem ui-monospace, monospace; letter-spacing: .12em; margin-bottom: 10px; }
.metric-row { margin: 8px 0; }
.metric-label { color: #d6d2c7; display: flex; font: 700 .62rem ui-monospace, monospace; justify-content: space-between; text-transform: uppercase; }
.metric-track { background: rgba(255,255,255,.11); height: 5px; margin-top: 5px; overflow: hidden; }
.metric-fill { background: linear-gradient(90deg, var(--cyan), var(--green)); height: 100%; }
.metric-row.stress .metric-fill { background: linear-gradient(90deg, #ffb347, var(--coral)); }
.stage-bottom { bottom: 0; display: flex; justify-content: space-between; left: 0; padding: 0 27px 24px; position: absolute; right: 0; }
.persona-bubble {
  align-self: flex-end;
  backdrop-filter: blur(10px);
  background: rgba(10,13,22,.91);
  border: 1px solid rgba(255,255,255,.16);
  border-radius: 14px;
  display: flex;
  gap: 12px;
  max-width: 58%;
  padding: 10px 13px;
}
.persona-bubble img { border: 2px solid var(--cyan); border-radius: 8px; height: 58px; object-fit: cover; width: 58px; }
.persona-copy b { color: var(--cyan); display: block; font: 800 .68rem ui-monospace, monospace; letter-spacing: .08em; text-transform: uppercase; }
.persona-copy p { color: #eee9dc !important; font-size: .8rem; line-height: 1.4; margin: 5px 0 0; }
.player-wrap { align-items: flex-end; display: flex; gap: 12px; }
.state-pill {
  background: rgba(7,10,18,.82);
  border: 1px solid rgba(255,255,255,.15);
  border-radius: 999px;
  color: var(--cream);
  font: 800 .63rem ui-monospace, monospace;
  margin-bottom: 8px;
  padding: 7px 10px;
  text-transform: uppercase;
}
.player-sprite {
  background-repeat: no-repeat;
  background-size: 400% 100%;
  filter: drop-shadow(0 16px 9px rgba(0,0,0,.55));
  height: 142px;
  image-rendering: pixelated;
  width: 126px;
}
.cascade-banner {
  animation: slide-in .28s ease-out;
  background: linear-gradient(90deg, rgba(255,107,95,.96), rgba(118,52,83,.94));
  border: 1px solid rgba(255,255,255,.2);
  box-shadow: 0 10px 35px rgba(0,0,0,.35);
  color: #fff;
  left: 50%;
  max-width: 70%;
  padding: 10px 18px;
  position: absolute;
  text-align: center;
  top: 49%;
  transform: translate(-50%, -50%);
  z-index: 4;
}
.loading-stage {
  align-items: center;
  background:
    radial-gradient(circle at 50% 35%, rgba(92,225,230,.10), transparent 30%),
    linear-gradient(145deg, #11182a, #070a12);
  display: flex;
  flex-direction: column;
  gap: 14px;
  justify-content: center;
  min-height: 530px;
  text-align: center;
}
.loading-orbit {
  animation: orbit 1.05s linear infinite;
  border: 3px solid rgba(255,255,255,.11);
  border-radius: 50%;
  border-top-color: var(--gold);
  height: 52px;
  width: 52px;
}
.loading-stage h2 { color: #fff !important; font: 1.7rem "Arial Black", Impact, sans-serif; margin: 0; text-transform: uppercase; }
.loading-stage p { color: var(--muted) !important; margin: 0; max-width: 460px; }
.loading-steps { color: var(--cyan); font: 700 .67rem ui-monospace, monospace; letter-spacing: .09em; text-transform: uppercase; }
.cascade-banner b { display: block; font: 900 .7rem ui-monospace, monospace; letter-spacing: .12em; text-transform: uppercase; }
.cascade-banner span { font-size: .76rem; }
.report-card {
  backdrop-filter: blur(15px);
  background: rgba(7,10,18,.94);
  border: 1px solid rgba(255,255,255,.18);
  border-top: 4px solid var(--gold);
  border-radius: 16px;
  inset: 6%;
  overflow: auto;
  padding: clamp(20px, 4vw, 42px);
  position: absolute;
  z-index: 4;
}
.report-card h2 { color: var(--gold) !important; font: clamp(1.8rem, 5vw, 3.7rem)/.95 "Arial Black", Impact, sans-serif; letter-spacing: -.055em; margin: 8px 0 18px; text-transform: uppercase; }
.report-card p { color: #e7e2d5 !important; line-height: 1.62; max-width: 850px; }
.report-card details { color: #aaa59a; margin-top: 18px; }
.report-card pre { white-space: pre-wrap; }
.choices-shell {
  background: rgba(8,11,20,.78);
  border: 1px solid rgba(255,255,255,.12);
  border-radius: 18px;
  margin-top: 14px;
  padding: 14px;
}
.choice-heading { align-items: center; display: flex; justify-content: space-between; margin: 2px 2px 11px; }
.choice-heading b { color: #fff; font-family: "Arial Black", Impact, sans-serif; letter-spacing: .02em; text-transform: uppercase; }
.choice-heading span { color: #827e74; font: .66rem ui-monospace, monospace; }
#choice-cards label {
  background: rgba(255,255,255,.035) !important;
  border: 1px solid rgba(255,255,255,.12) !important;
  border-radius: 10px !important;
  margin: 6px 0 !important;
  padding: 11px 12px !important;
  transition: .16s ease;
}
#choice-cards label:hover { background: rgba(255,200,87,.08) !important; border-color: rgba(255,200,87,.55) !important; transform: translateX(3px); }
#choice-cards label:has(input:checked) { background: rgba(255,200,87,.13) !important; border-color: var(--gold) !important; }
#path-options label, #persona-options label {
  background: rgba(255,255,255,.045) !important;
  border: 1px solid rgba(255,255,255,.11) !important;
  color: #e6e1d4 !important;
}
#path-options label:has(input:checked), #persona-options label:has(input:checked) {
  background: rgba(255,200,87,.12) !important;
  border-color: rgba(255,200,87,.7) !important;
}
#detected-paths { color: var(--cyan) !important; opacity: .74; }
#reset-button {
  background: transparent !important;
  border: 1px solid rgba(255,255,255,.15) !important;
  color: #aaa59a !important;
  margin-top: 11px;
}
#reset-button:hover { border-color: rgba(255,200,87,.45) !important; color: var(--gold) !important; }
@keyframes slide-in { from { opacity: 0; transform: translate(-50%, -42%); } to { opacity: 1; transform: translate(-50%, -50%); } }
@keyframes orbit { to { transform: rotate(360deg); } }
@media (max-width: 760px) {
  .gradio-container { padding: 12px !important; }
  .app-header { align-items: flex-start; flex-direction: column; }
  .game-frame { aspect-ratio: auto; min-height: 660px; }
  .stage-top { display: block; }
  .scenario-card { max-width: 100%; }
  .hud { margin-top: 10px; width: 100%; }
  .metric-row { display: inline-block; margin: 6px 1.2%; width: 46%; }
  .stage-bottom { padding: 0 15px 17px; }
  .persona-bubble { max-width: 74%; }
  .player-sprite { height: 105px; width: 93px; }
  .state-pill { display: none; }
}
"""


@lru_cache(maxsize=32)
def image_data_uri(path_text: str) -> str:
    path = Path(path_text)
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def parse_paths(dilemma: str) -> tuple[gr.Radio, str]:
    path_a, path_b = split_dilemma(dilemma)
    return (
        gr.Radio(choices=[(path_a, "A"), (path_b, "B")], value="A", label="Choose the future to enter"),
        f"PATHS DETECTED: {path_a.upper()} / {path_b.upper()}",
    )


def begin(dilemma: str, chosen_key: str, calibration: str, persona: str):
    if len(dilemma.strip()) < 5:
        raise gr.Error("Enter a real dilemma first.")
    if not calibration.strip():
        raise gr.Error("Add one concrete pressure, constraint, or proof point.")
    yield (
        None,
        loading_html(dilemma, calibration),
        gr.Radio(choices=[], value=None),
        "",
        gr.Group(visible=False),
        gr.Column(visible=False),
        gr.Group(visible=False),
        gr.Group(visible=True),
        gr.Button(interactive=False, value="Building your world..."),
    )
    session = start_session(dilemma, chosen_key or "A", calibration, persona, prefetch=False)
    node = current_node(session)
    yield (
        session,
        game_html(session, node),
        gr.Radio(choices=_choice_options(node), value=None, label="Choose your move"),
        "",
        gr.Group(visible=False),
        gr.Column(visible=True),
        gr.Group(visible=False),
        gr.Group(visible=True),
        gr.Button(interactive=True, value="Commit choice"),
    )
    prefetch_node(session, 1)


def make_choice(session: SimulationSession, choice_value: str | None, custom_choice: str):
    if session is None:
        raise gr.Error("Start a simulation first.")
    custom = custom_choice.strip()
    if not custom and choice_value is None:
        raise gr.Error("Choose an option or write your own move.")
    result = choose(session, int(choice_value or 0), custom)
    if result["complete"]:
        return (
            session,
            game_html(
                session,
                reaction=result.get("reaction", ""),
                cascade=result.get("cascade"),
                report=result["report"],
            ),
            gr.Radio(choices=[], value=None),
            "",
            gr.Group(visible=True),
            gr.Column(visible=False),
            gr.Group(visible=False),
            gr.Button(interactive=False),
        )
    node = result["node"]
    return (
        session,
        game_html(
            session,
            node,
            reaction=result.get("reaction", ""),
            cascade=result.get("cascade"),
        ),
        gr.Radio(choices=_choice_options(node), value=None, label="Choose your move"),
        "",
        gr.Group(visible=False),
        gr.Column(visible=True),
        gr.Group(visible=False),
        gr.Button(interactive=True),
    )


def reset():
    return (
        None,
        "",
        gr.Radio(choices=[], value=None),
        "",
        gr.Group(visible=False),
        gr.Column(visible=False),
        gr.Group(visible=True),
        gr.Group(visible=False),
        gr.Button(interactive=True),
    )


def loading_html(dilemma: str, calibration: str) -> str:
    path_a, path_b = split_dilemma(dilemma)
    detail = " ".join(calibration.split())[:150]
    return f"""
    <div class="game-frame loading-stage">
      <div class="loading-orbit"></div>
      <div class="eyebrow">Building a personalized causal world</div>
      <h2>{html.escape(path_a)} / {html.escape(path_b)}</h2>
      <p>Connecting your real constraint to the opening scene: {html.escape(detail)}</p>
      <div class="loading-steps">Calibrating state / placing consequences / preparing choices</div>
    </div>
    """


def game_html(
    session: SimulationSession,
    node: dict[str, Any] | None = None,
    reaction: str = "",
    cascade: dict[str, str] | None = None,
    report: dict[str, Any] | None = None,
) -> str:
    state = environment_state(session.world_state)
    expression = character_expression(session.world_state)
    background = image_data_uri(environment_image(session))
    sprite = image_data_uri(str(ROOT / "assets" / "characters" / "character.png"))
    portrait = image_data_uri(str(PERSONA_ASSETS[session.persona]))
    sprite_position = {"neutral": "0%", "stressed": "33.333%", "confident": "66.666%"}[expression]
    node = node or {
        "month_label": "Future report",
        "node_theme": "reflection",
        "scenario": "",
        "generation_source": "causal ledger",
    }

    cascade_markup = ""
    if cascade:
        cascade_markup = f"""
        <div class="cascade-banner">
          <b>{html.escape(cascade['label'])}</b>
          <span>{html.escape(cascade['memory'])} {html.escape(cascade['effect'])}</span>
        </div>
        """

    persona_text = reaction or (
        f"I'll stay with you through this version of {session.chosen_path}. "
        "Pay attention to what each choice costs, not only what it promises."
    )
    persona_markup = f"""
      <div class="persona-bubble">
        <img src="{portrait}" alt="{html.escape(session.persona)}">
        <div class="persona-copy">
          <b>{html.escape(session.persona)}</b>
          <p>{html.escape(persona_text)}</p>
        </div>
      </div>
    """

    report_markup = report_html(report) if report else ""
    return f"""
    <div class="game-frame">
      <div class="world-bg" style="background-image:url('{background}')"></div>
      <div class="world-shade"></div>
      <div class="stage-top">
        <section class="scenario-card">
          <div class="scene-meta">{html.escape(node['month_label'])} / {html.escape(node['node_theme'])}</div>
          <h2>{html.escape(session.chosen_path)}</h2>
          <p>{html.escape(node['scenario'])}</p>
          <small class="source-line">SOURCE: {html.escape(node.get('generation_source', 'deterministic')).upper()}</small>
        </section>
        {metrics_html(session)}
      </div>
      {cascade_markup}
      <div class="stage-bottom">
        {persona_markup}
        <div class="player-wrap">
          <span class="state-pill">World: {state} / You: {expression}</span>
          <div class="player-sprite" style="background-image:url('{sprite}');background-position:{sprite_position} 0"></div>
        </div>
      </div>
      {report_markup}
      <div class="scanlines"></div>
    </div>
    """


def metrics_html(session: SimulationSession) -> str:
    labels = {
        "financial_security": "Financial",
        "creative_fulfillment": "Fulfillment",
        "social_validation": "Validation",
        "stress": "Stress",
        "family_satisfaction": "Family",
    }
    rows = []
    for key in METRICS:
        value = session.world_state[key]
        rows.append(
            f"""
            <div class="metric-row {'stress' if key == 'stress' else ''}">
              <div class="metric-label"><span>{labels[key]}</span><span>{value}</span></div>
              <div class="metric-track"><div class="metric-fill" style="width:{value}%"></div></div>
            </div>
            """
        )
    return f"<aside class='hud'><div class='hud-title'>LIVE WORLD STATE</div>{''.join(rows)}</aside>"


def report_html(report: dict[str, Any]) -> str:
    ledger = html.escape(
        json.dumps(
            {"facts": report["facts"], "obligations": report["obligations"]},
            indent=2,
        )
    )
    return f"""
    <section class="report-card">
      <div class="eyebrow">Simulation complete / causal reflection</div>
      <h2>{html.escape(report['archetype'])}</h2>
      <p>{html.escape(report['summary'])}</p>
      <p>{html.escape(report['honest_mirror'])}</p>
      <details><summary>Open the causal ledger</summary><pre>{ledger}</pre></details>
    </section>
    """


def _choice_options(node: dict[str, Any]) -> list[tuple[str, str]]:
    return [(choice["text"], str(index)) for index, choice in enumerate(node["choices"])]


theme = gr.themes.Base(
    primary_hue="orange",
    neutral_hue="slate",
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui"],
).set(
    body_background_fill="#070a12",
    block_background_fill="#0d1120",
    block_border_color="rgba(255,255,255,.12)",
    input_background_fill="#080b15",
    input_border_color="rgba(255,255,255,.14)",
)

with gr.Blocks(css=CSS, theme=theme, title="LifeChoice Simulator") as demo:
    session_state = gr.State()
    gr.HTML(
        f"""
        <header class="app-header">
          <div class="brand-lockup">
            <div class="eyebrow">A causal future simulator</div>
            <h1>Life<span>Choice</span></h1>
            <p>Enter one road not taken. Make decisions inside it. Watch the world remember.</p>
          </div>
          <div class="model-chip">{MODEL_ID} / 7B</div>
        </header>
        """
    )

    with gr.Group(elem_classes="setup-card") as setup_group:
        with gr.Row(equal_height=True):
            with gr.Column(scale=5):
                gr.HTML(
                    """
                    <section class="setup-intro">
                      <div class="eyebrow">New simulation</div>
                      <h2>Try the future<br>before it happens.</h2>
                      <p>This is not a chatbot. It is an eight-node causal simulation with persistent metrics, delayed consequences, and a world that changes with your decisions.</p>
                      <div class="feature-list">
                        <div class="feature"><b>01</b> Immediate first scene</div>
                        <div class="feature"><b>02</b> Choices produce distinct state changes</div>
                        <div class="feature"><b>03</b> Your persona remembers what happened</div>
                      </div>
                    </section>
                    """
                )
            with gr.Column(scale=6, elem_classes="form-panel"):
                dilemma = gr.Textbox(
                    label="The fork in the road",
                    placeholder="Artist vs Software Engineer",
                    value="MTech vs Software Job",
                )
                path_choice = gr.Radio(
                    choices=[("MTech", "A"), ("Software Job", "B")],
                    value="A",
                    label="Choose the future to enter",
                    elem_id="path-options",
                )
                detected = gr.Markdown(
                    "PATHS DETECTED: MTECH / SOFTWARE JOB",
                    elem_classes="eyebrow",
                    elem_id="detected-paths",
                )
                calibration = gr.Textbox(
                    label="What makes this decision real?",
                    placeholder="A pressure, deadline, responsibility, or proof point...",
                    value="My family needs income soon, but a professor is already interested in my research.",
                    lines=2,
                )
                persona = gr.Radio(
                    choices=["Family", "Friend", "Mentor", "Partner", "Inner Voice"],
                    value="Mentor",
                    label="Choose the voice that follows you",
                    elem_id="persona-options",
                )
                begin_btn = gr.Button("Enter this future", variant="primary", elem_id="begin-button")
                gr.HTML(
                    "<p class='microcopy'>Reflective simulation only. Not medical, legal, financial, or professional advice. The first scene starts immediately while later scenes prepare in the background.</p>"
                )

    with gr.Group(visible=False) as game_group:
        game_board = gr.HTML()
        with gr.Column(visible=False, elem_classes="choices-shell") as play_column:
            gr.HTML("<div class='choice-heading'><b>What do you do?</b><span>YOUR DECISION CHANGES THE STATE</span></div>")
            choices = gr.Radio(choices=[], show_label=False, elem_id="choice-cards")
            custom = gr.Textbox(
                label="Or make your own move",
                placeholder="Describe one specific action...",
                lines=1,
            )
            choose_btn = gr.Button("Commit choice", variant="primary", elem_id="commit-button")
        with gr.Group(visible=False) as report_group:
            gr.Markdown(
                "The report reflects patterns in your causal ledger. It does not predict your future or tell you what to do."
            )
        reset_btn = gr.Button("Start a different simulation", variant="secondary", elem_id="reset-button")

    dilemma.change(parse_paths, dilemma, [path_choice, detected], show_progress="hidden")
    begin_btn.click(
        begin,
        [dilemma, path_choice, calibration, persona],
        [session_state, game_board, choices, custom, report_group, play_column, setup_group, game_group, choose_btn],
        show_progress="hidden",
    )
    choose_btn.click(
        make_choice,
        [session_state, choices, custom],
        [session_state, game_board, choices, custom, report_group, play_column, setup_group, choose_btn],
    )
    reset_btn.click(
        reset,
        outputs=[session_state, game_board, choices, custom, report_group, play_column, setup_group, game_group, choose_btn],
        show_progress="hidden",
    )

if __name__ == "__main__":
    demo.queue(default_concurrency_limit=8).launch()
