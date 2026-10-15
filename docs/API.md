# API Specification

All error responses strictly follow the standardized envelope:
```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Detailed description of the error",
    "details": null
  }
}
```

## 1. System Endpoints
| Method | Path | Description | Response Code |
|---|---|---|---|
| `GET` | `/health` | System health and database connectivity | `200 OK` |
| `GET` | `/docs` | OpenAPI / Swagger interactive documentation | `200 OK` |

## 2. Movies CRUD
| Method | Path | Query / Body Params | Description |
|---|---|---|---|
| `GET` | `/api/movies` | `genre`, `language`, `city`, `search`, `page`, `page_size`, `sort_by` | List movies with pagination & filters |
| `GET` | `/api/movies/{id}` | - | Get movie details |
| `POST` | `/api/movies` | MovieCreate JSON | Create movie (admin) |
| `PUT` | `/api/movies/{id}` | MovieUpdate JSON | Update movie (admin) |
| `DELETE` | `/api/movies/{id}` | - | Soft-delete / deactivate movie |

## 3. Theatres & Screens
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/theatres` | List theatres with city filter |
| `GET` | `/api/theatres/{id}` | Get theatre and its screens |
| `POST` | `/api/theatres` | Create theatre (admin) |
| `GET` | `/api/screens/{id}` | Get screen info and seat layout |
| `POST` | `/api/screens` | Create screen and generate seat grid |

## 4. Shows & Seats
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/shows` | List shows filtered by `movie_id`, `date`, `city` |
| `GET` | `/api/shows/{id}` | Get show details with pricing |
| `POST` | `/api/shows` | Schedule a show with collision checks |
| `GET` | `/api/shows/{id}/seats` | Real-time seat map: available, held, booked status |

## 5. Bookings & Payments
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/bookings` | Hold seats (max 6, 5-minute TTL) |
| `GET` | `/api/bookings/{id}` | Get booking details |
| `POST` | `/api/payments` | Confirm payment and finalize booking |
| `POST` | `/api/bookings/{id}/cancel` | Cancel booking and calculate refund |
| `GET` | `/api/users/{id}/bookings` | Get user booking history |

## 6. Generative AI (Direct LLM Calls)
| Method | Path | Request Body | Description |
|---|---|---|---|
| `POST` | `/api/ai/genai/movie-summary` | `{"movie_id": 1, "tone": "exciting"}` | Spoiler-free marketing summary |
| `POST` | `/api/ai/genai/recommend` | `{"mood": "space sci-fi thrill"}` | Top 3 recommendations from catalog |
| `POST` | `/api/ai/genai/review-summarize`| `{"reviews": ["..."]}` | Structured pros/cons/sentiment |
| `POST` | `/api/ai/genai/booking-email` | `{"booking_id": 1}` | Customer confirmation email text |

## 7. Single-Agent AI (Tool-Calling ReAct Loop)
| Method | Path | Request Body | Description |
|---|---|---|---|
| `POST` | `/api/ai/agent/chat` | `{"session_id": "...", "user_id": 1, "message": "..."}` | Autonomous assistant with DB tools |

## 8. Multi-Agent AI Orchestration
| Method | Path | Request Body | Description |
|---|---|---|---|
| `POST` | `/api/ai/multi/chat` | `{"session_id": "...", "user_id": 1, "message": "..."}` | Orchestrated specialist execution |
| `GET` | `/api/ai/multi/trace/{session_id}` | - | Step-by-step agent trace log |
