import re
import logging
from flask import Flask, request, jsonify
from repo_processor import fetch_repo_contents, build_llm_context
from llm_client import summarize_with_llm

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

GITHUB_URL_PATTERN = re.compile(
    r"^https?://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+?)(?:\.git)?/?$"
)


@app.route("/summarize", methods=["POST"])
def summarize():
    body = request.get_json()

    if not body or "github_url" not in body:
        return jsonify({"status": "error", "message": "Missing 'github_url' in request body"}), 400

    github_url = body["github_url"].strip().rstrip("/")
    match = GITHUB_URL_PATTERN.match(github_url)

    if not match:
        return jsonify({"status": "error", "message": "Invalid GitHub URL. Expected format: https://github.com/owner/repo"}), 400

    owner = match.group(1)
    repo = match.group(2)

    try:
        repo_data = fetch_repo_contents(owner, repo)
    except Exception as e:
        message = str(e)
        if "404" in message:
            return jsonify({"status": "error", "message": f"Repository '{owner}/{repo}' not found or is private."}), 404
        return jsonify({"status": "error", "message": f"Failed to fetch repository: {message}"}), 502

    if not repo_data["files"] and not repo_data["readme"]:
        return jsonify({"status": "error", "message": "Repository appears to be empty or has no readable content."}), 422

    context = build_llm_context(repo_data)

    try:
        result = summarize_with_llm(context, owner, repo)
    except Exception as e:
        return jsonify({"status": "error", "message": f"LLM API error: {str(e)}"}), 502

    return jsonify(result)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
