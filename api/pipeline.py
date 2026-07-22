import concurrent.futures
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
        "jurisdiction": {
            "type": "string",
            "description": (
                "The single US state this text is primarily about (e.g. 'North Carolina'), "
                "or 'federal' for national-level text, or 'unspecified' if it genuinely can't "
                "be determined. The text itself may never name the state explicitly - infer it "
                "from context using your own knowledge, e.g. who the speaker is and what office "
                "they hold, named local officials, agency names that are specific to one state "
                "(like a state's 'Board of Elections'), or place names mentioned in passing. "
                "This is used to anchor fact-checking searches to the correct state, so guess "
                "your best single answer rather than leaving it vague."
            ),
        },
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
                    "materiality": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "description": (
                            "How much this claim matters to the speaker's argument - not how "
                            "interesting or colorful it is. Ask: if this specific claim were proven "
                            "false, would it substantially weaken the speaker's point? 0.8-1.0 = "
                            "central to the argument, which falls apart or is seriously undercut if "
                            "this is false. 0.4-0.7 = a relevant supporting detail that weakens the "
                            "argument somewhat if false. 0.0-0.3 = a detail whose truth barely "
                            "matters to the point being made, even though it's technically checkable."
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
                    "materiality",
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
    "required": ["summary", "jurisdiction", "topics", "key_ideas", "claims", "entities"],
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

IINCLUDE a statement only if it asserts a concrete, specific factual claim that could reasonably be verified using evidence such as official records, legislation, government data, court documents, voting records, direct quotations, public statements, or reliable reporting.

A claim is a concrete factual assertion that conveys specific information about the world and 
whose truth or falsity would materially affect a reader's understanding of a public issue. Do not extract
statements that merely describe generalized conditions, personal beliefs, political messaging, or rhetorical framing.

Examples of claims to INCLUDE:
- An event occurred or a condition exists (e.g. "we have had closures").
- A person or organization performed a specific, identifiable action or made a specific decision (e.g. "Trump called Abbott", "Federal agents demanded records", "the Department of Education introduced a regulation").
- A claim about a bill, law, regulation, or policy should only be extracted if the statement makes a factual assertion about its contents, status, sponsors, effects, passage, implementation, or other objectively verifiable characteristics. Merely mentioning or advocating for a bill does not constitute a claim.
- A person holds or held a particular office or role.
- A statistic, quantity, date, ranking, comparison, or measurable trend is stated as fact.
- A claim about a person's voting record, public position, sponsorship of legislation, fundraising, finances, criminal proceedings, government actions, or official conduct.
- A direct factual allegation about a public official or organization (e.g. "James Talarico opposes voter ID", "Trump received a $400 million jet").

Extract the claim even if it is disputed, misleading, or likely false—the question is whether the factual assertion itself can be verified.

If a sentence mixes factual content with opinion, extract only the factual portion.

If a claim's own existence is uncertain (for example, a bill name may be garbled by transcription), still extract it but assign a lower confidence score.

EXCLUDE a statement if it is only:
- An opinion, insult, value judgment, or subjective characterization (e.g. "too radical", "devastating", "the most corrupt president").
- Campaign messaging, slogans, or political branding (e.g. "Make America Great Again", "America is back").
- A broad statement of effort, intent, mission, or policy objective rather than a discrete factual assertion (e.g. "working every day to lower costs", "fighting for free and fair elections", "protecting the American people", "securing the border", "delivering results").
- A promise or commitment about future action (e.g. "I will continue to stand with him", "we will fight for...").
- A prediction or speculation about the future with no concrete factual anchor (e.g. "we will have fewer providers", "AI may replace jobs").
- A hypothetical or conditional example (e.g. "if you have access to a nurse practitioner...").
- A rhetorical exhortation or advocacy statement (e.g. "let's be smart", "focus on winning", "we must...").
- A causal or policy argument stated as a generalization rather than a discrete factual assertion (e.g. "that's how we drive down costs").
- A question, including rhetorical or interview questions.
- A generic observation or truism that carries little factual content (e.g. "people graduate from high school and college").
- A subjective characterization of public sentiment or mood (e.g. "there's a lot of anxiety around AI").
- Speculative attribution of motive, intent, or causation without supporting evidence (e.g. "Trump is targeting me because I'm running for president", "some of that anxiety is due to AI").

When deciding whether to extract a statement, ask:
**Would an independent fact-checking organization realistically write a fact check evaluating this specific statement?**

Prefer claims that a professional fact-checking organization would realistically devote resources to verifying because 
they materially affect public understanding of politics, policy, government, elections, economics, public safety,
 or other matters of public interest. Do not extract incidental background facts whose truth is obvious, routine, or unlikely to be disputed.

If the answer is no because the statement is too vague, aspirational, rhetorical, or subjective, do not extract it as a claim.
## Work top-down from key ideas, not bottom-up from every sentence

Do not scan the text line by line looking for anything technically checkable. Instead:
1. First decide the 3-6 key ideas - the actual points the text is trying to make.
2. Then, for each key idea, find the claim(s) that most directly support or assert it.
3. Skip statements that are merely incidental context, scene-setting, or asides - even if they contain a verifiable fact - if they don't support one of the key ideas. A passing mention that isn't part of what the speaker is actually trying to argue is not worth flagging.

## Materiality: score how much each claim matters to the argument

Being checkable and being relevant to a key idea isn't enough on its own - claims also need a materiality score reflecting how much their truth matters. The test: if this specific claim were proven false, would it substantially weaken the speaker's point?

Example - a speech arguing a public official is corrupt:
- "He received a $400 million private jet as a gift." -> materiality ~0.9. If false, the corruption argument weakens a lot - this is central.
- "Federal agents knocked on former employees' doors." -> materiality ~0.5. Somewhat relevant supporting detail, but the core argument doesn't hinge on it.
- "He watches everything." -> materiality ~0.1. Whether literally true or not barely matters to the argument - it's color, not substance.

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
        "refer to (e.g. resolve pronouns like 'I' or 'we' to this speaker) and when writing context/explanation. "
        "Also use your own knowledge of who this person is (e.g. what office they hold and in which state) "
        "when inferring the jurisdiction field below, even though the text itself may never name the state.\n\n"
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
                "Also determine the jurisdiction (the US state, or 'federal', this text is "
                "primarily about) using contextual clues and your own knowledge - named "
                "officials' known roles, state-specific agency names, place names mentioned "
                "in passing - even if no state is ever named explicitly in the text. "
                "Then extract a concise summary, topics, and verifiable factual claims that "
                "each directly support one of those key ideas, applying the claim rules from "
                "the system prompt strictly. Ignore incidental context and claims that aren't "
                "relevant to the key ideas, even if technically verifiable - focus on quality "
                "and relevance over exhaustively listing everything checkable. Also extract "
                "named entities. For each claim, include a verbatim quote of the source "
                "sentence, a brief explanation of what it asserts and why it's checkable, "
                "surrounding context, the related entities involved, the year/time period the "
                "claim's underlying event actually happened (using your own knowledge of when "
                "named laws/programs occurred if the text doesn't state it), a materiality score "
                "per the system prompt's rules (how much the argument depends on this claim being "
                "true, not how interesting it is), and a confidence score. The quote field must be "
                "an exact character-for-character substring of the original text below.\n\n"
                f"---\n{text}\n---"
            ),
        },
    ]

    last_error: Exception = RuntimeError("Model did not return structured output")
    for _ in range(3):
        resp = client.chat.completions.create(
            model=settings.openai_model,
            max_tokens=8192,
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


SELECTED_CLAIM_SCHEMA = {
    "type": "object",
    "properties": {
        "is_claim": {
            "type": "boolean",
            "description": (
                "True only if the selected sentence is a concrete, verifiable factual claim "
                "that materially supports one of the text's key ideas."
            ),
        },
        "reason": {
            "type": "string",
            "description": (
                "If is_claim is false, explain briefly why (e.g. opinion, rhetorical framing, "
                "question, too vague, or not relevant to the argument)."
            ),
        },
        "claim": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "explanation": {"type": "string"},
                "context": {"type": "string"},
                "related_entities": {"type": "array", "items": {"type": "string"}},
                "time_reference": {"type": "string"},
                "materiality": {"type": "number", "minimum": 0, "maximum": 1},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": [
                "text",
                "explanation",
                "context",
                "related_entities",
                "time_reference",
                "materiality",
                "confidence",
            ],
        },
    },
    "required": ["is_claim", "reason", "claim"],
}

