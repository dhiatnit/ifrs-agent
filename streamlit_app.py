"""
Streamlit web interface for the IFRS agent (for Streamlit Community Cloud).

Deploy: set this file as the main file path. Add your Gemini key under
"Advanced settings -> Secrets" as:

    GOOGLE_API_KEY = "your_key_here"

The FAISS index (the `index/` folder) is committed in the repo, so the
app loads it without rebuilding.
"""

import os
import streamlit as st

# The API key must be in the environment BEFORE importing the agent
# (langchain reads GOOGLE_API_KEY at model construction). On Streamlit
# Cloud it comes from st.secrets; locally it comes from .env.
if "GOOGLE_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]

st.set_page_config(page_title="IFRS Agent", page_icon="📊")

st.title("IFRS Agent 📊")
st.caption(
    "Ask about IAS 2 (Inventories), IAS 16 (PP&E), IAS 36 (Impairment), "
    "IFRS 15 (Revenue), IFRS 16 (Leases) — definitions, treatments and "
    "calculations. Answers cite the standard and paragraph. "
    "EU-endorsed texts, Regulation (EU) 2023/1803."
)


@st.cache_resource(show_spinner="Loading the IFRS agent…")
def get_agent():
    from agent import build_agent
    return build_agent(verbose=False)


if not os.environ.get("GOOGLE_API_KEY"):
    st.error(
        "No GOOGLE_API_KEY found. Add it under "
        "**Manage app → Settings → Secrets** as `GOOGLE_API_KEY = \"...\"`."
    )
    st.stop()

executor = get_agent()

# chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("e.g. How is depreciation calculated under IAS 16?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                result = executor.invoke({"input": prompt})
                answer = result["output"]
            except Exception as exc:
                answer = f"Sorry, something went wrong: {exc}"
        st.markdown(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})

with st.sidebar:
    st.subheader("Example questions")
    st.markdown(
        "- How are inventories measured under IAS 2?\n"
        "- A machine costs €120,000, residual €20,000, useful life 8 years. "
        "Annual straight-line depreciation?\n"
        "- When is an asset impaired under IAS 36?\n"
        "- What is the current VAT rate in Italy? *(should be refused)*"
    )
    st.caption("IFRS/IAS agent — RAG over EU-endorsed standards with tool use.")
