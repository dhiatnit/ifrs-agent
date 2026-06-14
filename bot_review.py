import os
import re
import shutil
import time
from dotenv import load_dotenv

from langchain.globals import set_verbose
set_verbose(True)
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.docstore.document import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import FAISS
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory

# === CONFIG ===
MARKDOWN_DIR = "output_crawler"
VECTORSTORE_PATH = "index"
MODEL_NAME_LLM = "gemini-2.5-flash-lite"  # was gemini-2.0-flash (free-tier limit 0), then flash-latest (5/min); flash-lite gives 20/min and matches the agent's model for a clean baseline-vs-agent comparison
MODEL_NAME_EMBEDDINGS = "models/gemini-embedding-001"  # was models/embedding-001, retired by Google (404 as of 2026-06)
BATCH_SIZE = 50   # smaller embedding batches: free-tier tokens-per-minute limit
BATCH_WAIT = 45   # seconds between batches, lets the per-minute quota refresh

def parse_clean_exams(text):
    results = {}
    anno = None
    tipo = "obbligatori"
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        l = line.strip()
        if not l:
            continue
        # Anno riconosciuto
        m_anno = re.search(r"(primo|secondo|terzo|1°|2°|3°|first|second|third)[^\w]{0,5}(anno|year)", l, re.I)
        if m_anno:
            anno = m_anno.group(0).lower()
        # Tipo (elective)
        if any(x in l.lower() for x in ["a scelta", "elective", "opzionali"]):
            tipo = "a scelta"
        if any(x in l.lower() for x in ["obbligatori", "required"]):
            tipo = "obbligatori"
        # Riga esame pulito
        m_exam = re.match(r"-\s*([^\|].+?)(\([A-Z\-\/\d]+\))?$", l)
        if m_exam and not any(xx in m_exam.group(1).lower() for xx in ["credits", "programme", "thesis", "seminar", "cfu", "download"]):
            key = (anno or "generico", tipo)
            results.setdefault(key, []).append(m_exam.group(1).strip())
        # Riga tabella "| Course | nome"
        if "|" in l and not l.startswith("| ---"):
            items = [x.strip() for x in l.split("|") if x.strip()]
            if len(items) >= 2 and not any(xx in items[1].lower() for xx in ["credits", "programme", "download", "thesis", "seminar", "cfu"]):
                key = (anno or "generico", tipo)
                if items[1] and len(items[1]) > 3 and not items[1].isdigit():
                    results.setdefault(key, []).append(items[1])
    for k in results:
        seen = set()
        results[k] = [x for x in results[k] if not (x in seen or seen.add(x))]
    return results

from langchain.text_splitter import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

def load_and_split_documents():
    os.makedirs(MARKDOWN_DIR, exist_ok=True)
    loader = DirectoryLoader(
        MARKDOWN_DIR,
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={'encoding': 'utf-8'}
    )
    documents = loader.load()
    if not documents:
        print("Nessun documento Markdown trovato.")
        return []
    all_chunks = []
    # Chunking by main Markdown headings. headers_to_split_on takes
    # (header, metadata_key) tuples; split_text returns Document objects
    # carrying the heading in metadata. strip_headers=False keeps the
    # section title inside the chunk text (helps retrieval + citations).
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "standard"), ("##", "section")],
        strip_headers=False,
    )
    # Secondary split for oversize sections: gemini embeddings truncate
    # long inputs, so cap chunk size while keeping some overlap.
    sub_splitter = RecursiveCharacterTextSplitter(chunk_size=4000, chunk_overlap=200)
    for doc in documents:
        try:
            chunks = splitter.split_text(doc.page_content)
            for chunk in chunks:
                chunk.metadata.update(doc.metadata)
                if len(chunk.page_content) > 6000:
                    all_chunks.extend(sub_splitter.split_documents([chunk]))
                else:
                    all_chunks.append(chunk)
        except Exception as e:
            print(f"ATTENZIONE: split fallito per {doc.metadata.get('source')}: {e}")
            all_chunks.append(doc)
    print(f"Totale chunk indicizzati: {len(all_chunks)}")
    return all_chunks


