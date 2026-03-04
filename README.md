# GitHub Repository Summarizer

A Flask service that takes a GitHub repository URL and returns a human-readable summary: what it does, what technologies it uses, and how it's structured.

---

## Setup & Run

### Prerequisites
- Python 3.10+
- A [Nebius Token Factory](https://studio.nebius.com/) API key

### 1. Clone / unzip the project

```bash
cd nebius-final
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\Scripts\activate       # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set your API key

```bash
export NEBIUS_API_KEY="your_nebius_api_key_here"
```

### 5. Start the server

```bash
python main.py
```

The server will be available at `http://localhost:8000`.

---

## Usage

### Summarize a repository

```bash
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/psf/requests"}'
```

**Example response:**
```json
{
  "summary": "Requests is a simple, elegant HTTP library for Python that allows users to send HTTP/1.1 requests with minimal effort. It abstracts the complexity of making requests behind a simple API, widely used across the Python ecosystem.",
  "technologies": ["Python", "urllib3", "certifi", "charset-normalizer", "idna"],
  "structure": "Standard Python package layout with source code in src/requests/, tests in tests/, and documentation in docs/. Uses pyproject.toml for packaging."
}
```

### Health check

```bash
curl http://localhost:8000/health
```

---

## API Reference

### `POST /summarize`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `github_url` | string | yes | URL of a public GitHub repository |

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `summary` | string | Human-readable description of what the project does |
| `technologies` | string[] | Main languages, frameworks, and tools |
| `structure` | string | Brief description of the project layout |

**Error response:**
```json
{
  "status": "error",
  "message": "Description of what went wrong"
}
```

---

## Design Decisions

### Model: `meta-llama/Meta-Llama-3.1-70B-Instruct`

Chosen for its strong instruction-following capability (reliably returns JSON), large 128k context window (handles big repos), and availability on Nebius's free tier. The 70B size hits a good balance between quality and speed.

### Repository Content Strategy

Repositories can be huge, so the service uses a tiered content selection approach to stay within a ~40k character context budget:

**Always included:**
- **README** — the single most informative file in any repo; describes purpose, usage, and setup
- **GitHub repo metadata** — description, topics, total file count

**Priority files (fetched first):**
- Manifests & config: `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `Dockerfile`, etc.
- These reveal the tech stack, dependencies, and project type quickly and compactly

**Source files (fill remaining budget):**
- Sorted by path depth (shallower = more important), so top-level modules load before deeply nested utilities
- Each file is capped at 6,000 characters to prevent one large file from consuming the whole budget

**Always skipped:**
- `node_modules/`, `vendor/`, `.git/`, `__pycache__/`, build outputs — irrelevant or huge
- Lock files (`package-lock.json`, `poetry.lock`, etc.) — verbose, low-signal
- Binary & media files (images, fonts, compiled artifacts)
- Generated/minified files (`.min.js`, `.map`, etc.)
- Boilerplate files (`LICENSE`, `.gitignore`, `CHANGELOG`, etc.)

**Directory tree:**
- A compact tree (up to depth 3) is always included to give the LLM structural context even for files whose contents weren't fetched

This approach ensures the LLM always gets the highest-signal content (README + manifests) while using any remaining context budget on actual source code.
