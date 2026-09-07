# config.py — the only file you need to edit to tune the agent

# ─── LLM Provider ────────────────────────────────────────────────────────────
# Switch providers by changing these two lines.
# Supported: "anthropic" | "openai" | "ollama"
# Anthropic models: "claude-haiku-4-5-20251001" (cheap) | "claude-sonnet-4-6" (better)
# OpenAI models:    "gpt-4o-mini" (cheap) | "gpt-4o" (better)
# Ollama models:    "llama3" | "mistral" | any model you have pulled locally

LLM_PROVIDER = "anthropic"
LLM_MODEL    = "claude-haiku-4-5-20251001"

# ─── Databases ───────────────────────────────────────────────────────────────
# Enable/disable by commenting out. All four are on by default.
DATABASES = [
    "pubmed",
    "arxiv",
    "medrxiv",
    "semantic_scholar",
]

# Per-cluster database override.
# arXiv is only useful for methods/ML topics — clinical papers rarely appear there.
# Clusters not listed here fall back to all DATABASES above.
CLUSTER_DATABASES = {
    "causal_inference":                    ["pubmed", "arxiv", "medrxiv", "semantic_scholar"],
    "data_science":                        ["pubmed", "arxiv", "semantic_scholar"],
    "double_robust_semiparametric":        ["pubmed", "arxiv", "semantic_scholar"],
    "effect_modification_heterogeneity":   ["pubmed", "arxiv", "semantic_scholar"],
    "epidemiology_methods":                ["pubmed", "medrxiv", "semantic_scholar"],
    "applied_statistics":                  ["pubmed", "arxiv", "semantic_scholar"],
    "machine_learning_health":             ["pubmed", "arxiv", "semantic_scholar"],
    "environmental_epidemiology":          ["pubmed", "medrxiv", "semantic_scholar"],
    "reproductive_perinatal_epidemiology": ["pubmed", "medrxiv", "semantic_scholar"],
    "fertility":                           ["pubmed", "medrxiv", "semantic_scholar"],
    "ivf_art":                             ["pubmed", "medrxiv", "semantic_scholar"],
    "diet_nutrition_epidemiology":         ["pubmed", "medrxiv", "semantic_scholar"],
}

# arXiv category filter — prevents results from unrelated fields (physics, CS systems, etc.)
# stat.ME=Statistics Methodology, stat.AP=Applications, stat.ML=Machine Learning,
# econ.EM=Econometrics, cs.LG=Machine Learning, q-bio.QM=Quantitative Biology Methods
ARXIV_CATEGORIES = ["stat.ME", "stat.AP", "stat.ML", "econ.EM", "cs.LG", "q-bio.QM"]

# Semantic Scholar free API key (optional but recommended — raises rate limit 6x).
# Get one free at: https://www.semanticscholar.org/product/api
# Set in ~/.env as SEMANTIC_SCHOLAR_API_KEY=... (preferred) or paste here.
SEMANTIC_SCHOLAR_API_KEY = ""

# ─── Search Clusters ─────────────────────────────────────────────────────────
# Each key is a topic label; each value is a list of search strings.
# Add, remove, or edit queries freely as your interests evolve.

SEARCH_CLUSTERS = {
    "causal_inference": [
        "causal inference",
        "potential outcomes",
        "target trial emulation",
        "causal identification",
    ],
    "data_science": [
        "reproducibility research",
        "real-world evidence causal",
        "open science epidemiology",
        "data science public health",
    ],
    "double_robust_semiparametric": [
        "double robust estimation semiparametric",
        "targeted learning TMLE causal inference",
        "debiased machine learning average treatment effect",
        "doubly robust machine learning partially linear",
        "DR-learner effect modification",          # from EARTH paper
        "doubly robust effect modification heterogeneity",
    ],
    "effect_modification_heterogeneity": [
        "heterogeneous treatment effects machine learning",
        "conditional average treatment effect semiparametric",
        "treatment effect heterogeneity causal",
        "subgroup analysis doubly robust",
    ],
    "epidemiology_methods": [
        "epidemiological methods",
        "confounding selection bias epidemiology",
        "measurement error epidemiology",
        "selection bias epidemiology methods",
    ],
    "applied_statistics": [
        "semiparametric efficiency bounds biostatistics",
        "statistical inference p-value significance testing",
        "bootstrap variance estimation",
        "statistics reform significance",
    ],
    "machine_learning_health": [
        "machine learning clinical prediction ensemble",
        "SuperLearner ensemble methods prediction",
        "machine learning epidemiology methods",
    ],
    "environmental_epidemiology": [              # from EARTH study paper
        "endocrine disrupting chemicals fertility",
        "phthalates reproductive health epidemiology",
        "environmental chemicals ovarian reserve",
        "environmental exposures pregnancy outcomes cohort",
    ],
    "reproductive_perinatal_epidemiology": [
        "perinatal epidemiology birth outcomes cohort",
        "maternal health pregnancy complications",
        "preterm birth risk factors epidemiology",
        "preeclampsia causal inference",           # from Bodnar papers
    ],
    "fertility": [
        "fertility infertility treatment fecundability",
        "ovarian reserve fertility epidemiology",
        "time to pregnancy epidemiology",
        "antral follicle count ovarian reserve",   # from EARTH paper
    ],
    "ivf_art": [
        "in vitro fertilization outcomes live birth",
        "assisted reproductive technology embryo transfer",
        "IVF success predictors frozen embryo",
    ],
    "diet_nutrition_epidemiology": [
        "dietary patterns pregnancy outcomes cohort",
        "nutrition epidemiology causal inference",
        "diet fertility reproductive outcomes",
        "nutritional epidemiology methods",
        "dietary synergy machine learning pregnancy",  # from Bodnar 2020
        "Super Learner TMLE nutritional epidemiology", # from Bodnar papers
    ],
}

