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
# LangChain 0.3) does not support — so the agent uses gemini-2.5-flash,
# the newest model that works without them.
AGENT_MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = (
    "You are an AI agent specialised in IFRS/IAS international accounting standards. "
    "Your knowledge base covers exactly five standards (EU-endorsed texts, Regulation (EU) 2023/1803): "
    "IAS 2 Inventories, IAS 16 Property Plant and Equipment, IAS 36 Impairment of Assets, "
    "IFRS 15 Revenue from Contracts with Customers, IFRS 16 Leases.\n"
    "How to work:\n"
    "- For ANY question about accounting rules, definitions, scope or disclosures: call "
    "search_standards first and base your answer ONLY on what it returns. Never answer from memory.\n"
    "- For ANY numeric computation (depreciation, impairment loss, present value, allocation): "
    "first establish the correct treatment with search_standards if needed, then compute with the "
    "calculator tool. Never do arithmetic in your head. Show the formula and the computed result.\n"
    "- ALWAYS cite the standard and paragraph number(s) supporting your answer, e.g. (IAS 16, paragraph 50).\n"
    "- If the question concerns a topic outside the five standards above (e.g. IFRS 9, IAS 12, tax law): "
    "do NOT attempt an answer. Say it is outside your coverage and list the five standards you do cover.\n"
    "- Answer in clear, plain English: conclusion first, then the reasoning and citations."
)


def build_agent(verbose: bool = True) -> AgentExecutor:
    llm = ChatGoogleGenerativeAI(model=AGENT_MODEL, temperature=0.1)
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
