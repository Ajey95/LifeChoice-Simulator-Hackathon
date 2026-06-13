import json
import re
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCAN_EXTENSIONS = {".py", ".json", ".toml", ".yaml", ".yml"}


def test_manifest_contains_only_sub_32b_models():
    manifest = json.loads((ROOT / "MODEL_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["models"]
    assert all(model["parameters_billions"] < 32 for model in manifest["models"])


def test_no_forbidden_runtime_model_names():
    forbidden = (
        "llama-3.3-70b",
        "gpt-4o-mini",
        "gpt-4o",
        "mixtral-8x7b",
        "qwen2.5-32b",
        "qwen2.5-72b",
    )
    hits = []
    for path in ROOT.rglob("*"):
        if (
            path.is_file()
            and path.suffix.lower() in SCAN_EXTENSIONS
            and ".git" not in path.parts
            and path.name != "test_model_compliance.py"
        ):
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for model in forbidden:
                if model in text:
                    hits.append(f"{path.relative_to(ROOT)}: {model}")
    assert not hits, "Forbidden model references found: " + ", ".join(hits)


def test_runtime_model_matches_manifest():
    source = (ROOT / "lifechoice_engine.py").read_text(encoding="utf-8")
    runtime = re.search(r'MODEL_ID = "([^"]+)"', source).group(1)
    manifest = json.loads((ROOT / "MODEL_MANIFEST.json").read_text(encoding="utf-8"))
    assert runtime == manifest["models"][0]["id"]
