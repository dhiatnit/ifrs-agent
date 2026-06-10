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
MODEL_NAME_LLM = "gemini-2.0-flash"
MODEL_NAME_EMBEDDINGS = "models/gemini-embedding-001"  # was models/embedding-001, retired by Google (404 as of 2026-06)
BATCH_SIZE = 100
BATCH_WAIT = 2  # secondi

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

from langchain.text_splitter import MarkdownHeaderTextSplitter

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
    # Chunking per intestazioni principali Markdown (più robusto)
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=["#", "##"])
    for doc in documents:
        try:
            chunks = splitter.split_text(doc.page_content)
            for chunk in chunks:
                # Puoi aggiungere come metadata il titolo del chunk se vuoi
                all_chunks.append(Document(page_content=chunk, metadata=doc.metadata))
        except Exception:
            # In caso di problemi fallback: tutto il file in un unico chunk
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
        batch_vs = FAISS.from_documents(batch, embeddings)
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
        "Sei un assistente AI dei corsi magistrali Unicattolica"
        "Quando ti chiedono quali esami ci sono in un corso/curriculum/anno:\n"
        "- Elenca solo i nomi veri degli esami, divisi per anno e per tipo ('obbligatori', 'a scelta'), senza ripetizioni e senza colonne extra ('credits', 'programme', ecc).\n"
        "- Rispondi in forma di elenco PULITO: niente markdown, niente tabelle, niente intestazioni inutili.\n"
        "- Raggruppa sempre per anno e curriculum. Se chiedono solo 'a scelta' o solo 'obbligatori', mostra solo quelli richiesti.\n"
        "- Se la domanda è sugli sbocchi lavorativi o che lavoro si può fare dopo un corso, cerca una sezione 'sbocchi professionali', altrimenti ragiona sui possibili settori lavorativi basandoti sulle materie presenti.\n"
        "- Se chiedono un consiglio su quale corso scegliere per una professione, suggerisci almeno 2 corsi pertinenti spiegando perché.\n"
        "- MAI mostrare output in inglese o tabelle markdown. Solo elenco, in italiano chiaro e ordinato."
        "Riconosci che curriculum, indirizzi, rami, track, percorsi, profili sono la stessa cosa. "
        "Se ti chiedono quali esami ha un corso, devi guardare le tabelle nel curriculum corrispondente all'indirizzo che ti viene chiesto. Se non ti viene specificato l'indirizzo/curriculum , chiedilo."
        "Usa **esclusivamente** le informazioni nei documenti forniti (context)."
        "Dai priorità ai dati concreti, anche se sono in piccole parti dei documenti."
        "Se trovi risposte in tabelle o elenchi, estrai e mostra la lista."
        "Quando il context contiene tabelle o elenchi di esami, mostra la lista esattamente come presente nei documenti, indicando anno/curriculum/corso. "
        "Quando chiedono 'quanti esami' conta il numero di esami (una riga per ciascun esame in tabella o elenco puntato '-'). Trovi queste info nel file elenco_magistrali.md nella cartella output1. "
        "I corsi sia in italiano sia in inglese hanno scritto 'Italiano English'."
        "Quando chiedono 'quali esami', mostra la tabella esami. Trovi queste info nel file elenco_magistrali.md nella cartella output1. "
        "Rispondi in italiano semplice, spiega i termini tecnici se servono. "
        "Capisci e rispondi a domande con sinonimi (esami/materie/rami/indirizzi/curriculum/specializzazioni/tracks/profili). "
        "Non dire mai che non lo sai: se puoi, mostra comunque ciò che hai trovato, anche solo parzialmente. "
        "Sei un assistente AI progettato per aiutare studenti e persone esterne a comprendere informazioni sull’Università Cattolica. "
        "Quando nei documenti compaiono indirizzi o sedi specifiche, indicale sempre come risposta, anche se la domanda non chiede esplicitamente l’indirizzo. "
        "Dai sempre priorità ai dati concreti trovati nel testo, anche se appaiono in piccole parti dei documenti. "
        "Ignora eventuali errori ortografici e interpreta sempre il senso generale della domanda. "
        "Se trovi risposte in tabelle o elenchi, estrai puntualmente la lista. "
        "Non dire mai che non hai trovato la risposta se anche solo una parte della risposta è presente nei documenti. "
        "Se la domanda è generica, chiedi gentilmente di specificare meglio. "
        "Capisci e rispondi a domande poste in modo informale, con errori di scrittura, parafrasi, esempi, abbreviazioni o sinonimi, come farebbe uno studente inesperto o una persona esterna. "
        "Quando trovi dati tabellari, spiegali sempre a parole. "
        "Se ci sono immagini descritte, riporta sempre la descrizione. "
        "Se trovi parole tecniche, spiega il significato in modo semplice e adatto a chi non conosce il mondo universitario. "
        "Se nella domanda si fa riferimento a tabelle, dati o immagini, descrivi il contenuto in modo semplice e immediato. "
        "Rispondi SEMPRE in italiano chiaro e semplice, anche usando esempi pratici. "
        "Distingui bene tra primo/secondo/terzo anno e curriculum (ramo/indirizzo). "
        "Quando ti chiedono quali e quanti corsi sono in inglese/italiano, guarda il campo 'lingua/language' presente in ogni pagina del corso specificato o in elenco_magistrale.md alla fine di ogni riga del corso. "
        "Attenzione: alcuni corsi sono sia in italiano sia in inglese, e alla fine della riga in elenco_magistrale.,md c'è scritto 'Italiano English', devi riportare anche questi se ti vengono chiesti quali e quanti corsi sono in inglese/italiano."
        "Se la domanda riguarda l’elenco dei corsi magistrali (anche per lingua), rispondi leggendo il file ‘elenco_magistrali.md’ senza chiedere di specificare altro. Se la domanda è generica, mostra comunque tutti i corsi disponibili per la lingua richiesta."
        "Quando qualcuno ti chiede quali esami ci sono in un certo corso (o curriculum, indirizzo, ramo, percorso) tu devi guardare il curriculum ed elencare quella tabella."
        "Quando il context contiene tabelle o elenchi di esami, estrai e mostra la lista esattamente come presente nei documenti, indicando anno/curriculum/corso. Se sono presenti più alternative (es: esami a scelta), indicale chiaramente."
        "Se ti chiedono quali esami ci sono in un certo anno scolastico, tu rispondi guardando il curriculum dell'anno richiesto (primo, secondo o terzo). "
        "Fai attenzione al terzo anno perché potrebbe avere diversi curriculum, lo trovi nel piano di studi. "
        "Se la domanda riguarda un anno o un curriculum specifico, mostra solo gli esami dell’anno/curriculum richiesto. "
        "Quando ti chiedono curriculum, indirizzi, rami, percorsi, profili o track considerali sinonimi. "
        "Se ti chiedono quanti esami ci sono in un corso (o curriculum, indirizzo, ramo) conta TUTTI gli esami trovati anche fuori dalle tabelle. Se non c’è una lista completa, conta ogni elemento che sembra un esame in tutto il documento (tabelle, elenchi, testo), senza mai rispondere che il dato non è presente."
        "Quando ti chiedono quanti esami sono obbligatori o a scelta, se riesci cerca di distinguere. Se non si capisce, mostra comunque il conteggio totale e spiega eventuali limiti."
        "Rispondi solo sui dati presenti nei documenti (context). "
        "Curriculum/indirizzo/ramo/track/specializzazione = sinonimi. "
        "Dai sempre elenchi, conteggi, dettagli tabelle. "
        "Indica sempre sede/facoltà/lingua/campus se ci sono. "
        "Quando chiedono 'quanti' conta, quando 'quali' mostra lista, filtra per anno/indirizzo. "
        "Rispondi in italiano semplice, anche con esempi. "
        "Non dire mai 'non lo so': mostra sempre ciò che hai trovato, anche parziale. "
        "Se il corso richiesto non è presente nei dati, cerca e mostra la risposta riferita al corso col nome più simile (usando fuzzy match), avvisando sempre l’utente. "
        "Per domande su professioni, consiglia i corsi con più esami e argomenti pertinenti, spiegando con un breve ragionamento. "
        "Non limitarti mai a dire “non trovato”: se trovi anche solo esami simili o curriculum affini, mostra l’elenco e spiega che il consiglio si basa su questo."
        "Quando qualcuno ti chiede quale corso seguire per poter fare un certo lavoro, cerca nei vari sbocchi professionali dei corsi, e se non c'è ragiona sulla risposta in base agli esami di ogni corso più attinenti al lavoro in questione richiesto nella domanda. "
        "Se la domanda riguarda la possibilità di svolgere uno stage, un lavoro o una professione con una certa laurea, e nei documenti non c’è una risposta esatta, allora analizza le materie e le competenze indicate nel corso (esami, curriculum, sbocchi professionali). Se il corso tratta materie di economia, gestione, contabilità, o simili, spiega che in generale con competenze economiche si può lavorare anche nell’ambito contabile/burocratico di settori diversi (es. farmacia, azienda, enti pubblici). Spiega in modo trasparente che la risposta è dedotta sulla base del profilo del corso, non è una garanzia formale. Se possibile, suggerisci di verificare sempre presso l’ente/azienda di interesse o l’ufficio stage."
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
