import sqlite3
from werkzeug.security import generate_password_hash


DB_NAME = "app.db"

# -------------------------------
# DATABASE CONNECTION
# -------------------------------

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    # Enforce FK constraints for every connection.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# -------------------------------
# NORMALIZATION HELPERS
# -------------------------------

def _normalize_text(value):
    if value is None:
        return None
    value = value.strip()
    return value if value else None


def _normalize_email(value):
    value = _normalize_text(value)
    return value.lower() if value else None


# -------------------------------
# ID LOOKUPS / ENSURE HELPERS
# -------------------------------

def _get_department_id(conn, name, create=False):
    name = _normalize_text(name)
    if not name:
        return None
    row = conn.execute(
        "SELECT id FROM departments WHERE name = ?",
        (name,)
    ).fetchone()
    if row:
        return row["id"]
    if create:
        conn.execute(
            "INSERT OR IGNORE INTO departments (name) VALUES (?)",
            (name,)
        )
        row = conn.execute(
            "SELECT id FROM departments WHERE name = ?",
            (name,)
        ).fetchone()
        return row["id"] if row else None
    return None


def _get_user_id(conn, username):
    username = _normalize_text(username)
    if not username:
        return None
    row = conn.execute(
        "SELECT id FROM users WHERE username = ?",
        (username,)
    ).fetchone()
    return row["id"] if row else None


def _get_checklist_item_id(conn, department_id, item, create=False):
    item = _normalize_text(item)
    if not department_id or not item:
        return None
    row = conn.execute(
        "SELECT id FROM checklist_items WHERE department_id = ? AND item = ?",
        (department_id, item)
    ).fetchone()
    if row:
        return row["id"]
    if create:
        conn.execute(
            "INSERT OR IGNORE INTO checklist_items (department_id, item) VALUES (?, ?)",
            (department_id, item)
        )
        row = conn.execute(
            "SELECT id FROM checklist_items WHERE department_id = ? AND item = ?",
            (department_id, item)
        ).fetchone()
        return row["id"] if row else None
    return None


