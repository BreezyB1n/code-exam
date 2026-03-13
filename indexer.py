import re
import math
import asyncio
import jieba

# Suppress jieba initialization messages
jieba.setLogLevel('ERROR')

# In-memory index state
inverted_index: dict[str, dict[str, int]] = {}  # token -> {doc_id: count}
doc_word_count: dict[str, int] = {}              # doc_id -> total token count
doc_texts: dict[str, str] = {}                   # doc_id -> raw text (for snippet)

_lock = asyncio.Lock()


def tokenize(text: str) -> list[str]:
    """Tokenize text: cut_for_search for finer Chinese segmentation, preserve punctuation tokens."""
    result = []
    for tok in jieba.cut_for_search(text):
        for part in tok.split():
            # Keep both word-chars and standalone punctuation (e.g. '&')
            result.extend(re.findall(r'\w+|[^\w\s]+', part.lower()))
    return result


def _build_index(docs: dict[str, dict]) -> tuple[dict, dict]:
    """Build inverted index and doc word counts from docs dict."""
    new_inverted: dict[str, dict[str, int]] = {}
    new_word_count: dict[str, int] = {}

    for doc_id, doc in docs.items():
        tokens = tokenize(doc['text'])
        new_word_count[doc_id] = len(tokens)
        for tok in tokens:
            posting = new_inverted.setdefault(tok, {})
            posting[doc_id] = posting.get(doc_id, 0) + 1

    return new_inverted, new_word_count


async def rebuild(docs: dict[str, dict]) -> None:
    """Rebuild index atomically (thread-safe)."""
    new_inv, new_wc = _build_index(docs)
    async with _lock:
        global inverted_index, doc_word_count, doc_texts
        inverted_index = new_inv
        doc_word_count = new_wc
        doc_texts = {doc_id: doc['text'] for doc_id, doc in docs.items()}


async def tfidf_search(query: str, docs: dict[str, dict]) -> list[dict]:
    """Search using TF-IDF scoring. Returns list of {id, title, snippet, score}."""
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    async with _lock:
        idx_snapshot = inverted_index
        wc_snapshot = doc_word_count
        texts_snapshot = doc_texts

    N = len(wc_snapshot)
    if N == 0:
        return []

    # Find docs containing all query tokens.
    candidate_sets = [set(idx_snapshot.get(tok, {})) for tok in query_tokens]
    candidate_docs = set.intersection(*candidate_sets)
    if not candidate_docs:
        return []

    # Score candidates using TF-IDF
    results = []
    for doc_id in candidate_docs:
        total_words = wc_snapshot.get(doc_id, 1)
        score = 0.0
        for tok in query_tokens:
            posting = idx_snapshot.get(tok, {})
            tf = posting.get(doc_id, 0) / total_words
            df = len(posting)
            idf = math.log((N + 1) / (df + 1)) + 1
            score += tf * idf

        # Generate snippet: find first token position in text
        text = texts_snapshot.get(doc_id, '')
        snippet = _make_snippet(text, query_tokens)

        results.append({
            'id': doc_id,
            'title': docs[doc_id]['title'],
            'snippet': snippet,
            'score': round(score, 4),
        })

    # Sort by score descending
    results.sort(key=lambda x: x['score'], reverse=True)
    return results


def _make_snippet(text: str, tokens: list[str]) -> str:
    """Extract snippet around first token match."""
    text_lower = text.lower()
    best_pos = len(text)
    for tok in tokens:
        pos = text_lower.find(tok)
        if pos != -1 and pos < best_pos:
            best_pos = pos

    if best_pos == len(text):
        return text[:160].strip()

    start = max(0, best_pos - 80)
    end = min(len(text), best_pos + 80)
    return text[start:end].strip()
