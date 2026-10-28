import json
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessageChunk
from app.main import create_app
from app.config import Settings
from app.retrieval import Retriever
from app.ingest import Chunk

CHUNKS=[Chunk('a','password reset email verification','guide.md','Reset password',12,[])]
class LLM:
    def __init__(self, answer): self.answer=answer
    async def astream(self,messages):
        yield AIMessageChunk(content=self.answer)

def client(llm=None):
    s=Settings(retrieval_mode='bm25')
    return TestClient(create_app(s,Retriever(s,CHUNKS),llm))

def test_health_validation_and_no_key():
    with client() as c:
        assert c.get('/api/health').json()['chunks']==1
        assert c.post('/api/chat',json={'question':' '}).status_code==422
        assert c.post('/api/chat',json={'question':'x'*1001}).status_code==422
        body=c.post('/api/chat',json={'question':'password'}).text
        assert 'retrieval_only' in body and 'guide.md' in body
        assert 'DEEPSEEK_API_KEY' in body

def test_routes_and_no_evidence():
    with client() as c:
        for q, expected in [('Talk to a human agent','handoff'),('hello','greeting'),('What should I do?','clarify'),('zzxxqq','insufficient_evidence')]:
            assert expected in c.post('/api/chat',json={'question':q}).text

def test_valid_and_invalid_citations():
    for answer, expected in [('Use your registered email to reset your password.[1]','"intent": "answer"'),('Fabricated content[99]','insufficient_evidence'),('No citation','insufficient_evidence')]:
        with client(LLM(answer)) as c:
            body=c.post('/api/chat',json={'question':'password'}).text
            assert expected in body
            if expected=='insufficient_evidence':
                frames = [json.loads(f.split('data: ',1)[1]) for f in body.split('\n\n') if f.startswith('event: replace')]
                assert frames and 'Fabricated content' not in frames[-1]['text']

def test_model_error_is_sanitized():
    class Broken:
        async def astream(self,messages):
            raise RuntimeError('super-secret-key')
            yield
    with client(Broken()) as c:
        body=c.post('/api/chat',json={'question':'password'}).text
        assert 'event: error' in body and 'super-secret-key' not in body


def test_followup_rewrite_with_langchain_fake():
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    model = FakeListChatModel(responses=['password reset', 'Reset your password using your email. [1]'])
    with client(model) as c:
        body=c.post('/api/chat',json={'question':'How do I do that?','history':[{'role':'user','content':'I forgot my password'}]}).text
        assert '"query": "password reset"' in body
        assert '"intent": "answer"' in body


def test_reranker_threshold_and_context_budget():
    from app.service import context_for
    assert context_for([{'source':'a','heading':'b','text':'x'*200}],1)==[]
    s=Settings(retrieval_mode='hybrid_rerank',min_rerank_score=.5)
    r=Retriever(Settings(retrieval_mode='bm25'),CHUNKS)
    r.search=lambda query: [{**CHUNKS[0].__dict__,'score':.1,'rank':1}]
    with TestClient(create_app(s,r,LLM('Wrong answer[1]'))) as c:
        body=c.post('/api/chat',json={'question':'password'}).text
        assert 'insufficient_evidence' in body and 'Wrong answer' not in body


def test_english_question_is_translated_for_chinese_sources():
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    chunks = [Chunk('zh', '\u83b7\u53d6token \u5fc5\u586b\u53c2\u6570 client_id client_secret grant_type', 'token.md', 'Query', 15, [])]
    settings = Settings(retrieval_mode='bm25')
    retriever = Retriever(settings, chunks)
    model = FakeListChatModel(responses=['\u83b7\u53d6token \u5fc5\u586b\u53c2\u6570', 'Required parameters: client_id, client_secret, and grant_type. [1]'])
    with TestClient(create_app(settings, retriever, model)) as c:
        body = c.post('/api/chat', json={'question':'Which parameters are required for an access token?'}).text
        assert '\u83b7\u53d6token' in body
        answer = ''.join(json.loads(f.split('data: ',1)[1])['text'] for f in body.split('\n\n') if f.startswith('event: token'))
        assert 'Required parameters' in answer and '"intent": "answer"' in body


def test_partial_model_error_replaces_provisional_answer():
    class Broken:
        async def astream(self, messages):
            yield AIMessageChunk(content='An incomplete draft')
            raise RuntimeError('private-provider-error')
    with client(Broken()) as c:
        body = c.post('/api/chat', json={'question':'password'}).text
        assert 'An incomplete draft' in body
        assert body.index('event: token') < body.index('event: replace') < body.index('event: error')
        assert 'private-provider-error' not in body
