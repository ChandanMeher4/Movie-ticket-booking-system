"""Tests for live LLM path, tool-calling execution loop, JSON recovery, and iteration bounds.

Tests the OpenAI-compatible client interactions, validating:
1. Tool-calling multi-turn loop (LLM returns tool_call -> backend executes -> LLM returns text).
2. Malformed / invalid JSON in tool arguments (graceful parsing & fallback).
3. JSON retry prompt in structured output generation.
4. Maximum iteration limit guard (terminates cleanly at MAX_ITERATIONS=6).
"""

import json
from unittest.mock import MagicMock, patch
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.genai_features import recommend_movies
from app.ai.llm_client import LLMResponse, LLMToolCall, llm_client
from app.ai.single_agent import run_single_agent, MAX_ITERATIONS


class FakeFunction:
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class FakeToolCall:
    def __init__(self, tool_id: str, name: str, arguments: str):
        self.id = tool_id
        self.function = FakeFunction(name, arguments)


class FakeMessage:
    def __init__(self, content: str = None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class FakeChoice:
    def __init__(self, message: FakeMessage):
        self.message = message


class FakeChatCompletionResponse:
    def __init__(self, message: FakeMessage):
        self.choices = [FakeChoice(message)]


def test_fake_client_tool_calling_loop_execution(db_session: Session):
    """Verify with fake OpenAI client that the multi-step tool-calling loop executes tool, appends context, and yields final synthesis."""
    session_id = f"llm-test-{uuid.uuid4().hex[:8]}"

    # Mock OpenAI client that:
    # 1. On turn 1 returns tool_call for 'search_movies'
    # 2. On turn 2 returns synthesized text
    turn1_msg = FakeMessage(
        content=None,
        tool_calls=[FakeToolCall("call_123", "search_movies", json.dumps({"query": "Inception"}))],
    )
    turn2_msg = FakeMessage(
        content="We found Inception (Sci-Fi, English) in our active cinema catalog. Showtimes are available.",
        tool_calls=[],
    )

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.side_effect = [
        FakeChatCompletionResponse(turn1_msg),
        FakeChatCompletionResponse(turn2_msg),
    ]

    with patch.object(llm_client, "_client", fake_openai), \
         patch.object(llm_client, "is_mock", False):

        response = run_single_agent(
            db=db_session,
            session_id=session_id,
            user_id=2,
            user_message="Do you have Inception playing?",
        )

        assert response.mock is False
        assert "Inception" in response.reply
        assert len(response.tool_calls_made) == 1
        assert response.tool_calls_made[0]["tool"] == "search_movies"
        assert response.tool_calls_made[0]["arguments"] == {"query": "Inception"}
        assert response.tool_calls_made[0]["result"]["count"] >= 1


def test_fake_client_invalid_json_arguments_handled_gracefully(db_session: Session):
    """Verify with fake OpenAI client that tool call with malformed/invalid JSON arguments does not crash and recovers."""
    session_id = f"llm-bad-json-{uuid.uuid4().hex[:8]}"

    # Return invalid JSON in tool arguments
    turn1_msg = FakeMessage(
        content=None,
        tool_calls=[FakeToolCall("call_bad", "search_movies", '{"query": "Dune", BROKEN_JSON}')],
    )
    turn2_msg = FakeMessage(
        content="I searched our catalog with default parameters and found active movies.",
        tool_calls=[],
    )

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.side_effect = [
        FakeChatCompletionResponse(turn1_msg),
        FakeChatCompletionResponse(turn2_msg),
    ]

    with patch.object(llm_client, "_client", fake_openai), \
         patch.object(llm_client, "is_mock", False):

        response = run_single_agent(
            db=db_session,
            session_id=session_id,
            user_id=2,
            user_message="Find Dune movies",
        )

        assert response.mock is False
        assert len(response.tool_calls_made) == 1
        assert response.tool_calls_made[0]["tool"] == "search_movies"
        # Tool executed with empty or fallback arguments rather than crashing with 500
        assert "catalog" in response.reply.lower() or "movies" in response.reply.lower()


def test_fake_client_iteration_limit_enforced(db_session: Session):
    """Verify with fake OpenAI client that agent loop terminates cleanly at MAX_ITERATIONS when model continually returns tool calls."""
    session_id = f"llm-infinite-{uuid.uuid4().hex[:8]}"

    # Client continually returns tool calls without producing final text
    loop_msg = FakeMessage(
        content=None,
        tool_calls=[FakeToolCall("call_loop", "search_movies", json.dumps({"query": "action"}))],
    )

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.return_value = FakeChatCompletionResponse(loop_msg)

    with patch.object(llm_client, "_client", fake_openai), \
         patch.object(llm_client, "is_mock", False):

        response = run_single_agent(
            db=db_session,
            session_id=session_id,
            user_id=2,
            user_message="Keep searching action movies in a loop",
        )

        assert response.mock is False
        # Loop strictly capped at MAX_ITERATIONS (6)
        assert len(response.tool_calls_made) == MAX_ITERATIONS
        assert "reasoning" in response.reply.lower() or "limit" in response.reply.lower() or "steps" in response.reply.lower()


def test_fake_client_structured_json_retry_mechanism(db_session: Session):
    """Verify with fake OpenAI client that structured output generator retries when model first returns non-JSON text."""
    invalid_json_text = "Here is my movie recommendation: Inception is great!"
    valid_json_text = json.dumps({
        "recommendations": [
            {"movie_id": 1, "title": "Inception", "match_score": 95, "reason": "Mind-bending sci-fi thriller matching deep mood."},
            {"movie_id": 2, "title": "Interstellar", "match_score": 90, "reason": "Emotional cosmic odyssey."},
            {"movie_id": 3, "title": "Dune: Part Two", "match_score": 88, "reason": "Epic visual sci-fi spectacle."},
        ]
    })

    fake_openai = MagicMock()
    fake_openai.chat.completions.create.side_effect = [
        FakeChatCompletionResponse(FakeMessage(content=invalid_json_text)),
        FakeChatCompletionResponse(FakeMessage(content=valid_json_text)),
    ]

    with patch.object(llm_client, "_client", fake_openai), \
         patch.object(llm_client, "is_mock", False):

        rec = recommend_movies(db_session, mood="deep thought and sci-fi wonder")
        assert len(rec.recommendations) == 3
        assert rec.recommendations[0].title == "Inception"
        assert rec.recommendations[1].title == "Interstellar"
        # Two completions requested (initial attempt + 1 retry)
        assert fake_openai.chat.completions.create.call_count == 2
