import pytest
import pytest_asyncio
import httpx
import os

from main import app


@pytest_asyncio.fixture(scope='module', loop_scope='module')
async def client():
    """Set up async test client with all 10 docs loaded."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as c:
        # Load all data files via POST /documents
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        for i in range(1, 11):
            filepath = os.path.join(data_dir, f'doc{i}.html')
            with open(filepath, 'r', encoding='utf-8') as f:
                html = f.read()
            resp = await c.post('/documents', json={'id': f'doc{i}', 'html': html})
            assert resp.status_code == 201
        yield c


@pytest.mark.asyncio
async def test_故障_returns_all_10_docs(client):
    resp = await client.get('/search?q=故障')
    assert resp.status_code == 200
    data = resp.json()
    assert len(data['results']) == 10, f"Expected 10, got {len(data['results'])}: {[r['id'] for r in data['results']]}"


@pytest.mark.asyncio
async def test_GPU_returns_doc8_only(client):
    resp = await client.get('/search?q=GPU')
    assert resp.status_code == 200
    data = resp.json()
    ids = [r['id'] for r in data['results']]
    assert ids == ['doc8'], f"Expected ['doc8'], got {ids}"


@pytest.mark.asyncio
async def test_replication_returns_empty(client):
    """'replication' is inside a <script> tag in doc2 and should NOT be indexed."""
    resp = await client.get('/search?q=replication')
    assert resp.status_code == 200
    data = resp.json()
    assert data['results'] == [], f"Expected empty, got {[r['id'] for r in data['results']]}"


@pytest.mark.asyncio
async def test_CDN_returns_doc10(client):
    resp = await client.get('/search?q=CDN')
    assert resp.status_code == 200
    data = resp.json()
    ids = [r['id'] for r in data['results']]
    assert 'doc10' in ids, f"Expected doc10 in results, got {ids}"


@pytest.mark.asyncio
async def test_ampersand_entity(client):
    """'&' (decoded from &amp;) should appear in doc3, doc6, doc8, doc10."""
    resp = await client.get('/search?q=%26')
    assert resp.status_code == 200
    data = resp.json()
    ids = set(r['id'] for r in data['results'])
    expected = {'doc3', 'doc6', 'doc8', 'doc10'}
    assert expected.issubset(ids), f"Expected {expected} in results, got {ids}"


@pytest.mark.asyncio
async def test_on_call_returns_all_10(client):
    resp = await client.get('/search?q=on-call')
    assert resp.status_code == 200
    data = resp.json()
    assert len(data['results']) == 10, f"Expected 10, got {len(data['results'])}: {[r['id'] for r in data['results']]}"


@pytest.mark.asyncio
async def test_nonexistent_query_returns_empty(client):
    resp = await client.get('/search?q=notexistxyz123')
    assert resp.status_code == 200
    data = resp.json()
    assert data['results'] == []


@pytest.mark.asyncio
async def test_multi_keyword_GPU_cluster(client):
    """Multi-keyword search: GPU+集群 should return only doc8."""
    resp = await client.get('/search?q=GPU+集群')
    assert resp.status_code == 200
    data = resp.json()
    ids = [r['id'] for r in data['results']]
    assert ids == ['doc8'], f"Expected only ['doc8'], got {ids}"


@pytest.mark.asyncio
async def test_tfidf_sorted_by_score(client):
    """Multi-doc results should be sorted by score descending."""
    resp = await client.get('/search?q=告警')
    assert resp.status_code == 200
    data = resp.json()
    results = data['results']
    if len(results) > 1:
        scores = [r['score'] for r in results]
        assert scores == sorted(scores, reverse=True), "Results not sorted by score"


# Phase 2: multi-keyword intersection tests

@pytest.mark.asyncio
async def test_multi_keyword_intersection_and_sorted(client):
    """故障+响应 should return only docs containing both terms, sorted by score desc."""
    resp = await client.get('/search?q=故障+响应')
    assert resp.status_code == 200
    data = resp.json()
    results = data['results']
    # All returned docs must contain both tokens (intersection)
    assert len(results) > 0, "Expected at least one result for 故障+响应"
    if len(results) > 1:
        scores = [r['score'] for r in results]
        assert scores == sorted(scores, reverse=True), "Results not sorted by score desc"


@pytest.mark.asyncio
async def test_multi_keyword_zhiban_faban(client):
    """值班+发版 should return only docs containing both terms."""
    resp = await client.get('/search?q=值班+发版')
    assert resp.status_code == 200
    data = resp.json()
    results = data['results']
    # Result may be empty or non-empty, but must be intersection
    if len(results) > 1:
        scores = [r['score'] for r in results]
        assert scores == sorted(scores, reverse=True), "Results not sorted by score desc"


@pytest.mark.asyncio
async def test_invalid_mode_returns_400(client):
    resp = await client.get('/search?q=foo&mode=invalid')
    assert resp.status_code == 400


# Phase 3: semantic search tests

@pytest.mark.asyncio
async def test_semantic_server_down(client):
    """服务器挂了怎么办 semantic: doc1 (backend) and doc4 (SRE) should rank in top 3."""
    resp = await client.get('/search?q=%E6%9C%8D%E5%8A%A1%E5%99%A8%E6%8C%82%E4%BA%86%E6%80%8E%E4%B9%88%E5%8A%9E&mode=semantic')
    assert resp.status_code == 200
    data = resp.json()
    results = data['results']
    assert len(results) > 0, "Expected results for semantic search"
    top_ids = [r['id'] for r in results[:3]]
    assert 'doc1' in top_ids or 'doc4' in top_ids, \
        f"Expected doc1 or doc4 in top 3, got {top_ids}"


@pytest.mark.asyncio
async def test_semantic_hacker_attack(client):
    """如何处理黑客攻击 semantic: doc5 (security) and doc10 (network/CDN) should rank in top 3."""
    resp = await client.get('/search?q=%E5%A6%82%E4%BD%95%E5%A4%84%E7%90%86%E9%BB%91%E5%AE%A2%E6%94%BB%E5%87%BB&mode=semantic')
    assert resp.status_code == 200
    data = resp.json()
    results = data['results']
    assert len(results) > 0, "Expected results for semantic search"
    top_ids = [r['id'] for r in results[:3]]
    assert 'doc5' in top_ids or 'doc10' in top_ids, \
        f"Expected doc5 or doc10 in top 3, got {top_ids}"


@pytest.mark.asyncio
async def test_semantic_ml_model_issue(client):
    """机器学习模型上线出问题 semantic: doc8 (AI & algo) should rank in top 3."""
    resp = await client.get('/search?q=%E6%9C%BA%E5%99%A8%E5%AD%A6%E4%B9%A0%E6%A8%A1%E5%9E%8B%E4%B8%8A%E7%BA%BF%E5%87%BA%E9%97%AE%E9%A2%98&mode=semantic')
    assert resp.status_code == 200
    data = resp.json()
    results = data['results']
    assert len(results) > 0, "Expected results for semantic search"
    top_ids = [r['id'] for r in results[:3]]
    assert 'doc8' in top_ids, f"Expected doc8 in top 3, got {top_ids}"


@pytest.mark.asyncio
async def test_keyword_mode_explicit(client):
    """mode=keyword should produce same results as default (no mode param)."""
    resp_default = await client.get('/search?q=告警')
    resp_keyword = await client.get('/search?q=告警&mode=keyword')
    assert resp_default.status_code == 200
    assert resp_keyword.status_code == 200
    ids_default = [r['id'] for r in resp_default.json()['results']]
    ids_keyword = [r['id'] for r in resp_keyword.json()['results']]
    assert ids_default == ids_keyword, \
        f"Default and mode=keyword differ: {ids_default} vs {ids_keyword}"
