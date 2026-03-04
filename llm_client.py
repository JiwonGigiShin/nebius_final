import os
import json
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

MODEL = "deepseek-ai/DeepSeek-R1-0528"

SYSTEM_PROMPT = """"You are an experienced Developer Advocate and senior software engineer who has reviewed thousands of
open source repositories. You are skilled at quickly understanding what a
project does and explaining it clearly to both technical and non-technical audiences.

Given repository contents (README, file tree, source files), produce a structured JSON summary.

You MUST respond with ONLY valid JSON - no markdown fences, no extra text, just the JSON object.

INSTRUCTIONS FOR EACH FIELD:

'summary':
- 2-4 sentences describing what the project does and who it is for
- Start with the project name and what it is (e.g. "Requests is a Python HTTP library...")
- Focus on purpose and value, not implementation details
- Do not start with "This repository contains" or "This project is"
- If content is sparse, infer from file structure and config files rather than saying you don't know

'technologies':
- List the most important languages, frameworks, libraries, and tools
- Order by importance (most central to the project first)
- Use proper capitalisation (e.g. "Python" not "python", "FastAPI" not "fastapi")
- Do NOT include version numbers (e.g. "Flask" not "Flask 2.x")
- Do NOT include trivial dependencies that are not central to what the project does
- Aim for 5-10 items

'structure':
- 1-2 sentences describing how the project is laid out
- Mention the most important directories and what they contain
- Name the overall pattern if applicable (e.g. "standard Python package layout", "monorepo", "MVC structure")
- Do not list every single folder, just the most meaningful ones

The JSON must have exactly these three fields:
{
  "summary": "A clear 2-4 sentence description of what the project does and its purpose.",
  "technologies": ["list", "of", "main", "languages", "frameworks", "and", "tools"],
  "structure": "1-2 sentences describing how the project is organised."
}
"""


def extract_json(text):
    """Try several strategies to extract a JSON object from the response."""

    text = text.strip()

    # DeepSeek R1 wraps reasoning in <think> tags before the answer - strip it
    if "<think>" in text and "</think>" in text:
        text = text[text.rfind("</think>") + len("</think>"):].strip()

    # Strategy 1: parse as-is
    try:
        return json.loads(text)
    except Exception:
        pass

    # Strategy 2: strip markdown fences
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part)
            except Exception:
                pass

    # Strategy 3: find the first { ... } block in the text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            pass

    return None


def summarize_with_llm(context, owner, repo):
    api_key = os.environ.get("NEBIUS_API_KEY")
    if not api_key:
        raise ValueError("NEBIUS_API_KEY environment variable is not set.")

    client = OpenAI(
        base_url="https://api.tokenfactory.nebius.com/v1/",
        api_key=api_key
    )

    user_message = "Please analyse this GitHub repository and return a JSON summary.\n\n"
    user_message += "Repository: " + owner + "/" + repo + "\n\n---\n\n"
    user_message += context
    user_message += "\n\n---\n\nRespond with ONLY the JSON object. No explanation, no markdown, just JSON."

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=1024,
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]
    )

    raw_text = response.choices[0].message.content
    if not raw_text:
        raise ValueError("LLM returned an empty response.")

    raw_text = raw_text.strip()
    logger.info("LLM raw response: %s", raw_text[:300])

    parsed = extract_json(raw_text)

    if parsed is None:
        logger.error("Could not parse JSON from LLM response: %s", raw_text[:500])
        raise ValueError("LLM did not return valid JSON. Raw response: " + raw_text[:200])

    summary = str(parsed.get("summary", "")).strip()
    technologies = parsed.get("technologies", [])
    if isinstance(technologies, str):
        technologies = [t.strip() for t in technologies.split(",") if t.strip()]
    elif not isinstance(technologies, list):
        technologies = []
    structure = str(parsed.get("structure", "")).strip()

    if not summary:
        raise ValueError("LLM returned empty summary field.")

    return {
        "summary": summary,
        "technologies": [str(t) for t in technologies],
        "structure": structure,
    }
