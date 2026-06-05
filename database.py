"""
database.py — Capa de acceso a datos con PostgreSQL (Supabase).
Soporta múltiples usuarios con autenticación por contraseña.
"""

import bcrypt
import calendar
import os
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()


# ──────────────────────────────────────────────
# Conexión
# ──────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode="require",
    )


# ──────────────────────────────────────────────
# Inicialización / Migraciones
# ──────────────────────────────────────────────

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            SERIAL PRIMARY KEY,
            username      TEXT NOT NULL UNIQUE,
            password_hash TEXT,
            created_at    TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT")

    c.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id      SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name    TEXT NOT NULL,
            type    TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id           SERIAL PRIMARY KEY,
            user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            type         TEXT    NOT NULL,
            amount       NUMERIC NOT NULL,
            category_id  INTEGER REFERENCES categories(id),
            description  TEXT,
            date         DATE    NOT NULL,
            is_recurring BOOLEAN DEFAULT FALSE,
            has_reminder BOOLEAN DEFAULT FALSE,
            reminder_date DATE,
            created_at   TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    c.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS has_reminder  BOOLEAN DEFAULT FALSE")
    c.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS reminder_date DATE")

    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# Usuarios
# ──────────────────────────────────────────────

def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def _verify(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

DEFAULT_CATEGORIES = [
    ("Alimentación",    "expense"), ("Alquiler",     "expense"),
    ("Servicios",       "expense"), ("Transporte",   "expense"),
    ("Salud",           "expense"), ("Educación",    "expense"),
    ("Entretenimiento", "expense"), ("Ropa",         "expense"),
    ("Tecnología",      "expense"), ("Otros Gastos", "expense"),
    ("Sueldo",          "income"),  ("Freelance",    "income"),
    ("Inversiones",     "income"),  ("Otros Ingresos","income"),
]

def _create_default_categories(conn, user_id: int):
    c = conn.cursor()
    for name, cat_type in DEFAULT_CATEGORIES:
        c.execute("INSERT INTO categories (user_id, name, type) VALUES (%s, %s, %s)",
                  (user_id, name, cat_type))

def register_user(username: str, password: str) -> tuple:
    """(user_id, None) o (None, error_str)"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username = %s", (username,))
    if c.fetchone():
        conn.close()
        return None, "El usuario ya existe."
    c.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id",
              (username, _hash(password)))
    user_id = c.fetchone()[0]
    _create_default_categories(conn, user_id)
    conn.commit()
    conn.close()
    return user_id, None

def login_user(username: str, password: str) -> tuple:
    """(user_id, None) o (None, error_str)"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, password_hash FROM users WHERE username = %s", (username,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None, "Usuario no encontrado."
    user_id, pwd_hash = row
    if pwd_hash is None:          # usuario legacy sin contraseña
        return user_id, None
    if not _verify(password, pwd_hash):
        return None, "Contraseña incorrecta."
    return user_id, None

def get_all_users() -> list:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, username FROM users ORDER BY username")
    rows = c.fetchall()
    conn.close()
    return rows


# ──────────────────────────────────────────────
# Categorías
# ──────────────────────────────────────────────

def get_categories(user_id: int, cat_type: str = None) -> list:
    conn = get_conn()
    c = conn.cursor()
    if cat_type:
        c.execute("SELECT id, name FROM categories WHERE user_id=%s AND type=%s ORDER BY name",
                  (user_id, cat_type))
    else:
        c.execute("SELECT id, name, type FROM categories WHERE user_id=%s ORDER BY type, name",
                  (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows


# ──────────────────────────────────────────────
# Transacciones
# ──────────────────────────────────────────────

def _add_months(dt: datetime, n: int) -> datetime:
    month = dt.month - 1 + n
    year  = dt.year + month // 12
    month = month % 12 + 1
    day   = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)

def add_transaction(
    user_id: int, type: str, amount: float, category_id: int,
    description: str, date: str,
    is_recurring: bool = False, recurring_months: int = 0,
    has_reminder: bool = False,
) -> None:
    conn = get_conn()
    c = conn.cursor()

    date_dt      = datetime.strptime(date, "%Y-%m-%d")
    reminder_dt  = (date_dt - timedelta(days=1)).strftime("%Y-%m-%d") if has_reminder else None

    c.execute(
        """INSERT INTO transactions
           (user_id,type,amount,category_id,description,date,is_recurring,has_reminder,reminder_date)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (user_id, type, amount, category_id, description, date, is_recurring, has_reminder, reminder_dt),
    )

    if is_recurring and recurring_months > 0:
        for i in range(1, recurring_months + 1):
            fd  = _add_months(date_dt, i)
            fds = fd.strftime("%Y-%m-%d")
            frd = (fd - timedelta(days=1)).strftime("%Y-%m-%d") if has_reminder else None
            c.execute(
                """INSERT INTO transactions
                   (user_id,type,amount,category_id,description,date,is_recurring,has_reminder,reminder_date)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (user_id, type, amount, category_id, f"{description} (programado)", fds, True, has_reminder, frd),
            )

    conn.commit()
    conn.close()

def delete_transaction(transaction_id: int) -> None:
    conn = get_conn()
    conn.cursor().execute("DELETE FROM transactions WHERE id = %s", (transaction_id,))
    conn.commit()
    conn.close()

def get_transactions(user_id: int, start_date: str = None, end_date: str = None) -> list:
    conn = get_conn()
    c = conn.cursor()
    q = """SELECT t.id, t.type, t.amount, cat.name, t.description,
                  t.date::text, t.is_recurring, t.has_reminder
           FROM transactions t
           LEFT JOIN categories cat ON t.category_id = cat.id
           WHERE t.user_id = %s"""
    p = [user_id]
    if start_date and end_date:
        q += " AND t.date BETWEEN %s AND %s"; p += [start_date, end_date]
    elif start_date:
        q += " AND t.date >= %s"; p.append(start_date)
    q += " ORDER BY t.date DESC"
    c.execute(q, p)
    rows = c.fetchall()
    conn.close()
    return rows

def get_pending_reminders(user_id: int) -> list:
    conn = get_conn()
    c = conn.cursor()
    today    = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    c.execute("""
        SELECT t.description, t.amount, t.date::text, cat.name, t.type
        FROM transactions t
        LEFT JOIN categories cat ON t.category_id = cat.id
        WHERE t.user_id=%s AND t.has_reminder=TRUE
              AND t.reminder_date BETWEEN %s AND %s
        ORDER BY t.date
    """, (user_id, today, tomorrow))
    rows = c.fetchall()
    conn.close()
    return rows


# ──────────────────────────────────────────────
# Resúmenes
# ──────────────────────────────────────────────

def get_monthly_summary(user_id: int) -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT TO_CHAR(date,'YYYY-MM') AS month, type, SUM(amount) AS total "
        "FROM transactions WHERE user_id=%s GROUP BY month,type ORDER BY month",
        conn, params=(user_id,))
    conn.close()
    return df

def get_expenses_by_category(user_id: int, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    conn = get_conn()
    q = ("SELECT cat.name AS category, SUM(t.amount) AS total "
         "FROM transactions t LEFT JOIN categories cat ON t.category_id=cat.id "
         "WHERE t.user_id=%s AND t.type='expense'")
    p = [user_id]
    if start_date and end_date:
        q += " AND t.date BETWEEN %s AND %s"; p += [start_date, end_date]
    q += " GROUP BY cat.name ORDER BY total DESC"
    df = pd.read_sql_query(q, conn, params=p)
    conn.close()
    return df

def get_balance_up_to(user_id: int, date: str) -> float:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT type, COALESCE(SUM(amount),0) FROM transactions "
        "WHERE user_id=%s AND date<=%s GROUP BY type",
        (user_id, date))
    r = dict(c.fetchall())
    conn.close()
    return float(r.get("income", 0)) - float(r.get("expense", 0))

def get_monthly_detail(user_id: int, year_month: str) -> dict:
    """Datos completos de un mes para el reporte.
    Usa una conexión independiente por query para evitar problemas con el pooler."""

    def query(sql, params):
        conn = get_conn()
        c    = conn.cursor()
        c.execute(sql, params)
        rows = c.fetchall()
        conn.close()
        return rows

    def month_totals(ym):
        rows = query(
            "SELECT type, COALESCE(SUM(amount),0) FROM transactions "
            "WHERE user_id=%s AND TO_CHAR(date,'YYYY-MM')=%s GROUP BY type",
            (user_id, ym))
        return dict(rows)

    def month_cats(ym):
        return query(
            "SELECT cat.name, SUM(t.amount) FROM transactions t "
            "LEFT JOIN categories cat ON t.category_id=cat.id "
            "WHERE t.user_id=%s AND TO_CHAR(t.date,'YYYY-MM')=%s AND t.type='expense' "
            "GROUP BY cat.name ORDER BY SUM(t.amount) DESC",
            (user_id, ym))

    t         = month_totals(year_month)
    pt        = month_totals(_prev_month(year_month))
    cats      = month_cats(year_month)
    prev_cats = month_cats(_prev_month(year_month))
    upcoming  = query(
        "SELECT t.description, t.amount, t.date::text, cat.name FROM transactions t "
        "LEFT JOIN categories cat ON t.category_id=cat.id "
        "WHERE t.user_id=%s AND TO_CHAR(t.date,'YYYY-MM')=%s AND t.type='expense' ORDER BY t.date",
        (user_id, _next_month(year_month)))

    inc  = float(t.get("income",  0)); exp  = float(t.get("expense",  0))
    pinc = float(pt.get("income", 0)); pexp = float(pt.get("expense", 0))

    return {
        "year_month":        year_month,
        "income":            inc,  "expense":         exp,
        "balance":           inc - exp,
        "savings_rate":      (inc - exp) / inc * 100 if inc > 0 else 0,
        "categories":        [(r[0], float(r[1])) for r in cats],
        "prev_income":       pinc, "prev_expense":    pexp,
        "prev_balance":      pinc - pexp,
        "prev_savings_rate": (pinc - pexp) / pinc * 100 if pinc > 0 else 0,
        "prev_categories":   [(r[0], float(r[1])) for r in prev_cats],
        "upcoming_payments": [(u[0], float(u[1]), u[2], u[3]) for u in upcoming],
        "surplus":           max(0, inc - exp),
    }

def _prev_month(ym: str) -> str:
    y, m = map(int, ym.split("-"))
    m -= 1
    if m == 0: m, y = 12, y - 1
    return f"{y}-{m:02d}"

def _next_month(ym: str) -> str:
    y, m = map(int, ym.split("-"))
    m += 1
    if m == 13: m, y = 1, y + 1
    return f"{y}-{m:02d}"