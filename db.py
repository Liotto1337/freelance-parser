"""SQLite-хранилище заказов."""
import json
import re
import sqlite3
from contextlib import contextmanager

import config
from sources import Order, utcnow

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site TEXT NOT NULL,
    ext_id TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    budget_text TEXT,
    budget INTEGER,
    categories TEXT,          -- JSON: все категории, где встретился заказ
    tags TEXT,                -- JSON: теги площадки
    skills TEXT,              -- JSON: найденные навыки (ключи из config.SKILLS)
    published_at TEXT,
    published_text TEXT,
    responses INTEGER,
    views INTEGER,
    hired INTEGER NOT NULL DEFAULT 0,    -- 1, если покупатель уже выбрал исполнителя
    status TEXT NOT NULL DEFAULT 'new',  -- new | interesting | responded | skipped
    note TEXT DEFAULT '',
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    UNIQUE(site, ext_id)
);
CREATE INDEX IF NOT EXISTS idx_orders_seen ON orders(first_seen);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    new_orders INTEGER DEFAULT 0,
    errors TEXT DEFAULT '[]'
);
"""

STATUSES = {
    "new": "Новый",
    "interesting": "Интересно",
    "responded": "Откликнулся",
    "skipped": "Пропущен",
}

_skill_patterns = {
    key: re.compile("|".join(pats), re.IGNORECASE)
    for key, (_, pats) in config.SKILLS.items()
}


def detect_skills(order: Order) -> list[str]:
    text = " ".join([order.title, order.description, " ".join(order.tags)])
    found = {k for k, rx in _skill_patterns.items() if rx.search(text)}
    if order.category_skill:
        found.add(order.category_skill)
    return sorted(found)


@contextmanager
def connect():
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    # Встроенный LOWER/LIKE в SQLite не понимает кириллицу
    conn.create_function("ulower", 1, lambda s: s.lower() if s else s, deterministic=True)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init():
    with connect() as c:
        c.executescript(SCHEMA)
        # Базы, созданные до появления колонки hired
        cols = {r["name"] for r in c.execute("PRAGMA table_info(orders)")}
        if "hired" not in cols:
            c.execute("ALTER TABLE orders ADD COLUMN hired INTEGER NOT NULL DEFAULT 0")


def upsert(conn, order: Order) -> bool:
    """Сохраняет заказ. Возвращает True, если заказ новый."""
    now = utcnow().isoformat()
    skills = detect_skills(order)
    row = conn.execute(
        "SELECT id, categories, skills FROM orders WHERE site=? AND ext_id=?",
        (order.site, order.ext_id)).fetchone()
    if row is None:
        conn.execute(
            """INSERT INTO orders (site, ext_id, url, title, description, budget_text,
               budget, categories, tags, skills, published_at, published_text,
               responses, views, hired, first_seen, last_seen)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (order.site, order.ext_id, order.url, order.title, order.description,
             order.budget_text, order.budget, json.dumps([order.category], ensure_ascii=False),
             json.dumps(order.tags, ensure_ascii=False), json.dumps(skills),
             order.published_at or now, order.published_text,
             order.responses, order.views, int(order.hired), now, now))
        return True
    cats = json.loads(row["categories"] or "[]")
    if order.category not in cats:
        cats.append(order.category)
    merged = sorted(set(json.loads(row["skills"] or "[]")) | set(skills))
    conn.execute(
        """UPDATE orders SET title=?, budget_text=?, budget=?, categories=?, skills=?,
           responses=COALESCE(?, responses), views=COALESCE(?, views), hired=?, last_seen=?
           WHERE id=?""",
        (order.title, order.budget_text, order.budget,
         json.dumps(cats, ensure_ascii=False), json.dumps(merged),
         order.responses, order.views, int(order.hired), now, row["id"]))
    return False
