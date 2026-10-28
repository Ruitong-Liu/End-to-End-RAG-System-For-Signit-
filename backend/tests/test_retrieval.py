import numpy as np
from app.config import Settings
from app.ingest import Chunk
from app.retrieval import Retriever, rrf
from app.evaluate import metrics

CHUNKS = [Chunk('a','password reset email verification','password.md','password',7,[]),Chunk('b','report export CSV','export.md','Reports',5,[]),Chunk('c','human support hours','support.md','Support',5,[])]
class Encoder:
    def encode(self, texts, **kwargs):
        return np.array([[1.,0.] if 'password' in t else [0.,1.] for t in texts])
class Reranker:
    def predict(self,pairs,**kwargs):
        return np.array([.9 if 'password' in text else .1 for q,text in pairs])

def test_rrf_consensus_and_duplicates():
    assert rrf([[0,1,1],[1,2]])[0] == 1
    assert rrf([[],[]]) == []

def test_dense_hybrid_cache(tmp_path):
    s=Settings(index_dir=str(tmp_path),retrieval_mode='hybrid',top_k=2)
    r=Retriever(s,CHUNKS,encoder=Encoder())
    assert r.search('password')[0]['id']=='a'
    assert r.search('password','dense')[0]['id']=='a'
    assert r.search('password') == r.search('password')
    assert list(tmp_path.glob('*.npy'))

def test_bm25_no_models(tmp_path):
    r=Retriever(Settings(retrieval_mode='bm25'),CHUNKS)
    assert r.search('password')[0]['source']=='password.md'
    assert r.search('xxzzqq') == []
    assert r.vectors is None

def test_document_metrics():
    hits=[{'source':'a','aliases':['duplicate']},{'source':'b'}]
    assert metrics(hits,['duplicate','b']) == (1,1)
    assert metrics(hits,['b']) == (1,.5)
    assert metrics(hits,[]) == (None,None)


def test_api_title_is_searchable_when_body_only_has_parameters():
    chunks=[Chunk('x','client_id client_secret grant_type','authentication/access_token.md','Query',4,[])]
    r=Retriever(Settings(retrieval_mode='bm25'),chunks)
    assert r.search('access_token')[0]['id']=='x'