# -------------------------------
# INITIALIZE DATABASE
# -------------------------------

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # DEPARTMENTS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL COLLATE NOCASE
        )
    """)

    # USERS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL COLLATE NOCASE,
            password TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            department_id INTEGER,
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL
        )
    """)

    # ADMINS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL COLLATE NOCASE,
            password TEXT NOT NULL
        )
    """)

    # CHECKLIST ITEMS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS checklist_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department_id INTEGER NOT NULL,
            item TEXT NOT NULL,
            UNIQUE (department_id, item),
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE
        )
    """)

    # CHECKLIST PROGRESS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS checklist_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            checklist_item_id INTEGER NOT NULL,
            checked INTEGER NOT NULL DEFAULT 0 CHECK (checked IN (0, 1)),
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (user_id, checklist_item_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (checklist_item_id) REFERENCES checklist_items(id) ON DELETE CASCADE
        )
    """)

    # SUBMISSION ORDER
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS submission_order (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department_id INTEGER NOT NULL,
            checklist_item_id INTEGER NOT NULL,
            position INTEGER NOT NULL CHECK (position >= 0),
            UNIQUE (department_id, position),
            UNIQUE (department_id, checklist_item_id),
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE,
            FOREIGN KEY (checklist_item_id) REFERENCES checklist_items(id) ON DELETE CASCADE
        )
    """)

    # FAQ CATEGORIES
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faq_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)

    # FAQS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faqs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            FOREIGN KEY (category_id) REFERENCES faq_categories(id) ON DELETE CASCADE
        )
    """)

    # DOCUMENT TEMPLATES
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL
        )
    """)

    # INDEXES
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_checklist_items_department
        ON checklist_items(department_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_checklist_progress_user
        ON checklist_progress(user_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_checklist_progress_item
        ON checklist_progress(checklist_item_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_submission_order_department_position
        ON submission_order(department_id, position)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_faqs_category
        ON faqs(category_id)
    """)

    conn.commit()
    conn.close()
    print("database initialized successfully")


# -------------------------------
# USER FUNCTIONS
# -------------------------------

def create_user(username, password, email, phone):
    username = _normalize_text(username)
    email = _normalize_email(email)
    phone = _normalize_text(phone)
    hashed_pw = generate_password_hash(password)

    if not username:
        return

    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO users (username, password, email, phone) VALUES (?, ?, ?, ?)",
            (username, hashed_pw, email, phone)
        )


def get_user(username):
    username = _normalize_text(username)
    if not username:
        return None

    with get_db_connection() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
    return user


# -------------------------------
# ADMIN FUNCTIONS
# -------------------------------

def create_admin(username, password):
    username = _normalize_text(username)
    if not username:
        return

    hashed = generate_password_hash(password)
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO admins (username, password) VALUES (?, ?)",
            (username, hashed)
        )


def get_admin(username):
    username = _normalize_text(username)
    if not username:
        return None

    with get_db_connection() as conn:
        admin = conn.execute(
            "SELECT * FROM admins WHERE username = ?",
            (username,)
        ).fetchone()
    return admin


def ensure_admin_exists():
    # Security: do NOT auto-create a default admin account.
    with get_db_connection() as conn:
        admin = conn.execute(
            "SELECT 1 FROM admins LIMIT 1"
        ).fetchone()
    return bool(admin)


# -------------------------------
# DEPARTMENTS
# -------------------------------

def get_departments():
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT name FROM departments ORDER BY name"
        ).fetchall()
    return [row["name"] for row in rows]


def add_department(name):
    name = _normalize_text(name)
    if not name:
        return

    with get_db_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO departments (name) VALUES (?)",
            (name,)
        )


def delete_department_by_name(name):
    name = _normalize_text(name)
    if not name:
        return

    with get_db_connection() as conn:
        conn.execute("DELETE FROM departments WHERE name = ?", (name,))


# -------------------------------
# CHECKLIST ITEMS
# -------------------------------

def get_checklist_items(department):
    department = _normalize_text(department)
    if not department:
        return []

    with get_db_connection() as conn:
        department_id = _get_department_id(conn, department)
        if not department_id:
            return []
        rows = conn.execute(
            "SELECT id, item FROM checklist_items WHERE department_id = ? ORDER BY id",
            (department_id,)
        ).fetchall()
    return [dict(row) for row in rows]


def add_checklist_item(department, item):
    department = _normalize_text(department)
    item = _normalize_text(item)
    if not department or not item:
        return

    with get_db_connection() as conn:
        department_id = _get_department_id(conn, department, create=True)
        if not department_id:
            return
        conn.execute(
            "INSERT OR IGNORE INTO checklist_items (department_id, item) VALUES (?, ?)",
            (department_id, item)
        )


def delete_checklist_item_by_id(item_id):
    with get_db_connection() as conn:
        conn.execute(
            "DELETE FROM checklist_items WHERE id = ?",
            (item_id,)
        )


# Backwards-compatible alias used in app.py
def delete_checklist_item(item_id):
    delete_checklist_item_by_id(item_id)


# -------------------------------
# CHECKLIST PROGRESS
# -------------------------------

def save_progress(username, department, item, checked):
    try:
        checked_value = 1 if int(checked) == 1 else 0
    except (TypeError, ValueError):
        checked_value = 0

    with get_db_connection() as conn:
        user_id = _get_user_id(conn, username)
        department_id = _get_department_id(conn, department)
        checklist_item_id = _get_checklist_item_id(conn, department_id, item)

        if not user_id or not checklist_item_id:
            return

        conn.execute("""
            INSERT INTO checklist_progress (user_id, checklist_item_id, checked)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, checklist_item_id)
            DO UPDATE SET checked = excluded.checked,
                         updated_at = CURRENT_TIMESTAMP
        """, (user_id, checklist_item_id, checked_value))


def load_progress(username, department):
    with get_db_connection() as conn:
        user_id = _get_user_id(conn, username)
        department_id = _get_department_id(conn, department)

        if not user_id or not department_id:
            return {}

        rows = conn.execute("""
            SELECT ci.item, cp.checked
            FROM checklist_progress cp
            JOIN checklist_items ci ON cp.checklist_item_id = ci.id
            WHERE cp.user_id = ? AND ci.department_id = ?
        """, (user_id, department_id)).fetchall()

    return {row["item"]: row["checked"] for row in rows}


# -------------------------------
# SUBMISSION ORDER
# -------------------------------

def get_submission_order(department):
    with get_db_connection() as conn:
        department_id = _get_department_id(conn, department)
        if not department_id:
            return []
        rows = conn.execute("""
            SELECT ci.item
            FROM submission_order so
            JOIN checklist_items ci ON so.checklist_item_id = ci.id
            WHERE so.department_id = ?
            ORDER BY so.position
        """, (department_id,)).fetchall()

    return [row["item"] for row in rows]


def save_submission_order(department, items):
    department = _normalize_text(department)
    if not department:
        return

    normalized_items = []
    seen = set()
    for item in items:
        value = _normalize_text(item)
        if value:
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized_items.append(value)

    with get_db_connection() as conn:
        department_id = _get_department_id(conn, department, create=True)
        if not department_id:
            return

        # Transaction ensures delete + insert is atomic.
        conn.execute(
            "DELETE FROM submission_order WHERE department_id = ?",
            (department_id,)
        )
        for index, item in enumerate(normalized_items):
            checklist_item_id = _get_checklist_item_id(conn, department_id, item, create=True)
            if not checklist_item_id:
                continue
            conn.execute("""
                INSERT INTO submission_order (department_id, checklist_item_id, position)
                VALUES (?, ?, ?)
            """, (department_id, checklist_item_id, index))


# -------------------------------
# FAQ FUNCTIONS
# -------------------------------

def get_categories():
    with get_db_connection() as conn:
        categories = conn.execute(
            "SELECT * FROM faq_categories ORDER BY name"
        ).fetchall()
    return categories


def add_category(name):
    name = _normalize_text(name)
    if not name:
        return

    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO faq_categories (name) VALUES (?)",
            (name,)
        )


def update_category(cat_id, new_name):
    new_name = _normalize_text(new_name)
    if not new_name:
        return

    with get_db_connection() as conn:
        conn.execute(
            "UPDATE faq_categories SET name = ? WHERE id = ?",
            (new_name, cat_id)
        )


def delete_category(cat_id):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM faq_categories WHERE id = ?", (cat_id,))


def get_faqs():
    with get_db_connection() as conn:
        faqs = conn.execute(
            """SELECT f.id, f.question, f.answer, f.category_id, c.name AS category_name
           FROM faqs f
           JOIN faq_categories c ON f.category_id = c.id
           ORDER BY c.name, f.id"""
        ).fetchall()
    return faqs


def add_faq(category_id, question, answer):
    question = _normalize_text(question)
    answer = _normalize_text(answer)
    if not question or not answer:
        return

    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO faqs (category_id, question, answer) VALUES (?, ?, ?)",
            (category_id, question, answer)
        )


def get_faq_by_id(faq_id):
    with get_db_connection() as conn:
        faq = conn.execute(
            "SELECT * FROM faqs WHERE id = ?",
            (faq_id,)
        ).fetchone()
    return faq


def update_faq(faq_id, category_id, question, answer):
    question = _normalize_text(question)
    answer = _normalize_text(answer)
    if not question or not answer:
        return

    with get_db_connection() as conn:
        conn.execute(
            "UPDATE faqs SET category_id = ?, question = ?, answer = ? WHERE id = ?",
            (category_id, question, answer, faq_id)
        )


def delete_faq(faq_id):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM faqs WHERE id = ?", (faq_id,))


def get_faqs_grouped_by_category():
    all_faqs = get_faqs()
    grouped = {}
    for faq in all_faqs:
        category = faq["category_name"]
        if category not in grouped:
            grouped[category] = []
        grouped[category].append(faq)
    return grouped


# -------------------------------
# TEMPLATE FUNCTIONS
# -------------------------------

def get_templates():
    with get_db_connection() as conn:
        templates = conn.execute(
            "SELECT * FROM templates ORDER BY name"
        ).fetchall()
    return templates


def get_template_by_name(name):
    name = _normalize_text(name)
    if not name:
        return None

    with get_db_connection() as conn:
        template = conn.execute(
            "SELECT * FROM templates WHERE name = ?",
            (name,)
        ).fetchone()
    return template


def save_template(name, content):
    name = _normalize_text(name)
    if content is None:
        content_value = None
    else:
        content_value = str(content)

    if not name or content_value is None:
        return

    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO templates (name, content)
            VALUES (?, ?)
            ON CONFLICT(name)
            DO UPDATE SET content = excluded.content
        """, (name, content_value))
