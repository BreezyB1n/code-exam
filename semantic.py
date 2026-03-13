import numpy as np
import os

# Lazy-loaded model and embeddings
_model = None
_model_loaded = False
_model_error = None

doc_embeddings: np.ndarray = np.array([])
doc_ids: list[str] = []
doc_titles: dict[str, str] = {}
doc_texts: dict[str, str] = {}

MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'
CACHE_DIR = os.path.expanduser('~/.cache/huggingface/hub')


def get_model():
    """Lazily load the sentence transformer model."""
    global _model, _model_loaded, _model_error
    if _model_loaded:
        return _model
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME, cache_folder=CACHE_DIR)
        _model_loaded = True
    except Exception as e:
        _model_error = str(e)
        _model_loaded = True  # Mark as attempted
    return _model


def model_status() -> dict:
    """Return model loading status for health check."""
    return {
        'loaded': _model is not None,
        'attempted': _model_loaded,
        'error': _model_error,
        'model': MODEL_NAME,
    }


def rebuild(docs: dict[str, dict]) -> None:
    """Rebuild embeddings for all documents."""
    global doc_embeddings, doc_ids, doc_titles, doc_texts

    model = get_model()
    if model is None:
        return

    ids = list(docs.keys())
    texts = [docs[doc_id]['text'] for doc_id in ids]

    embeddings = model.encode(texts, show_progress_bar=False)

    doc_ids.clear()
    doc_ids.extend(ids)
    doc_titles.clear()
    doc_titles.update({doc_id: docs[doc_id]['title'] for doc_id in ids})
    doc_texts.clear()
    doc_texts.update({doc_id: docs[doc_id]['text'] for doc_id in ids})
    doc_embeddings = np.array(embeddings)


def cosine_search(query: str, top_k: int = 10) -> list[dict]:
    """Search documents using cosine similarity of embeddings."""
    model = get_model()
    if model is None or len(doc_ids) == 0:
        return []

    q_vec = model.encode([query])[0]
    q_norm = np.linalg.norm(q_vec)
    if q_norm == 0:
        return []

    doc_norms = np.linalg.norm(doc_embeddings, axis=1)
    # Avoid division by zero
    valid = doc_norms > 0
    scores = np.zeros(len(doc_ids))
    scores[valid] = (doc_embeddings[valid] @ q_vec) / (doc_norms[valid] * q_norm)

    ranked_indices = np.argsort(-scores)[:top_k]

    results = []
    for idx in ranked_indices:
        doc_id = doc_ids[idx]
        score = float(scores[idx])
        text = doc_texts.get(doc_id, '')
        snippet = text[:150].strip()
        results.append({
            'id': doc_id,
            'title': doc_titles.get(doc_id, ''),
            'snippet': snippet,
            'score': round(score, 4),
        })

    return results
