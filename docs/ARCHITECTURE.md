# System Architecture

## Component Overview
```mermaid
graph TD
    Client[Browser / Vanilla JS Frontend] -->|HTTP / JSON| API[FastAPI Application]
    
    subgraph FastAPI Application
        Routers[Routers: Movies, Theatres, Shows, Bookings, AI]
        Errors[Errors & Standard Exception Handlers]
        Auth[Demo User Context Header]
    end
    
    subgraph Business Services
        BookingService[Booking Service: Seat Hold, Release, Confirm]
        PricingEngine[Pricing Engine: Tiers, Surcharges, Fees]
        Seeder[Seed Service]
    end

    subgraph AI Layer
        LLMClient[LLM Client: OpenAI API / Deterministic Mock]
        Guardrails[Guardrails & Security Filters]
        GenAIFeatures[GenAI Features: Summary, Recommender, Reviews]
        SingleAgent[Single Agent ReAct Loop: Tools + DB Engine]
        MultiAgent[Multi-Agent Orchestrator: Discovery, Booking, Payment, Support, Critic]
    end

    subgraph Database Layer
        MySQL[(MySQL 8 Database / PyMySQL)]
        SQLiteTest[(SQLite In-Memory / pytest)]
    end

    API --> Business Services
    API --> AI Layer
    Business Services --> MySQL
    Business Services --> SQLiteTest
    AI Layer --> Business Services
    AI Layer --> LLMClient
```

## Entity Relationship (ER) Diagram
```mermaid
erDiagram
    users ||--o{ bookings : places
    theatres ||--|{ screens : contains
    screens ||--|{ seats : has
    movies ||--o{ shows : scheduled_as
    screens ||--o{ shows : hosts
    shows ||--o{ bookings : booked_in
    bookings ||--|{ booking_seats : reserves
    seats ||--o{ booking_seats : allocated_as
    bookings ||--o{ payments : paid_by

    users {
        int id PK
        varchar name
        varchar email UK
        varchar phone
        enum role "customer,admin"
        datetime created_at
    }

    movies {
        int id PK
        varchar title
        text description
        varchar genre
        varchar language
        int duration_min
        enum rating "U,UA,A"
        date release_date
        varchar poster_url
        boolean is_active
    }

    theatres {
        int id PK
        varchar name
        varchar city
        text address
    }

    screens {
        int id PK
        int theatre_id FK
        varchar name
        int total_rows
        int seats_per_row
    }

    seats {
        int id PK
        int screen_id FK
        varchar row_label
        int seat_number
        enum seat_type "regular,premium,recliner"
    }

    shows {
        int id PK
        int movie_id FK
        int screen_id FK
        datetime start_time
        datetime end_time
        decimal base_price
        enum status "scheduled,cancelled,completed"
    }

    bookings {
        int id PK
        int user_id FK
        int show_id FK
        enum status "pending,confirmed,cancelled"
        decimal total_amount
        datetime created_at
        datetime expires_at
    }

    booking_seats {
        int id PK
        int booking_id FK
        int show_id FK
        int seat_id FK
        decimal price
    }

    payments {
        int id PK
        int booking_id FK
        decimal amount
        enum method "card,upi,wallet"
        enum status "success,failed,refunded"
        varchar txn_ref
        datetime created_at
    }

    ai_logs {
        int id PK
        varchar session_id
        varchar agent_name
        text input
        text output
        json tool_calls
        int latency_ms
        datetime created_at
    }
```

## Booking Lifecycle & State Transitions
```mermaid
stateDiagram-v2
    [*] --> Available: Seat created on screen
    Available --> Held: User requests hold (status='pending', TTL 5 min)
    Held --> Available: Hold expired (cleanup query sets status='cancelled')
    Held --> Available: User cancels hold
    Held --> Confirmed: Payment successful (status='confirmed')
    Confirmed --> Cancelled: User cancels booking (> 2 hrs before showtime)
    Cancelled --> [*]: Refund processed (100% if >24h, 50% if 2-24h)
    Confirmed --> [*]: Show completed
```

## AI Orchestration Flow
```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Router as /api/ai/multi/chat
    participant Orchestrator as OrchestratorAgent
    participant Specialists as Specialist Agents (Discovery, Booking, Support, Payment)
    participant Critic as CriticAgent (Verifier)
    participant Tools as DB / Service Tools
    participant LLM as LLM / Mock Engine

    User->>Router: User Message + Session ID
    Router->>Orchestrator: Forward with current State
    Orchestrator->>LLM: Intent classification & agent dispatch
    Orchestrator->>Specialists: Invoke specialist agent
    Specialists->>Critic: Propose action / plan
    Critic->>Critic: Verify constraints (seats valid, price matches, user confirmed)
    alt Action Approved
        Critic-->>Specialists: Approved
        Specialists->>Tools: Execute service tools
        Tools-->>Specialists: Tool result
        Specialists-->>Orchestrator: Formatted response
    else Action Rejected
        Critic-->>Specialists: Reject with reason
        Specialists-->>Orchestrator: Ask clarification / report error
    end
    Orchestrator-->>Router: Final reply + Agent Trace
    Router-->>User: JSON Response
```
