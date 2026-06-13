from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from huggingface_hub import HfApi
from huggingface_hub.errors import LocalTokenNotFoundError


ROOT = Path(__file__).resolve().parents[1]
REPO_ID = "build-small-hackathon/LifeChoice-Simulator"
REQUIRED_USER = "Ajeya95"


def main() -> None:
    api = HfApi()
    try:
        identity = api.whoami()
    except LocalTokenNotFoundError:
        raise SystemExit(
            f"No Hugging Face CLI login found. Run `hf auth login` with the {REQUIRED_USER} account."
        ) from None
    username = identity.get("name", "")
    if username.casefold() != REQUIRED_USER.casefold():
        raise SystemExit(
            f"Refusing to deploy as {username or 'an unauthenticated user'}. "
            f"Run `hf auth login` with the {REQUIRED_USER} account."
        )

    organizations = {
        org.get("name", "").casefold(): org.get("roleInOrg", "")
        for org in identity.get("orgs", [])
        if isinstance(org, dict)
    }
    role = organizations.get("build-small-hackathon", "")
    if role not in {"admin", "write", "contributor"}:
        raise SystemExit(
            "Ajeya95 does not have write access to build-small-hackathon. "
            "Ask an organization admin to grant Space creation permission."
        )

    api.create_repo(
        repo_id=REPO_ID,
        repo_type="space",
        space_sdk="gradio",
        private=False,
        exist_ok=True,
    )

    with tempfile.TemporaryDirectory(prefix="lifechoice-space-") as temp:
        bundle = Path(temp)
        for filename in ("app.py", "lifechoice_engine.py", "requirements.txt", "README.md", "MODEL_MANIFEST.json"):
            shutil.copy2(ROOT / filename, bundle / filename)

        shutil.copytree(ROOT / "docs", bundle / "docs")
        shutil.copytree(ROOT / "assets", bundle / "assets")
        api.upload_folder(
            repo_id=REPO_ID,
            repo_type="space",
            folder_path=bundle,
            commit_message="Deploy LifeChoice Simulator from Codex-built repository",
        )

    print(f"https://huggingface.co/spaces/{REPO_ID}")


if __name__ == "__main__":
    main()
