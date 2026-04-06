import os
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from database import (
    init_db, get_db_connection,
    create_user, get_user,
    create_admin, get_admin,
    get_departments, add_department, delete_department_by_name,
    get_checklist_items, add_checklist_item, delete_checklist_item,
    save_progress, load_progress,
    get_submission_order, save_submission_order, add_category, get_categories, delete_department_by_name
)


from database import ensure_admin_exists
from database import (
    get_faqs, add_faq, delete_faq, update_faq,
    get_templates, get_template_by_name, save_template,
    add_category, update_category, get_categories, get_faq_by_id, delete_category, get_faqs,
)





from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import io

app = Flask(__name__)
app.secret_key = "super-secret-key-change-later"

# Initialize database
init_db()
ensure_admin_exists()


# -----------------------------
# HOME
# -----------------------------
@app.route("/")
def home():
    return render_template("index.html")


# -----------------------------
# AUTH – USERS
# -----------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    error = None

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        email = request.form.get("email")
        phone = request.form.get("phone")

        if get_user(username):
            flash("Username already exists")
        else:
            # password will be hashed inside create_user()
            create_user(username, password, email, phone)
            session["user"] = username
            return redirect(url_for("select_department"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = get_user(username)

        if not user or not check_password_hash(user["password"], password):
            flash("Invalid login details")
        else:
            session["user"] = username
            return redirect(url_for("select_department"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


# -----------------------------
# AUTH – ADMIN
# -----------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        admin = get_admin(username)

        if not admin or not check_password_hash(admin["password"], password):
            flash("Invalid admin credentials")
        else:
            session["admin"] = username
            return redirect("/admin/dashboard")

    return render_template("admin_login.html")


# -----------------------------
# ADMIN SETUP (ONE-TIME)
# -----------------------------
@app.route("/setup-admin", methods=["GET", "POST"])
def setup_admin():
    # Allow only when no admin exists and a setup token is configured.
    if ensure_admin_exists():
        abort(404)

    setup_token = os.environ.get("ADMIN_SETUP_TOKEN")
    if not setup_token:
        abort(404)

    if request.method == "POST":
        token = request.form.get("token", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if token != setup_token:
            flash("Invalid setup token.", "error")
        elif not username or not password:
            flash("Username and password are required.", "error")
        else:
            create_admin(username, password)
            flash("Admin account created. Please log in.", "success")
            return redirect(url_for("admin_login"))

    return render_template("setup_admin.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect("/")


# -----------------------------
# ADMIN DASHBOARD
# -----------------------------
@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect("/admin/login")

    conn = get_db_connection()
    users = conn.execute("""
        SELECT u.username, u.email, u.phone, d.name AS department
        FROM users u
        LEFT JOIN departments d ON u.department_id = d.id
        ORDER BY u.username
    """).fetchall()

    total_users = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
    total_departments = conn.execute("SELECT COUNT(*) AS count FROM departments").fetchone()["count"]
    total_faqs = conn.execute("SELECT COUNT(*) AS count FROM faqs").fetchone()["count"]

    department_rows = conn.execute(
        "SELECT id, name FROM departments ORDER BY name"
    ).fetchall()

    dept_item_rows = conn.execute("""
        SELECT department_id, COUNT(*) AS total_items
        FROM checklist_items
        GROUP BY department_id
    """).fetchall()
    dept_item_map = {row["department_id"]: row["total_items"] for row in dept_item_rows}

    progress_rows = conn.execute("""
        SELECT u.username,
               d.id AS department_id,
               d.name AS department,
               SUM(CASE WHEN cp.checked = 1 THEN 1 ELSE 0 END) AS completed
        FROM checklist_progress cp
        JOIN users u ON cp.user_id = u.id
        JOIN checklist_items ci ON cp.checklist_item_id = ci.id
        JOIN departments d ON ci.department_id = d.id
        GROUP BY u.username, d.id, d.name
        ORDER BY u.username, d.name
    """).fetchall()

    progress_overview = []
    progress_users = set()
    progress_by_department = {}
    for row in progress_rows:
        total_items = dept_item_map.get(row["department_id"], 0)
        completed = row["completed"] or 0
        percent = round((completed / total_items) * 100) if total_items else 0

        progress_overview.append({
            "username": row["username"],
            "department": row["department"],
            "completed": completed,
            "total": total_items,
            "percent": percent
        })
        progress_users.add(row["username"])
        progress_by_department.setdefault(row["department_id"], []).append({
            "username": row["username"],
            "completed": completed
        })

    users_no_progress = [user["username"] for user in users if user["username"] not in progress_users]

    department_stats = []
    for dept_row in department_rows:
        department = dept_row["name"]
        department_id = dept_row["id"]
        total_items = dept_item_map.get(department_id, 0)
        dept_progress = progress_by_department.get(department_id, [])
        students_started = len({entry["username"] for entry in dept_progress})
        total_completed = sum(entry["completed"] for entry in dept_progress)
        avg_completion = 0
        if students_started and total_items:
            avg_completion = round((total_completed / (students_started * total_items)) * 100)

        department_stats.append({
            "department": department,
            "total_items": total_items,
            "students_started": students_started,
            "avg_completion": avg_completion
        })

    conn.close()

    return render_template(
        "admin_dashboard.html",
        users=users,
        total_users=total_users,
        total_departments=total_departments,
        total_faqs=total_faqs,
        progress_overview=progress_overview,
        users_no_progress=users_no_progress,
        department_stats=department_stats
    )


# -----------------------------
# ADMIN – DEPARTMENTS
# -----------------------------
@app.route("/admin/departments", methods=["GET", "POST"])
def admin_departments():
    if "admin" not in session:
        return redirect("/admin/login")

    if request.method == "POST":
        name = request.form.get("name")
        if name:
            add_department(name)

    departments = get_departments()
    return render_template("admin_departments.html", departments=departments)


@app.route("/admin/departments/delete/<path:department>")
def delete_department(department):
    if "admin" not in session:
        return redirect("/admin/login")

    delete_department_by_name(department)
    return redirect("/admin/departments")



# -----------------------------
# ADMIN – CHECKLIST ITEMS
# -----------------------------
@app.route("/admin/checklist-items", methods=["GET", "POST"])
def admin_checklist_items():
    if "admin" not in session:
        return redirect("/admin/login")

    departments = get_departments()  # get all departments
    department = request.args.get("department", "").strip()  # trim spaces

    # Handle adding a new checklist item
    if request.method == "POST":
        item = request.form.get("item", "").strip()
        dept = request.form.get("department", "").strip()
        if item and dept:
            add_checklist_item(dept, item)
        return redirect(url_for("admin_checklist_items", department=dept))

    # Fetch items for the selected department
    items = get_checklist_items(department) if department else []

    return render_template(
        "admin_checklist_items.html",
        departments=departments,
        selected_department=department,
        items=items
    )



@app.route("/admin/checklist-items/delete/<int:item_id>")
def admin_delete_checklist_item(item_id):
    if "admin" not in session:
        return redirect("/admin/login")

    delete_checklist_item(item_id)

    # redirect back to previous page to keep department selected
    ref = request.referrer or url_for('admin_checklist_items')
    return redirect(ref)



# -----------------------------
# ADMIN – SUBMISSION ORDER
# -----------------------------
@app.route("/admin/submission-order", methods=["GET", "POST"])
def admin_submission_order():
    if "admin" not in session:
        return redirect("/admin/login")

    departments = get_departments()
    department = request.args.get("department")
    current_order = []

    # Load existing order when department is selected
    if department:
        current_order = get_submission_order(department)

    # Save updated order
    if request.method == "POST":
        department = request.form.get("department")
        items = request.form.get("items")

        if department and items:
            department = department.strip()
            item_list = [i.strip() for i in items.split(",") if i.strip()]
            save_submission_order(department, item_list)

        return redirect(f"/admin/submission-order?department={department}")

    return render_template(
        "admin_submission_order.html",
        departments=departments,
        selected_department=department,
        current_order=current_order
    )



# -----------------------------
# STUDENT – DEPARTMENT SELECTION
# -----------------------------
@app.route("/select-department")
def select_department():
    if "user" not in session:
        return redirect("/login")

    departments = get_departments()
    return render_template(
        "select_department.html",
        departments=departments
    )


# -----------------------------
# STUDENT – CHECKLIST
# -----------------------------
@app.route("/checklist")
def checklist():
    if "user" not in session:
        return redirect("/login")

    department = request.args.get("department")
    if not department:
        return "Invalid department", 400

    department = department.strip()  # remove extra spaces

    # Fetch admin-defined checklist items
    raw_items = get_checklist_items(department)
    if not raw_items:
        return "No checklist items found for this department", 404

    # Convert to list of item names
    items = [item["item"] for item in raw_items]

    # Load user progress
    progress = load_progress(session["user"], department)

    return render_template(
        "checklist.html",
        department=department,
        items=items,
        progress=progress
    )




@app.route("/save-progress", methods=["POST"])
def save_checklist_progress():
    if "user" not in session:
        return "", 401

    data = request.get_json()
    save_progress(
        session["user"],
        data["department"],
        data["item"],
        data["checked"]
    )
    return "", 204


# -----------------------------
# STUDENT – SUBMISSION ORDER
# -----------------------------
@app.route("/submission-order")
def submission_order():
    if "user" not in session:
        return redirect("/login")

    department = request.args.get("department")
    if not department:
        return redirect("/select-department")

    department = department.strip()
    order = get_submission_order(department)

    return render_template(
        "submission_order.html",
        department=department,
        order=order
    )



# -----------------------------
# DOCUMENT GENERATION
# -----------------------------
@app.route("/generate-document", methods=["GET", "POST"])
def generate_document():
    document = None
    name = ""
    doc_type = ""

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        doc_type = request.form.get("doc_type", "").strip()

        # Validate inputs early to provide user-friendly feedback.
        if not name or not doc_type:
            flash("Please provide your name and select a document type.", "error")
        else:
            # Simple templates
            templates = {
                "Attestation Letter": f"""
LETTER OF ATTESTATION

This is to certify that {name} is a bona fide student
of the University of Nigeria, Nsukka (UNN).

Signed:
____________________
""",
                "Undertaking Letter": f"""
                         LETTER OF UNDERTAKING


       I, {name}, hereby undertake to abide by all rules and regulations governing 
the University of Nigeria, Nsukka. in tryth bbfbf fbfbfbf fbfbfbf fbfbfbfbf fbfbfbfbf bfbfbfbf bfbfbfbfbf fbfbfbfbf fbfbfbfbfb

Signature:
____________________
"""
            }

            document = templates.get(doc_type)
            if not document:
                flash("Selected document type is not available.", "error")

    return render_template(
        "generate_document.html",
        document=document,
        name=name,
        doc_type=doc_type
    )


@app.route("/download-pdf", methods=["POST"])
def download_pdf():
    text = request.form.get("document", "").strip()
    if not text:
        flash("No document available to download yet.", "error")
        return redirect(url_for("generate_document"))

    # Create PDF in memory
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, pageCompression=1)
    _, height = A4

    # Use a text object for smoother rendering of multi-line documents.
    text_object = pdf.beginText(60, height - 50)
    text_object.setLeading(18)
    for line in text.split('\n'):
        text_object.textLine(line.rstrip())

    pdf.drawText(text_object)

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="document.pdf",
        mimetype="application/pdf"
    )


def get_faqs_grouped_by_category():
    all_faqs = get_faqs()
    grouped = {}
    for faq in all_faqs:
        category = faq["category_name"]
        if category not in grouped:
            grouped[category] = []
        grouped[category].append(faq)
    return grouped

@app.route("/admin/faqs", methods=["GET"])
def admin_faqs():
    if "admin" not in session:
        return redirect("/admin/login")

    faqs = get_faqs()
    categories = get_categories()
    return render_template("admin_faqs.html", faqs=faqs, categories=categories)


@app.route("/admin/faqs/add", methods=["GET", "POST"])
def admin_add_faq():
    if "admin" not in session:
        return redirect("/admin/login")

    categories = get_categories()

    if request.method == "POST":
        category_id = request.form.get("category_id")
        question = request.form.get("question")
        answer = request.form.get("answer")

        if category_id and question and answer:
            add_faq(category_id, question, answer)
            return redirect("/admin/faqs")

    return render_template("admin_faq_add.html", categories=categories)


@app.route("/admin/faqs/edit/<int:faq_id>", methods=["GET", "POST"])
def admin_edit_faq(faq_id):
    if "admin" not in session:
        return redirect("/admin/login")

    faq = get_faq_by_id(faq_id)
    categories = get_categories()

    if request.method == "POST":
        category_id = request.form.get("category_id")
        question = request.form.get("question")
        answer = request.form.get("answer")

        if category_id and question and answer:
            update_faq(faq_id, category_id, question, answer)
            return redirect("/admin/faqs")

    return render_template("admin_faq_edit.html", faq=faq, categories=categories)


@app.route("/admin/faqs/delete/<int:faq_id>")
def admin_delete_faq(faq_id):
    if "admin" not in session:
        return redirect("/admin/login")

    delete_faq(faq_id)
    return redirect("/admin/faqs")

@app.route("/faqs")
def faqs():
    grouped_faqs = get_faqs_grouped_by_category()
    return render_template("faqs.html", grouped_faqs=grouped_faqs)

@app.route("/admin/faq-categories", methods=["GET", "POST"])
def admin_faq_categories():
    if request.method == "POST":
        name = request.form.get("name")
        if name:
            add_category(name)
        return redirect("/admin/faq-categories")

    categories = get_categories()
    return render_template("admin_faq_categories.html", categories=categories)

@app.route("/admin/delete-category/<int:category_id>", methods=["POST"])
def delete_category_route(category_id):
    if "admin" not in session:
        flash("Unauthorized access", "error")
        return redirect(url_for("admin_login"))

    delete_category(category_id)
    flash("Category deleted successfully", "success")
    return redirect(url_for("manage_categories"))


@app.route("/admin/add-category", methods=["POST"])
def add_category_route():
    if "admin" not in session:
        flash("Unauthorized access", "error")
        return redirect(url_for("admin_login"))

    name = request.form.get("name", "").strip()

    if not name:
        flash("Category name cannot be empty", "error")
        return redirect(url_for("manage_categories"))

    add_category(name)
    flash("Category added successfully", "success")
    return redirect(url_for("manage_categories"))


@app.route("/admin/update-category/<int:cat_id>", methods=["POST"])
def update_category_route(cat_id):
    if "admin" not in session:
        flash("Unauthorized access", "error")
        return redirect(url_for("admin_login"))

    new_name = request.form.get("name", "").strip()

    if not new_name:
        flash("Category name cannot be empty", "error")
        return redirect(url_for("manage_categories"))

    update_category(cat_id, new_name)
    flash("Category updated successfully", "success")
    return redirect(url_for("manage_categories"))

# -----------------------------
# RUN APP
# -----------------------------
if __name__ == "__main__":
    app.run()


