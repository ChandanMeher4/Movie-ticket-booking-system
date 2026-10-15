"""OpenAI-compatible LLM client with deterministic offline mock fallback.

When LLM_API_KEY is missing or invalid, transparently provides rule-based completions
with {"mock": true} reported in all responses.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from openai import OpenAI
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger("llm_client")


class LLMToolCall(BaseModel):
    id: str
    name: str
    arguments: Dict[str, Any]


class LLMResponse(BaseModel):
    content: Optional[str] = None
    tool_calls: Optional[List[LLMToolCall]] = None
    mock: bool = False


class LLMClient:
    """Wrapper around OpenAI SDK with deterministic rule-based fallback."""

    def __init__(self) -> None:
        self.is_mock = settings.is_mock_llm
        self._client: Optional[OpenAI] = None

        if not self.is_mock:
            try:
                self._client = OpenAI(
                    api_key=settings.llm_api_key,
                    base_url=settings.llm_base_url,
                )
                logger.info("Initialized live OpenAI client for model: %s", settings.llm_model)
            except Exception as e:
                logger.warning("Failed to initialize OpenAI client (%s). Operating in mock mode.", e)
                self.is_mock = True
        else:
            logger.info("Operating in deterministic mock mode (no LLM API key configured).")

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        response_format: Optional[Dict[str, str]] = None,
    ) -> LLMResponse:
        """Execute chat completion either via OpenAI API or deterministic mock fallback."""
        if not self.is_mock and self._client:
            try:
                kwargs: Dict[str, Any] = {
                    "model": settings.llm_model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"
                if response_format:
                    kwargs["response_format"] = response_format

                response = self._client.chat.completions.create(**kwargs)
                choice = response.choices[0]
                message = choice.message

                parsed_tool_calls = None
                if message.tool_calls:
                    parsed_tool_calls = []
                    for tc in message.tool_calls:
                        try:
                            raw_args = tc.function.arguments or "{}"
                            parsed_args = json.loads(raw_args)
                        except Exception:
                            parsed_args = {}
                        parsed_tool_calls.append(
                            LLMToolCall(
                                id=tc.id,
                                name=tc.function.name,
                                arguments=parsed_args,
                            )
                        )

                return LLMResponse(
                    content=message.content,
                    tool_calls=parsed_tool_calls,
                    mock=False,
                )
            except Exception as exc:
                logger.warning("Live LLM request failed (%s). Falling back to mock engine.", exc)

        return self._mock_completion(messages, tools)

    def _mock_completion(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Deterministic, keyword-based mock generator for cinema use cases."""
        combined_text = " ".join([m.get("content", "") for m in messages]).lower()
        system_text = next((m.get("content", "") for m in messages if m.get("role") == "system"), "").lower()
        user_text = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "").lower()

        # 1. Tool-Calling Agent Simulation (takes precedence when tools are supplied)
        if tools:
            tool_call = self._mock_tool_calling(user_text, tools)
            if tool_call:
                return LLMResponse(content=None, tool_calls=[tool_call], mock=True)

        # 2. Movie Summary / Blurb
        if "marketing blurb" in system_text or "cinema copywriter" in system_text:
            return self._mock_movie_summary(combined_text)

        # 3. Movie Recommendations (Structured JSON)
        if "recommend exactly 3 movies" in system_text or "cinephile concierge" in system_text:
            return self._mock_recommendations(user_text)

        # 4. Review Sentiment & Pros/Cons (Structured JSON)
        if "audience sentiment analyst" in system_text or "film critic" in system_text:
            return self._mock_review_summary(user_text)

        # 5. Booking Confirmation Email
        if "booking confirmation email" in system_text or "customer communications system" in system_text:
            return self._mock_booking_email(combined_text)

        # Default conversational reply
        reply = (
            "Welcome to Cineverse! I can help you discover active movies, check showtimes, "
            "select seats, hold tickets, and manage your bookings. How may I assist your movie plans today?"
        )
        return LLMResponse(content=reply, tool_calls=None, mock=True)

    def _mock_movie_summary(self, text: str) -> LLMResponse:
        """Generate deterministic marketing blurb tailored to tone."""
        tone = "engaging"
        for t in ["exciting", "poetic", "family-friendly", "dramatic", "humorous", "dark"]:
            if t in text:
                tone = t
                break

        if tone == "exciting":
            blurb = (
                "Prepare for an adrenaline-fueled cinematic spectacle that pushes the boundaries of imagination! "
                "Featuring pulse-pounding set-pieces, an extraordinary ensemble cast, and non-stop momentum, "
                "this blockbuster demands to be experienced on the biggest screen possible. Book your tickets now!"
            )
        elif tone == "poetic":
            blurb = (
                "A mesmerizing meditation on memory, longing, and the fragile geometry of human connection. "
                "Through haunting visual landscapes and an evocative orchestral tapestry, the film invites viewers "
                "into a deeply transcendent journey of wonder and quiet revelation."
            )
        elif tone == "family-friendly":
            blurb = (
                "A delightful and heartwarming cinematic celebration bursting with vibrant colors, infectious humor, "
                "and timeless life lessons! Perfect for moviegoers of all generations, this captivating adventure "
                "will have the whole auditorium smiling from opening title to closing credits."
            )
        else:
            blurb = (
                "A gripping cinematic masterpiece that weaves intense character conflict with awe-inspiring visuals. "
                "Every sequence pulls the audience deeper into an unforgettable narrative world built with exquisite craft. "
                "An essential theatrical experience of the season."
            )

        return LLMResponse(content=blurb, mock=True)

    def _mock_recommendations(self, text: str) -> LLMResponse:
        """Return 3 ranked movie recommendations matching mood keywords."""
        if any(w in text for w in ["action", "thrill", "fight", "batman", "dark", "crime"]):
            recs = [
                {"movie_id": 4, "title": "The Dark Knight", "match_score": 96, "reason": "Legendary psychological action thriller with unmatched stakes and iconic performances."},
                {"movie_id": 7, "title": "RRR", "match_score": 91, "reason": "Electrifying high-octane action epic packed with revolutionary fervor and grand scale."},
                {"movie_id": 1, "title": "Inception", "match_score": 88, "reason": "Mind-bending heist thriller blending intense action with layered dream architecture."}
            ]
        elif any(w in text for w in ["space", "sci-fi", "science", "future", "dune", "cosmic"]):
            recs = [
                {"movie_id": 2, "title": "Interstellar", "match_score": 98, "reason": "Breathtaking emotional journey across the cosmos driven by stellar science and score."},
                {"movie_id": 3, "title": "Dune: Part Two", "match_score": 94, "reason": "Epic sci-fi warfare and desert destiny brought to life with monumental sound design."},
                {"movie_id": 1, "title": "Inception", "match_score": 89, "reason": "Cerebral sci-fi masterwork exploring the uncharted architecture of the subconscious."}
            ]
        elif any(w in text for w in ["family", "animation", "anime", "kids", "fun", "spirit"]):
            recs = [
                {"movie_id": 6, "title": "Spider-Man: Across the Spider-Verse", "match_score": 97, "reason": "Visually groundbreaking multiverse adventure celebrating creativity and courage."},
                {"movie_id": 8, "title": "Spirited Away", "match_score": 93, "reason": "Timeless Ghibli wonder exploring enchanting spirit worlds and resilience."},
                {"movie_id": 1, "title": "Inception", "match_score": 80, "reason": "Entertaining, visually splendid puzzle for mature family movie nights."}
            ]
        else:
            # Default diverse trio
            recs = [
                {"movie_id": 1, "title": "Inception", "match_score": 92, "reason": "Captivating concept that keeps audiences on the edge of their seats throughout."},
                {"movie_id": 5, "title": "Oppenheimer", "match_score": 90, "reason": "Monumental historical drama exploring intense moral conflicts and world history."},
                {"movie_id": 6, "title": "Spider-Man: Across the Spider-Verse", "match_score": 87, "reason": "Bursting with creative visual flair and relatable characters."}
            ]

        data = {"recommendations": recs}
        return LLMResponse(content=json.dumps(data), mock=True)

    def _mock_review_summary(self, text: str) -> LLMResponse:
        """Analyze positive and negative keywords in reviews."""
        positive_words = ["great", "masterpiece", "loved", "superb", "brilliant", "amazing", "best", "stunning"]
        negative_words = ["slow", "boring", "disappointing", "long", "loud", "flat", "poor", "confusing"]

        pos_count = sum(text.count(w) for w in positive_words)
        neg_count = sum(text.count(w) for w in negative_words)

        if pos_count > neg_count * 1.5:
            sentiment = "positive"
            summary = "Audience reception is overwhelmingly enthusiastic, highlighting magnificent performances and spectacle."
            pros = ["Stunning visual effects and immersive direction", "Compelling performances that anchor the emotional stakes"]
            cons = ["Longer runtime requiring viewer patience", "Occasional pacing dips in the middle act"]
        elif neg_count > pos_count:
            sentiment = "negative"
            summary = "Audiences expressed frustration with the pacing and narrative coherence despite notable visual ambition."
            pros = ["Strong technical sound design", "Select visually memorable action set-pieces"]
            cons = ["Overextended narrative that feels sluggish", "Underdeveloped supporting character arcs"]
        else:
            sentiment = "mixed"
            summary = "Viewers are divided, with praise for visual ambition counterbalanced by critiques of runtime and pacing."
            pros = ["Ambitious concept and high production values", "Memorable musical score and cinematography"]
            cons = ["Runtime feels somewhat bloated", "Complex plot threads that leave some questions unresolved"]

        data = {
            "sentiment": sentiment,
            "summary": summary,
            "pros": pros,
            "cons": cons,
        }
        return LLMResponse(content=json.dumps(data), mock=True)

    def _mock_booking_email(self, text: str) -> LLMResponse:
        """Format confirmation email."""
        email_text = (
            "Subject: Booking Confirmed: Your Tickets at Cineverse!\n\n"
            "Dear Customer,\n\n"
            "Your movie ticket booking is confirmed! Here are your screening details:\n\n"
            "  * Movie: Cineverse Screening\n"
            "  * Status: Confirmed & Paid\n"
            "  * Arrival: Please arrive at the theatre at least 15 minutes before showtime.\n"
            "  * Admission: Present this confirmation or QR code on your mobile device at the entrance.\n\n"
            "Thank you for choosing Cineverse. Sit back, relax, and enjoy the show!\n\n"
            "Warm regards,\n"
            "The Cineverse Guest Experience Team"
        )
        return LLMResponse(content=email_text, mock=True)

    def _mock_tool_calling(self, text: str, tools: List[Dict[str, Any]]) -> Optional[LLMToolCall]:
        """Heuristic rule-based tool dispatcher for single and multi agent mock mode."""
        available_names = [t["function"]["name"] if "function" in t else t.get("name") for t in tools]

        # 1. Confirm booking (highest priority action)
        if "confirm_booking" in available_names and any(w in text for w in ["confirm", "proceed with payment", "pay"]):
            return LLMToolCall(id="mock-tc-confirm", name="confirm_booking", arguments={"booking_id": 1, "payment_method": "card"})

        # 2. Cancel booking
        if "cancel_booking" in available_names and any(w in text for w in ["cancel", "refund"]):
            return LLMToolCall(id="mock-tc-cancel", name="cancel_booking", arguments={"booking_id": 1})

        # 3. Hold seats (explicit reserve/hold)
        if "hold_seats" in available_names and any(w in text for w in ["hold", "reserve", "book"]):
            return LLMToolCall(id="mock-tc-hold", name="hold_seats", arguments={"user_id": 2, "show_id": 10, "seat_ids": [1, 2]})

        # 4. Calculate price
        if "calculate_price" in available_names and any(w in text for w in ["price", "cost", "how much", "total"]):
            return LLMToolCall(id="mock-tc-price", name="calculate_price", arguments={"show_id": 10, "seat_ids": [1, 2]})

        # 5. User bookings
        if "get_my_bookings" in available_names and any(w in text for w in ["my bookings", "my tickets", "history"]):
            return LLMToolCall(id="mock-tc-mybookings", name="get_my_bookings", arguments={"user_id": 2})

        # 6. Available seats
        if "get_available_seats" in available_names and any(w in text for w in ["seats", "seat", "available", "row"]):
            return LLMToolCall(id="mock-tc-seats", name="get_available_seats", arguments={"show_id": 10, "count": 2})

        # 7. Showtimes
        if "get_showtimes" in available_names and any(w in text for w in ["showtime", "shows", "when", "schedule", "tomorrow", "today"]):
            movie_id = 1
            if "interstellar" in text:
                movie_id = 2
            elif "dune" in text:
                movie_id = 3
            elif "dark knight" in text:
                movie_id = 4
            return LLMToolCall(id="mock-tc-shows", name="get_showtimes", arguments={"movie_id": movie_id})

        # 8. Search movies
        if "search_movies" in available_names and any(w in text for w in ["search", "movies", "genre", "action", "sci-fi", "show me"]):
            genre = None
            if "sci-fi" in text:
                genre = "Sci-Fi"
            elif "action" in text:
                genre = "Action"
            elif "animation" in text:
                genre = "Animation"
            return LLMToolCall(id="mock-tc-search", name="search_movies", arguments={"query": "", "genre": genre})

        return None


llm_client = LLMClient()
