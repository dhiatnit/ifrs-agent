"""
Web chat interface for the IFRS agent, built with Gradio.

Run with:  python app.py
then open the local URL it prints (usually http://127.0.0.1:7860).
"""

import gradio as gr

from agent import build_agent

executor = build_agent(verbose=True)


def respond(message, history):
    """Called by Gradio for every user message; returns the agent's answer."""
    try:
        result = executor.invoke({"input": message})
        return result["output"]
    except Exception as exc:
        return f"Sorry, something went wrong: {exc}"


demo = gr.ChatInterface(
    respond,
    title="IFRS Agent 📊",
    description=(
        "Ask about IAS 2 (Inventories), IAS 16 (PP&E), IAS 36 (Impairment), "
        "IFRS 15 (Revenue), IFRS 16 (Leases) — definitions, treatments and "
        "calculations (depreciation, impairment, lease liabilities). "
        "Answers cite the standard and paragraph. EU-endorsed texts, "
        "Regulation (EU) 2023/1803."
    ),
    examples=[
        "How are inventories measured under IAS 2?",
        "A machine costs 120000 euros, residual value 20000, useful life 8 years. Annual straight-line depreciation?",
        "When is an asset impaired under IAS 36?",
    ],
)

if __name__ == "__main__":
    demo.launch()
