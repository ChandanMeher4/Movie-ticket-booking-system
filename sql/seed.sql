-- Movie Ticket Booking System - Seed Data
-- 8+ Movies, 3 Theatres, 6 Screens with Seats, 30+ Shows over 7 Days, 3 Users

USE movie_ticket_booking;

-- Users (1 Admin, 2 Customers)
INSERT INTO users (id, name, email, phone, role, created_at) VALUES
(1, 'Admin Cineverse', 'admin@cineverse.com', '+91-9876543210', 'admin', NOW()),
(2, 'Aarav Sharma', 'aarav.sharma@example.com', '+91-9811223344', 'customer', NOW()),
(3, 'Diya Patel', 'diya.patel@example.com', '+91-9822334455', 'customer', NOW())
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- Movies (8 blockbuster titles with rich genres and languages)
INSERT INTO movies (id, title, description, genre, language, duration_min, rating, release_date, poster_url, is_active) VALUES
(1, 'Inception', 'A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea into the mind of a C.E.O.', 'Sci-Fi', 'English', 148, 'UA', '2010-07-16', 'https://images.unsplash.com/photo-1536440136628-849c177e76a1?auto=format&fit=crop&w=600&q=80', TRUE),
(2, 'Interstellar', 'When Earth becomes uninhabitable in the future, a farmer and ex-NASA pilot, Joseph Cooper, is tasked to pilot a spacecraft along with a team of researchers to find a new planet for humans.', 'Sci-Fi', 'English', 169, 'UA', '2014-11-07', 'https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=600&q=80', TRUE),
(3, 'Dune: Part Two', 'Paul Atreides unites with Chani and the Fremen while seeking revenge against the conspirators who destroyed his family.', 'Sci-Fi', 'English', 166, 'UA', '2024-03-01', 'https://images.unsplash.com/photo-1509198397868-475647b2a1e5?auto=format&fit=crop&w=600&q=80', TRUE),
(4, 'The Dark Knight', 'When the menace known as the Joker wreaks havoc and chaos on the people of Gotham, Batman must accept one of the greatest psychological and physical tests of his ability to fight injustice.', 'Action', 'English', 152, 'UA', '2008-07-18', 'https://images.unsplash.com/photo-1509281373149-e957c6296406?auto=format&fit=crop&w=600&q=80', TRUE),
(5, 'Oppenheimer', 'The story of American scientist J. Robert Oppenheimer and his role in the development of the atomic bomb during World War II.', 'Drama', 'English', 180, 'A', '2023-07-21', 'https://images.unsplash.com/photo-1440404653325-ab127d49abc1?auto=format&fit=crop&w=600&q=80', TRUE),
(6, 'Spider-Man: Across the Spider-Verse', 'Miles Morales catapults across the Multiverse, where he encounters a team of Spider-People charged with protecting its very existence.', 'Animation', 'English', 140, 'U', '2023-06-02', 'https://images.unsplash.com/photo-1635805737707-575885ab0820?auto=format&fit=crop&w=600&q=80', TRUE),
(7, 'RRR', 'A fearless warrior on a perilous mission comes face to face with a steely cop serving British forces in pre-independent India.', 'Action', 'Telugu', 187, 'UA', '2022-03-25', 'https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=600&q=80', TRUE),
(8, 'Spirited Away', 'During her family''s move to the suburbs, a sullen 10-year-old girl wanders into a world ruled by gods, witches, and spirits, and where humans are changed into beasts.', 'Animation', 'Japanese', 125, 'U', '2001-07-20', 'https://images.unsplash.com/photo-1578632767115-351597cf2477?auto=format&fit=crop&w=600&q=80', TRUE)
ON DUPLICATE KEY UPDATE title=VALUES(title);

