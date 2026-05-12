# wifibuddy — Claude Code Instructions

## Project Overview

**wifibuddy** is a community-tracked database of wifi speeds at public cafes and spaces. Users submit speed test results; the app aggregates and surfaces that data for people looking for a good place to work.

## Spec-Kit Workflow

All features are developed spec-first. Before writing any code:

1. Write (or locate) the spec in `specs/` — see [Spec Format](#spec-format) below
2. Get the spec reviewed/approved before implementation begins
3. Write failing tests that match the spec's acceptance criteria
4. Implement code to make the tests pass
5. Verify all acceptance criteria are met before marking a feature done

**Never skip the spec.** If a task has no spec, write one first.

## Repository Structure

```
wifibuddy/
├── specs/              # Feature specifications (source of truth)
│   └── TEMPLATE.md     # Spec template — copy for each new feature
├── src/                # Application source code
├── tests/              # Test suite (unit, integration, e2e)
├── docs/               # Architecture decisions, API contracts
├── .env.example        # Required env vars (no secrets — commit this)
├── .env                # Actual secrets (never commit — blocked from Claude)
└── .claude/
    └── settings.json   # Claude Code permissions
```

## Spec Format

Each spec in `specs/` must include:

```markdown
# Feature: <name>

## Status
Draft | In Review | Approved | In Progress | Done

## Overview
One paragraph describing what this feature does and why.

## Goals
- Bullet list of what success looks like

## Non-Goals
- Explicit list of what this feature does NOT do

## User Stories
- As a <role>, I want <action> so that <outcome>

## Technical Design
High-level approach: data model changes, API shape, key algorithms.

## Acceptance Criteria
- [ ] Testable, binary pass/fail conditions
- [ ] Each maps directly to a test case

## Open Questions
- Unresolved decisions that need answers before implementation
```

## Development Standards

### Code Quality
- No feature code without a corresponding test
- Tests live in `tests/` mirroring the `src/` structure
- Each PR must include: spec reference, tests, and implementation — no partial work
- Run the full test suite before marking a PR ready for review

### Security
- Secrets go in `.env` only — never hardcoded, never in comments
- `.env` is blocked from Claude reads (enforced via `.claude/settings.json`)
- Use `.env.example` to document required variables without values
- Rotate any secret that was accidentally committed immediately

### Git Hygiene
- Branch from `main` for every feature/fix
- Branch naming: `feat/<spec-slug>`, `fix/<issue-slug>`, `chore/<slug>`
- PRs must reference the spec: "Implements specs/feature-name.md"
- Squash-merge to keep `main` history clean

### No Gold-Plating
- Implement only what the spec's acceptance criteria require
- No speculative abstractions, no "we might need this later" code
- Three similar lines is preferable to a premature helper function

## Secrets Management

Claude cannot read secret files. This is enforced in `.claude/settings.json`.

Blocked from Claude:
- `.env` and all `.env.*` variants
- `secrets/` directory
- `*.pem`, `*.key`, `*.p12`, `*.pfx`, `*.crt` files

To work with secrets yourself:
1. Copy `.env.example` → `.env`
2. Fill in real values in `.env`
3. Never commit `.env` (it is in `.gitignore`)

## Environment Variables

See `.env.example` for all required variables. At minimum:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Primary database connection string |
| `API_KEY_SECRET` | Server-side API signing key |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins |

## Running the Project

```bash
# Install dependencies (add your actual commands here)
# npm install / pip install -r requirements.txt / etc.

# Run tests
# npm test / pytest / etc.

# Start dev server
# npm run dev / python -m uvicorn app:app --reload / etc.
```

Update this section once the tech stack is chosen.

## Asking Claude for Help

- Reference the relevant spec when requesting implementation work
- For exploratory questions, Claude will suggest an approach — confirm before implementation starts
- Claude will not read `.env` or any secrets files — provide env var names (not values) when describing issues
