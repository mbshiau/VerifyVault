import json
import re
from urllib.parse import urlparse

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
                    "time_reference": {
                        "type": "string",
                        "description": (
                            "The year (or year range) the claim's central event actually happened, e.g. "
                            "'2022' or '2021-2022'. If the text doesn't state a year, use your own "
                            "knowledge of when the named law/program/event occurred (e.g. the Bipartisan "
                            "Infrastructure Law was signed in 2021, the CHIPS Act in 2022). If you genuinely "
                            "don't know or it's not a dated event, use 'unspecified'."
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
                    "time_reference",
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
    messages = [
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
                "surrounding context, the related entities involved, the year/time period the "
                "claim's underlying event actually happened (using your own knowledge of when "
                "named laws/programs occurred if the text doesn't state it), and a confidence "
                "score. The quote field must be an exact character-for-character substring of the "
                "original text below.\n\n"
                f"---\n{text}\n---"
            ),
        },
    ]

    last_error: Exception = RuntimeError("Model did not return structured output")
    for _ in range(3):
        resp = client.chat.completions.create(
            model=settings.openai_model,
            max_tokens=4096,
            tools=[EXTRACT_TOOL],
            tool_choice={"type": "function", "function": {"name": "record_analysis"}},
            messages=messages,
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            continue
        try:
            return json.loads(msg.tool_calls[0].function.arguments)
        except json.JSONDecodeError as e:
            last_error = e
    raise last_error


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
    ("yahoo.com", 2),
    ("cnn.com", 2),
    ("nbcnews.com", 2),
    ("abcnews.go.com", 2),
    ("cbsnews.com", 2),
    ("usatoday.com", 2),
    ("theguardian.com", 2),
    ("axios.com", 2),
]


def _domain_score(url: str) -> int:
    url = url.lower()
    return max((score for suffix, score in PREFERRED_DOMAIN_SCORES if suffix in url), default=0)


def _speaker_name_slugs(speaker: str | None) -> list[str]:
    if not speaker:
        return []
    return [w.lower() for w in re.findall(r"[A-Za-z]+", speaker) if len(w) >= 4]


def _is_speaker_own_site(url: str, speaker_slugs: list[str]) -> bool:
    if not speaker_slugs:
        return False
    netloc = urlparse(url.lower()).netloc
    if not any(slug in netloc for slug in speaker_slugs):
        return False
    # Only treat it as a self-published source if the domain also looks like an
    # official/campaign site for a person, not e.g. a news article whose path
    # happens to mention the speaker (path isn't checked - only the domain is).
    return (
        netloc.endswith((".gov", ".house.gov", ".senate.gov"))
        or "forcongress" in netloc
        or "campaign" in netloc
    )


_YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")
# Tavily's basic-search snippets often lead with a scraped "Mon D, YYYY —" publish
# date (e.g. "Aug 16, 2022 — The law allocates..."); there's no structured
# published_date field at this search depth, so this is the only date signal we have.
_CONTENT_DATE_RE = re.compile(r"\b[A-Z][a-z]{2,8}\.?\s+\d{1,2},\s+(\d{4})\b")


def _parse_claim_year(time_reference: str | None) -> int | None:
    if not time_reference:
        return None
    years = [int(y) for y in _YEAR_RE.findall(time_reference)]
    return min(years) if years else None


def _parse_content_year(content: str) -> int | None:
    m = _CONTENT_DATE_RE.search(content or "")
    return int(m.group(1)) if m else None


