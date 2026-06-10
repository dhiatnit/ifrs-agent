#!/usr/bin/env python3
"""
Script per valutare le risposte del RAG usando un LLM come giudice.
Confronta answer e true_answer utilizzando lo stesso modello LLM per determinare l'equivalenza semantica.
"""

import sys
import json
import os
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate

# Carica le variabili d'ambiente
load_dotenv()

# Configurazione modello (stessa del bot)
MODEL_NAME_LLM = "gemini-2.0-flash"

def load_evaluation_data(json_file: str) -> List[Dict[str, Any]]:
    """Carica i dati di valutazione dal file JSON."""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Estrai i risultati dal formato batch_query
        if isinstance(data, dict) and 'results' in data:
            results = data['results']
        elif isinstance(data, list):
            results = data
        else:
            raise ValueError("Formato JSON non riconosciuto")
            
        # Filtra solo le risposte valide (non errori) che hanno true_answer
        valid_results = []
        for item in results:
            answer = item.get('answer', '')
            true_answer = item.get('true_answer', '')
            
            if (not answer.startswith('ERRORE:') and 
                answer and true_answer and 
                answer.strip() and true_answer.strip()):
                valid_results.append(item)
                
        return valid_results
        
    except Exception as e:
        print(f"Errore nel caricamento del file JSON: {e}")
        return []

def create_judge_prompt() -> ChatPromptTemplate:
    """Crea il prompt per il giudizio LLM."""
    
    system_message = """Sei un giudice esperto che valuta la qualità e correttezza delle risposte di un chatbot universitario.

Il tuo compito è confrontare due risposte alla stessa domanda:
1. ANSWER: La risposta generata dal chatbot
2. TRUE_ANSWER: La risposta corretta di riferimento

Devi determinare se le due risposte sono semanticamente equivalenti, cioè se trasmettono sostanzialmente le stesse informazioni corrette.

CRITERI DI VALUTAZIONE:
- Le risposte sono EQUIVALENTI se:
  * Forniscono le stesse informazioni principali
  * Hanno lo stesso significato sostanziale
  * Sono entrambe corrette (anche se con formulazioni diverse)
  * Includono gli stessi dettagli importanti

- Le risposte NON sono equivalenti se:
  * Forniscono informazioni contraddittorie
  * Una è corretta e l'altra sbagliata
  * Mancano informazioni cruciali in una delle due
  * Il significato generale è diverso

FORMATO RISPOSTA:
Devi rispondere ESCLUSIVAMENTE con un JSON nel seguente formato:
{{
  "equivalent": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "breve spiegazione del giudizio"
}}

IMPORTANTE: 
- Sii rigoroso ma ragionevole nella valutazione
- Considera che risposte diverse nella forma possono essere equivalenti nel contenuto
- La confidence deve riflettere quanto sei sicuro del giudizio (1.0 = certezza assoluta, 0.5 = incerto)
- Il reasoning deve essere conciso ma giustificare la decisione"""

    human_message = """DOMANDA:
{query}

ANSWER (risposta del chatbot):
{answer}

TRUE_ANSWER (risposta corretta):
{true_answer}

Valuta se le due risposte sono semanticamente equivalenti e rispondi in formato JSON."""

    return ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("human", human_message)
    ])

def initialize_llm():
    """Inizializza il modello LLM."""
    try:
        llm = ChatGoogleGenerativeAI(
            model=MODEL_NAME_LLM, 
            temperature=0.1,
            convert_system_message_to_human=False
        )
        return llm
    except Exception as e:
        print(f"Errore nell'inizializzazione del modello LLM: {e}")
        return None

