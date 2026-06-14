# IFRS Agent 📊

An AI agent that answers questions about **IFRS/IAS international accounting
standards** — and computes accounting figures (depreciation, impairment,
lease liabilities…) — using RAG over the EU-endorsed standard texts plus
LangChain tool use.

Built for the AI course track **"AI agent with tool use"**.

## How it works

```
   question  ─►  LangChain Agent (Gemini)
                      │ decides:
            ┌─────────┴──────────┐
            ▼                    ▼
   search_standards         calculator
   (FAISS over IFRS texts)  (depreciation, PV,
   = the RAG part            lease, impairment)
            │
            ▼
   answer + which standard/paragraph it used
```

The agent has two tools: `search_standards` retrieves passages from a FAISS
index over five standards (IAS 2, IAS 16, IAS 36, IFRS 15, IFRS 16), and
`calculator` evaluates the arithmetic the LLM should not do by itself.

## Problem framing

Accounting standards are long, precise legal texts, and questions about them
have two awkward properties: (1) the answer must be **traceable to a specific
paragraph** — an unsourced or invented citation is worse than no answer; and
(2) many questions need an **exact number** (depreciation, impairment, lease
liability), where language models are unreliable. A generic chatbot fails on
both counts. We therefore framed the task as: *ground every answer in the
source text with a citation, compute figures deterministically, and refuse or
flag what falls outside the covered material.* That framing is what pushes the
design from "a chatbot" to "a retrieval-augmented agent with tools."

## Design decisions & alternatives considered

Each row is a choice we made and the alternative we rejected, with the reason.

| Decision | We chose | Rejected — and why |
|---|---|---|
| Build vs adapt | Adapt the course `studentsbot` RAG template | From scratch — slower, riskier, and ignores the provided materials |
| Data source | EUR-Lex EU-endorsed IFRS text (Reg. 2023/1803) | ifrs.org official texts — copyrighted, not redistributable |
| Architecture | **Agent** with 2 tools (search + calculator) | **Plain RAG** — cannot do reliable arithmetic and doesn't meet the "tool use" track |
| Doing math | A `calculator` tool (sandboxed eval) | Letting the LLM compute — LLMs miscalculate and can't be audited |
| Vector store | **FAISS** (local, file-based) | Chroma / a hosted vector DB — extra service and setup with no benefit at this scale |
| Chunking | By the standards' **section headings** | Fixed-size character chunks — would split paragraphs and blur citations |
| Embeddings | `gemini-embedding-001` | `sentence-transformers` (local) — fine, but keeps the stack on one provider |
| LLM | **`gemini-2.5-flash-lite`** | `gemini-3.x` — needs "thought signatures" that break the course-compatible LangChain; bigger models — no free quota headroom for a multi-call agent |
| Evaluation | Reuse `rageval.py` + LLM-judge, **agent vs plain-RAG baseline on the same model** | Building new metrics — the provided scripts are trusted and the same-model baseline isolates the effect of tool use |

(The "why" behind the model choice is also a finding in itself: free-tier
**daily request limits** are the binding constraint when evaluating an *agent*,
because an agent makes several model calls per question — see
`results/error_analysis.md`.)

## Credits / foundation

The RAG core (indexing, chat loop, batch querying and the evaluation
scripts `rageval.py` / `llm_as_judge.py`) is adapted from
[nluninja/studentsbot](https://github.com/nluninja/studentsbot) (MIT),
the RAG chatbot template by Prof. Andrea Belli — see `LICENSE`.
Data swapped to IFRS standards, agent + tools added, evaluation reused.

## Data and copyright

Standard texts come from the **EU-endorsed IFRS full text**
([Regulation (EU) 2023/1803](https://eur-lex.europa.eu/eli/reg/2023/1803/oj)),
© European Union — reuse allowed with attribution. The official IFRS
Foundation versions are copyrighted and are **not** used here.

## Setup

Requires **Python 3.12 or 3.13** (not 3.14) and a free Gemini API key
from [aistudio.google.com](https://aistudio.google.com).

```bash
git clone <this repo>
cd ifrs-agent
py -3.13 -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# configure the API key
copy .env.example .env          # then edit .env: GOOGLE_API_KEY=...
```

The extracted standards are already committed in `output_crawler/`.
To regenerate them from scratch:

```bash
# download the full EU regulation text (~12 MB XHTML, one file)
mkdir data_src
curl -L -o data_src/ifrs_eurlex_full.html "http://publications.europa.eu/resource/celex/32023R1803?language=eng&format=xhtml"

python prepare_ifrs_data.py
```

## Usage

```bash
python bot_review.py --index_only     # build the FAISS index (one-time)
python agent.py                       # chat with the AGENT (search + calculator)
python bot_review.py --interactive    # chat with the plain-RAG baseline
streamlit run streamlit_app.py        # web UI

# batch evaluation
python batch_query_agent.py data/questions.xlsx results/agent_answers.json     # agent
python batch_query.py       data/questions.xlsx results/baseline_answers.json  # baseline
python rageval.py     results/agent_answers.json results/agent_rageval.json
python llm_as_judge.py results/agent_answers.json -o results/agent_judge.json
```

On Windows, run with UTF-8 mode if you see encoding errors:
`set PYTHONUTF8=1`.

## Project status

- [x] Environment + pinned dependencies
- [x] IFRS data extraction from EUR-Lex (5 standards)
- [x] FAISS index + IFRS system prompt
- [x] Agent with tools (`agent.py`, `tools.py`)
- [x] Question set (30 questions with true answers)
- [x] Evaluation results (rageval + LLM-as-judge)
- [x] Demo notebook + Gradio UI
- [x] Slides

## Team

| Member | GitHub | Focus |
|---|---|---|
| Ben Hassine Dhia Eddine | @dhiatnit | Core: environment, data pipeline, agent & tools, prompts, evaluation |
| Madushani | @A-Madushani | Data QA, Gradio UI, eval questions, slides |
| Davide Papini | @papinidavide | Data QA, demo notebook, eval questions, metrics & error analysis |

See `TEAM_PLAN.md` for the detailed work split and commit plan.

## Results

Evaluation on a 30-question test set (15 definitions/scope, 12 calculations,
3 out-of-scope refusal tests). The agent and the plain-RAG baseline use the
**same** LLM (`gemini-2.5-flash-lite`), so differences come from the agent's
tool use, not the model. Full details in
[`results/error_analysis.md`](results/error_analysis.md).

- **30 / 30** questions answered; **3 / 3** out-of-scope questions correctly refused.
- **Agent beats the plain-RAG baseline** on the automatic metrics:

  | Metric | Agent | Baseline |
  |---|---|---|
  | Keyword recall | **0.74** | 0.67 |
  | Keyword F1 | **0.44** | 0.40 |
  | Text similarity | **0.31** | 0.26 |
  | ROUGE-1 F1 | **0.37** | 0.32 |
  | BLEU | 0.16 | 0.16 |

- **LLM-as-judge (agent):** 15/19 judged answers semantically equivalent
  (**79%**), mean confidence **0.97**. (Overlap metrics read low because the
  agent gives fuller, *cited* answers than the one-line references — keyword
  recall and the judge confirm the content is correct.)
- Calculations are exact because they are routed to the `calculator` tool.

Slides: [`slides/presentation.pptx`](slides/presentation.pptx).
