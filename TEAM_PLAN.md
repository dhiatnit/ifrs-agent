# Team plan — who does what, and the commit schedule

Principle: **everyone touches every area** (data, code, evaluation, slides),
but the heavy technical core stays with Ben. Each member commits **from
their own machine with their own GitHub account** — that is what makes the
contributor graph and history credible. Small, logical commits; no giant
"add everything" dumps.

Rules:
- `.env` (the API key) is git-ignored and must NEVER be committed.
- Branches: `feature/<area>`; open a PR, one of the other two reviews/merges.
- Run the code before committing (`set PYTHONUTF8=1` on Windows).

---

## Ben (@dhiatnit) — core (~60%)

Owns: environment, data pipeline, agent, prompts, evaluation runs (has the
API key).

| # | Commit | Content |
|---|---|---|
| B1 | Bootstrap project | README, LICENSE, .gitignore, .env.example, requirements |
| B2 | Import RAG core from studentsbot | bot_review.py, batch_query.py, rageval.py, llm_as_judge.py + embedding-001→gemini-embedding-001 fix |
| B3 | Add EUR-Lex extractor | prepare_ifrs_data.py |
| B4 | Add extracted standards | output_crawler/*.md (5 standards) |
| B5 | IFRS system prompt | replace the Unicatt prompt in bot_review.py |
| B6 | FAISS index build verified | any indexing fixes |
| B7 | tools.py | search_standards + calculator tools |
| B8 | agent.py | LangChain agent wiring the two tools |
| B9 | Evaluation run | results/answers.json from batch_query |

## Teammate A (@___) — data QA + UI + eval + slides (~20%)

| # | Commit | Content |
|---|---|---|
| A1 | Data QA: IAS 2 + IAS 16 | proofread extracted .md, fix extraction glitches (duplicated list paragraphs, stray table dumps) |
| A2 | Gradio app | app.py — simple chat UI calling the agent |
| A3 | Eval questions 1–15 | first half of data/questions.xlsx (definitions + "which standard governs X") |
| A4 | Slides: problem, data, architecture | first third of the deck |

## Teammate B (@___) — data QA + notebook + eval + analysis (~20%)

| # | Commit | Content |
|---|---|---|
| C1 | Data QA: IAS 36 + IFRS 15 + IFRS 16 | proofread extracted .md, fix glitches |
| C2 | Demo notebook | notebook/demo.ipynb — 4–5 worked examples incl. one calculation |
| C3 | Eval questions 16–30 | second half of questions.xlsx (calculations + out-of-scope refusals) |
| C4 | Metrics + error analysis | results/rageval + llm_as_judge outputs, error_analysis.md |
| C5 | Slides: results, error analysis, demo | last third of the deck |

---

## Suggested order (incremental history over ~5 days)

```
Day 1   B1 → B2 → B3 → B4
Day 2   B5 → B6 → A1 → C1
Day 3   B7 → B8 → A2 → C2
Day 4   A3 → C3 → B9
Day 5   C4 → A4 → C5 → final README update (Ben)
```

Interleaving members across days (rather than one member per day) is what
makes the history look like genuine parallel teamwork — because it is.

## Handoff

The working environment lives on Ben's machine (he has the Gemini key and
the Python 3.13 venv). For A and C: clone the repo, create your venv per
README, get your own free Gemini key from aistudio.google.com for testing.
Ben prepares the starting material for your tasks; you review, adapt,
test, and commit from your side.
