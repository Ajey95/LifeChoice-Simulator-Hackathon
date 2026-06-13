# Build Small Hackathon Compliance

Verified on June 13, 2026.

| Requirement | Status | Evidence |
|---|---|---|
| Use a model under 32B | Complete | Runtime model is `Qwen/Qwen2.5-7B-Instruct` at 7.616B parameters |
| Keep every fallback under 32B | Complete | No secondary model is configured; fallback behavior is deterministic Python |
| Every model is under 32B | Complete | Hub metadata: 7,615,616,512 parameters; `MODEL_MANIFEST.json`; compliance tests |
| Deploy as Gradio Space | Blocked externally | Gradio app and guarded deploy script are complete |
| Host under `build-small-hackathon` | Blocked externally | `Ajeya95` lacks an active writable CLI login/organization Space-creation permission |
| Public without local setup | Pending Space deployment | Space frontmatter, dependencies, and deterministic no-token mode are complete |
| Public demo video | Complete | `docs/lifechoice-demo.mp4`, publicly served from GitHub |
| Public social media post | Blocked externally | Final copy is in `docs/social-post.md`; installed connectors cannot publish |
| Demo video link in README | Complete | README links the public GitHub-hosted MP4 |
| Social post link in README | Pending publication | Placeholder remains explicit |
| Hackathon frontmatter tags | Complete | README YAML frontmatter |
| Short top description | Complete | First paragraph under title |
| Screenshots/GIFs | Complete | Four browser-verified screenshots |
| Architecture diagram image | Complete | `docs/architecture.svg` |
| Built with Codex section | Complete | README section |
| Codex-attributed commits | Complete | Commits `6929152` and `a340a52` |
| AI safety/disclaimer | Complete | UI and README |
| Explain why not a chatbot | Complete | README architecture explanation |
| Models and stack documented | Complete | README and model manifest |
| Test full Space incognito | Pending Space deployment | Full local browser flow verified; public Space cannot yet exist under target org |
| Verify no model violates rule | Complete | Automated source scan and manifest tests |
| Target requested categories | Complete | README lists Thousand Token Wood, Best Agent, Best Demo, OpenAI Prize |
| Modal credits | Not targeted | No claim made |
| Off Brand | Not targeted | Custom UI exists, but no category claim made |
| Tiny Titan | Not targeted | 7.616B model, so no claim made |
| OpenBMB | Not targeted | No MiniCPM claim |
| NVIDIA | Not targeted | No Nemotron claim |

## Verification Commands

```bash
pytest -q
python scripts/deploy_space.py
```

The deployment command intentionally refuses to use any Hub identity other than `Ajeya95`.
