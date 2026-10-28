import asyncio
import pytest
from langchain_core.messages import AIMessageChunk
from app.config import Settings
from app.ingest import Chunk
from app.retrieval import Retriever
from app.service import SupportService

class GatedModel:
    def __init__(self):
        self.release = asyncio.Event()
        self.waiting = asyncio.Event()
        self.finished = False
        self.closed = False

    async def astream(self, messages):
        try:
            yield AIMessageChunk(content='Reset your password ')
            self.waiting.set()
            await self.release.wait()
            yield AIMessageChunk(content='using email. [1]')
            self.finished = True
        finally:
            self.closed = True

def make_service(model):
    settings = Settings(retrieval_mode='bm25', deepseek_api_key='')
    chunks = [Chunk('a','password reset email','guide.md','Password',5,[])]
    return SupportService(settings, Retriever(settings,chunks),model)

async def first_token(events):
    while True:
        event, data = await anext(events)
        if event == 'token':
            return data

def test_first_delta_is_delivered_while_provider_is_still_blocked():
    async def check():
        model=GatedModel()
        events=make_service(model).events('password',[])
        data=await asyncio.wait_for(first_token(events),2)
        assert data['text']=='Reset your password '
        assert not model.finished
        next_event=asyncio.create_task(anext(events))
        await asyncio.wait_for(model.waiting.wait(),2)
        assert not next_event.done()
        model.release.set()
        assert (await next_event)[0]=='token'
        remaining=[item async for item in events]
        done=next(data for event,data in remaining if event=='done')
        assert done['citations_valid'] is True
        assert done['first_token_ms'] <= done['latency_ms']
        assert model.closed
    asyncio.run(check())

def test_closing_browser_stream_closes_provider_stream():
    async def check():
        model=GatedModel()
        events=make_service(model).events('password',[])
        await first_token(events)
        await events.aclose()
        assert model.closed and not model.finished
    asyncio.run(check())

def test_cancelling_inflight_read_cancels_provider():
    async def check():
        model=GatedModel()
        events=make_service(model).events('password',[])
        await first_token(events)
        pending=asyncio.create_task(anext(events))
        await asyncio.wait_for(model.waiting.wait(),2)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        await events.aclose()
        assert model.closed and not model.finished
    asyncio.run(check())

def test_asgi_disconnect_closes_provider_and_releases_request_slot():
    from fastapi.testclient import TestClient
    from app.main import create_app
    async def check(app,model):
        disconnects=asyncio.Queue()
        first_request=True
        async def receive():
            nonlocal first_request
            if first_request:
                first_request=False
                return {'type':'http.request','body':b'{"question":"password"}','more_body':False}
            return await disconnects.get()
        async def send(message):
            if message['type']=='http.response.body' and b'event: token' in message.get('body',b''):
                await disconnects.put({'type':'http.disconnect'})
        scope={'type':'http','asgi':{'version':'3.0','spec_version':'2.3'},'http_version':'1.1',
               'method':'POST','scheme':'http','path':'/api/chat','raw_path':b'/api/chat',
               'query_string':b'','root_path':'','headers':[(b'content-type',b'application/json')],
               'client':('127.0.0.1',1234),'server':('127.0.0.1',8000)}
        await asyncio.wait_for(app(scope,receive,send),3)
        assert model.closed and not model.finished
        assert app.state.gate._value==2
    model=GatedModel()
    service=make_service(model)
    app=create_app(service.settings,service.retriever,model)
    with TestClient(app):
        asyncio.run(check(app,model))