def get_vectorstore(force_recreate=False):
    embeddings = GoogleGenerativeAIEmbeddings(model=MODEL_NAME_EMBEDDINGS)
    if os.path.exists(VECTORSTORE_PATH) and not force_recreate:
        try:
            print("Carico il vectorstore esistente...")
            return FAISS.load_local(VECTORSTORE_PATH, embeddings, allow_dangerous_deserialization=True)
        except Exception as e:
            print(f"Errore caricamento vectorstore: {e}, lo rigenero...")
            shutil.rmtree(VECTORSTORE_PATH)
    documents = load_and_split_documents()
    if not documents:
        print("Nessun documento da indicizzare.")
        return None
    batches = [documents[i:i+BATCH_SIZE] for i in range(0, len(documents), BATCH_SIZE)]
    vs = None
    for i, batch in enumerate(batches):
        print(f"Indicizzazione batch {i+1}/{len(batches)} ({len(batch)} doc)")
        # free-tier quota is per-minute: on 429, wait and retry the batch
        for attempt in range(4):
            try:
                batch_vs = FAISS.from_documents(batch, embeddings)
                break
            except Exception as e:
                if "429" in str(e) and attempt < 3:
                    print(f"Rate limit (429): attendo 70s e riprovo (tentativo {attempt + 2}/4)...")
                    time.sleep(70)
                else:
                    raise
        if vs is None:
            vs = batch_vs
        else:
            vs.merge_from(batch_vs)
        if i < len(batches) - 1:
            print(f"Attendo {BATCH_WAIT} secondi per evitare rate limit...")
            time.sleep(BATCH_WAIT)
    if vs is None:
        print("Errore: vectorstore non creato.")
        return None
    print("Indicizzazione completata, salvo e ritorno il vectorstore!")
    vs.save_local(VECTORSTORE_PATH)
    return vs

def query_chatbot(question, vectorstore=None, chat_history=None, verbose=False):
    """
    Query the chatbot with a question.
    
    Args:
        question (str): The question to ask
        vectorstore: FAISS vectorstore (if None, will try to load existing one)
        chat_history: List of chat history messages (optional)
        verbose (bool): Whether to print debug information
        
    Returns:
        str: The bot's answer
    """
    try:
        # Load vectorstore if not provided
        if vectorstore is None:
            if not os.path.exists(VECTORSTORE_PATH):
                return "Errore: Nessun vectorstore trovato. Eseguire prima l'indicizzazione."
            embeddings = GoogleGenerativeAIEmbeddings(model=MODEL_NAME_EMBEDDINGS)
            vectorstore = FAISS.load_local(VECTORSTORE_PATH, embeddings, allow_dangerous_deserialization=True)
        
        # Create RAG chain
        rag_chain = create_rag_chain(vectorstore)
        
        # Prepare input
        input_data = {
            "input": question,
            "chat_history": chat_history or []
        }
        
        # Get response
        if verbose:
            print(f"Query: {question}")
        
        response = rag_chain(input_data)
        answer = response.get("answer", "Non ho trovato una risposta.")
        
        if verbose:
            print(f"Answer: {answer}")
        
        return answer
        
    except Exception as e:
        error_msg = f"Errore durante l'elaborazione della query: {e}"
        if verbose:
            print(error_msg)
        return error_msg

