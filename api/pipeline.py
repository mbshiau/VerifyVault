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
                    "quote": {
                        "type": "string",
                        "description": (
                            "The exact sentence copied verbatim from the original text "
                            "(character-for-character, no paraphrasing) that this claim is based on."
                        ),
                    },
                    "explanation": {
                        "type": "string",
                        "description": (
                            "1-2 plain-language sentences explaining what the claim asserts and "
                            "why it matters or what makes it checkable."
                        ),
                    },
                    "context": {
                        "type": "string",
                        "description": (
                            "1-2 sentences of surrounding background needed to understand the claim "
                            "(e.g. what prompted it, how it fits the rest of the text)."
                        ),
                    },
                    "related_entities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Names of people, organizations, laws, programs, or locations from the "
                            "extracted entities list that are directly relevant to this claim."
                        ),
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["text", "quote", "explanation", "context", "related_entities", "confidence"],
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
                        "enum": ["person", "organization", "law", "program", "location", "group", "event"],
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
                    "topics, verifiable factual claims, and named entities. For each claim, include "
                    "a verbatim quote of the source sentence, a brief explanation of what it asserts "
                    "and why it's checkable, surrounding context, the related entities involved, and "
                    "a confidence score. The quote field must be an exact character-for-character "
                    "substring of the original text below.\n\n"
                    f"---\n{text}\n---"
                ),
            },
        ],
    )
    msg = resp.choices[0].message
    if msg.tool_calls:
        return json.loads(msg.tool_calls[0].function.arguments)
    raise RuntimeError("Model did not return structured output")


SOCIAL_MEDIA_DOMAINS = [
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "tiktok.com",
    "reddit.com",
    "pinterest.com",
    "threads.net",
    "youtube.com",
    "youtu.be",
]

# Domain suffixes/substrings that indicate a more authoritative, lower-bias source.
# Higher score = ranked first among results.
PREFERRED_DOMAIN_SCORES: list[tuple[str, int]] = [
    (".gov", 3),
    (".mil", 3),
    ("congress.gov", 3),
    ("govinfo.gov", 3),
    (".edu", 3),
    ("who.int", 3),
    ("un.org", 3),
    ("worldbank.org", 3),
    ("imf.org", 3),
    (".org", 1),  # NGOs/nonprofits/think tanks - mild boost over generic .com
    ("reuters.com", 2),
    ("apnews.com", 2),
    ("bbc.com", 2),
    ("npr.org", 2),
    ("pbs.org", 2),
    ("bloomberg.com", 2),
    ("wsj.com", 2),
    ("nytimes.com", 2),
    ("washingtonpost.com", 2),
    ("factcheck.org", 2),
    ("politifact.com", 2),
    ("snopes.com", 2),
]


def _domain_score(url: str) -> int:
    url = url.lower()
    return max((score for suffix, score in PREFERRED_DOMAIN_SCORES if suffix in url), default=0)


def search_sources(query: str, k: int = 3) -> list[dict]:
    if not settings.tavily_api_key:
        return []
    r = httpx.post(
        "https://api.tavily.com/search",
        json={
            "api_key": settings.tavily_api_key,
            "query": query,
            "max_results": k * 4,
            "search_depth": "basic",
            "include_answer": False,
            "exclude_domains": SOCIAL_MEDIA_DOMAINS,
        },
        timeout=20.0,
    )
    r.raise_for_status()
    data = r.json()
    results = data.get("results", [])
    # Primary signal is Tavily's own relevance score; the domain preference is only
    # a small nudge so an irrelevant .edu/.org page can't outrank a relevant result.
    results.sort(key=lambda x: x.get("score", 0) + _domain_score(x.get("url", "")) * 0.05, reverse=True)
    return [
        {"title": x.get("title", ""), "url": x.get("url", ""), "snippet": x.get("content", "")[:280]}
        for x in results[:k]
    ]


RELATE_SCHEMA = {
    "type": "object",
    "properties": {
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "relation": {
                        "type": "string",
                        "description": (
                            "One short sentence (under 20 words) on how this specific source "
                            "relates to the claim - e.g. whether it supports, contradicts, or "
                            "provides background/context for it."
                        ),
                    },
                },
                "required": ["url", "relation"],
            },
        },
    },
    "required": ["relations"],
}

RELATE_TOOL = {
    "type": "function",
    "function": {
        "name": "record_relevance",
        "description": "Record how each search result relates to the claim.",
        "parameters": RELATE_SCHEMA,
    },
}


def explain_relevance(claim_text: str, sources: list[dict]) -> dict[str, str]:
    if not sources:
        return {}
    listing = "\n".join(
        f"- url: {s['url']}\n  title: {s['title']}\n  excerpt: {s['snippet'][:200]}" for s in sources
    )
    resp = client.chat.completions.create(
        model=settings.groq_model,
        max_tokens=1024,
        tools=[RELATE_TOOL],
        tool_choice={"type": "function", "function": {"name": "record_relevance"}},
        messages=[
            {
                "role": "system",
                "content": (
                    "You explain how search results relate to a factual claim, via the "
                    "record_relevance tool. Always call the tool exactly once."
                ),
            },
            {
                "role": "user",
                "content": (
                    f'Claim: "{claim_text}"\n\nSearch results:\n{listing}\n\n'
                    "For each result above (matched by its url), write one short sentence on "
                    "how it relates to the claim."
                ),
            },
        ],
    )
    msg = resp.choices[0].message
    if msg.tool_calls:
        data = json.loads(msg.tool_calls[0].function.arguments)
        return {r["url"]: r["relation"] for r in data.get("relations", []) if "url" in r}
    return {}


def run(text: str) -> dict:
    result = extract(text)
    for claim in result.get("claims", []):
        try:
            sources = search_sources(claim["text"], k=3)
            relations = explain_relevance(claim["text"], sources)
            for s in sources:
                s["relation"] = relations.get(s["url"], "")
            claim["sources"] = sources
        except Exception:
            claim["sources"] = []
    return result
