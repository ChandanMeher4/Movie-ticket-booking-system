"""Single-Agent AI Assistant router providing conversational ticketing and tool execution."""

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.single_agent import AgentChatResponse, run_single_agent
from app.database import get_db

router = APIRouter(prefix="/api/ai/agent", tags=["single-agent"])


class AgentChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=100, description="Unique conversation session token")
    user_id: int = Field(default=2, description="ID of the authenticated or demo customer")
    message: str = Field(..., min_length=1, max_length=1000, description="Natural language input from the customer")


@router.post("/chat", response_model=AgentChatResponse, status_code=status.HTTP_200_OK)
def agent_chat(payload: AgentChatRequest, db: Session = Depends(get_db)) -> AgentChatResponse:
    """Execute autonomous single-agent conversation turn with tool calling and security guardrails."""
    return run_single_agent(
        db=db,
        session_id=payload.session_id,
        user_id=payload.user_id,
        user_message=payload.message,
    )