-- Theatres (3 prime cities: Mumbai, Bengaluru, Delhi)
INSERT INTO theatres (id, name, city, address) VALUES
(1, 'PVR ICON Phoenix Palladium', 'Mumbai', '462 Senapati Bapat Marg, Lower Parel, Mumbai, Maharashtra 400013'),
(2, 'INOX Megaplex Nexus Koramangala', 'Bengaluru', 'Hosur Rd, 7th Block, Koramangala, Bengaluru, Karnataka 560095'),
(3, 'Cinepolis DLF Avenue Saket', 'Delhi', 'A4 Press Enclave Marg, Saket District Centre, New Delhi 110017')
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- Screens (2 screens per theatre = 6 screens)
INSERT INTO screens (id, theatre_id, name, total_rows, seats_per_row) VALUES
(1, 1, 'Screen 1 (IMAX Laser)', 4, 10),
(2, 1, 'Screen 2 (Dolby Atmos)', 4, 10),
(3, 2, 'Screen 1 (4DX Experience)', 4, 10),
(4, 2, 'Screen 2 (Insignia Lounge)', 4, 10),
(5, 3, 'Screen 1 (Macro XE)', 4, 10),
(6, 3, 'Screen 2 (Onyx LED)', 4, 10)
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- Generate Seats for all 6 screens
-- Rows A & B: regular (seat 1-10)
-- Row C: premium (seat 1-10)
-- Row D: recliner (seat 1-10)
-- Total 40 seats per screen * 6 = 240 seats
INSERT IGNORE INTO seats (screen_id, row_label, seat_number, seat_type)
SELECT s.id, r.row_label, n.num,
       CASE 
         WHEN r.row_label IN ('A', 'B') THEN 'regular'
         WHEN r.row_label = 'C' THEN 'premium'
         ELSE 'recliner'
       END
FROM screens s
CROSS JOIN (
    SELECT 'A' AS row_label UNION ALL SELECT 'B' UNION ALL SELECT 'C' UNION ALL SELECT 'D'
) r
CROSS JOIN (
    SELECT 1 AS num UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5
    UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9 UNION ALL SELECT 10
) n;

-- Schedule 36 Shows over the next 7 days
-- Across all 6 screens, movies 1-8
INSERT INTO shows (movie_id, screen_id, start_time, end_time, base_price, status) VALUES
-- Day 0 (Today)
(1, 1, DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 14 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 16 HOUR), INTERVAL 30 MINUTE), 320.00, 'scheduled'),
(2, 1, DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 18 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 20 HOUR), INTERVAL 50 MINUTE), 350.00, 'scheduled'),
(3, 2, DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 15 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 17 HOUR), INTERVAL 45 MINUTE), 300.00, 'scheduled'),
(4, 2, DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 19 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 21 HOUR), INTERVAL 35 MINUTE), 280.00, 'scheduled'),
(5, 3, DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 14 HOUR), INTERVAL 30 MINUTE), DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 17 HOUR), INTERVAL 30 MINUTE), 310.00, 'scheduled'),
(6, 4, DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 16 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 18 HOUR), INTERVAL 20 MINUTE), 290.00, 'scheduled'),

-- Day 1 (Tomorrow)
(7, 5, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 1 DAY), INTERVAL 13 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 1 DAY), INTERVAL 16 HOUR), INTERVAL 10 MINUTE), 280.00, 'scheduled'),
(8, 6, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 1 DAY), INTERVAL 14 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 1 DAY), INTERVAL 16 HOUR), INTERVAL 05 MINUTE), 260.00, 'scheduled'),
(1, 1, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 1 DAY), INTERVAL 17 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 1 DAY), INTERVAL 19 HOUR), INTERVAL 30 MINUTE), 320.00, 'scheduled'),
(2, 2, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 1 DAY), INTERVAL 18 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 1 DAY), INTERVAL 20 HOUR), INTERVAL 50 MINUTE), 350.00, 'scheduled'),
(3, 3, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 1 DAY), INTERVAL 19 HOUR), INTERVAL 30 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 1 DAY), INTERVAL 22 HOUR), INTERVAL 15 MINUTE), 310.00, 'scheduled'),

-- Day 2
(4, 4, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 2 DAY), INTERVAL 14 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 2 DAY), INTERVAL 16 HOUR), INTERVAL 35 MINUTE), 290.00, 'scheduled'),
(5, 5, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 2 DAY), INTERVAL 17 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 2 DAY), INTERVAL 20 HOUR), INTERVAL 0 MINUTE), 320.00, 'scheduled'),
(6, 6, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 2 DAY), INTERVAL 18 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 2 DAY), INTERVAL 20 HOUR), INTERVAL 20 MINUTE), 300.00, 'scheduled'),
(7, 1, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 2 DAY), INTERVAL 20 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 2 DAY), INTERVAL 23 HOUR), INTERVAL 10 MINUTE), 320.00, 'scheduled'),

