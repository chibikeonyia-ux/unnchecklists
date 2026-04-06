"""
Migration script: TEXT-based schema -> ID-based schema with foreign keys.

Steps:
1. Creates new *_v2 tables with normalized relationships and constraints.
2. Migrates departments, users, admins, checklist items, submission order,
   checklist progress, FAQ categories/faqs, templates.
3. Renames old tables to *_old and swaps in new tables.
4. Creates indexes.

IMPORTANT: This script makes a backup of app.db before changing anything.
"""
import datetime
import os
import shutil
import sqlite3

DB_NAME = "app.db"


def normalize_text(value):
    if value is None:
        return None
    value = value.strip()
    return value if value else None


def table_exists(conn, name):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (name,)
    ).fetchone()
    return row is not None


def main():
    if not os.path.exists(DB_NAME):
        raise FileNotFoundError(f"{DB_NAME} not found")

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"{DB_NAME}.bak_{timestamp}"
    shutil.copyfile(DB_NAME, backup)
    print(f"Backup created: {backup}")

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    cur = conn.cursor()

    # 1) Create v2 tables
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS departments_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL COLLATE NOCASE
    );

    CREATE TABLE IF NOT EXISTS users_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL COLLATE NOCASE,
        password TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        department_id INTEGER,
        FOREIGN KEY (department_id) REFERENCES departments_v2(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS admins_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL COLLATE NOCASE,
        password TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS checklist_items_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        department_id INTEGER NOT NULL,
        item TEXT NOT NULL,
        UNIQUE (department_id, item),
        FOREIGN KEY (department_id) REFERENCES departments_v2(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS checklist_progress_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        checklist_item_id INTEGER NOT NULL,
        checked INTEGER NOT NULL DEFAULT 0 CHECK (checked IN (0, 1)),
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (user_id, checklist_item_id),
        FOREIGN KEY (user_id) REFERENCES users_v2(id) ON DELETE CASCADE,
        FOREIGN KEY (checklist_item_id) REFERENCES checklist_items_v2(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS submission_order_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        department_id INTEGER NOT NULL,
        checklist_item_id INTEGER NOT NULL,
        position INTEGER NOT NULL CHECK (position >= 0),
        UNIQUE (department_id, position),
        UNIQUE (department_id, checklist_item_id),
        FOREIGN KEY (department_id) REFERENCES departments_v2(id) ON DELETE CASCADE,
        FOREIGN KEY (checklist_item_id) REFERENCES checklist_items_v2(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS faq_categories_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    );

    CREATE TABLE IF NOT EXISTS faqs_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        FOREIGN KEY (category_id) REFERENCES faq_categories_v2(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS templates_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        content TEXT NOT NULL
    );
    """)

    # 2) Migrate departments from all sources
    dept_names = set()
    sources = [
        ("departments", "name"),
        ("checklist_items", "department"),
        ("submission_order", "department"),
        ("checklist_progress", "department"),
        ("users", "department"),
    ]
    for table, column in sources:
        if not table_exists(conn, table):
            continue
        for row in conn.execute(f"SELECT DISTINCT {column} FROM {table}").fetchall():
            name = normalize_text(row[column])
            if name:
                dept_names.add(name)

    for name in sorted(dept_names):
        conn.execute("INSERT OR IGNORE INTO departments_v2 (name) VALUES (?)", (name,))

    def get_department_id(name):
        if not name:
            return None
        row = conn.execute(
            "SELECT id FROM departments_v2 WHERE name = ?",
            (name,)
        ).fetchone()
        return row["id"] if row else None

    # 3) Migrate users
    if table_exists(conn, "users"):
        users = conn.execute("SELECT username, password, email, phone, department FROM users").fetchall()
        for row in users:
            dept_id = get_department_id(normalize_text(row["department"]))
            conn.execute(
                "INSERT OR IGNORE INTO users_v2 (username, password, email, phone, department_id) VALUES (?, ?, ?, ?, ?)",
                (
                    normalize_text(row["username"]),
                    row["password"],
                    row["email"],
                    row["phone"],
                    dept_id,
                )
            )

    # 4) Migrate admins
    if table_exists(conn, "admins"):
        admins = conn.execute("SELECT username, password FROM admins").fetchall()
        for row in admins:
            conn.execute(
                "INSERT OR IGNORE INTO admins_v2 (username, password) VALUES (?, ?)",
                (normalize_text(row["username"]), row["password"])
            )

    # 5) Migrate checklist items
    if table_exists(conn, "checklist_items"):
        items = conn.execute("SELECT department, item FROM checklist_items").fetchall()
        for row in items:
            dept_id = get_department_id(normalize_text(row["department"]))
            item = normalize_text(row["item"])
            if dept_id and item:
                conn.execute(
                    "INSERT OR IGNORE INTO checklist_items_v2 (department_id, item) VALUES (?, ?)",
                    (dept_id, item)
                )

    # Ensure any items referenced by submission_order or progress exist
    extra_sources = [
        ("submission_order", "department", "item"),
        ("checklist_progress", "department", "item"),
    ]
    for table, dept_col, item_col in extra_sources:
        if not table_exists(conn, table):
            continue
        for row in conn.execute(f"SELECT DISTINCT {dept_col}, {item_col} FROM {table}").fetchall():
            dept_id = get_department_id(normalize_text(row[dept_col]))
            item = normalize_text(row[item_col])
            if dept_id and item:
                conn.execute(
                    "INSERT OR IGNORE INTO checklist_items_v2 (department_id, item) VALUES (?, ?)",
                    (dept_id, item)
                )

    def get_checklist_item_id(dept_id, item):
        if not dept_id or not item:
            return None
        row = conn.execute(
            "SELECT id FROM checklist_items_v2 WHERE department_id = ? AND item = ?",
            (dept_id, item)
        ).fetchone()
        return row["id"] if row else None

    def get_user_id(username):
        if not username:
            return None
        row = conn.execute(
            "SELECT id FROM users_v2 WHERE username = ?",
            (username,)
        ).fetchone()
        return row["id"] if row else None

    # 6) Migrate submission order
    if table_exists(conn, "submission_order"):
        rows = conn.execute("SELECT department, item, position FROM submission_order").fetchall()
        for row in rows:
            dept_id = get_department_id(normalize_text(row["department"]))
            item = normalize_text(row["item"])
            item_id = get_checklist_item_id(dept_id, item)
            if dept_id and item_id is not None:
                conn.execute(
                    "INSERT OR IGNORE INTO submission_order_v2 (department_id, checklist_item_id, position) VALUES (?, ?, ?)",
                    (dept_id, item_id, row["position"])
                )

    # 7) Migrate checklist progress
    if table_exists(conn, "checklist_progress"):
        rows = conn.execute("SELECT username, department, item, checked FROM checklist_progress").fetchall()
        for row in rows:
            user_id = get_user_id(normalize_text(row["username"]))
            dept_id = get_department_id(normalize_text(row["department"]))
            item = normalize_text(row["item"])
            item_id = get_checklist_item_id(dept_id, item)
            if user_id and item_id:
                checked = 1 if row["checked"] else 0
                conn.execute(
                    "INSERT OR IGNORE INTO checklist_progress_v2 (user_id, checklist_item_id, checked) VALUES (?, ?, ?)",
                    (user_id, item_id, checked)
                )

    # 8) Migrate FAQ categories and FAQs
    if table_exists(conn, "faq_categories"):
        rows = conn.execute("SELECT id, name FROM faq_categories").fetchall()
        for row in rows:
            conn.execute(
                "INSERT OR IGNORE INTO faq_categories_v2 (id, name) VALUES (?, ?)",
                (row["id"], row["name"])
            )

    if table_exists(conn, "faqs"):
        rows = conn.execute("SELECT id, category_id, question, answer FROM faqs").fetchall()
        for row in rows:
            conn.execute(
                "INSERT OR IGNORE INTO faqs_v2 (id, category_id, question, answer) VALUES (?, ?, ?, ?)",
                (row["id"], row["category_id"], row["question"], row["answer"])
            )

    # 9) Migrate templates
    if table_exists(conn, "templates"):
        rows = conn.execute("SELECT id, name, content FROM templates").fetchall()
        for row in rows:
            conn.execute(
                "INSERT OR IGNORE INTO templates_v2 (id, name, content) VALUES (?, ?, ?)",
                (row["id"], row["name"], row["content"])
            )

    # 10) Swap tables
    table_pairs = [
        ("users", "users_v2"),
        ("admins", "admins_v2"),
        ("departments", "departments_v2"),
        ("checklist_items", "checklist_items_v2"),
        ("checklist_progress", "checklist_progress_v2"),
        ("submission_order", "submission_order_v2"),
        ("faq_categories", "faq_categories_v2"),
        ("faqs", "faqs_v2"),
        ("templates", "templates_v2"),
    ]

    for old, new in table_pairs:
        if table_exists(conn, old):
            conn.execute(f"ALTER TABLE {old} RENAME TO {old}_old")
        conn.execute(f"ALTER TABLE {new} RENAME TO {old}")

    # 11) Create indexes
    conn.executescript("""
    CREATE INDEX IF NOT EXISTS idx_checklist_items_department
        ON checklist_items(department_id);
    CREATE INDEX IF NOT EXISTS idx_checklist_progress_user
        ON checklist_progress(user_id);
    CREATE INDEX IF NOT EXISTS idx_checklist_progress_item
        ON checklist_progress(checklist_item_id);
    CREATE INDEX IF NOT EXISTS idx_submission_order_department_position
        ON submission_order(department_id, position);
    CREATE INDEX IF NOT EXISTS idx_faqs_category
        ON faqs(category_id);
    """)

    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")
    conn.close()

    print("Migration complete. Old tables renamed with _old suffix.")


if __name__ == "__main__":
    main()
