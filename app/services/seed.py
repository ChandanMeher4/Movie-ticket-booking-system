"""Idempotent database seeding service.

Can be run programmatically or via CLI:
python -m app.services.seed
"""

from datetime import datetime, timedelta
from decimal import Decimal
import logging
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import Base, engine, SessionLocal
from app.models import (
    Movie,
    MovieRating,
    Screen,
    Seat,
    SeatType,
    Show,
    ShowStatus,
    Theatre,
    User,
    UserRole,
)

logger = logging.getLogger("seed")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def seed_database(db: Session, target_engine=None) -> None:
    """Populate database with initial seed data idempotently."""
    logger.info("Initializing database tables...")
    active_engine = target_engine or db.get_bind() or engine
    Base.metadata.create_all(bind=active_engine)

    # 1. Users
    existing_users = {u.email: u for u in db.scalars(select(User)).all()}
    initial_users = [
        User(
            name="Admin Cineverse",
            email="admin@cineverse.com",
            phone="+91-9876543210",
            role=UserRole.ADMIN,
        ),
        User(
            name="Aarav Sharma",
            email="aarav.sharma@example.com",
            phone="+91-9811223344",
            role=UserRole.CUSTOMER,
        ),
        User(
            name="Diya Patel",
            email="diya.patel@example.com",
            phone="+91-9822334455",
            role=UserRole.CUSTOMER,
        ),
    ]
    for u in initial_users:
        if u.email not in existing_users:
            db.add(u)
            logger.info("Created user: %s (%s)", u.name, u.email)
    db.commit()

    # 2. Movies
    existing_movies = {m.title: m for m in db.scalars(select(Movie)).all()}
    initial_movies = [
        Movie(
            title="Inception",
            description="A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea into the mind of a C.E.O.",
            genre="Sci-Fi",
            language="English",
            duration_min=148,
            rating=MovieRating.UA,
            release_date=datetime(2010, 7, 16),
            poster_url="https://images.unsplash.com/photo-1536440136628-849c177e76a1?auto=format&fit=crop&w=600&q=80",
            is_active=True,
        ),
        Movie(
            title="Interstellar",
            description="When Earth becomes uninhabitable in the future, a farmer and ex-NASA pilot, Joseph Cooper, is tasked to pilot a spacecraft along with a team of researchers to find a new planet for humans.",
            genre="Sci-Fi",
            language="English",
            duration_min=169,
            rating=MovieRating.UA,
            release_date=datetime(2014, 11, 7),
            poster_url="https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=600&q=80",
            is_active=True,
        ),
        Movie(
            title="Dune: Part Two",
            description="Paul Atreides unites with Chani and the Fremen while seeking revenge against the conspirators who destroyed his family.",
            genre="Sci-Fi",
            language="English",
            duration_min=166,
            rating=MovieRating.UA,
            release_date=datetime(2024, 3, 1),
            poster_url="https://images.unsplash.com/photo-1509198397868-475647b2a1e5?auto=format&fit=crop&w=600&q=80",
            is_active=True,
        ),
        Movie(
            title="The Dark Knight",
            description="When the menace known as the Joker wreaks havoc and chaos on the people of Gotham, Batman must accept one of the greatest psychological and physical tests of his ability to fight injustice.",
            genre="Action",
            language="English",
            duration_min=152,
            rating=MovieRating.UA,
            release_date=datetime(2008, 7, 18),
            poster_url="https://images.unsplash.com/photo-1509281373149-e957c6296406?auto=format&fit=crop&w=600&q=80",
            is_active=True,
        ),
        Movie(
            title="Oppenheimer",
            description="The story of American scientist J. Robert Oppenheimer and his role in the development of the atomic bomb during World War II.",
            genre="Drama",
            language="English",
            duration_min=180,
            rating=MovieRating.A,
            release_date=datetime(2023, 7, 21),
            poster_url="https://images.unsplash.com/photo-1440404653325-ab127d49abc1?auto=format&fit=crop&w=600&q=80",
            is_active=True,
        ),
        Movie(
            title="Spider-Man: Across the Spider-Verse",
            description="Miles Morales catapults across the Multiverse, where he encounters a team of Spider-People charged with protecting its very existence.",
            genre="Animation",
            language="English",
            duration_min=140,
            rating=MovieRating.U,
            release_date=datetime(2023, 6, 2),
            poster_url="https://images.unsplash.com/photo-1635805737707-575885ab0820?auto=format&fit=crop&w=600&q=80",
            is_active=True,
        ),
        Movie(
            title="RRR",
            description="A fearless warrior on a perilous mission comes face to face with a steely cop serving British forces in pre-independent India.",
            genre="Action",
            language="Telugu",
            duration_min=187,
            rating=MovieRating.UA,
            release_date=datetime(2022, 3, 25),
            poster_url="https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=600&q=80",
            is_active=True,
        ),
        Movie(
            title="Spirited Away",
            description="During her family's move to the suburbs, a sullen 10-year-old girl wanders into a world ruled by gods, witches, and spirits, and where humans are changed into beasts.",
            genre="Animation",
            language="Japanese",
            duration_min=125,
            rating=MovieRating.U,
            release_date=datetime(2001, 7, 20),
            poster_url="https://images.unsplash.com/photo-1578632767115-351597cf2477?auto=format&fit=crop&w=600&q=80",
            is_active=True,
        ),
    ]
    for m in initial_movies:
        if m.title not in existing_movies:
            db.add(m)
            logger.info("Created movie: %s", m.title)
    db.commit()

    # 3. Theatres
    existing_theatres = {t.name: t for t in db.scalars(select(Theatre)).all()}
    initial_theatres = [
        Theatre(
            name="PVR ICON Phoenix Palladium",
            city="Mumbai",
            address="462 Senapati Bapat Marg, Lower Parel, Mumbai, Maharashtra 400013",
        ),
        Theatre(
            name="INOX Megaplex Nexus Koramangala",
            city="Bengaluru",
            address="Hosur Rd, 7th Block, Koramangala, Bengaluru, Karnataka 560095",
        ),
        Theatre(
            name="Cinepolis DLF Avenue Saket",
            city="Delhi",
            address="A4 Press Enclave Marg, Saket District Centre, New Delhi 110017",
        ),
    ]
    for t in initial_theatres:
        if t.name not in existing_theatres:
            db.add(t)
            logger.info("Created theatre: %s (%s)", t.name, t.city)
    db.commit()

    all_theatres = db.scalars(select(Theatre).order_by(Theatre.id)).all()

    # 4. Screens
    for theatre in all_theatres:
        screens_for_theatre = db.scalars(
            select(Screen).where(Screen.theatre_id == theatre.id)
        ).all()
        if not screens_for_theatre:
            s1 = Screen(theatre_id=theatre.id, name="Screen 1 (Laser)", total_rows=4, seats_per_row=10)
            s2 = Screen(theatre_id=theatre.id, name="Screen 2 (Atmos)", total_rows=4, seats_per_row=10)
            db.add_all([s1, s2])
            logger.info("Created 2 screens for %s", theatre.name)
    db.commit()

    # 5. Seats for each screen
    all_screens = db.scalars(select(Screen).order_by(Screen.id)).all()
    for screen in all_screens:
        seat_count = db.scalar(
            select(Seat.id).where(Seat.screen_id == screen.id).limit(1)
        )
        if not seat_count:
            seats_to_add = []
            # Rows A, B: regular; Row C: premium; Row D: recliner
            rows = [("A", SeatType.REGULAR), ("B", SeatType.REGULAR), ("C", SeatType.PREMIUM), ("D", SeatType.RECLINER)]
            for row_label, seat_type in rows:
                for seat_num in range(1, 11):
                    seats_to_add.append(
                        Seat(
                            screen_id=screen.id,
                            row_label=row_label,
                            seat_number=seat_num,
                            seat_type=seat_type,
                        )
                    )
            db.add_all(seats_to_add)
            logger.info("Generated 40 seats for Screen %d (%s)", screen.id, screen.name)
    db.commit()

    # 6. Shows (Schedule 30+ shows over the next 7 days)
    existing_shows = db.scalars(select(Show).order_by(Show.id)).all()
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)

    # Check if shows are missing or if all shows have expired into the past
    max_start_time = max((s.start_time for s in existing_shows), default=None)
    needs_refresh = (
        not existing_shows
        or (max_start_time and max_start_time < now + timedelta(days=2))
    )

    if not existing_shows:
        movies = db.scalars(select(Movie).order_by(Movie.id)).all()
        screens = db.scalars(select(Screen).order_by(Screen.id)).all()
        shows_to_create = []

        # Generate 35 shows across days 1 to 7 (next 7 days)
        for day in range(1, 8):
            target_date = now + timedelta(days=day)
            # Create 5 shows each day
            time_slots = [
                (11, 0, Decimal("260.00")),
                (14, 0, Decimal("300.00")),
                (17, 0, Decimal("320.00")),
                (19, 30, Decimal("350.00")),
                (22, 15, Decimal("280.00")),
            ]
            for slot_idx, (hour, minute, price) in enumerate(time_slots):
                movie = movies[(day + slot_idx) % len(movies)]
                screen = screens[(slot_idx * 2 + day) % len(screens)]
                start = target_date.replace(hour=hour, minute=minute)
                end = start + timedelta(minutes=movie.duration_min + 20)  # include interval/turnaround
                shows_to_create.append(
                    Show(
                        movie_id=movie.id,
                        screen_id=screen.id,
                        start_time=start,
                        end_time=end,
                        base_price=price,
                        status=ShowStatus.SCHEDULED,
                    )
                )

        db.add_all(shows_to_create)
        db.commit()
        logger.info("Successfully scheduled %d shows across 7 days.", len(shows_to_create))
    elif needs_refresh:
        # Re-anchor existing shows forward to the upcoming 7 days starting tomorrow
        logger.info("Existing shows have expired. Re-anchoring %d shows to the upcoming 7 days.", len(existing_shows))
        shows_per_day = 5
        for idx, show in enumerate(existing_shows):
            day_offset = (idx // shows_per_day) + 1
            slot_idx = idx % shows_per_day
            time_slots = [(11, 0), (14, 0), (17, 0), (19, 30), (22, 15)]
            hour, minute = time_slots[slot_idx]
            target_date = now + timedelta(days=day_offset)
            duration = show.movie.duration_min if show.movie else 120
            new_start = target_date.replace(hour=hour, minute=minute)
            show.start_time = new_start
            show.end_time = new_start + timedelta(minutes=duration + 20)
            show.status = ShowStatus.SCHEDULED
        db.commit()
        logger.info("Successfully re-anchored %d shows to future dates.", len(existing_shows))
    else:
        logger.info("Shows already present and active in database.")

    logger.info("Database seeding completed successfully.")


if __name__ == "__main__":
    session = SessionLocal()
    try:
        seed_database(session)
    finally:
        session.close()
