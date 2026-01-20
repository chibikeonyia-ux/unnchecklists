import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash


DB_NAME = "app.db"

# -------------------------------
# DATABASE CONNECTION
# -------------------------------
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# -------------------------------
# INITIALIZE DATABASE
# -------------------------------
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # USERS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            department TEXT
        )
    """)

    # ADMINS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # DEPARTMENTS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)

    # CHECKLIST ITEMS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS checklist_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department TEXT NOT NULL,
            item TEXT NOT NULL
        )
    """)

    # CHECKLIST PROGRESS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS checklist_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            department TEXT NOT NULL,
            item TEXT NOT NULL,
            checked INTEGER NOT NULL,
            UNIQUE(username, department, item)
        )
    """)

    # SUBMISSION ORDER
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS submission_order (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department TEXT NOT NULL,
            item TEXT NOT NULL,
            position INTEGER NOT NULL
        )
    """)

    # FAQ



    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faqs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            FOREIGN KEY (category_id) REFERENCES faq_categories(id)
    );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faq_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );
    """)

    # DOCUMENT TEMPLATES
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL
        )
    """)



    conn.commit()
    conn.close()
    print("database initialized successfully")



# -------------------------------
# USER FUNCTIONS
# -------------------------------
def create_user(username, password, email, phone):
    conn = get_db_connection()
    hashed_pw = generate_password_hash(password)
    conn.execute(
        "INSERT INTO users (username, password, email, phone) VALUES (?, ?, ?, ?)",
        (username, hashed_pw, email, phone)
    )
    conn.commit()
    conn.close()



def get_user(username):
    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    return user


# -------------------------------
# ADMIN FUNCTIONS
# -------------------------------
def create_admin(username, password):
    hashed = generate_password_hash(password)
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO admins (username, password) VALUES (?, ?)",
        (username, hashed)
    )
    conn.commit()
    conn.close()


def get_admin(username):
    conn = get_db_connection()
    admin = conn.execute(
        "SELECT * FROM admins WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    return admin


def ensure_admin_exists():
    conn = get_db_connection()
    admin = conn.execute(
        "SELECT * FROM admins WHERE username = ?",
        ("admin",)
    ).fetchone()
    conn.close()

    if not admin:
        create_admin("admin", "admin123")


# -------------------------------
# DEPARTMENTS
# -------------------------------
def get_departments():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT name FROM departments ORDER BY name"
    ).fetchall()
    conn.close()
    return [row["name"] for row in rows]


def add_department(name):
    conn = get_db_connection()
    conn.execute(
        "INSERT OR IGNORE INTO departments (name) VALUES (?)",
        (name,)
    )
    conn.commit()
    conn.close()


def delete_department_by_name(name):
    conn = get_db_connection()
    conn.execute("DELETE FROM departments WHERE name = ?", (name,))
    conn.commit()
    conn.close()



# -------------------------------
# CHECKLIST ITEMS
# -------------------------------
# -------------------------------
# CHECKLIST ITEMS
# -------------------------------
def get_checklist_items(department):
    department = department.strip()  # remove trailing spaces
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, item FROM checklist_items WHERE department = ?",
        (department,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]  # returns list of dicts with keys: id, item


def add_checklist_item(department, item):
    department = department.strip()
    item = item.strip()
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO checklist_items (department, item) VALUES (?, ?)",
        (department, item)
    )
    conn.commit()
    conn.close()



def delete_checklist_item_by_id(item_id):  # ✅ updated function name for clarity
    conn = get_db_connection()
    conn.execute(
        "DELETE FROM checklist_items WHERE id = ?",
        (item_id,)
    )
    conn.commit()
    conn.close()


# -------------------------------
# CHECKLIST PROGRESS
# -------------------------------
def save_progress(username, department, item, checked):
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO checklist_progress (username, department, item, checked)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(username, department, item)
        DO UPDATE SET checked = excluded.checked
    """, (username, department, item, checked))
    conn.commit()
    conn.close()


def load_progress(username, department):
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT item, checked
        FROM checklist_progress
        WHERE username = ? AND department = ?
    """, (username, department)).fetchall()
    conn.close()
    return {row["item"]: row["checked"] for row in rows}


