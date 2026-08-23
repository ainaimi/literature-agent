# profile.py — builds and caches your researcher relevance profile
# from files in the interests/ folder.

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

import config
import llm


# ─── Text extraction ─────────────────────────────────────────────────────────

def _extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    try:
        if suffix == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        elif suffix == ".docx":
            from docx import Document
            doc = Document(str(path))
            return "\n".join(p.text for p in doc.paragraphs)
        elif suffix in (".tex", ".txt", ".md"):
            return path.read_text(encoding="utf-8", errors="ignore")
        else:
            return ""
    except Exception as e:
        print(f"  [profile] Could not read {path.name}: {e}")
        return ""


def _collect_texts(interests_dir: Path) -> dict[str, str]:
    """Return {filename: extracted_text} for all readable files."""
    texts = {}
    for f in sorted(interests_dir.iterdir()):
        if f.is_file() and not f.name.startswith("."):
            text = _extract_text(f)
            if text.strip():
                texts[f.name] = text[:8000]  # cap per file to keep prompt reasonable
    return texts


# ─── Cache management ────────────────────────────────────────────────────────

def _folder_hash(interests_dir: Path) -> str:
    """Hash of all filenames + modification times — changes if anything is added/modified."""
    parts = []
    for f in sorted(interests_dir.iterdir()):
        if f.is_file() and not f.name.startswith("."):
            parts.append(f"{f.name}:{f.stat().st_mtime}")
    return hashlib.md5("|".join(parts).encode()).hexdigest()


def _load_cache() -> dict | None:
    cache_path = Path(config.PROFILE_CACHE_FILE)
    if not cache_path.exists():
        return None
    try:
        return json.loads(cache_path.read_text())
    except Exception:
        return None


def _save_cache(profile_text: str, folder_hash: str):
    cache = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "folder_hash": folder_hash,
        "profile": profile_text,
    }
    Path(config.PROFILE_CACHE_FILE).write_text(json.dumps(cache, indent=2))


def _cache_is_fresh(cache: dict, current_hash: str) -> bool:
    if cache.get("folder_hash") != current_hash:
        return False  # files have changed
    generated_at = datetime.fromisoformat(cache["generated_at"])
    age_days = (datetime.now(timezone.utc) - generated_at).days
    return age_days < config.PROFILE_MAX_AGE_DAYS


# ─── Profile generation ──────────────────────────────────────────────────────

def _generate_profile(texts: dict[str, str]) -> str:
    """Ask the LLM to summarize the researcher's interests from their papers."""
    combined = "\n\n---\n\n".join(
        f"FILE: {name}\n{text}" for name, text in texts.items()
    )
    prompt = f"""
The following are excerpts from papers written by or collected by a researcher.
Read them and write a concise researcher profile (250–350 words) that captures:
- Their core methodological interests and expertise
- The substantive health/scientific domains they work in
- The specific questions or intersections they tend to focus on
- Any distinctive approaches or frameworks they use

This profile will be used to judge the relevance of new papers, so be specific
about methods, populations, and study designs — not just broad topic labels.

PAPERS:
{combined}

Write only the profile text. No headers, no bullet points.
""".strip()

    print("  [profile] Generating relevance profile from interests/ folder...")
    return llm.call_llm(prompt)


# ─── Public interface ────────────────────────────────────────────────────────

def get_profile() -> str:
    """
    Return the researcher's relevance profile.
    Uses cached version if interests/ files haven't changed and cache isn't stale.
    Regenerates otherwise.
    """
    interests_dir = Path(config.INTERESTS_DIR)
    real_files = []
    if interests_dir.exists():
        real_files = [f for f in interests_dir.iterdir()
                      if f.is_file() and not f.name.startswith(".")]
    cache = _load_cache()

    # No local papers to profile from — e.g. a headless / cloud run where the
    # interests/ PDFs are gitignored and therefore absent. Fall back to a
    # previously generated cache if one is present (the GitHub Actions workflow
    # restores it from an encrypted secret); otherwise use topic-only scoring.
    if not real_files:
        if cache and cache.get("profile"):
            print("  [profile] No interests/ files present; using restored cache.")
            return cache["profile"]
        return "(No papers found in interests/ folder — using topic-only relevance scoring.)"

    current_hash = _folder_hash(interests_dir)

    if cache and _cache_is_fresh(cache, current_hash):
        print("  [profile] Using cached relevance profile.")
        return cache["profile"]

    # Regenerate
    texts = _collect_texts(interests_dir)
    if not texts:
        return "(Could not extract text from any file in interests/ folder.)"

    profile = _generate_profile(texts)
    _save_cache(profile, current_hash)
    print("  [profile] Profile saved to cache.")
    return profile
