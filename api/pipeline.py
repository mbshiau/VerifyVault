import json

import httpx
from openai import OpenAI

from config import settings

client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url or None)

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "2-4 sentence executive summary."},
        "topics": {
            "type": "array",
            "items": {"type": "string"},
            "description": "High-level topics (e.g., Economy, Healthcare, Immigration).",
        },
        "key_ideas": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "3-6 core ideas/main points the text is making - the things it is actually "
                "trying to argue or communicate, not just topics it touches on in passing. "
                "Identify these BEFORE selecting claims below; every claim must trace back to one of these."
            ),
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "key_idea": {
                        "type": "string",
                        "description": (
                            "Which entry from key_ideas above this claim is directly relevant to. "
                            "Every claim must support one of the key ideas - if a verifiable statement "
                            "doesn't clearly tie back to a key idea, leave it out."
                        ),
                    },
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
                "required": [
                    "text",
                    "key_idea",
                    "quote",
                    "explanation",
                    "context",
                    "related_entities",
                    "confidence",
                ],
            },
            "description": (
                "Verifiable factual claims that are directly relevant to one of the key_ideas above. "
                "Skip claims that are merely incidental context, background color, or tangential to "
                "the text's actual main points, even if technically verifiable."
            ),
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
    "required": ["summary", "topics", "key_ideas", "claims", "entities"],
}

EXTRACT_TOOL = {
    "type": "function",
    "function": {
        "name": "record_analysis",
        "description": "Record the structured analysis of a political text.",
        "parameters": EXTRACT_SCHEMA,
    },
}


CLAIM_RULES = """\
## What counts as a verifiable factual claim

INCLUDE a statement if it asserts something objectively checkable against evidence, e.g.:
- An event occurred or a condition exists (e.g. "we have had closures").
- A document, bill, law, or regulation exists or was proposed/introduced (e.g. "I have a bill to get that moving").
- A person or group holds a role, took an action, or made a decision (e.g. "the Department of Education is trying to roll back access").
- A statistic, quantity, date, or comparison is stated as fact.
Extract the claim even if its accuracy is disputed or unconfirmed - the assertion itself being checkable is what matters, not whether it's true. If a statement mixes opinion and fact, extract only the factual portion as the claim. If a claim's own existence is uncertain (e.g. a bill name that may be garbled), still extract it, but lower its confidence score.

EXCLUDE a statement if it is only:
- An opinion or value judgment (e.g. "that's broken", "devastating").
- A prediction about the future with no concrete factual anchor (e.g. "we will have fewer providers"), including hedged speculation using words like "may" or "could" (e.g. "technology that may displace a lot of entry-level jobs").
- A hypothetical or conditional example (e.g. "if you have access to a nurse practitioner...").
- A rhetorical exhortation or advocacy statement (e.g. "let's be smart", "focus on winning").
- A causal/policy argument stated as a generalization rather than a discrete checkable fact (e.g. "that's how we drive down costs").
- A question, including rhetorical or interview questions directed at someone else (e.g. "how should policymakers respond?") - questions assert nothing and are never claims.
- A generic observation or truism that is trivially true and carries no specific, meaningful content worth checking (e.g. "people are graduating from high school and college"). A statement only counts as a claim if it asserts something specific enough that it could plausibly be false.
- A subjective characterization of mood, sentiment, or attention around a topic (e.g. "there's a lot of anxiety around AI").
- Speculative attribution of cause or motive without evidence (e.g. "some of that angst has to do with the advent of this new technology").

## Work top-down from key ideas, not bottom-up from every sentence

Do not scan the text line by line looking for anything technically checkable. Instead:
1. First decide the 3-6 key ideas - the actual points the text is trying to make.
2. Then, for each key idea, find the claim(s) that most directly support or assert it.
3. Skip statements that are merely incidental context, scene-setting, or asides - even if they contain a verifiable fact - if they don't support one of the key ideas. A passing mention that isn't part of what the speaker is actually trying to argue is not worth flagging.

## Worked examples

Segment: "I represent a rural committee outside of Chicago. In the last year we have had closures. Those facilities need help to stay open. I have a bill to get that moving. ... We will have fewer providers. If you have access to a nurse practitioner in your community and there is no physician what is he supposed to do? ... It doesn't have to explode the deficit."

Claims to extract: "I represent a rural committee outside of Chicago" (verifiable role/constituency); "In the last year we have had closures" (verifiable event); "I have a bill to get that moving" (verifiable - a specific bill either exists or doesn't).

Not claims: "Those facilities need help to stay open" (opinion); "We will have fewer providers" (prediction); "If you have access to a nurse practitioner..." (hypothetical); "It doesn't have to explode the deficit" (prediction/opinion).

Segment: "There's a lot of anxiety around AI. People are graduating from high school and graduating from college. There's a lot of angst out there about the job market and if you look at the unemployment rate for young workers, whether college graduate or not, it is rising, and some of that angst has to do with the advent of this new technology that may displace a lot of entry-level jobs. To what extent do you think AI-driven job replacement is similar or different from automation?"

Claims to extract: "If you look at the unemployment rate for young workers, whether college graduate or not, it is rising" (concrete, checkable labor-market statistic).

Not claims: "There's a lot of anxiety around AI" (subjective characterization); "People are graduating from high school and graduating from college" (generic truism, not meaningfully checkable); "There's a lot of angst out there about the job market" (subjective sentiment); "Some of that angst has to do with the advent of this new technology..." (speculative attribution of cause); "...technology that may displace a lot of entry-level jobs" (hedged prediction); "To what extent do you think AI-driven job replacement is similar or different from automation?" (question).
"""