# ─── Followed Authors ────────────────────────────────────────────────────────
# Papers by these authors are always included (subject to LOOKBACK_DAYS),
# bypassing the relevance threshold.
#
# To find s2_author_id: go to semanticscholar.org, search the person's name,
# click their profile — the ID is the number at the end of the URL.
# e.g. semanticscholar.org/author/Sander-Greenland/2109704 → "2109704"
#
# pubmed_query: how their name appears in PubMed author field, e.g. "Greenland S"

FOLLOWED_AUTHORS = [
    # S2 IDs verified by paper count. IDs marked None need manual lookup:
    # go to semanticscholar.org, search name, copy the number from the profile URL.
    {"name": "Sander Greenland",            "s2_author_id": "143898747", "pubmed_query": "Greenland S"},
    {"name": "Eric Tchetgen Tchetgen",      "s2_author_id": "5328034",   "pubmed_query": "Tchetgen EJ"},
    {"name": "Edward Kennedy",              "s2_author_id": "48224429",  "pubmed_query": "Kennedy EH"},
    {"name": "Mark van der Laan",           "s2_author_id": "3033525",   "pubmed_query": "van der Laan MJ"},
    {"name": "Miguel Hernan",               "s2_author_id": "40362338",  "pubmed_query": "Hernan MA"},
    {"name": "Issa Dahabreh",               "s2_author_id": "1809920",   "pubmed_query": "Dahabreh IJ"},
    {"name": "Stijn Vansteelandt",          "s2_author_id": "3345793",   "pubmed_query": "Vansteelandt S"},
    {"name": "Stephen Cole",                "s2_author_id": "145276274", "pubmed_query": "Cole SR"},        # verify S2 ID manually
    {"name": "Margarita Moreno-Betancur",   "s2_author_id": "1389976737","pubmed_query": "Moreno-Betancur M"}, # verify S2 ID manually
    {"name": "Paul Zivich",                 "s2_author_id": "17100249",  "pubmed_query": "Zivich PN"},      # verify S2 ID manually
]

# ─── Pre-filter Keywords ─────────────────────────────────────────────────────
# Applied to paper titles BEFORE LLM scoring — fast and free.
# All matching is case-insensitive and checks for substring presence.

# Papers whose title contains ANY of these terms are dropped immediately.
# Add terms for topics that consistently produce irrelevant results.
EXCLUDE_KEYWORDS = [
    # Clinical specialties outside your scope — add as you identify them
    # e.g. "robotic surgery", "sleep apnea", "knee osteoarthritis",
]

# Papers whose title contains NONE of these terms are dropped.
# Leave empty [] to disable (recommended unless PubMed noise is very high).
# Use sparingly — too aggressive for broad research areas.
REQUIRE_KEYWORDS = []

# ─── Search Settings ─────────────────────────────────────────────────────────
LOOKBACK_DAYS        = 7   # how many days back to search
FETCH_LIMIT_PER_QUERY = 8  # papers fetched per query before LLM scoring
RELEVANCE_THRESHOLD  = 6   # 0–10: papers scoring below this are dropped
TOP_N_PAPERS         = 20  # number of papers in the final weekly digest

# ─── History (no repeats) ────────────────────────────────────────────────────
# Databases re-return old papers for weeks when publication dates are vague
# (a year-only PubMed date matches every weekly window in that year). The agent
# therefore records every paper listed in a sent digest — email or attachment —
# in _seen.json and skips those papers in later runs, before LLM scoring.
# To let one paper reappear, delete its entry from _seen.json; to reset
# completely, delete the file. One-off repeat run: `python run.py --include-seen`.

SKIP_SEEN_PAPERS    = True  # False disables the cross-run history entirely
SEEN_RETENTION_DAYS = 730   # forget papers after ~2 years (0 = remember forever)

# ─── Interests Folder ────────────────────────────────────────────────────────
# Drop PDFs, Word docs (.docx), LaTeX (.tex), or plain text (.txt / .md)
# into this folder. The agent reads them to build your relevance profile.
# Profile is cached and regenerated automatically when files change.

INTERESTS_DIR       = "./interests"
PROFILE_CACHE_FILE  = "./_profile_cache.json"
PROFILE_MAX_AGE_DAYS = 30  # force regeneration after this many days even if files unchanged

# ─── Delivery ────────────────────────────────────────────────────────────────
DIGEST_DAY  = "sunday"  # day of week the digest is sent (used when scheduling cron)
DIGEST_HOUR = 8         # hour (24h, local time)

# Email delivery
# Set SMTP credentials in ~/.env:
#   SMTP_USERNAME=you@gmail.com          ← also used as EMAIL_FROM
#   SMTP_PASSWORD=your-app-password      ← Gmail: myaccount.google.com/apppasswords
#   EMAIL_TO=you@institution.edu         ← recipient (can differ from sender)
#   SMTP_HOST=smtp.gmail.com             (optional, default shown)
#   SMTP_PORT=587                        (optional, default shown)
EMAIL_SUBJECT = "Your Lit-Search Digest"
