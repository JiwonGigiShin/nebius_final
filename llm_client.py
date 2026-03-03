import os
import json
import requests
import logging

logger = logging.getLogger(__name__)

NEBIUS_API_URL = "https://api.studio.nebius.com/v1/chat/completions"
MODEL = "meta-llama/Meta-Llama-3.1-70B-Instruct"

SYSTEM_PROMPT = """You are a senior software engineer tasked with analysing GitHub repositories.
Given repository contents (README, file tree, source files), produce a structured JSON summary.

You MUST respond with ONLY valid JSON - no markdown fences, no extra text, just the JSON object.

The JSON must have exactly these three fields:
{
    "summary": "A clear 2-4 sentence description of what the project does and its purpose.",
    "technologies": ["list", "of", "main", "languages", "frameworks", "and", "tools"],
    "structure": "1-2 sentences describing how the project is organised."
}
"""


def summarise_with_llm(context, owner, repo):
    api_key = os.environ.get("NEBIUS_API_KEY")
    if not api_key:
        raise ValueError("NEBIUS_API_KEY environment variable is not set.")

    user_message = "Please analyse this GitHub repository and return a JSON summary.\n\n"
    user_message += "Repository: " + owner + "/" + repo + "\n\n---\n\n"
    user_message += context
    user_message += "\n\n---\n\nRespond with ONLY the JSON object."

    payload = {
        "model": MODEL,
        "max_tokens": 1024,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    }

    headers = {
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
    }

    response = requests.post(NEBIUS_API_URL, json=payload, headers=headers, timeout=60)
    response.raise_for_status()

    data = response.json()
    raw_text = data["choices"][0]["message"]["content"].strip()

    logger.info("LLM response (first 200 chars): %s", raw_text[:200])

    # Strip markdown fences if the model ignored instructions
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    parsed = json.loads(raw_text)

    summary = str(parsed.get("summary", "")).strip()
    technologies = parsed.get("technologies", [])
    if isinstance(technologies, str):
        technologies = [t.strip() for t in technologies.split(",") if t.strip()]
    elif not isinstance(technologies, list):
        technologies = []
    structure = str(parsed.get("structure", "")).strip()

    if not summary:
        raise ValueError("LLM returned empty summary")

    return {
        "summary": summary,
        "technologies": [str(t) for t in technologies],
        "structure": structure,
    }
