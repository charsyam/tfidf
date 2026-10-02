import math
import unittest

from app import analyze, app


class AnalysisTests(unittest.TestCase):
    def test_scores_and_stemming(self):
        result = analyze({'mode': 'en', 'documents': ['Cats running running.', 'Dogs running.']})
        terms = {t['word']: t for t in result['terms']}
        self.assertEqual(result['documents'][0]['counts'], {'cat': 1, 'run': 2})
        self.assertEqual(terms['run']['idf'], 0)
        self.assertAlmostEqual(terms['cat']['cells'][0]['score'], math.log(2))
        self.assertEqual(terms['cat']['cells'][1]['score'], 0)

    def test_options(self):
        result = analyze({'mode': 'en', 'documents': ['Cats running.'],
                          'options': {'lower': False, 'stemming': False, 'filter': False}})
        self.assertEqual(result['documents'][0]['counts'], {'Cats': 1, 'running': 1, '.': 1})
        result = analyze({'mode': 'en', 'documents': ['The cats are running.'], 'options': {'stop': True}})
        self.assertEqual(result['documents'][0]['counts'], {'cat': 1, 'run': 1})

    def test_empty_filtered_tokens(self):
        result = analyze({'mode': 'en', 'documents': ['...', 'Cats.']})
        self.assertEqual(result['documents'][0]['total'], 0)
        self.assertEqual(result['terms'][0]['cells'][0]['score'], 0)

    def test_korean_dictionary_isolation(self):
        text = '초거대언어모델을 공부한다.'
        custom = analyze({'mode': 'ko', 'documents': [text], 'dictionary': ['초거대언어모델']})
        self.assertIn('초거대언어모델', custom['documents'][0]['counts'])
        self.assertTrue(any(t['tag'].startswith('J') and not t['included'] for t in custom['documents'][0]['tokens']))
        baseline = analyze({'mode': 'ko', 'documents': [text]})
        self.assertNotIn('초거대언어모델', baseline['documents'][0]['counts'])

    def test_custom_stopwords_and_toggle(self):
        payload = {'mode': 'en', 'documents': ['The cats are running.'], 'stopwords': ['RUNNING', 'the', 'are']}
        result = analyze(payload)
        self.assertEqual(result['documents'][0]['counts'], {'cat': 1})
        self.assertTrue(next(t for t in result['documents'][0]['tokens'] if t['form'] == 'running')['stopword'])
        payload['options'] = {'stop': False}
        self.assertIn('run', analyze(payload)['documents'][0]['counts'])
        payload['options'] = {'stop': True}
        payload['stopwords'] = []
        self.assertIn('the', analyze(payload)['documents'][0]['counts'])

    def test_korean_stopwords_independent_of_pos_filter(self):
        result = analyze({'mode': 'ko', 'documents': ['우주 영화는 재미있다.'],
                          'stopwords': ['영화', '는'], 'options': {'filter': False}})
        doc = result['documents'][0]
        self.assertNotIn('영화', doc['counts'])
        self.assertNotIn('는', doc['counts'])
        self.assertIn('우주', doc['counts'])
        self.assertEqual(sum(t['stopword'] for t in doc['tokens']), 2)

    def test_api(self):
        with app.test_client() as client:
            with client.get('/') as response:
                self.assertEqual(response.status_code, 200)
            self.assertEqual(client.post('/api/analyze', json={'documents': []}).status_code, 400)
            self.assertEqual(client.post('/api/analyze', json=[]).status_code, 400)
            self.assertEqual(client.get('/api/stopwords').status_code, 200)
            self.assertEqual(client.post('/api/analyze', json={'mode': 'en', 'documents': ['hello'], 'stopwords': ['two words']}).status_code, 400)
            self.assertEqual(client.post('/api/analyze', json={'mode': 'xx', 'documents': ['hello']}).status_code, 400)
            self.assertEqual(client.post('/api/analyze', json={'mode': 'en', 'documents': ['hello']}).status_code, 200)


if __name__ == '__main__':
    unittest.main()