SELECTED_CLAIM_TOOL = {
    "type": "function",
    "function": {
        "name": "record_selected_claim",
        "description": "Validate and structure a user-selected sentence from the original text.",
        "parameters": SELECTED_CLAIM_SCHEMA,
    },
}


def analyze_selected_claim(text: str, selected_text: str, speaker: str | None = None) -> dict:
    selected = (selected_text or "").strip()
    if len(selected) < 8:
        return {"is_claim": False, "reason": "Selection is too short to evaluate.", "claim": None}

    def _normalize_ws(s: str) -> str:
        return re.sub(r"\s+", " ", s or "").strip().lower()

    if _normalize_ws(selected) not in _normalize_ws(text):
        return {"is_claim": False, "reason": "Please select text directly from the original transcript.", "claim": None}

    speaker_line = (
        f"The speaker of the full text is {speaker}. Use that for pronouns like I/we.\n\n" if speaker else ""
    )
    resp = client.chat.completions.create(
        model=settings.openai_model,
        max_tokens=1200,
        tools=[SELECTED_CLAIM_TOOL],
        tool_choice={"type": "function", "function": {"name": "record_selected_claim"}},
        messages=[
            {
                "role": "system",
                "content": (
                    "You decide whether a selected sentence is a claim worth fact-checking and return "
                    "structured output via the record_selected_claim tool. Always call the tool exactly once.\n\n"
                    + CLAIM_RULES
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{speaker_line}"
                    "Given the full political text and one user-selected sentence, decide if the selected "
                    "sentence is a concrete factual claim that is both verifiable and materially relevant "
                    "to the text's argument. If it is not, set is_claim=false and explain why in reason.\n\n"
                    f"Full text:\n---\n{text}\n---\n\n"
                    f"Selected sentence:\n---\n{selected}\n---"
                ),
            },
        ],
    )
    msg = resp.choices[0].message
    if not msg.tool_calls:
        return {"is_claim": False, "reason": "Could not evaluate selected sentence.", "claim": None}
    data = json.loads(msg.tool_calls[0].function.arguments)
    if not data.get("is_claim"):
        reason = (data.get("reason") or "").strip() or "Selected text is not a verifiable, relevant factual claim."
        return {"is_claim": False, "reason": reason, "claim": None}

    claim = data.get("claim") or {}
    claim["text"] = (claim.get("text") or selected).strip()
    claim["quote"] = selected
    claim["explanation"] = (claim.get("explanation") or "").strip()
    claim["context"] = (claim.get("context") or "").strip()
    claim["related_entities"] = claim.get("related_entities") or []
    claim["time_reference"] = (claim.get("time_reference") or "unspecified").strip()
    claim["materiality"] = float(claim.get("materiality", 0.5))
    claim["confidence"] = float(claim.get("confidence", 0.5))
    _fact_check_claim(claim, speaker)
    return {"is_claim": True, "reason": "", "claim": claim}


