import requests
import base64
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"

MAX_CONTEXT_CHARS = 40000
MAX_FILE_CHARS = 6000

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".pytest_cache", "dist", "build",
    "target", "vendor", ".venv", "venv", "env", ".env", ".tox", "coverage",
    ".nyc_output", ".next", ".nuxt", "out", "eggs", "wheels", "htmlcov",
    "site-packages", "bower_components", ".cache", "tmp", "temp",
}

SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".bmp",
    ".pdf", ".zip", ".tar", ".gz", ".tgz", ".rar", ".7z",
    ".exe", ".dll", ".so", ".dylib", ".wasm",
    ".ttf", ".woff", ".woff2", ".eot", ".otf",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
    ".pyc", ".pyo", ".class", ".o", ".a",
    ".lock", ".sum",
    ".csv", ".tsv", ".parquet", ".sqlite", ".db",
    ".pb", ".onnx", ".pt", ".pth", ".pkl", ".h5",
}

SKIP_FILENAMES = {
    "package-lock.json", "yarn.lock", "poetry.lock", "Pipfile.lock",
    "Cargo.lock", "composer.lock", "Gemfile.lock", "pnpm-lock.yaml",
    ".DS_Store", "thumbs.db", ".gitignore", ".gitattributes",
    ".editorconfig", ".prettierrc", ".eslintignore", ".npmignore",
    "CHANGELOG.md", "CHANGES.md", "LICENSE", "LICENSE.md", "LICENSE.txt",
    "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md",
}

PRIORITY_FILENAMES = {
    "README.md", "README.rst", "README.txt", "README",
    "pyproject.toml", "setup.py", "setup.cfg",
    "package.json", "tsconfig.json",
    "Cargo.toml", "go.mod", "build.gradle", "pom.xml",
    "Makefile", "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "requirements.txt", "Pipfile", "environment.yml",
}

SOURCE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".kt",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
    ".sh", ".bash", ".yaml", ".yml", ".toml", ".json", ".ini", ".cfg",
    ".html", ".css", ".scss", ".sql", ".md", ".rst", ".tf",
}


def should_skip_path(path):
    parts = Path(path).parts
    for part in parts:
        if part in SKIP_DIRS:
            return True
    name = Path(path).name
    if name in SKIP_FILENAMES:
        return True
    suffix = Path(path).suffix.lower()
    if suffix in SKIP_EXTENSIONS:
        return True
    return False


def is_source_file(path):
    suffix = Path(path).suffix.lower()
    return suffix in SOURCE_EXTENSIONS


def is_priority_file(path):
    name = Path(path).name
    return name in PRIORITY_FILENAMES


def fetch_file_content(owner, repo, path):
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
    response = requests.get(url, timeout=15)
    if response.status_code != 200:
        return None
    data = response.json()
    if data.get("encoding") == "base64":
        try:
            raw = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            if "\x00" in raw[:1000]:
                return None
            return raw
        except Exception:
            return None
    return None


def build_dir_tree(all_files, max_depth=3):
    dirs = set()
    for path in all_files:
        parts = Path(path).parts
        for i in range(1, min(len(parts), max_depth + 1)):
            dirs.add("/".join(parts[:i]))

    visible = sorted(d for d in dirs if not any(
        part in SKIP_DIRS or part.startswith(".")
        for part in d.split("/")
    ))

    lines = []
    for d in visible[:80]:
        depth = d.count("/")
        name = d.split("/")[-1]
        lines.append("  " * depth + name + "/")

    return "\n".join(lines) if lines else "(empty)"


def fetch_repo_contents(owner, repo):
    import os
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = "Bearer " + token

    repo_resp = requests.get(f"{GITHUB_API}/repos/{owner}/{repo}", headers=headers, timeout=15)
    if repo_resp.status_code == 404:
        raise Exception("404: Repository not found")
    repo_resp.raise_for_status()

    repo_info = repo_resp.json()
    default_branch = repo_info.get("default_branch", "main")
    description = repo_info.get("description") or ""
    topics = repo_info.get("topics", [])

    tree_resp = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{default_branch}",
        params={"recursive": "1"},
        headers=headers,
        timeout=15
    )
    tree_resp.raise_for_status()

    all_files = [
        item["path"] for item in tree_resp.json().get("tree", [])
        if item["type"] == "blob"
    ]

    dir_tree = build_dir_tree(all_files)

    readme_path = None
    priority_files = []
    source_files = []

    for path in all_files:
        if should_skip_path(path):
            continue
        name = Path(path).name.upper()
        if name.startswith("README"):
            readme_path = path
        elif is_priority_file(path):
            priority_files.append(path)
        elif is_source_file(path):
            source_files.append(path)

    chars_used = 0
    budget = MAX_CONTEXT_CHARS

    readme_content = ""
    if readme_path:
        content = fetch_file_content(owner, repo, readme_path)
        if content:
            readme_content = content[:MAX_FILE_CHARS]
            chars_used += len(readme_content)

    files_content = []

    for path in priority_files:
        if chars_used >= budget:
            break
        content = fetch_file_content(owner, repo, path)
        if content:
            truncated = content[:MAX_FILE_CHARS]
            files_content.append((path, truncated))
            chars_used += len(truncated)

    source_files.sort(key=lambda p: (p.count("/"), p))
    for path in source_files:
        if chars_used >= budget:
            break
        content = fetch_file_content(owner, repo, path)
        if content:
            truncated = content[:MAX_FILE_CHARS]
            files_content.append((path, truncated))
            chars_used += len(truncated)

    logger.info("Fetched %d files, %d chars total", len(files_content), chars_used)

    return {
        "owner": owner,
        "repo": repo,
        "description": description,
        "topics": topics,
        "readme": readme_content,
        "files": files_content,
        "dir_tree": dir_tree,
        "total_files": len(all_files),
    }


def build_llm_context(repo_data):
    parts = []

    parts.append("# Repository: " + repo_data["owner"] + "/" + repo_data["repo"])
    if repo_data["description"]:
        parts.append("Description: " + repo_data["description"])
    if repo_data["topics"]:
        parts.append("Topics: " + ", ".join(repo_data["topics"]))
    parts.append("Total files in repo: " + str(repo_data["total_files"]))
    parts.append("")

    if repo_data["readme"]:
        parts.append("## README")
        parts.append(repo_data["readme"])
        parts.append("")

    parts.append("## Directory Structure")
    parts.append(repo_data["dir_tree"])
    parts.append("")

    if repo_data["files"]:
        parts.append("## Key Files")
        for path, content in repo_data["files"]:
            parts.append("\n### " + path)
            parts.append(content)

    return "\n".join(parts)
