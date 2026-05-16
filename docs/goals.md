# Stash Goals

## v1 (current)

- [ ] **Smooth onboarding** — minimize prerequisites. Ideally `pip install stash` works with auto-detection of Ollama or guided setup on first run.
- [ ] **Model guidance** — add a quick table in the README showing which models work well, their tradeoffs (speed vs capability), and a recommended default.
- [ ] **Demo GIF** — produce a clean terminal demo using VHS showing the full flow: task input → ReAct stream → plan approval → execution → rule scheduling.
- [ ] **Polish the README** — demo GIF at the top, clearer install instructions, a "quick start" section that gets someone from zero to their first organized folder in under 2 minutes.

## v2

- [ ] **Bring Your Own Key (BYOK)** — allow users to configure OpenAI / Anthropic / etc. as the backend for users who want more capable models but don't have the compute for local LLMs. Ollama remains the default free path.
- [ ] **Name discoverability** — evaluate whether the name "Stash" causes SEO/discoverability issues and consider renaming or adding a distinguishing subtitle before v2 marketing push.

## Long-term

- [ ] Open source launch with community contribution guidelines
- [ ] Plugins / custom tool SDK for power users
- [ ] Cross-platform packaged binary (PyInstaller or similar) so users don't need Python installed at all