-- Day 3
(8, 2, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 3 DAY), INTERVAL 11 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 3 DAY), INTERVAL 13 HOUR), INTERVAL 05 MINUTE), 250.00, 'scheduled'),
(1, 3, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 3 DAY), INTERVAL 14 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 3 DAY), INTERVAL 16 HOUR), INTERVAL 30 MINUTE), 310.00, 'scheduled'),
(2, 4, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 3 DAY), INTERVAL 17 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 3 DAY), INTERVAL 19 HOUR), INTERVAL 50 MINUTE), 340.00, 'scheduled'),
(3, 5, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 3 DAY), INTERVAL 19 HOUR), INTERVAL 30 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 3 DAY), INTERVAL 22 HOUR), INTERVAL 15 MINUTE), 330.00, 'scheduled'),

-- Day 4
(4, 6, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 4 DAY), INTERVAL 13 HOUR), INTERVAL 30 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 4 DAY), INTERVAL 16 HOUR), INTERVAL 05 MINUTE), 280.00, 'scheduled'),
(5, 1, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 4 DAY), INTERVAL 16 HOUR), INTERVAL 30 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 4 DAY), INTERVAL 19 HOUR), INTERVAL 30 MINUTE), 350.00, 'scheduled'),
(6, 2, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 4 DAY), INTERVAL 19 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 4 DAY), INTERVAL 21 HOUR), INTERVAL 20 MINUTE), 300.00, 'scheduled'),
(7, 3, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 4 DAY), INTERVAL 20 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 4 DAY), INTERVAL 23 HOUR), INTERVAL 10 MINUTE), 310.00, 'scheduled'),

-- Day 5 (Weekend)
(1, 4, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 5 DAY), INTERVAL 11 HOUR), INTERVAL 30 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 5 DAY), INTERVAL 14 HOUR), INTERVAL 0 MINUTE), 360.00, 'scheduled'),
(2, 5, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 5 DAY), INTERVAL 14 HOUR), INTERVAL 45 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 5 DAY), INTERVAL 17 HOUR), INTERVAL 35 MINUTE), 380.00, 'scheduled'),
(3, 6, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 5 DAY), INTERVAL 18 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 5 DAY), INTERVAL 20 HOUR), INTERVAL 45 MINUTE), 350.00, 'scheduled'),
(8, 1, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 5 DAY), INTERVAL 21 HOUR), INTERVAL 15 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 5 DAY), INTERVAL 23 HOUR), INTERVAL 20 MINUTE), 320.00, 'scheduled'),

-- Day 6 (Weekend)
(4, 2, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 6 DAY), INTERVAL 12 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 6 DAY), INTERVAL 14 HOUR), INTERVAL 35 MINUTE), 320.00, 'scheduled'),
(5, 3, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 6 DAY), INTERVAL 15 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 6 DAY), INTERVAL 18 HOUR), INTERVAL 0 MINUTE), 350.00, 'scheduled'),
(6, 4, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 6 DAY), INTERVAL 18 HOUR), INTERVAL 30 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 6 DAY), INTERVAL 20 HOUR), INTERVAL 50 MINUTE), 340.00, 'scheduled'),
(7, 5, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 6 DAY), INTERVAL 21 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 6 DAY), INTERVAL 23 HOUR), INTERVAL 55 MINUTE), 340.00, 'scheduled'),

-- Day 7
(1, 6, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 7 DAY), INTERVAL 13 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 7 DAY), INTERVAL 15 HOUR), INTERVAL 30 MINUTE), 300.00, 'scheduled'),
(2, 1, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 7 DAY), INTERVAL 16 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 7 DAY), INTERVAL 18 HOUR), INTERVAL 50 MINUTE), 330.00, 'scheduled'),
(3, 2, DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 7 DAY), INTERVAL 19 HOUR), INTERVAL 0 MINUTE), DATE_ADD(DATE_ADD(DATE_ADD(CURDATE(), INTERVAL 7 DAY), INTERVAL 21 HOUR), INTERVAL 45 MINUTE), 310.00, 'scheduled');
