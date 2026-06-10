#!/usr/bin/env python3
"""
Script per valutare le risposte del RAG chatbot confrontando answer con true_answer.
Legge un file JSON con query, answer e true_answer e calcola diverse metriche di valutazione.
"""

import sys
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Tuple
import difflib
from collections import Counter
import math

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
            
        # Filtra solo le risposte valide (non errori)
        valid_results = []
        for item in results:
            if not item.get('answer', '').startswith('ERRORE:'):
                valid_results.append(item)
                
        return valid_results
        
    except Exception as e:
        print(f"Errore nel caricamento del file JSON: {e}")
        return []

def normalize_text(text: str) -> str:
    """Normalizza il testo per il confronto."""
    if not text:
        return ""
    
    # Converti in minuscolo
    text = text.lower()
    
    # Rimuovi punteggiatura e caratteri speciali
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Normalizza spazi
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def extract_keywords(text: str) -> set:
    """Estrae parole chiave dal testo."""
    normalized = normalize_text(text)
    
    # Lista di stop words italiane base
    stop_words = {
        'il', 'la', 'lo', 'le', 'gli', 'un', 'una', 'uno', 'di', 'da', 'del', 'della', 
        'dello', 'delle', 'degli', 'dei', 'dal', 'dalla', 'dallo', 'dalle', 'dagli', 
        'dai', 'in', 'su', 'per', 'tra', 'fra', 'con', 'senza', 'sopra', 'sotto',
        'e', 'o', 'ma', 'però', 'quindi', 'che', 'chi', 'cui', 'dove', 'quando',
        'come', 'perché', 'se', 'questo', 'questa', 'questi', 'queste', 'quello',
        'quella', 'quelli', 'quelle', 'suo', 'sua', 'suoi', 'sue', 'mio', 'mia',
        'miei', 'mie', 'nostro', 'nostra', 'nostri', 'nostre', 'vostro', 'vostra',
        'vostri', 'vostre', 'loro', 'è', 'sono', 'sei', 'siamo', 'siete', 'era',
        'erano', 'ero', 'eri', 'eravamo', 'eravate', 'sarà', 'sarai', 'saremo',
        'sarete', 'saranno', 'ho', 'hai', 'ha', 'abbiamo', 'avete', 'hanno'
    }
    
    words = normalized.split()
    keywords = {word for word in words if word not in stop_words and len(word) > 2}
    
    return keywords

def calculate_similarity_score(answer: str, true_answer: str) -> float:
    """Calcola un punteggio di similarità tra answer e true_answer."""
    if not answer or not true_answer:
        return 0.0
    
    # Normalizza i testi
    norm_answer = normalize_text(answer)
    norm_true = normalize_text(true_answer)
    
    # Calcola similarità usando difflib
    similarity = difflib.SequenceMatcher(None, norm_answer, norm_true).ratio()
    
    return similarity

def calculate_keyword_overlap(answer: str, true_answer: str) -> Dict[str, float]:
    """Calcola l'overlap delle parole chiave tra answer e true_answer."""
    keywords_answer = extract_keywords(answer)
    keywords_true = extract_keywords(true_answer)
    
    if not keywords_true:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    
    overlap = keywords_answer.intersection(keywords_true)
    
    # Precision: quante delle parole chiave dell'answer sono corrette
    precision = len(overlap) / len(keywords_answer) if keywords_answer else 0.0
    
    # Recall: quante delle parole chiave corrette sono state trovate
    recall = len(overlap) / len(keywords_true)
    
    # F1 score
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "overlap_count": len(overlap),
        "answer_keywords": len(keywords_answer),
        "true_keywords": len(keywords_true)
    }

def calculate_length_metrics(answer: str, true_answer: str) -> Dict[str, Any]:
    """Calcola metriche sulla lunghezza delle risposte."""
    len_answer = len(answer) if answer else 0
    len_true = len(true_answer) if true_answer else 0
    
    length_ratio = len_answer / len_true if len_true > 0 else 0.0
    
    words_answer = len(answer.split()) if answer else 0
    words_true = len(true_answer.split()) if true_answer else 0
    
    words_ratio = words_answer / words_true if words_true > 0 else 0.0
    
    return {
        "char_answer": len_answer,
        "char_true": len_true,
        "char_ratio": length_ratio,
        "words_answer": words_answer,
        "words_true": words_true,
        "words_ratio": words_ratio
    }

