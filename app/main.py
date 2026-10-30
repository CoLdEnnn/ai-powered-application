from contextlib import asynccontextmanager
from pathlib import Path
import logging
from typing import Literal
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from .config import Settings
from .llm import LocalLlamaClient, LocalModelError
from .prompting import PromptTooLong
from .retrieval import RetrievalInputError, RetrievalUnavailable
from .service import AssistantService, AssistantBusy

LOGGER=logging.getLogger(__name__)
STATIC=Path(__file__).parent/'static'


class ChatRequest(BaseModel):
    question: str=Field(min_length=2,max_length=1200)
    audience: Literal['all','applicant','current_student']='all'

    @field_validator('question')
    @classmethod
    def clean_question(cls,value):
        value=value.strip()
        if len(value)<2:
            raise ValueError('Enter a question with at least two characters.')
        return value


def create_app(config_path: str | Path='config.json', service_override=None) -> FastAPI:
    settings=Settings.load(config_path)

    @asynccontextmanager
    async def lifespan(app):
        if service_override is not None:
            app.state.service=service_override
        else:
            from .retrieval import Retriever
            retriever=Retriever(settings.corpus_path,settings.index_dir,settings.embedding_model,settings.embedding_cache,threads=settings.embedding_threads)
            retriever.warm_up()
            app.state.service=AssistantService(settings,retriever,LocalLlamaClient(settings.llama_base_url,settings.request_timeout_seconds))
        yield
        if service_override is None:
            app.state.service.close()

    app=FastAPI(title='AITU Local Assistant',version='0.1.0',lifespan=lifespan)
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_methods=['*'],allow_headers=['*'])
    app.mount('/static',StaticFiles(directory=STATIC),name='static')

    @app.get('/',include_in_schema=False)
    def home():
        return FileResponse(STATIC/'index.html')

    @app.get('/api/health')
    def health(request: Request):
        service=request.app.state.service
        return {'status':'ready' if service.model.ready() else 'model_unavailable','model_variant':settings.model_variant,'evidence_status':'pending_team_review','source_snapshot_date':'2026-10-21','conversation_mode':'independent_questions'}

    @app.post('/api/chat')
    def chat(payload: ChatRequest,request: Request):
        if len(payload.question)>settings.max_question_chars:
            raise HTTPException(422,detail=f'Question exceeds the configured {settings.max_question_chars}-character limit.')
        try:
            return request.app.state.service.ask(payload.question,payload.audience)
        except AssistantBusy as exc:
            raise HTTPException(429,detail=str(exc)) from exc
        except (PromptTooLong, RetrievalInputError) as exc:
            raise HTTPException(422,detail=str(exc)) from exc
        except (LocalModelError, RetrievalUnavailable) as exc:
            LOGGER.warning('Local assistant failed: %s',exc)
            raise HTTPException(503,detail=str(exc)) from exc

    return app
