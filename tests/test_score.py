# Tests for score.py — prompt golden tests (byte-equality with the historical
# prompts) and score_all behavior with a stubbed LLM.

import json

import score
from models import DEFAULT_PERSONA

# The system prompt exactly as it appeared in score.py before the refactor.
GOLDEN_SYSTEM_PROMPT = """
You are a research assistant helping a quantitative epidemiologist and statistician
evaluate new papers for relevance and importance to their work. Address the
researcher directly in the second person ("you"/"your"), never by name and never in
the third person.
Your responses must be valid JSON. Be precise and concise.
""".strip()

PAPER = {
    "title": "Doubly robust estimation under outcome misclassification",
    "authors": "Smith A, Jones B",
    "year": 2026,
    "source": "pubmed",
    "abstract": "We propose a doubly robust estimator.",
}


def _golden_user_prompt(paper, researcher_profile):
    # The user prompt exactly as the pre-refactor code built it (surname literal).
    return f"""
RESEARCHER PROFILE:
{researcher_profile}

PAPER:
Title: {paper['title']}
Authors: {paper.get('authors', 'Unknown')}
Year: {paper.get('year', 'Unknown')}
Source: {paper.get('source', '')}
Abstract: {paper['abstract']}

TASK:
1. Score this paper's relevance to the researcher on a scale of 0–10, where:
   - 0–3: Not relevant (wrong field, wrong methods, wrong population)
   - 4–5: Tangentially relevant
   - 6–7: Relevant — touches their methods or domain
   - 8–9: Highly relevant — directly in their area of expertise or active research
   - 10: Essential — they must read this

2. Write exactly 4 bullet points summarizing the paper's main contributions.
   Each bullet: 1–2 sentences. Be specific. No filler.

3. Write exactly 1 bullet point explaining why you specifically should read this
   paper, referencing your own methods, domains, or research questions. Address the
   reader directly as "you"/"your" — never by name and never in the third person
   (no "the researcher", no "This paper addresses Naimi's interests"; instead
   "This paper directly addresses your interest in ..."). If the score is below 6,
   write "N/A".

Respond with valid JSON only, in this exact format:
{{
  "score": <integer 0–10>,
  "summary_bullets": [
    "<bullet 1>",
    "<bullet 2>",
    "<bullet 3>",
    "<bullet 4>"
  ],
  "read_bullets": [
    "<bullet 1>"
  ]
}}
""".strip()


def test_system_prompt_golden():
    assert score.build_system_prompt(DEFAULT_PERSONA) == GOLDEN_SYSTEM_PROMPT


def test_user_prompt_golden():
    profile = "A methods-focused epidemiologist."
    assert (score.build_user_prompt(PAPER, profile, example_name="Naimi")
            == _golden_user_prompt(PAPER, profile))


def test_user_prompt_interpolates_example_name():
    prompt = score.build_user_prompt(PAPER, "p", example_name="Curie")
    assert "This paper addresses Curie's interests" in prompt
    assert "Naimi" not in prompt


# ─── score_and_summarize / score_all with stubbed LLM ────────────────────────

def _llm_returning(payload):
    def llm_call(prompt, system=""):
        return payload
    return llm_call


GOOD_RESULT = json.dumps({"score": 8, "summary_bullets": ["a", "b", "c", "d"],
                          "read_bullets": ["r"]})


def test_score_and_summarize_parses_result():
    out = score.score_and_summarize(
        PAPER, "profile", llm_call=_llm_returning(GOOD_RESULT),
        threshold=6, system_prompt="sys", example_name="Naimi")
    assert out == {"score": 8, "summary_bullets": ["a", "b", "c", "d"],
                   "read_bullets": ["r"]}


def test_score_and_summarize_strips_code_fences():
    fenced = f"```json\n{GOOD_RESULT}\n```"
    out = score.score_and_summarize(
        PAPER, "profile", llm_call=_llm_returning(fenced),
        threshold=6, system_prompt="sys", example_name="Naimi")
    assert out["score"] == 8


def test_score_and_summarize_drops_below_threshold():
    low = json.dumps({"score": 4, "summary_bullets": [], "read_bullets": []})
    assert score.score_and_summarize(
        PAPER, "profile", llm_call=_llm_returning(low),
        threshold=6, system_prompt="sys", example_name="Naimi") is None


def test_score_and_summarize_skips_missing_abstract():
    def must_not_call(prompt, system=""):
        raise AssertionError("no LLM call expected")
    assert score.score_and_summarize(
        {"title": "T", "abstract": " "}, "profile", llm_call=must_not_call,
        threshold=6, system_prompt="sys", example_name="Naimi") is None


def test_score_all_sorts_cuts_topn_and_mutates_in_place():
    papers = [
        {"title": f"Paper {i}", "abstract": f"Abstract {i}"} for i in range(4)
    ]
    scores = {"Paper 0": 6, "Paper 1": 9, "Paper 2": 3, "Paper 3": 8}

    def llm_call(prompt, system=""):
        for title, s in scores.items():
            if f"Title: {title}\n" in prompt:
                return json.dumps({"score": s, "summary_bullets": ["x"] * 4,
                                   "read_bullets": ["y"]})
        raise AssertionError("unknown paper")

    top, all_scored = score.score_all(
        papers, "profile", llm_call=llm_call, threshold=6, top_n=2)

    assert [p["title"] for p in all_scored] == ["Paper 1", "Paper 3", "Paper 0"]
    assert [p["title"] for p in top] == ["Paper 1", "Paper 3"]
    assert top[0] is all_scored[0]          # shared dict objects
    assert papers[1]["score"] == 9          # input dicts mutated in place
    assert "score" not in papers[2]         # dropped paper untouched
