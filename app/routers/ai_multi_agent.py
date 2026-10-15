"""API router for Multi-Agent AI Orchestration endpoints.

Provides endpoints for chatting with the multi-agent system and inspecting agent execution traces.
"""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.multi_agent import (
    AgentStepTrace,
    MultiAgentChatResponse,
    OrchestratorEngine,
    get_session_traces,
)
from app.database import get_db

router = APIRouter(prefix="/api/ai/multi", tags=["ai-multi-agent"])


class MultiAgentChatRequest(BaseModel):
    """Payload for multi-agent conversational interaction."""
    session_id: str = Field(..., min_length=1, description="Unique conversation session identifier")
    user_id: int = Field(default=2, description="Target customer ID")
    message: str = Field(..., min_length=1, max_length=2000, description="User prompt or response")

    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": "session-multi-101",
                "user_id": 2,
                "message": "Show me upcoming showtimes for Interstellar",
            }
        }
    }


class MultiAgentTraceResponse(BaseModel):
    """Response envelope for retrieving execution traces of a session."""
    session_id: str
    traces: List[AgentStepTrace]


@router.post("/chat", response_model=MultiAgentChatResponse, status_code=status.HTTP_200_OK)
def chat_with_multi_agent(
    payload: MultiAgentChatRequest,
    db: Session = Depends(get_db),
) -> MultiAgentChatResponse:
    """Coordinate user intent across specialized agents with CriticAgent validation."""
    return OrchestratorEngine.process_chat(
        db=db,
        session_id=payload.session_id,
        user_id=payload.user_id,
        message=payload.message,
    )


@router.get("/trace/{session_id}", response_model=MultiAgentTraceResponse, status_code=status.HTTP_200_OK)
def get_trace_history(session_id: str) -> MultiAgentTraceResponse:
    """Retrieve the multi-agent execution step traces for an active session."""
    traces = get_session_traces(session_id)
    return MultiAgentTraceResponse(
        session_id=session_id,
        traces=traces,
    )
