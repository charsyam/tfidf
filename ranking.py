"""Transparent query scoring; BM25L/+ follow ECIR 2020 Table 1.
Only matching terms contribute. BM25 uses positive (Lucene-style) IDF.
"""
import math

MODELS = ('tfidf', 'bm25', 'bm25l', 'bm25plus')


def parameters(raw):
    if not isinstance(raw, dict):
        raise ValueError('BM25 파라미터를 확인해 주세요.')
    result = {}
    for key, default, minimum, maximum in (
        ('k1', 1.5, 0.01, 5), ('b', 0.75, 0, 1),
        ('delta_l', 0.5, 0, 3), ('delta_plus', 1.0, 0, 3),
    ):
        value = raw.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
            raise ValueError(f'{key} 값은 {minimum}~{maximum} 범위의 숫자여야 합니다.')
        result[key] = value
    return result


def score_documents(documents, query, params):
    n = len(documents)
    avgdl = sum(d['total'] for d in documents) / n
    # Query repetition is deliberately ignored to keep term contributions comparable.
    words = list(dict.fromkeys(t['root'] for t in query['tokens'] if t['included']))
    df = {word: sum(word in d['counts'] for d in documents) for word in words}
    rows = []
    for index, doc in enumerate(documents):
        length = doc['total']
        norm = 1 - params['b'] + params['b'] * length / avgdl if avgdl else 1
        contributions = []
        totals = dict.fromkeys(MODELS, 0.0)
        for word in words:
            frequency = doc['counts'].get(word, 0)
            freq_docs = df[word]
            idfs = {
                'tfidf': math.log(n / freq_docs) if freq_docs else 0,
                'bm25': math.log1p((n - freq_docs + 0.5) / (freq_docs + 0.5)) if freq_docs else 0,
                'bm25l': math.log((n + 1) / (freq_docs + 0.5)) if freq_docs else 0,
                'bm25plus': math.log((n + 1) / freq_docs) if freq_docs else 0,
            }
            weights = dict.fromkeys(MODELS, 0.0)
            c = frequency / norm if frequency else 0
            if frequency:
                base = (params['k1'] + 1) * frequency / (frequency + params['k1'] * norm)
                weights = {
                    'tfidf': frequency,
                    'bm25': base,
                    'bm25l': (params['k1'] + 1) * (c + params['delta_l']) / (params['k1'] + c + params['delta_l']),
                    'bm25plus': base + params['delta_plus'],
                }
            scores = {m: idfs[m] * weights[m] for m in MODELS}
            for m in MODELS:
                totals[m] += scores[m]
            contributions.append({'word': word, 'df': freq_docs, 'frequency': frequency,
                                  'c': c, 'idfs': idfs, 'weights': weights, 'scores': scores})
        rows.append({'index': index, 'length': length, 'norm': norm, 'scores': totals, 'contributions': contributions})
    for row in rows:
        row['ranks'] = {m: 1 + sum(other['scores'][m] > row['scores'][m] and not math.isclose(other['scores'][m], row['scores'][m], rel_tol=1e-12, abs_tol=1e-12) for other in rows) for m in MODELS}
    return {'query': query, 'words': words, 'avgdl': avgdl, 'parameters': params, 'rows': rows}
