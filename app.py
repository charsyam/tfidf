import math
import re
from collections import Counter
from functools import lru_cache
from threading import Lock

from flask import Flask, jsonify, request
from kiwipiepy import Kiwi
from nltk.stem import PorterStemmer
from ranking import parameters, score_documents

app = Flask(__name__, static_folder='static', static_url_path='')
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024
stemmer = PorterStemmer()
analysis_lock = Lock()
# Curated learning defaults; users can replace this list for their corpus.
EN_STOP = set("""a an the am is are was were be been being have has had do does did
 i me my mine we us our ours you your yours he him his she her hers it its
 they them their theirs this that these those who whom which what
 and or but if because as until while of at by for with about against
 between into through during before after above below to from up down
 in out on off over under again further then once here there when where
 why how all any both each few more most other some such no nor not only
 own same so than too very can will just should now would could may might
 must shall also don't doesn't didn't isn't aren't wasn't weren't
 haven't hasn't hadn't won't wouldn't can't couldn't shouldn't""".split())
KO_STOP = set("""이 그 저 이것 그것 저것 여기 거기 저기 나 너 우리 저희 여러분
 자신 누구 무엇 어디 언제 것 수 등 및 또는 그리고 그러나 하지만 그래서
 따라서 또한 즉 아주 매우 좀 더 가장 다시 모두 여러 어떤 이런 그런 저런
 하 되 있 없 이다 아니다 은 는 이 가 을 를 에 에서 에게 한테 께 와 과
 의 도 만 로 으로 부터 까지 보다 처럼 다 요 고 며 면 지 게""".split())


@lru_cache(maxsize=4)
def korean_analyzer(words):
    analyzer = Kiwi(num_workers=1)
    for word in words:
        analyzer.add_user_word(word, 'NNP', score=5)
    return analyzer


def analyze(payload):
    mode = payload.get('mode', 'ko')
    if mode not in ('ko', 'en'):
        raise ValueError('언어 모드를 확인해 주세요.')
    texts = payload.get('documents', [])
    if not isinstance(texts, list) or not 1 <= len(texts) <= 10:
        raise ValueError('문장을 1~10개 입력해 주세요.')
    if any(not isinstance(t, str) or not t.strip() or len(t) > 500 for t in texts):
        raise ValueError('각 문장에는 1~500자의 내용을 입력해 주세요.')
    dictionary = payload.get('dictionary', [])
    if not isinstance(dictionary, list) or len(dictionary) > 30 or any(
        not isinstance(w, str) or not w.strip() or len(w) > 50 or re.search(r'\s', w) for w in dictionary
    ):
        raise ValueError('사용자 사전에는 공백 없는 단어를 최대 30개 등록할 수 있습니다.')
    words = tuple(sorted(set(dictionary)))
    options = payload.get('options', {})
    if not isinstance(options, dict):
        raise ValueError('처리 옵션을 확인해 주세요.')
    lower = bool(options.get('lower', True))
    stemming = bool(options.get('stemming', True))
    filtering = bool(options.get('filter', True))
    stop = bool(options.get('stop', True))
    stopwords = payload.get('stopwords', sorted(KO_STOP if mode == 'ko' else EN_STOP))
    if not isinstance(stopwords, list) or len(stopwords) > 300 or any(
        not isinstance(w, str) or not w.strip() or len(w) > 50 or re.search(r'\s', w) for w in stopwords
    ):
        raise ValueError('불용어는 공백 없는 토큰을 최대 300개 입력할 수 있습니다.')
    stop_set = {w.lower().replace('’', "'") for w in stopwords}
    query_text = payload.get('query', '')
    if not isinstance(query_text, str) or len(query_text) > 500:
        raise ValueError('검색어는 500자 이하의 문자열이어야 합니다.')
    params = parameters(payload.get('parameters', {}))
    documents = []
    with analysis_lock:
        kiwi = korean_analyzer(words) if mode == 'ko' else None
        for text in texts + [query_text]:
            if kiwi:
                raw = [{'form': t.form, 'tag': t.tag, 'surface': text[t.start:t.start+t.len]} for t in kiwi.tokenize(text)]
            else:
                raw = [{'form': t, 'tag': 'WORD' if re.search(r'\w', t) else 'PUNCT', 'surface': t}
                       for t in re.findall(r"\w+(?:['’]\w+)*|[^\w\s]", text)]
            tokens = []
            for token in raw:
                normalized = token['form'].lower() if lower else token['form']
                # Porter lowercasing is controlled explicitly by the preceding stage.
                is_stopword = stop and normalized.lower().replace('’', "'") in stop_set
                root = stemmer.stem(normalized, to_lowercase=False) if mode == 'en' and stemming and token['tag'] == 'WORD' and not is_stopword else normalized
                reason = ''
                if filtering:
                    if mode == 'ko' and not token['tag'].startswith(('NN', 'VV', 'VA', 'MAG', 'SL', 'SN', 'XR')):
                        reason = '조사·어미·기호 등 제외 품사'
                    elif mode == 'en' and token['tag'] == 'PUNCT':
                        reason = '문장부호 제외'
                if is_stopword:
                    reason = '불용어 목록에 포함'
                tokens.append({**token, 'lower': normalized, 'root': root, 'included': not reason, 'reason': reason, 'stopword': is_stopword})
            counts = Counter(t['root'] for t in tokens if t['included'])
            documents.append({'text': text, 'tokens': tokens, 'counts': dict(counts), 'total': sum(counts.values())})
    query_document = documents.pop()
    vocabulary = sorted(set().union(*(d['counts'] for d in documents)))
    n = len(documents)
    terms = []
    for word in vocabulary:
        df = sum(word in d['counts'] for d in documents)
        idf = math.log(n / df)
        cells = []
        for doc in documents:
            count = doc['counts'].get(word, 0)
            tf = count
            cells.append({'count': count, 'tf': tf, 'score': tf * idf})
        terms.append({'word': word, 'df': df, 'idf': idf, 'cells': cells})
    return {'documents': documents, 'terms': terms, 'n': n,
            'retrieval': score_documents(documents, query_document, params)}


@app.get('/')
def index():
    return app.send_static_file('index.html')


@app.get('/api/stopwords')
def default_stopwords():
    return jsonify(ko=sorted(KO_STOP), en=sorted(EN_STOP))


@app.post('/api/analyze')
def api_analyze():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error='입력 데이터를 확인해 주세요.'), 400
    try:
        return jsonify(analyze(payload))
    except ValueError as error:
        return jsonify(error=str(error)), 400


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5050)
