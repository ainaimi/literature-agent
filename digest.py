# digest.py — formats the weekly digest (plain text for terminal, HTML for email)

from datetime import datetime


def format_digest(papers: list[dict], total_searched: int = 0, passed_count: int = 0) -> str:
    """Plain-text digest for terminal output (dry-run)."""
    today = datetime.now().strftime("%B %d, %Y")
    stats = f"{total_searched} searched · {passed_count} relevant · {len(papers)} shown"
    lines = [f"Weekly Literature Digest — {today}", stats, ""]

    for i, paper in enumerate(papers, 1):
        title   = paper.get("title", "No title")
        url     = paper.get("url", "")
        authors = paper.get("authors", "")
        year    = paper.get("year", "")
        source  = paper.get("source", "").replace("_", " ").title()
        cluster = paper.get("cluster", "").replace("_", " ").title()
        score   = paper.get("score", "?")
        summary_bullets = paper.get("summary_bullets", [])
        read_bullets    = paper.get("read_bullets", [])

        lines.append(f"{i}. {title}")
        if url:
            lines.append(f"   {url}")
        lines.append(f"   {authors[:80]}{'…' if len(authors) > 80 else ''}")
        lines.append(f"   {year} · {source} · {cluster} · {score}/10")
        lines.append("")

        for b in summary_bullets:
            lines.append(f"   • {b}")
        if summary_bullets:
            lines.append("")

        if read_bullets and read_bullets[0] != "N/A":
            lines.append(f"   Why read this: {read_bullets[0]}")

        lines.append("")
        lines.append("─" * 60)
        lines.append("")

    return "\n".join(lines)


# ─── Shared HTML building blocks ─────────────────────────────────────────────

_CSS = """
    body { font-family: Georgia, 'Times New Roman', serif; max-width: 680px;
           margin: 0 auto; padding: 24px 16px; color: #1a1a1a; background: #fff; }
    h1   { font-size: 1.3em; font-weight: bold; border-bottom: 2px solid #1a1a1a;
           padding-bottom: 8px; margin-bottom: 4px; }
    .date { color: #555; font-size: 0.9em; margin-bottom: 28px; }
    .paper { margin-bottom: 2.2em; padding-bottom: 2em;
             border-bottom: 1px solid #ddd; }
    .paper:last-child { border-bottom: none; }
    .num  { color: #888; font-size: 0.85em; font-family: monospace; }
    .title { font-size: 1.05em; font-weight: bold; margin: 2px 0 4px; }
    .title a { color: #1a0dab; text-decoration: none; }
    .title a:hover { text-decoration: underline; }
    .meta { font-size: 0.82em; color: #555; margin-bottom: 10px; }
    .badge { display: inline-block; background: #f0f0f0; border-radius: 3px;
             padding: 1px 6px; margin-right: 4px; font-size: 0.8em; color: #333; }
    .score { display: inline-block; background: #1a1a1a; color: #fff;
             border-radius: 3px; padding: 1px 6px; font-size: 0.8em; }
    ul   { margin: 6px 0 10px; padding-left: 18px; }
    li   { margin-bottom: 5px; line-height: 1.55; font-size: 0.95em; }
    .why-label { font-size: 0.8em; font-weight: bold; text-transform: uppercase;
                 color: #555; letter-spacing: 0.05em; margin-top: 10px; }
    .why { font-size: 0.92em; line-height: 1.55; color: #222;
           border-left: 3px solid #ccc; padding-left: 10px; margin: 4px 0 0; }
    """


def _paper_block_html(i: int, paper: dict) -> str:
    """Render one paper as an HTML block — shared by the email digest and the
    full-list attachment so both stay visually identical."""
    title   = paper.get("title", "No title")
    url     = paper.get("url", "")
    authors = paper.get("authors", "Unknown")
    year    = paper.get("year", "")
    source  = paper.get("source", "").replace("_", " ").title()
    cluster = paper.get("cluster", "").replace("_", " ").title()
    score   = paper.get("score", "?")
    summary_bullets = paper.get("summary_bullets", [])
    read_bullets    = paper.get("read_bullets", [])

    title_html = (f'<a href="{url}">{_esc(title)}</a>' if url else _esc(title))
    authors_short = authors[:100] + ("…" if len(authors) > 100 else "")

    bullets_html = "".join(f"<li>{_esc(b)}</li>" for b in summary_bullets)
    why_html = ""
    if read_bullets and read_bullets[0] != "N/A":
        why_html = (f'<div class="why-label">Why read this</div>'
                    f'<div class="why">{_esc(read_bullets[0])}</div>')

    return f"""<div class="paper">
  <div class="num">#{i}</div>
  <div class="title">{title_html}</div>
  <div class="meta">
    {_esc(authors_short)}<br>
    <span class="badge">{_esc(source)}</span>
    <span class="badge">{_esc(cluster)}</span>
    <span class="badge">{year}</span>
    <span class="score">{score}/10</span>
  </div>
  <ul>{bullets_html}</ul>
  {why_html}
</div>
"""


def _html_page(heading: str, date: str, stats: str, body: str,
               note: str = "", title: str = "") -> str:
    """Wrap rendered paper blocks in a full HTML document with shared styling."""
    note_html = f'<div class="date">📎 {_esc(note)}</div>\n' if note else ""
    page_title = title or heading
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{_esc(page_title)}</title><style>{_CSS}</style></head>
<body>
<h1>{_esc(heading)}</h1>
<div class="date">{date}</div>
<div class="date">{stats}</div>
{note_html}{body}
</body></html>"""


def format_digest_html(papers: list[dict], total_searched: int = 0,
                       passed_count: int = 0, full_list_note: str = "", *,
                       threshold: int = 6) -> str:
    """HTML digest for email delivery — the top-N papers, with an optional note
    pointing at the attached full list."""
    today = datetime.now().strftime("%B %d, %Y")
    stats = (f"{total_searched} papers searched &nbsp;·&nbsp; "
             f"{passed_count} passed threshold (≥{threshold}/10) &nbsp;·&nbsp; "
             f"top {len(papers)} shown")
    body = "\n".join(_paper_block_html(i, p) for i, p in enumerate(papers, 1))
    return _html_page("Weekly Literature Digest", today, stats, body,
                      note=full_list_note)


def format_full_list_html(papers: list[dict], total_searched: int = 0, *,
                          threshold: int = 6) -> str:
    """Standalone HTML page listing every paper that passed the threshold —
    attached to the email so the full set is available beyond the top-N digest."""
    today = datetime.now().strftime("%B %d, %Y")
    stats = (f"{total_searched} papers searched &nbsp;·&nbsp; "
             f"{len(papers)} passed threshold (≥{threshold}/10) &nbsp;·&nbsp; "
             f"all {len(papers)} shown")
    body = "\n".join(_paper_block_html(i, p) for i, p in enumerate(papers, 1))
    return _html_page("Full Scored List", today, stats, body,
                      title=f"Full Scored List — {today}")


def _esc(text: str) -> str:
    """Minimal HTML escaping."""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))
