
#!/usr/bin/env python3
"""
main.py - Registradora con Tkinter + SQLite
- Ejecutar: python main.py
- La BD se crea en app/database/punto_ventas.db
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
import uuid
import os
from datetime import datetime
from tkinter import filedialog  # si ya lo importaste arriba, no hace falta duplicar

# Requiere: pip install reportlab
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas as pdfcanvas
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

def save_receipt_pdf(sale_id, sale_rows, total, received=None, change=None, company_name="Mi Negocio", filename=None):
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("reportlab no está instalado. pip install reportlab")
    if filename is None:
        filename = f"receipt_{sale_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    c = pdfcanvas.Canvas(filename, pagesize=letter)
    w, h = letter
    x = 40; y = h - 40
    c.setFont("Helvetica-Bold", 12); c.drawString(x, y, company_name); y -= 18
    c.setFont("Helvetica", 9); c.drawString(x, y, f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"); y -= 14
    c.drawString(x, y, f"Venta ID: {sale_id}"); y -= 18
    c.drawString(x, y, "-"*40); y -= 18
    c.drawString(x, y, f"{'Cant':>4} {'Producto':<22} {'Total':>10}"); y -= 14
    c.drawString(x, y, "-"*40); y -= 16
    def fm(x): return f"{int(round(float(x))):,}".replace(",", ".")
    for it in sale_rows:
        qty = int(it.get("qty",0))
        name = it.get("product_name", it.get("name",""))
        subtotal = int(round(float(it.get("subtotal", it.get("price",0) * qty))))
        name_disp = (name[:22] + "...") if len(name) > 22 else name
        c.drawString(x, y, f"{qty:>4} {name_disp:<22} {fm(subtotal):>10}")
        y -= 14
        if y < 60:
            c.showPage(); y = h - 40
    y -= 4
    c.drawString(x, y, "-"*40); y -= 18
    c.drawString(x, y, f"{'TOTAL':>30} ${fm(total)}"); y -= 14
    if received is not None:
        c.drawString(x, y, f"{'RECIBIDO':>30} ${fm(received)}"); y -= 14
    if change is not None:
        c.drawString(x, y, f"{'DEVUELTA':>30} ${fm(change)}"); y -= 14
    y -= 10
    c.drawString(x, y, "Gracias por su compra")
    c.save()
    return filename

# Windows: pip install pywin32
def print_text_file_windows(path):
    try:
        import win32print, win32api
    except Exception:
        raise RuntimeError("pywin32 no instalado (win32print). pip install pywin32")
    win32api.ShellExecute(0, "print", path, None, ".", 0)
    return True

# Unix: lp / lpr
import subprocess
def print_text_file_lp(path):
    try:
        subprocess.run(["lp", path], check=True)
        return True
    except Exception:
        try:
            subprocess.run(["lpr", path], check=True)
            return True
        except Exception as e:
            raise RuntimeError("No se pudo enviar a la cola de impresión (lp/lpr).") from e


# ---------------- CONFIG ----------------
DB_PATH = os.path.join("app", "database", "punto_ventas.db")

# ---------------- DB --------------------
def init_db():
    dirpath = os.path.dirname(DB_PATH)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # activar fk
    c.execute("PRAGMA foreign_keys = ON")

    # categories
    c.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )
    """)

    # products
    c.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        name TEXT,
        price REAL,
        stock INTEGER,
        category_id INTEGER,
        FOREIGN KEY(category_id) REFERENCES categories(id)
    )
    """)
    # --------- tabla suppliers ----------
    c.execute("""
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        tax_id TEXT,           -- NIT / RUT / CIF (opcional)
        contact_person TEXT,
        email TEXT,
        phone TEXT,
        phone2 TEXT,
        address TEXT,
        notes TEXT,
        created_at TEXT
    )
    """)

    # sales and items
    c.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        total REAL
    )
    """)
        # tabla para salidas / gastos
    c.execute("""
    CREATE TABLE IF NOT EXISTS outflows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        amount INTEGER,
        description TEXT
    )
    """)


    c.execute("""
    CREATE TABLE IF NOT EXISTS inventory_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        product_code TEXT,
        product_name TEXT,
        change INTEGER,            -- cantidad añadida (puede ser negativa)
        reason TEXT,
        created_at TEXT,
        FOREIGN KEY(product_id) REFERENCES products(id)
    )
    
    """)



    # --- Tabla de clientes ---
    c.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        document TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        notes TEXT,
        created_at TEXT
    )
    """)

    # --- Créditos / Fiados ---
    c.execute("""
    CREATE TABLE IF NOT EXISTS credits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        reference TEXT,
        description TEXT,
        amount INTEGER NOT NULL DEFAULT 0,
        balance INTEGER NOT NULL DEFAULT 0,
        closed INTEGER NOT NULL DEFAULT 0,
        created_at TEXT,
        due_date TEXT,
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    )
    """)

    # --- Pagos de créditos ---
    c.execute("""
    CREATE TABLE IF NOT EXISTS credit_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        credit_id INTEGER NOT NULL,
        amount INTEGER NOT NULL DEFAULT 0,
        method TEXT,
        note TEXT,
        created_at TEXT,
        FOREIGN KEY (credit_id) REFERENCES credits(id)
    )
    """)

    # --- Deudas / Pasivos ---
    c.execute("""
    CREATE TABLE IF NOT EXISTS debts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        creditor_name TEXT NOT NULL,
        description TEXT,
        amount INTEGER NOT NULL DEFAULT 0,
        balance INTEGER NOT NULL DEFAULT 0,
        closed INTEGER NOT NULL DEFAULT 0,
        created_at TEXT,
        due_date TEXT
    )
    """)

    # --- Pagos de deudas ---
    c.execute("""
    CREATE TABLE IF NOT EXISTS debt_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        debt_id INTEGER NOT NULL,
        amount INTEGER NOT NULL DEFAULT 0,
        method TEXT,
        note TEXT,
        created_at TEXT,
        FOREIGN KEY (debt_id) REFERENCES debts(id)
    )
    """)

    conn.commit()
    



    c.execute("""
    CREATE TABLE IF NOT EXISTS sale_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER,
        product_id INTEGER,
        product_code TEXT,
        product_name TEXT,
        category_id INTEGER,
        qty INTEGER,
        price REAL,
        FOREIGN KEY(sale_id) REFERENCES sales(id)
    )
    """)

    # insertar 10 categorias por defecto si tabla vacía
    c.execute("SELECT COUNT(*) as cnt FROM categories")
    if c.fetchone()["cnt"] == 0:
        defaults = [f"Categoría {i}" for i in range(1, 11)]
        for name in defaults:
            try:
                c.execute("INSERT INTO categories (name) VALUES (?)", (name,))
            except sqlite3.IntegrityError:
                pass
        conn.commit()

    conn.commit()
    return conn

conn = init_db()

# ---------------- DB HELPERS ----------------


 #---------- Clientes (si no existen) ----------
def add_customer_db(data):
    now = datetime.now().isoformat(sep=' ', timespec='seconds')
    c = conn.cursor()
    c.execute("""
        INSERT INTO customers (name, document, phone, email, address, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get('name'),
        data.get('document'),
        data.get('phone'),
        data.get('email'),
        data.get('address'),
        data.get('notes'),
        now
    ))
    conn.commit()
    return c.lastrowid

def update_customer_db(cid, data):
    c = conn.cursor()
    c.execute("""
        UPDATE customers SET name=?, document=?, phone=?, email=?, address=?, notes=? WHERE id=?
    """, (data.get('name'), data.get('document'), data.get('phone'), data.get('email'), data.get('address'), data.get('notes'), cid))
    conn.commit()

def delete_customer_db(cid):
    c = conn.cursor()
    c.execute("DELETE FROM customers WHERE id=?", (cid,))
    conn.commit()

def get_customers_db(q=None, limit=500):
    c = conn.cursor()
    if q:
        like = f"%{q}%"
        c.execute("SELECT id, name, document, phone, email, address, notes, created_at FROM customers WHERE name LIKE ? OR document LIKE ? OR phone LIKE ? ORDER BY id DESC LIMIT ?", (like, like, like, limit))
    else:
        c.execute("SELECT id, name, document, phone, email, address, notes, created_at FROM customers ORDER BY id DESC LIMIT ?", (limit,))
    return c.fetchall()

def get_customer_db(cid):
    c = conn.cursor()
    c.execute("SELECT * FROM customers WHERE id=?", (cid,))
    return c.fetchone()

# ------------------ Créditos (cuentas por cobrar) ------------------
def create_credit(customer_id, amount, reference=None, description=None, due_date=None):
    now = datetime.now().isoformat(sep=' ', timespec='seconds')
    c = conn.cursor()
    c.execute(
        "INSERT INTO credits (customer_id, reference, description, amount, balance, created_at, due_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (customer_id, reference, description, int(amount), int(amount), now, due_date)
    )
    conn.commit()
    return c.lastrowid

def get_credits(q=None, only_open=True, limit=500):
    c = conn.cursor()
    clause = ""
    params = []
    if only_open:
        clause += " WHERE c.closed=0"
    if q:
        like = f"%{q}%"
        if clause:
            clause += " AND (c.reference LIKE ? OR c.description LIKE ? OR cu.name LIKE ?)"
        else:
            clause += " WHERE (c.reference LIKE ? OR c.description LIKE ? OR cu.name LIKE ?)"
        params += [like, like, like]
    sql = f"""
        SELECT c.*, cu.name as customer_name
        FROM credits c
        LEFT JOIN customers cu ON c.customer_id = cu.id
        {clause}
        ORDER BY c.id DESC
        LIMIT ?
    """
    params.append(limit)
    c.execute(sql, params)
    return c.fetchall()

def get_credit(credit_id):
    c = conn.cursor()
    c.execute("SELECT c.*, cu.name as customer_name FROM credits c LEFT JOIN customers cu ON c.customer_id = cu.id WHERE c.id=?", (credit_id,))
    return c.fetchone()

def add_credit_payment(credit_id, amount, method=None, note=None):
    now = datetime.now().isoformat(sep=' ', timespec='seconds')
    c = conn.cursor()
    c.execute("INSERT INTO credit_payments (credit_id, amount, method, note, created_at) VALUES (?, ?, ?, ?, ?)", (credit_id, int(amount), method, note, now))
    c.execute("UPDATE credits SET balance = balance - ? WHERE id=?", (int(amount), credit_id))
    c.execute("UPDATE credits SET closed = 1 WHERE id=? AND balance <= 0", (credit_id,))
    conn.commit()
    return c.lastrowid

def get_credit_payments(credit_id):
    c = conn.cursor()
    c.execute("SELECT * FROM credit_payments WHERE credit_id=? ORDER BY id DESC", (credit_id,))
    return c.fetchall()

# ------------------ Deudas (pasivos) ------------------
def create_debt(creditor_name, amount, description=None, due_date=None):
    now = datetime.now().isoformat(sep=' ', timespec='seconds')
    c = conn.cursor()
    c.execute("INSERT INTO debts (creditor_name, description, amount, balance, created_at, due_date) VALUES (?, ?, ?, ?, ?, ?)",
              (creditor_name, description, int(amount), int(amount), now, due_date))
    conn.commit()
    return c.lastrowid

def get_debts(q=None, only_open=True, limit=500):
    c = conn.cursor()
    clause = ""
    params = []
    if only_open:
        clause += " WHERE closed=0"
    if q:
        like = f"%{q}%"
        if clause:
            clause += " AND (creditor_name LIKE ? OR description LIKE ?)"
        else:
            clause += " WHERE (creditor_name LIKE ? OR description LIKE ?)"
        params += [like, like]
    qsql = f"SELECT * FROM debts {clause} ORDER BY id DESC LIMIT ?"
    params.append(limit)
    c.execute(qsql, params)
    return c.fetchall()

def get_debt(debt_id):
    c = conn.cursor()
    c.execute("SELECT * FROM debts WHERE id=?", (debt_id,))
    return c.fetchone()

def add_debt_payment(debt_id, amount, method=None, note=None):
    now = datetime.now().isoformat(sep=' ', timespec='seconds')
    c = conn.cursor()
    c.execute("INSERT INTO debt_payments (debt_id, amount, method, note, created_at) VALUES (?, ?, ?, ?, ?)", (debt_id, int(amount), method, note, now))
    c.execute("UPDATE debts SET balance = balance - ? WHERE id=?", (int(amount), debt_id))
    c.execute("UPDATE debts SET closed = 1 WHERE id=? AND balance <= 0", (debt_id,))
    conn.commit()
    return c.lastrowid

def get_debt_payments(debt_id):
    c = conn.cursor()
    c.execute("SELECT * FROM debt_payments WHERE debt_id=? ORDER BY id DESC", (debt_id,))
    return c.fetchall()

