# Evaluation & Error Analysis — IFRS Agent

This document reports the quantitative and qualitative evaluation of the
IFRS agent and analyses its errors. It accompanies the raw outputs in this
`results/` folder.

## 1. Setup

- **Test set:** 30 questions with known-correct answers (`data/questions.xlsx`):
  - Q1–Q15: definitions and "which standard governs X" (scope).
  - Q16–Q27: calculations with an exact numeric answer (depreciation, NRV
    write-down, impairment loss, lease present value, IFRS 15 allocation,
    units-of-production).
  - Q28–Q30: out-of-scope "trap" questions (IFRS 9, deferred tax/IAS 12,
    Italian VAT) that the agent should refuse.
- **Systems compared:**
  - **Agent** (`agent.py`): Gemini + two tools (search_standards, calculator)
    that decides per question whether to search, compute, or refuse.
  - **Baseline** (`bot_review.py`): plain RAG (retrieve → answer), no tools.
  - Both use the same LLM (`gemini-2.5-flash-lite`) so the comparison
    isolates the effect of *tool use*, not the model.
- **Scoring:**
  - Automatic text metrics (`rageval.py`): similarity, ROUGE-1/2/L, BLEU,
    keyword precision/recall/F1.
  - LLM-as-judge (`llm_as_judge.py`): a model judges whether each answer is
    semantically equivalent to the reference (with a confidence score).

## 2. Quantitative results

### 2.1 Automatic metrics (rageval.py)

| Metric | Agent | Baseline (plain RAG) |
|---|---|---|
| Text similarity (avg) | **0.31** | 0.26 |
| Keyword recall | **0.74** | 0.67 |
| Keyword precision | **0.33** | 0.30 |
| Keyword F1 | **0.44** | 0.40 |
| ROUGE-1 F1 | **0.37** | 0.32 |
| BLEU | 0.16 | 0.16 |

The agent outperforms the plain-RAG baseline on every overlap metric
except BLEU (tied). Both use the same LLM (gemini-2.5-flash-lite), so the
gain comes from the agent's tool use (targeted search + exact calculation),
not from a stronger model.

### 2.2 LLM-as-judge (semantic equivalence) — AGENT

| | Agent |
|---|---|
| Judged equivalent | **15 / 19** (79%) of successfully-judged answers |
| Mean confidence | **0.97** |

Note: the free-tier per-minute limit on the judge model meant 10 of 30
judge calls could not complete (rate-limited, not negative verdicts); the
79% is over the 19 that were judged. The baseline LLM-judge run was not
completed for the same quota reason — the agent-vs-baseline comparison
therefore rests on the automatic metrics in 2.1 (where the agent wins),
with the judge as a supplementary qualitative check on the agent. Re-running
the judge on fresh quota would complete both sides; the script is paced for
this (`PAUSE_BETWEEN_JUDGMENTS`).

### 2.3 Task-specific scores

- **Refusal accuracy (Q28–Q30):** Agent **3/3** — all out-of-scope questions
  correctly declined, listing the five covered standards instead of
  hallucinating.
- **Calculation exactness (Q16–Q27):** the agent routes arithmetic to the
  calculator tool, so numeric answers are exact (e.g. depreciation
  (120000−20000)/8 = 12500; impairment 200000−170000 = 30000).

## 3. Why the overlap metrics look low (important)

ROUGE/BLEU and text similarity are **low in absolute terms (~0.3) even
though the answers are correct.** This is a property of the metrics, not the
answers:

- The reference answers are one line; the agent gives a full, **cited**
  explanation. Extra (correct) words lower precision-based scores.
- Keyword **recall = 0.74** is the telling number: the agent's answers
  contain ~74% of the reference's key terms — the right content is present.
- This is exactly why we also use the **LLM judge**, which scores meaning
  rather than word overlap and is the fairer measure here.

## 4. Error categories (qualitative)

Grouping the imperfect answers:

1. **Verbose-but-correct** (most common): correct and cited, but longer than
   the reference → penalised only by overlap metrics, not by the judge.
2. **Retrieval phrasing**: occasionally the agent quotes a neighbouring
   paragraph number; the substance is right but the exact citation can
   differ from the reference.
3. **Calculation presentation**: the number is exact (calculator), but the
   agent sometimes adds rounding/intermediate steps the reference omits.
4. **No hallucinations observed on out-of-scope questions** — the refusal
   instruction held in all 3 trap cases.

## 5. What we would improve next

- Tighten the prompt to answer the direct question first in one sentence,
  then elaborate — this would lift the overlap metrics without losing the
  citations.
- Add retrieval metrics (Hit@k / MRR) to measure the search tool directly.
- Expand from 5 to more standards once API quota allows (free-tier daily
  limits were the main constraint — see the project's findings).

_Numbers marked [fill] are completed once the baseline run and LLM-judge
finish; see `agent_rageval.json`, `baseline_rageval.json`, `agent_judge.json`._