def search_sources(query: str, k: int = 3, speaker: str | None = None, claim_year: int | None = None) -> list[dict]:
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
    # Drop the speaker's own official/campaign site - it's a primary source, not
    # independent verification, and otherwise tends to crowd out real coverage.
    speaker_slugs = _speaker_name_slugs(speaker)
    results = [x for x in results if not _is_speaker_own_site(x.get("url", ""), speaker_slugs)]
    # Drop bare homepages (e.g. "house.gov" with no path) - they're never specific
    # enough to verify a claim, and the domain boost below would otherwise let a
    # trusted TLD rescue an essentially content-free result into the top ranks.
    results = [x for x in results if urlparse(x.get("url", "")).path not in ("", "/")]

    def _score(x: dict) -> float:
        base = x.get("score", 0)
        # Only apply the domain-trust nudge once a result has already cleared a
        # basic relevance bar - otherwise a near-irrelevant page (Tavily score
        # near 0) can outrank genuinely relevant results purely by being on a
        # trusted domain, which defeats the "small nudge" intent.
        score = base + (_domain_score(x.get("url", "")) * 0.05 if base >= 0.15 else 0)
        if claim_year is not None:
            content_year = _parse_content_year(x.get("content", ""))
            # Only penalize when we're confident the article predates the claimed
            # event by more than a year - a 1yr buffer covers pre-announcement/
            # proposal coverage without letting genuinely stale articles rank high.
            if content_year is not None and content_year < claim_year - 1:
                score -= 0.5
        return score

    # Primary signal is Tavily's own relevance score; the domain preference and
    # date penalty are only small nudges so a single mismatch can't flip the order
    # of two otherwise-similar results.
    results.sort(key=_score, reverse=True)
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


def calculate_confidence(
    claim: dict,
    sources: list[dict],
    source_relations: dict[str, str],
    speaker: str | None = None,
) -> tuple[float, str]:
    """Calculate confidence score based on source verification, date relevance, and speaker credibility."""
    confidence = 0.5
    factors = []
    
    # Factor 1: Source verification (0-0.3)
    if sources:
        supporting_count = sum(
            1 for url, relation in source_relations.items()
            if relation and any(w in relation.lower() for w in ["support", "confirm", "verify", "corroborate"])
        )
        contradicting_count = sum(
            1 for url, relation in source_relations.items()
            if relation and any(w in relation.lower() for w in ["contradict", "dispute", "refute", "deny"])
        )
        
        if contradicting_count > 0:
            source_boost = -0.2
            factors.append(f"contradicted by {contradicting_count} source(s)")
        elif supporting_count >= len(sources):
            source_boost = 0.3
            factors.append(f"supported by all {len(sources)} source(s)")
        elif supporting_count > 0:
            source_boost = 0.15 + (supporting_count / len(sources)) * 0.15
            factors.append(f"supported by {supporting_count}/{len(sources)} source(s)")
        else:
            source_boost = 0.05
            factors.append(f"mentioned in {len(sources)} source(s)")
        confidence += source_boost
    else:
        factors.append("no sources found")
    
    # Factor 2: Date relevance (0-0.2)
    claim_year = _parse_claim_year(claim.get("time_reference"))
    if claim_year:
        from datetime import datetime
        current_year = datetime.now().year
        years_old = current_year - claim_year
        
        if years_old <= 1:
            date_boost = 0.2
            factors.append(f"recent claim ({claim_year})")
        elif years_old <= 5:
            date_boost = 0.1
            factors.append(f"from {claim_year}")
        elif years_old <= 10:
            date_boost = 0.05
            factors.append(f"from {claim_year}")
        else:
            date_boost = 0.0
            factors.append(f"from {claim_year} (dated)")
        confidence += date_boost
    
    # Factor 3: Speaker credibility (0-0.2)
    if speaker:
        credibility_score = _assess_speaker_credibility(speaker)
        factors.append(f"speaker credibility: {credibility_score['level']}")
        confidence += credibility_score['boost']
    
    # Clamp to [0, 1]
    confidence = max(0.0, min(1.0, confidence))
    
    explanation = "; ".join(factors)
    return confidence, explanation


def _assess_speaker_credibility(speaker: str) -> dict[str, float | str]:
    """Simple heuristic for speaker credibility based on known roles/positions."""
    speaker_lower = speaker.lower()
    
    # Government officials typically have higher credibility
    if any(w in speaker_lower for w in ["senator", "congressman", "representative", "judge", "secretary", "president", "minister"]):
        return {"level": "High", "boost": 0.2}
    
    # Academics and researchers
    if any(w in speaker_lower for w in ["professor", "dr.", "phd", "researcher"]):
        return {"level": "High", "boost": 0.2}
    
    # Advocacy groups and organizations
    if any(w in speaker_lower for w in ["director", "executive", "founder"]):
        return {"level": "Medium", "boost": 0.1}
    
    # Unknown or unverified speakers
    return {"level": "Unknown", "boost": 0.0}


