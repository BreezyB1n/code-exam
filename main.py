import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import parser as html_parser
import indexer
import semantic

# In-memory document store: doc_id -> {title, text}
docs: dict[str, dict] = {}
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, 'data')
STATIC_DIR = os.path.join(BASE_DIR, 'static')


class DocumentIn(BaseModel):
    id: str
    html: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load all documents from data/ directory at startup
    if os.path.isdir(DATA_DIR):
        for filename in sorted(os.listdir(DATA_DIR)):
            if filename.endswith('.html'):
                doc_id = filename[:-5]  # strip .html
                filepath = os.path.join(DATA_DIR, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    html = f.read()
                parsed = html_parser.parse_html(html)
                docs[doc_id] = parsed
        if docs:
            await indexer.rebuild(docs)
            await asyncio.to_thread(semantic.rebuild, docs)
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'http://localhost:5500',
        'http://127.0.0.1:5500',
        'http://localhost:8000',
        'http://127.0.0.1:8000',
    ],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Mount static files
if os.path.isdir(STATIC_DIR):
    app.mount('/static', StaticFiles(directory=STATIC_DIR), name='static')


@app.get('/')
async def index():
    index_path = os.path.join(STATIC_DIR, 'index.html')
    return FileResponse(index_path)


@app.get('/health')
async def health():
    return {
        'status': 'ok',
        'docs_loaded': len(docs),
        'semantic_model': semantic.model_status(),
    }


@app.post('/documents', status_code=201)
async def add_document(doc: DocumentIn):
    parsed = html_parser.parse_html(doc.html)
    docs[doc.id] = parsed
    await indexer.rebuild(docs)
    await asyncio.to_thread(semantic.rebuild, docs)
    return {'id': doc.id, 'title': parsed['title']}


@app.get('/search')
async def search(q: str = '', mode: str = 'keyword'):
    if mode not in ('keyword', 'semantic'):
        raise HTTPException(status_code=400, detail="mode must be 'keyword' or 'semantic'")

    if not q:
        return {'query': q, 'results': []}
    if mode == 'keyword':
        # Keyword mode: use TF-IDF indexer
        results = await indexer.tfidf_search(q, docs)
    else:
        results = semantic.cosine_search(q)
    return {'query': q, 'results': results}