# -------------------------------
# SUBMISSION ORDER
# -------------------------------
def get_submission_order(department):
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT item FROM submission_order
        WHERE department = ?
        ORDER BY position
    """, (department,)).fetchall()
    conn.close()
    print("DEBUG get_submission_order:", department, rows)
    return [row["item"] for row in rows]


def save_submission_order(department, items):
    conn = get_db_connection()
    conn.execute(
        "DELETE FROM submission_order WHERE department = ?",
        (department,)
    )
    for index, item in enumerate(items):
        conn.execute("""
            INSERT INTO submission_order (department, item, position)
            VALUES (?, ?, ?)
        """, (department, item, index))
    conn.commit()
    conn.close()
    print("DEBUG save_submission_order:", department, items)


# -------------------------------
# FAQ FUNCTIONS
# -------------------------------
def get_categories():
    conn = get_db_connection()
    categories = conn.execute(
        "SELECT * FROM faq_categories ORDER BY name"
    ).fetchall()
    conn.close()
    return categories

def add_category(name):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO faq_categories (name) VALUES (?)",
        (name,)
    )
    conn.commit()
    conn.close()

def update_category(cat_id, new_name):
    conn = get_db_connection()
    conn.execute(
        "UPDATE faq_categories SET name = ? WHERE id = ?",
        (new_name, cat_id)
    )
    conn.commit()
    conn.close()

def delete_category(cat_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM faq_categories WHERE id = ?", (cat_id,))
    conn.commit()
    conn.close()

def get_faqs():
    conn = get_db_connection()
    faqs = conn.execute(
        """SELECT f.id, f.question, f.answer, f.category_id, c.name AS category_name
           FROM faqs f
           JOIN faq_categories c ON f.category_id = c.id
           ORDER BY c.name, f.id"""
    ).fetchall()
    conn.close()
    return faqs

def add_faq(category_id, question, answer):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO faqs (category_id, question, answer) VALUES (?, ?, ?)",
        (category_id, question, answer)
    )
    conn.commit()
    conn.close()

def get_faq_by_id(faq_id):
    conn = get_db_connection()
    faq = conn.execute("SELECT * FROM faqs WHERE id = ?", (faq_id,)).fetchone()
    conn.close()
    return faq

def update_faq(faq_id, category_id, question, answer):
    conn = get_db_connection()
    conn.execute(
        "UPDATE faqs SET category_id = ?, question = ?, answer = ? WHERE id = ?",
        (category_id, question, answer, faq_id)
    )
    conn.commit()
    conn.close()

def delete_faq(faq_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM faqs WHERE id = ?", (faq_id,))
    conn.commit()
    conn.close()

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
    conn = get_db_connection()
    templates = conn.execute(
        "SELECT * FROM templates ORDER BY name"
    ).fetchall()
    conn.close()
    return templates


def get_template_by_name(name):
    conn = get_db_connection()
    template = conn.execute(
        "SELECT * FROM templates WHERE name = ?",
        (name,)
    ).fetchone()
    conn.close()
    return template


def save_template(name, content):
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO templates (name, content)
        VALUES (?, ?)
        ON CONFLICT(name)
        DO UPDATE SET content = excluded.content
    """, (name, content))
    conn.commit()
    conn.close()

def delete_checklist_item(item_id):
    conn = get_db_connection()
    conn.execute(
        "DELETE FROM checklist_items WHERE id = ?",
        (item_id,)
    )
    conn.commit()
    conn.close()


def get_categories():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM faq_categories ORDER BY name").fetchall()
    conn.close()
    return rows


def add_category(name):
    conn = get_db_connection()
    conn.execute("INSERT INTO faq_categories (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()


def update_category(cat_id, new_name):
    conn = get_db_connection()
    conn.execute("UPDATE faq_categories SET name = ? WHERE id = ?", (new_name, cat_id))
    conn.commit()
    conn.close()


def delete_category(cat_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM faq_categories WHERE id = ?", (cat_id,))
    conn.commit()
    conn.close()