def calculate_rouge_n(candidate: str, reference: str, n: int = 1) -> Dict[str, float]:
    """Calcola ROUGE-N score tra candidate e reference."""
    if not candidate or not reference:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    
    # Normalizza e tokenizza
    candidate_tokens = normalize_text(candidate).split()
    reference_tokens = normalize_text(reference).split()
    
    if len(candidate_tokens) < n or len(reference_tokens) < n:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    
    # Genera n-grammi
    def get_ngrams(tokens: List[str], n: int) -> List[Tuple[str, ...]]:
        return [tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]
    
    candidate_ngrams = Counter(get_ngrams(candidate_tokens, n))
    reference_ngrams = Counter(get_ngrams(reference_tokens, n))
    
    # Calcola overlap
    overlap = sum((candidate_ngrams & reference_ngrams).values())
    
    # Calcola precision, recall, F1
    precision = overlap / sum(candidate_ngrams.values()) if candidate_ngrams else 0.0
    recall = overlap / sum(reference_ngrams.values()) if reference_ngrams else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1
    }

def calculate_rouge_l(candidate: str, reference: str) -> Dict[str, float]:
    """Calcola ROUGE-L score basato sulla Longest Common Subsequence."""
    if not candidate or not reference:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    
    candidate_tokens = normalize_text(candidate).split()
    reference_tokens = normalize_text(reference).split()
    
    if not candidate_tokens or not reference_tokens:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    
    # Calcola LCS usando programmazione dinamica
    def lcs_length(seq1: List[str], seq2: List[str]) -> int:
        m, n = len(seq1), len(seq2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if seq1[i-1] == seq2[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])
        
        return dp[m][n]
    
    lcs_len = lcs_length(candidate_tokens, reference_tokens)
    
    precision = lcs_len / len(candidate_tokens)
    recall = lcs_len / len(reference_tokens)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1
    }

def calculate_bleu_score(candidate: str, reference: str, max_n: int = 4) -> Dict[str, float]:
    """Calcola BLEU score tra candidate e reference."""
    if not candidate or not reference:
        return {"bleu": 0.0, "brevity_penalty": 1.0, "precision_scores": [0.0] * max_n}
    
    candidate_tokens = normalize_text(candidate).split()
    reference_tokens = normalize_text(reference).split()
    
    if not candidate_tokens or not reference_tokens:
        return {"bleu": 0.0, "brevity_penalty": 1.0, "precision_scores": [0.0] * max_n}
    
    # Calcola precision per ogni n-gram
    precision_scores = []
    
    for n in range(1, max_n + 1):
        if len(candidate_tokens) < n:
            precision_scores.append(0.0)
            continue
            
        # Genera n-grammi
        candidate_ngrams = Counter()
        reference_ngrams = Counter()
        
        for i in range(len(candidate_tokens) - n + 1):
            ngram = tuple(candidate_tokens[i:i+n])
            candidate_ngrams[ngram] += 1
            
        for i in range(len(reference_tokens) - n + 1):
            ngram = tuple(reference_tokens[i:i+n])
            reference_ngrams[ngram] += 1
        
        # Calcola clipped precision
        clipped_matches = 0
        total_candidate_ngrams = 0
        
        for ngram, count in candidate_ngrams.items():
            clipped_matches += min(count, reference_ngrams.get(ngram, 0))
            total_candidate_ngrams += count
        
        precision = clipped_matches / total_candidate_ngrams if total_candidate_ngrams > 0 else 0.0
        precision_scores.append(precision)
    
    # Calcola brevity penalty
    candidate_length = len(candidate_tokens)
    reference_length = len(reference_tokens)
    
    if candidate_length > reference_length:
        brevity_penalty = 1.0
    else:
        brevity_penalty = math.exp(1 - reference_length / candidate_length) if candidate_length > 0 else 0.0
    
    # Calcola BLEU finale (media geometrica delle precision)
    if all(p > 0 for p in precision_scores):
        geometric_mean = math.exp(sum(math.log(p) for p in precision_scores) / len(precision_scores))
        bleu = brevity_penalty * geometric_mean
    else:
        bleu = 0.0
    
    return {
        "bleu": bleu,
        "brevity_penalty": brevity_penalty,
        "precision_scores": precision_scores
    }

