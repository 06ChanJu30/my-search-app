# -*- coding: utf-8 -*-
"""OPS 지침 검색 순위 (2026-10 개선) - app.py의 지침 검색과 JSON API가 같이 쓴다. streamlit 없이 동작.

예전 규칙(검색어 단어가 "전부" 들어 있어야 결과)은 "고소작업대 경사로에서 써도 돼?" 같은 문장·구어 질문을 0건으로
만들었다. 바꾼 규칙 (오르빗 qa_search/ops/ops_search.py의 search_combined와 같은 점수 - 현장 실제 질문 20건 1순위 7 -> 19):
  - 검색어를 단어로 나누고, 조사·어미("~할 때", "써도 돼?", "~방법", "기준")는 빼고, 끝 조사는 떼어 본다.
    자료에 없는 말은 앞부분만 남겨 보고, 끝내 없으면 점수에서 뺀다
  - 현장 용어 사전(ops_synonyms.json: 아시바 -> 비계 등)으로 같은 뜻 단어도 같이 찾는다
  - 단어마다 제목에 있으면 +10(제목 단어 중간에만 맞으면 절반), 본문에만 있으면 +3. 흔한 말일수록 작게,
    본문에 자주 나올수록(길이 대비) 조금 더, 붙은 두 단어가 구절로 나오면 더
  - 단어 절반 이상이 맞거나 제목에 맞은 단어가 있는 지침만 결과. 0건이면 가장 흔한 단어부터 빼고 다시 찾는다
"""

import json
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SYNONYMS_JSON = os.path.join(HERE, "ops_synonyms.json")  # pages/01의 synonyms.json(검색어 -> id 목록)과 다른 파일
TITLE_POINTS, BODY_POINTS = 10, 3
STOPWORDS = {
    "때", "할", "할때", "하는", "하기", "하면", "해도", "써도", "돼", "되나", "되나요", "돼요", "되요", "될까", "되는",
    "방법", "기준", "어떻게", "뭐", "뭐야", "무엇", "알려줘", "보여줘", "찾아줘", "있어", "있나", "있는", "없는", "곳", "것", "거",
    "전", "후", "시", "중", "및", "등", "관련", "대한", "위한", "좀", "그", "이", "저", "더", "해", "해줘", "가능", "가능해",
}
ENDINGS = ("에서는", "에서도", "으로는", "에서", "으로", "에게", "할때", "하는", "하기", "해도", "해서", "가서", "에는",
           "에도", "까지", "부터", "보다", "처럼", "이랑", "랑", "와", "과", "을", "를", "이", "가", "은", "는", "의",
           "에", "로", "도", "만", "기")


def normalize(text) -> str:
    return re.sub(r"[\s\W_]+", "", str(text).lower())


def title_key(title) -> str:
    """제목 -> ' 단어 단어' (단어마다 앞에 공백) - ' '+말로 단어 머리 일치를 본다."""
    return "".join(" " + w for w in re.split(r"[\s\W_]+", str(title).lower()) if w)


def load_synonyms(path: str = SYNONYMS_JSON) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    out = {}
    for k, v in raw.items():
        if str(k).startswith("_"):
            continue
        vals = v if isinstance(v, list) else [v]
        out[normalize(k)] = [normalize(x) for x in vals if normalize(x)]
    return out


def build_corpus(titles, bodies) -> list:
    """[(제목 키, 정규화 본문)] - app.py는 df['title'], df['search_normalized']로 한 번 만들어 캐시."""
    return [(title_key(t), str(b or "").lower()) for t, b in zip(titles, bodies)]


def _in_corpus(form, corpus):
    return any(form in t or form in b for t, b in corpus)


def query_terms(query, corpus, syn) -> list:
    terms = []
    for tok in re.findall(r"[0-9a-z가-힣]+", str(query).lower()):
        if tok in STOPWORDS or len(tok) < 2 and not tok.isdigit():
            continue
        forms = [tok] + [tok[:-len(e)] for e in ENDINGS if tok.endswith(e) and len(tok) - len(e) >= 2]
        chosen = next((f for f in forms if f in syn or _in_corpus(f, corpus)), None)
        if chosen is None:
            chosen = next((tok[:n] for n in range(len(tok) - 1, 1, -1) if _in_corpus(tok[:n], corpus)), None)
        if chosen is None or chosen in STOPWORDS:
            continue
        variants = [chosen] + [v for v in syn.get(chosen, []) if v != chosen]
        if variants not in terms:
            terms.append(variants)
    return terms


def _weights(terms, corpus):
    n = len(corpus) or 1
    out = []
    for variants in terms:
        df = sum(1 for t, b in corpus if any(v in t or v in b for v in variants))
        out.append(max(0.05, math.log((n + 1) / (df + 1)) / math.log(n + 1)))
    return out


def _score(terms, title, body, ws, avg_len):
    score = matched = in_title = 0
    for variants, w in zip(terms, ws):
        count = sum(body.count(v) for v in variants)
        if any(v in title for v in variants):
            head = any(" " + v in title for v in variants)
            score, matched, in_title = score + TITLE_POINTS * w * (1 if head else 0.5), matched + 1, in_title + 1
        elif count:
            score, matched = score + BODY_POINTS * w, matched + 1
        tf = count / (count + 1.2 * (0.25 + 0.75 * len(body) / avg_len)) if count else 0
        score += 2 * w * tf
    for (a, wa), (b, wb) in zip(zip(terms, ws), zip(terms[1:], ws[1:])):
        joined = [x + y for x in a for y in b]
        if any(j in title for j in joined):
            score += TITLE_POINTS * (wa + wb) / 2
        elif any(j in body for j in joined):
            score += BODY_POINTS * (wa + wb) / 2
    return round(score, 3), matched, in_title


def rank(query, corpus, syn=None):
    """반환: (결과 [(위치, 점수)] 점수 높은 순, 일부만 맞은 것 [(위치, 점수)], 0건이라 뺀 단어 목록).
    위치는 corpus(= df) 순서 번호 - app.py에서 df.iloc[...]로 쓴다."""
    syn = load_synonyms() if syn is None else syn
    terms = query_terms(query, corpus, syn)
    dropped = []
    avg_len = sum(len(b) for _, b in corpus) / max(len(corpus), 1)
    while True:
        need = (len(terms) + 1) // 2
        ws = _weights(terms, corpus)
        scored = [(i, *_score(terms, t, b, ws, avg_len)) for i, (t, b) in enumerate(corpus)] if terms else []
        hits = [x for x in scored if x[2] >= max(need, 1) or x[3]]
        if hits or len(terms) <= 1:
            break
        df = [sum(_score([v], t, b, [1], avg_len)[1] for t, b in corpus) for v in terms]
        k = df.index(max(df))
        dropped.append(terms[k][0])
        terms = [v for i, v in enumerate(terms) if i != k]
    hits.sort(key=lambda x: (-x[1], x[0]))
    shown = {i for i, *_ in hits}
    partial = sorted(((i, s) for i, s, m, _ in scored if m >= 1 and i not in shown), key=lambda x: (-x[1], x[0]))
    return [(i, s) for i, s, _, _ in hits], partial, dropped