SOCIAL_MEDIA_DOMAINS = [
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "tiktok.com",
    "reddit.com",
    "pinterest.com",
    "threads.net",
    "threads.com",
    "youtube.com",
    "youtu.be",
    "linkedin.com",
    "bsky.app",
    "truthsocial.com",
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
    # A domain containing the speaker's own name is almost always their
    # personal, campaign, or official site rather than independent
    # journalism - real news outlets brand their domain after their own
    # outlet, not the politician they're covering. Only the domain is
    # checked (not the path), so a news article whose URL path happens to
    # mention the speaker still passes through.
    return any(slug in netloc for slug in speaker_slugs)


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


_US_STATES = [
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine",
    "maryland", "massachusetts", "michigan", "minnesota", "mississippi",
    "missouri", "montana", "nebraska", "nevada", "new hampshire", "new jersey",
    "new mexico", "new york", "north carolina", "north dakota", "ohio",
    "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina",
    "south dakota", "tennessee", "texas", "utah", "vermont", "virginia",
    "washington", "west virginia", "wisconsin", "wyoming",
]


def _mentioned_state(*texts: str | None) -> str | None:
    """Find the first US state name mentioned across the given texts, checked in order."""
    for text in texts:
        t = (text or "").lower()
        for state in _US_STATES:
            if re.search(rf"\b{re.escape(state)}\b", t):
                return state
    return None


def _mentions_other_state(url: str, claim_state: str | None) -> bool:
    """True if the source's domain names a different US state than the claim is about.

    A claim about North Carolina's election rules citing Ohio's official
    elections site isn't lower-relevance evidence - it's evidence for the
    wrong state entirely, so this is a hard exclude rather than a scoring nudge.
    """
    if not claim_state:
        return False
    netloc = urlparse(url.lower()).netloc
    claim_compact = claim_state.replace(" ", "")
    for state in _US_STATES:
        if state == claim_state:
            continue
        compact = state.replace(" ", "")
        if compact in netloc and claim_compact not in netloc:
            return True
    return False


def search_sources(query: str, k: int = 3, speaker: str | None = None, claim_year: int | None = None) -> list[dict]:
    if not settings.tavily_api_key:
        return []
    r = httpx.post(
        "https://api.tavily.com/search",
        json={
            "api_key": settings.tavily_api_key,
            "query": query,
            "max_results": k * 4,
            "search_depth": "advanced",
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
    
    # Factor 1: Source verification (0-0.35)
    source_factor_desc = ""
    if sources:
        supporting_count = sum(
            1 for url, relation in source_relations.items()
            if relation and any(w in relation.lower() for w in ["support", "confirm", "verify", "corroborate", "affirm"])
        )
        contradicting_count = sum(
            1 for url, relation in source_relations.items()
            if relation and any(w in relation.lower() for w in ["contradict", "dispute", "refute", "deny", "challenge"])
        )
        
        if contradicting_count > 0:
            source_boost = -0.25
            source_factor_desc = f"Contradicted by {contradicting_count} article(s)"
        elif supporting_count >= len(sources):
            source_boost = 0.35
            source_factor_desc = f"Supported by all {len(sources)} article(s)"
        elif supporting_count > 0:
            source_boost = 0.15 + (supporting_count / len(sources)) * 0.2
            source_factor_desc = f"Supported by {supporting_count} out of {len(sources)} article(s)"
        else:
            source_boost = 0.05
            source_factor_desc = f"Mentioned in {len(sources)} article(s), relationship unclear"
        confidence += source_boost
        factors.append(f"• {source_factor_desc}")
    else:
        factors.append("• No corroborating articles found")
    
    # Factor 2: Date relevance (0-0.25)
    claim_year = _parse_claim_year(claim.get("time_reference"))
    if claim_year:
        from datetime import datetime
        current_year = datetime.now().year
        years_old = current_year - claim_year
        
        if years_old <= 1:
            date_boost = 0.25
            date_desc = f"Recent claim (event from {claim_year})"
        elif years_old <= 3:
            date_boost = 0.15
            date_desc = f"Current topic (event from {claim_year})"
        elif years_old <= 7:
            date_boost = 0.08
            date_desc = f"Moderately recent (event from {claim_year})"
        elif years_old <= 10:
            date_boost = 0.03
            date_desc = f"Older claim (event from {claim_year})"
        else:
            date_boost = 0.0
            date_desc = f"Historical claim (event from {claim_year})"
        confidence += date_boost
        factors.append(f"• {date_desc}")
    else:
        factors.append("• Timing not specified")
    
    # Factor 3: Speaker credibility (0-0.25)
    if speaker:
        credibility_score = _assess_speaker_credibility(speaker)
        speaker_desc = f"Speaker credibility: {credibility_score['level']}"
        confidence += credibility_score['boost']
        factors.append(f"• {speaker_desc}")
    
    # Clamp to [0, 1]
    confidence = max(0.0, min(1.0, confidence))
    
    explanation = "\n".join(factors)
    return confidence, explanation


def _assess_speaker_credibility(speaker: str) -> dict[str, float | str]:
    """Simple heuristic for speaker credibility based on known roles/positions."""
    speaker_lower = speaker.lower()
    
    # Government officials typically have higher credibility
    if any(w in speaker_lower for w in ["senator", "congressman", "representative", "judge", "secretary", "president", "minister", "governor"]):
        return {"level": "High (Government Official)", "boost": 0.25}
    
    # Academics and researchers
    if any(w in speaker_lower for w in ["professor", "dr.", "phd", "researcher", "scientist"]):
        return {"level": "High (Academic/Expert)", "boost": 0.25}
    
    # Advocacy groups and organizations
    if any(w in speaker_lower for w in ["director", "executive", "founder", "ceo", "cto"]):
        return {"level": "Medium (Organization Leader)", "boost": 0.12}
    
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

        def _enrich(x: dict) -> dict:
            title = x.get("title", "")
            url = x.get("url", "")
            content = x.get("content", "")
            return {
                "title": title,
                "url": url,
                # No LLM summarization call here - the UI already falls back to
                # this snippet when summary is empty, so skip the extra round trip.
                "snippet": _clean_snippet(content),
                "summary": "",
                "category": _categorize_result(title, url, content),
            }

        return [_enrich(x) for x in results[:k]]
    except Exception:
        return []


MAX_PARALLEL_WORKERS = 8


def _is_date_like(name: str) -> bool:
    """Detect date-like or schedule-like entity names so they can be filtered out."""
    if not name:
        return False
    n = name.strip()
    # numeric date formats
    if re.search(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", n):
        return True
    if re.search(r"\b\d{4}-\d{2}-\d{2}\b", n):
        return True
    # month names with day/year
    if re.search(
        r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?"
        r"|sep(?:t(?:ember)?)|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b\s+\d{1,2}(?:,\s*\d{4})?",
        n,
        flags=re.IGNORECASE,
    ):
        return True
    # weekday + date tokens
    if re.search(
        r"\b(?:mon|tue|wed|thu|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        n,
        flags=re.IGNORECASE,
    ):
        return True
    # time tokens
    if re.search(r"\b\d{1,2}:\d{2}\s*(am|pm)?\b", n, flags=re.IGNORECASE):
        return True
    # obvious placeholder tokens
    if any(tok in n for tok in ("monthfull", "deltahours", "deltaMinutes", "ampm", "[hour]", "[minute]")):
        return True
    return False


_STOPWORDS = frozenset({
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "her", "was",
    "one", "our", "out", "get", "has", "him", "his", "how", "new", "now", "see",
    "two", "way", "who", "did", "its", "let", "put", "say", "she", "too", "use",
    "under", "over", "each", "with", "that", "this", "from", "have", "had",
    "will", "would", "could", "should", "than", "then", "into", "onto", "upon",
    "when", "where", "which", "while", "been", "being", "does", "doing", "such",
    "some", "any", "more", "most", "other", "said", "says",
})


def _fact_check_claim(claim: dict, speaker: str | None, jurisdiction: str | None = None) -> None:
    """Search for and rank sources for one claim, then score confidence. Mutates claim in place."""
    try:
        claim_query = claim.get("quote") or claim["text"]
        # Search on the claim's distinctive keywords, not the raw sentence -
        # rhetorical/opinion-laden phrasing ("is doubling down on his failed
        # tariff strategy — and sticking Americans with the bill") tanks
        # Tavily's relevance scoring (observed ~0.2 for the full sentence vs.
        # ~0.85+ for the same claim reduced to content words), likely because
        # a keyword search engine treats the extra rhetorical words as noise
        # to match against rather than signal. Dedup while preserving order.
        claim_tokens = list(dict.fromkeys(
            t.lower() for t in re.findall(r"[A-Za-z]+", claim_query)
            if len(t) > 2 and t.lower() not in _STOPWORDS
        ))
        # Anchor the search on whoever/whatever this specific claim is about
        # (its related_entities), not unconditionally the speaker - a claim can
        # be about a third party entirely (e.g. an opponent), and always
        # appending the speaker biases search results toward the speaker's
        # own coverage instead of the claim's actual subject.
        context_terms = claim.get("related_entities") or ([speaker] if speaker else [])
        claim_year = _parse_claim_year(claim.get("time_reference"))
        # Prefer the document-level jurisdiction (inferred once at extraction
        # time from the model's own knowledge, e.g. recognizing the speaker as
        # a specific state's governor) since a claim's own text/context often
        # never names the state at all. Fall back to regex-detecting a state
        # name from this claim specifically only if that's unavailable.
        jurisdiction_normalized = (jurisdiction or "").strip().lower()
        claim_state = (
            jurisdiction_normalized if jurisdiction_normalized in _US_STATES
            else _mentioned_state(claim.get("context"), claim.get("text"), claim_query)
        )
        # Tokenize and dedup related_entities into the same flat word list as
        # claim_tokens, rather than appending raw entity phrases - otherwise
        # words already present in the quote (e.g. "Republican", "county
        # board") get restated by an overlapping entity name and end up
        # over-weighted, which made results noticeably less stable in testing.
        entity_tokens = [
            t.lower() for term in context_terms
            for t in re.findall(r"[A-Za-z]+", term)
            if len(t) > 2 and t.lower() not in _STOPWORDS
        ]
        query = " ".join(dict.fromkeys(claim_tokens + entity_tokens)).strip()
        # Only inject the state into the query text for claims that are
        # actually state/local in nature - a claim about federal policy (e.g.
        # a governor commenting on the President's tariffs) has nothing to do
        # with the speaker's own state, and appending it tanked relevance in
        # testing (0.85 -> 0.02 for a Trump tariffs claim once "massachusetts"
        # was added, since the query now searches for a combination that
        # doesn't correspond to any real coverage). The wrong-state exclusion
        # filter below still applies regardless, since it only removes sources
        # that name a *different* state and is harmless for national topics.
        is_national_topic = bool(
            re.search(r"\b(president|federal|congress|senate|white house|supreme court)\b", claim_query, flags=re.IGNORECASE)
            or any(re.search(r"\b(president|federal)\b", t, flags=re.IGNORECASE) for t in context_terms)
        )
        if claim_state and not is_national_topic:
            query = f"{query} {claim_state}"
        if claim_year is not None:
            query = f"{query} {claim_year}"
        # If the claim looks like a schedule/event (contains a time or words like "markup"/"subcommittee"),
        # bias the query toward calendars/events and government sites. Checked
        # against the original sentence, not the keyword query, since digit-based
        # time patterns like "3:00 pm" don't survive the [A-Za-z]+ tokenization above.
        is_schedule_like = bool(
            re.search(r"\b\d{1,2}:\d{2}\s*(am|pm)\b", claim_query, flags=re.IGNORECASE)
            or re.search(r"\b(markup|subcommittee|hearing|meeting|schedule|calendar)\b", claim_query, flags=re.IGNORECASE)
        )
        if is_schedule_like:
            query = query + " calendar OR schedule OR event site:house.gov OR site:senate.gov"
        # Request a larger set and then re-rank to prioritize event/calendar pages
        sources = search_sources(query, k=6, speaker=speaker, claim_year=claim_year)
        # Drop sources naming a different state than this claim is about - a
        # same-shaped-but-wrong-state .gov page isn't weaker evidence, it's
        # evidence for something else entirely.
        sources = [s for s in sources if not _mentions_other_state(s.get("url", ""), claim_state)]
        # Re-rank sources to prefer ones that explicitly mention schedule/event tokens

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
            for ct in claim_tokens:
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
        confidence, confidence_explanation = calculate_confidence(claim, sources, relations, speaker=speaker)
        claim["confidence"] = confidence
        claim["confidence_explanation"] = confidence_explanation
    except Exception:
        claim["sources"] = []
        claim["confidence_explanation"] = "error calculating confidence"


def _build_entity_detail(
    entity: dict, claims: list[dict], entity_descriptions: dict[str, str]
) -> dict:
    entity_name = entity.get("name", "")
    entity_type = entity.get("type", "")
    related_claims = [c["text"] for c in claims if entity_name in (c.get("related_entities") or [])]
    try:
        related_sources = search_entity_sources(entity_name, entity_type, k=2)
    except Exception:
        related_sources = []
    return {
        "name": entity_name,
        "type": entity_type,
        "description": entity_descriptions.get(entity_name, ""),
        "related_claims": related_claims,
        "related_sources": related_sources,
    }


def run(text: str, speaker: str | None = None) -> dict:
    result = extract(text, speaker)
    # Order by materiality (highest first) but don't cap the count - longer
    # speeches legitimately surface more claims, and a fixed cap would drop
    # real ones instead of just deprioritizing low-stakes ones in the UI.
    claims = result.get("claims", [])
    claims.sort(key=lambda c: c.get("materiality", 0), reverse=True)
    result["claims"] = claims

    # Filter out date-like entities from the extracted entities list
    original_entities = result.get("entities", [])
    result["entities"] = [e for e in original_entities if not _is_date_like(e.get("name", ""))]

    # Remove date-like tokens from claims' related_entities lists
    for claim in result["claims"]:
        rels = claim.get("related_entities", []) or []
        claim["related_entities"] = [r for r in rels if not _is_date_like(r)]

    # Fact-check claims and enrich entities concurrently rather than as two
    # sequential stages - entity descriptions/details only depend on extract()'s
    # output (claim text + related_entities, already set above), not on the
    # fact-checked claims, so there's no reason to make one wait on the other.
    entities = result["entities"]
    jurisdiction = result.get("jurisdiction")
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_PARALLEL_WORKERS) as pool:
        claim_futures = [pool.submit(_fact_check_claim, c, speaker, jurisdiction) for c in result["claims"]]
        descriptions_future = pool.submit(enrich_entity_descriptions, text, entities)

        entity_descriptions = descriptions_future.result()
        entity_futures = [
            pool.submit(_build_entity_detail, e, result["claims"], entity_descriptions) for e in entities
        ]

        for f in claim_futures:
            f.result()
        result["entity_details"] = [f.result() for f in entity_futures]

    return result