def add_supplier_db(data):
    """
    data: dict con keys: name, tax_id, contact_person, email, phone, phone2, address, notes
    """
    now = datetime.now().isoformat(sep=' ', timespec='seconds')
    c = conn.cursor()
    c.execute("""
        INSERT INTO suppliers (name, tax_id, contact_person, email, phone, phone2, address, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get('name'),
        data.get('tax_id'),
        data.get('contact_person'),
        data.get('email'),
        data.get('phone'),
        data.get('phone2'),
        data.get('address'),
        data.get('notes'),
        now
    ))
    conn.commit()
    return c.lastrowid

def update_supplier_db(supplier_id, data):
    c = conn.cursor()
    c.execute("""
        UPDATE suppliers SET name=?, tax_id=?, contact_person=?, email=?, phone=?, phone2=?, address=?, notes=?
        WHERE id=?
    """, (
        data.get('name'),
        data.get('tax_id'),
        data.get('contact_person'),
        data.get('email'),
        data.get('phone'),
        data.get('phone2'),
        data.get('address'),
        data.get('notes'),
        supplier_id
    ))
    conn.commit()

def delete_supplier_db(supplier_id):
    c = conn.cursor()
    c.execute("DELETE FROM suppliers WHERE id=?", (supplier_id,))
    conn.commit()

def get_suppliers_db(q=None, limit=500):
    c = conn.cursor()
    if q:
        like = f"%{q}%"
        c.execute("SELECT id, name, tax_id, contact_person, email, phone, phone2, address, notes, created_at FROM suppliers WHERE name LIKE ? OR email LIKE ? OR phone LIKE ? OR tax_id LIKE ? ORDER BY id DESC LIMIT ?",
                  (like, like, like, like, limit))
    else:
        c.execute("SELECT id, name, tax_id, contact_person, email, phone, phone2, address, notes, created_at FROM suppliers ORDER BY id DESC LIMIT ?", (limit,))
    return c.fetchall()

def get_supplier_db(supplier_id):
    c = conn.cursor()
    c.execute("SELECT id, name, tax_id, contact_person, email, phone, phone2, address, notes, created_at FROM suppliers WHERE id=?", (supplier_id,))
    return c.fetchone()

def add_outflow(amount_int, description=""):
    """
    amount_int: entero (ej. 5000)
    description: texto
    """
    c = conn.cursor()
    created_at = datetime.now().isoformat(sep=' ', timespec='seconds')
    c.execute("INSERT INTO outflows (created_at, amount, description) VALUES (?, ?, ?)", (created_at, amount_int, description))
    conn.commit()
    return c.lastrowid

def get_outflows_in_range(start_date=None, end_date=None):
    """
    Devuelve lista de outflows dentro del rango (date strings YYYY-MM-DD) y la suma total.
    """
    c = conn.cursor()
    clause = ""
    params = ()
    if start_date and end_date:
        clause = "WHERE date(created_at) BETWEEN ? AND ?"
        params = (start_date, end_date)
    elif start_date:
        clause = "WHERE date(created_at) >= ?"
        params = (start_date,)
    elif end_date:
        clause = "WHERE date(created_at) <= ?"
        params = (end_date,)

    c.execute(f"SELECT id, created_at, amount, description FROM outflows {clause} ORDER BY id DESC", params)
    rows = c.fetchall()
    c.execute(f"SELECT COALESCE(SUM(amount),0) as total_out FROM outflows {clause}", params)
    total_row = c.fetchone()
    total_out = total_row['total_out'] if total_row else 0
    return rows, total_out


# def generate_receipt_text(sale_id, sale_rows, total, received=None, change=None, company_name="Mi Negocio"):
#     def fm(x):
#         try:
#             return f"{int(round(float(x))):,}".replace(",", ".")
#         except:
#             return str(x)
#     lines = []
#     lines.append(company_name)
#     lines.append(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
#     lines.append(f"Venta ID: {sale_id}")
#     lines.append("-" * 32)
#     lines.append(f"{'Cant':>4} {'Producto':<18} {'Total':>8}")
#     lines.append("-" * 32)
#     for it in sale_rows:
#         qty = int(it.get("qty", 0))
#         name = it.get("product_name", it.get("name",""))
#         subtotal = int(round(float(it.get("subtotal", it.get("price",0) * qty))))
#         name_disp = (name[:16] + "...") if len(name) > 16 else name
#         lines.append(f"{qty:>4} {name_disp:<18} {fm(subtotal):>8}")
#     lines.append("-" * 32)
#     lines.append(f"{'TOTAL':>24} ${fm(total)}")
#     if received is not None:
#         lines.append(f"{'RECIBIDO':>24} ${fm(received)}")
#     if change is not None:
#         lines.append(f"{'DEVUELTA':>24} ${fm(change)}")
#     lines.append("-" * 32)
#     lines.append("Gracias por su compra")
#     return "\n".join(lines)

def save_receipt_text_file(text, filename):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(text)
    return filename

# --- Utilities para dinero ---
def parse_money_to_int(value):
    """Normaliza '7.000', '7000', '7000.00' -> 7000 (int)."""
    try:
        s = str(value).strip()
        s = s.replace("$", "")
        if ',' in s and s.count(',') == 1 and s.count('.') > 0:
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace('.', '').replace(',', '.')
        return int(round(float(s)))
    except Exception:
        return 0

def format_money(value):
    """Formatea entero a '7.000'."""
    try:
        n = int(round(float(value)))
        return f"{n:,}".replace(",", ".")
    except Exception:
        return "0"

# ----------------- Generar texto del recibo -----------------
def generate_receipt_text(sale_id, sale_rows, total, received=None, change=None, company_name="Mi Negocio"):
    """
    sale_rows: lista de dicts con keys:
       product_name, qty, price (int unitario), subtotal (int),
       product_code (opt), category_name (opt)
    total/received/change: enteros
    Devuelve string con el contenido del recibo (formateado).
    """
    def fm(x):
        try:
            return f"{int(round(float(x))):,}".replace(",", ".")
        except:
            return str(x)

    lines = []
    lines.append(company_name)
    lines.append(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Venta ID: {sale_id}")
    lines.append("-" * 64)
    # Encabezado: Cant | Cód. | Producto | Precio unit. | Total
    lines.append(f"{'Cant':>4} {'Cód.':<8} {'Producto':<24} {'P.U.':>10} {'Total':>12}")
    lines.append("-" * 64)

    for it in sale_rows:
        qty = int(it.get("qty", 0))
        name = it.get("product_name", it.get("name",""))
        code = str(it.get("product_code", it.get("code","")) or "")
        unit_price = int(round(float(it.get("price", 0))))
        subtotal = int(round(float(it.get("subtotal", unit_price * qty))))

        # recortar nombre y código si son largos
        name_disp = (name[:24] + "...") if len(name) > 24 else name
        code_disp = (code[:8]) if len(code) > 8 else code

        lines.append(f"{qty:>4} {code_disp:<8} {name_disp:<24} {fm(unit_price):>10} {fm(subtotal):>12}")

    lines.append("-" * 64)
    lines.append(f"{'TOTAL':>52} ${fm(total)}")
    if received is not None:
        lines.append(f"{'RECIBIDO':>52} ${fm(received)}")
    if change is not None:
        lines.append(f"{'DEVUELTA':>52} ${fm(change)}")
    lines.append("-" * 64)
    lines.append("Gracias por su compra")
    return "\n".join(lines) 

    """
    sale_rows: lista de dicts con keys: product_name, qty, price (int), subtotal (int), category_name (opt)
    total/received/change: enteros
    Devuelve string con el contenido del recibo (formateado).
    """
    def fm(x):
        try:
            return f"{int(round(float(x))):,}".replace(",", ".")
        except:
            return str(x)

    lines = []
    lines.append(company_name)
    lines.append(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Venta ID: {sale_id}")
    lines.append("-" * 32)
    lines.append(f"{'Cant':>4} {'Producto':<18} {'Total':>8}")
    lines.append("-" * 32)
    for it in sale_rows:
        qty = int(it.get("qty", 0))
        name = it.get("product_name", it.get("name",""))
        subtotal = int(round(float(it.get("subtotal", it.get("price",0) * qty))))
        # recortar nombre si es muy largo
        name_disp = (name[:16] + "...") if len(name) > 16 else name
        lines.append(f"{qty:>4} {name_disp:<18} {fm(subtotal):>8}")
    lines.append("-" * 32)
    lines.append(f"{'TOTAL':>24} ${fm(total)}")
    if received is not None:
        lines.append(f"{'RECIBIDO':>24} ${fm(received)}")
    if change is not None:
        lines.append(f"{'DEVUELTA':>24} ${fm(change)}")
    lines.append("-" * 32)
    lines.append("Gracias por su compra")
    return "\n".join(lines)

# ----------------- Guardar recibo como .txt -----------------
def save_receipt_text_file(text, filename):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(text)
    return filename

# ----------------- Generar PDF (si reportlab está instalado) -----------------
def save_receipt_pdf(sale_id, sale_rows, total, received=None, change=None, company_name="Mi Negocio", filename=None):
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("reportlab no está instalado. pip install reportlab")
    if filename is None:
        filename = f"receipt_{sale_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    # elegir tamaño A4 pequeño
    c = pdfcanvas.Canvas(filename, pagesize=letter)
    w, h = letter
    x = 40
    y = h - 40
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x, y, company_name)
    y -= 18
    c.setFont("Helvetica", 9)
    c.drawString(x, y, f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    y -= 14
    c.drawString(x, y, f"Venta ID: {sale_id}")
    y -= 18
    c.drawString(x, y, "-"*40)
    y -= 18
    c.drawString(x, y, f"{'Cant':>4} {'Producto':<22} {'Total':>10}")
    y -= 14
    c.drawString(x, y, "-"*40)
    y -= 16
    def fm(x): return f"{int(round(float(x))):,}".replace(",", ".")
    for it in sale_rows:
        qty = int(it.get("qty",0))
        name = it.get("product_name", it.get("name",""))
        subtotal = int(round(float(it.get("subtotal", it.get("price",0) * qty))))
        name_disp = (name[:22] + "...") if len(name) > 22 else name
        c.drawString(x, y, f"{qty:>4} {name_disp:<22} {fm(subtotal):>10}")
        y -= 14
        if y < 60:
            c.showPage()
            y = h - 40
    y -= 4
    c.drawString(x, y, "-"*40)
    y -= 18
    c.drawString(x, y, f"{'TOTAL':>30} ${fm(total)}")
    y -= 14
    if received is not None:
        c.drawString(x, y, f"{'RECIBIDO':>30} ${fm(received)}")
        y -= 14
    if change is not None:
        c.drawString(x, y, f"{'DEVUELTA':>30} ${fm(change)}")
        y -= 14
    y -= 10
    c.drawString(x, y, "Gracias por su compra")
    c.save()
    return filename

# ----------------- Enviar a impresora (Windows: win32print) -----------------
def print_text_file_windows(path):
    try:
        import win32print
        import win32api
    except Exception as e:
        raise RuntimeError("pywin32 no instalado (win32print). pip install pywin32") from e
    # impresora por defecto
    printer_name = win32print.GetDefaultPrinter()
    # usar ShellExecute para imprimir el archivo con la aplicación por defecto
    # esto funciona con .txt/.pdf si hay asociación de impresión
    win32api.ShellExecute(0, "print", path, None, ".", 0)
    return True

# ----------------- Enviar a impresora (Linux/macOS) usando lpr/lp -----------------
import subprocess
def print_text_file_lp(path):
    # intenta enviar con lp o lpr
    try:
        subprocess.run(["lp", path], check=True)
        return True
    except Exception:
        try:
            subprocess.run(["lpr", path], check=True)
            return True
        except Exception as e:
            raise RuntimeError("No se pudo enviar a la cola de impresión (lpr/lp).") from e

# ----------------- Impresión ESC/POS (impresora térmica) - opcional -----------------
def print_escpos(text, device=None):
    """
    Requiere python-escpos. device puede ser dict con parámetros de conexión (usb/network).
    Ejemplo básico (USB):
      from escpos.printer import Usb
      p = Usb(0x04b8, 0x0202)  # vendor/product id
      p.text(text)
      p.cut()
    Aquí solo devolvemos el texto o levantamos error si no hay lib.
    """
    try:
        from escpos import printer as escprinter
    except Exception as e:
        raise RuntimeError("python-escpos no instalado (pip install python-escpos)") from e
    # el uso depende del tipo de impresora; fuera del alcance general — el desarrollador debe adaptarlo.
    raise NotImplementedError("Implementa la conexión ESC/POS según tu impresora (usb/ip) usando python-escpos.")

def parse_money_to_int(value):
    s = str(value).strip()
    s = s.replace("$", "").replace(".", "").replace(",", ".")
    try:
        return int(round(float(s)))
    except:
        return 0

def format_money(value):
    try:
        value = float(str(value).replace(".", "").replace(",", "."))
        return f"{int(value):,}".replace(",", ".")
    except:
        return str(value)
        
def generate_unique_code():
    c = conn.cursor()
    while True:
        code = uuid.uuid4().hex[:8].upper()
        c.execute("SELECT 1 FROM products WHERE code=?", (code,))
        if not c.fetchone():
            return code

def add_category(name):
    try:
        c = conn.cursor()
        c.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def delete_category(cid):
    c = conn.cursor()
    c.execute("DELETE FROM categories WHERE id=?", (cid,))
    conn.commit()

def get_categories():
    c = conn.cursor()
    c.execute("SELECT id, name FROM categories ORDER BY id ASC")
    return c.fetchall()

def add_product(name, price, stock, category_id=None, code=None):
    if code is None:
        code = generate_unique_code()
    try:
        c = conn.cursor()
        c.execute(
            "INSERT INTO products (code, name, price, stock, category_id) VALUES (?, ?, ?, ?, ?)",
            (code, name, price, stock, category_id)
        )
        conn.commit()
        return True, code
    except sqlite3.IntegrityError as e:
        return False, str(e)

def update_product_category(product_id, category_id):
    c = conn.cursor()
    c.execute("UPDATE products SET category_id=? WHERE id=?", (category_id, product_id))
    conn.commit()

def get_all_products(filter_text=None):
    c = conn.cursor()
    if filter_text:
        like = f"%{filter_text}%"
        c.execute("SELECT id, code, name, price, stock, category_id FROM products WHERE name LIKE ? OR code LIKE ? ORDER BY id DESC", (like, like))
    else:
        c.execute("SELECT id, code, name, price, stock, category_id FROM products ORDER BY id DESC")
    return c.fetchall()

def get_product_by_id(pid):
    c = conn.cursor()
    c.execute("SELECT id, code, name, price, stock, category_id FROM products WHERE id=?", (pid,))
    return c.fetchone()

def get_product_by_code(code):
    c = conn.cursor()
    c.execute("SELECT id, code, name, price, category FROM products WHERE code=?", (code,))
    return c.fetchone()

def save_sale(cart_items):
    """
    Guarda la venta y actualiza stock.
    Ahora soporta cart_items que tengan 'product_id' = None (artículos manuales).
    cart_items: lista de dicts con keys: product_id (o None), code, name, price, qty, category_id
    """
    c = conn.cursor()

    # Validar existencia de producto SOLO para ítems que tengan product_id
    for it in cart_items:
        pid = it.get('product_id')
        qty = int(it.get('qty', 0))
        if qty < 0:
            raise ValueError(f"Cantidad inválida para {it.get('name','?')}: {qty}")

        if pid is not None:
            c.execute("SELECT stock, name FROM products WHERE id=?", (pid,))
            row = c.fetchone()
            if not row:
                raise ValueError(f"Producto no encontrado (id={pid})")
            # No bloqueamos la venta por stock; permitimos stock negativo.
            # Si quisieras advertir aquí, podrías hacerlo.

    # Guardar venta
    total = sum(int(it['qty']) * int(round(float(it['price']))) for it in cart_items)
    created_at = datetime.now().isoformat(sep=' ', timespec='seconds')
    c.execute("INSERT INTO sales (created_at, total) VALUES (?, ?)", (created_at, total))
    sale_id = c.lastrowid

    for it in cart_items:
        pid = it.get('product_id')
        qty = int(it.get('qty', 0))
        price = int(round(float(it.get('price', 0))))
        # permitimos product_id NULL en la inserción
        c.execute(
            "INSERT INTO sale_items (sale_id, product_id, product_code, product_name, category_id, qty, price) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sale_id, pid, it.get('code'), it.get('name'), it.get('category_id'), qty, price)
        )
        # disminuir stock SOLO si product_id existe (productos reales)
        if pid is not None:
            c.execute("UPDATE products SET stock = stock - ? WHERE id=?", (qty, pid))

    conn.commit()
    return sale_id






def get_sales_recent(limit=100):
    c = conn.cursor()
    c.execute("SELECT id, created_at, total FROM sales ORDER BY id DESC LIMIT ?", (limit,))
    return c.fetchall()

def get_sale_items(sale_id):
    c = conn.cursor()
    c.execute("SELECT product_name, qty, price, category_id FROM sale_items WHERE sale_id=?", (sale_id,))
    return c.fetchall()

def get_category_name(cid):
    if cid is None:
        return "Sin categoría"
    c = conn.cursor()
    c.execute("SELECT name FROM categories WHERE id=?", (cid,))
    r = c.fetchone()
    return r['name'] if r else f"Categoría {cid}"

# ---------------- CART ITEM ----------------
class CartItem:
    def __init__(self, product_id, code, name, price, qty, category_id):
        self.product_id = product_id
        self.code = code
        self.name = name
        self.price = price
        self.qty = qty
        self.category_id = category_id
    def total(self):
        return self.price * self.qty

# ---------------- APP ----------------
class POSApp:
    def __init__(self, master):
        self.master = master
        self.root = master
        self.root.title("Registradora - POS")
        self.root.geometry("1024x600")

        # ===================== NAVBAR SUPERIOR =====================
        navbar = ttk.Frame(self.root, padding=6, )
        navbar.pack(side=tk.TOP, fill=tk.X)

       
    #    navbar.configure(style="Nav.TFrame")
    #    style = ttk.Style()
    #    style.configure("Nav.TFrame", background="#2b2b2b")
    #    style.configure("Nav.TButton", background="#444", foreground="white", font=("Segoe UI", 10, "bold"))
    #    style.map("Nav.TButton", background=[("active", "#666")])
    # ttk.Button(navbar, text="🏠 Inicio", style="Nav.TButton", command=self.refresh_cart).pack(side=tk.LEFT, padx=4)
# 
       

        
        # Grupo 1 - Operaciones
        # ttk.Button(navbar, text="🏠 Inicio", command=self.refresh_cart).pack(side=tk.LEFT, padx=4)
        # ttk.Button(navbar, text="🛒 Caja / Venta", command=self.checkout).pack(side=tk.LEFT, padx=4)
        ttk.Button(navbar, text="✍️ Registrar manual", command=self.open_calculator_mode).pack(side=tk.LEFT, padx=4)
        ttk.Button(navbar, text="📦 Productos", command=self.open_add_product_window).pack(side=tk.LEFT, padx=4)
        ttk.Button(navbar, text="💰 Créditos", command=self.open_credits_window).pack(side=tk.LEFT, padx=4)
        ttk.Button(navbar, text="📉 Pasivos", command=self.open_debts_window).pack(side=tk.LEFT, padx=4)
        ttk.Button(navbar, text="💸 Gastos", command=self.open_outflow_dialog).pack(side=tk.LEFT, padx=4)
        
        # Separador visual
        ttk.Separator(navbar, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=8)
        
        # Grupo 2 - Gestión / Administración
        ttk.Button(navbar, text="📊 Estadísticas", command=self.open_stats_window).pack(side=tk.LEFT, padx=4)

        ttk.Button(navbar, text="🏭 Proveedores", command=self.open_suppliers_window).pack(side=tk.LEFT, padx=4)
        ttk.Button(navbar, text="👥 Clientes", command=self.open_customer_window).pack(side=tk.LEFT, padx=4)
        ttk.Button(navbar, text="🗂️ Categorías",  command=self.manage_categories_window).pack(side=tk.LEFT, padx=4)
        ttk.Button(navbar, text="🧾 Historial", command=self.open_history_window).pack(side=tk.LEFT, padx=4)
        
        # Separador final y botón de salida
        ttk.Separator(navbar, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(navbar, text="🚪 Salir", command=self.root.destroy).pack(side=tk.RIGHT, padx=6)
        # ===========================================================
     # ttk.Button(actions_frame, text="ESTADISTICAS", command=self.open_stats_window).pack(side=tk.LEFT, padx=4)
        # ttk.Button(actions_frame, text="ADMINISTRAR CATEGORIAS", command=self.manage_categories_window).pack(side=tk.LEFT, padx=4)
        # ttk.Button(actions_frame, text="INVENTARIO", command=self.open_inventory_mode).pack(side=tk.LEFT, padx=4)
        # ttk.Button(actions_frame, text="PROVEEDORES", command=self.open_suppliers_window).pack(side=tk.LEFT, padx=4)
        # ttk.Button(actions_frame, text="INGRESO MANUAL", command=self.open_calculator_mode).pack(side=tk.LEFT, padx=4)
        # ttk.Button(actions_frame, text="HISTORIAL", command=self.open_history_window).pack(side=tk.LEFT, padx=4)
        # ttk.Button(actions_frame, text="AGREGAR UN PRODUCTO", command=self.open_add_product_window).pack(side=tk.LEFT, padx=4)
        # ttk.Button(actions_frame, text="GASTOS", command=self.open_outflow_dialog).pack(side=tk.LEFT, padx=4)
        # ttk.Button(actions_frame, text="Créditos / Fiados", command=self.open_credits_window).pack(side=tk.LEFT, padx=4)
        # ttk.Button(actions_frame, text="Deudas / Pasivos", command=self.open_debts_window).pack(side=tk.LEFT, padx=4)

        # track open windows to avoid duplicates
        self.open_windows = {}
        # cart
        self.cart = {}

        # layout: left categories, center products, right cart
        left = ttk.Frame(self.root, padding=6)
        left.pack(side=tk.LEFT, fill=tk.Y)
        center = ttk.Frame(self.root, padding=6)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right = ttk.Frame(self.root, padding=6)
        right.pack(side=tk.RIGHT, fill=tk.Y)


        

        # left: categories
        ttk.Label(left, text="", font=(None, 12, 'bold')).pack(pady=(0,8))
        self.cat_frame = ttk.Frame(left)
        self.cat_frame.pack()


        # ttk.Button(left, text="INGRESO MANUAL", command=self.open_calculator_mode).pack(fill=tk.X, pady=6)

        # ttk.Button(left, text="HISTORIAL", command=self.open_history_window).pack(fill=tk.X, pady=6)
        # ttk.Button(left, text="AGREGAR UN PRODUCTO", command=self.open_add_product_window).pack(fill=tk.X, pady=6)
        # ttk.Button(left, text="GASTOS", command=self.open_outflow_dialog).pack(fill=tk.X, pady=6)

        # ttk.Button(left, text="Créditos / Fiados", command=self.open_credits_window).pack(fill=tk.X, pady=6)
        # ttk.Button(left, text="Deudas / Pasivos", command=self.open_debts_window).pack(fill=tk.X, pady=6)






        

        self.reload_category_buttons()

        # center: buscador y lista
        ttk.Label(center, text="Variedades Sembrador", font=(None, 12, 'bold')).pack(anchor=tk.W)
        sf = ttk.Frame(center)
        sf.pack(fill=tk.X, pady=6)
        ttk.Label(sf, text="Buscar:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(sf, textvariable=self.search_var)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        self.search_entry.bind('<Return>', lambda e: self.load_products())
        self.search_var.trace_add('write', lambda *args: self.load_products())

        # Si presionas Down estando en el entry, pasar foco al tree y seleccionar primer elemento
        self.search_entry.bind('<Down>', lambda e: (
            (self.products_tree.focus_set() or True) and
            (self.tree_move(self.products_tree, 1))
        ))




        # Enter también ejecutará la búsqueda (opcional)
        self.search_entry.bind('<Return>', lambda e: self.load_products())
        ttk.Button(sf, text="Buscar", command=self.load_products).pack(side=tk.LEFT, padx=4)
        ttk.Button(sf, text="Refrescar", command=lambda: self.load_products("")).pack(side=tk.LEFT)
        
        


        #---------------------------------------------------------------------------------------- columnas
        cols = ("id","Codigo","Articulo","Precio","stock","Categoria")
        self.products_tree = ttk.Treeview(center, columns=cols, show='headings', height=10)
        for c in cols:
            self.products_tree.heading(c, text=c.capitalize())
        self.products_tree.column('id', width=5, anchor=tk.CENTER)
        self.products_tree.column('Codigo', width=50, anchor=tk.CENTER)
        self.products_tree.column('Articulo', width=90, anchor=tk.CENTER)
        self.products_tree.column('Precio', width=50, anchor=tk.E)
        self.products_tree.column('stock', width=20, anchor=tk.E)
        self.products_tree.column('Categoria', width=50, anchor=tk.CENTER)
        self.products_tree.pack(fill=tk.BOTH, expand=True)
        self.products_tree.bind('<Double-1>', self.on_product_double)
        # bind Enter key on products tree
        self.products_tree.bind('<Return>', self.on_product_enter)


        self.products_tree.bind('<Double-1>', self.on_product_double)
        self.products_tree.bind('<Return>', self.on_product_enter)
        self.products_tree.bind('<Down>', lambda e: self.tree_move(self.products_tree, 1))
        self.products_tree.bind('<Up>',   lambda e: self.tree_move(self.products_tree, -1))


        self.load_products()
        
                # ejemplo: un frame de acciones
        actions_frame = ttk.Frame(center)  # donde esté tu products_tree
        actions_frame.pack(fill=tk.X, padx=8, pady=(4,8))
        ttk.Button(actions_frame, text="Editar producto", command=lambda: self._edit_selected_product()).pack(side=tk.LEFT, padx=4)
        ttk.Button(actions_frame, text="Eliminar producto", command=lambda: self._delete_selected_product()).pack(side=tk.LEFT, padx=4)
        
        # ttk.Button(actions_frame, text="ESTADISTICAS", command=self.open_stats_window).pack(side=tk.LEFT, padx=4)
        # ttk.Button(actions_frame, text="ADMINISTRAR CATEGORIAS", command=self.manage_categories_window).pack(side=tk.LEFT, padx=4)
        # ttk.Button(actions_frame, text="INVENTARIO", command=self.open_inventory_mode).pack(side=tk.LEFT, padx=4)
        # ttk.Button(actions_frame, text="PROVEEDORES", command=self.open_suppliers_window).pack(side=tk.LEFT, padx=4)
        # ttk.Button(actions_frame, text="INGRESO MANUAL", command=self.open_calculator_mode).pack(side=tk.LEFT, padx=4)
        # ttk.Button(actions_frame, text="HISTORIAL", command=self.open_history_window).pack(side=tk.LEFT, padx=4)
        # ttk.Button(actions_frame, text="AGREGAR UN PRODUCTO", command=self.open_add_product_window).pack(side=tk.LEFT, padx=4)
        # ttk.Button(actions_frame, text="GASTOS", command=self.open_outflow_dialog).pack(side=tk.LEFT, padx=4)
        # ttk.Button(actions_frame, text="Créditos / Fiados", command=self.open_credits_window).pack(side=tk.LEFT, padx=4)
        # ttk.Button(actions_frame, text="Deudas / Pasivos", command=self.open_debts_window).pack(side=tk.LEFT, padx=4)
        
        
        # ejemplo: un frame de acciones
        actions_frame = ttk.Frame(center)  # donde esté tu products_tree
        actions_frame.pack(fill=tk.X, padx=8, pady=(4,8))

        
        # menú contextual para editar/eliminar producto
        self._prod_menu = tk.Menu(self.root, tearoff=0)
        self._prod_menu.add_command(label="Editar producto", command=lambda: None)   # reemplazado al mostrar
        self._prod_menu.add_command(label="Eliminar producto", command=lambda: None)

        
        
        def on_products_right_click(event):
            iid = self.products_tree.identify_row(event.y)
            if not iid:
                return
            self.products_tree.selection_set(iid)
            vals = self.products_tree.item(iid, 'values')
            pid = int(vals[0])
            # actualizar comandos con el id seleccionado
            self._prod_menu.entryconfigure(0, command=lambda pid=pid: self.open_edit_product_window(pid))
            self._prod_menu.entryconfigure(1, command=lambda pid=pid: self.delete_product(pid))
            try:
                self._prod_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self._prod_menu.grab_release()
        
        # enlazar click derecho y tecla Supr
        self.products_tree.bind("<Button-3>", on_products_right_click)   # click derecho
        self.products_tree.bind("<Delete>", lambda e: (lambda sel=self.products_tree.selection(): self.delete_product(int(self.products_tree.item(sel[0],'values')[0])) if sel else None)())



        
        

        # right: cart
        ttk.Label(right, text="Carrito", font=(None, 12, 'bold')).pack()
        self.cart_listbox = tk.Listbox(right, width=80, height=24)
        self.cart_listbox.pack(pady=6)
        ttk.Button(right, text="Eliminar seleccionado", command=self.remove_selected_cart_item).pack(fill=tk.X, pady=3)
        ttk.Button(right, text="Vaciar carrito", command=self.clear_cart).pack(fill=tk.X, pady=3)
        self.total_var = tk.StringVar(value="Total: $0")
        ttk.Label(right, textvariable=self.total_var, font=(None, 11, 'bold')).pack(pady=6)
        ttk.Button(right, text="Finalizar venta (Ctrl+Enter)", command=self.checkout).pack(fill=tk.X, pady=3)
        

        # global bindings
        self.root.bind('<Control-Return>', lambda e: self.checkout())
        self.root.bind('<Escape>', lambda e: self.close_active_window())
    def load_categories(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, name FROM categories ORDER BY id ASC")
        rows = c.fetchall()
        conn.close()
        return rows


    def open_calculator_mode(self):
        """
        Modo calculadora: agregar items por precio y categoría (sin producto).
        Se añaden al carrito como items con product_id = None.
        """
        # ventana única
        def creator():
            win = tk.Toplevel(self.root)
            win.title("Modo Calculadora")
            win.geometry("720x420")
            win.transient(self.root)
    
            topf = ttk.Frame(win, padding=8); topf.pack(fill=tk.X)
            ttk.Label(topf, text="Precio (ej. 7.000):").grid(row=0, column=0, sticky=tk.W)
            price_var = tk.StringVar()
            price_entry = ttk.Entry(topf, textvariable=price_var); price_entry.grid(row=0, column=1, sticky=tk.EW, padx=6)
            topf.columnconfigure(1, weight=1)
    
            ttk.Label(topf, text="Cantidad:").grid(row=1, column=0, sticky=tk.W, pady=(6,0))
            qty_var = tk.IntVar(value=1)
            qty_spin = ttk.Spinbox(topf, from_=1, to=9999, textvariable=qty_var, width=8); qty_spin.grid(row=1, column=1, sticky=tk.W, padx=6, pady=(6,0))
    
            ttk.Label(topf, text="Categoría:").grid(row=2, column=0, sticky=tk.W, pady=(6,0))
            cats = [f"{cid} - {name}" for cid, name in get_categories()]
            cat_var = tk.StringVar(value=cats[0] if cats else "0 - Ninguna")
            cat_combo = ttk.Combobox(topf, values=cats, textvariable=cat_var, state='readonly')
            cat_combo.grid(row=2, column=1, sticky=tk.EW, padx=6, pady=(6,0))
    
            # listbox de items temporales en esta sesión
            midf = ttk.Frame(win, padding=8); midf.pack(fill=tk.BOTH, expand=True)
            ttk.Label(midf, text="Items (calculadora) agregados:").pack(anchor=tk.W)
            calc_tree = ttk.Treeview(midf, columns=('desc','qty','price','subtotal','cat'), show='headings', height=8)
            calc_tree.heading('desc', text='Descripción')
            calc_tree.heading('qty', text='Cant.')
            calc_tree.heading('price', text='Precio')
            calc_tree.heading('subtotal', text='Subtotal')
            calc_tree.heading('cat', text='Categoría')
            calc_tree.column('desc', width=180)
            calc_tree.column('qty', width=60, anchor=tk.E)
            calc_tree.column('price', width=100, anchor=tk.E)
            calc_tree.column('subtotal', width=110, anchor=tk.E)
            calc_tree.column('cat', width=120)
            calc_tree.pack(fill=tk.BOTH, expand=True, pady=(6,0))
    
            # footer: subtotal y botones
            foot = ttk.Frame(win, padding=8); foot.pack(fill=tk.X)
            total_var = tk.StringVar(value="Total: $0")
            ttk.Label(foot, textvariable=total_var, font=(None, 11, 'bold')).pack(side=tk.LEFT)
    
            def parse_price_to_int(s):
                return parse_money_to_int(s)
    
            calc_items = []  # lista de dicts temporales: name, price, qty, category_id
    
            def refresh_calc_list():
                # recarga tree y total
                for i in calc_tree.get_children(): calc_tree.delete(i)
                total = 0
                for idx, it in enumerate(calc_items):
                    subtotal = int(it['price']) * int(it['qty'])
                    total += subtotal
                    catname = get_category_name(it.get('category_id'))
                    desc = it.get('name') or f"Item {idx+1}"
                    calc_tree.insert('', tk.END, values=(desc, it['qty'], f"${format_money(it['price'])}", f"${format_money(subtotal)}", catname))
                total_var.set(f"Total: ${format_money(total)}")
    
            def add_calc_item(_ev=None):
                # leer y validar
                raw_price = price_var.get().strip()
                price_int = parse_price_to_int(raw_price)
                if price_int <= 0:
                    messagebox.showwarning("Precio inválido", "Ingresa un precio válido (>0)")
                    return
                qty = int(qty_var.get() or 1)
                sel = cat_var.get() or ""
                try:
                    cid = int(sel.split(' - ')[0])
                except:
                    cid = None
                name = f"Item manual"
                # crear item temporal
                it = {"product_id": None, "code": f"CALC-{uuid.uuid4().hex[:6].upper()}", "name": name, "price": price_int, "qty": qty, "category_id": cid}
                calc_items.append(it)
                refresh_calc_list()
                # opcional: añadir directamente al carrito (si quieres que se agregue al carrito ya)
                # self.add_to_cart(it['product_id'], it['code'], it['name'], it['price'], it['qty'], category_id=cid)
                # pero preferimos que el cajero agregue al carrito desde acá con botón "Agregar al carrito"
                price_var.set("")
                qty_var.set(1)
                price_entry.focus_set()
    
            def add_all_to_cart():
                # pasar todos los calc_items al carrito como items sueltos (product_id None)
                for it in calc_items:
                    # En CartItem aceptamos product_id None; CartItem initializer casts to int -> avoid that:
                    # Usaremos add_to_cart with code/name/price/qty and set product_id=None by creating a CartItem-like entry manually.
                    # Implement by adding to self.cart with unique key (code)
                    code = it['code']
                    # if already in cart, sum quantities
                    if code in self.cart:
                        self.cart[code].qty += int(it['qty'])
                    else:
                        # create lightweight object similar to CartItem but allowing product_id None
                        # reemplaza la creación anterior de SimpleItem por esto (dentro de add_all_to_cart)
                        class SimpleItem:
                            def __init__(self, product_id, code, name, price, qty, category_id):
                                self.product_id = product_id
                                self.code = code
                                self.name = name
                                self.price = int(price)
                                self.qty = int(qty)
                                self.category_id = category_id
                            def total(self):
                                return int(self.price) * int(self.qty)
                        
                        # luego, en el loop:
                        si = SimpleItem(None, code, it['name'], it['price'], it['qty'], it.get('category_id'))
                        self.cart[code] = si
                        
                self.refresh_cart()
                try:
                    self.update_category_buttons_state()
                except:
                    pass
                # limpiar lista calculadora
                # calc_items.clear()
                # refresh_calc_list()
                # reemplaza la creación anterior de SimpleItem por esto (dentro de add_all_to_cart)
                # reemplaza la creación anterior de SimpleItem por esto (dentro de add_all_to_cart)
                class SimpleItem:
                    def __init__(self, product_id, code, name, price, qty, category_id):
                        self.product_id = product_id
                        self.code = code
                        self.name = name
                        self.price = int(price)
                        self.qty = int(qty)
                        self.category_id = category_id
                    def total(self):
                        return int(self.price) * int(self.qty)
                
                # luego, en el loop:
                si = SimpleItem(None, code, it['name'], it['price'], it['qty'], it.get('category_id'))
                self.cart[code] = si
                
                
                
    
            def finalize_from_calc():
                # añadir al carrito y abrir el checkout (o directamente finalizar)
                add_all_to_cart()
                # abrir checkout (usa tu checkout principal)
                self.checkout()
                # cerrar ventana de calculadora
                try: win.destroy()
                except: pass
    
            # botones
            bframe = ttk.Frame(foot); bframe.pack(side=tk.RIGHT)
            ttk.Button(bframe, text="Agregar item", command=add_calc_item).pack(side=tk.LEFT, padx=4)
            ttk.Button(bframe, text="Agregar todo al carrito", command=add_all_to_cart).pack(side=tk.LEFT, padx=4)
            ttk.Button(bframe, text="Finalizar (ir a cobro)", command=finalize_from_calc).pack(side=tk.LEFT, padx=4)
            ttk.Button(bframe, text="Cerrar", command=win.destroy).pack(side=tk.LEFT, padx=4)
    
            # Bindings: Enter en price añade item rápido
            price_entry.bind("<Return>", add_calc_item)
            win.bind("<Escape>", lambda e: win.destroy())
    
            # enfoque inicial
            price_entry.focus_set()
            refresh_calc_list()
            return win
    
        return self.open_window_once("calculator_mode", creator)



    def open_suppliers_window(self):
        """
        CRUD de proveedores: buscar, agregar, editar, eliminar.
        """
        def creator():
            win = tk.Toplevel(self.root)
            win.title("Proveedores")
            win.geometry("1200x520")
            win.transient(self.root)
    
            top = ttk.Frame(win, padding=8); top.pack(fill=tk.X)
            ttk.Label(top, text="Buscar (nombre / email / teléfono / NIT):").pack(side=tk.LEFT)
            search_var = tk.StringVar()
            search_entry = ttk.Entry(top, textvariable=search_var, width=36)
            search_entry.pack(side=tk.LEFT, padx=(6,8))
            def do_search(_ev=None):
                q = search_var.get().strip()
                load_list(q)
            ttk.Button(top, text="Buscar", command=do_search).pack(side=tk.LEFT)
            ttk.Button(top, text="Mostrar todo", command=lambda: (search_var.set(""), load_list(None))).pack(side=tk.LEFT, padx=6)
            search_entry.bind("<Return>", do_search)
    
            # left: lista de proveedores
            left = ttk.Frame(win, padding=8); left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            cols = ("id","name","tax_id","contact","email","phone")
            tree = ttk.Treeview(left, columns=cols, show='headings', height=20)
            for c in cols:
                tree.heading(c, text=c.capitalize())
            tree.column("id", width=10, anchor=tk.CENTER)
            tree.column("name", width=220)
            tree.column("tax_id", width=100)
            tree.column("contact", width=140)
            tree.column("email", width=180)
            tree.column("phone", width=120)
            tree.pack(fill=tk.BOTH, expand=True)
    
            # right: detalle / acciones
            right = ttk.Frame(win, padding=8); right.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
            ttk.Label(right, text="Detalle proveedor", font=(None, 11, "bold")).pack(anchor=tk.W)
            detailf = ttk.Frame(right); detailf.pack(fill=tk.X, pady=(6,0))
            ttk.Label(detailf, text="Nombre:").grid(row=0, column=0, sticky=tk.W, pady=2)
            name_var = tk.StringVar(); name_e = ttk.Entry(detailf, textvariable=name_var, width=36); name_e.grid(row=0, column=1, pady=2)
    
            ttk.Label(detailf, text="NIT / Tax ID:").grid(row=1, column=0, sticky=tk.W, pady=2)
            tax_var = tk.StringVar(); tax_e = ttk.Entry(detailf, textvariable=tax_var); tax_e.grid(row=1, column=1, pady=2)
    
            ttk.Label(detailf, text="Contacto:").grid(row=2, column=0, sticky=tk.W, pady=2)
            contact_var = tk.StringVar(); contact_e = ttk.Entry(detailf, textvariable=contact_var); contact_e.grid(row=2, column=1, pady=2)
    
            ttk.Label(detailf, text="Email:").grid(row=3, column=0, sticky=tk.W, pady=2)
            email_var = tk.StringVar(); email_e = ttk.Entry(detailf, textvariable=email_var); email_e.grid(row=3, column=1, pady=2)
    
            ttk.Label(detailf, text="Teléfono 1:").grid(row=4, column=0, sticky=tk.W, pady=2)
            phone_var = tk.StringVar(); phone_e = ttk.Entry(detailf, textvariable=phone_var); phone_e.grid(row=4, column=1, pady=2)
    
            ttk.Label(detailf, text="Teléfono 2:").grid(row=5, column=0, sticky=tk.W, pady=2)
            phone2_var = tk.StringVar(); phone2_e = ttk.Entry(detailf, textvariable=phone2_var); phone2_e.grid(row=5, column=1, pady=2)
    
            ttk.Label(detailf, text="Dirección:").grid(row=6, column=0, sticky=tk.W, pady=2)
            address_var = tk.StringVar(); address_e = ttk.Entry(detailf, textvariable=address_var, width=36); address_e.grid(row=6, column=1, pady=2)
    
            ttk.Label(detailf, text="Notas:").grid(row=7, column=0, sticky=tk.W, pady=2)
            notes_var = tk.StringVar(); notes_e = ttk.Entry(detailf, textvariable=notes_var, width=36); notes_e.grid(row=7, column=1, pady=2)
    
            # acciones
            actionf = ttk.Frame(right); actionf.pack(fill=tk.X, pady=8)
            def on_add():
                name = name_var.get().strip()
                if not name:
                    messagebox.showwarning("Aviso", "Nombre es obligatorio"); return
                data = {
                    "name": name,
                    "tax_id": tax_var.get().strip() or None,
                    "contact_person": contact_var.get().strip() or None,
                    "email": email_var.get().strip() or None,
                    "phone": phone_var.get().strip() or None,
                    "phone2": phone2_var.get().strip() or None,
                    "address": address_var.get().strip() or None,
                    "notes": notes_var.get().strip() or None
                }
                sid = add_supplier_db(data)
                messagebox.showinfo("Creado", f"Proveedor creado (ID: {sid})")
                load_list(None)
                clear_fields()
    
            def on_update():
                sel = tree.selection()
                if not sel:
                    messagebox.showwarning("Aviso", "Selecciona un proveedor para editar"); return
                sid = int(tree.item(sel[0], 'values')[0])
                data = {
                    "name": name_var.get().strip(),
                    "tax_id": tax_var.get().strip() or None,
                    "contact_person": contact_var.get().strip() or None,
                    "email": email_var.get().strip() or None,
                    "phone": phone_var.get().strip() or None,
                    "phone2": phone2_var.get().strip() or None,
                    "address": address_var.get().strip() or None,
                    "notes": notes_var.get().strip() or None
                }
                update_supplier_db(sid, data)
                messagebox.showinfo("Guardado", "Proveedor actualizado.")
                load_list(None)
    
            def on_delete():
                sel = tree.selection()
                if not sel:
                    messagebox.showwarning("Aviso", "Selecciona un proveedor para eliminar"); return
                sid = int(tree.item(sel[0], 'values')[0])
                if messagebox.askyesno("Confirmar", f"Eliminar proveedor ID {sid}?"):
                    delete_supplier_db(sid)
                    messagebox.showinfo("Eliminado", "Proveedor eliminado.")
                    load_list(None)
                    clear_fields()
    
            ttk.Button(actionf, text="Agregar", command=on_add).pack(fill=tk.X, pady=4)
            ttk.Button(actionf, text="Guardar cambios", command=on_update).pack(fill=tk.X, pady=4)
            ttk.Button(actionf, text="Eliminar", command=on_delete).pack(fill=tk.X, pady=4)
    
            def clear_fields():
                name_var.set(""); tax_var.set(""); contact_var.set(""); email_var.set("")
                phone_var.set(""); phone2_var.set(""); address_var.set(""); notes_var.set("")
    
            # cuando se selecciona proveedor en la lista
            def on_select(event=None):
                sel = tree.selection()
                if not sel:
                    return
                vals = tree.item(sel[0], 'values')
                sid = int(vals[0])
                row = get_supplier_db(sid)
                if not row:
                    return
                name_var.set(row['name'] or "")
                tax_var.set(row['tax_id'] or "")
                contact_var.set(row['contact_person'] or "")
                email_var.set(row['email'] or "")
                phone_var.set(row['phone'] or "")
                phone2_var.set(row['phone2'] or "")
                address_var.set(row['address'] or "")
                notes_var.set(row['notes'] or "")
    
            tree.bind("<<TreeviewSelect>>", on_select)
            tree.bind("<Double-1>", lambda e: on_select())
    
            # cargar lista
            def load_list(q=None):
                for i in tree.get_children(): tree.delete(i)
                rows = get_suppliers_db(q)
                for r in rows:
                    tree.insert('', tk.END, values=(r['id'], r['name'], r['tax_id'] or "", r['contact_person'] or "", r['email'] or "", r['phone'] or ""))
                clear_fields()
    
            # atajos: Supr -> borrar seleccionado
            tree.bind("<Delete>", lambda e: on_delete())
    
            # inicializar
            load_list()
            win.bind("<Escape>", lambda e: win.destroy())
            # focus en búsqueda
            win.after(50, lambda: search_entry.focus_set())
            return win
    
        return self.open_window_once("suppliers", creator)
    
    
    
    
    def open_outflow_dialog(self):
        """
        Diálogo global para registrar una salida (gasto).
        Guarda con add_outflow(amount, description) y refresca productos + stats si están abiertos.
        """
        dlg = tk.Toplevel(self.root)
        dlg.title("Registrar salida")
        dlg.geometry("360x180")
        dlg.resizable(False, False)
        ttk.Label(dlg, text="Monto:").pack(anchor=tk.W, padx=8, pady=(8,0))
        amt_var = tk.StringVar(value="0")
        amt_e = ttk.Entry(dlg, textvariable=amt_var); amt_e.pack(fill=tk.X, padx=8)
        ttk.Label(dlg, text="Descripción (opcional):").pack(anchor=tk.W, padx=8, pady=(8,0))
        desc_var = tk.StringVar()
        desc_e = ttk.Entry(dlg, textvariable=desc_var); desc_e.pack(fill=tk.X, padx=8)
    
        def on_save():
            try:
                amt = parse_money_to_int(amt_var.get())
                if amt <= 0:
                    messagebox.showwarning("Monto inválido", "Ingrese un monto mayor a 0")
                    return
                add_outflow(amt, desc_var.get().strip())
                messagebox.showinfo("Registrado", f"Salida registrada: ${format_money(amt)}")
                dlg.destroy()
    
                # refrescar productos (mostrar stock/estado actualizado)
                try:
                    self.load_products()
                except Exception:
                    pass
    
                # si la ventana de estadísticas está abierta y tiene refresh, llamarla
                try:
                    win_stats = self.open_windows.get('stats')
                    if win_stats and hasattr(win_stats, 'refresh'):
                        win_stats.refresh()
                except Exception:
                    pass
    
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo registrar la salida:\n{e}")
    
        btnf = ttk.Frame(dlg); btnf.pack(pady=10)
        ttk.Button(btnf, text="Guardar", command=on_save).pack(side=tk.LEFT, padx=6)
        ttk.Button(btnf, text="Cancelar", command=dlg.destroy).pack(side=tk.LEFT, padx=6)
        dlg.bind("<Return>", lambda e: on_save())
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        amt_e.focus_set()

    def open_receipt_preview(self, sale_id, sale_rows, total, received=None, change=None, company_name="Mi Negocio"):
        """
        Ventana de vista previa del recibo.
        sale_rows: lista de dicts con keys: product_name, qty, price, subtotal
        """
        # generar texto del recibo
        text = generate_receipt_text(sale_id, sale_rows, total, received=received, change=change, company_name=company_name)
    
        win = tk.Toplevel(self.root)
        win.title(f"Vista previa recibo - Venta {sale_id}")
        win.geometry("640x560")
        win.transient(self.root)
    
        # texto en widget scrollable (monospaced)
        frm = ttk.Frame(win, padding=8); frm.pack(fill=tk.BOTH, expand=True)
        txt = tk.Text(frm, wrap='none', font=("Courier New", 10))
        txt.insert('1.0', text)
        txt.config(state=tk.DISABLED)
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
        # scrollbars
        yscroll = ttk.Scrollbar(frm, orient=tk.VERTICAL, command=txt.yview)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        txt['yscrollcommand'] = yscroll.set
        xscroll = ttk.Scrollbar(win, orient=tk.HORIZONTAL, command=txt.xview)
        xscroll.pack(fill=tk.X)
        txt['xscrollcommand'] = xscroll.set
    
        # botones de acción
        btnf = ttk.Frame(win, padding=(8,8))
        btnf.pack(fill=tk.X)
    
        def do_save_text():
            path = tk.filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files","*.txt")])
            if not path:
                return
            save_receipt_text_file(text, path)
            messagebox.showinfo("Guardado", f"Recibo guardado en:\n{path}")
    
        def do_save_pdf():
            if not REPORTLAB_AVAILABLE:
                messagebox.showerror("PDF no disponible", "reportlab no está instalado. Instala pip install reportlab")
                return
            path = tk.filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files","*.pdf")])
            if not path:
                return
            try:
                save_receipt_pdf(sale_id, sale_rows, total, received=received, change=change, company_name=company_name, filename=path)
                messagebox.showinfo("PDF generado", f"PDF guardado en:\n{path}")
            except Exception as e:
                messagebox.showerror("Error PDF", str(e))
    
        def do_print():
            # guardar temporal y enviar a impresora
            tmp = os.path.join(os.getcwd(), f"preview_receipt_{sale_id}.txt")
            save_receipt_text_file(text, tmp)
            try:
                if os.name == 'nt':
                    print_text_file_windows(tmp)
                else:
                    print_text_file_lp(tmp)
                messagebox.showinfo("Impresión", "Enviado a la impresora")
            except Exception as e:
                messagebox.showerror("Error impresión", str(e))
    
        ttk.Button(btnf, text="💾 Guardar (TXT)", command=do_save_text).pack(side=tk.LEFT, padx=6)
        ttk.Button(btnf, text="📄 Guardar (PDF)", command=do_save_pdf).pack(side=tk.LEFT, padx=6)
        ttk.Button(btnf, text="🖨️ Imprimir", command=do_print).pack(side=tk.LEFT, padx=6)
        # en lugar de llamar directamente a print_receipt(), usa:
        # ttk.Button(btnf, text="🧾 Vista previa recibo", command=lambda: self.open_receipt_preview(sale_id, sale_rows, total, received, change)).pack(side=tk.LEFT, padx=6)

        ttk.Button(btnf, text="Cerrar", command=win.destroy).pack(side=tk.RIGHT, padx=6)
    
        # facilitar cerrar con Enter/Escape (Enter -> Cerrar por defecto)
        win.bind("<Return>", lambda e: win.destroy())
        win.bind("<Escape>", lambda e: win.destroy())
    
        # foco en el botón cerrar para que Enter cierre
        win.after(50, lambda: btnf.winfo_children()[-1].focus_set())
    
        return win
    



    def open_inventory_mode(self):
        """
        Modo inventario rápido: buscar por código o nombre, aumentar/disminuir stock,
        registrar en inventory_log y refrescar la tabla de productos.
        Soporta scanner de código: enfoque automático y Enter = buscar / aplicar.
        """
        key = "inventory_mode"
        def creator():
            win = tk.Toplevel(self.root)
            win.title("Modo Inventario Rápido")
            win.geometry("880x540")
            win.transient(self.root)
    
            # Top: búsqueda / scanner
            topf = ttk.Frame(win, padding=8); topf.pack(fill=tk.X)
            ttk.Label(topf, text="Código / Nombre:").grid(row=0, column=0, sticky=tk.W)
            search_var = tk.StringVar()
            search_e = ttk.Entry(topf, textvariable=search_var)
            search_e.grid(row=0, column=1, sticky=tk.EW, padx=(6,6))
            topf.columnconfigure(1, weight=1)
    
            ttk.Label(topf, text="Cantidad (±):").grid(row=0, column=2, sticky=tk.W, padx=(6,0))
            qty_var = tk.IntVar(value=1)
            qty_spin = ttk.Spinbox(topf, from_=-99999, to=99999, textvariable=qty_var, width=8)
            qty_spin.grid(row=0, column=3, sticky=tk.W, padx=(6,0))
    
            ttk.Label(topf, text="Motivo (opcional):").grid(row=1, column=0, sticky=tk.W, pady=(6,0))
            reason_var = tk.StringVar()
            reason_e = ttk.Entry(topf, textvariable=reason_var)
            reason_e.grid(row=1, column=1, columnspan=3, sticky=tk.EW, padx=(6,6), pady=(6,0))
    
            # Middle: producto encontrado y acciones
            mid = ttk.Frame(win, padding=8); mid.pack(fill=tk.X)
            result_var = tk.StringVar(value="Producto: —")
            stock_var = tk.StringVar(value="Stock actual: —")
            ttk.Label(mid, textvariable=result_var, font=(None, 11, "bold")).pack(anchor=tk.W)
            ttk.Label(mid, textvariable=stock_var).pack(anchor=tk.W, pady=(4,0))
    
            btnf = ttk.Frame(mid); btnf.pack(anchor=tk.E, pady=(6,0))
            def increase_quick(): qty_var.set(max(1, qty_var.get())); adjust_stock(abs(qty_var.get()))
            def decrease_quick(): qty_var.set(max(1, qty_var.get())); adjust_stock(-abs(qty_var.get()))
    
            ttk.Button(btnf, text=" + Añadir (Enter rápido)", command=increase_quick).pack(side=tk.LEFT, padx=6)
            ttk.Button(btnf, text=" - Quitar (Shift+Enter)", command=decrease_quick).pack(side=tk.LEFT, padx=6)
            ttk.Button(btnf, text="Aplicar (Ctrl+Enter)", command=lambda: apply_adjustment()).pack(side=tk.LEFT, padx=6)
    
            # Lower: árboles con productos y log
            lower = ttk.Frame(win, padding=8); lower.pack(fill=tk.BOTH, expand=True)
            left = ttk.Frame(lower); left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,6))
            right = ttk.Frame(lower); right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6,0))
    
            # Products list (search results)
            ttk.Label(left, text="Resultados (doble clic o seleccionar + Aplicar):").pack(anchor=tk.W)
            pcols = ("id","code","name","price","stock","cat")
            p_tree = ttk.Treeview(left, columns=pcols, show='headings', height=12)
            for c in pcols: p_tree.heading(c, text=c.capitalize())
            p_tree.column("id", width=60, anchor=tk.CENTER)
            p_tree.column("price", width=100, anchor=tk.E)
            p_tree.pack(fill=tk.BOTH, expand=True)
    
            # inventory log
            ttk.Label(right, text="Historial de ajustes recientes", font=(None, 11, "bold")).pack(anchor=tk.W)
            lcols = ("id","when","product","change","reason")
            log_tree = ttk.Treeview(right, columns=lcols, show='headings', height=12)
            for c in lcols: log_tree.heading(c, text=c.capitalize())
            log_tree.column("id", width=60, anchor=tk.CENTER)
            log_tree.column("change", width=90, anchor=tk.E)
            log_tree.pack(fill=tk.BOTH, expand=True)
    
            # bottom buttons
            bottom = ttk.Frame(win, padding=8); bottom.pack(fill=tk.X)
            ttk.Button(bottom, text="Exportar log CSV", command=lambda: export_log_csv()).pack(side=tk.LEFT)
            ttk.Button(bottom, text="Refrescar", command=lambda: do_search()).pack(side=tk.LEFT, padx=6)
            ttk.Button(bottom, text="Cerrar (Esc)", command=win.destroy).pack(side=tk.RIGHT)
    
            # helpers
            selected_product = {"row": None}  # dict mutable para capturar seleccionado
    
            def show_product(prod):
                if not prod:
                    result_var.set("Producto: —")
                    stock_var.set("Stock actual: —")
                    selected_product["row"] = None
                    return
                selected_product["row"] = prod
                result_var.set(f"Producto: {prod['name']} ({prod['code']})")
                stock_var.set(f"Stock actual: {int(prod['stock'])}")
    
            def populate_products(rows):
                for i in p_tree.get_children(): p_tree.delete(i)
                for r in rows:
                    pid, code, name, price, stock, cid = r
                    p_tree.insert('', tk.END, values=(pid, code, name, format_money(price), stock, get_category_name(cid)))
                # auto-select first
                kids = p_tree.get_children()
                if kids:
                    p_tree.selection_set(kids[0]); p_tree.focus(kids[0]); p_tree.see(kids[0])
                    vals = p_tree.item(kids[0], 'values')
                    prod = get_product_by_id(int(vals[0]))
                    show_product(prod)
    
            def populate_log():
                for i in log_tree.get_children(): log_tree.delete(i)
                c = conn.cursor()
                c.execute("SELECT id, created_at, product_name, change, reason FROM inventory_log ORDER BY id DESC LIMIT 200")
                for row in c.fetchall():
                    log_tree.insert('', tk.END, values=(row["id"], row["created_at"], row["product_name"], row["change"], row["reason"] or ""))
    
            def do_search(_ev=None):
                q = search_var.get().strip()
                # si es numérico y coincide con código exacto, priorizamos
                c = conn.cursor()
                if q:
                    # buscar por code exacto
                    c.execute("SELECT id, code, name, price, stock, category_id FROM products WHERE code = ? COLLATE NOCASE", (q,))
                    row = c.fetchone()
                    if row:
                        populate_products([row])
                        show_product(row)
                        return
                    # buscar por nombre LIKE
                    like = f"%{q}%"
                    c.execute("SELECT id, code, name, price, stock, category_id FROM products WHERE name LIKE ? OR code LIKE ? ORDER BY id DESC", (like, like))
                    rows = c.fetchall()
                    populate_products(rows)
                    if not rows:
                        show_product(None)
                else:
                    # listar recientes
                    c.execute("SELECT id, code, name, price, stock, category_id FROM products ORDER BY id DESC LIMIT 200")
                    rows = c.fetchall()
                    populate_products(rows)
    
            def adjust_stock(delta, reason_text=None):
                """Centraliza ajuste: delta puede ser +n o -n. Busca producto seleccionado y aplica cambio."""
                prod = selected_product.get("row")
                if not prod:
                    messagebox.showwarning("Selecciona producto", "Selecciona un producto antes de aplicar ajuste.")
                    return
                pid = int(prod["id"])
                code = prod["code"]
                name = prod["name"]
                # aplicar cambio
                c = conn.cursor()
                c.execute("UPDATE products SET stock = stock + ? WHERE id=?", (int(delta), pid))
                now = datetime.now().isoformat(sep=' ', timespec='seconds')
                c.execute("INSERT INTO inventory_log (product_id, product_code, product_name, change, reason, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                          (pid, code, name, int(delta), reason_text or reason_var.get().strip(), now))
                conn.commit()
                # actualizar UI
                show_product(get_product_by_id(pid))
                self.load_products()
                populate_log()
                # si producto sigue en lista de productos, actualizar su fila
                do_search()
    
            def adjust_stock_confirm(delta):
                prod = selected_product.get("row")
                if not prod:
                    messagebox.showwarning("Selecciona producto", "Selecciona un producto antes de aplicar ajuste.")
                    return
                pid = int(prod["id"]); name = prod["name"]
                if delta < 0:
                    if not messagebox.askyesno("Confirmar", f"Quitar {-delta} unidades de '{name}'? (El stock puede quedar negativo)"):
                        return
                adjust_stock(delta)
    
            def apply_adjustment():
                # aplica la cantidad indicada en qty_var (puede ser positivo o negativo)
                delta = int(qty_var.get() or 0)
                if delta == 0:
                    messagebox.showwarning("Cantidad 0", "Ingresa una cantidad distinta de 0.")
                    return
                # si qty es positiva el botón Aplicar suma, si quieres sea +/- según signo
                adjust_stock_confirm(delta)
    
            def export_log_csv():
                from tkinter import filedialog
                path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")])
                if not path:
                    return
                import csv
                c = conn.cursor()
                c.execute("SELECT id, created_at, product_code, product_name, change, reason FROM inventory_log ORDER BY id DESC")
                rows = c.fetchall()
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["ID","Fecha","Código","Producto","Cambio","Motivo"])
                    for r in rows:
                        w.writerow([r["id"], r["created_at"], r["product_code"], r["product_name"], r["change"], r["reason"] or ""])
                messagebox.showinfo("Exportado", f"Log exportado a:\n{path}")
    
            # tree bindings
            def on_prod_select(event=None):
                sel = p_tree.selection()
                if not sel:
                    return
                vals = p_tree.item(sel[0], 'values')
                pid = int(vals[0])
                prod = get_product_by_id(pid)
                show_product(prod)
    
            p_tree.bind("<Double-1>", lambda e: (on_prod_select(), adjust_stock_confirm(int(qty_var.get()))))
            p_tree.bind("<<TreeviewSelect>>", lambda e: on_prod_select())
    
            # keyboard bindings convenient for scanner:
            # Enter on search = buscar; Ctrl+Enter = aplicar; Shift+Enter = quitar
            search_e.bind("<Return>", lambda e: do_search())
            search_e.bind("<Control-Return>", lambda e: apply_adjustment())
            search_e.bind("<Shift-Return>", lambda e: adjust_stock_confirm(-abs(int(qty_var.get() or 0))))
            # focus quick: cuando la ventana abre, el entry recibe focus para scanner
            win.after(50, lambda: search_e.focus_set())
    
            # inicializar
            do_search()
            populate_log()
    
            # cerrar
            win.bind("<Escape>", lambda e: win.destroy())
            return win
    
        return self.open_window_once(key, creator)
    
    
    def open_credits_window(self):
        """
        Ventana para gestionar créditos (fiados) a clientes:
        - CRUD de clientes
        - Crear crédito (vinculado a cliente)
        - Registrar pago parcial o total
        - Buscar / exportar CSV / ver historial pagos
        """
        def creator():
            win = tk.Toplevel(self.root)
            win.title("CREDITOS")
            win.geometry("1200x600")
            win.transient(self.root)
    
            # TOP: búsqueda y botones
            top = ttk.Frame(win, padding=8); top.pack(fill=tk.X)
            ttk.Label(top, text="Buscar (cliente / ref / descripción):").pack(side=tk.LEFT)
            qvar = tk.StringVar(); qentry = ttk.Entry(top, textvariable=qvar, width=36); qentry.pack(side=tk.LEFT, padx=6)
            def do_search(): load_credits(qvar.get().strip())
            ttk.Button(top, text="Buscar", command=do_search).pack(side=tk.LEFT)
            ttk.Button(top, text="Nuevo cliente", command=lambda: self.open_customer_window()).pack(side=tk.LEFT, padx=6)
            ttk.Button(top, text="Exportar CSV", command=lambda: export_credits_csv()).pack(side=tk.RIGHT)
    
            # main split
            left = ttk.Frame(win, padding=8); left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            right = ttk.Frame(win, padding=8); right.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
    
              # credits list
            cols = ("id", "customer", "ref", "amount", "balance", "due", "created")
            tree = ttk.Treeview(left, columns=cols, show='headings', height=18)
            for c in cols:
                tree.heading(c, text=c.capitalize())
            
            # Ajustar anchura de columnas (en píxeles)
            tree.column("id", width=40, anchor=tk.CENTER)
            tree.column("customer", width=140, anchor=tk.W)
            tree.column("ref", width=100, anchor=tk.W)
            tree.column("amount", width=90, anchor=tk.E)
            tree.column("balance", width=90, anchor=tk.E)
            tree.column("due", width=100, anchor=tk.CENTER)
            tree.column("created", width=120, anchor=tk.CENTER)
            
            tree.pack(fill=tk.BOTH, expand=True)
                
            # detalle / acciones
            ttk.Label(right, text="Detalle / Acciones", font=(None,11,"bold")).pack(anchor=tk.W)
            frm = ttk.Frame(right); frm.pack(fill=tk.X, pady=6)
            ttk.Label(frm, text="Cliente:").grid(row=0, column=0, sticky=tk.W)
            cust_var = tk.StringVar(); cust_combo = ttk.Combobox(frm, textvariable=cust_var, values=[f"{r['id']} - {r['name']}" for r in get_customers_db(None)], state='readonly', width=30); cust_combo.grid(row=0, column=1, pady=3)
            ttk.Label(frm, text="Referencia:").grid(row=1, column=0, sticky=tk.W)
            ref_var = tk.StringVar(); ref_e = ttk.Entry(frm, textvariable=ref_var); ref_e.grid(row=1, column=1, pady=3)
            ttk.Label(frm, text="Monto:").grid(row=2, column=0, sticky=tk.W)
            amount_var = tk.StringVar(); amount_e = ttk.Entry(frm, textvariable=amount_var); amount_e.grid(row=2, column=1, pady=3)
            ttk.Label(frm, text="Vencimiento (YYYY-MM-DD):").grid(row=3, column=0, sticky=tk.W)
            due_var = tk.StringVar(); due_e = ttk.Entry(frm, textvariable=due_var); due_e.grid(row=3, column=1, pady=3)
            ttk.Label(frm, text="Descripción:").grid(row=4, column=0, sticky=tk.W)
            desc_var = tk.StringVar(); desc_e = ttk.Entry(frm, textvariable=desc_var); desc_e.grid(row=4, column=1, pady=3)
    
            def load_credits(q=None):
                for i in tree.get_children(): tree.delete(i)
                rows = get_credits(q=q, only_open=False, limit=1000)
                for r in rows:
                    row = dict(r)  # sqlite3.Row -> dict para usar .get si es necesario
                    tree.insert('', tk.END, values=(
                        row['id'],
                        row.get('customer_name') or "-",
                        row.get('reference') or "-",
                        f"${format_money(row['amount'])}",
                        f"${format_money(row['balance'])}",
                        row.get('due_date') or "",
                        row.get('created_at') or ""
                    ))
                    
            def create_credit_action():
                # obtener customer id
                sel = cust_var.get()
                if not sel:
                    messagebox.showwarning("Aviso", "Selecciona un cliente o crea uno nuevo"); return
                cid = int(sel.split(' - ')[0])
                try:
                    amt = parse_money_to_int(amount_var.get())
                except:
                    messagebox.showwarning("Aviso", "Monto inválido"); return
                ref = ref_var.get().strip() or None
                desc = desc_var.get().strip() or None
                due = due_var.get().strip() or None
                cidn = create_credit(cid, amt, reference=ref, description=desc, due_date=due)
                messagebox.showinfo("Creado", f"Crédito creado (ID: {cidn})")
                load_credits()
                # limpiar campos
                ref_var.set(""); amount_var.set(""); desc_var.set(""); due_var.set("")
    
            ttk.Button(right, text="Crear crédito (fiado)", command=create_credit_action).pack(fill=tk.X, pady=(6,4))
    
            # pagos: registrar pago sobre crédito seleccionado
            payf = ttk.LabelFrame(right, text="Registrar pago", padding=6); payf.pack(fill=tk.X, pady=8)
            pay_amount = tk.StringVar(); ttk.Label(payf, text="Monto:").grid(row=0,column=0,sticky=tk.W); ttk.Entry(payf, textvariable=pay_amount).grid(row=0,column=1,sticky=tk.EW)
            pay_method = tk.StringVar(); ttk.Label(payf, text="Método:").grid(row=1,column=0,sticky=tk.W); ttk.Entry(payf, textvariable=pay_method).grid(row=1,column=1,sticky=tk.EW)
            pay_note = tk.StringVar(); ttk.Label(payf, text="Nota:").grid(row=2,column=0,sticky=tk.W); ttk.Entry(payf, textvariable=pay_note).grid(row=2,column=1,sticky=tk.EW)
            def do_pay():
                sel = tree.selection()
                if not sel:
                    messagebox.showwarning("Aviso", "Selecciona un crédito"); return
                credit_id = int(tree.item(sel[0],'values')[0])
                try:
                    amt = parse_money_to_int(pay_amount.get())
                except:
                    messagebox.showwarning("Monto inválido", "Ingresa monto válido"); return
                add_credit_payment(credit_id, amt, method=pay_method.get().strip() or None, note=pay_note.get().strip() or None)
                messagebox.showinfo("Pago registrado", "Pago registrado correctamente")
                load_credits()
                pay_amount.set(""); pay_method.set(""); pay_note.set("")
            ttk.Button(payf, text="Registrar pago", command=do_pay).grid(row=3,column=0,columnspan=2,sticky=tk.EW,pady=(6,0))
    
            # ver pagos del crédito seleccionado
            paylog = ttk.LabelFrame(right, text="Pagos (últimos)", padding=6); paylog.pack(fill=tk.BOTH, expand=True, pady=6)
            pay_tree = ttk.Treeview(paylog, columns=('id','when','amount','method','note'), show='headings', height=8)
            for c in ('id','when','amount','method','note'): pay_tree.heading(c, text=c.capitalize())
            pay_tree.column('amount', anchor=tk.E, width=110)
            pay_tree.pack(fill=tk.BOTH, expand=True)
    
            def show_payments_for_selected():
                for i in pay_tree.get_children(): pay_tree.delete(i)
                sel = tree.selection()
                if not sel: return
                cid = int(tree.item(sel[0],'values')[0])
                rows = get_credit_payments(cid)
                for r in rows:
                    pay_tree.insert('', tk.END, values=(r['id'], r['created_at'], f"${format_money(r['amount'])}", r['method'] or "", r['note'] or ""))
    
            # bind selection
            tree.bind("<<TreeviewSelect>>", lambda e: show_payments_for_selected())
    
            # export csv
            def export_credits_csv():
                from tkinter import filedialog
                path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")])
                if not path: return
                import csv
                rows = get_credits(q=None, only_open=False, limit=10000)
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["ID","Cliente","Ref","Amount","Balance","Due","Created"])
                    for r in rows:
                        w.writerow([r['id'], r.get('customer_name') or "", r.get('reference') or "", r['amount'], r['balance'], r.get('due_date') or "", r.get('created_at')])
                messagebox.showinfo("Exportado", f"Exportado a:\n{path}")
    
            # inicializar
            load_credits()
            win.bind("<Escape>", lambda e: win.destroy())
            return win
    
        # return self.open_window_once("credits", creator)

            win = tk.Toplevel(self.root)
            win.title("Créditos / Fiados")
            win.geometry("980x600")
            win.transient(self.root)
    
            top = ttk.Frame(win, padding=8); top.pack(fill=tk.X)
            ttk.Label(top, text="Buscar (cliente / ref / descripción):").pack(side=tk.LEFT)
            qvar = tk.StringVar()
            qentry = ttk.Entry(top, textvariable=qvar, width=36); qentry.pack(side=tk.LEFT, padx=6)
            def do_search(): load_credits(qvar.get().strip())
            ttk.Button(top, text="Buscar", command=do_search).pack(side=tk.LEFT)
            ttk.Button(top, text="Nuevo cliente", command=lambda: self.open_customer_window()).pack(side=tk.LEFT, padx=6)
            ttk.Button(top, text="Exportar CSV", command=lambda: export_credits_csv()).pack(side=tk.RIGHT)
    
            left = ttk.Frame(win, padding=8); left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            right = ttk.Frame(win, padding=8); right.pack(side=tk.LEFT, fill=tk.Y, expand=False)
    
            cols = ("id","customer","ref","amount","balance","due","created")
            tree = ttk.Treeview(left, columns=cols, show='headings', height=20)
            for c in cols: tree.heading(c, text=c.capitalize())
            tree.column("id", width=70, anchor=tk.CENTER)
            tree.column("amount", width=120, anchor=tk.E)
            tree.column("balance", width=120, anchor=tk.E)
            tree.pack(fill=tk.BOTH, expand=True)
    
            # detalle / acciones
            ttk.Label(right, text="Detalle / Acciones", font=(None,11,"bold")).pack(anchor=tk.W)
            frm = ttk.Frame(right); frm.pack(fill=tk.X, pady=6)
    
            # combobox de clientes (valores iniciales)
            cust_var = tk.StringVar()
            cust_values = [f"{r['id']} - {r['name']}" for r in get_customers_db(None)]
            cust_combo = ttk.Combobox(frm, textvariable=cust_var, values=cust_values, state='readonly', width=30)
            ttk.Label(frm, text="Cliente:").grid(row=0, column=0, sticky=tk.W)
            cust_combo.grid(row=0, column=1, pady=3)
    
            ttk.Label(frm, text="Referencia:").grid(row=1, column=0, sticky=tk.W)
            ref_var = tk.StringVar(); ref_e = ttk.Entry(frm, textvariable=ref_var); ref_e.grid(row=1, column=1, pady=3)
            ttk.Label(frm, text="Monto:").grid(row=2, column=0, sticky=tk.W)
            amount_var = tk.StringVar(); amount_e = ttk.Entry(frm, textvariable=amount_var); amount_e.grid(row=2, column=1, pady=3)
            ttk.Label(frm, text="Vencimiento (YYYY-MM-DD):").grid(row=3, column=0, sticky=tk.W)
            due_var = tk.StringVar(); due_e = ttk.Entry(frm, textvariable=due_var); due_e.grid(row=3, column=1, pady=3)
            ttk.Label(frm, text="Descripción:").grid(row=4, column=0, sticky=tk.W)
            desc_var = tk.StringVar(); desc_e = ttk.Entry(frm, textvariable=desc_var); desc_e.grid(row=4, column=1, pady=3)
    
            def refresh_customer_combo():
                vals = [f"{r['id']} - {r['name']}" for r in get_customers_db(None)]
                cust_combo['values'] = vals
                if vals:
                    cust_combo.current(0)
    
            def load_credits(q=None):
                for i in tree.get_children(): tree.delete(i)
                rows = get_credits(q=q, only_open=False, limit=1000)
                for r in rows:
                    row = dict(r)  # sqlite3.Row -> dict para usar .get si es necesario
                    tree.insert('', tk.END, values=(
                        row['id'],
                        row.get('customer_name') or "-",
                        row.get('reference') or "-",
                        f"${format_money(row['amount'])}",
                        f"${format_money(row['balance'])}",
                        row.get('due_date') or "",
                        row.get('created_at') or ""
                    ))
    
            def create_credit_action():
                sel = cust_var.get()
                if not sel:
                    messagebox.showwarning("Aviso", "Selecciona un cliente o crea uno nuevo"); return
                cid = int(sel.split(' - ')[0])
                try:
                    amt = parse_money_to_int(amount_var.get())
                except:
                    messagebox.showwarning("Aviso", "Monto inválido"); return
                ref = ref_var.get().strip() or None
                desc = desc_var.get().strip() or None
                due = due_var.get().strip() or None
                cidn = create_credit(cid, amt, reference=ref, description=desc, due_date=due)
                messagebox.showinfo("Creado", f"Crédito creado (ID: {cidn})")
                load_credits()
                ref_var.set(""); amount_var.set(""); desc_var.set(""); due_var.set("")
    
            ttk.Button(right, text="Crear crédito (fiado)", command=create_credit_action).pack(fill=tk.X, pady=(6,4))
    
            # pagos
            payf = ttk.LabelFrame(right, text="Registrar pago", padding=6); payf.pack(fill=tk.X, pady=8)
            pay_amount = tk.StringVar(); ttk.Label(payf, text="Monto:").grid(row=0,column=0,sticky=tk.W); ttk.Entry(payf, textvariable=pay_amount).grid(row=0,column=1,sticky=tk.EW)
            pay_method = tk.StringVar(); ttk.Label(payf, text="Método:").grid(row=1,column=0,sticky=tk.W); ttk.Entry(payf, textvariable=pay_method).grid(row=1,column=1,sticky=tk.EW)
            pay_note = tk.StringVar(); ttk.Label(payf, text="Nota:").grid(row=2,column=0,sticky=tk.W); ttk.Entry(payf, textvariable=pay_note).grid(row=2,column=1,sticky=tk.EW)
    
            pay_tree = ttk.Treeview(right, columns=('id','when','amount','method','note'), show='headings', height=8)
            for c in ('id','when','amount','method','note'): pay_tree.heading(c, text=c.capitalize())
            pay_tree.column('amount', anchor=tk.E, width=110)
            pay_tree.pack(fill=tk.BOTH, expand=True)
    
            def do_pay():
                sel = tree.selection()
                if not sel:
                    messagebox.showwarning("Aviso", "Selecciona un crédito"); return
                credit_id = int(tree.item(sel[0],'values')[0])
                try:
                    amt = parse_money_to_int(pay_amount.get())
                except:
                    messagebox.showwarning("Monto inválido", "Ingresa monto válido"); return
                add_credit_payment(credit_id, amt, method=pay_method.get().strip() or None, note=pay_note.get().strip() or None)
                messagebox.showinfo("Pago registrado", "Pago registrado correctamente")
                load_credits()
                pay_amount.set(""); pay_method.set(""); pay_note.set("")
    
            def show_payments_for_selected():
                for i in pay_tree.get_children(): pay_tree.delete(i)
                sel = tree.selection()
                if not sel: return
                cid = int(tree.item(sel[0],'values')[0])
                rows = get_credit_payments(cid)
                for r in rows:
                    rr = dict(r)
                    pay_tree.insert('', tk.END, values=(rr['id'], rr['created_at'], f"${format_money(rr['amount'])}", rr.get('method') or "", rr.get('note') or ""))
    
            tree.bind("<<TreeviewSelect>>", lambda e: show_payments_for_selected())
    
            def export_credits_csv():
                from tkinter import filedialog, csv
                path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")])
                if not path: return
                rows = get_credits(q=None, only_open=False, limit=10000)
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["ID","Cliente","Ref","Amount","Balance","Due","Created"])
                    for r in rows:
                        rr = dict(r)
                        w.writerow([rr['id'], rr.get('customer_name') or "", rr.get('reference') or "", rr['amount'], rr['balance'], rr.get('due_date') or "", rr.get('created_at') or ""])
                messagebox.showinfo("Exportado", f"Exportado a:\n{path}")
    
            # inicializar
            refresh_customer_combo()
            load_credits()
            win.bind("<Escape>", lambda e: win.destroy())
            return win
    
        return self.open_window_once("credits", creator)



    def open_debts_window(self):
        """
        Ventana para gestionar deudas (lo que la tienda/cajero debe):
        - Crear deuda, ver saldo, registrar pagos, exportar CSV
        """
        def creator():
            win = tk.Toplevel(self.root)
            win.title("Deudas / Pasivos")
            win.geometry("1200x560")
            win.transient(self.root)
    
            top = ttk.Frame(win, padding=8); top.pack(fill=tk.X)
            ttk.Label(top, text="Buscar (acreedor / descripción):").pack(side=tk.LEFT)
            qvar = tk.StringVar(); qentry = ttk.Entry(top, textvariable=qvar, width=36); qentry.pack(side=tk.LEFT, padx=6)
            def do_search(): load_debts(qvar.get().strip())
            ttk.Button(top, text="Buscar", command=do_search).pack(side=tk.LEFT)
            ttk.Button(top, text="Exportar CSV", command=lambda: export_debts_csv()).pack(side=tk.RIGHT)
    
            left = ttk.Frame(win, padding=8); left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            right = ttk.Frame(win, padding=8); right.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
    
            cols = ("id","creditor","amount","balance","due","created")
            tree = ttk.Treeview(left, columns=cols, show='headings', height=20)
            for c in cols: tree.heading(c, text=c.capitalize())
            tree.column("id", width=40, anchor=tk.CENTER)
            tree.column("creditor", width=120, anchor=tk.E)
            
            tree.column("amount", width=120, anchor=tk.E)
            tree.column("balance", width=120, anchor=tk.E)
            tree.column("due", width=120, anchor=tk.E)
            tree.column("created", width=120, anchor=tk.E)
            tree.pack(fill=tk.BOTH, expand=True)
    
            # detalle / crear deuda
            ttk.Label(right, text="Crear deuda / Registrar pago", font=(None,11,"bold")).pack(anchor=tk.W)
            f = ttk.Frame(right); f.pack(fill=tk.X, pady=6)
            creditor_var = tk.StringVar(); ttk.Label(f, text="Acreedor:").grid(row=0,column=0,sticky=tk.W); ttk.Entry(f, textvariable=creditor_var).grid(row=0,column=1,sticky=tk.EW)
            amount_var = tk.StringVar(); ttk.Label(f, text="Monto:").grid(row=1,column=0,sticky=tk.W); ttk.Entry(f, textvariable=amount_var).grid(row=1,column=1,sticky=tk.EW)
            due_var = tk.StringVar(); ttk.Label(f, text="Vencimiento:").grid(row=2,column=0,sticky=tk.W); ttk.Entry(f, textvariable=due_var).grid(row=2,column=1,sticky=tk.EW)
            desc_var = tk.StringVar(); ttk.Label(f, text="Descripción:").grid(row=3,column=0,sticky=tk.W); ttk.Entry(f, textvariable=desc_var).grid(row=3,column=1,sticky=tk.EW)
    
            def create_debt_action():
                name = creditor_var.get().strip()
                if not name:
                    messagebox.showwarning("Aviso", "Nombre acreedor requerido"); return
                try:
                    amt = parse_money_to_int(amount_var.get())
                except:
                    messagebox.showwarning("Aviso", "Monto inválido"); return
                create_debt(name, amt, description=desc_var.get().strip() or None, due_date=due_var.get().strip() or None)
                messagebox.showinfo("Creado", "Deuda creada.")
                load_debts()
                creditor_var.set(""); amount_var.set(""); desc_var.set(""); due_var.set("")
    
            ttk.Button(right, text="Crear deuda", command=create_debt_action).pack(fill=tk.X, pady=6)
    
            # registrar pago
            payf = ttk.LabelFrame(right, text="Registrar pago", padding=6); payf.pack(fill=tk.X, pady=6)
            pay_amount = tk.StringVar(); ttk.Label(payf, text="Monto:").grid(row=0,column=0,sticky=tk.W); ttk.Entry(payf, textvariable=pay_amount).grid(row=0,column=1,sticky=tk.EW)
            pay_method = tk.StringVar(); ttk.Label(payf, text="Método:").grid(row=1,column=0,sticky=tk.W); ttk.Entry(payf, textvariable=pay_method).grid(row=1,column=1,sticky=tk.EW)
            pay_note = tk.StringVar(); ttk.Label(payf, text="Nota:").grid(row=2,column=0,sticky=tk.W); ttk.Entry(payf, textvariable=pay_note).grid(row=2,column=1,sticky=tk.EW)
    
            pay_tree = ttk.Treeview(right, columns=('id','when','amount','method','note'), show='headings', height=8)
            for c in ('id','when','amount','method','note'): pay_tree.heading(c, text=c.capitalize())
            pay_tree.column('amount', anchor=tk.E, width=110)
            pay_tree.pack(fill=tk.BOTH, expand=True, pady=(6,0))
    
            def do_pay():
                sel = tree.selection()
                if not sel:
                    messagebox.showwarning("Aviso", "Selecciona deuda"); return
                debt_id = int(tree.item(sel[0],'values')[0])
                try:
                    amt = parse_money_to_int(pay_amount.get())
                except:
                    messagebox.showwarning("Monto inválido", "Ingresa monto válido"); return
                add_debt_payment(debt_id, amt, method=pay_method.get().strip() or None, note=pay_note.get().strip() or None)
                messagebox.showinfo("Pago registrado", "Pago registrado correctamente")
                load_debts()
                pay_amount.set(""); pay_method.set(""); pay_note.set("")
                show_payments_for_selected()
    
            ttk.Button(right, text="Registrar pago", command=do_pay).pack(fill=tk.X, pady=6)
    
            def load_debts(q=None):
                for i in tree.get_children(): tree.delete(i)
                rows = get_debts(q=q, only_open=False, limit=1000)
                for r in rows:
                    rr = dict(r)
                    tree.insert('', tk.END, values=(
                        rr['id'],
                        rr.get('creditor_name') or "",
                        f"${format_money(rr['amount'])}",
                        f"${format_money(rr['balance'])}",
                        rr.get('due_date') or "",
                        rr.get('created_at') or ""
                    ))
    
            def show_payments_for_selected():
                for i in pay_tree.get_children(): pay_tree.delete(i)
                sel = tree.selection()
                if not sel: return
                debt_id = int(tree.item(sel[0],'values')[0])
                rows = get_debt_payments(debt_id)
                for r in rows:
                    pay_tree.insert('', tk.END, values=(r['id'], r['created_at'], f"${format_money(r['amount'])}", r['method'] or "", r['note'] or ""))
    
            tree.bind("<<TreeviewSelect>>", lambda e: show_payments_for_selected())
    
            def export_debts_csv():
                from tkinter import filedialog
                path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")])
                if not path: return
                import csv
                rows = get_debts(q=None, only_open=False, limit=10000)
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["ID","Acreedor","Amount","Balance","Due","Created"])
                    for r in rows:
                        w.writerow([r['id'], r['creditor_name'], r['amount'], r['balance'], r.get('due_date') or "", r.get('created_at')])
                messagebox.showinfo("Exportado", f"Exportado a:\n{path}")
    
            # inicializar
            load_debts()
            win.bind("<Escape>", lambda e: win.destroy())
            return win
    
        return self.open_window_once("debts", creator)
    



 
    def _get_selected_product_id(self):
        sel = self.products_tree.selection()
        if not sel: return None
        return int(self.products_tree.item(sel[0], 'values')[0])
    
    def _edit_selected_product(self):
        pid = self._get_selected_product_id()
        if pid: self.open_edit_product_window(pid)
        else: messagebox.showwarning("Aviso", "Selecciona un producto")
    
    def _delete_selected_product(self):
        pid = self._get_selected_product_id()
        if pid: self.delete_product(pid)
        else: messagebox.showwarning("Aviso", "Selecciona un producto")
    def delete_product(self, product_id):
        prod = get_product_by_id(product_id)
        if not prod:
            messagebox.showerror("Error", "Producto no encontrado"); return
        if messagebox.askyesno("Confirmar", f"Eliminar producto '{prod['name']}' (ID {product_id})?"):
            c = conn.cursor()
            c.execute("DELETE FROM products WHERE id=?", (product_id,))
            conn.commit()
            messagebox.showinfo("Eliminado", "Producto eliminado.")
            self.load_products()
    
    def open_edit_product_window(self, product_id):
        prod = get_product_by_id(product_id)
        if not prod:
            messagebox.showerror("Error", "Producto no encontrado"); return
    
        def creator():
            win = tk.Toplevel(self.root)
            win.title("Editar producto")
            win.geometry("380x300")
            ttk.Label(win, text='Nombre:').pack(anchor=tk.W, padx=8, pady=(8,0))
            name_e = ttk.Entry(win); name_e.pack(fill=tk.X, padx=8); name_e.insert(0, prod['name']); name_e.focus()
            ttk.Label(win, text='Precio:').pack(anchor=tk.W, padx=8, pady=(8,0))
            price_e = ttk.Entry(win); price_e.pack(fill=tk.X, padx=8); price_e.insert(0, str(prod['price']))
            ttk.Label(win, text='Stock:').pack(anchor=tk.W, padx=8, pady=(8,0))
            stock_e = ttk.Entry(win); stock_e.pack(fill=tk.X, padx=8); stock_e.insert(0, str(prod['stock']))
            ttk.Label(win, text='Categoría (opcional):').pack(anchor=tk.W, padx=8, pady=(8,0))
            cats = [f"0 - Ninguna"] + [f"{cid} - {name}" for cid, name in get_categories()]
            sel_cat = f"{prod['category_id']} - {get_category_name(prod['category_id'])}" if prod['category_id'] else "0 - Ninguna"
            cat_var = tk.StringVar(value=sel_cat)
            cat_combo = ttk.Combobox(win, values=cats, textvariable=cat_var, state='readonly')
            cat_combo.pack(fill=tk.X, padx=8, pady=(0,8))
    
            def save_edit(_ev=None):
                name = name_e.get().strip()
                if not name:
                    messagebox.showerror('Error', 'Nombre vacío'); return
                try:
                    price_input = price_e.get().strip()
                    price_clean = price_input.replace(".", "").replace(",", ".")
                    price = int(round(float(price_clean)))
                except:
                    messagebox.showerror('Error', 'Precio inválido'); return
                try:
                    stock = int(stock_e.get())
                except:
                    messagebox.showerror('Error', 'Stock inválido'); return
                sel = cat_var.get()
                cid = int(sel.split(' - ')[0]) if sel and sel != '0 - Ninguna' else None
                c = conn.cursor()
                c.execute("UPDATE products SET name=?, price=?, stock=?, category_id=? WHERE id=?", (name, price, stock, cid, product_id))
                conn.commit()
                messagebox.showinfo('Guardado', 'Producto actualizado.')
                win.destroy()
                self.load_products()
    
            ttk.Button(win, text='Guardar (Enter)', command=save_edit).pack(pady=8)
            win.bind('<Return>', save_edit)
            win.bind('<Escape>', lambda e: win.destroy())
            return win
        
            return self.open_window_once(f'edit_prod_{product_id}', creator)
    def reload_category_buttons(self):
        # Limpiar frame
        for w in self.cat_frame.winfo_children():
            w.destroy()
    
        cats = get_categories()
        self.category_hotkeys = {}  # tecla (string) -> (cid, name)
    
        # keys: '1'..'9','0' (0 representa la décima categoría)
        keys = ["1","2","3","4","5","6","7","8","9","0"]
    
        for i, (cid, name) in enumerate(cats):
            if i >= len(keys):
                break  # sólo manejamos hasta 10 botones por ahora
            key = keys[i]
            btn_text = f"{key} - {name}"
            btn = ttk.Button(
                self.cat_frame,
                text=btn_text,
                width=22,
                command=lambda c=cid, n=name: self.open_search_for_category(c, n)
            )
            btn.pack(pady=3)
            # guardar el atajo
            self.category_hotkeys[key] = (cid, name)
    
        # bind global (solo una vez). Si ya está puesto, no lo ponemos otra vez.
        if not getattr(self, "_category_hotkey_bound", False):
            # bind_all captura tanto fila superior como keypad keys
            self.root.bind_all("<Key>", self._handle_category_hotkey)
            # opcional: bind específico a KP_* (algunos sistemas necesitan esto)
            for kp in ("KP_1","KP_2","KP_3","KP_4","KP_5","KP_6","KP_7","KP_8","KP_9","KP_0"):
                self.root.bind_all(f"<KeyPress-{kp}>", self._handle_category_hotkey)
            self._category_hotkey_bound = True
    
    
    def _handle_category_hotkey(self, event):
        """
        Handler único para teclas. Soporta:
          - teclas de la fila superior: event.char ('1','2',...)
          - teclado numérico: event.keysym ('KP_1','KP_2',...)
        La acción sólo se ejecuta si el foco está dentro de la tabla principal (self.products_tree).
        """
        # 1) Sólo actuar si el foco está en la tabla principal (o en widgets permitidos)
        if not self._focus_in_main_table():
            return  # no hacemos nada si el foco está en otra ventana/entry/dialog
    
        # 2) primero comprobar event.char (fila superior)
        key = event.char
        if key and key in self.category_hotkeys:
            cid, name = self.category_hotkeys[key]
            self.open_search_for_category(cid, name)
            return "break"
    
        # 3) luego comprobar numpad (keysym)
        ks = event.keysym  # ejemplo: 'KP_1' o 'KP_0'
        if ks.startswith("KP_"):
            num = ks.split("_", 1)[1]  # '1', '2', ...
            hot = '0' if num == '0' else num
            if hot in self.category_hotkeys:
                cid, name = self.category_hotkeys[hot]
                self.open_search_for_category(cid, name)
                return "break"
    
        # si no lo manejamos, dejamos que el evento siga su curso
    
    
    def _focus_in_main_table(self):
        """
        Devuelve True si el widget con foco (focus_get) está dentro de la tabla principal.
        Ajusta esto si quieres permitir otros widgets (por ejemplo cart_listbox, search entry, etc.)
        """
        try:
            focused = self.root.focus_get()
            if not focused:
                return False
            # Si el foco está en otra ventana (Toplevel distinto), rechazamos.
            if focused.winfo_toplevel() is not self.root:
                return False
            # Si no tienes 'products_tree' definido, por seguridad permitimos (se puede cambiar).
            if not hasattr(self, "products_tree"):
                return True
    
            # sube por la cadena de padres para ver si alguno es products_tree
            w = focused
            while w is not None:
                if w is self.products_tree:
                    return True
                if w is self.root:
                    break
                w = getattr(w, "master", None)
    
            # Si quieres permitir más widgets, añade condiciones aquí:
            # e.g. if hasattr(self, "cart_listbox") and (w == self.cart_listbox or ancestor == self.cart_listbox): return True
    
            return False
        except Exception:
            return False
    
    def open_customer_window(self):
        def creator():
            win = tk.Toplevel(self.root)
            win.title("Clientes")
            win.geometry("1200x480")
            top = ttk.Frame(win, padding=8); top.pack(fill=tk.X)
            ttk.Label(top, text="Buscar cliente:").pack(side=tk.LEFT)
            qvar = tk.StringVar(); qentry = ttk.Entry(top, textvariable=qvar, width=36); qentry.pack(side=tk.LEFT, padx=6)
            def do_search(): load_list(qvar.get().strip())
            ttk.Button(top, text="Buscar", command=do_search).pack(side=tk.LEFT)
            left = ttk.Frame(win, padding=8); left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            cols = ("id","name","document","phone","email")
            tree = ttk.Treeview(left, columns=cols, show='headings', height=18)
            for c in cols: tree.heading(c, text=c.capitalize())
            tree.column("id", width=10, anchor=tk.CENTER)
            tree.pack(fill=tk.BOTH, expand=True)
            right = ttk.Frame(win, padding=8); right.pack(side=tk.LEFT, fill=tk.Y)
            # campos
            name_var = tk.StringVar(); doc_var = tk.StringVar(); phone_var = tk.StringVar(); email_var = tk.StringVar(); addr_var = tk.StringVar(); notes_var = tk.StringVar()
            ttk.Label(right, text="Nombre:").pack(anchor=tk.W); ttk.Entry(right, textvariable=name_var).pack(fill=tk.X)
            ttk.Label(right, text="Documento:").pack(anchor=tk.W); ttk.Entry(right, textvariable=doc_var).pack(fill=tk.X)
            ttk.Label(right, text="Teléfono:").pack(anchor=tk.W); ttk.Entry(right, textvariable=phone_var).pack(fill=tk.X)
            ttk.Label(right, text="Email:").pack(anchor=tk.W); ttk.Entry(right, textvariable=email_var).pack(fill=tk.X)
            ttk.Label(right, text="Dirección:").pack(anchor=tk.W); ttk.Entry(right, textvariable=addr_var).pack(fill=tk.X)
            ttk.Label(right, text="Notas:").pack(anchor=tk.W); ttk.Entry(right, textvariable=notes_var).pack(fill=tk.X)
            def load_list(q=None):
                for i in tree.get_children(): tree.delete(i)
                rows = get_customers_db(q)
                for r in rows: tree.insert('', tk.END, values=(r['id'], r['name'], r['document'] or "", r['phone'] or "", r['email'] or ""))
            def on_add():
                name = name_var.get().strip()
                if not name: messagebox.showwarning("Aviso","Nombre requerido"); return
                data = {"name": name, "document": doc_var.get().strip() or None, "phone": phone_var.get().strip() or None, "email": email_var.get().strip() or None, "address": addr_var.get().strip() or None, "notes": notes_var.get().strip() or None}
                add_customer_db(data); messagebox.showinfo("Creado","Cliente creado"); load_list()
            def on_update():
                sel = tree.selection()
                if not sel: messagebox.showwarning("Aviso","Selecciona cliente"); return
                cid = int(tree.item(sel[0],'values')[0])
                data = {"name": name_var.get().strip(), "document": doc_var.get().strip() or None, "phone": phone_var.get().strip() or None, "email": email_var.get().strip() or None, "address": addr_var.get().strip() or None, "notes": notes_var.get().strip() or None}
                update_customer_db(cid, data); messagebox.showinfo("Guardado","Cliente actualizado"); load_list()
            def on_delete():
                sel = tree.selection()
                if not sel: messagebox.showwarning("Aviso","Selecciona cliente"); return
                cid = int(tree.item(sel[0],'values')[0])
                if messagebox.askyesno("Confirmar", f"Eliminar cliente ID {cid}?"): delete_customer_db(cid); messagebox.showinfo("Eliminado","Cliente eliminado"); load_list()
            ttk.Button(right, text="Agregar", command=on_add).pack(fill=tk.X, pady=4)
            ttk.Button(right, text="Guardar cambios", command=on_update).pack(fill=tk.X, pady=4)
            ttk.Button(right, text="Eliminar", command=on_delete).pack(fill=tk.X, pady=4)
            tree.bind("<<TreeviewSelect>>", lambda e: (lambda sel=tree.selection(): (lambda: (name_var.set(tree.item(sel[0],'values')[1]), doc_var.set(tree.item(sel[0],'values')[2]), phone_var.set(tree.item(sel[0],'values')[3]), email_var.set(tree.item(sel[0],'values')[4])))() if sel else None)())
            load_list()
            win.bind("<Escape>", lambda e: win.destroy())
            return win
        return self.open_window_once("customers", creator)




    # ---------- windows single-instance helpers ----------
    def open_window_once(self, key, creator):
        """If window keyed exists bring to front else create via creator() and store."""
        if key in self.open_windows and self.open_windows[key].winfo_exists():
            self.open_windows[key].lift()
            return self.open_windows[key]
        win = creator()
        self.open_windows[key] = win
        # remove from dict when closed
        def on_close():
            try:
                del self.open_windows[key]
            except KeyError:
                pass
            try:
                win.destroy()
            except:
                pass
        win.protocol('WM_DELETE_WINDOW', on_close)
        return win

    def close_active_window(self):
        # close last opened window if any
        if self.open_windows:
            # close the most recently added
            key = list(self.open_windows.keys())[-1]
            win = self.open_windows.get(key)
            if win and win.winfo_exists():
                win.destroy()
                del self.open_windows[key]

    # ---------- manage categories window ----------
    def manage_categories_window(self):
        def creator():
            win = tk.Toplevel(self.root)
            win.title('Administrar categorías')
            win.geometry('420x420')
            listbox = tk.Listbox(win, width=50, height=12)
            listbox.pack(pady=8)

            def refresh():
                listbox.delete(0, tk.END)
                for cid, name in get_categories():
                    listbox.insert(tk.END, f"{cid} - {name}")
            refresh()

            name_var = tk.StringVar()
            ttk.Label(win, text='Nombre:').pack()
            entry = ttk.Entry(win, textvariable=name_var)
            entry.pack(pady=6)
            entry.bind('<Return>', lambda e: add())

            def add():
                name = name_var.get().strip()
                if not name:
                    messagebox.showwarning('Aviso', 'Escribe un nombre')
                    return
                ok = add_category(name)
                if not ok:
                    messagebox.showerror('Error', 'Esa categoría ya existe')
                name_var.set('')
                refresh()
                self.reload_category_buttons()

            def delete():
                sel = listbox.curselection()
                if not sel:
                    messagebox.showwarning('Aviso', 'Selecciona una categoría')
                    return
                text = listbox.get(sel[0])
                cid = int(text.split(' - ')[0])
                if messagebox.askyesno('Confirmar', 'Eliminar categoría? (No borra productos)'):
                    delete_category(cid)
                    refresh()
                    self.reload_category_buttons()

            ttk.Button(win, text='Agregar', command=add).pack(pady=4)
            ttk.Button(win, text='Eliminar', command=delete).pack(pady=4)
            ttk.Button(win, text='Cerrar (Esc)', command=win.destroy).pack(pady=6)
            
            win.bind('<Escape>', lambda e: win.destroy())
            
            return win
        return self.open_window_once('manage_categories', creator)

    # ---------- add product window ----------
    def open_add_product_window(self):
        def creator():
            win = tk.Toplevel(self.root)
            win.title('Agregar producto')
            win.geometry('380x320')
            ttk.Label(win, text='Nombre:').pack(anchor=tk.W, padx=8, pady=(8,0))
            name_e = ttk.Entry(win)
            name_e.pack(fill=tk.X, padx=8)
            name_e.focus()

            ttk.Label(win, text='Precio:').pack(anchor=tk.W, padx=8, pady=(8,0))
            price_e = ttk.Entry(win)
            price_e.pack(fill=tk.X, padx=8)

            ttk.Label(win, text='Stock:').pack(anchor=tk.W, padx=8, pady=(8,0))
            stock_e = ttk.Entry(win)
            stock_e.pack(fill=tk.X, padx=8)

            ttk.Label(win, text='Categoría (opcional):').pack(anchor=tk.W, padx=8, pady=(8,0))
            cats = [f"0 - Ninguna"] + [f"{cid} - {name}" for cid, name in get_categories()]
            cat_var = tk.StringVar(value=cats[0])
            cat_combo = ttk.Combobox(win, values=cats, textvariable=cat_var, state='readonly')
            cat_combo.pack(fill=tk.X, padx=8, pady=(0,8))

            code = generate_unique_code()
            ttk.Label(win, text=f'Código generado: {code}').pack(anchor=tk.W, padx=8, pady=(4,8))

            def save(_ev=None):
                name = name_e.get().strip()
                if not name:
                    messagebox.showerror('Error', 'Nombre vacío')
                    return
                try:
                    price = float(price_e.get())
                except:
                    messagebox.showerror('Error', 'Precio inválido')
                    return
                try:
                    stock = int(stock_e.get())
                except:
                    messagebox.showerror('Error', 'Stock inválido')
                    return
                sel = cat_var.get()
                if sel and sel != '0 - Ninguna':
                    cid = int(sel.split(' - ')[0])
                else:
                    cid = None
                ok, res = add_product(name, price, stock, cid, code=code)
                if ok:
                    messagebox.showinfo('Guardado', f'Producto guardado: {res}')
                    win.destroy()
                    self.load_products()
                else:
                    messagebox.showerror('Error', res)

            ttk.Button(win, text='Guardar (Enter)', command=save).pack(pady=10)
            win.bind('<Return>', save)
            win.bind('<Escape>', lambda e: win.destroy())
            return win
        return self.open_window_once('add_product', creator)

    def open_stats_window(self):
        """
        Ventana con:
         - Ventas del día (cantidad y total)
         - Totales por categoría (unidades vendidas y monto)
         - Top productos (hoy / todo el tiempo)
         - Rango de fechas opcional y exportar CSV
        """
        def run_query_for_range(start_date, end_date):
            # start_date/end_date en formato YYYY-MM-DD o None
            c = conn.cursor()
            date_clause = ""
            params = ()
            if start_date and end_date:
                date_clause = "WHERE date(s.created_at) BETWEEN ? AND ?"
                params = (start_date, end_date)
            elif start_date:
                date_clause = "WHERE date(s.created_at) >= ?"
                params = (start_date,)
            elif end_date:
                date_clause = "WHERE date(s.created_at) <= ?"
                params = (end_date,)



            # después de obtener tot_row (ventas totals)
            # obtener salidas
            # usando same start_date/end_date used above
            of_clause = ""
            of_params = params
            if start_date and end_date:
                of_clause = "WHERE date(created_at) BETWEEN ? AND ?"
                of_params = (start_date, end_date)
            elif start_date:
                of_clause = "WHERE date(created_at) >= ?"
                of_params = (start_date,)
            elif end_date:
                of_clause = "WHERE date(created_at) <= ?"
                of_params = (end_date,)
        
            c.execute(f"SELECT COALESCE(SUM(amount),0) as total_out FROM outflows {of_clause}", of_params)
            total_out_row = c.fetchone()
            total_out = total_out_row["total_out"] if total_out_row else 0
        
            
        


        
            # --- Totales ventas ---
            q_tot = f"""
                SELECT COUNT(*) as cnt, COALESCE(SUM(s.total),0) as total_amount
                FROM sales s
                {date_clause}
            """
            c.execute(q_tot, params)
            tot_row = c.fetchone()
        
            # --- Totales por categoría ---
            q_cat = f"""
                SELECT
                    COALESCE(si.category_id, 0) as cid,
                    COALESCE(ca.name, 'Sin categoría') as cat_name,
                    SUM(si.qty) as units,
                    SUM(si.qty * si.price) as amount
                FROM sale_items si
                LEFT JOIN sales s ON si.sale_id = s.id
                LEFT JOIN categories ca ON si.category_id = ca.id
                {('WHERE date(s.created_at) BETWEEN ? AND ?' if start_date and end_date else
                  'WHERE date(s.created_at) >= ?' if start_date else
                  'WHERE date(s.created_at) <= ?' if end_date else '')}
                GROUP BY COALESCE(si.category_id,0)
                ORDER BY units DESC
            """
            c.execute(q_cat, params)
            cats = c.fetchall()
        
            # --- Productos más vendidos ---
            q_prod = f"""
                SELECT
                    si.product_id,
                    si.product_name,
                    SUM(si.qty) as units,
                    SUM(si.qty * si.price) as amount
                FROM sale_items si
                LEFT JOIN sales s ON si.sale_id = s.id
                {('WHERE date(s.created_at) BETWEEN ? AND ?' if start_date and end_date else
                  'WHERE date(s.created_at) >= ?' if start_date else
                  'WHERE date(s.created_at) <= ?' if end_date else '')}
                GROUP BY si.product_id, si.product_name
                ORDER BY units DESC
                LIMIT 10
            """
            c.execute(q_prod, params)
            prods = c.fetchall()
            # net total (ventas - salidas)
            net_total = (tot_row["total_amount"] if tot_row and tot_row["total_amount"] else 0) - int(total_out)
        
            return tot_row, cats, prods, total_out, net_total
        
            # return tot_row, cats, prods
        
    
        # ventana
        win = tk.Toplevel(self.root)
        win.title("Estadísticas rápidas")
        win.geometry("1020x600")
        win.transient(self.root)
    
        # filtros
        flt = ttk.Frame(win, padding=8); flt.pack(fill=tk.X)
        ttk.Label(flt, text="Desde (YYYY-MM-DD):").pack(side=tk.LEFT)
        start_var = tk.StringVar()
        start_e = ttk.Entry(flt, textvariable=start_var, width=12); start_e.pack(side=tk.LEFT, padx=(4,8))
        ttk.Label(flt, text="Hasta (YYYY-MM-DD):").pack(side=tk.LEFT)
        end_var = tk.StringVar()
        end_e = ttk.Entry(flt, textvariable=end_var, width=12); end_e.pack(side=tk.LEFT, padx=(4,8))
    
        def set_today():
            today = datetime.now().strftime("%Y-%m-%d")
            start_var.set(today); end_var.set(today)
            refresh()
    
        ttk.Button(flt, text="Hoy", command=set_today).pack(side=tk.LEFT, padx=6)
        ttk.Button(flt, text="Aplicar filtro", command=lambda: refresh()).pack(side=tk.LEFT, padx=6)
        ttk.Button(flt, text="Exportar CSV", command=lambda: export_csv()).pack(side=tk.RIGHT, padx=6)
    
        # top summary
        # top summary (ahora incluye salidas y neto)
        sumf = ttk.Frame(win, padding=8); sumf.pack(fill=tk.X)
        total_sales_var = tk.StringVar(value="Ventas: 0   |   Total: $0")
        total_out_var = tk.StringVar(value="Salidas: $0")
        net_total_var = tk.StringVar(value="Neto: $0")
        ttk.Label(sumf, textvariable=total_sales_var, font=(None, 12, "bold")).pack(anchor=tk.W)
        ttk.Label(sumf, textvariable=total_out_var, font=(None, 10)).pack(anchor=tk.W, pady=(2,0))
        ttk.Label(sumf, textvariable=net_total_var, font=(None, 11, "bold")).pack(anchor=tk.W, pady=(2,6))
    
        # botón para registrar salida
        btns_frame = ttk.Frame(sumf)
        btns_frame.pack(fill=tk.X, pady=(4,0))
        # ttk.Button(btns_frame, text="Registrar salida", command=lambda: add_outflow_dialog()).pack(side=tk.LEFT)
        # ttk.Button(btns_frame, text="Exportar CSV", command=lambda: export_csv()).pack(side=tk.RIGHT)
    
    
        # split: left categories, right products
        body = ttk.Frame(win, padding=8); body.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(body); left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,6))
        right = ttk.Frame(body); right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6,0))
    
        # categories tree
        ttk.Label(left, text="Totales por categoría (unidades / monto)", font=(None, 11, "bold")).pack(anchor=tk.W)
        cat_cols = ("categoria","unidades","monto")
        cat_tree = ttk.Treeview(left, columns=cat_cols, show="headings", height=12)
        for c in cat_cols:
            cat_tree.heading(c, text=c.capitalize())
        cat_tree.column("categoria", width=200)
        cat_tree.column("unidades", width=100, anchor=tk.E)
        cat_tree.column("monto", width=120, anchor=tk.E)
        cat_tree.pack(fill=tk.BOTH, expand=True, pady=(6,0))
    
        # products tree
        ttk.Label(right, text="Productos más vendidos (unidades)", font=(None, 11, "bold")).pack(anchor=tk.W)
        prod_cols = ("producto","unidades","monto")
        prod_tree = ttk.Treeview(right, columns=prod_cols, show="headings", height=12)
        
        for a in prod_cols:
            prod_tree.heading(a, text=a.capitalize())
            
        prod_tree.column("producto", width=260)
        prod_tree.column("unidades", width=100, anchor=tk.E)
        prod_tree.column("monto", width=120, anchor=tk.E)
        prod_tree.pack(fill=tk.BOTH, expand=True, pady=(6,0))
    
        # detalle inferior: lista de ventas individuales en rango
        ttk.Separator(win, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)
        ttk.Label(win, text="Ventas en el rango (ID - Fecha - Total)", font=(None, 11, "bold")).pack(anchor=tk.W, padx=8)
        sales_list = ttk.Treeview(win, columns=("id","created_at","total"), show="headings", height=8)
        sales_list.heading("id", text="ID"); sales_list.heading("created_at", text="Fecha"); sales_list.heading("total", text="Total")
        sales_list.column("id", width=80, anchor=tk.CENTER)
        sales_list.column("created_at", width=300)
        sales_list.column("total", width=140, anchor=tk.E)
        sales_list.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6,8))

            # lista de salidas (debajo del sales_list o en la derecha)
        ttk.Label(win, text="Salidas en el rango (ID - Fecha - Monto - Descripción)", font=(None, 11, 'bold')).pack(anchor=tk.W, padx=8)
        outflows_list = ttk.Treeview(win, columns=('id','created_at','amount','desc'), show='headings', height=6)
        outflows_list.heading('id', text='ID'); outflows_list.heading('created_at', text='Fecha'); outflows_list.heading('amount', text='Monto'); outflows_list.heading('desc', text='Descripción')
        outflows_list.column('id', width=60, anchor=tk.CENTER); outflows_list.column('amount', width=120, anchor=tk.E)
        outflows_list.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6,8))
    
    
        # refresh function
        current_data = {"tot": None, "cats": None, "prods": None}
    
        def refresh():
            # validate dates
            s = start_var.get().strip() or None
            e = end_var.get().strip() or None
            # if only one provided and it's invalid, ignore
            try:
                if s:
                    datetime.strptime(s, "%Y-%m-%d")
                if e:
                    datetime.strptime(e, "%Y-%m-%d")
            except Exception:
                messagebox.showwarning("Formato fecha", "Formato de fecha inválido. Use YYYY-MM-DD.")
                return
            # obtener salidas detalladas
            out_rows, out_total = get_outflows_in_range(s, e)
            for i in outflows_list.get_children(): outflows_list.delete(i)
            for r in out_rows:
                outflows_list.insert('', tk.END, values=(r['id'], r['created_at'], f"${format_money(r['amount'])}", r['description'] or ""))
            
            tot_row, cats, prods, total_out, net_total = run_query_for_range(s, e)

            current_data["tot"] = tot_row; current_data["cats"] = cats; current_data["prods"] = prods
    
            # update summary
            cnt = tot_row["cnt"] if tot_row else 0
            total_amt = tot_row["total_amount"] if tot_row else 0
            total_sales_var.set(f"Ventas: {cnt}   |   Total: ${format_money(total_amt)}")
            total_out_var.set(f"Salidas: ${format_money(total_out)}")
            net_total_var.set(f"Neto: ${format_money(net_total)}")
            
    
            # fill cats
            for i in cat_tree.get_children(): cat_tree.delete(i)
            for r in cats:
                cid = r["cid"]; name = r["cat_name"]; units = r["units"] or 0; amount = r["amount"] or 0
                cat_tree.insert("", tk.END, values=(name, int(units), f"${format_money(amount)}"))
    
            # fill products
            for i in prod_tree.get_children(): prod_tree.delete(i)
            for r in prods:
                pname = r["product_name"]; units = r["units"] or 0; amount = r["amount"] or 0
                prod_tree.insert("", tk.END, values=(pname, int(units), f"${format_money(amount)}"))
    
            # fill sales list
            for i in sales_list.get_children(): sales_list.delete(i)
            c = conn.cursor()
            # build date where
            date_clause = ""
            params = ()
            if s and e:
                date_clause = "WHERE date(created_at) BETWEEN ? AND ?"
                params = (s, e)
            elif s:
                date_clause = "WHERE date(created_at) >= ?"; params = (s,)
            elif e:
                date_clause = "WHERE date(created_at) <= ?"; params = (e,)
            c.execute(f"SELECT id, created_at, total FROM sales {date_clause} ORDER BY id DESC", params)
            for row in c.fetchall():
                sales_list.insert("", tk.END, values=(row["id"], row["created_at"], f"${format_money(row['total'])}"))


        def add_outflow_dialog():
            dlg = tk.Toplevel(win)
            dlg.title("Registrar salida")
            dlg.geometry("360x180")
            ttk.Label(dlg, text="Monto:").pack(anchor=tk.W, padx=8, pady=(8,0))
            amt_var = tk.StringVar(value="0")
            amt_e = ttk.Entry(dlg, textvariable=amt_var); amt_e.pack(fill=tk.X, padx=8)
            ttk.Label(dlg, text="Descripción (opcional):").pack(anchor=tk.W, padx=8, pady=(8,0))
            desc_var = tk.StringVar()
            desc_e = ttk.Entry(dlg, textvariable=desc_var); desc_e.pack(fill=tk.X, padx=8)
        
            def on_save():
                try:
                    amt = parse_money_to_int(amt_var.get())
                    if amt <= 0:
                        messagebox.showwarning("Monto inválido", "Ingrese un monto mayor a 0"); return
                    add_outflow(amt, desc_var.get().strip())
                    messagebox.showinfo("Registrado", f"Salida registrada: ${format_money(amt)}")
                    dlg.destroy()
                    refresh()  # refresca la ventana de estadísticas
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo registrar la salida:\n{e}")
        
            btnf = ttk.Frame(dlg); btnf.pack(pady=10)
            ttk.Button(btnf, text="Guardar", command=on_save).pack(side=tk.LEFT, padx=6)
            ttk.Button(btnf, text="Cancelar", command=dlg.destroy).pack(side=tk.LEFT, padx=6)
            dlg.bind("<Return>", lambda e: on_save())
            dlg.bind("<Escape>", lambda e: dlg.destroy())
            amt_e.focus_set()

    
        def export_csv():
            # export current data: categories + products + sales
            path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files","*.csv")], title="Guardar estadísticas como CSV")
            if not path:
                return
            import csv
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["---- RESUMEN ----"])
                tot = current_data["tot"]
                writer.writerow(["Ventas_count", tot["cnt"] if tot else 0])
                writer.writerow(["Ventas_total", tot["total_amount"] if tot else 0])
                writer.writerow([])
                writer.writerow(["-- TOYTALES POR CATEGORIA --"])
                writer.writerow(["Categoria","Unidades","Monto"])
                for r in current_data["cats"]:
                    writer.writerow([r["cat_name"], r["units"] or 0, r["amount"] or 0])
                writer.writerow([])
                writer.writerow(["---- PRODUCTOS TOP ----"])
                writer.writerow(["Producto","Unidades","Monto"])
                for r in current_data["prods"]:
                    writer.writerow([r["product_name"], r["units"] or 0, r["amount"] or 0])
                writer.writerow([])
                writer.writerow(["---- GASTOS ----"])
                writer.writerow(["ID","Fecha","Monto","Descripción"])
                outs, outs_total = get_outflows_in_range()
                for o in outs:
                    writer.writerow([o['id'], o['created_at'], o['amount'], o['description']])
                writer.writerow([])
                writer.writerow(["Salidas_total", outs_total])
                # writer.writerow([])
                writer.writerow(["Neto ventas - salidas", (tot["total_amount"] if tot else 0) - outs_total])
    
            messagebox.showinfo("Exportado", f"Estadísticas guardadas en:\n{path}")
    
        # inicializar con hoy
        start_var.set(datetime.now().strftime("%Y-%m-%d"))
        end_var.set(datetime.now().strftime("%Y-%m-%d"))
        refresh()
    
        win.bind("<Escape>", lambda e: win.destroy())
        return win
    




    # ---------- open search for category (button) ----------
    def open_search_for_category(self, category_id, category_name):
        key = f'search_cat_{category_id}'
        # qvar = tk.StringVar()
        # qentry = ttk.Entry(top, textvariable=qvar)
        # qentry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        # qentry.focus()
        
        def creator():
            win = tk.Toplevel(self.root)
            win.title(f'Buscar productos - Vender como: {category_name}')
            win.geometry('720x460')

            top = ttk.Frame(win)
            top.pack(fill=tk.X, padx=8, pady=6)
            ttk.Label(top, text=f'Vender como: {category_name}', font=(None, 11, 'bold')).pack(side=tk.LEFT)
            ttk.Label(top, text='  | Buscar:').pack(side=tk.LEFT, padx=(8,0))
            qvar = tk.StringVar()
            qentry = ttk.Entry(top, textvariable=qvar)
            qentry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
            qentry.focus()

            cols = ('id','code','name','price','stock','cat')
            tree = ttk.Treeview(win, columns=cols, show='headings', height=16)
            for c in cols:
                tree.heading(c, text=c.capitalize())
            tree.column('id', width=60, anchor=tk.CENTER)
            tree.column('price', width=90, anchor=tk.E)
            tree.pack(fill=tk.BOTH, expand=True, padx=8)

            def load_list():
                for i in tree.get_children():
                    tree.delete(i)
                rows = get_all_products(qvar.get().strip())
                for r in rows:
                    pid, code, name, price, stock, cid = r
                    tree.insert('', tk.END, values=(pid, code, name, f"{int(price):,}".replace(",", "."), stock, get_category_name(cid)))

                    
            load_list()
            # poner foco en la lista y seleccionar el primer item si existe
            kids = tree.get_children()
            if kids:
                tree.selection_set(kids[0])
                tree.focus(kids[0])
                tree.see(kids[0])

            qty_var = tk.IntVar(value=1)
            qty_frame = ttk.Frame(win)
            qty_frame.pack(fill=tk.X, padx=8, pady=6)
            ttk.Label(qty_frame, text='Cantidad:').pack(side=tk.LEFT)
            qty_spin = ttk.Spinbox(qty_frame, from_=1, to=999, textvariable=qty_var, width=6)
            qty_spin.pack(side=tk.LEFT, padx=6)
            
            # Actualización en tiempo real mientras escribes
            qvar.trace_add('write', lambda *args: load_list())
            

            #Si el usuario pulsa Down desde el entry, pasar foco a la lista y seleccionar (para navegar)
            def entry_down_to_tree(event):
                # si no hay elementos, carga la lista (por si no había resultados)
                load_list()
                kids = tree.get_children()
                if kids:
                    tree.focus_set()
                    tree.selection_set(kids[0])
                    tree.focus(kids[0])
                    tree.see(kids[0])
                return "break"
            
            qentry.bind('<Down>', entry_down_to_tree)
            qentry.bind('<Return>', lambda e: load_list())  # Enter en la caja actualiza
            qentry.bind('<Escape>', lambda e: win.destroy())
            
            # Bindings para la tabla: Enter y flechas
            tree.bind('<Double-1>', lambda e: add_selected())
            tree.bind('<Return>', lambda e: add_selected())
            tree.bind('<Down>',  lambda e: self.tree_move(tree, 1))
            tree.bind('<Up>',    lambda e: self.tree_move(tree, -1))
        
            def reassign():
                sel = tree.selection()
                if not sel:
                    messagebox.showwarning('Aviso', 'Selecciona un producto')
                    return
                vals = tree.item(sel[0], 'values')
                pid = int(vals[0])
                # pedir id de categoria
                cats = get_categories()
                opts = ['0 - Ninguna'] + [f"{cid} - {n}" for cid, n in cats]
                choice = simpledialog.askstring('Reasignar categoría', 'Escribe la opción (ej: 2 - Snacks):\n' + '\n'.join(opts), parent=win)
                if not choice:
                    return
                try:
                    cid = int(choice.split(' - ')[0])
                except:
                    messagebox.showerror('Error', 'Formato inválido')
                    return
                if cid == 0:
                    cid = None
                update_product_category(pid, cid)
                load_list()
                self.load_products()

            # reemplaza la función add_selected y sus bindings por este código
            def add_selected(close_after=False, event=None):
                # intenta usar selección; si no existe usa el focused item; si tampoco, el primero
                sel = tree.selection()
                if not sel:
                    focused = tree.focus()
                    if focused:
                        sel = (focused,)
                    else:
                        kids = tree.get_children()
                        if not kids:
                            return "break"
                        sel = (kids[0],)
            
                vals = tree.item(sel[0], 'values')
                if not vals:
                    return "break"
                try:
                    pid = int(vals[0])
                except:
                    messagebox.showerror('Error', 'ID de producto inválido')
                    return "break"
            
                # obtener datos reales desde DB
                prod = get_product_by_id(pid)
                if not prod:
                    messagebox.showerror('Error', 'Producto no encontrado')
                    return "break"
            
                code = prod['code']
                name = prod['name']
                price = prod['price']
                stock = int(prod['stock'])
            
                # pedir cantidad (sin maxvalue para permitir stock negativo)
                default_qty = int(qty_var.get()) if qty_var.get() else 1
                qty = simpledialog.askinteger(
                    "Cantidad",
                    f"Ingrese la cantidad para '{name}' (stock disponible: {stock}).\n\nNota: puede vender aun si stock es insuficiente.",
                    parent=win,
                    minvalue=1,
                    initialvalue=default_qty
                )
                if qty is None:
                    return "break"
                if qty <= 0:
                    messagebox.showwarning('Aviso', 'Cantidad inválida')
                    return "break"
            
                if stock < qty:
                    # advertir pero permitir
                    if not messagebox.askyesno("Stock insuficiente",
                                               f"Stock disponible: {stock}. ¿Desea continuar y permitir stock negativo?"):
                        return "break"
            
                # añadir al carrito
                self.add_to_cart(pid, code, name, price, qty, category_id=category_id)
            
                # recargar listas para reflejar cambios
                self.load_products()
                load_list()
            
                # si se pidió cerrar la ventana (Enter), la cerramos
                if close_after:
                    try:
                        win.destroy()
                    except:
                        pass
            
                return "break"
            
            # bindings: Enter -> agrega y cierra; doble-clic -> agrega y deja ventana abierta
            tree.bind('<Return>', lambda e: add_selected(True, e))
            tree.bind('<Double-1>', lambda e: add_selected(False, e))
            # mantener navegación por flechas
            tree.bind('<Down>', lambda e: self.tree_move(tree, 1))
            tree.bind('<Up>', lambda e: self.tree_move(tree, -1))
            

            btnf = ttk.Frame(win)
            btnf.pack(fill=tk.X, padx=8, pady=6)
            ttk.Button(btnf, text='Reasignar categoría del producto', command=reassign).pack(side=tk.LEFT)
            ttk.Button(btnf, text='Agregar seleccionado al carrito (Enter)', command=add_selected).pack(side=tk.RIGHT)
            return win
        return self.open_window_once(key, creator)
    

    def tree_move(self, tree, delta):
        """
        Mueve la selección del treeview `tree` en `delta` (1 o -1).
        Devuelve 'break' para evitar que Tk haga otras cosas con la tecla.
        """
        children = tree.get_children()
        if not children:
            return "break"
        sel = tree.selection()
        try:
            if sel:
                idx = children.index(sel[0]) + delta
            else:
                idx = 0 if delta > 0 else len(children) - 1
        except ValueError:
            idx = 0 if delta > 0 else len(children) - 1
        idx = max(0, min(idx, len(children) - 1))
        item = children[idx]
        tree.selection_set(item)
        tree.focus(item)
        tree.see(item)
        return "break"







    # ---------- products list center interactions ----------
    def load_products(self, q=None):
        if q is None:
            q = self.search_var.get().strip()
        for i in self.products_tree.get_children():
            self.products_tree.delete(i)
        rows = get_all_products(q)
        for r in rows:
            pid, code, name, price, stock, cid = r
            # self.products_tree.insert('', tk.END, values=(pid, code, name, f"{int(price):,}".replace(",", "."), stock, get_category_name(cid)))
            # self.products_tree.insert('', tk.END, values=(pid, code, name, format_money(price), stock, get_category_name(cid)))
            # después de crear self.products_tree (una vez), configura tags:
            self.products_tree.tag_configure('negative', foreground='red')
            self.products_tree.tag_configure('5products', foreground='orange')
        
            # en load_products(), cuando insertas:
            if stock <= 0:
                tag = 'negative'
            elif 1 < stock <= 5:
                tag = '5products'
            else:
                tag = ''
                


            self.products_tree.insert('', tk.END, values=(pid, code, name, f"{int(price):,}".replace(",", "."), stock, get_category_name(cid)), tags=(tag,))
    
            
            


    def on_product_double(self, event):
        self._add_selected_from_tree(self.products_tree)

    def on_product_enter(self, event):
        self._add_selected_from_tree(self.products_tree)

    def _add_selected_from_tree(self, tree):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo('Info', 'Selecciona un producto (Enter para buscar si no hay selección).')
            return
        vals = tree.item(sel[0], 'values')
        pid = int(vals[0])
        code = vals[1]
        name = vals[2]
        price = int(str(vals[3]).replace("$", "").replace(".", "").replace(",", "").strip())

        stock = int(vals[4])
        # pedir cantidad
        # qty = simpledialog.askinteger('Cantidad', f'Cantidad a agregar (stock: {stock}):', parent=self.root, minvalue=1, maxvalue=stock)
        # if not qty:
        #     return

        qty = simpledialog.askinteger(
            'Cantidad',
            f'Cantidad a agregar (stock: {stock}).\n\nNota: puede vender aun si stock es insuficiente.',
            parent=self.root,
            minvalue=1,
            initialvalue=1
            # no maxvalue
        )
        if not qty:
            return
        if qty <= 0:
            messagebox.showwarning('Aviso', 'Cantidad inválida'); return
        if stock < qty:
            if not messagebox.askyesno("Stock insuficiente", f"Stock disponible: {stock}. ¿Desea continuar y permitir stock negativo?"):
                return
        
        
        prod = get_product_by_id(pid)
        default_cid = prod['category_id'] if prod else None
        # preguntar si usar categoría del producto
        # use_prod_cat = messagebox.askyesno('Categoría', 'Usar la categoría del producto para esta venta? (Sí)')
        # cat = default_cid if use_prod_cat else None
        self.add_to_cart(pid, code, name, price, qty)
        self.load_products()

    # ---------- cart operations ----------
    def add_to_cart(self, product_id, code, name, price, qty, category_id=None):
        if code in self.cart:
            self.cart[code].qty += qty
        else:
            self.cart[code] = CartItem(product_id, code, name, price, qty, category_id)
        self.refresh_cart()

    def refresh_cart(self):
        try:
            self.cart_listbox.delete(0, tk.END)
            total = 0
            for item in self.cart.values():
                # obtener price y qty de forma segura
                try:
                    price_i = int(item.price)
                except Exception:
                    price_i = int(parse_money_to_int(getattr(item, 'price', 0)))
                try:
                    qty_i = int(item.qty)
                except Exception:
                    qty_i = int(getattr(item, 'qty', 0))
    
                # si existe método total, usarlo (compatibilidad)
                if hasattr(item, 'total') and callable(getattr(item, 'total')):
                    try:
                        subtotal = int(item.total())
                    except Exception:
                        subtotal = price_i * qty_i
                else:
                    subtotal = price_i * qty_i
    
                total += subtotal
    
                catname = get_category_name(getattr(item, 'category_id', None))
                line = f"{qty_i} x {item.name} ({item.code}) [{catname}] - ${format_money(subtotal)}"
                self.cart_listbox.insert(tk.END, line)
    
            self.total_var.set(f"Total: ${format_money(total)}")
        except Exception as e:
            messagebox.showerror("Error en carrito", f"Ocurrió un error al actualizar el carrito:\n{e}")
    


    def remove_selected_cart_item(self):
        sel = self.cart_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        key = list(self.cart.keys())[idx]
        del self.cart[key]
        self.refresh_cart()

    def clear_cart(self):
        if messagebox.askyesno('Confirmar', 'Vaciar carrito?'):
            self.cart.clear()
            self.refresh_cart()










    def checkoutxxx(self):
        """
        Abre la ventana de pago donde se ingresa el monto recibido y se calcula la devolución.
        Usa open_window_once('payment', creator) para asegurar una sola instancia.
        """
        if not self.cart:
            messagebox.showinfo('Carrito vacío', 'No hay items para cobrar.')
            return
    
        # calcular total
        total = sum(item.total() for item in self.cart.values())
    
        def creator():
            win = tk.Toplevel(self.root)
            win.title("Caja - Pago")
            win.geometry("360x220")
            win.resizable(False, False)
    
            ttk.Label(win, text="PAGAR", font=(None, 14, 'bold')).pack(pady=(10,6))
    
            frame = ttk.Frame(win, padding=8)
            frame.pack(fill=tk.BOTH, expand=True)
    
            ttk.Label(frame, text=f"Total a pagar:").grid(row=0, column=0, sticky=tk.W)
            total_var = tk.StringVar(value=f"{int(total):,}".replace(",", "."))

            ttk.Label(frame, textvariable=total_var, font=(None, 12, 'bold')).grid(row=0, column=1, sticky=tk.E)
    
            ttk.Label(frame, text="Recibido:").grid(row=1, column=0, sticky=tk.W, pady=(8,0))
            received_var = tk.StringVar(value=f"{int(total):,}".replace(",", "."))
            # por defecto igual al total
            received_entry = ttk.Entry(frame, textvariable=received_var)
            received_entry.grid(row=1, column=1, sticky=tk.EW, pady=(8,0))
            received_entry.focus()
    
            ttk.Label(frame, text="Devolución:").grid(row=2, column=0, sticky=tk.W, pady=(8,0))
            change_var = tk.StringVar(value="0.00")
            ttk.Label(frame, textvariable=change_var, font=(None, 11, 'bold')).grid(row=2, column=1, sticky=tk.E, pady=(8,0))
    
            # Mensaje de error debajo
            msg_var = tk.StringVar(value="")
            msg_lbl = ttk.Label(frame, textvariable=msg_var, foreground="red")
            msg_lbl.grid(row=3, column=0, columnspan=2, pady=(6,0))
    
            # Ajustes de grid
            frame.columnconfigure(1, weight=1)
    
            def compute_change(*_):
                try:
                    rec = float(received_var.get())
                except:
                    change_var.set("—")
                    msg_var.set("Recibido inválido")
                    return
                change = rec - total
                change_var.set(f"{int(change):,}".replace(",", "."))

                if rec < total:
                    msg_var.set("Monto insuficiente")
                else:
                    msg_var.set("")
                return
    
            # trace para cambio en tiempo real
            received_var.trace_add('write', lambda *a: compute_change())
    
            def finalize_payment(_ev=None):
                
                                # validar
                try:
                    rec = float(received_var.get())
                except:
                    messagebox.showwarning("Error", "Monto recibido inválido.")
                    return
                if rec < total:
                    messagebox.showwarning("Error", f"Monto insuficiente. Total: ${int(total):,}".replace(",", "."))

                    return
    
                # preparar items para guardar (mismo formato que save_sale espera)
                items = []
                for it in self.cart.values():
                    items.append({
                        'product_id': it.product_id,
                        'code': it.code,
                        'name': it.name,
                        'price': it.price,
                        'qty': it.qty,
                        'category_id': it.category_id
                    })
    
                # guardar venta (usa la función save_sale que tienes)
                try:
                    sale_id = save_sale(items)
                
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo guardar la venta: {e}")
                    return
    
                change = rec - total
                # mostrar resumen
                messagebox.showinfo(
                    "Venta realizada",
                    f"Venta registrada (ID: {sale_id})\n"
                    f"Total: ${int(total):,}".replace(",", ".") + "\n"
                    f"Recibido: ${int(rec):,}".replace(",", ".") + "\n"
                    f"Devolución: ${int(change):,}".replace(",", ".")
                )
                
    
                # limpiar carrito y actualizar UI
                self.cart.clear()
                self.refresh_cart()
                # si implementaste badges en botones
                try:
                    self.update_category_buttons_state()
                except Exception:
                    pass
    
                # refrescar lista productos (stock actualizado)
                try:
                    self.load_products()
                except Exception:
                    pass
    
                # cerrar ventana de pago
                try:
                    win.destroy()
                except:
                    pass
    
            # Bindings: Enter para finalizar, Esc para cerrar
            received_entry.bind('<Return>', finalize_payment)
            win.bind('<Return>', finalize_payment)
            win.bind('<Escape>', lambda e: win.destroy())
    
            # Botones
            btn_frame = ttk.Frame(win)
            btn_frame.pack(fill=tk.X, pady=(8,10))
            ttk.Button(btn_frame, text="Confirmar (Enter)", command=finalize_payment).pack(side=tk.RIGHT, padx=8)
            ttk.Button(btn_frame, text="Cancelar (Esc)", command=win.destroy).pack(side=tk.RIGHT)
           


    
            # calcular cambio inicial
            compute_change()
    
            return win
        
    
        # abrir la ventana de pago (solo una instancia)
        return self.open_window_once('payment', creator)

    
    
    
    
    def checkout(self):
        """
        Checkout sencillo:
         - Lista navegable con flechas: Cobrar exacto / Ingresar recibido / Ingresar devuelta
         - Enter en la lista: si modo exacto finaliza; si modo recibido/devuelta pasa al entry
         - En 'Ingresar recibido' escribes cuánto te pagan (ej. 100000) y calcula la devolución en tiempo real
         - Enter en el entry confirma la venta
        """
        if not self.cart:
            messagebox.showinfo("Carrito vacío", "No hay items para cobrar.")
            return
    
        total = sum(item.total() for item in self.cart.values())
    
        def creator():
            win = tk.Toplevel(self.root)
            win.title("Cobro (simple)")
            win.geometry("420x260")
            win.resizable(False, False)
    
            ttk.Label(win, text=f"Total: ${format_money(total)}", font=(None, 13, "bold")).pack(pady=(8,6))
    
            # Lista de modos (navegables con flechas)
            modes = ["Cobrar exacto", "Ingresar recibido", "Ingresar devuelta"]
            lb = tk.Listbox(win, height=len(modes), exportselection=False)
            for m in modes:
                lb.insert(tk.END, m)
            lb.pack(fill=tk.X, padx=12)
            lb.selection_set(0)
            lb.focus_set()
    
            # Campo para monto (usado para recibido o devuelta según modo)
            frame = ttk.Frame(win, padding=(12,8))
            frame.pack(fill=tk.X)
            ttk.Label(frame, text="Monto (si aplica):").grid(row=0, column=0, sticky=tk.W)
            amount_var = tk.StringVar(value=format_money(total))
            amount_entry = ttk.Entry(frame, textvariable=amount_var)
            amount_entry.grid(row=0, column=1, sticky=tk.EW, padx=(6,0))
            frame.columnconfigure(1, weight=1)
    
            # Label para mostrar devolución en tiempo real
            change_var = tk.StringVar(value="0")
            ttk.Label(frame, text="Devolución:").grid(row=1, column=0, sticky=tk.W, pady=(8,0))
            ttk.Label(frame, textvariable=change_var, font=(None, 11, "bold")).grid(row=1, column=1, sticky=tk.E, pady=(8,0))
    
            # Mensaje de estado
            status_var = tk.StringVar(value="")
            ttk.Label(win, textvariable=status_var, foreground="red").pack(pady=(6,0))
    
            # Helpers
            def update_change_display():
                idxs = lb.curselection()
                mode = lb.get(idxs[0]) if idxs else modes[0]
                val = parse_money_to_int(amount_var.get())
                if mode == "Cobrar exacto":
                    change_var.set("0")
                    status_var.set("")
                elif mode == "Ingresar recibido":
                    ch = val - total
                    change_var.set(format_money(ch) if ch >= 0 else "—")
                    status_var.set("" if val >= total else "Monto insuficiente")
                else:  # "Ingresar devuelta"
                    # interpretamos el campo como la devuelta deseada
                    dev = val
                    change_var.set(format_money(dev))
                    status_var.set("")
                
    
            # Cuando se presiona Enter en la lista
            def on_list_enter(event=None):
                sel = lb.curselection()
                if not sel:
                    return
                mode = lb.get(sel[0])
                if mode == "Cobrar exacto":
                    finalize_payment_exact()
                else:
                    # pasar foco al entry para escribir monto
                    amount_entry.focus_set()
                    try:
                        amount_entry.selection_range(0, tk.END)
                    except:
                        pass
    
            lb.bind("<Return>", on_list_enter)
            lb.bind("<Double-1>", on_list_enter)
    
            # Enter en el entry finaliza según modo
            def on_entry_enter(event=None):
                sel = lb.curselection()
                mode = lb.get(sel[0]) if sel else modes[0]
                if mode == "Ingresar recibido":
                    finalize_payment_received()
                elif mode == "Ingresar devuelta":
                    finalize_payment_change()
    
            amount_entry.bind("<Return>", on_entry_enter)
            amount_var.trace_add("write", lambda *a: update_change_display())
    
            # Finalizadores
            def finalize_payment_exact():
                # construir items desde el carrito actual
                items = []
                for it in self.cart.values():
                    items.append({
                        "product_id": it.product_id,
                        "code": it.code,
                        "name": it.name,
                        "price": it.price,
                        "qty": it.qty,
                        "category_id": it.category_id
                    })
            
                # intentar guardar la venta
                try:
                    sale_id = save_sale(items)
                except ValueError as e:
                    messagebox.showerror("Error al cobrar", str(e))
                    return
                except Exception as e:
                    messagebox.showerror("Error", f"Ocurrió un error al guardar la venta:\n{e}")
                    return
            
                # actualizar productos (mostrar nuevo stock)
                try:
                    self.load_products()
                except Exception:
                    pass
            
                # preparar datos para el recibo
                sale_rows = []
                for it in items:
                    price_int = int(round(float(it.get('price', 0))))
                    qty_int = int(it.get('qty', 0))
                    sale_rows.append({
                        "product_code": it.get('code'),
                        "product_name": it.get('name'),
                        "qty": qty_int,
                        "price": price_int,
                        "subtotal": price_int * qty_int,
                        
                    })
            
                total_amount = sum(r["subtotal"] for r in sale_rows)
                rec_amount = total_amount
                change_amount = 0
            
                # ventana de confirmación (una sola)
                def show_success_window():
                    win2 = tk.Toplevel(self.root)
                    win2.title("Venta realizada ✅")
                    win2.geometry("380x250")
                    win2.resizable(False, False)
            
                    ttk.Label(win2, text="✅ Venta registrada correctamente", font=(None, 12, "bold")).pack(pady=(12,4))
                    ttk.Label(win2, text=f"ID: {sale_id}", font=(None, 10)).pack()
                    ttk.Label(win2, text=f"Total: ${format_money(total_amount)}", font=(None, 10)).pack()
                    ttk.Label(win2, text=f"Recibido: ${format_money(rec_amount)}", font=(None, 10)).pack()
                    ttk.Label(win2, text=f"Devuelta: ${format_money(change_amount)}", font=(None, 10)).pack(pady=(0,8))
            
                    def open_preview():
                        try:
                            self.open_receipt_preview(
                                sale_id,
                                sale_rows,
                                total_amount,
                                rec_amount,
                                change_amount,
                                company_name="Variedades El Sembrador"
                            )
                        except Exception as e:
                            messagebox.showerror("Error", f"No se pudo abrir la vista previa:\n{e}")
            
                    def close_window():
                        try:
                            win2.destroy()
                        except:
                            pass
                        # intentar cerrar la ventana de cobro si sigue abierta
                        try:
                            if win.winfo_exists():
                                win.destroy()
                        except Exception:
                            pass
                        # limpiar carrito y refrescar UI
                        self.cart.clear()
                        try: self.refresh_cart()
                        except: pass
                        try: self.update_category_buttons_state()
                        except: pass
                        try: self.load_products()
                        except: pass
            
                    btn_frame = ttk.Frame(win2)
                    btn_frame.pack(pady=8)
                    ttk.Button(btn_frame, text="🧾 Vista previa recibo", command=open_preview).pack(side=tk.LEFT, padx=6)
                    cancel_btn = ttk.Button(btn_frame, text="Cancelar / Cerrar", command=close_window)
                    cancel_btn.pack(side=tk.LEFT, padx=6)
                    cancel_btn.focus_set()
            
                    win2.bind("<Return>", lambda e: close_window())
                    win2.bind("<Escape>", lambda e: close_window())
            
                    return win2
            
                show_success_window()
            
            
            def finalize_payment_received():
                try:
                    rec = parse_money_to_int(amount_var.get())
                except Exception:
                    messagebox.showwarning("Error", "Monto recibido inválido")
                    return
            
                if rec < total:
                    messagebox.showwarning("Error", f"Monto insuficiente. Total: ${format_money(total)}")
                    return
            
                items = []
                for it in self.cart.values():
                    items.append({
                        "product_id": it.product_id,
                        "code": it.code,
                        "name": it.name,
                        "price": it.price,
                        "qty": it.qty,
                        "category_id": it.category_id
                    })
                try:
                    sale_id = save_sale(items)
                except ValueError as e:
                    messagebox.showerror("Error al cobrar", str(e)); return
                except Exception as e:
                    messagebox.showerror("Error", f"Ocurrió un error al guardar la venta:\n{e}"); return
            
                # actualizar productos
                try:
                    self.load_products()
                except Exception:
                    pass
            
                change = rec - total
                rec_amount = rec
                change_amount = change
            
                sale_rows = []
                for it in items:
                    price_int = int(round(float(it.get('price', 0))))
                    qty_int = int(it.get('qty', 0))
                    sale_rows.append({
                        "product_code": it.get('code'),
                        "product_name": it.get('name'),
                        "qty": qty_int,
                        "price": price_int,
                        "subtotal": price_int * qty_int,
                        
                    })
            
                total_amount = sum(r["subtotal"] for r in sale_rows)
            
                def show_success_windowss():
                    win2 = tk.Toplevel(self.root)
                    win2.title("Venta realizada ✅")
                    win2.geometry("380x250")
                    win2.resizable(False, False)
            
                    ttk.Label(win2, text="✅ Venta registrada correctamente ", font=(None, 12, "bold")).pack(pady=(12,4))
                    ttk.Label(win2, text=f"ID: {sale_id}", font=(None, 10)).pack()
                    ttk.Label(win2, text=f"Total: ${format_money(total_amount)}", font=(None, 10)).pack()
                    ttk.Label(win2, text=f"Recibido: ${format_money(rec_amount)}", font=(None, 10)).pack()
                    ttk.Label(win2, text=f"Devuelta: ${format_money(change_amount)}", font=(None, 10)).pack(pady=(0,8))
            
                    def open_preview():
                        try:
                            self.open_receipt_preview(
                                sale_id,
                                sale_rows,
                                total_amount,
                                rec_amount,
                                change_amount,
                                company_name="Mi Negocio"
                            )
                        except Exception as e:
                            messagebox.showerror("Error", f"No se pudo abrir la vista previa:\n{e}")
            
                    def close_window():
                        try:
                            win2.destroy()
                        except:
                            pass
                        try:
                            if win.winfo_exists():
                                win.destroy()
                        except:
                            pass
                        self.cart.clear()
                        try: self.refresh_cart()
                        except: pass
                        try: self.update_category_buttons_state()
                        except: pass
                        try: self.load_products()
                        except: pass
            
                    btn_frame = ttk.Frame(win2)
                    btn_frame.pack(pady=8)
                    ttk.Button(btn_frame, text="🧾 Vista previa recibo", command=open_preview).pack(side=tk.LEFT, padx=6)
                    cancel_btn = ttk.Button(btn_frame, text="Cancelar / Cerrar", command=close_window)
                    cancel_btn.pack(side=tk.LEFT, padx=6)
                    cancel_btn.focus_set()
            
                    win2.bind("<Return>", lambda e: close_window())
                    win2.bind("<Escape>", lambda e: close_window())
            
                    return win2
            
                show_success_windowss()
            
            
            def finalize_payment_change():
                try:
                    dev = parse_money_to_int(amount_var.get())
                except Exception:
                    messagebox.showwarning("Error", "Cantidad inválida")
                    return
            
                rec = total + dev
            
                items = []
                for it in self.cart.values():
                    items.append({
                        "product_id": it.product_id,
                        "code": it.code,
                        "name": it.name,
                        "price": it.price,
                        "qty": it.qty,
                        "category_id": it.category_id
                    })
                try:
                    sale_id = save_sale(items)
                except ValueError as e:
                    messagebox.showerror("Error al cobrar", str(e)); return
                except Exception as e:
                    messagebox.showerror("Error", f"Ocurrió un error al guardar la venta:\n{e}"); return
            
                # actualizar productos
                try:
                    self.load_products()
                except Exception:
                    pass
            
                rec_amount = rec
                change_amount = dev
            
                sale_rows = []
                for it in items:
                    price_int = int(round(float(it.get('price', 0))))
                    qty_int = int(it.get('qty', 0))
                    sale_rows.append({
                        "product_code": it.get('code'),
                        "product_name": it.get('name'),
                        "qty": qty_int,
                        "price": price_int,
                        "subtotal": price_int * qty_int,
                        
                    })
            
                total_amount = sum(r["subtotal"] for r in sale_rows)
            
                def show_success_windows():
                    win2 = tk.Toplevel(self.root)
                    win2.title("Venta realizada ✅")
                    win2.geometry("380x250")
                    win2.resizable(False, False)
            
                    ttk.Label(win2, text="✅ Venta registrada correctamente", font=(None, 12, "bold")).pack(pady=(12,4))
                    ttk.Label(win2, text=f"ID: {sale_id}", font=(None, 10)).pack()
                    ttk.Label(win2, text=f"Total: ${format_money(total_amount)}", font=(None, 10)).pack()
                    ttk.Label(win2, text=f"Recibido: ${format_money(rec_amount)}", font=(None, 10)).pack()
                    ttk.Label(win2, text=f"Devuelta: ${format_money(change_amount)}", font=(None, 10)).pack(pady=(0,8))
            
                    def open_preview():
                        try:
                            self.open_receipt_preview(
                                sale_id,
                                sale_rows,
                                total_amount,
                                rec_amount,
                                change_amount,
                                company_name="Mi Negocio"
                            )
                        except Exception as e:
                            messagebox.showerror("Error", f"No se pudo abrir la vista previa:\n{e}")
            
                    def close_window():
                        try:
                            win2.destroy()
                        except:
                            pass
                        try:
                            if win.winfo_exists():
                                win.destroy()
                        except:
                            pass
                        self.cart.clear()
                        try: self.refresh_cart()
                        except: pass
                        try: self.update_category_buttons_state()
                        except: pass
                        try: self.load_products()
                        except: pass
            
                    btn_frame = ttk.Frame(win2)
                    btn_frame.pack(pady=8)
                    ttk.Button(btn_frame, text="🧾 Vista previa recibo", command=open_preview).pack(side=tk.LEFT, padx=6)
                    cancel_btn = ttk.Button(btn_frame, text="Cancelar / Cerrar", command=close_window)
                    cancel_btn.pack(side=tk.LEFT, padx=6)
                    cancel_btn.focus_set()
            
                    win2.bind("<Return>", lambda e: close_window())
                    win2.bind("<Escape>", lambda e: close_window())
            
                    return win2
            
                show_success_windows()
            
                dev = parse_money_to_int(amount_var.get())
                rec = total + dev
                items = []
                for it in self.cart.values():
                    items.append({
                        "product_id": it.product_id,
                        "code": it.code,
                        "name": it.name,
                        "price": it.price,
                        "qty": it.qty,
                        "category_id": it.category_id
                    })
                try:
                    sale_id = save_sale(items)
                except ValueError as e:
                    messagebox.showerror("Error al cobrar", str(e))
                try:
                    self.load_products()
                except Exception:
                    pass
                    return
                # messagebox.showinfo("Venta realizada",
                #                     f"Venta registrada (ID: {sale_id})\nTotal: ${format_money(total)}\nRecibido: ${format_money(rec)}\nDevolución: ${format_money(dev)}")
                self.cart.clear()
                self.refresh_cart()
                try: self.update_category_buttons_state()
                except: pass
                win.destroy()
    
            # Teclas: Esc cierra, Enter actúa según foco (list/entry)
            win.bind("<Escape>", lambda e: win.destroy())
            win.bind("<Return>", lambda e: on_list_enter() if win.focus_get() == lb else on_entry_enter())
            
    
            # iniciar mostrando cambio según default
            update_change_display()
            return win
    
        return self.open_window_once("simple_payment", creator)
    
    
    



    # ---------- historial ----------
    def open_history_window(self):
        def creator():
            win = tk.Toplevel(self.root)
            win.title('Historial y resumen')
            win.geometry('960x560')
            top = ttk.Frame(win, padding=8)
            top.pack(fill=tk.X)
    
            # BARRA DE BÚSQUEDA: por código de producto, nombre o ID de venta
            search_frame = ttk.Frame(top)
            search_frame.pack(fill=tk.X, pady=(0,6))
            ttk.Label(search_frame, text="Buscar (código producto / nombre / ID venta):").pack(side=tk.LEFT)
            search_var = tk.StringVar()
            search_entry = ttk.Entry(search_frame, textvariable=search_var, width=36)
            search_entry.pack(side=tk.LEFT, padx=(6,8))
            def do_search_btn():
                q = search_var.get().strip()
                load_sales(q)
            ttk.Button(search_frame, text="Buscar", command=do_search_btn).pack(side=tk.LEFT)
            ttk.Button(search_frame, text="Mostrar todo", command=lambda: (search_var.set(""), load_sales(""))).pack(side=tk.LEFT, padx=6)
            search_entry.bind("<Return>", lambda e: do_search_btn())
    
            ttk.Label(top, text='Resumen por categoría (unidades vendidas)', font=(None, 11, 'bold')).pack(anchor=tk.W)
            sum_tree = ttk.Treeview(top, columns=('cat','qty'), show='headings', height=6)
            sum_tree.heading('cat', text='Categoría')
            sum_tree.heading('qty', text='Unidades')
            sum_tree.column('qty', anchor=tk.E, width=120)
            sum_tree.pack(fill=tk.X, pady=6)
    
            # cargar resumen por categoría (global)
            c = conn.cursor()
            c.execute('SELECT COALESCE(category_id, 0) as cid, SUM(qty) as total_qty FROM sale_items GROUP BY COALESCE(category_id,0) ORDER BY total_qty DESC')
            rows = c.fetchall()
            for r in rows:
                cid = r['cid']; qty = r['total_qty']
                sum_tree.insert('', tk.END, values=(get_category_name(cid), qty if qty else 0))
    
            ttk.Separator(win, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
            bottom = ttk.Frame(win, padding=8)
            bottom.pack(fill=tk.BOTH, expand=True)
            leftf = ttk.Frame(bottom); leftf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,6))
            rightf = ttk.Frame(bottom); rightf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6,0))
    
            # lista de ventas
            ttk.Label(leftf, text='Ventas (doble clic para detalle)', font=(None, 11, 'bold')).pack(anchor=tk.W)
            sales_tree = ttk.Treeview(leftf, columns=('id','created_at','total'), show='headings', height=18)
            sales_tree.heading('id', text='ID'); sales_tree.heading('created_at', text='Fecha / Hora'); sales_tree.heading('total', text='Total')
            sales_tree.column('total', anchor=tk.E, width=120)
            sales_tree.pack(fill=tk.BOTH, expand=True)
    
            # detalle de la venta seleccionada (derecha)
            ttk.Label(rightf, text='Detalle venta seleccionada', font=(None, 11, 'bold')).pack(anchor=tk.W)
            detail_tree = ttk.Treeview(rightf, columns=('qty','code','name','price','subtotal','cat'), show='headings', height=18)
            detail_tree.heading('qty', text='Cant.'); detail_tree.heading('code', text='Cód.'); detail_tree.heading('name', text='Producto')
            detail_tree.heading('price', text='Precio'); detail_tree.heading('subtotal', text='Subtotal'); detail_tree.heading('cat', text='Categoría')
            detail_tree.column('price', anchor=tk.E, width=90); detail_tree.column('subtotal', anchor=tk.E, width=100)
            detail_tree.pack(fill=tk.BOTH, expand=True)
    
            # función para cargar ventas (opcional filtro q)
            def load_sales(q=""):
                for i in sales_tree.get_children(): sales_tree.delete(i)
                q = q.strip()
                c = conn.cursor()
                if not q:
                    # sin filtro: últimas ventas
                    c.execute("SELECT id, created_at, total FROM sales ORDER BY id DESC LIMIT 500")
                    rows = c.fetchall()
                else:
                    # buscar por ID exacto si es entero
                    if q.isdigit():
                        c.execute("SELECT id, created_at, total FROM sales WHERE id=? ORDER BY id DESC", (int(q),))
                        rows = c.fetchall()
                    else:
                        # buscar ventas que contengan items con product_code LIKE q o product_name LIKE q
                        like = f"%{q}%"
                        c.execute("""
                            SELECT DISTINCT s.id, s.created_at, s.total
                            FROM sales s
                            JOIN sale_items si ON si.sale_id = s.id
                            WHERE si.product_code LIKE ? OR si.product_name LIKE ?
                            ORDER BY s.id DESC
                            LIMIT 500
                        """, (like, like))
                        rows = c.fetchall()
                for s in rows:
                    sales_tree.insert('', tk.END, values=(s['id'], s['created_at'], f"${format_money(s['total'])}"))
    
                # limpiar detalle
                for i in detail_tree.get_children(): detail_tree.delete(i)
    
            # cargar detalle de venta seleccionada
            def load_sale_detail(event=None):
                sel = sales_tree.selection()
                if not sel:
                    return
                sale_id = int(sales_tree.item(sel[0], 'values')[0])
                for i in detail_tree.get_children(): detail_tree.delete(i)
                c = conn.cursor()
                c.execute("SELECT product_name, qty, price, product_code, category_id FROM sale_items WHERE sale_id=? ORDER BY id", (sale_id,))
                for r in c.fetchall():
                    pname = r['product_name']; qty = r['qty']; price = r['price']; code = r['product_code']; cid = r['category_id']
                    detail_tree.insert('', tk.END, values=(qty, code, pname, f"${format_money(price)}", f"${format_money(int(qty)*int(price))}", get_category_name(cid)))
    
            # double click en ventas => abrir detalle en la derecha y permitir abrir ventana detalle si se quiere
            sales_tree.bind('<Double-1>', lambda e: (load_sale_detail(), self.open_sale_detail_window(int(sales_tree.item(sales_tree.selection()[0],'values')[0]))))
            sales_tree.bind('<<TreeviewSelect>>', lambda e: load_sale_detail())
    
            # botón imprimir recibo desde aquí
            def print_selected():
                sel = sales_tree.selection()
                if not sel:
                    messagebox.showwarning("Aviso", "Selecciona una venta para imprimir")
                    return
                sale_id = int(sales_tree.item(sel[0], 'values')[0])
                # reconstruir sale_rows para preview/impresión
                c = conn.cursor()
                c.execute("SELECT product_name, qty, price, product_code, category_id FROM sale_items WHERE sale_id=?", (sale_id,))
                sale_rows = []
                total = 0
                for r in c.fetchall():
                    pname = r['product_name']; qty = r['qty']; price = r['price']; code = r['product_code']
                    subtotal = int(qty) * int(price)
                    total += subtotal
                    sale_rows.append({"product_name": pname, "qty": qty, "price": price, "subtotal": subtotal, "product_code": code})
                self.open_receipt_preview(sale_id, sale_rows, total, None, None)
    
            btns = ttk.Frame(leftf)
            btns.pack(fill=tk.X, pady=(6,0))
            ttk.Button(btns, text="Imprimir / Vista previa (venta seleccionada)", command=print_selected).pack(side=tk.LEFT, padx=6)
    
            # inicializar
            load_sales()
            populate_log = lambda : None  # placeholder si quieres usar logs
            win.bind('<Escape>', lambda e: win.destroy())
            return win
    
        return self.open_window_once('history', creator)
    
    
    def open_sale_detail_window(self, sale_id):
        def creator():
            win = tk.Toplevel(self.root)
            win.title(f'Detalle venta #{sale_id}')
            win.geometry('520x380')
            ttk.Label(win, text=f'Venta #{sale_id}', font=(None, 11, 'bold')).pack(anchor=tk.W, padx=8, pady=6)
            tree = ttk.Treeview(win, columns=('name','qty','price','cat'), show='headings', height=12)
            tree.heading('name', text='Producto')
            tree.heading('qty', text='Cant.')
            tree.heading('price', text='Precio')
            tree.heading('cat', text='Categoría')
            tree.column('price', anchor=tk.E, width=100)
            tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
            for r in get_sale_items(sale_id):
                name, qty, price, cid = r
                tree.insert('', tk.END, values=(name, qty,f"{int(price):,}".replace(",", "."), get_category_name(cid)))
            win.bind('<Escape>', lambda e: win.destroy())
            return win
        return self.open_window_once(f'sale_{sale_id}', creator)

# ---------------- run ----------------
if __name__ == '__main__':
    root = tk.Tk()
    app = POSApp(root)
    root.mainloop()