"""
The two tools of the IFRS agent.

- search_standards: semantic search over the FAISS index built from the
  five IFRS/IAS standards (the RAG part, reused from bot_review.py).
- calculator: safe arithmetic evaluator, so numeric answers
  (depreciation, present values, allocations) are computed exactly
  instead of estimated by the language model.
"""

import math
import re

from langchain_core.tools import tool
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from bot_review import VECTORSTORE_PATH, MODEL_NAME_EMBEDDINGS

_vectorstore = None


def _get_vectorstore():
    """Load the FAISS index once and cache it."""
    global _vectorstore
    if _vectorstore is None:
        embeddings = GoogleGenerativeAIEmbeddings(model=MODEL_NAME_EMBEDDINGS)
        _vectorstore = FAISS.load_local(
            VECTORSTORE_PATH, embeddings, allow_dangerous_deserialization=True
        )
    return _vectorstore


@tool
def search_standards(query: str) -> str:
    """Search the IFRS/IAS knowledge base and return the most relevant passages.

    The knowledge base contains the EU-endorsed texts of exactly five
    standards: IAS 2 Inventories, IAS 16 Property Plant and Equipment,
    IAS 36 Impairment of Assets, IFRS 15 Revenue from Contracts with
    Customers, IFRS 16 Leases. Use this for every question about
    accounting treatments, definitions, scope or disclosure. The result
    shows, for each passage, the standard and section it comes from —
    cite them in your answer.
    """
    docs = _get_vectorstore().as_retriever(search_kwargs={"k": 6}).invoke(query)
    if not docs:
        return "No relevant passage found in the five covered standards."
    parts = []
    for d in docs:
        std = d.metadata.get("standard", "unknown standard")
        sec = d.metadata.get("section", "")
        header = f"[{std}" + (f" — {sec}" if sec else "") + "]"
        parts.append(f"{header}\n{d.page_content}")
    return "\n\n---\n\n".join(parts)


# characters/tokens allowed in a calculator expression
_SAFE_EXPR = re.compile(r"^[\d\s\.\,\+\-\*\/\(\)eE]*(?:[a-z_]+\(|\b(?:pi|e)\b|[\d\s\.\,\+\-\*\/\(\)eE])*$")
_ALLOWED_NAMES = {
    "sqrt": math.sqrt, "log": math.log, "exp": math.exp,
    "abs": abs, "round": round, "pow": pow, "min": min, "max": max,
    "pi": math.pi, "e": math.e,
}


@tool
def calculator(expression: str) -> str:
    """Evaluate an arithmetic expression and return the exact result.

    Use this for EVERY numeric computation (depreciation charges,
    impairment losses, present values, transaction price allocations)
    instead of computing mentally. Supports + - * / ** parentheses and
    the functions sqrt, log, exp, abs, round, pow, min, max, and the
    constants pi and e. Example: "(120000 - 20000) / 8" or
    "10000 * (1 - 1.05**-5) / 0.05".
    """
    expr = expression.strip()
    # whitelist check: digits, operators, parentheses and known names only
    leftover = re.sub(r"[a-z_]+", lambda m: "" if m.group(0) in _ALLOWED_NAMES else "X", expr)
    if "X" in leftover or not re.fullmatch(r"[\d\s\.\,\+\-\*\/\(\)eE]*", re.sub(r"[a-z_]+", "", expr)):
        return f"Error: expression contains disallowed names or characters: {expression!r}"
    try:
        result = eval(compile(expr, "<calculator>", "eval"), {"__builtins__": {}}, _ALLOWED_NAMES)
    except Exception as exc:
        return f"Error evaluating {expression!r}: {exc}"
    return f"{expression} = {result}"


ALL_TOOLS = [search_standards, calculator]
