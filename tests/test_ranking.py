import math
import unittest

from app import analyze, app
from ranking import parameters, score_documents


class RankingTests(unittest.TestCase):
    def test_hand_calculated_scores(self):
        result = analyze({'mode': 'en', 'documents': ['cat cat dog', 'dog'], 'query': 'cat',
                          'parameters': {'k1': 1.5, 'b': 0.75, 'delta_l': 0.5, 'delta_plus': 1}})
        ranking = result['retrieval']
        row = ranking['rows'][0]
        self.assertEqual(ranking['avgdl'], 2)
        self.assertEqual(row['norm'], 1.375)
        base = 2.5 * 2 / (2 + 1.5 * 1.375)
        c = 2 / 1.375
        self.assertAlmostEqual(row['scores']['tfidf'], 2 * math.log(2))
        self.assertAlmostEqual(row['scores']['bm25'], math.log(2) * base)
        self.assertAlmostEqual(row['scores']['bm25l'], math.log(2) * 2.5 * (c + 0.5) / (1.5 + c + 0.5))
        self.assertAlmostEqual(row['scores']['bm25plus'], math.log(3) * (base + 1))
        self.assertTrue(all(score == 0 for score in ranking['rows'][1]['scores'].values()))

    def test_query_does_not_change_corpus(self):
        payload = {'mode': 'en', 'documents': ['cats running', 'dogs running'], 'query': 'Cats cats mystery'}
        result = analyze(payload)
        self.assertEqual(result['n'], 2)
        self.assertEqual(result['retrieval']['avgdl'], 2)
        self.assertEqual(result['retrieval']['words'], ['cat', 'mysteri'])
        before = result['terms']
        payload['query'] = 'dogs'
        self.assertEqual(analyze(payload)['terms'], before)
        self.assertEqual(result['retrieval']['rows'][0]['contributions'][1]['df'], 0)
        self.assertTrue(all(v == 0 for v in result['retrieval']['rows'][0]['contributions'][1]['scores'].values()))

    def test_delta_and_length_controls(self):
        docs = [{'counts': {'cat': 1}, 'total': 1}, {'counts': {'cat': 1, 'dog': 9}, 'total': 10}]
        query = {'tokens': [{'root': 'cat', 'included': True}]}
        baseline = score_documents(docs, query, parameters({'b': 0, 'delta_l': 0, 'delta_plus': 0}))
        for model in ('bm25', 'bm25l', 'bm25plus'):
            self.assertEqual(baseline['rows'][0]['scores'][model], baseline['rows'][1]['scores'][model])
            self.assertEqual(baseline['rows'][1]['ranks'][model], 1)
        corrected = score_documents(docs, query, parameters({'b': 1}))
        self.assertGreater(corrected['rows'][0]['scores']['bm25'], corrected['rows'][1]['scores']['bm25'])
        boosted = score_documents(docs, query, parameters({'b': 0, 'delta_l': 1, 'delta_plus': 1}))
        self.assertEqual(boosted['rows'][0]['scores']['bm25'], baseline['rows'][0]['scores']['bm25'])
        self.assertGreater(boosted['rows'][0]['scores']['bm25l'], baseline['rows'][0]['scores']['bm25l'])
        self.assertGreater(boosted['rows'][0]['scores']['bm25plus'], baseline['rows'][0]['scores']['bm25plus'])

    def test_empty_query_and_empty_corpus(self):
        for query in ('', 'the', 'cat'):
            ranking = analyze({'mode': 'en', 'documents': ['the', '...'], 'query': query})['retrieval']
            self.assertEqual(ranking['avgdl'], 0)
            for row in ranking['rows']:
                self.assertTrue(all(score == 0 for score in row['scores'].values()))
                self.assertTrue(all(rank == 1 for rank in row['ranks'].values()))

    def test_query_shares_dictionary_and_stopwords(self):
        ranking = analyze({'mode': 'ko', 'documents': ['초거대언어모델을 공부한다.', '영화 음악'],
                           'dictionary': ['초거대언어모델'], 'stopwords': ['영화'],
                           'query': '초거대언어모델 영화'})['retrieval']
        self.assertEqual(ranking['words'], ['초거대언어모델'])
        self.assertGreater(ranking['rows'][0]['scores']['bm25'], 0)
        self.assertEqual(ranking['rows'][1]['scores']['bm25'], 0)

    def test_raw_tf_ignores_length_and_counts_repetitions(self):
        result = analyze({'mode': 'en', 'documents': ['cat', 'cat dog bird fish', 'cat cat dog', 'dog'], 'query': 'cat'})
        rows = result['retrieval']['rows']
        self.assertGreater(rows[0]['scores']['tfidf'], 0)
        self.assertEqual(rows[0]['scores']['tfidf'], rows[1]['scores']['tfidf'])
        self.assertAlmostEqual(rows[2]['scores']['tfidf'], 2 * rows[0]['scores']['tfidf'])
        cat = next(term for term in result['terms'] if term['word'] == 'cat')
        self.assertEqual([cell['tf'] for cell in cat['cells']], [1, 1, 2, 0])
        self.assertEqual([cell['score'] for cell in cat['cells']], [row['scores']['tfidf'] for row in rows])

    def test_bad_parameters(self):
        with app.test_client() as client:
            for params in ({'b': 2}, {'k1': 0}, {'k1': 'bad'}, {'delta_l': -1}, {'delta_plus': float('nan')}, {'b': True}):
                self.assertEqual(client.post('/api/analyze', json={'mode': 'en', 'documents': ['cat'], 'parameters': params}).status_code, 400)


if __name__ == '__main__':
    unittest.main()
