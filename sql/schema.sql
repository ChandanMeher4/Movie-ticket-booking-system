-- Movie Ticket Booking System - MySQL 8 DDL Schema
-- Character Set: utf8mb4, Engine: InnoDB

CREATE DATABASE IF NOT EXISTS movie_ticket_booking
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE movie_ticket_booking;

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(191) NOT NULL UNIQUE,
    phone VARCHAR(20) NOT NULL,
    role ENUM('customer', 'admin') NOT NULL DEFAULT 'customer',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_users_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Movies Table
CREATE TABLE IF NOT EXISTS movies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    genre VARCHAR(60) NOT NULL,
    language VARCHAR(60) NOT NULL,
    duration_min INT NOT NULL,
    rating ENUM('U', 'UA', 'A') NOT NULL DEFAULT 'UA',
    release_date DATE NOT NULL,
    poster_url VARCHAR(500) NOT NULL DEFAULT '',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    INDEX idx_movies_genre (genre),
    INDEX idx_movies_language (language),
    INDEX idx_movies_title (title),
    INDEX idx_movies_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Theatres Table
CREATE TABLE IF NOT EXISTS theatres (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    city VARCHAR(80) NOT NULL,
    address TEXT NOT NULL,
    INDEX idx_theatres_city (city)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Screens Table
CREATE TABLE IF NOT EXISTS screens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    theatre_id INT NOT NULL,
    name VARCHAR(80) NOT NULL,
    total_rows INT NOT NULL DEFAULT 8,
    seats_per_row INT NOT NULL DEFAULT 10,
    CONSTRAINT fk_screens_theatre
        FOREIGN KEY (theatre_id) REFERENCES theatres(id)
        ON DELETE CASCADE,
    INDEX idx_screens_theatre (theatre_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Seats Table
CREATE TABLE IF NOT EXISTS seats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    screen_id INT NOT NULL,
    row_label VARCHAR(5) NOT NULL,
    seat_number INT NOT NULL,
    seat_type ENUM('regular', 'premium', 'recliner') NOT NULL DEFAULT 'regular',
    CONSTRAINT uq_screen_seat UNIQUE (screen_id, row_label, seat_number),
    CONSTRAINT fk_seats_screen
        FOREIGN KEY (screen_id) REFERENCES screens(id)
        ON DELETE CASCADE,
    INDEX idx_seats_screen (screen_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. Shows Table
CREATE TABLE IF NOT EXISTS shows (
    id INT AUTO_INCREMENT PRIMARY KEY,
    movie_id INT NOT NULL,
    screen_id INT NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    base_price DECIMAL(10, 2) NOT NULL,
    status ENUM('scheduled', 'cancelled', 'completed') NOT NULL DEFAULT 'scheduled',
    CONSTRAINT fk_shows_movie
        FOREIGN KEY (movie_id) REFERENCES movies(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_shows_screen
        FOREIGN KEY (screen_id) REFERENCES screens(id)
        ON DELETE CASCADE,
    INDEX idx_shows_movie (movie_id),
    INDEX idx_shows_screen_time (screen_id, start_time),
    INDEX idx_shows_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Bookings Table
CREATE TABLE IF NOT EXISTS bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    show_id INT NOT NULL,
    status ENUM('pending', 'confirmed', 'cancelled') NOT NULL DEFAULT 'pending',
    total_amount DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    CONSTRAINT fk_bookings_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_bookings_show
        FOREIGN KEY (show_id) REFERENCES shows(id)
        ON DELETE CASCADE,
    INDEX idx_bookings_user (user_id),
    INDEX idx_bookings_show (show_id),
    INDEX idx_bookings_status_expires (status, expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. Booking Seats Table (Double-Booking Barrier via UNIQUE(show_id, seat_id))
CREATE TABLE IF NOT EXISTS booking_seats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL,
    show_id INT NOT NULL,
    seat_id INT NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    CONSTRAINT uq_show_seat UNIQUE (show_id, seat_id),
    CONSTRAINT fk_bs_booking
        FOREIGN KEY (booking_id) REFERENCES bookings(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_bs_show
        FOREIGN KEY (show_id) REFERENCES shows(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_bs_seat
        FOREIGN KEY (seat_id) REFERENCES seats(id)
        ON DELETE CASCADE,
    INDEX idx_bs_booking (booking_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 9. Payments Table
CREATE TABLE IF NOT EXISTS payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    method ENUM('card', 'upi', 'wallet') NOT NULL,
    status ENUM('success', 'failed', 'refunded') NOT NULL,
    txn_ref VARCHAR(100) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_payments_booking
        FOREIGN KEY (booking_id) REFERENCES bookings(id)
        ON DELETE CASCADE,
    INDEX idx_payments_booking (booking_id),
    INDEX idx_payments_txn (txn_ref)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 10. AI Logs Table
CREATE TABLE IF NOT EXISTS ai_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    agent_name VARCHAR(60) NOT NULL,
    input TEXT NOT NULL,
    output TEXT NOT NULL,
    tool_calls JSON NULL,
    latency_ms INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ai_logs_session (session_id),
    INDEX idx_ai_logs_agent (agent_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