def extract(text: str, speaker: str | None = None) -> dict:
    speaker_line = (
        f"This text was said or written by {speaker}. Use that when judging who entities/related_entities "
        "refer to (e.g. resolve pronouns like 'I' or 'we' to this speaker) and when writing context/explanation.\n\n"
        if speaker
        else ""
    )
    resp = client.chat.completions.create(
        model=settings.openai_model,
        max_tokens=4096,
        tools=[EXTRACT_TOOL],
        tool_choice={"type": "function", "function": {"name": "record_analysis"}},
        messages=[
            {
                "role": "system",
                "content": (
                    "You analyze political text and return structured output via the "
                    "record_analysis tool. Always call the tool exactly once. You are especially "
                    "careful to distinguish objectively verifiable factual claims from opinions, "
                    "predictions, rhetorical flourishes, and hypotheticals.\n\n" + CLAIM_RULES
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{speaker_line}"
                    "Analyze the following political text. First identify its key ideas - the "
                    "actual points it's trying to make, not just topics it mentions in passing. "
                    "Then extract a concise summary, topics, and verifiable factual claims that "
                    "each directly support one of those key ideas, applying the claim rules from "
                    "the system prompt strictly. Ignore incidental context and claims that aren't "
                    "relevant to the key ideas, even if technically verifiable - focus on quality "
                    "and relevance over exhaustively listing everything checkable. Also extract "
                    "named entities. For each claim, include a verbatim quote of the source "
                    "sentence, a brief explanation of what it asserts and why it's checkable, "
                    "surrounding context, the related entities involved, and a confidence score. "
                    "The quote field must be an exact character-for-character substring of the "
                    "original text below.\n\n"
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
        model=settings.openai_model,
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


def run(text: str, speaker: str | None = None) -> dict:
    result = extract(text, speaker)
    for claim in result.get("claims", []):
        try:
            query = f"{speaker}: {claim['text']}" if speaker else claim["text"]
            sources = search_sources(query, k=3)
            relations = explain_relevance(claim["text"], sources)
            for s in sources:
                s["relation"] = relations.get(s["url"], "")
            claim["sources"] = sources
        except Exception:
            claim["sources"] = []
    return result
