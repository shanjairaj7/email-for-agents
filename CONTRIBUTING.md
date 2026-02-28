# Contributing to email-for-agents

Thank you for contributing. This repository is a curated collection of production-ready examples — quality over quantity. Every example should be something a developer can clone, run, and ship.

---

## What we're looking for

**New framework examples** — integrations with agent frameworks not yet covered (AutoGen, Haystack, Semantic Kernel, DSPy, etc.)

**Language ports** — working examples in Go, Ruby, Rust, or other languages using the Commune REST API directly

**Real-world use cases** — patterns that go beyond the basics: multi-step workflows, hybrid email+SMS flows, agent escalation chains, scheduled digests

**Improvements to existing examples** — clearer code, better error handling, updated dependencies, additional comments

---

## What we are not looking for

- Examples that don't run (untested code)
- Hello-world snippets with no context
- Framework comparisons or opinion pieces
- Changes to the core README structure without prior discussion

---

## How to contribute

### 1. Open an issue first (for new examples)

Before writing a full example, open an issue describing:
- What framework or use case you're adding
- What the example will demonstrate
- Whether you're working on it now (so we don't duplicate effort)

For small fixes (typos, dependency updates, broken links), skip the issue and go straight to a PR.

### 2. Fork and clone

```bash
git clone https://github.com/commune-email/email-for-agents.git
cd email-for-agents
```

### 3. Create a branch

```bash
git checkout -b add-haystack-example
```

### 4. Write your example

Follow the conventions of existing examples in this repo:

- **One folder per framework or major use case**: `haystack/`, `autogen/`, etc.
- **Every folder needs a `README.md`** explaining what the example does, how to install, and how to run it
- **Code must run as written** — include a `requirements.txt` or `package.json`, and test it
- **Use environment variables for secrets** — never hardcode API keys
- **Include error handling** — `try/except` or `try/catch` around network calls; at minimum, surface the error clearly
- **Keep it focused** — one example per file, one concept per example

### 5. Example README template

Every example folder should have a `README.md` with at minimum:

```markdown
# <Example Name>

What this example does in one sentence.

## Prerequisites
- Python 3.9+ / Node 18+
- Commune API key (commune.email)
- <any other dependencies>

## Install
pip install -r requirements.txt

## Configure
cp .env.example .env
# Add your COMMUNE_API_KEY

## Run
python main.py

## How it works
Brief explanation of the key moving parts.
```

### 6. Open a pull request

- Title: `add: haystack customer support example` or `fix: update langchain tool signature`
- Description: what the PR adds or fixes, and how you tested it
- Link to the related issue if one exists

---

## Code style

**Python**
- Follow PEP 8
- Use type hints where they add clarity
- Keep functions short and single-purpose
- `requirements.txt` with pinned minor versions (`langchain==0.2.*`)

**TypeScript**
- Strict mode (`"strict": true` in tsconfig)
- Explicit return types on public functions
- `package.json` with pinned minor versions
- ESM modules preferred

**All languages**
- Real comments on non-obvious lines
- No dead code
- `.env.example` alongside any `.env` usage

---

## Dependency policy

- Pin minor versions, not patch: `langchain==0.2.*` not `langchain==0.2.14`
- Do not add dependencies that are not used
- Prefer the official SDK (`commune-mail`, `commune-ai`) over raw HTTP calls unless you're demonstrating the REST API directly

---

## Testing your example

Before opening a PR, verify:

1. Fresh install from scratch: `pip install -r requirements.txt` (or `npm install`) in a clean environment
2. The example runs end-to-end with a real Commune API key
3. The README's "Run" instructions produce the expected output

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License — the same license that covers this repository.

---

Questions? Open an issue or email [hello@commune.email](mailto:hello@commune.email).