def judge_response_pair(llm, prompt_template, query: str, answer: str, true_answer: str) -> Dict[str, Any]:
    """Usa l'LLM per giudicare una coppia di risposte."""
    try:
        # Crea la chain
        chain = prompt_template | llm
        
        # Esegui il giudizio
        response = chain.invoke({
            "query": query,
            "answer": answer,
            "true_answer": true_answer
        })
        
        # Estrai il contenuto della risposta
        response_text = response.content.strip()
        
        # Prova a parsare il JSON dalla risposta
        try:
            # Trova il JSON nella risposta (potrebbe esserci testo extra)
            import re
            json_match = re.search(r'\{[^}]*"equivalent"[^}]*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                judgment = json.loads(json_str)
            else:
                # Fallback: prova a parsare tutta la risposta
                judgment = json.loads(response_text)
            
            # Valida la struttura
            if not all(key in judgment for key in ["equivalent", "confidence", "reasoning"]):
                raise ValueError("Struttura JSON non valida")
                
            return {
                "equivalent": bool(judgment["equivalent"]),
                "confidence": float(judgment["confidence"]),
                "reasoning": str(judgment["reasoning"]),
                "raw_response": response_text,
                "status": "success"
            }
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            # Se il parsing JSON fallisce, prova a inferire la risposta
            response_lower = response_text.lower()
            
            if "true" in response_lower or "equivalenti" in response_lower or "equivalents" in response_lower:
                equivalent = True
            elif "false" in response_lower or "non equivalenti" in response_lower or "not equivalent" in response_lower:
                equivalent = False
            else:
                equivalent = False  # Default conservativo
            
            return {
                "equivalent": equivalent,
                "confidence": 0.3,  # Bassa confidence per parsing fallito
                "reasoning": f"Parsing JSON fallito, inferito da testo: {response_text[:100]}...",
                "raw_response": response_text,
                "status": "json_parse_error"
            }
            
    except Exception as e:
        return {
            "equivalent": False,
            "confidence": 0.0,
            "reasoning": f"Errore durante il giudizio: {str(e)}",
            "raw_response": "",
            "status": "error"
        }

def evaluate_with_llm_judge(data: List[Dict[str, Any]], llm, progress_callback=None) -> List[Dict[str, Any]]:
    """Valuta tutti gli elementi usando l'LLM come giudice."""
    prompt_template = create_judge_prompt()
    results = []
    
    for i, item in enumerate(data):
        if progress_callback:
            progress_callback(i + 1, len(data))
        
        query = item.get('query', '')
        answer = item.get('answer', '')
        true_answer = item.get('true_answer', '')
        
        # Esegui il giudizio
        judgment = judge_response_pair(llm, prompt_template, query, answer, true_answer)
        
        # Combina i dati originali con il giudizio
        result = {
            "query": query,
            "answer": answer,
            "true_answer": true_answer,
            "llm_judgment": judgment,
            "timestamp": item.get('timestamp', ''),
            "original_item": item
        }
        
        results.append(result)
    
    return results

def calculate_judgment_statistics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calcola statistiche sui giudizi LLM."""
    if not results:
        return {}
    
    total = len(results)
    equivalent_count = sum(1 for r in results if r["llm_judgment"]["equivalent"])
    
    confidences = [r["llm_judgment"]["confidence"] for r in results]
    avg_confidence = sum(confidences) / len(confidences)
    
    # Statistiche per status
    status_counts = {}
    for r in results:
        status = r["llm_judgment"]["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    
    # Distribuzione per confidence
    high_conf = sum(1 for c in confidences if c >= 0.8)
    medium_conf = sum(1 for c in confidences if 0.5 <= c < 0.8)
    low_conf = sum(1 for c in confidences if c < 0.5)
    
    return {
        "total_evaluations": total,
        "equivalent_responses": equivalent_count,
        "non_equivalent_responses": total - equivalent_count,
        "equivalence_rate": equivalent_count / total * 100,
        "average_confidence": avg_confidence,
        "confidence_distribution": {
            "high (≥0.8)": {"count": high_conf, "percentage": high_conf / total * 100},
            "medium (0.5-0.8)": {"count": medium_conf, "percentage": medium_conf / total * 100},
            "low (<0.5)": {"count": low_conf, "percentage": low_conf / total * 100}
        },
        "processing_status": status_counts
    }

def save_results(results: List[Dict[str, Any]], statistics: Dict[str, Any], output_file: str):
    """Salva i risultati in un file JSON."""
    output_data = {
        "evaluation_timestamp": datetime.now().isoformat(),
        "model_used": MODEL_NAME_LLM,
        "statistics": statistics,
        "detailed_results": results
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

def print_summary(statistics: Dict[str, Any]):
    """Stampa un riassunto delle statistiche."""
    print("\n" + "="*60)
    print("VALUTAZIONE LLM-AS-JUDGE")
    print("="*60)
    
    print(f"Modello utilizzato: {MODEL_NAME_LLM}")
    print(f"Valutazioni totali: {statistics['total_evaluations']}")
    
    print(f"\nRISULTATI EQUIVALENZA:")
    print(f"  Risposte equivalenti:     {statistics['equivalent_responses']} ({statistics['equivalence_rate']:.1f}%)")
    print(f"  Risposte non equivalenti: {statistics['non_equivalent_responses']} ({100-statistics['equivalence_rate']:.1f}%)")
    
    print(f"\nCONFIDENCE:")
    print(f"  Confidence media: {statistics['average_confidence']:.3f}")
    
    print(f"\nDISTRIBUZIONE CONFIDENCE:")
    for level, stats in statistics['confidence_distribution'].items():
        print(f"  {level}: {stats['count']} ({stats['percentage']:.1f}%)")
    
    print(f"\nSTATUS PROCESSAMENTO:")
    for status, count in statistics['processing_status'].items():
        print(f"  {status}: {count}")

def main():
    """Funzione principale."""
    if len(sys.argv) < 2 or '--help' in sys.argv or '-h' in sys.argv:
        print("LLM-as-Judge Evaluation Tool per StudentsBot")
        print("Usa un LLM per valutare l'equivalenza tra answer e true_answer")
        print("\nUSO:")
        print("  python llm_as_judge.py <file_json> [opzioni]")
        print("\nPARAMETRI:")
        print("  file_json     File JSON con query, answer, true_answer")
        print("\nOPZIONI:")
        print("  --output, -o  File di output per risultati dettagliati")
        print("  --help, -h    Mostra questo aiuto")
        print("\nESEMPI:")
        print("  python llm_as_judge.py risultati.json")
        print("  python llm_as_judge.py risultati.json -o giudizi.json")
        sys.exit(1)
    
    json_file = sys.argv[1]
    
    # Parse opzioni
    output_file = None
    for i, arg in enumerate(sys.argv[2:], 2):
        if arg in ['--output', '-o'] and i + 1 < len(sys.argv):
            output_file = sys.argv[i + 1]
    
    # Carica dati
    print(f"Caricamento dati da: {json_file}")
    data = load_evaluation_data(json_file)
    
    if not data:
        print("Errore: Nessun dato valido trovato.")
        print("Assicurati che il JSON contenga 'query', 'answer' e 'true_answer'.")
        sys.exit(1)
    
    print(f"Trovati {len(data)} elementi da valutare...")
    
    # Inizializza LLM
    print("Inizializzazione modello LLM...")
    llm = initialize_llm()
    if not llm:
        print("Errore nell'inizializzazione del modello. Verifica le variabili d'ambiente.")
        sys.exit(1)
    
    print("Modello inizializzato. Inizio valutazione...")
    
    # Esegui valutazioni
    def progress_callback(current, total):
        print(f"Valutazione {current}/{total} ({current/total*100:.1f}%)", end='\r')
    
    results = evaluate_with_llm_judge(data, llm, progress_callback)
    
    print(f"\nValutazione completata per {len(results)} elementi.")
    
    # Calcola statistiche
    statistics = calculate_judgment_statistics(results)
    
    # Salva risultati se richiesto
    if output_file:
        save_results(results, statistics, output_file)
        print(f"Risultati dettagliati salvati in: {output_file}")
    
    # Stampa riassunto
    print_summary(statistics)

if __name__ == "__main__":
    main()