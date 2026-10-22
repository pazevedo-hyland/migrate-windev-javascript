# Contributing

Contributions are welcome through GitHub issues and pull requests.

## The spirit

- The guide covers the **tools** (planner and implementer agents, Git, CI, test machine, packaging) and the **working rules** (the loop, the handoff, ADRs, project memory, "verify before assuming", measurable parity).
- It proposes defaults for TypeScript/Tauri, but every architecture choice remains the reader's, recorded in an ADR. Mark opinions as recommendations, not requirements.
- **Neutral, factual tone**: describe; do not disparage any vendor or tool. State licence and hosting as facts.

## Proposing a change

1. Open an **issue** to discuss the idea.
2. Fork, work on a **branch**, write clear commits (short title).
3. Open a **pull request**; a maintainer reviews in four categories — (1) blocking, (2) parity/accuracy gap, (3) naming/convention, (4) content/cosmetic — and decides.
4. Update `CHANGELOG.md` for notable changes, and `docs/upstream-audit.md` when a chapter's coverage of the upstream guide changes.

## Form and checks

- English Markdown, short sentences, UTF-8, LF line endings; expand abbreviations at first use; link official technical references.
- When you change tool behavior, update `scripts/README.md` and the tests. Run `python3 -m unittest discover -s tests -v` (it also checks relative Markdown links).
- Never contribute customer source, personal data, credentials, real exports or proprietary graphics: use synthetic fixtures. Preserve upstream attribution and license.
- A claim of migration parity needs reproducible evidence, not only generated code.
