"""
LLM client using Nebius Token Factory API via OpenAI-compatible SDK.
Model: meta-llama/Meta-Llama-3.1-70B-Instruct-fast
"""

import os
import json
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

MODEL = "meta-llama/Meta-Llama-3.1-70B-Instruct-fast"

SYSTEM_PROMPT = """You are a senior software engineer tasked with analyzing GitHub repositories.
Given repository contents (README, file tree, source files), produce a structured JSON summary.

You MUST respond with ONLY valid JSON - no markdown fences, no extra text, just the JSON object.

The JSON must have exactly these three fields:
{
  "summary": "A clear 2-4 sentence description of what the project does and its purpose.",
  "technologies": ["list", "of", "main", "languages", "frameworks", "and", "tools"],
  "structure": "1-2 sentences describing how the project is organized."
}
"""


def summarize_with_llm(context, owner, repo):
    api_key = os.environ.get("NEBIUS_API_KEY")
    if not api_key:
        raise ValueError("NEBIUS_API_KEY environment variable is not set.")

    client = OpenAI(
        base_url="https://api.tokenfactory.nebius.com/v1/",
        api_key=api_key
    )

    user_message = "Please analyze this GitHub repository and return a JSON summary.\n\n"
    user_message += "Repository: " + owner + "/" + repo + "\n\n---\n\n"
    user_message += context
    user_message += "\n\n---\n\nRespond with ONLY the JSON object."

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=1024,
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]
    )

    raw_text = response.choices[0].message.content.strip()
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
