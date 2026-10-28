import asyncio
import anyio
import json
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Literal
from .config import Settings
from .retrieval import Retriever
from .service import SupportService

logger = logging.getLogger(__name__)

class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)

class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: list[Message] = Field(default_factory=list, max_length=12)

def create_app(settings=None, retriever=None, llm=None):
    settings = settings or Settings()
    @asynccontextmanager
    async def lifespan(app):
        app.state.service = SupportService(settings, retriever or await asyncio.to_thread(Retriever, settings), llm)
        app.state.gate = asyncio.Semaphore(2)
        yield
    app = FastAPI(title="Intelligent Customer Support Assistant", lifespan=lifespan)
    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": settings.retrieval_mode, "chunks": len(app.state.service.retriever.chunks),
            "generation_configured": bool(settings.deepseek_api_key), "models_loaded": app.state.service.retriever.vectors is not None}
    @app.post("/api/chat")
    async def chat(request: ChatRequest):
        if not request.question.strip():
            raise HTTPException(422, "Question cannot be blank")
        async def stream():
            events = app.state.service.events(request.question, [m.model_dump() for m in request.history])
            pending = None
            try:
                yield 'event: status\ndata: {"phase":"queued"}\n\n'
                async with app.state.gate:
                    while True:
                        if pending is None:
                            pending = asyncio.create_task(anext(events))
                        ready, _ = await asyncio.wait({pending}, timeout=15)
                        if not ready:
                            # Keep proxies alive while retrieval or the provider is working.
                            yield ': keep-alive\n\n'
                            continue
                        try:
                            event, payload = pending.result()
                        except StopAsyncIteration:
                            break
                        finally:
                            pending = None
                        yield f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Chat request failed")
                yield 'event: replace\ndata: {"text":"The answer could not be completed or verified. Please try again.","reason":"stream_error"}\n\n'
                yield 'event: error\ndata: {"message":"The request failed. Check the server logs and model configuration, then try again."}\n\n'
            finally:
                # Starlette's disconnect cancellation must not interrupt resource cleanup.
                with anyio.CancelScope(shield=True):
                    if pending is not None:
                        pending.cancel()
                        await asyncio.gather(pending, return_exceptions=True)
                    await events.aclose()
        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control":"no-cache", "X-Accel-Buffering":"no"})
    return app

app = create_app()
