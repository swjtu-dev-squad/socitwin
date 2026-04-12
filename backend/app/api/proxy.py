import logging
import time

from fastapi import APIRouter

from app.models.proxy import ChatCompletionRequest, ChatCompletionResponse
from app.services.proxy_service import proxy_service


logger = logging.getLogger(__name__)

router = APIRouter(tags=["openai-proxy"])


@router.get("/v1/models")
async def list_models():
    """List proxy-exposed models in an OpenAI-compatible format."""
    return await proxy_service.list_models()


@router.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    """Proxy chat completions to Ollama and fall back to local sentiment analysis."""
    logger.info("Received proxy request for model: %s", request.model)
    return await proxy_service.chat_completions(request)


@router.get("/proxy/health")
async def proxy_health_check():
    """Health check for the proxy module."""
    return {"status": "ok", "timestamp": int(time.time())}
