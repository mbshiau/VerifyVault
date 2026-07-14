import json

import httpx
from groq import Groq

from config import settings

client = Groq(api_key=settings.groq_api_key)

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "2-4 sentence executive summary."},
        "topics": {
            "type": "array",
            "items": {"type": "string"},
            "description": "High-level topics (e.g., Economy, Healthcare, Immigration).",
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["text", "confidence"],
            },
            "description": "Verifiable factual claims made in the text.",
        },
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": ["person", "organization", "law", "program", "location"],
                    },
                },
                "required": ["name", "type"],
            },
        },
    },
    "required": ["summary", "topics", "claims", "entities"],
}

EXTRACT_TOOL = {
    "type": "function",
    "function": {
        "name": "record_analysis",
        "description": "Record the structured analysis of a political text.",
        "parameters": EXTRACT_SCHEMA,
    },
}


def extract(text: str) -> dict:
    resp = client.chat.completions.create(
        model=settings.groq_model,
        max_tokens=4096,
        tools=[EXTRACT_TOOL],
        tool_choice={"type": "function", "function": {"name": "record_analysis"}},
        messages=[
            {
                "role": "system",
                "content": (
                    "You analyze political text and return structured output via the "
                    "record_analysis tool. Always call the tool exactly once."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Analyze the following political text. Extract a concise summary, "
                    "topics, verifiable factual claims (with confidence), and named entities.\n\n"
                    f"---\n{text}\n---"
                ),
            },
        ],
    )
    msg = resp.choices[0].message
    if msg.tool_calls:
        return json.loads(msg.tool_calls[0].function.arguments)
    raise RuntimeError("Model did not return structured output")


def search_sources(query: str, k: int = 3) -> list[dict]:
    if not settings.tavily_api_key:
        return []
    r = httpx.post(
        "https://api.tavily.com/search",
        json={
            "api_key": settings.tavily_api_key,
            "query": query,
            "max_results": k,
            "search_depth": "basic",
            "include_answer": False,
        },
        timeout=20.0,
    )
    r.raise_for_status()
    data = r.json()
    return [
        {"title": x.get("title", ""), "url": x.get("url", ""), "snippet": x.get("content", "")[:280]}
        for x in data.get("results", [])
    ]


def run(text: str) -> dict:
    result = extract(text)
    for claim in result.get("claims", []):
        try:
            claim["sources"] = search_sources(claim["text"], k=3)
        except Exception:
            claim["sources"] = []
    return result
