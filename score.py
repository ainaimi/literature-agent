# score.py — LLM relevance scoring and paper summarization

import json

from models import DEFAULT_PERSONA


def build_system_prompt(persona: str) -> str:
    # With the default persona this renders byte-identically to the prompt the
    # single-user tool always used — guarded by a golden test. Don't reflow.
    return f"""
You are a research assistant helping {persona}
evaluate new papers for relevance and importance to their work. Address the
researcher directly in the second person ("you"/"your"), never by name and never in
the third person.
Your responses must be valid JSON. Be precise and concise.
""".strip()


def build_user_prompt(paper: dict, researcher_profile: str, *,
                      example_name: str) -> str:
    # example_name appears only inside the negative example teaching the model
    # not to use the researcher's name; per-tenant it becomes their surname.
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
   (no "the researcher", no "This paper addresses {example_name}'s interests"; instead
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


def score_and_summarize(paper: dict, researcher_profile: str, *,
                        llm_call, threshold: int, system_prompt: str,
                        example_name: str) -> dict | None:
    """
    Score a paper for relevance and generate a structured summary.

    Returns a dict with keys: score, summary_bullets, read_bullets
    Returns None if the paper should be dropped (score below threshold or no abstract).
    """
    if not paper.get("abstract", "").strip():
        return None

    prompt = build_user_prompt(paper, researcher_profile,
                               example_name=example_name)

    try:
        response = llm_call(prompt, system=system_prompt)
        # Strip markdown code blocks if present
        response = response.strip()
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        result = json.loads(response.strip())

        score = int(result.get("score", 0))
        if score < threshold:
            return None

        return {
            "score": score,
            "summary_bullets": result.get("summary_bullets", []),
            "read_bullets": result.get("read_bullets", []),
        }

    except Exception as e:
        print(f"  [score] Failed to score '{paper['title'][:60]}...': {e}")
        return None


def score_all(papers: list[dict], researcher_profile: str, *,
              llm_call, threshold: int, top_n: int,
              persona: str = DEFAULT_PERSONA, example_name: str = "Naimi",
              workers: int = 5) -> tuple[list[dict], list[dict]]:
    """
    Score all papers concurrently, attach results to each, drop papers below threshold.
    Returns (top, all_passed): `top` is the top top_n papers for the email digest;
    `all_passed` is every paper that passed the threshold, sorted by score descending
    (used for the full-list attachment). Both lists share the same dicts.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    system_prompt = build_system_prompt(persona)
    total = len(papers)
    scored = []
    completed = 0

    def _score_one(paper):
        return paper, score_and_summarize(paper, researcher_profile,
                                          llm_call=llm_call,
                                          threshold=threshold,
                                          system_prompt=system_prompt,
                                          example_name=example_name)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_score_one, paper): paper for paper in papers}
        for future in as_completed(futures):
            completed += 1
            try:
                paper, result = future.result()
                status = f"score={result['score']}" if result else "dropped"
                print(f"  [score] {completed}/{total}: {paper['title'][:60]}... [{status}]")
                if result is not None:
                    paper["score"] = result["score"]
                    paper["summary_bullets"] = result["summary_bullets"]
                    paper["read_bullets"] = result["read_bullets"]
                    scored.append(paper)
            except Exception as e:
                paper = futures[future]
                print(f"  [score] {completed}/{total}: {paper['title'][:60]}... [error: {e}]")

    scored.sort(key=lambda p: p["score"], reverse=True)
    top = scored[:top_n]
    print(f"[score] {len(scored)} papers passed threshold → keeping top {len(top)}")
    return top, scored
