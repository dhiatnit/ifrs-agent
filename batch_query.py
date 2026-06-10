
#!/usr/bin/env python3
"""
Script per eseguire query massive al chatbot StudentsBot.
Utilizza la funzione query_chatbot estratta da bot_review.py.
"""

import sys
import os
import json
import csv
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd

# Import the query function from bot_review
from bot_review import query_chatbot

def load_questions_from_excel(file_path):
    """Carica le domande e le risposte corrette da un file Excel con colonne 'query' e 'true_answer'."""
    data = []
    
    if not file_path.endswith(('.xlsx', '.xls')):
        raise ValueError("Il file deve essere in formato Excel (.xlsx o .xls)")
    
    try:
        # Load Excel file
        df = pd.read_excel(file_path)
        
        # Check required columns
        required_columns = ['query', 'true_answer']
        if not all(col in df.columns for col in required_columns):
            raise ValueError(f"Il file Excel deve contenere le colonne: {required_columns}")
        
        # Extract data
        for _, row in df.iterrows():
            query = str(row['query']).strip() if pd.notna(row['query']) else ''
            true_answer = str(row['true_answer']).strip() if pd.notna(row['true_answer']) else ''
            
            if query:  # Only add rows with non-empty queries
                data.append({
                    'query': query,
                    'true_answer': true_answer
                })
        
    except Exception as e:
        print(f"Errore nel caricamento del file Excel: {e}")
        return []
    
    return data

def save_results(results, output_file):
    """Salva i risultati in un file (supporta .json, .csv)."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if output_file.endswith('.json'):
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': timestamp,
                'total_queries': len(results),
                'results': results
            }, f, ensure_ascii=False, indent=2)
    
    elif output_file.endswith('.csv'):
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['query', 'answer', 'true_answer', 'timestamp'])
            writer.writeheader()
            for result in results:
                writer.writerow(result)

def batch_query(data, verbose=False, save_to=None):
    """
    Esegue query massive al chatbot.
    
    Args:
        data (list): Lista di dict con 'query' e 'true_answer'
        verbose (bool): Se stampare informazioni dettagliate
        save_to (str): Percorso file dove salvare i risultati
        
    Returns:
        list: Lista di risultati con query, answer e true_answer
    """
    results = []
    total = len(data)
    
    print(f"Inizio elaborazione di {total} query...")
    
    for i, item in enumerate(data, 1):
        query = item['query']
        true_answer = item['true_answer']
        
        if verbose:
            print(f"\n[{i}/{total}] Elaborando: {query}")
        else:
            print(f"Progresso: {i}/{total}")
        
        try:
            answer = query_chatbot(query, verbose=verbose)
            result = {
                'query': query,
                'answer': answer,
                'true_answer': true_answer,
                'timestamp': datetime.now().isoformat()
            }
            results.append(result)
            
            if not verbose:
                print(f"✓ Risposta ottenuta per query {i}")
            
        except Exception as e:
            error_msg = f"Errore per la query '{query}': {e}"
            print(f"✗ {error_msg}")
            result = {
                'query': query,
                'answer': f"ERRORE: {e}",
                'true_answer': true_answer,
                'timestamp': datetime.now().isoformat()
            }
            results.append(result)
    
    print(f"\nElaborazione completata. {len(results)} risultati ottenuti.")
    
    # Salva risultati se richiesto
    if save_to:
        save_results(results, save_to)
        print(f"Risultati salvati in: {save_to}")

    return results

def main():
    """Funzione principale per uso da linea di comando."""
    load_dotenv()
    
    if len(sys.argv) < 2 or '--help' in sys.argv or '-h' in sys.argv:
        print("Batch Query Tool per StudentsBot")
        print("\nUSO:")
        print("  python batch_query.py <file_excel> [output_file] [--verbose] [--limit N]")
        print("\nFORMATO SUPPORTATO:")
        print("  .xlsx, .xls - File Excel con colonne 'query' e 'true_answer'")
        print("\nPARAMETRI:")
        print("  --verbose     Mostra output dettagliato durante l'elaborazione")
        print("  --limit N     Elabora solo le prime N query del file")
        print("  --help, -h    Mostra questo aiuto")
        print("\nESEMPI:")
        print("  python batch_query.py data/queries.xlsx")
        print("  python batch_query.py data/queries.xlsx risultati.json")
        print("  python batch_query.py data/queries.xlsx risultati.json --verbose")
        print("  python batch_query.py data/queries.xlsx risultati.json --limit 10")
        print("  python batch_query.py data/queries.xlsx risultati.json --limit 5 --verbose")
        print("\nESEMPI SUBSET TESTING:")
        print("  python batch_query.py data/queries.xlsx test_5.json --limit 5      # Prime 5 query")
        print("  python batch_query.py data/queries.xlsx test_10.json --limit 10    # Prime 10 query")
        print("  python batch_query.py data/queries.xlsx debug.json --limit 3 --verbose  # Debug veloce")
        sys.exit(1)
    
    excel_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else None
    verbose = '--verbose' in sys.argv
    
    # Parse limit parameter
    limit = None
    if '--limit' in sys.argv:
        try:
            limit_index = sys.argv.index('--limit')
            if limit_index + 1 < len(sys.argv):
                limit = int(sys.argv[limit_index + 1])
                if limit <= 0:
                    print("Errore: il valore di --limit deve essere un numero positivo.")
                    sys.exit(1)
            else:
                print("Errore: --limit richiede un numero.")
                sys.exit(1)
        except ValueError:
            print("Errore: il valore di --limit deve essere un numero valido.")
            sys.exit(1)
    
    if not os.path.exists(excel_file):
        print(f"Errore: File {excel_file} non trovato.")
        sys.exit(1)
    
    # Carica dati dal file Excel
    try:
        data = load_questions_from_excel(excel_file)
        if not data:
            print("Errore: Nessuna query trovata nel file Excel.")
            sys.exit(1)
        
        # Applica il limite se specificato
        total_queries = len(data)
        if limit and limit < total_queries:
            data = data[:limit]
            print(f"Limite applicato: elaborazione di {limit} query su {total_queries} totali")
        
    except Exception as e:
        print(f"Errore nel caricamento dei dati: {e}")
        sys.exit(1)
    
    # Esegui batch query
    results = batch_query(data, verbose=verbose, save_to=output_file)
    
    # Mostra statistiche finali
    successful = len([r for r in results if not r['answer'].startswith('ERRORE:')])
    print(f"\nStatistiche finali:")
    if limit and limit < total_queries:
        print(f"- Query totali nel file: {total_queries}")
        print(f"- Query elaborate (limite): {len(results)}")
    else:
        print(f"- Query elaborate: {len(results)}")
    print(f"- Risposte riuscite: {successful}")
    print(f"- Errori: {len(results) - successful}")

if __name__ == "__main__":
    main()