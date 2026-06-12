#!/usr/bin/env python3
"""
Run the evaluation question set against the AGENT (agent.py).

Same protocol and output format as the professor's batch_query.py
(which evaluates the plain RAG chatbot and serves as our baseline):
reads an Excel file with columns 'query' and 'true_answer', writes a
JSON file that rageval.py and llm_as_judge.py consume unchanged.

Free-tier aware: pauses between questions and retries on 429.

Usage:
    python batch_query_agent.py data/questions.xlsx results/agent_answers.json [--limit N] [--verbose]
"""

import json
import sys
import time
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from batch_query import load_questions_from_excel, save_results
from agent import ask_agent

PAUSE_BETWEEN_QUESTIONS = 20  # seconds; stays inside free-tier per-minute limits
RETRIES_ON_QUOTA = 3
QUOTA_WAIT = 65               # seconds to wait after a 429 before retrying


def ask_with_retry(question: str, verbose: bool = False) -> str:
    for attempt in range(RETRIES_ON_QUOTA + 1):
        try:
            return ask_agent(question, verbose=verbose)
        except Exception as exc:
            if "429" in str(exc) and attempt < RETRIES_ON_QUOTA:
                print(f"  Rate limit (429): waiting {QUOTA_WAIT}s, retry {attempt + 2}/{RETRIES_ON_QUOTA + 1}...")
                time.sleep(QUOTA_WAIT)
            else:
                raise


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args or "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(1)

    excel_file = args[0]
    output_file = args[1] if len(args) > 1 else "results/agent_answers.json"
    verbose = "--verbose" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    data = load_questions_from_excel(excel_file)
    if not data:
        print("No questions found.")
        sys.exit(1)
    if limit:
        data = data[:limit]

    print(f"Evaluating the AGENT on {len(data)} questions "
          f"(~{PAUSE_BETWEEN_QUESTIONS}s pause between questions)...")
    results = []
    for i, item in enumerate(data, 1):
        print(f"[{i}/{len(data)}] {item['query'][:70]}")
        try:
            answer = ask_with_retry(item["query"], verbose=verbose)
            print("  OK")
        except Exception as exc:
            answer = f"ERRORE: {exc}"
            print(f"  FAILED: {exc}")
        results.append({
            "query": item["query"],
            "answer": answer,
            "true_answer": item["true_answer"],
            "timestamp": datetime.now().isoformat(),
        })
        if i < len(data):
            time.sleep(PAUSE_BETWEEN_QUESTIONS)

    save_results(results, output_file)
    ok = sum(1 for r in results if not r["answer"].startswith("ERRORE:"))
    print(f"\nDone: {ok}/{len(results)} answered. Results in {output_file}")


if __name__ == "__main__":
    main()