def create_rag_chain(vectorstore):
    llm = ChatGoogleGenerativeAI(model=MODEL_NAME_LLM, temperature=0.1, convert_system_message_to_human=False)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 10})
    system_prompt = (
        "You are an assistant specialised in IFRS/IAS international accounting standards. "
        "Your knowledge base contains the EU-endorsed texts (Regulation (EU) 2023/1803) of exactly five standards: "
        "IAS 2 Inventories, IAS 16 Property Plant and Equipment, IAS 36 Impairment of Assets, "
        "IFRS 15 Revenue from Contracts with Customers, and IFRS 16 Leases.\n"
        "Rules:\n"
        "- Answer ONLY from the documents provided in the context below. Never invent requirements, "
        "paragraph numbers or figures that are not in the context.\n"
        "- ALWAYS cite the standard and paragraph number(s) you used, e.g. (IAS 2, paragraph 9). "
        "Every factual claim should be traceable to a cited paragraph.\n"
        "- When asked for a definition, quote the standard's wording faithfully, then explain it simply.\n"
        "- For questions involving figures (depreciation, impairment, lease liabilities, revenue allocation): "
        "state the accounting treatment with its citation, show the formula and the computation step by step.\n"
        "- If the question concerns a standard or topic NOT in your knowledge base (e.g. IFRS 9, IAS 12, tax rates), "
        "say clearly that it is outside your coverage of the five standards listed above, and do not attempt an answer.\n"
        "- If the question is ambiguous, ask one short clarifying question.\n"
        "- Answer in clear, plain English. Define technical terms on first use. Be concise: answer first, detail after."
        "\n<context>\n{context}\n</context>"
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ])
    question_answer_chain = create_stuff_documents_chain(llm, prompt)
    def custom_chain(input):
        query = input["input"]
        chat_history = input.get("chat_history", [])
        docs = retriever.invoke(query)
        print(query)
        print("invoking Mr. Google..")
        for i, doc in enumerate(docs):
            print("*", doc.metadata["source"])
        output = question_answer_chain.invoke({"input": query, "context": docs, "chat_history": chat_history})
        
        if isinstance(output, dict):
            return output
        else:
            return {"answer": output}
    return custom_chain

def run_interactive_chat():
    """Avvia la modalità chat interattiva senza prompt di configurazione."""
    print("Caricamento vectorstore esistente...")
    
    # Try to load existing vectorstore
    if not os.path.exists(VECTORSTORE_PATH):
        print(f"Errore: Nessun vectorstore trovato in {VECTORSTORE_PATH}")
        print("Eseguire prima: python bot_review.py --index_only")
        return
    
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model=MODEL_NAME_EMBEDDINGS)
        vectorstore = FAISS.load_local(VECTORSTORE_PATH, embeddings, allow_dangerous_deserialization=True)
        print("Vectorstore caricato con successo!")
    except Exception as e:
        print(f"Errore nel caricamento del vectorstore: {e}")
        return
    
    # Create RAG chain
    rag_chain = create_rag_chain(vectorstore)
    if rag_chain is None:
        print("Errore interno: la catena RAG non è inizializzata!")
        return
    
    chat_history = ChatMessageHistory()
    
    print("\nChatbot pronta. Scrivi 'esci' per terminare.")
    print("----------------------------------------------------")
    while True:
        try:
            query = input("Tu: ")
            if query.lower() in ["esci", "quit", "exit"]:
                print("Chatbot: Arrivederci!")
                break
            if not query.strip():
                continue
            
            print("Chatbot: Sto pensando...")
            response = rag_chain({"input": query, "chat_history": chat_history.messages})
            answer = response.get("answer", "Non ho trovato una risposta.")
            print(f"Chatbot: {answer}\n")
            chat_history.add_user_message(query)
            chat_history.add_ai_message(answer)
        except KeyboardInterrupt:
            print("\nChatbot: Arrivederci!")
            break
        except Exception as e:
            print(f"Errore: {e}")
        print("----------------------------------------------------")

