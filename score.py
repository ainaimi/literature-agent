# score.py — LLM relevance scoring and paper summarization

import json
import config
import llm

SYSTEM_PROMPT = """
You are a research assistant helping a quantitative epidemiologist and statistician
evaluate new papers for relevance and importance to their work.
Your responses must be valid JSON. Be precise and concise.
""".strip()


def score_and_summarize(paper: dict, researcher_profile: str) -> dict | None:
    """
    Score a paper for relevance and generate a structured summary.

    Returns a dict with keys: score, summary_bullets, read_bullets
    Returns None if the paper should be dropped (score below threshold or no abstract).
    """
    if not paper.get("abstract", "").strip():
        return None

    prompt = f"""
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

3. Write exactly 1 bullet point explaining why THIS researcher specifically
   should read this paper. Reference their methods, domains, or research questions.
   If the score is below 6, write "N/A".

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

    try:
        response = llm.call_llm(prompt, system=SYSTEM_PROMPT)
        # Strip markdown code blocks if present
        response = response.strip()
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        result = json.loads(response.strip())

        score = int(result.get("score", 0))
        if score < config.RELEVANCE_THRESHOLD:
            return None

        return {
            "score": score,
            "summary_bullets": result.get("summary_bullets", []),
            "read_bullets": result.get("read_bullets", []),
        }

    except Exception as e:
        print(f"  [score] Failed to score '{paper['title'][:60]}...': {e}")
        return None


def score_all(papers: list[dict], researcher_profile: str) -> list[dict]:
    """
    Score all papers concurrently, attach results to each, drop papers below threshold.
    Returns list sorted by score descending, capped at TOP_N_PAPERS.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    WORKERS = 5  # concurrent LLM calls; increase if you have higher rate limits
    total = len(papers)
    scored = []
    completed = 0

    def _score_one(paper):
        return paper, score_and_summarize(paper, researcher_profile)

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
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
    top = scored[:config.TOP_N_PAPERS]
    print(f"[score] {len(scored)} papers passed threshold → keeping top {len(top)}")
    return top, len(scored)
