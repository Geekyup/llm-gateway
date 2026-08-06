from fastapi import APIRouter, Depends

from app.api.deps import get_gateway_service
from app.auth.deps import get_current_user
from app.auth.models import User
from app.gateway.proxy_service import GatewayService
from app.openai_compat.router import run_chat_completion
from app.openai_compat.schemas import ChatCompletionRequest

router = APIRouter(prefix="/me/playground", tags=["playground"])


@router.post("/chat/completions", operation_id="playground_chat_completions")
async def playground_chat_completions(
    request: ChatCompletionRequest,
    gateway: GatewayService = Depends(get_gateway_service),
    user: User = Depends(get_current_user),
):
    return await run_chat_completion(request, gateway=gateway, user_id=user.id)
