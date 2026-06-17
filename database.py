import os
from contextlib import contextmanager

import psycopg2
from psycopg2.pool import SimpleConnectionPool
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

pool = SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    dsn=DATABASE_URL,
)


@contextmanager
def get_db():
    conn = pool.getconn()
    try:
        with conn.cursor() as cursor:
            yield cursor
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        pool.putconn(conn)


def init_db():
    with get_db() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                full_name VARCHAR(150) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'user'
                    CHECK (role IN ('user', 'staff', 'admin')),
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                description TEXT
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_requests (
                id SERIAL PRIMARY KEY,
                requester_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                priority VARCHAR(20) NOT NULL DEFAULT 'medium'
                    CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
                status VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'assigned', 'in_progress', 'resolved', 'closed')),
                assigned_to INTEGER REFERENCES users(id) ON DELETE SET NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                resolved_at TIMESTAMP
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS request_status_history (
                id SERIAL PRIMARY KEY,
                request_id INTEGER NOT NULL REFERENCES service_requests(id) ON DELETE CASCADE,
                status VARCHAR(20) NOT NULL,
                changed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                changed_at TIMESTAMP NOT NULL DEFAULT NOW(),
                note TEXT
            );
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_requests_status ON service_requests(status);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_requests_assigned_to ON service_requests(assigned_to);
        """)

    print("tables created successfully")


if __name__ == "__main__":
    init_db()
