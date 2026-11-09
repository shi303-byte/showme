import os
import sqlite3
import hashlib
import secrets
from datetime import datetime

DB_FILE = os.getenv("DATABASE_PATH", "showme.db")
OWNER_USER = os.getenv("OWNER_USERNAME", "owner")
OWNER_PASS = os.getenv("OWNER_PASSWORD", "admin123")
OWNER_EMAIL = os.getenv("OWNER_EMAIL", "owner@showme.local")

def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def hash_pw(pw: str, salt: str = None) -> tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((pw + salt).encode("utf-8")).hexdigest()
    return hashed, salt

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        is_owner INTEGER DEFAULT 0,
        is_verified INTEGER DEFAULT 0,
        badge_title TEXT DEFAULT 'Member',
        created_at TEXT NOT NULL
    );
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS profiles (
        user_id INTEGER PRIMARY KEY,
        display_name TEXT,
        bio TEXT,
        avatar_url TEXT,
        banner_url TEXT,
        background_url TEXT,
        bg_effect TEXT DEFAULT 'particles',
        theme TEXT DEFAULT 'midnight',
        font_family TEXT DEFAULT 'JetBrains Mono',
        accent_color TEXT DEFAULT '#8b5cf6',
        text_color TEXT DEFAULT '#f8fafc',
        card_opacity REAL DEFAULT 0.85,
        card_blur INTEGER DEFAULT 12,
        card_border_radius INTEGER DEFAULT 16,
        audio_url TEXT,
        audio_title TEXT,
        audio_artist TEXT,
        audio_autoplay INTEGER DEFAULT 0,
        audio_loop INTEGER DEFAULT 1,
        layout_style TEXT DEFAULT 'glass_card',
        custom_css TEXT,
        views INTEGER DEFAULT 0,
        socials_json TEXT DEFAULT '{}',
        badges_json TEXT DEFAULT '[]',
        custom_links_json TEXT DEFAULT '[]',
        FOREIGN KEY (user_id) REFERENCES users (id)
    );
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS invites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        discord_code TEXT NOT NULL,
        destination_url TEXT NOT NULL,
        custom_title TEXT,
        custom_desc TEXT,
        accent_color TEXT DEFAULT '#5865F2',
        clicks INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        expires_at TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS invite_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invite_id INTEGER NOT NULL,
        ip_hash TEXT,
        user_agent TEXT,
        referrer TEXT,
        visited_at TEXT NOT NULL,
        FOREIGN KEY (invite_id) REFERENCES invites (id)
    );
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS profile_views (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        ip_hash TEXT,
        user_agent TEXT,
        viewed_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );
    """)
    conn.commit()

    c.execute("SELECT id FROM users WHERE is_owner = 1")
    if not c.fetchone():
        hashed, salt = hash_pw(OWNER_PASS)
        c.execute("""
            INSERT INTO users (username, email, password_hash, salt, is_owner, is_verified, badge_title, created_at)
            VALUES (?, ?, ?, ?, 1, 1, 'Founder & Architect', ?)
        """, (OWNER_USER, OWNER_EMAIL, hashed, salt, datetime.utcnow().isoformat()))
        owner_id = c.lastrowid
        c.execute("""
            INSERT OR IGNORE INTO profiles (
                user_id, display_name, bio, avatar_url, banner_url, background_url,
                bg_effect, theme, font_family, accent_color, card_opacity, card_blur,
                card_border_radius, audio_url, audio_title, audio_artist, audio_autoplay,
                socials_json, badges_json, custom_links_json
            ) VALUES (
                ?, 'Owner LO', 'The architect behind ShowMe. Breaking boundaries.',
                'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=400',
                'https://images.unsplash.com/photo-1579783900882-c0d3dad7b119?w=1200',
                'https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=1600',
                'aurora', 'cyberpunk', 'Syne', '#ec4899', 0.82, 16, 20,
                'https://cdn.pixabay.com/download/audio/2022/03/15/audio_c8c8a73467.mp3?filename=cyberpunk-2099-10701.mp3',
                'Synthwave Resonance', 'Master', 1,
                '{"github":"lo-writer","twitter":"lowriter","discord":"lo#0001","spotify":"lowriter","telegram":"lowriter"}',
                '["Crown Owner","Pioneer","System Architect"]',
                '[{"label":"My Vault","url":"https://github.com","icon":"vault"},{"label":"Secret Wire","url":"https://t.me","icon":"signal"}]'
            )
        """, (owner_id,))
        c.execute("""
            INSERT OR IGNORE INTO invites (
                user_id, slug, discord_code, destination_url, custom_title, custom_desc, accent_color, created_at
            ) VALUES (
                ?, 'syndicate', 'discord-developers', 'https://discord.gg/discord-developers',
                'The Syndicate Hub', 'Exclusive developer sanctuary and underground dispatch.', '#ec4899', ?
            )
        """, (owner_id, datetime.utcnow().isoformat()))
        conn.commit()

    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
