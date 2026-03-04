# GitHub Repository Summariser

A simple Flask service that takes a GitHub repository URL and returns a human-readable summary: what it does, what technologies it uses, and how it's structured.

---

## Setup & Run

### Prerequisites
- Python 3.10+
- A [Nebius Token Factory](https://studio.nebius.com/) API key
- A [GitHub Personal Access Token](https://github.com/settings/tokens) (free, needed to avoid rate limits)

### 1. Git clone & Unzip the project and navigate into it

```
git clone git@github.com:JiwonGigiShin/nebius_final.git
cd nebius_final
```

### 2. Create a virtual environment

A virtual environment keeps this project's dependencies separate from the rest of your computer. You only need to do this once.

**Mac/Linux:**
```
python -m venv .venv
source .venv/bin/activate
```

**Windows:**
```
python -m venv .venv
.venv\Scripts\activate
```

You'll know it's working when you see `(.venv)` at the start of your terminal line.

### 3. Install dependencies

```
pip install -r requirements.txt
```

### 4. Set your API keys

You need to set two API keys before starting the server. Think of these as passwords that allow the app to talk to external services. You need to do this every time you open a new terminal window.

**Nebius API key** (for the AI summarization):
- Log in to [Nebius Token Factory](https://studio.nebius.com), click your profile picture (top right) → **API Keys** → **Create API Key**

**GitHub token** (to avoid hitting GitHub's rate limit of 60 requests/hour):
- Go to [github.com](https://github.com) → profile picture → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)** → **Generate new token (classic)**
- Give it any name, set any expiry, and **don't tick any scopes** — then click **Generate token** and copy it immediately (you won't see it again)

Once you have both, set them in your terminal:

**Mac/Linux:**
```
export NEBIUS_API_KEY="your_nebius_api_key_here"
export GITHUB_TOKEN="your_github_token_here"
```

**Windows:**
```
set NEBIUS_API_KEY=your_nebius_api_key_here
set GITHUB_TOKEN=your_github_token_here
```

> ⚠️ These only last for the current terminal session. If you close and reopen your terminal, you'll need to set them again.
> 🔒 Never share your API keys or paste them into your code — treat them like passwords.

### 5. Start the server

```
python main.py
```

You should see something like:
```
* Running on http://0.0.0.0:8000
```

The server is now ready to use.

---

## Usage

Open a **new terminal window** (keep the server running in the other one) and run:

```
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/psf/requests"}'
```

**On Windows (PowerShell):**
```
Invoke-WebRequest -Uri http://localhost:8000/summarize -Method POST -ContentType "application/json" -Body '{"github_url": "https://github.com/psf/requests"}'
```

**Example response:**
```json
{
  "summary": "Requests is a simple, elegant HTTP library for Python that allows users to send HTTP/1.1 requests with minimal effort. It abstracts the complexity of making requests behind a simple API, widely used across the Python ecosystem.",
  "technologies": ["Python", "urllib3", "certifi", "charset-normalizer", "idna"],
  "structure": "Standard Python package layout with source code in src/requests/, tests in tests/, and documentation in docs/. Uses pyproject.toml for packaging."
}
```

> 💡 If you visit `http://localhost:8000/summarize` in your browser you'll get a "Not Found" error — that's normal. Browsers send GET requests, but this endpoint only accepts POST requests. Use curl or PowerShell instead.

### Health check

```
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

### Model: `deepseek-ai/DeepSeek-R1-0528`

We use DeepSeek R1 because it is a reasoning model — before giving its final answer, it thinks through the problem step by step internally. This makes it significantly better at tasks that require understanding and synthesis, like reading through a codebase and producing an accurate, structured summary. Compared to standard models, it is less likely to hallucinate technologies or misrepresent what a project does. It is available on Nebius Token Factory and performs well within the free credit tier.

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
- Boilerplate files (`LICENSE`, `.gitignore`, `CHANGELOG`, etc.)

**Directory tree:**
- A compact tree (up to depth 3) is always included to give the model structural context even for files whose contents weren't fetched
