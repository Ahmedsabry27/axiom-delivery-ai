from fastapi import APIRouter, HTTPException

from app.models.chat import ChatRequest, ChatResponse
from app.services.chat_service import chat_service

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):

    try:

        answer = chat_service.ask(request.message)

        return ChatResponse(response=answer)

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )