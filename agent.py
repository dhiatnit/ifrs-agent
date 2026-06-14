"""
The IFRS agent: a Gemini-powered LangChain agent with two tools.

Unlike plain RAG (which always retrieves, then answers), the agent
DECIDES at each step whether to search the standards, use the
calculator, do both in sequence, or refuse an out-of-scope question.

Usage:
    python agent.py                 # interactive chat
    from agent import ask_agent     # programmatic use
"""

import sys

from dotenv import load_dotenv

load_dotenv()

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI

from tools import ALL_TOOLS

# The agent needs multi-step tool calling. Gemini 3.x models require
# "thought signatures" to be round-tripped through the conversation,
# which langchain-google-genai 2.x (the last version compatible with
# LangChain 0.3) does not support — so the agent uses a 2.5 model.
# flash-lite over flash: the agent makes several calls per question, and
# flash-lite's free-tier daily quota (~1000 req/day) is ~4x flash's,
# which comfortably covers the 30-question evaluation with room to re-run.
AGENT_MODEL = "gemini-2.5-flash-lite"

SYSTEM_PROMPT = (
    "You are a helpful AI assistant specialised in IFRS/IAS international accounting standards. "
    "Your detailed knowledge base contains the EU-endorsed full texts (Regulation (EU) 2023/1803) of "
    "five standards: IAS 2 Inventories, IAS 16 Property Plant and Equipment, IAS 36 Impairment of "
    "Assets, IFRS 15 Revenue from Contracts with Customers, IFRS 16 Leases.\n"
    "Be helpful first. In particular:\n"
    "- General accounting questions (e.g. 'What is IFRS?', 'What is Regulation (EU) 2023/1803?', "
    "'What is depreciation?', 'What does an auditor do?'): answer them directly and clearly from your "
    "general knowledge. IFRS = International Financial Reporting Standards, the global accounting "
    "standards issued by the IASB. Do NOT refuse these.\n"
    "- Questions about the five standards above: call search_standards first, base the answer on what "
    "it returns, and ALWAYS cite the standard and paragraph, e.g. (IAS 16, paragraph 50). Never invent "
    "paragraph numbers.\n"
    "- Numeric computations (depreciation, impairment loss, present value, allocation): establish the "
    "treatment (search if needed), then use the calculator tool — never do arithmetic in your head. "
    "Show the formula and the computed result.\n"
    "- For DETAILED questions about a specific other standard NOT in your five (e.g. the detailed rules "
    "of IFRS 9 or IAS 12), say that standard's full text is not in your knowledge base so you can only "
    "give general guidance, and point to the five you cover in depth. Only fully decline questions that "
    "are clearly unrelated to accounting (e.g. tax rates, weather, sports).\n"
    "- Answer in clear, plain English: conclusion first, then the reasoning and any citations."
)


def build_agent(verbose: bool = True) -> AgentExecutor:
    # max_retries=1: the default (6) creates a "retry storm" — on a
    # per-minute 429 it fires many rapid retries that themselves count
    # against the 20 req/min free-tier limit, keeping us pinned at it.
    # Let a 429 bubble up quickly to the controlled 65s wait in
    # batch_query_agent.py instead, which lets the minute window reset.
    llm = ChatGoogleGenerativeAI(model=AGENT_MODEL, temperature=0.1, max_retries=1)
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])
    agent = create_tool_calling_agent(llm, ALL_TOOLS, prompt)
    return AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        verbose=verbose,
        max_iterations=6,
        handle_parsing_errors=True,
    )


_executor = None


def ask_agent(question: str, chat_history=None, verbose: bool = False) -> str:
    """Ask the agent one question and return its final answer text."""
    global _executor
    if _executor is None:
        _executor = build_agent(verbose=verbose)
    payload = {"input": question}
    if chat_history:
        payload["chat_history"] = chat_history
    result = _executor.invoke(payload)
    return result["output"]


def main():
    print("IFRS Agent — ask about IAS 2, IAS 16, IAS 36, IFRS 15, IFRS 16.")
    print("It can also compute figures (depreciation, impairment, leases).")
    print("Type 'exit' to quit.")
    print("-" * 60)
    executor = build_agent(verbose="--quiet" not in sys.argv)
    history = []
    while True:
        try:
            question = input("You: ")
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            break
        if question.strip().lower() in {"exit", "quit", "esci"}:
            print("Bye!")
            break
        if not question.strip():
            continue
        try:
            result = executor.invoke({"input": question, "chat_history": history})
            answer = result["output"]
        except Exception as exc:
            answer = f"Error: {exc}"
        print(f"\nAgent: {answer}\n" + "-" * 60)
        history.append(("human", question))
        history.append(("ai", answer))


if __name__ == "__main__":
    main()