def main_chat():
    import sys
    
    # Check for parameters
    index_only = '--index_only' in sys.argv
    interactive = '--interactive' in sys.argv
    
    if index_only:
        print("Modalità solo indicizzazione attivata.")
        print("Creazione/aggiornamento del vectorstore...")
        vectorstore = get_vectorstore(force_recreate=True)
        if vectorstore:
            print("Indicizzazione completata con successo!")
        else:
            print("Errore durante l'indicizzazione.")
        return
    
    if interactive:
        print("Modalità interattiva forzata.")
        run_interactive_chat()
        return
    
    print("Inizializzazione chatbot...")
    
    # Check if vectorstore exists
    vectorstore_exists = os.path.exists(VECTORSTORE_PATH)
    
    if vectorstore_exists:
        print(f"Vectorstore esistente trovato in: {VECTORSTORE_PATH}")
        recreate = input("Rigenerare vectorstore? (s/N): ").lower() == 's'
        enable_indexing = True  # Always enable if recreating
    else:
        print("Nessun vectorstore esistente trovato.")
        enable_indexing = input("Abilitare indicizzazione? (S/n): ").lower() != 'n'
        recreate = enable_indexing  # Force creation if indexing is enabled
    
    if not enable_indexing:
        print("Indicizzazione disabilitata. Il bot non potrà rispondere a domande.")
        print("Avvio comunque per scopi di test...")
        # Create a mock vectorstore or handle gracefully
        vectorstore = None
    else:
        vectorstore = get_vectorstore(force_recreate=recreate)
        if not vectorstore:
            print("Errore nella creazione del vectorstore.")
            return
    
    if vectorstore:
        rag_chain = create_rag_chain(vectorstore)
        if rag_chain is None:
            print("Errore interno: la catena RAG non è inizializzata!")
            return
    else:
        rag_chain = None

    chat_history = ChatMessageHistory()

    print("\nChatbot pronta. Scrivi 'esci' per terminare.")
    if not enable_indexing:
        print("NOTA: Indicizzazione disabilitata - il bot risponderà solo con messaggi di test.")
    print("----------------------------------------------------")
    while True:
        try:
            query = input("Tu: ")
            if query.lower() in ["esci", "quit"]:
                print("Chatbot: Arrivederci!")
                break
            if not query.strip():
                continue
            
            if not enable_indexing or not rag_chain:
                print("Chatbot: Indicizzazione disabilitata. Non posso rispondere a domande sui documenti.")
                print("Chatbot: Per abilitare le risposte, riavvia il bot e abilita l'indicizzazione.")
            else:
                print("Chatbot: Sto pensando...")
                response = rag_chain({"input": query, "chat_history": chat_history.messages})
                answer = response.get("answer", "Non ho trovato una risposta.")
                print(f"Chatbot: {answer}\n")
                chat_history.add_user_message(query)
                chat_history.add_ai_message(answer)
        except Exception as e:
            print(f"Errore: {e}")
        print("----------------------------------------------------")

if __name__ == "__main__":
    import sys
    
    # Show help if requested
    if '--help' in sys.argv or '-h' in sys.argv:
        print("StudentsBot - Chatbot per informazioni Università Cattolica")
        print("\nDESCRIZIONE:")
        print("  Bot conversazionale che risponde a domande su corsi, esami, servizi")
        print("  e procedure dell'Università Cattolica utilizzando documenti crawlati.")
        print("\nUSO:")
        print("  python bot_review.py                    # Modalità configurazione guidata")
        print("  python bot_review.py --interactive      # Chat diretto (richiede vectorstore)")
        print("  python bot_review.py --index_only       # Solo indicizzazione (senza chat)")
        print("  python bot_review.py --help             # Mostra questo aiuto")
        print("\nPARAMETRI:")
        print("  --interactive   Avvia direttamente il chat senza prompt di configurazione")
        print("                  Richiede un vectorstore già esistente")
        print("  --index_only    Crea/aggiorna solo il vectorstore senza avviare il chat")
        print("                  Forza la rigenerazione completa dell'indice")
        print("  --help, -h      Mostra questo messaggio di aiuto")
        print("\nFILE DI CONFIGURAZIONE:")
        print(f"  📁 Documenti markdown: {MARKDOWN_DIR}/")
        print(f"  🗄️  Vectorstore FAISS:  {VECTORSTORE_PATH}/")
        print("  🔑 API Keys Google:     .env (GOOGLE_API_KEY)")
        print("\nESEMPI D'USO:")
        print("  # Prima configurazione")
        print("  python bot_review.py --index_only")
        print("  python bot_review.py --interactive")
        print("")
        print("  # Query massive da Excel")
        print("  python batch_query.py 'domande chatbot.xlsx' risultati.json")
        print("\nNOTE:")
        print("  - La modalità --interactive richiede un vectorstore già creato")
        print("  - Utilizzare --index_only per creare l'indice la prima volta")
        print("  - Il file .env deve contenere GOOGLE_API_KEY per l'API Gemini")
        sys.exit(0)
    
    load_dotenv()
    main_chat()