def evaluate_single_response(item: Dict[str, Any]) -> Dict[str, Any]:
    """Valuta una singola risposta."""
    query = item.get('query', '')
    answer = item.get('answer', '')
    true_answer = item.get('true_answer', '')
    
    # Calcola diverse metriche
    similarity = calculate_similarity_score(answer, true_answer)
    keyword_metrics = calculate_keyword_overlap(answer, true_answer)
    length_metrics = calculate_length_metrics(answer, true_answer)
    
    # Calcola metriche ROUGE e BLEU
    rouge_1 = calculate_rouge_n(answer, true_answer, n=1)
    rouge_2 = calculate_rouge_n(answer, true_answer, n=2)
    rouge_l = calculate_rouge_l(answer, true_answer)
    bleu_metrics = calculate_bleu_score(answer, true_answer)
    
    return {
        "query": query,
        "answer": answer,
        "true_answer": true_answer,
        "similarity_score": similarity,
        "keyword_metrics": keyword_metrics,
        "length_metrics": length_metrics,
        "rouge_metrics": {
            "rouge_1": rouge_1,
            "rouge_2": rouge_2,
            "rouge_l": rouge_l
        },
        "bleu_metrics": bleu_metrics,
        "timestamp": item.get('timestamp', '')
    }

def calculate_aggregate_metrics(evaluations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calcola metriche aggregate su tutte le valutazioni."""
    if not evaluations:
        return {}
    
    # Raccogli tutte le metriche
    similarities = [eval_item["similarity_score"] for eval_item in evaluations]
    precisions = [eval_item["keyword_metrics"]["precision"] for eval_item in evaluations]
    recalls = [eval_item["keyword_metrics"]["recall"] for eval_item in evaluations]
    f1_scores = [eval_item["keyword_metrics"]["f1"] for eval_item in evaluations]
    
    # Raccogli metriche ROUGE e BLEU
    rouge_1_f1 = [eval_item["rouge_metrics"]["rouge_1"]["f1"] for eval_item in evaluations]
    rouge_2_f1 = [eval_item["rouge_metrics"]["rouge_2"]["f1"] for eval_item in evaluations]
    rouge_l_f1 = [eval_item["rouge_metrics"]["rouge_l"]["f1"] for eval_item in evaluations]
    bleu_scores = [eval_item["bleu_metrics"]["bleu"] for eval_item in evaluations]
    
    # Calcola statistiche aggregate
    aggregate = {
        "total_responses": len(evaluations),
        "similarity": {
            "mean": sum(similarities) / len(similarities),
            "min": min(similarities),
            "max": max(similarities),
            "std": math.sqrt(sum((x - sum(similarities)/len(similarities))**2 for x in similarities) / len(similarities))
        },
        "keyword_precision": {
            "mean": sum(precisions) / len(precisions),
            "min": min(precisions),
            "max": max(precisions)
        },
        "keyword_recall": {
            "mean": sum(recalls) / len(recalls),
            "min": min(recalls),
            "max": max(recalls)
        },
        "keyword_f1": {
            "mean": sum(f1_scores) / len(f1_scores),
            "min": min(f1_scores),
            "max": max(f1_scores)
        },
        "rouge_metrics": {
            "rouge_1_f1": {
                "mean": sum(rouge_1_f1) / len(rouge_1_f1),
                "min": min(rouge_1_f1),
                "max": max(rouge_1_f1)
            },
            "rouge_2_f1": {
                "mean": sum(rouge_2_f1) / len(rouge_2_f1),
                "min": min(rouge_2_f1),
                "max": max(rouge_2_f1)
            },
            "rouge_l_f1": {
                "mean": sum(rouge_l_f1) / len(rouge_l_f1),
                "min": min(rouge_l_f1),
                "max": max(rouge_l_f1)
            }
        },
        "bleu_metrics": {
            "mean": sum(bleu_scores) / len(bleu_scores),
            "min": min(bleu_scores),
            "max": max(bleu_scores)
        }
    }
    
    # Classificazione per fasce di qualità
    excellent = sum(1 for s in similarities if s >= 0.8)
    good = sum(1 for s in similarities if 0.6 <= s < 0.8)
    fair = sum(1 for s in similarities if 0.4 <= s < 0.6)
    poor = sum(1 for s in similarities if s < 0.4)
    
    aggregate["quality_distribution"] = {
        "excellent (≥0.8)": {"count": excellent, "percentage": excellent / len(similarities) * 100},
        "good (0.6-0.8)": {"count": good, "percentage": good / len(similarities) * 100},
        "fair (0.4-0.6)": {"count": fair, "percentage": fair / len(similarities) * 100},
        "poor (<0.4)": {"count": poor, "percentage": poor / len(similarities) * 100}
    }
    
    return aggregate

def save_evaluation_results(evaluations: List[Dict[str, Any]], aggregate: Dict[str, Any], output_file: str):
    """Salva i risultati della valutazione in un file JSON."""
    results = {
        "evaluation_timestamp": datetime.now().isoformat(),
        "aggregate_metrics": aggregate,
        "detailed_evaluations": evaluations
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

def print_summary(aggregate: Dict[str, Any]):
    """Stampa un riassunto delle metriche aggregate."""
    print("\n" + "="*60)
    print("RIASSUNTO VALUTAZIONE RAG")
    print("="*60)
    
    print(f"Risposte totali valutate: {aggregate['total_responses']}")
    
    print(f"\nSIMILARITÀ TESTUALE:")
    print(f"  Media: {aggregate['similarity']['mean']:.3f}")
    print(f"  Min:   {aggregate['similarity']['min']:.3f}")
    print(f"  Max:   {aggregate['similarity']['max']:.3f}")
    print(f"  Std:   {aggregate['similarity']['std']:.3f}")
    
    print(f"\nPAROLE CHIAVE:")
    print(f"  Precision media: {aggregate['keyword_precision']['mean']:.3f}")
    print(f"  Recall media:    {aggregate['keyword_recall']['mean']:.3f}")
    print(f"  F1 Score medio:  {aggregate['keyword_f1']['mean']:.3f}")
    
    print(f"\nMETRICHE ROUGE:")
    rouge = aggregate['rouge_metrics']
    print(f"  ROUGE-1 F1: {rouge['rouge_1_f1']['mean']:.3f} (min: {rouge['rouge_1_f1']['min']:.3f}, max: {rouge['rouge_1_f1']['max']:.3f})")
    print(f"  ROUGE-2 F1: {rouge['rouge_2_f1']['mean']:.3f} (min: {rouge['rouge_2_f1']['min']:.3f}, max: {rouge['rouge_2_f1']['max']:.3f})")
    print(f"  ROUGE-L F1: {rouge['rouge_l_f1']['mean']:.3f} (min: {rouge['rouge_l_f1']['min']:.3f}, max: {rouge['rouge_l_f1']['max']:.3f})")
    
    print(f"\nMETRICHE BLEU:")
    bleu = aggregate['bleu_metrics']
    print(f"  BLEU Score: {bleu['mean']:.3f} (min: {bleu['min']:.3f}, max: {bleu['max']:.3f})")
    
    print(f"\nDISTRIBUZIONE QUALITÀ:")
    for quality, stats in aggregate['quality_distribution'].items():
        print(f"  {quality}: {stats['count']} ({stats['percentage']:.1f}%)")

def main():
    """Funzione principale."""
    if len(sys.argv) < 2 or '--help' in sys.argv or '-h' in sys.argv:
        print("RAG Evaluation Tool per StudentsBot")
        print("Calcola metriche di similarità, ROUGE, BLEU e keyword overlap")
        print("\nUSO:")
        print("  python rageval.py <file_json> [output_file]")
        print("\nPARAMETRI:")
        print("  file_json     File JSON con query, answer, true_answer")
        print("  output_file   File di output per i risultati dettagliati (opzionale)")
        print("  --help, -h    Mostra questo aiuto")
        print("\nMETRICHE CALCOLATE:")
        print("  - Similarità testuale (difflib)")
        print("  - ROUGE-1, ROUGE-2, ROUGE-L")
        print("  - BLEU score")
        print("  - Keyword overlap (precision, recall, F1)")
        print("\nESEMPI:")
        print("  python rageval.py risultati.json")
        print("  python rageval.py risultati.json valutazione.json")
        sys.exit(1)
    
    json_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Carica i dati
    print(f"Caricamento dati da: {json_file}")
    data = load_evaluation_data(json_file)
    
    if not data:
        print("Errore: Nessun dato valido trovato nel file JSON.")
        sys.exit(1)
    
    print(f"Trovate {len(data)} risposte valide da valutare...")
    
    # Esegui valutazioni
    evaluations = []
    for i, item in enumerate(data, 1):
        print(f"Valutazione {i}/{len(data)}", end='\r')
        evaluation = evaluate_single_response(item)
        evaluations.append(evaluation)
    
    print(f"\nValutazione completata per {len(evaluations)} risposte.")
    
    # Calcola metriche aggregate
    aggregate = calculate_aggregate_metrics(evaluations)
    
    # Salva risultati se richiesto
    if output_file:
        save_evaluation_results(evaluations, aggregate, output_file)
        print(f"Risultati dettagliati salvati in: {output_file}")
    
    # Stampa riassunto
    print_summary(aggregate)

if __name__ == "__main__":
    main()