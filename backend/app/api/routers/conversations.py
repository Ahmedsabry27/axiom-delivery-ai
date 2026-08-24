import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.runtime.context import RuntimeContext
from app.services.runtime_service import runtime

router = APIRouter(
    prefix="/api/conversations",
    tags=["conversations"],
)


# --------------------------------------------------
# Temporary In-Memory Storage
# --------------------------------------------------

conversations = {}

messages = {}


# --------------------------------------------------
# Models
# --------------------------------------------------


class ConversationCreateRequest(BaseModel):
    title: str = "New Conversation"


class ConversationRenameRequest(BaseModel):
    title: str


class ConversationRequest(BaseModel):
    conversation_id: str | None = None

    message: str


class ConversationResponse(BaseModel):
    conversation_id: str

    message: str

    agent: str

    actions: list[str]

    status: str

    metadata: dict = {}

    timestamp: datetime


# --------------------------------------------------
# Create Conversation
# --------------------------------------------------


@router.post("")
def create_conversation(request: ConversationCreateRequest):

    conversation_id = str(uuid.uuid4())

    conversation = {
        "id": conversation_id,
        "title": request.title,
        "created_at": datetime.now(UTC),
    }

    conversations[conversation_id] = conversation

    messages[conversation_id] = []

    return conversation


# --------------------------------------------------
# Get Conversations
# --------------------------------------------------


@router.get("")
def get_conversations():

    return list(conversations.values())


# --------------------------------------------------
# Get Messages
# --------------------------------------------------


@router.get("/{conversation_id}/messages")
def get_messages(conversation_id: str):

    if conversation_id not in messages:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return messages[conversation_id]


# --------------------------------------------------
# Rename Conversation
# --------------------------------------------------


@router.patch("/{conversation_id}")
def rename_conversation(conversation_id: str, request: ConversationRenameRequest):

    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversations[conversation_id]["title"] = request.title

    return conversations[conversation_id]


# --------------------------------------------------
# Delete Conversation
# --------------------------------------------------


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: str):

    conversations.pop(conversation_id, None)

    messages.pop(conversation_id, None)

    return {"status": "deleted"}


# --------------------------------------------------
# Runtime Execution
# --------------------------------------------------


@router.post(
    "/message",
    response_model=ConversationResponse,
)
async def send_message(
    request: ConversationRequest,
):

    conversation_id = request.conversation_id or str(uuid.uuid4())

    if conversation_id not in conversations:
        conversations[conversation_id] = {
            "id": conversation_id,
            "title": request.message[:60],
            "created_at": datetime.now(UTC),
        }

        messages[conversation_id] = []

    # -----------------------------
    # Store User Message
    # -----------------------------

    messages[conversation_id].append(
        {
            "id": str(uuid.uuid4()),
            "role": "user",
            "content": request.message,
            "timestamp": datetime.now(UTC),
        }
    )

    # -----------------------------
    # Runtime Context
    # -----------------------------

    context = RuntimeContext(
        request_id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        conversation_id=uuid.UUID(conversation_id),
        tenant_id="default",
        user_id="anonymous",
        goal=request.message,
        trace_id=str(uuid.uuid4()),
        metadata={"conversation_id": conversation_id},
    )

    # -----------------------------
    # Execute Runtime
    # -----------------------------

    result = await runtime.run(context)

    output = result.output if isinstance(result.output, dict) else {}

    # -----------------------------
    # Clean Assistant Message
    # -----------------------------

    assistant_message = {
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": "Workflow completed successfully.",
        "metadata": {
            "workflow_id": output.get("workflow_id"),
            "agent": output.get("agent", "default-agent"),
            "status": output.get("state", "COMPLETED"),
            "tasks_total": output.get("tasks_total", 0),
            "tasks_completed": output.get("tasks_completed", 0),
            "duration_ms": output.get("duration_ms"),
            "actions": [],
        },
        "timestamp": datetime.now(UTC),
    }

    messages[conversation_id].append(assistant_message)

    return {
        "conversation_id": conversation_id,
        "message": assistant_message["content"],
        "agent": assistant_message["metadata"]["agent"],
        "actions": [],
        "status": assistant_message["metadata"]["status"],
        "metadata": assistant_message["metadata"],
        "timestamp": datetime.now(UTC),
    }