ENTITY_DESCRIPTION_SCHEMA = {
    "type": "object",
    "properties": {
        "descriptions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {
                        "type": "string",
                        "description": "1-2 sentence factual description of who/what this entity is and why it matters to the text.",
                    },
                },
                "required": ["name", "description"],
            },
        },
    },
    "required": ["descriptions"],
}

ENTITY_DESCRIPTION_TOOL = {
    "type": "function",
    "function": {
        "name": "record_entity_descriptions",
        "description": "Record descriptions for named entities mentioned in political text.",
        "parameters": ENTITY_DESCRIPTION_SCHEMA,
    },
}


def enrich_entity_descriptions(text: str, entities: list[dict]) -> dict[str, str]:
    """Use LLM to generate concise descriptions for entities based on the text context."""
    if not entities:
        return {}
    
    entity_list = ", ".join(e["name"] for e in entities)
    resp = client.chat.completions.create(
        model=settings.openai_model,
        max_tokens=1024,
        tools=[ENTITY_DESCRIPTION_TOOL],
        tool_choice={"type": "function", "function": {"name": "record_entity_descriptions"}},
        messages=[
            {
                "role": "system",
                "content": (
                    "You provide brief, factual descriptions of named entities mentioned in political text, "
                    "based on context clues in the text itself. Use the record_entity_descriptions tool. "
                    "Always call the tool exactly once."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Based on the following political text, provide brief descriptions (1-2 sentences each) "
                    f"for these entities: {entity_list}\n\n"
                    f"Text:\n---\n{text}\n---\n\n"
                    f"Focus on what the text reveals about each entity and why they matter to the claims being made."
                ),
            },
        ],
    )
    msg = resp.choices[0].message
    if msg.tool_calls:
        try:
            data = json.loads(msg.tool_calls[0].function.arguments)
            return {e["name"]: e["description"] for e in data.get("descriptions", [])}
        except (json.JSONDecodeError, KeyError):
            return {}
    return {}


def _summarize_text(content: str, title: str | None = None) -> str:
    """Generate a 2-3 sentence neutral summary for a piece of content using the LLM."""
    if not content:
        return ""
    prompt_title = f"Title: {title}\n\n" if title else ""
    messages = [
        {
            "role": "system",
            "content": "You are a concise summarization assistant. Produce a neutral, factual 2-3 sentence summary of the provided article content. Avoid opinion, and focus on the main facts or claims presented.",
        },
        {
            "role": "user",
            "content": prompt_title + "Article excerpt:\n---\n" + (content[:3000] if len(content) > 3000 else content) + "\n---\n\nProvide a 2-3 sentence summary." ,
        },
    ]
    try:
        resp = client.chat.completions.create(model=settings.openai_model, messages=messages, max_tokens=256)
        msg = resp.choices[0].message
        # prefer the assistant content
        if msg.content:
            return msg.content.strip()
        return ""
    except Exception:
        return ""


def search_entity_sources(entity_name: str, entity_type: str, k: int = 3) -> list[dict]:
    """Search for news, speeches, and other sources related to a specific entity.

    Returns a list of dicts with keys: title, url, snippet, summary, category.
    """
    if not settings.tavily_api_key:
        return []

    # Build a more specific query based on entity type
    type_hints = {
        "person": f'"{entity_name}" recent news OR speech OR interview',
        "organization": f'"{entity_name}" announcement OR news OR policy',
        "law": f'"{entity_name}" bill OR legislation OR passed OR enacted',
        "program": f'"{entity_name}" program OR initiative OR launched',
        "location": f'"{entity_name}" political news OR developments',
    }

    query = type_hints.get(entity_type, entity_name)

    try:
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

        # Filter: must have content, exclude homepages and short snippets
        def _is_valid_result(x: dict) -> bool:
            url = x.get("url", "")
            title = (x.get("title", "") or "").strip()
            content = (x.get("content", "") or "").strip()
            if not url or urlparse(url).path in ("", "/"):
                return False
            # Must have substantial content
            if not content or len(content) < 300:
                return False
            # Filter out generic or unhelpful titles
            if title.lower() in ("home", "news", "politics", "articles", "latest"):
                return False
            # Exclude templated hub pages or scraper templates that include bracketed placeholders
            if re.search(r"\[.*?\]", content):
                return False
            # Exclude common placeholder tokens produced by feeds/templates
            placeholder_tokens = ("monthFull", "deltaHours", "deltaMinutes", "AMPM", "[hour]", "[minute]")
            if any(tok in content for tok in placeholder_tokens):
                return False
            # Exclude pages that look like schedules or event listings (many time/date entries or table-like separators)
            time_matches = len(re.findall(r"\b\d{1,2}:\d{2}\s*(am|pm)\b", content, flags=re.IGNORECASE))
            date_slash_matches = len(re.findall(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", content))
            weekday_text_matches = len(re.findall(r"\b(?:mon|tue|wed|thu|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", content, flags=re.IGNORECASE))
            if time_matches + date_slash_matches + weekday_text_matches >= 3:
                return False
            if content.count("|") >= 3 or content.count(" - ") >= 4:
                return False
            # Prefer content containing at least one full sentence with punctuation
            if len(re.findall(r"[A-Za-z0-9].+[\.\!\?]", content)) < 1:
                return False
            return True

        results = [x for x in results if _is_valid_result(x)]

        results.sort(key=lambda x: _domain_score(x.get("url", "")), reverse=True)

        def _clean_snippet(content: str, max_len: int = 300) -> str:
            content = content.strip()
            if len(content) <= max_len:
                return content
            truncated = content[:max_len]
            for end_char in [". ", "! ", "? "]:
                last_idx = truncated.rfind(end_char)
                if last_idx > int(max_len * 0.3):
                    return truncated[: last_idx + 1]
            return truncated.rsplit(" ", 1)[0] + "..."

        def _categorize_result(title: str, url: str, content: str) -> str:
            s = (title or "") + " " + (content or "")[:400]
            s = s.lower()
            path = urlparse(url).path.lower()
            # Event/schedule pages
            if any(p in path for p in ("/calendar", "/events", "/event", "/eventsingle", "/calendar/", "/event/")):
                return "Event/Schedule"
            if any(p in path for p in ("/press", "/press-release", "/statements", "/statement", "/briefing")):
                return "Briefing & Statement"
            if any(p in path for p in ("/transcript", "/speech", "/remarks", "/address")):
                return "Speech/Transcript"
            if any(k in s for k in ("opinion", "op-ed", "editorial", "commentary", "analysis")):
                return "Opinion/Commentary"
            if any(k in s for k in ("factcheck", "fact-check", "snopes", "politi", "fact check")):
                return "Fact-check"
            # fallback to News
            return "News"

        enriched = []
        for x in results[:k]:
            title = x.get("title", "")
            url = x.get("url", "")
            content = x.get("content", "")
            snippet = _clean_snippet(content)
            summary = _summarize_text(content, title)
            category = _categorize_result(title, url, content)
            enriched.append({"title": title, "url": url, "snippet": snippet, "summary": summary, "category": category})

        return enriched
    except Exception:
        return []


def run(text: str, speaker: str | None = None) -> dict:
    result = extract(text, speaker)

    # Helper: detect date-like or schedule-like entity names to suppress them
    def _is_date_like(name: str) -> bool:
        if not name:
            return False
        n = name.strip()
        # numeric date formats
        if re.search(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", n):
            return True
        if re.search(r"\b\d{4}-\d{2}-\d{2}\b", n):
            return True
        # month names with day/year
        if re.search(r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b\s+\d{1,2}(?:,\s*\d{4})?", n, flags=re.IGNORECASE):
            return True
        # weekday + date tokens
        if re.search(r"\b(?:mon|tue|wed|thu|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", n, flags=re.IGNORECASE):
            return True
        # time tokens
        if re.search(r"\b\d{1,2}:\d{2}\s*(am|pm)?\b", n, flags=re.IGNORECASE):
            return True
        # obvious placeholder tokens
        if any(tok in n for tok in ("monthfull", "deltahours", "deltaMinutes", "ampm", "[hour]", "[minute]")):
            return True
        return False

    # Filter out date-like entities from the extracted entities list
    original_entities = result.get("entities", [])
    filtered_entities = [e for e in original_entities if not _is_date_like(e.get("name", ""))]
    result["entities"] = filtered_entities

    # Remove date-like tokens from claims' related_entities lists
    for claim in result.get("claims", []):
        rels = claim.get("related_entities", []) or []
        claim["related_entities"] = [r for r in rels if not _is_date_like(r)]

    for claim in result.get("claims", []):
        try:
            claim_query = claim.get("quote") or claim["text"]
            # Anchor the search on whoever/whatever this specific claim is about
            # (its related_entities), not unconditionally the speaker - a claim can
            # be about a third party entirely (e.g. an opponent), and always
            # appending the speaker biases search results toward the speaker's
            # own coverage instead of the claim's actual subject.
            context_terms = claim.get("related_entities") or ([speaker] if speaker else [])
            claim_year = _parse_claim_year(claim.get("time_reference"))
            query = f"{claim_query} {' '.join(context_terms)}".strip()
            if claim_year is not None:
                query = f"{query} {claim_year}"
            # If the claim looks like a schedule/event (contains a time or words like "markup"/"subcommittee"),
            # bias the query toward calendars/events and government sites.
            is_schedule_like = bool(re.search(r"\b\d{1,2}:\d{2}\s*(am|pm)\b", query, flags=re.IGNORECASE) or re.search(r"\b(markup|subcommittee|hearing|meeting|schedule|calendar)\b", query, flags=re.IGNORECASE))
            if is_schedule_like:
                query = query + " calendar OR schedule OR event site:house.gov OR site:senate.gov"
            # Request a larger set and then re-rank to prioritize event/calendar pages
            sources = search_sources(query, k=6, speaker=speaker, claim_year=claim_year)
            # Re-rank sources to prefer ones that explicitly mention schedule/event tokens
            claim_tokens = [t.lower() for t in re.findall(r"[A-Za-z]+", claim_query) if len(t) > 2]
            def _source_score(s: dict) -> float:
                score = 0.0
                title = (s.get("title", "") or "").lower()
                snippet = (s.get("snippet", "") or "").lower()
                url = s.get("url", "") or ""
                # boost if title or snippet contains event-related tokens from the claim
                for tok in ("markup", "subcommittee", "hearing", "committee", "calendar", "schedule", "markup"):
                    if tok in title or tok in snippet or tok in url.lower():
                        score += 1.0
                # boost if snippet/title mentions specific numeric tokens (six, seven, 6, 7)
                for numtok in ("six", "seven", "6", "7"):
                    if numtok in title or numtok in snippet:
                        score += 0.8
                # small boost for containing any claim tokens
                for ct in claim_tokens[:10]:
                    if ct in title or ct in snippet:
                        score += 0.1
                # domain trust nudges already applied, keep that as tiebreaker
                score += _domain_score(url) * 0.01
                return score
            sources.sort(key=_source_score, reverse=True)
            # Trim to the top 3
            sources = sources[:3]
            relations = explain_relevance(claim["text"], sources)
            for s in sources:
                s["relation"] = relations.get(s["url"], "")
            claim["sources"] = sources
            
            # Calculate confidence based on sources, date, and speaker credibility
            confidence, confidence_explanation = calculate_confidence(
                claim, sources, relations, speaker=speaker
            )
            claim["confidence"] = confidence
            claim["confidence_explanation"] = confidence_explanation
        except Exception:
            claim["sources"] = []
            claim["confidence_explanation"] = "error calculating confidence"
    
    # Enrich entities with descriptions and related sources
    entities = result.get("entities", [])
    entity_descriptions = enrich_entity_descriptions(text, entities)
    
    entity_details = []
    for entity in entities:
        entity_name = entity.get("name", "")
        entity_type = entity.get("type", "")
        
        # Find related claims for this entity
        related_claims = [
            claim["text"]
            for claim in result.get("claims", [])
            if entity_name in claim.get("related_entities", [])
        ]
        
        # Search for related sources/news about this entity
        try:
            related_sources = search_entity_sources(entity_name, entity_type, k=2)
        except Exception:
            related_sources = []
        
        entity_detail = {
            "name": entity_name,
            "type": entity_type,
            "description": entity_descriptions.get(entity_name, ""),
            "related_claims": related_claims,
            "related_sources": related_sources,
        }
        entity_details.append(entity_detail)
    
    result["entity_details"] = entity_details
    return result
