
#!/usr/bin/env python3
"""
main.py - Registradora con Tkinter + SQLite
- Ejecutar: python main.py
- La BD se crea en app/database/punto_ventas.db
"""

import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, simpledialog
import sqlite3
# from tkinter import csv
import uuid
import os
import csv
from datetime import datetime
from tkinter import filedialog  # si ya lo importaste arriba, no hace falta duplicar
import json
from PIL import Image, ImageTk  # Importar desde Pillow


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
    c.execute("""
    CREATE TABLE IF NOT EXISTS sale_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER NOT NULL,
        method TEXT NOT NULL,
        amount INTEGER NOT NULL,
        details TEXT,
        created_at TEXT,
        FOREIGN KEY(sale_id) REFERENCES sales(id)
    )
    """)
    
    c.execute("""
    CREATE TABLE IF NOT EXISTS adjustments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT,
        reference_id INTEGER,
        note TEXT,
        amount INTEGER,
        user TEXT,
        created_at TEXT
    )
    """)
    
    c.execute("""
    CREATE TABLE IF NOT EXISTS cash_closures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        opened_at TEXT,
        closed_at TEXT,
        opening_cash INTEGER DEFAULT 0,
        cash_in_sales INTEGER DEFAULT 0,
        cash_expenses INTEGER DEFAULT 0,
        cash_counted INTEGER DEFAULT 0,
        cash_diff INTEGER DEFAULT 0,
        total_sales INTEGER DEFAULT 0,
        payments_summary TEXT,
        notes TEXT,
        created_at TEXT
    )
    """)

    conn.commit()
        
    c.execute("""CREATE TABLE IF NOT EXISTS paid_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT NOT NULL,
        amount INTEGER NOT NULL,
        note TEXT,
        created_at TEXT
    )""")
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
        defaults = [f"CATEGORIA {i}" for i in range(1, 11)]
        for name in defaults:
            try:
                c.execute("INSERT INTO categories (name) VALUES (?)", (name,))
            except sqlite3.IntegrityError:
                pass
        conn.commit()

    conn.commit()
    return conn

conn = init_db()


# ---------- helpers para ventas/pagos ----------
def get_sales_total_for_period(conn, start_dt, end_dt):
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(total),0) as total_sales FROM sales WHERE created_at BETWEEN ? AND ?", (start_dt, end_dt))
    r = c.fetchone()
    return int((r['total_sales'] if isinstance(r, dict) and 'total_sales' in r else (r[0] if r else 0)) or 0)

def get_payments_summary_for_period(conn, start_dt, end_dt):
    """
    Devuelve lista de dicts: [{'method':..., 'total':..., 'count':...}, ...]
    """
    c = conn.cursor()
    c.execute("""
        SELECT sp.method, SUM(sp.amount) as total, COUNT(DISTINCT sp.sale_id) as count
        FROM sale_payments sp
        JOIN sales s ON sp.sale_id = s.id
        WHERE s.created_at BETWEEN ? AND ?
        GROUP BY sp.method
    """, (start_dt, end_dt))
    return c.fetchall()

# ---------- paid_orders ----------
def add_paid_order(conn, customer_name, amount, note=None):
    now = datetime.now().isoformat(sep=' ', timespec='seconds')
    c = conn.cursor()
    c.execute("INSERT INTO paid_orders (customer_name, amount, note, created_at) VALUES (?, ?, ?, ?)",
              (customer_name, int(amount), note or "", now))
    conn.commit()
    return c.lastrowid

def get_paid_orders_for_period(conn, start_dt, end_dt):
    c = conn.cursor()
    c.execute("SELECT id, customer_name, amount, note, created_at FROM paid_orders WHERE created_at BETWEEN ? AND ? ORDER BY created_at ASC",
              (start_dt, end_dt))
    return c.fetchall()

def sum_paid_orders_for_period(conn, start_dt, end_dt):
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(amount),0) as total FROM paid_orders WHERE created_at BETWEEN ? AND ?", (start_dt, end_dt))
    r = c.fetchone()
    return int((r['total'] if isinstance(r, dict) and 'total' in r else (r[0] if r else 0)) or 0)

# ---------- adjustments (gastos) ----------

def _get_table_columns(conn, table):
    cur = conn.cursor()
    try:
        cur.execute(f"PRAGMA table_info({table})")
        return [r[1] if isinstance(r, (list,tuple)) else (r.get('name') if isinstance(r, dict) else None) for r in cur.fetchall()]
    except Exception:
        return []

def _detect_amount_column(conn, table):
    # candidatos por nombre
    candidates = ['amount','monto','total','value','importe','price','cost','amount_cents','monto_cents']
    cols = _get_table_columns(conn, table)
    for c in candidates:
        if c in cols:
            return c
    # si no hay candidato por nombre, intentar inferir a partir de la primera fila
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT * FROM {table} LIMIT 1")
        row = cur.fetchone()
        if not row:
            return None
        # si row es dict-like, verificamos tipos en valores
        try:
            rowd = dict(row)
            for k,v in rowd.items():
                if isinstance(v,(int,float)) and k in cols:
                    return k
        except Exception:
            # tupla: probar por posición
            for idx, colname in enumerate(cols):
                try:
                    val = row[idx]
                    if isinstance(val,(int,float)):
                        return colname
                except Exception:
                    continue
    except Exception:
        pass
    return None

def get_adjustments_for_period(conn, start_dt, end_dt, table="adjustments"):
    """
    Devuelve lista de dicts con campos: id, kind, note, amount, user, created_at
    Detecta la columna de monto automáticamente.
    """
    cur = conn.cursor()
    col_amount = _detect_amount_column(conn, table)
    if not col_amount:
        # no se encontró columna de monto: devolver filas sin monto (0)
        try:
            cur.execute(f"SELECT * FROM {table} WHERE created_at BETWEEN ? AND ? ORDER BY created_at DESC", (start_dt, end_dt))
            rows = cur.fetchall()
            out = []
            for r in rows:
                try:
                    row = dict(r)
                except:
                    # mapear por posiciones hasta 6 campos como fallback
                    row = {
                        "id": r[0] if len(r)>0 else None,
                        "kind": r[1] if len(r)>1 else "",
                        "note": r[2] if len(r)>2 else "",
                        "amount": 0,
                        "user": r[4] if len(r)>4 else "",
                        "created_at": r[5] if len(r)>5 else ""
                    }
                row['amount'] = 0
                out.append(row)
            return out
        except Exception as e:
            print("Error get_adjustments_for_period_auto (no amount col):", e)
            return []

    # construir SELECT con la columna detectada renombrada como amount
    sql = f"SELECT id, COALESCE(kind,'') as kind, COALESCE(note,'') as note, COALESCE({col_amount},0) as amount, COALESCE(user,'') as user, COALESCE(created_at,'') as created_at FROM {table} WHERE created_at BETWEEN ? AND ? ORDER BY created_at DESC"
    try:
        cur.execute(sql, (start_dt, end_dt))
        rows = cur.fetchall()
        out = []
        for r in rows:
            try:
                rr = dict(r)
            except:
                rr = {
                    "id": r[0] if len(r)>0 else None,
                    "kind": r[1] if len(r)>1 else "",
                    "note": r[2] if len(r)>2 else "",
                    "amount": r[3] if len(r)>3 else 0,
                    "user": r[4] if len(r)>4 else "",
                    "created_at": r[5] if len(r)>5 else ""
                }
            # normalizar monto a entero positivo
            try:
                rr['amount'] = abs(int(rr.get('amount') or 0))
            except:
                try:
                    rr['amount'] = abs(int(float(rr.get('amount') or 0)))
                except:
                    rr['amount'] = 0
            out.append(rr)
        return out
    except Exception as e:
        print("Error get_adjustments_for_period_auto:", e)
        return []

def sum_adjustments_for_period(conn, start_dt, end_dt, table="adjustments"):
    cur = conn.cursor()
    col_amount = _detect_amount_column(conn, table)
    if not col_amount:
        return 0
    try:
        cur.execute(f"SELECT IFNULL(SUM({col_amount}),0) as total FROM {table} WHERE created_at BETWEEN ? AND ?", (start_dt, end_dt))
        row = cur.fetchone()
        try:
            total = row['total'] if isinstance(row, dict) and 'total' in row else (row[0] if row else 0)
        except:
            total = row[0] if row else 0
        try:
            total = abs(int(total))
        except:
            try: total = abs(int(float(total)))
            except: total = 0
        return total
    except Exception as e:
        print("Error sum_adjustments_for_period_auto:", e)
        return 0


def sum_adjustments_for_period(conn, start_dt, end_dt, kind=None):
    c = conn.cursor()
    if kind:
        c.execute("SELECT COALESCE(SUM(amount),0) as total FROM adjustments WHERE kind=? AND created_at BETWEEN ? AND ?", (kind, start_dt, end_dt))
    else:
        c.execute("SELECT COALESCE(SUM(amount),0) as total FROM adjustments WHERE created_at BETWEEN ? AND ?", (start_dt, end_dt))
    r = c.fetchone()
    return int((r['total'] if isinstance(r, dict) and 'total' in r else (r[0] if r else 0)) or 0)

# ---------- credits / debts ----------
def sum_credits_for_period(conn, start_dt, end_dt):
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(amount),0) as total, COALESCE(SUM(balance),0) as balance FROM credits WHERE created_at BETWEEN ? AND ?", (start_dt, end_dt))
    r = c.fetchone()
    t = int((r['total'] if isinstance(r, dict) and 'total' in r else (r[0] if r else 0)) or 0)
    b = int((r['balance'] if isinstance(r, dict) and 'balance' in r else (r[1] if r else 0)) or 0)
    return t, b

def sum_debts_for_period(conn, start_dt, end_dt):
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(amount),0) as total, COALESCE(SUM(balance),0) as balance FROM debts WHERE created_at BETWEEN ? AND ?", (start_dt, end_dt))
    r = c.fetchone()
    t = int((r['total'] if isinstance(r, dict) and 'total' in r else (r[0] if r else 0)) or 0)
    b = int((r['balance'] if isinstance(r, dict) and 'balance' in r else (r[1] if r else 0)) or 0)
    return t, b

# ---------- export CSV helper ----------
def export_cash_closure_csv(path, summary: dict, lists: dict, company_name="Mi Negocio"):
    """
    Exporta un cierre con estilo tipo factura a CSV.
    - path: ruta destino (string)
    - summary: diccionario con claves y totales (ej: 'total_sales', 'cash_in', ...)
    - lists: diccionario con listas: 'payments' (iterable de filas), 'paid_orders', 'adjustments'
    - company_name: nombre que aparecerá en el encabezado
    """
    import csv
    from datetime import datetime

    def _fmt(v):
        # intenta usar format_money si existe, si no, formatea simple
        try:
            return format_money(int(v)) if (isinstance(v, (int, float)) or str(v).isdigit()) else str(v)
        except Exception:
            try:
                return format_money(v)
            except Exception:
                try:
                    return f"{int(v):,}"
                except:
                    return str(v)

    # normalizar fuentes de listas
    payments = lists.get("payments", [])
    paid_orders = lists.get("paid_orders", [])
    adjustments = lists.get("adjustments", [])

    # abrir y escribir CSV (UTF-8, Excel-friendly)
    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        w = csv.writer(csvfile)

        # --- Encabezado tipo factura ---
        w.writerow([company_name])
        w.writerow(["CIERRE DE CAJA", summary.get("closed_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))])
        w.writerow([])

        # --- Resumen principal (lado izquierdo como clave: valor) ---
        w.writerow(["---------RESUMEN-------------"])
        # Orden de campos (intencionalmente legible)
        ordered_keys = [
            ("TOTAL VENTA---------", "total_sales"),
            ("EFECTIVO------------", "cash_in"),
            ("TRANSFERENCIA-------", "transfer_in"),
            ("PEDIDOS PAGADOS-----", "paid_orders_total"),
            ("adjustments_total---", "adjustments_total"),
            ("TOTAL CREDITOS------", "credits_total"),
            ("TOTAL EN DEUDAS-----", "debts_total"),
            ("APERTURA------------", "opening"),
            ("EFECTIVO CONTADO----", "counted"),
            ("DIFERENCIA----------", "cash_diff")
        ]
        for label, key in ordered_keys:
            if key in summary:
                w.writerow([label, _fmt(summary.get(key))])
        w.writerow([])

        # --- Pagos: desglosado por método ---
        w.writerow(["---------PAGOS (por método)---------"])
        w.writerow(["Método", "Monto"])
        # payments puede venir como lista de tuplas o rows; intentamos manejar ambos casos
        if payments:
            for p in payments:
                # p puede ser dict, row de sqlite, o tupla (method, total)
                try:
                    if isinstance(p, dict):
                        method = p.get("method") or p.get("method_name") or p.get("name") or ""
                        amount = p.get("amount") or p.get("total") or p.get("sum") or ""
                    else:
                        # row-like: tratar como iterable
                        method = getattr(p, "method", None) or (p[0] if len(p) > 0 else "")
                        amount = getattr(p, "total", None) or (p[1] if len(p) > 1 else "")
                except Exception:
                    method = str(p)
                    amount = ""
                w.writerow([method, _fmt(amount)])
        else:
            w.writerow(["(sin registros)"])
        w.writerow([])

        # --- Pedidos pagados (detalle) ---
        w.writerow(["---------PEDIDOS PAGADOS (detalle)---------"])
        # encabezados: si paid_orders tiene dict-like podemos usar keys, sino usamos columnas por defecto
        if paid_orders:
            # intentar inferir columnas
            first = paid_orders[0]
            if isinstance(first, dict):
                headers = list(first.keys())
                w.writerow(headers)
                for r in paid_orders:
                    row = [r.get(h, "") for h in headers]
                    # formatear montos detectados
                    row = [(_fmt(x) if ("amount" in str(h).lower() or "total" in str(h).lower() or "monto" in str(h).lower()) else x) for x, h in zip(row, headers)]
                    w.writerow(row)
            else:
                # tratar filas como tuplas: asumimos (id, cliente, monto, nota, created_at) u otra forma
                # usar encabezado genérico
                w.writerow(["ID", "Cliente", "Monto", "Nota/Detalle", "Fecha"])
                for r in paid_orders:
                    try:
                        # si r es row-like con indices
                        rid = r[0] if len(r)>0 else ""
                        cliente = r[1] if len(r)>1 else ""
                        monto = r[2] if len(r)>2 else ""
                        nota = r[3] if len(r)>3 else ""
                        fecha = r[4] if len(r)>4 else ""
                    except Exception:
                        rid = r
                        cliente = monto = nota = fecha = ""
                    w.writerow([rid, cliente, _fmt(monto), nota, fecha])
        else:
            w.writerow(["(sin pedidos pagados en el período)"])
        w.writerow([])

        # --- Ajustes / Gastos (detalle) ---
        w.writerow(["---------GASTOS / AJUSTES (detalle)---------"])
        if adjustments:
            first = adjustments[0]
            if isinstance(first, dict):
                headers = list(first.keys())
                w.writerow(headers)
                for r in adjustments:
                    row = [r.get(h, "") for h in headers]
                    row = [(_fmt(x) if ("amount" in str(h).lower() or "monto" in str(h).lower()) else x) for x, h in zip(row, headers)]
                    w.writerow(row)
            else:
                # columnas por defecto
                w.writerow(["ID", "Tipo", "Nota", "Monto", "Usuario", "Fecha"])
                for a in adjustments:
                    try:
                        aid = a[0] if len(a)>0 else ""
                        kind = a[1] if len(a)>1 else ""
                        note = a[2] if len(a)>2 else ""
                        amt = a[3] if len(a)>3 else ""
                        usr = a[4] if len(a)>4 else ""
                        fecha = a[5] if len(a)>5 else ""
                    except Exception:
                        aid = kind = note = amt = usr = fecha = ""
                    w.writerow([aid, kind, note, _fmt(amt), usr, fecha])
        else:
            w.writerow(["(sin ajustes/gastos en el período)"])
        w.writerow([])

        # --- Notas, firma y pie ---
        w.writerow(["NOTAS"])
        notes = summary.get("notes") or summary.get("observations") or ""
        if notes:
            # si la nota tiene saltos, escribirla en la misma celda (CSV lo permite)
            w.writerow([notes])
        else:
            w.writerow(["-"])
        w.writerow([])
        w.writerow(["CAJERO", "__________________________", "FECHA", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        w.writerow([])
        w.writerow(["Generado por sistema POS"])

    # fin archivo
    return True




    """
    summary: dict con totales
    lists: dict de tablas: {'sales': [...], 'paid_orders': [...], 'adjustments': [...]}
    """
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Cierre de caja"])
        w.writerow(["Fecha cierre", summary.get("closed_at")])
        w.writerow([])
        w.writerow(["RESUMEN"])
        for k,v in summary.items():
            w.writerow([k, v])
        w.writerow([])
        # Detalles
        if 'paid_orders' in lists:
            w.writerow(["Pedidos pagados (detalle)"])
            w.writerow(["Cliente","Monto","Nota","Fecha"])
            for r in lists['paid_orders']:
                rr = dict(r) if hasattr(r, 'keys') else r
                w.writerow([rr.get('customer_name') if isinstance(rr, dict) else rr[1],
                            rr.get('amount') if isinstance(rr, dict) else rr[2],
                            rr.get('note') if isinstance(rr, dict) else rr[3],
                            rr.get('created_at') if isinstance(rr, dict) else rr[4]])
            w.writerow([])

        if 'adjustments' in lists:
            w.writerow(["Ajustes / Gastos (detalle)"])
            w.writerow(["ID","Tipo","Nota","Monto","Usuario","Fecha"])
            for r in lists['adjustments']:
                rr = dict(r) if hasattr(r, 'keys') else r
                w.writerow([rr.get('id'), rr.get('kind'), rr.get('note'), rr.get('amount'), rr.get('user'), rr.get('created_at')])
            w.writerow([])

        # payments per method if present
        if 'payments' in lists:
            w.writerow(["Pagos por método"])
            w.writerow(["Método","Total"])
            for p in lists['payments']:
                rp = dict(p) if hasattr(p, 'keys') else p
                w.writerow([rp.get('method') if isinstance(rp, dict) else rp[0], rp.get('total') if isinstance(rp, dict) else rp[1]])
    return path
# ---------------- DB ayudas ----------------
def add_sale_payment(sale_id, method, amount, details=None):
    """Registra un pago para una venta (amount en enteros)."""
    now = datetime.now().isoformat(sep=' ', timespec='seconds')
    c = conn.cursor()
    c.execute(
        "INSERT INTO sale_payments (sale_id, method, amount, details, created_at) VALUES (?, ?, ?, ?, ?)",
        (sale_id, method, int(amount), details, now)
    )
    conn.commit()
    return c.lastrowid

def get_sale_items_for_sales(start_dt, end_dt):
    """
    Resumen de productos vendidos entre start_dt y end_dt.
    Devuelve filas con: product_id, product_code, product_name, qty, subtotal
    start_dt / end_dt: strings con formato 'YYYY-MM-DD HH:MM:SS'
    """
    c = conn.cursor()
    c.execute("""
        SELECT si.product_id,
               si.product_code,
               si.product_name,
               SUM(si.qty) as qty,
               SUM(si.qty * si.price) as subtotal
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        WHERE s.created_at BETWEEN ? AND ?
        GROUP BY si.product_id, si.product_code, si.product_name
        ORDER BY qty DESC
    """, (start_dt, end_dt))
    return c.fetchall()

def get_payments_summary(start_dt, end_dt):
    """
    Resumen de pagos por método entre fechas.
    Devuelve filas con: method, total, sales_count
    """
    c = conn.cursor()
    c.execute("""
        SELECT sp.method,
               SUM(sp.amount) as total,
               COUNT(DISTINCT sp.sale_id) as sales_count
        FROM sale_payments sp
        JOIN sales s ON sp.sale_id = s.id
        WHERE s.created_at BETWEEN ? AND ?
        GROUP BY sp.method
        ORDER BY total DESC
    """, (start_dt, end_dt))
    return c.fetchall()

def get_credits_summary(start_dt, end_dt):
    """
    Resumen simple de créditos creados en el periodo.
    Devuelve dict-like (sqlite3.Row) con created, total_created, total_balance
    """
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*) as created,
               COALESCE(SUM(amount),0) as total_created,
               COALESCE(SUM(balance),0) as total_balance
        FROM credits
        WHERE created_at BETWEEN ? AND ?
    """, (start_dt, end_dt))
    return c.fetchone()

def get_debts_summary(start_dt, end_dt):
    """
    Resumen simple de deudas creadas en el periodo.
    """
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*) as created,
               COALESCE(SUM(amount),0) as total_created,
               COALESCE(SUM(balance),0) as total_balance
        FROM debts
        WHERE created_at BETWEEN ? AND ?
    """, (start_dt, end_dt))
    return c.fetchone()

def get_adjustments_summary(start_dt, end_dt):
    """
    Resumen de ajustes por tipo entre fechas.
    Devuelve filas con kind, cnt, total_amount
    """
    c = conn.cursor()
    c.execute("""
        SELECT kind, COUNT(*) as cnt, COALESCE(SUM(amount),0) as total_amount
        FROM adjustments
        WHERE created_at BETWEEN ? AND ?
        GROUP BY kind
        ORDER BY cnt DESC
    """, (start_dt, end_dt))
    return c.fetchall()

def sum_order_payments_for_period(conn, start_dt, end_dt):
    """
    Suma pagos de order_payments entre start_dt y end_dt (strings 'YYYY-MM-DD HH:MM:SS').
    Devuelve entero.
    """
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(amount),0) as total FROM order_payments WHERE created_at BETWEEN ? AND ?", (start_dt, end_dt))
    row = c.fetchone()
    # si row es sqlite3.Row usa row['total'] else row[0]
    try:
        return int(row['total'] or 0)
    except Exception:
        return int(row[0] or 0)

def get_order_payments_list_for_period(conn, start_dt, end_dt):
    """
    Devuelve lista de pagos individuales por pedido en el periodo:
    id, order_id, customer_name, amount, method, note, created_at
    """
    c = conn.cursor()
    c.execute("""
        SELECT op.id, op.order_id, o.customer_name, op.amount, op.method, op.note, op.created_at
        FROM order_payments op
        LEFT JOIN orders o ON op.order_id=o.id
        WHERE op.created_at BETWEEN ? AND ?
        ORDER BY op.created_at ASC
    """, (start_dt, end_dt))
    return c.fetchall()

def get_total_sales_for_period(conn, start_dt, end_dt):
    """
    Suma la columna total de sales entre fechas.
    """
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(total),0) as total_sales FROM sales WHERE created_at BETWEEN ? AND ?", (start_dt, end_dt))
    row = c.fetchone()
    try:
        return int(row['total_sales'] or 0)
    except Exception:
        return int(row[0] or 0)

def export_orders_payments_summary_csv(conn, path, start_dt, end_dt):
    """
    Exporta CSV con filas: customer_name, order_id, amount y al final resumen.
    """
    rows = get_order_payments_list_for_period(conn, start_dt, end_dt)
    total_payments = sum_order_payments_for_period(conn, start_dt, end_dt)
    total_sales = get_total_sales_for_period(conn, start_dt, end_dt)
    diff = total_sales - total_payments

    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["Cliente", "Order ID", "Monto", "Método", "Nota", "Fecha"])
        for r in rows:
            rr = dict(r) if hasattr(r, 'keys') else r
            customer = rr.get('customer_name') if isinstance(rr, dict) else rr[2]
            order_id = rr.get('order_id') if isinstance(rr, dict) else rr[1]
            amount = rr.get('amount') if isinstance(rr, dict) else rr[3]
            method = rr.get('method') if isinstance(rr, dict) else rr[4]
            note = rr.get('note') if isinstance(rr, dict) else rr[5]
            when = rr.get('created_at') if isinstance(rr, dict) else rr[6]
            w.writerow([customer, order_id, amount, method, note, when])
        # resumen
        w.writerow([])
        w.writerow(["Resumen"])
        w.writerow(["Total pagos pedidos", total_payments])
        w.writerow(["Total ventas periodo", total_sales])
        w.writerow(["Diferencia (ventas - pagos pedidos)", diff])
    return path

def save_cash_closure(user, opened_at, closed_at, opening_cash, cash_in_sales,
                      cash_expenses, cash_counted, total_sales, payments_summary, notes=None):
    """
    Guarda un cierre de caja. payments_summary debe ser un dict {method:amount,...}
    Devuelve el id insertado.
    """
    now = datetime.now().isoformat(sep=' ', timespec='seconds')
    c = conn.cursor()
    ps_json = json.dumps(payments_summary or {}, ensure_ascii=False)
    # calcular diferencia de caja (puedes adaptar la fórmula)
    try:
        cash_diff = int(cash_counted) - (int(opening_cash) + int(cash_in_sales) - int(cash_expenses or 0))
    except Exception:
        cash_diff = 0
    c.execute("""
        INSERT INTO cash_closures
        (user, opened_at, closed_at, opening_cash, cash_in_sales, cash_expenses, cash_counted, cash_diff, total_sales, payments_summary, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user, opened_at, closed_at, int(opening_cash), int(cash_in_sales), int(cash_expenses or 0), int(cash_counted), int(cash_diff), int(total_sales), ps_json, notes or "", now))
    conn.commit()
    return c.lastrowid
# ---------------- sale_payments helper ----------------
def add_sale_payment(sale_id, method, amount, details=None):
    """Registra un pago para una venta (amount en enteros)."""
    now = datetime.now().isoformat(sep=' ', timespec='seconds')
    c = conn.cursor()
    c.execute(
        "INSERT INTO sale_payments (sale_id, method, amount, details, created_at) VALUES (?, ?, ?, ?, ?)",
        (sale_id, method, int(amount), details, now)
    )
    conn.commit()
    return c.lastrowid


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

# CRUD y consultas mínimas para paid_orders
def add_paid_order(conn, customer_name, amount, note=None):
    now = datetime.now().isoformat(sep=' ', timespec='seconds')
    c = conn.cursor()
    c.execute("INSERT INTO paid_orders (customer_name, amount, note, created_at) VALUES (?, ?, ?, ?)",
              (customer_name, int(amount), note or "", now))
    conn.commit()
    return c.lastrowid

def delete_paid_order(conn, order_id):
    c = conn.cursor()
    c.execute("DELETE FROM paid_orders WHERE id=?", (order_id,))
    conn.commit()
    return c.rowcount

def get_paid_orders_for_period(conn, start_dt, end_dt):
    c = conn.cursor()
    c.execute("SELECT id, customer_name, amount, note, created_at FROM paid_orders WHERE created_at BETWEEN ? AND ? ORDER BY created_at ASC",
              (start_dt, end_dt))
    return c.fetchall()

def sum_paid_orders_for_period(conn, start_dt, end_dt):
    c = conn.cursor()
    c.execute("SELECT COALESCE(SUM(amount),0) as total FROM paid_orders WHERE created_at BETWEEN ? AND ?", (start_dt, end_dt))
    row = c.fetchone()
    try:
        return int(row['total'] or 0)
    except Exception:
        return int(row[0] or 0)

def get_total_sales_for_period(conn, start_dt, end_dt):
    """
    Suma la tabla sales.total en el periodo. Si no tienes tabla sales, devuelve 0.
    """
    c = conn.cursor()
    try:
        c.execute("SELECT COALESCE(SUM(total),0) as total_sales FROM sales WHERE created_at BETWEEN ? AND ?", (start_dt, end_dt))
        row = c.fetchone()
        try:
            return int(row['total_sales'] or 0)
        except Exception:
            return int(row[0] or 0)
    except Exception:
        return 0

def export_paid_orders_csv(conn, path, start_dt, end_dt):
    rows = get_paid_orders_for_period(conn, start_dt, end_dt)
    total = sum_paid_orders_for_period(conn, start_dt, end_dt)
    total_sales = get_total_sales_for_period(conn, start_dt, end_dt)
    diff = total_sales - total
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["Cliente","Monto","Nota","Fecha"])
        for r in rows:
            rr = dict(r) if hasattr(r, 'keys') else r
            if isinstance(rr, dict):
                w.writerow([rr.get('customer_name'), rr.get('amount'), rr.get('note'), rr.get('created_at')])
            else:
                w.writerow([rr[1], rr[2], rr[3], rr[4]])
        w.writerow([])
        w.writerow(["Resumen"])
        w.writerow(["Total pagos pedidos", total])
        w.writerow(["Total ventas periodo", total_sales])
        w.writerow(["Diferencia (ventas - pagos pedidos)", diff])
    return path
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

# def format_money(value):
#     """Formatea entero a '7.000'."""
#     try:
#         n = int(round(float(value)))
#         return f"{n:,}".replace(",", ".")
#     except Exception:
#         return "0"

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
        val = float(value)
        if val > 1000000:  # por ejemplo si está en centavos
            val /= 100
        return f"{int(val):,}".replace(",", ".")
    except Exception:
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
        self.root.title("Rhino")
        self.root.geometry("1024x600")




        

            # Fuente global
        default_font = tkfont.Font(family="Segoe UI", size=10)
        root.option_add("*Font", default_font)
    
        # Colores (puedes cambiar aquí)
        PRIMARY = "#2B7A78"    # verde oscuro
        ACCENT = "#17252A"     # casi negro
        BG = "#F6F6F6"         # fondo claro
        CARD = "#FFFFFF"       # tarjetas/blanco
    
        root.configure(bg=BG)
    
        # Estilo ttk
        style = ttk.Style()
        style.theme_use('default')  # usa default para control total


        # Configurar estilos
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD, relief="flat")
        style.configure("Header.TLabel", background=BG, font=("Segoe UI", 14, "bold"), foreground=ACCENT)
        style.configure("TLabel", background=BG, foreground=ACCENT)
        style.configure("Card.TLabel", background=CARD, foreground=ACCENT)
        style.configure("TButton",  background=PRIMARY, foreground="white", padding=8, relief="flat")
        # botón principal con estilo personalizado
        style.map("TButton",    background=[("active", "#1f5f5d"), ("pressed", "#144F4D")])
    
        # Contenedor principal
        container = ttk.Frame(root, padding=1, style="TFrame")
        container.pack(fill="both")
    
        # Header
        # header = ttk.Label(container, text="Rhino POS", style="Header.TLabel")
        # header.pack(anchor="w", pady=(4,0))

        # Abrir imagen (puede ser PNG o JPG)
      
        # Card (simula tarjeta con fondo blanco)
        # card = ttk.Frame(container, style="Card.TFrame", padding=12)
        # card.pack(fill="x", pady=(0,12))
    
        # Contenido de la tarjeta
        # name_label = ttk.Label(card, text="Artículo", style="Card.TLabel")
        # name_label.grid(row=0, column=0, sticky="w")
        # price_label = ttk.Label(card, text="$ 12.000", style="Card.TLabel")
        # price_label.grid(row=0, column=1, sticky="e")
    
        # desc = ttk.Label(card, text="Descripción breve del producto.", style="Card.TLabel")
        # desc.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6,0))
    
        # Separador
        # sep = ttk.Separator(container, orient="horizontal")
        # sep.pack(fill="x", pady=8)
    
        # Botones
        # btn_frame = ttk.Frame(container, style="TFrame")
        # btn_frame.pack(fill="x")
    
        # add_btn = ttk.Button(btn_frame, text="Agregar", command=lambda: print("Agregar"))
        # add_btn.pack(side="left", padx=(0,10))
    
        # pay_btn = ttk.Button(btn_frame, text="Pagar", command=lambda: print("Pagar"))
        # pay_btn.pack(side="left")
    
        # Pie con info
        # footer = ttk.Label(container, text="Status: listo", style="TLabel")
        # footer.pack(anchor="w", pady=(12,0))













        # ===================== NAVBAR SUPERIOR =====================
        navbar = ttk.Frame(self.root, padding=5, )
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
        ttk.Button(navbar, text="✍️ REGISTRO MANUAL", command=self.open_calculator_mode).pack(side=tk.LEFT, padx=0)
                # Separador visual
        # ttk.Separator(navbar, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(navbar, text="📦 + PRODUCTO", command=self.open_add_product_window).pack(side=tk.LEFT, padx=0)
        ttk.Button(navbar, text="💰 CREDITOS", command=self.open_credits_window).pack(side=tk.LEFT, padx=0)
        ttk.Button(navbar, text="📉 DEUDAS", command=self.open_debts_window).pack(side=tk.LEFT, padx=0)
        ttk.Button(navbar, text="💸 GASTOS", command=self.open_outflow_dialog).pack(side=tk.LEFT, padx=0)
        ttk.Button(navbar, text="📦 PEDIDOS", command=self.open_paid_orders_window).pack(side=tk.LEFT, padx=0)


        
        # Separador visual
        # ttk.Separator(navbar, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=8)
        
        # Grupo 2 - Gestión / Administración
        ttk.Button(navbar, text="📊 ESTADISTICA", command=self.open_stats_window).pack(side=tk.LEFT, padx=0)

        ttk.Button(navbar, text="🏭 PROVEEDORES", command=self.open_suppliers_window).pack(side=tk.LEFT, padx=0)
        # ttk.Button(navbar, text="👥 CLIENTES", command=self.open_customer_window).pack(side=tk.LEFT, padx=1)
        ttk.Button(navbar, text="🗂️ CATEGORIAS",  command=self.manage_categories_window).pack(side=tk.LEFT, padx=0)
        ttk.Button(navbar, text="🧾 HISTORIAL", command=self.open_history_window).pack(side=tk.LEFT, padx=0)
                # Separador visual
        # ttk.Separator(navbar, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Button(navbar, text="💰 CIERRE DE CAJA", command=self.open_cash_closure_window).pack(side=tk.LEFT, padx=0, pady=0)



        
        # Separador final y botón de salida
        # ttk.Separator(navbar, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=8)

        
        ttk.Button(navbar, text="🚪 SALIR", command=self.root.destroy).pack(side=tk.RIGHT, padx=0)
        imagen = Image.open("img/rhinoo.png")
        imagen = imagen.resize((150, 40))
        imagen_tk = ImageTk.PhotoImage(imagen)
        
        label = tk.Label(root, image=imagen_tk)
        label.imagen = imagen_tk  # Mantener referencia
        # label.pack(pady=0)
        label.pack(side="top",anchor='w', padx=0, pady=0)
        
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
        ttk.Label(left, text="", font=(None, 12, 'bold')).pack(pady=(0,0))
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
        # ttk.Label(center, text="Variedades Sembrador", font=(None, 12, 'bold')).pack(anchor=tk.W)
        sf = ttk.Frame(center)
        sf.pack(fill=tk.X, pady=0)
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
        self.products_tree.column('Articulo', width=90)
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
        ttk.Label(right, text="CARRITO", font=(None, 12, 'bold')).pack()
        self.cart_listbox = tk.Listbox(right, width=80, height=19)
        self.cart_listbox.pack(pady=6)
        
        ttk.Button(right, text="Eliminar seleccionado", command=self.remove_selected_cart_item).pack(side="bottom",fill=tk.X, pady=3)
        ttk.Button(right, text="Vaciar carrito", command=self.clear_cart).pack(side="bottom",fill=tk.X, pady=3)
        self.total_var = tk.StringVar(value="Total: $0")
        ttk.Label(right, textvariable=self.total_var, font=(None, 25, 'bold')).pack(side="bottom",pady=6)
        ttk.Button(right,text="Finalizar venta (Ctrl+Enter)", command=self.checkout).pack(side="bottom", fill=tk.X, pady=3, ipadx=15, ipady=20)
        
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




        """
        Ventana que lista pagos de pedidos por periodo, suma pagos, resta del total de ventas y permite exportar CSV.
        """
        def creator():
            win = tk.Toplevel(self.root)
            win.title("Pagos pedidos — Resumen y comparación con ventas")
            win.geometry("820x560")
            try: win.grab_set()
            except: pass
            win.lift(); win.focus_force()
    
            top = ttk.Frame(win, padding=8); top.pack(fill=tk.X)
            ttk.Label(top, text="Desde (YYYY-MM-DD HH:MM:SS):").pack(side=tk.LEFT)
            from_var = tk.StringVar(value=(datetime.now().strftime("%Y-%m-%d") + " 00:00:00"))
            ttk.Entry(top, textvariable=from_var, width=20).pack(side=tk.LEFT, padx=6)
            ttk.Label(top, text="Hasta:").pack(side=tk.LEFT)
            to_var = tk.StringVar(value=(datetime.now().strftime("%Y-%m-%d") + " 23:59:59"))
            ttk.Entry(top, textvariable=to_var, width=20).pack(side=tk.LEFT, padx=6)
            ttk.Button(top, text="Buscar / Actualizar", command=lambda: load_list()).pack(side=tk.LEFT, padx=8)
            ttk.Button(top, text="Exportar CSV", command=lambda: do_export()).pack(side=tk.RIGHT, padx=6)
            # Botón nuevo pedido (reemplazar la llamada actual)
            ttk.Button(top, text="Nuevo pedido", command=lambda: self.open_add_edit_order_dialog(load_list, None, win)).pack(fill=tk.X, pady=4)
            
            # Botón editar seleccionado
            ttk.Button(top, text="Editar seleccionado", command=lambda: self.open_add_edit_order_dialog(load_list, get_selected_id(), win)).pack(fill=tk.X, pady=4)
            
    
            # Listado central
            tree = ttk.Treeview(win, columns=('customer','order_id','amount','method','note','created_at'), show='headings', height=18)
            for c in ('customer','order_id','amount','method','note','created_at'):
                tree.heading(c, text=c.capitalize())
            tree.column('customer', width=220)
            tree.column('order_id', width=80, anchor=tk.CENTER)
            tree.column('amount', width=120, anchor=tk.E)
            tree.column('method', width=120)
            tree.column('note', width=200)
            tree.column('created_at', width=160)
            tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6,0))
    
            # resumen inferior
            sumf = ttk.Frame(win, padding=8); sumf.pack(fill=tk.X)
            payments_total_var = tk.StringVar(value="Pedidos pagados: $0")
            sales_total_var = tk.StringVar(value="Ventas periodo: $0")
            diff_var = tk.StringVar(value="Apoyo: $0")
            ttk.Label(sumf, textvariable=payments_total_var, font=(None, 11, "bold")).pack(anchor=tk.W)
            ttk.Label(sumf, textvariable=sales_total_var, font=(None, 10)).pack(anchor=tk.W, pady=(2,0))
            ttk.Label(sumf, textvariable=diff_var, font=(None, 11, "bold")).pack(anchor=tk.W, pady=(4,0))




            
    
            # helper: limpiar
            def clear():
                for iid in tree.get_children(): tree.delete(iid)
    
            def load_list():
                clear()
                start_dt = from_var.get().strip()
                end_dt = to_var.get().strip()
                if not start_dt or not end_dt:
                    messagebox.showwarning("Fechas", "Ingresa rango válido (desde y hasta).")
                    return
                rows = get_order_payments_list_for_period(conn, start_dt, end_dt)
                total_payments = 0
                for r in rows:
                    rr = dict(r) if hasattr(r, 'keys') else r
                    customer = rr.get('customer_name') if isinstance(rr, dict) else rr[2]
                    order_id = rr.get('order_id') if isinstance(rr, dict) else rr[1]
                    amount = int(rr.get('amount') if isinstance(rr, dict) else rr[3])
                    method = rr.get('method') if isinstance(rr, dict) else rr[4]
                    note = rr.get('note') if isinstance(rr, dict) else rr[5]
                    when = rr.get('created_at') if isinstance(rr, dict) else rr[6]
                    tree.insert('', tk.END, values=(customer, order_id, f"${format_money(amount)}", method, note, when))
                    total_payments += amount
    
                total_sales = get_total_sales_for_period(conn, start_dt, end_dt)
                diff = int(total_sales) - int(total_payments)
    
                payments_total_var.set(f"Pedidos pagados (suma): ${format_money(total_payments)}")
                sales_total_var.set(f"Ventas periodo: ${format_money(total_sales)}")
                if diff < 0:
                    diff_var.set(f"Diferencia: -${format_money(abs(diff))} (déficit)")
                else:
                    diff_var.set(f"Diferencia: ${format_money(diff)}")
    
            def do_export():
                start_dt = from_var.get().strip(); end_dt = to_var.get().strip()
                if not start_dt or not end_dt:
                    messagebox.showwarning("Fechas", "Ingresa rango válido (desde y hasta).")
                    return
                from tkinter import filedialog
                path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=f"pedidos_pagos_{datetime.now().strftime('%Y%m%d')}.csv", filetypes=[("CSV","*.csv")])
                if not path: return
                try:
                    export_orders_payments_summary_csv(conn, path, start_dt, end_dt)
                    messagebox.showinfo("Exportado", f"CSV guardado en:\n{path}")
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo exportar:\n{e}")
    
            # atajos
            win.bind("<Escape>", lambda e: win.destroy())
            win.bind("<Return>", lambda e: load_list())
    
            # inicializar con hoy
            load_list()
            return win
        return self.open_window_once("orders_payments_summary", creator)
    

    
        # -----------------------
    # Métodos para la clase POSApp
    # -----------------------
    
    def open_add_edit_order_dialog(self, refresh_cb, order_id=None, parent_win=None):
        """
        Diálogo para crear o editar un pedido.
        - refresh_cb: función que se llama al guardar para recargar la lista (ej: load_list)
        - order_id: si es None crea nuevo; si es int, edita el pedido
        - parent_win: widget padre (opcional)
        """
        parent = parent_win or self.root
        ed = tk.Toplevel(parent)
        ed.title("Editar pedido" if order_id else "Nuevo pedido")
        ed.geometry("440x320")
        ed.resizable(False, False)
        try: ed.transient(parent)
        except: pass
        try: ed.grab_set()
        except: pass
        ed.lift(); ed.focus_force()
    
        existing = None
        if order_id:
            try:
                existing = get_order(conn, order_id)
            except Exception:
                existing = None
    
        name_var = tk.StringVar(value=(existing['customer_name'] if existing else ""))
        contact_var = tk.StringVar(value=(existing['contact'] if existing else ""))
        desc_var = tk.StringVar(value=(existing['description'] if existing else ""))
        total_var = tk.StringVar(value=str(existing['total_expected'] if existing else "0"))
    
        frm = ttk.Frame(ed, padding=12); frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text="Cliente:").grid(row=0, column=0, sticky=tk.W, pady=(0,6))
        ttk.Entry(frm, textvariable=name_var, width=42).grid(row=0, column=1, pady=(0,6))
        ttk.Label(frm, text="Contacto:").grid(row=1, column=0, sticky=tk.W, pady=(0,6))
        ttk.Entry(frm, textvariable=contact_var, width=42).grid(row=1, column=1, pady=(0,6))
        ttk.Label(frm, text="Descripción:").grid(row=2, column=0, sticky=tk.W, pady=(0,6))
        ttk.Entry(frm, textvariable=desc_var, width=42).grid(row=2, column=1, pady=(0,6))
        ttk.Label(frm, text="Total esperado:").grid(row=3, column=0, sticky=tk.W, pady=(0,6))
        ttk.Entry(frm, textvariable=total_var, width=20).grid(row=3, column=1, sticky=tk.W, pady=(0,6))
    
        btnf = ttk.Frame(frm); btnf.grid(row=4, column=0, columnspan=2, pady=(12,0))
        def on_save():
            name = name_var.get().strip()
            contact = contact_var.get().strip()
            desc = desc_var.get().strip()
            total = parse_money_to_int(total_var.get())
            if not name:
                messagebox.showwarning("Falta", "Ingrese el nombre del cliente.")
                return
            try:
                if order_id:
                    update_order(conn, order_id,
                                 customer_name=name,
                                 contact=contact,
                                 description=desc,
                                 total_expected=total)
                    messagebox.showinfo("Actualizado", "Pedido actualizado correctamente.")
                else:
                    nid = create_order(conn, name, contact, desc, total)
                    messagebox.showinfo("Creado", f"Pedido creado (ID: {nid})")
                try:
                    if callable(refresh_cb):
                        refresh_cb()
                except Exception:
                    pass
                ed.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar el pedido:\n{e}")
    
        ttk.Button(btnf, text="Guardar (Enter)", command=on_save).pack(side=tk.LEFT, padx=6)
        ttk.Button(btnf, text="Cancelar (Esc)", command=ed.destroy).pack(side=tk.LEFT, padx=6)
        ed.bind("<Return>", lambda e: on_save())
        ed.bind("<Escape>", lambda e: ed.destroy())
        ed.after(40, lambda: (ed.focus_force(), ed.grab_set(), ed.lift()))
        return ed
    
    
    def open_orders_window(self):
        """
        Ventana CRUD de pedidos y pagos. Incluye:
         - lista de pedidos
         - crear/editar/eliminar pedidos
         - agregar pagos a pedidos
         - exportar CSV pedidos y pagos
        """
        def creator():
            win = tk.Toplevel(self.root)
            win.title("Pedidos / Órdenes")
            win.geometry("980x620")
            try: win.grab_set()
            except: pass
            win.lift(); win.focus_force()
    
            top = ttk.Frame(win, padding=6); top.pack(fill=tk.X)
            ttk.Label(top, text="Buscar:").pack(side=tk.LEFT)
            qvar = tk.StringVar()
            qentry = ttk.Entry(top, textvariable=qvar, width=30); qentry.pack(side=tk.LEFT, padx=6)
            ttk.Label(top, text="Desde:").pack(side=tk.LEFT, padx=(12,0))
            from_var = tk.StringVar(value=(datetime.now().strftime("%Y-%m-%d") + " 00:00:00"))
            from_entry = ttk.Entry(top, textvariable=from_var, width=18); from_entry.pack(side=tk.LEFT, padx=6)
            ttk.Label(top, text="Hasta:").pack(side=tk.LEFT)
            to_var = tk.StringVar(value=(datetime.now().strftime("%Y-%m-%d") + " 23:59:59"))
            to_entry = ttk.Entry(top, textvariable=to_var, width=18); to_entry.pack(side=tk.LEFT, padx=6)
            ttk.Button(top, text="Buscar / Actualizar", command=lambda: load_list()).pack(side=tk.LEFT, padx=8)
            ttk.Button(top, text="Exportar pedidos (CSV)", command=lambda: self._export_orders_csv(from_var.get(), to_var.get())).pack(side=tk.RIGHT, padx=6)
            ttk.Button(top, text="Exportar pagos (CSV)", command=lambda: self._export_order_payments_csv(from_var.get(), to_var.get())).pack(side=tk.RIGHT)
    
            mid = ttk.Frame(win, padding=6); mid.pack(fill=tk.BOTH, expand=True)
            left = ttk.Frame(mid); left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,6))
            right = ttk.Frame(mid, width=320); right.pack(side=tk.LEFT, fill=tk.Y)
    
            cols = ('id','customer','contact','total_expected','total_paid','status','created_at')
            tree = ttk.Treeview(left, columns=cols, show='headings', height=20)
            for c in cols:
                tree.heading(c, text=c.capitalize())
            tree.column('id', width=50, anchor=tk.CENTER)
            tree.column('customer', width=220)
            tree.column('total_expected', width=110, anchor=tk.E)
            tree.column('total_paid', width=110, anchor=tk.E)
            tree.pack(fill=tk.BOTH, expand=True)
    
            # función para obtener id seleccionado
            def get_selected_id():
                sel = tree.selection()
                if not sel:
                    messagebox.showwarning("Seleccionar", "Selecciona un pedido primero.")
                    return None
                try:
                    vals = tree.item(sel[0], "values")
                    return int(vals[0])
                except Exception:
                    messagebox.showerror("Error", "No se pudo obtener el ID del pedido.")
                    return None
    
            # right side: detalle y acciones
            ttk.Label(right, text="Detalle / Acciones", font=(None, 11, 'bold')).pack(anchor=tk.W)
            details = tk.Text(right, height=8, wrap='word'); details.pack(fill=tk.X, pady=(6,4))
            ttk.Label(right, text="Pagos registrados:").pack(anchor=tk.W)
            payments_tree = ttk.Treeview(right, columns=('id','method','amount','created_at'), show='headings', height=8)
            payments_tree.heading('method', text='Método'); payments_tree.heading('amount', text='Monto'); payments_tree.heading('created_at', text='Fecha')
            payments_tree.column('amount', anchor=tk.E, width=100)
            payments_tree.pack(fill=tk.X, pady=(6,4))
    
            af = ttk.Frame(right); af.pack(fill=tk.X, pady=(6,0))
            ttk.Button(af, text="Nuevo pedido", command=lambda: self.open_add_edit_order_dialog(load_list, None, win)).pack(fill=tk.X, pady=4)
            ttk.Button(af, text="Editar seleccionado", command=lambda: self.open_add_edit_order_dialog(load_list, get_selected_id(), win)).pack(fill=tk.X, pady=4)
            ttk.Button(af, text="Eliminar pedido", command=lambda: do_delete(get_selected_id())).pack(fill=tk.X, pady=4)
            ttk.Separator(af, orient='horizontal').pack(fill=tk.X, pady=6)
            ttk.Button(af, text="Agregar pago", command=lambda: open_add_payment(get_selected_id())).pack(fill=tk.X, pady=4)
            ttk.Button(af, text="Sumar pagos del día", command=lambda: show_sum_today()).pack(fill=tk.X, pady=4)
    
            # helpers internos
            def format_money_local(x):
                try:
                    return f"{int(x):,}".replace(",", ".")
                except:
                    return str(x)
    
            def load_list():
                for iid in tree.get_children(): tree.delete(iid)
                q = qvar.get().strip() or None
                start = from_var.get().strip() or None
                end = to_var.get().strip() or None
                rows = get_orders(conn, q=q, start=start, end=end)
                for r in rows:
                    rr = dict(r)
                    tree.insert('', tk.END, values=(rr.get('id'), rr.get('customer_name'), rr.get('contact'),
                                                   f"${format_money(rr.get('total_expected') or 0)}",
                                                   f"${format_money(rr.get('total_paid') or 0)}",
                                                   rr.get('status'), rr.get('created_at')))
                details.delete('1.0', tk.END)
                payments_tree.delete(*payments_tree.get_children())
    
            def do_delete(order_id):
                if not order_id:
                    messagebox.showinfo("Seleccionar", "Selecciona un pedido")
                    return
                if not messagebox.askyesno("Confirmar", "¿Eliminar pedido y sus pagos?"): return
                delete_order(conn, order_id)
                load_list()
    
            def open_add_payment(order_id):
                if not order_id:
                    messagebox.showinfo("Seleccionar", "Selecciona un pedido")
                    return
                def do_save():
                    try:
                        m = method_var.get()
                        amt = parse_money_to_int(amount_var.get())
                        note = note_var.get().strip()
                        if amt <= 0:
                            messagebox.showwarning("Monto", "Ingresa monto válido"); return
                        add_order_payment(conn, order_id, m, amt, note)
                        messagebox.showinfo("Registrado", "Pago agregado")
                        ap.destroy(); load_list(); load_payments(order_id)
                    except Exception as e:
                        messagebox.showerror("Error", str(e))
                ap = tk.Toplevel(win); ap.title("Agregar pago"); ap.geometry("380x200")
                ttk.Label(ap, text="Método:").pack(anchor=tk.W, padx=8, pady=(8,0))
                method_var = tk.StringVar(value="Efectivo")
                ttk.Combobox(ap, textvariable=method_var, values=["Efectivo","Transferencia","Otro"], state='readonly').pack(fill=tk.X, padx=8)
                ttk.Label(ap, text="Monto:").pack(anchor=tk.W, padx=8, pady=(8,0))
                amount_var = tk.StringVar(value="0")
                ttk.Entry(ap, textvariable=amount_var).pack(fill=tk.X, padx=8)
                ttk.Label(ap, text="Nota (opcional):").pack(anchor=tk.W, padx=8, pady=(8,0))
                note_var = tk.StringVar()
                ttk.Entry(ap, textvariable=note_var).pack(fill=tk.X, padx=8)
                btnf = ttk.Frame(ap); btnf.pack(pady=10)
                ttk.Button(btnf, text="Guardar (Enter)", command=do_save).pack(side=tk.LEFT, padx=6)
                ttk.Button(btnf, text="Cancelar", command=ap.destroy).pack(side=tk.LEFT, padx=6)
                ap.bind("<Return>", lambda e: do_save()); ap.bind("<Escape>", lambda e: ap.destroy())
                ap.grab_set(); ap.focus_force()
    
            def load_payments(order_id):
                payments_tree.delete(*payments_tree.get_children())
                if not order_id: return
                rows = get_order_payments(conn, order_id)
                for r in rows:
                    rr = dict(r)
                    payments_tree.insert('', tk.END, values=(rr.get('id'), rr.get('method'), f"${format_money(rr.get('amount'))}", rr.get('created_at')))
    
            def show_detail():
                sel = tree.selection()
                if not sel:
                    details.delete('1.0', tk.END); payments_tree.delete(*payments_tree.get_children()); return
                oid = int(tree.item(sel[0], 'values')[0])
                row = get_order(conn, oid)
                details.delete('1.0', tk.END)
                if row:
                    rr = dict(row)
                    details.insert(tk.END, f"Cliente: {rr.get('customer_name')}\nContacto: {rr.get('contact')}\nDescripcion: {rr.get('description')}\nTotal esperado: ${format_money(rr.get('total_expected') or 0)}\nTotal pagado: ${format_money(rr.get('total_paid') or 0)}\nEstado: {rr.get('status')}\nCreado: {rr.get('created_at')}")
                load_payments(oid)
    
            def show_sum_today():
                today = datetime.now().strftime("%Y-%m-%d")
                total = sum_order_payments_for_date(conn, today)
                messagebox.showinfo("Total pagos hoy", f"Total recibido hoy por pedidos: ${format_money(total)}")
    
            # bindings
            tree.bind('<<TreeviewSelect>>', lambda e: show_detail())
            tree.bind('<Double-1>', lambda e: self.open_add_edit_order_dialog(load_list, get_selected_id(), win))
            load_list()
            return win
    
        return self.open_window_once("orders", creator)
    





    def open_paid_orders_window(self):
        """
        Ventana sencilla: listar pedidos pagados (periodo), agregar, eliminar, sumar y comparar con ventas, exportar CSV.
        """
        def creator():
            win = tk.Toplevel(self.root)
            win.title("Pedidos pagados — Resumen")
            win.geometry("760x520")
            try: win.grab_set()
            except: pass
            win.lift(); win.focus_force()
    
            top = ttk.Frame(win, padding=8); top.pack(fill=tk.X)
            ttk.Label(top, text="Desde (YYYY-MM-DD HH:MM:SS):").pack(side=tk.LEFT)
            from_var = tk.StringVar(value=(datetime.now().strftime("%Y-%m-%d") + " 00:00:00"))
            ttk.Entry(top, textvariable=from_var, width=20).pack(side=tk.LEFT, padx=6)
            ttk.Label(top, text="Hasta:").pack(side=tk.LEFT)
            to_var = tk.StringVar(value=(datetime.now().strftime("%Y-%m-%d") + " 23:59:59"))
            ttk.Entry(top, textvariable=to_var, width=20).pack(side=tk.LEFT, padx=6)
            ttk.Button(top, text="Actualizar", command=lambda: load_list()).pack(side=tk.LEFT, padx=8)
            ttk.Button(top, text="Exportar CSV", command=lambda: do_export()).pack(side=tk.RIGHT, padx=6)
    
            # tree
            cols = ('id','customer','amount','note','created')
            tree = ttk.Treeview(win, columns=cols, show='headings', height=16)
            tree.heading('id', text='ID'); tree.heading('customer', text='Cliente'); tree.heading('amount', text='Monto'); tree.heading('note', text='Nota'); tree.heading('created', text='Fecha')
            tree.column('id', width=40, anchor=tk.CENTER); tree.column('amount', width=120, anchor=tk.E); tree.column('customer', width=260)
            tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8,0))
    
            # bottom summary and actions
            sumf = ttk.Frame(win, padding=8); sumf.pack(fill=tk.X)
            paid_total_var = tk.StringVar(value="Pedidos pagados: $0")
            sales_total_var = tk.StringVar(value="Ventas periodo: $0")
            diff_var = tk.StringVar(value="Diferencia: $0")
            ttk.Label(sumf, textvariable=paid_total_var, font=(None,11,"bold")).pack(anchor=tk.W)
            ttk.Label(sumf, textvariable=sales_total_var).pack(anchor=tk.W, pady=(2,0))
            ttk.Label(sumf, textvariable=diff_var, font=(None,10,"bold")).pack(anchor=tk.W, pady=(6,0))
    
            btnf = ttk.Frame(win, padding=6); btnf.pack(fill=tk.X)
            ttk.Button(btnf, text="Agregar pedido pagado", command=lambda: open_add_dialog()).pack(side=tk.LEFT, padx=6)
            ttk.Button(btnf, text="Eliminar seleccionado", command=lambda: do_delete_selected()).pack(side=tk.LEFT)
            ttk.Button(btnf, text="Cerrar (Esc)", command=win.destroy).pack(side=tk.RIGHT)
    
            # helpers
            def clear():
                for i in tree.get_children(): tree.delete(i)
    
            def load_list():
                clear()
                start = from_var.get().strip(); end = to_var.get().strip()
                if not start or not end:
                    messagebox.showwarning("Fechas", "Ingrese un rango válido (desde/hasta).")
                    return
                rows = get_paid_orders_for_period(conn, start, end)
                total_payments = 0
                for r in rows:
                    rr = dict(r) if hasattr(r, 'keys') else r
                    if isinstance(rr, dict):
                        amt = int(rr.get('amount') or 0)
                        tree.insert('', tk.END, values=(rr.get('id'), rr.get('customer_name'), f"${format_money(amt)}", rr.get('note'), rr.get('created_at')))
                        total_payments += amt
                    else:
                        amt = int(rr[2] or 0)
                        tree.insert('', tk.END, values=(rr[0], rr[1], f"${format_money(amt)}", rr[3], rr[4]))
                        total_payments += amt
                # totals and comparison
                total_sales = get_total_sales_for_period(conn, start, end)
                paid_total_var.set(f"Pedidos pagados (suma): ${format_money(total_payments)}")
                sales_total_var.set(f"Ventas periodo: ${format_money(total_sales)}")
                diff = int(total_sales) - int(total_payments)
                if diff < 0:
                    diff_var.set(f"Diferencia: -${format_money(abs(diff))} (déficit)")
                else:
                    diff_var.set(f"Diferencia: ${format_money(diff)}")
    
            def open_add_dialog():
                d = tk.Toplevel(win); d.title("Agregar pedido pagado"); d.geometry("420x220")
                ttk.Label(d, text="Cliente:").pack(anchor=tk.W, padx=8, pady=(8,0))
                name_var = tk.StringVar(); ttk.Entry(d, textvariable=name_var).pack(fill=tk.X, padx=8)
                ttk.Label(d, text="Monto:").pack(anchor=tk.W, padx=8, pady=(8,0))
                amt_var = tk.StringVar(value="0"); ttk.Entry(d, textvariable=amt_var).pack(fill=tk.X, padx=8)
                ttk.Label(d, text="Nota (opcional):").pack(anchor=tk.W, padx=8, pady=(8,0))
                note_var = tk.StringVar(); ttk.Entry(d, textvariable=note_var).pack(fill=tk.X, padx=8)
                bf = ttk.Frame(d); bf.pack(pady=10)
                def save():
                    name = name_var.get().strip()
                    amt = parse_money_to_int(amt_var.get())
                    note = note_var.get().strip()
                    if not name or amt <= 0:
                        messagebox.showwarning("Datos", "Nombre y monto válido son requeridos."); return
                    add_paid_order(conn, name, amt, note)
                    d.destroy(); load_list()
                ttk.Button(bf, text="Guardar", command=save).pack(side=tk.LEFT, padx=6)
                ttk.Button(bf, text="Cancelar", command=d.destroy).pack(side=tk.LEFT, padx=6)
                d.bind("<Return>", lambda e: save()); d.bind("<Escape>", lambda e: d.destroy())
                d.grab_set(); d.focus_force()
    
            def do_delete_selected():
                sel = tree.selection()
                if not sel:
                    messagebox.showinfo("Seleccionar","Selecciona un pedido")
                    return
                oid = int(tree.item(sel[0], 'values')[0])
                if not messagebox.askyesno("Confirmar","Eliminar pedido seleccionado?"): return
                delete_paid_order(conn, oid)
                load_list()
    
            def do_export():
                start = from_var.get().strip(); end = to_var.get().strip()
                if not start or not end:
                    messagebox.showwarning("Fechas","Ingresa rango válido")
                    return
                from tkinter import filedialog
                path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=f"paid_orders_{datetime.now().strftime('%Y%m%d')}.csv", filetypes=[("CSV","*.csv")])
                if not path: return
                try:
                    export_paid_orders_csv(conn, path, start, end)
                    messagebox.showinfo("Exportado", f"CSV guardado en:\n{path}")
                except Exception as e:
                    messagebox.showerror("Error", str(e))
    
            win.bind("<Escape>", lambda e: win.destroy())
            load_list()
            return win
    
        # si tienes open_window_once en tu clase (evitar duplicados) úsalo, si no solo crea la ventana
        if hasattr(self, 'open_window_once'):
            return self.open_window_once("paid_orders", creator)
        else:
            return creator()
    


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
            btn = ttk.Button(self.cat_frame,text=btn_text, width=22, command=lambda c=cid, n=name: self.open_search_for_category(c, n))
            btn.pack(pady=3, ipady=6)
            # .pack(side="bottom", fill=tk.X, pady=3, ipadx=15, ipady=20)
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
           win.geometry('460x440')
           win.resizable(False, False)
           try: win.grab_set()
           except: pass
           win.transient(self.root)
           win.lift(); win.focus_force()
   
           # Listbox con scrollbar
           frame_list = ttk.Frame(win, padding=8)
           frame_list.pack(fill=tk.BOTH, expand=False)
           scrollbar = ttk.Scrollbar(frame_list, orient=tk.VERTICAL)
           listbox = tk.Listbox(frame_list, width=50, height=12, yscrollcommand=scrollbar.set)
           scrollbar.config(command=listbox.yview)
           listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
           scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
   
           # Load / refresh
           def refresh():
               listbox.delete(0, tk.END)
               try:
                   cats = get_categories()
               except Exception:
                   # si get_categories espera conn: intentar con conn global o self.conn
                   try:
                       cats = get_categories(conn)
                   except:
                       try:
                           cats = get_categories(self.conn)
                       except:
                           cats = []
               # cats puede venir como [(id,name),...] o list of dicts
               for c in cats:
                   try:
                       if isinstance(c, dict):
                           cid = c.get('id'); name = c.get('name')
                       else:
                           # tupla/row
                           cid = c[0]; name = c[1]
                       listbox.insert(tk.END, f"{cid} - {name}")
                   except Exception:
                       # forma fallback
                       listbox.insert(tk.END, str(c))
   
           refresh()
   
           # Formulario de edición/creación
           form = ttk.Frame(win, padding=(8,6))
           form.pack(fill=tk.X)
           ttk.Label(form, text='Nombre:').grid(row=0, column=0, sticky=tk.W)
           name_var = tk.StringVar()
           entry = ttk.Entry(form, textvariable=name_var, width=36)
           entry.grid(row=0, column=1, sticky=tk.W, padx=(6,0))
           entry.bind('<Return>', lambda e: add_or_update())
   
           ttk.Label(form, text='Color (opcional hex):').grid(row=1, column=0, sticky=tk.W, pady=(6,0))
           color_var = tk.StringVar(value="")
           color_entry = ttk.Entry(form, textvariable=color_var, width=16)
           color_entry.grid(row=1, column=1, sticky=tk.W, padx=(6,0), pady=(6,0))
   
           # Estado: si hay selección estamos en modo editar
           editing_id = {'id': None}
   
           def select_current():
               sel = listbox.curselection()
               if not sel:
                   editing_id['id'] = None
                   name_var.set('')
                   color_var.set('')
                   return
               text = listbox.get(sel[0])
               try:
                   cid = int(text.split(' - ')[0])
               except:
                   # fallback: intentar encontrar en get_categories
                   try:
                       cats = get_categories()
                   except:
                       try: cats = get_categories(conn)
                       except:
                           try: cats = get_categories(self.conn)
                           except: cats = []
                   cid = None
                   for c in cats:
                       if isinstance(c, dict) and c.get('name') in text:
                           cid = c.get('id'); break
                       elif isinstance(c, (list,tuple)) and str(c[1]) in text:
                           cid = c[0]; break
               if cid is None:
                   editing_id['id'] = None
                   return
               editing_id['id'] = cid
               # obtener nombre y color del helper
               try:
                   cats = get_categories()
               except:
                   try: cats = get_categories(conn)
                   except:
                       try: cats = get_categories(self.conn)
                       except: cats = []
               for c in cats:
                   try:
                       if (isinstance(c, dict) and c.get('id') == cid) or (not isinstance(c, dict) and c[0] == cid):
                           name = c.get('name') if isinstance(c, dict) else c[1]
                           color = c.get('color') if isinstance(c, dict) else (c[2] if len(c)>2 else "")
                           name_var.set(name or "")
                           color_var.set(color or "")
                           break
                   except:
                       pass
   
           # Add or update depending on selection
           def add_or_update():
               name = name_var.get().strip()
               color = color_var.get().strip() or None
               if not name:
                   messagebox.showwarning('Aviso', 'Escribe un nombre')
                   return
               cid = editing_id.get('id')
               if cid:
                   # UPDATE
                   try:
                       # prefer helper update_category
                       if 'update_category' in globals():
                           if color is not None:
                               update_category(conn if 'conn' in globals() else self.conn, cid, name=name, color=color, sort_order=None)
                           else:
                               update_category(conn if 'conn' in globals() else self.conn, cid, name=name)
                       else:
                           # fallback SQL
                           cur = (conn if 'conn' in globals() else self.conn).cursor()
                           if color is not None:
                               cur.execute("UPDATE categories SET name=?, color=? WHERE id=?", (name, color, cid))
                           else:
                               cur.execute("UPDATE categories SET name=? WHERE id=?", (name, cid))
                           (conn if 'conn' in globals() else self.conn).commit()
                       messagebox.showinfo('Editado', 'Categoría actualizada')
                   except Exception as e:
                       messagebox.showerror('Error', f'No se pudo actualizar: {e}')
               else:
                   # INSERT
                   try:
                       if 'add_category' in globals():
                           add_category(name)
                       else:
                           cur = (conn if 'conn' in globals() else self.conn).cursor()
                           cur.execute("INSERT INTO categories (name) VALUES (?)", (name,))
                           (conn if 'conn' in globals() else self.conn).commit()
                       messagebox.showinfo('Creada', 'Categoría creada')
                   except Exception as e:
                       messagebox.showerror('Error', f'No se pudo crear categoría: {e}')
               # limpiar y refrescar
               name_var.set(''); color_var.set(''); editing_id['id'] = None
               refresh()
               try: self.reload_category_buttons()
               except: pass
   
           def delete():
               sel = listbox.curselection()
               if not sel:
                   messagebox.showwarning('Aviso', 'Selecciona una categoría')
                   return
               text = listbox.get(sel[0])
               try:
                   cid = int(text.split(' - ')[0])
               except:
                   messagebox.showerror('Error', 'Formato de entrada inesperado'); return
               if messagebox.askyesno('Confirmar', 'Eliminar categoría? (No borra productos)'):
                   try:
                       if 'delete_category' in globals():
                           delete_category(cid)
                       else:
                           cur = (conn if 'conn' in globals() else self.conn).cursor()
                           cur.execute("DELETE FROM categories WHERE id=?", (cid,))
                           (conn if 'conn' in globals() else self.conn).commit()
                       messagebox.showinfo('Eliminada', 'Categoría eliminada')
                   except Exception as e:
                       messagebox.showerror('Error', f'No se pudo eliminar: {e}')
                   # limpiar y refrescar
                   name_var.set(''); color_var.set(''); editing_id['id'] = None
                   refresh()
                   try: self.reload_category_buttons()
                   except: pass
   
           # Botones
           btnf = ttk.Frame(win, padding=(8,6))
           btnf.pack(fill=tk.X)
           ttk.Button(btnf, text='Nuevo', command=lambda: (editing_id.update({'id': None}), name_var.set(''), color_var.set(''))).pack(side=tk.LEFT, padx=6)
           ttk.Button(btnf, text='Guardar / Renombrar', command=add_or_update).pack(side=tk.LEFT, padx=6)
           ttk.Button(btnf, text='Eliminar', command=delete).pack(side=tk.LEFT, padx=6)
           ttk.Button(btnf, text='Cerrar (Esc)', command=win.destroy).pack(side=tk.RIGHT, padx=6)
   
           # Bindings
           listbox.bind('<<ListboxSelect>>', lambda e: select_current())
           listbox.bind('<Double-Button-1>', lambda e: select_current())
           win.bind('<Escape>', lambda e: win.destroy())
   
           # focus
           entry.focus_set()
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
    
        # sumf = ttk.Frame(win, padding=8); sumf.pack(fill=tk.X)
        # total_out_var = tk.StringVar(value="Salidas: $0")
        # ttk.Label(sumf, textvariable=total_out_var, font=(None, 10)).pack(anchor=tk.W, pady=(2,0))
        # btns_frame = ttk.Frame(sumf)

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
            total_sales_var.set(f"Ventas: {cnt}")
            total_sales_var.set(f"Total: ${format_money(total_amt)}")
            
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
    
    
    
    def open_payment_dialog_and_finalize(self, cart_total, sale_id=None):
        """
        Abre un diálogo para cobrar la venta.
        - cart_total: total en enteros (p: 100000) o string con formato; se normaliza con parse_money_to_int.
        - sale_id: si ya creaste el registro de venta y tienes su id, pásalo para asociar el pago.
        """
        # normalizar total
        try:
            total = parse_money_to_int(cart_total) if not isinstance(cart_total, (int,float)) else int(cart_total)
        except Exception:
            # si no tienes parse_money_to_int, intenta quitar símbolos y convertir
            s = str(cart_total).replace("$","").replace(",","").strip()
            total = int(float(s))
    
        dlg = tk.Toplevel(self.root)
        dlg.title("Finalizar venta - Cobro")
        dlg.geometry("420x220")
        try: dlg.grab_set()
        except: pass
        dlg.transient(self.root)
        dlg.lift(); dlg.focus_force()
    
        frm = ttk.Frame(dlg, padding=10); frm.pack(fill=tk.BOTH, expand=True)
    
        ttk.Label(frm, text=f"Total a cobrar: ${format_money(total)}", font=(None,12,"bold")).pack(anchor=tk.W, pady=(0,8))
    
        # monto a cobrar (por defecto el total, permite editar para pagos parciales)
        ttk.Label(frm, text="Monto a recibir:").pack(anchor=tk.W)
        amount_var = tk.StringVar(value=str(total))
        amount_entry = ttk.Entry(frm, textvariable=amount_var, justify=tk.RIGHT, width=16, font=(None,11))
        amount_entry.pack(anchor=tk.W, pady=(0,6))
    
        # Métodos de pago: efectivo (default), transferencia, tarjeta
        ttk.Label(frm, text="Método de pago:").pack(anchor=tk.W, pady=(6,0))
        method_var = tk.StringVar(value="Efectivo")
        methods = [("Efectivo","Efectivo"), ("Transferencia","Transferencia"), ("Tarjeta","Tarjeta")]
        rb_frame = ttk.Frame(frm); rb_frame.pack(anchor=tk.W, pady=(2,6))
        for text, val in methods:
            ttk.Radiobutton(rb_frame, text=text, value=val, variable=method_var).pack(side=tk.LEFT, padx=(0,8))
    
        # Mensaje de ayuda
        help_lbl = ttk.Label(frm, text="Presiona ENTER para cobrar rápido (por defecto Efectivo).", foreground="#333")
        help_lbl.pack(anchor=tk.W, pady=(6,4))
    
        # Función que procesa el pago y guarda en DB
        def process_and_close(event=None):
            # leer monto y método
            try:
                amt = parse_money_to_int(amount_var.get()) if not isinstance(amount_var.get(), (int,float)) else int(amount_var.get())
            except Exception:
                # limpiar y convertir
                s = str(amount_var.get()).replace("$","").replace(",","").strip()
                try:
                    amt = int(float(s))
                except:
                    messagebox.showerror("Monto inválido", "Ingresa un monto válido."); return
    
            method = method_var.get() or "Efectivo"
    
            # validar monto mínimo
            if amt <= 0:
                messagebox.showwarning("Monto", "El monto debe ser mayor a cero."); return
    
            cur = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
            try:
                # Si no existe sale_id, crea la venta básica (adaptar campos según tu tabla 'sales')
                if not sale_id:
                    # Ajusta los campos INSERT según tu esquema de 'sales'
                    cur.execute("""
                        INSERT INTO sales (total_amount, status, created_at)
                        VALUES (?, ?, ?)
                    """, (total, 'open', now))
                    sale_id_local = cur.lastrowid
                else:
                    sale_id_local = sale_id
    
                # Insertar registro del pago en tabla sale_payments (ajusta nombres si es distinto)
                cur.execute("""
                    INSERT INTO sale_payments (sale_id, method, amount, created_at)
                    VALUES (?, ?, ?, ?)
                """, (sale_id_local, method, amt, now))
    
                # calcular pagos totales ya registrados para la venta
                cur.execute("SELECT IFNULL(SUM(amount), 0) as paid_total FROM sale_payments WHERE sale_id = ?", (sale_id_local,))
                paid = cur.fetchone()
                paid_total = paid['paid_total'] if isinstance(paid, dict) and 'paid_total' in paid else (paid[0] if paid else 0)
    
                # Si la suma de pagos >= total, marcar venta como 'paid' (o 'closed')
                if paid_total >= total:
                    cur.execute("UPDATE sales SET status = ?, paid_at = ? WHERE id = ?", ('paid', now, sale_id_local))
    
                conn.commit()
            except Exception as e:
                conn.rollback()
                messagebox.showerror("Error", f"No se pudo registrar el pago: {e}")
                return
    
            # Actualizar UI local: refrescar carrito, totals, etc. (llama a tus funciones)
            try:
                # Ejemplos de posibles funciones que tengas: refresh_sales_list, clear_cart, update_totals
                if hasattr(self, 'refresh_sales_list'): self.refresh_sales_list()
                if hasattr(self, 'clear_cart'): self.clear_cart()
                if hasattr(self, 'update_totals'): self.update_totals()
            except:
                pass
    
            messagebox.showinfo("Cobro", f"Pago registrado.\nMétodo: {method}\nMonto: ${format_money(amt)}")
            dlg.destroy()
    
        # Bind ENTER on the dialog and on the amount_entry to process quickly
        dlg.bind("<Return>", process_and_close)
        amount_entry.bind("<Return>", process_and_close)
    
        # Botones
        btns = ttk.Frame(frm); btns.pack(fill=tk.X, pady=(8,0))
        ttk.Button(btns, text="Cobrar (ENTER)", command=process_and_close).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(btns, text="Cancelar", command=dlg.destroy).pack(side=tk.LEFT, padx=(6,0), fill=tk.X, expand=True)
    
        # focus
        amount_entry.focus_set()




    def open_cash_closure_window(self):
        def creator():
            win = tk.Toplevel(self.root)
            win.title("Cierre de caja")
            win.geometry("1200x680")
            try: win.grab_set()
            except: pass
            win.lift(); win.focus_force()
    
            top = ttk.Frame(win, padding=8); top.pack(fill=tk.X)
            ttk.Label(top, text="Desde (YYYY-MM-DD HH:MM:SS):").pack(side=tk.LEFT)
            from_var = tk.StringVar(value=(datetime.now().strftime("%Y-%m-%d") + " 00:00:00"))
            ttk.Entry(top, textvariable=from_var, width=20).pack(side=tk.LEFT, padx=6)
            ttk.Label(top, text="Hasta:").pack(side=tk.LEFT)
            to_var = tk.StringVar(value=(datetime.now().strftime("%Y-%m-%d") + " 23:59:59"))
            ttk.Entry(top, textvariable=to_var, width=20).pack(side=tk.LEFT, padx=6)
            ttk.Button(top, text="Calcular resumen", command=lambda: do_calculate()).pack(side=tk.LEFT, padx=8)
            ttk.Button(top, text="Exportar CSV", command=lambda: do_export_csv()).pack(side=tk.RIGHT, padx=6)
    
            middle = ttk.Frame(win, padding=8); middle.pack(fill=tk.BOTH, expand=True)
            left = ttk.Frame(middle); left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,6))
            right = ttk.Frame(middle, width=260); right.pack(side=tk.LEFT, fill=tk.Y)
    
            # LEFT: listas detalladas
            ttk.Label(left, text="PEDIDOS PAGOS", font=(None,11,"bold")).pack(anchor=tk.W)
            paid_frame = ttk.Frame(left); paid_frame.pack(fill=tk.BOTH, expand=True, pady=(4,8))
            paid_tree = ttk.Treeview(paid_frame, columns=('id','customer','amount','note','created'), show='headings', height=7)
            for c,name in [('id','ID'),('customer','Cliente'),('amount','Monto'),('note','Nota'),('created','Fecha')]:
                paid_tree.heading(c, text=name)

            paid_tree.column('id', width=5, anchor=tk.CENTER)
            paid_tree.column('customer', width=5)
            paid_tree.column('amount', width=5, anchor=tk.E)
            paid_tree.column('note', width=5, anchor=tk.CENTER)
            paid_tree.column('created', width=5, anchor=tk.CENTER)
       
            paid_tree.pack(fill=tk.BOTH, expand=True)
    
            ttk.Label(left, text="GASTOS", font=(None,11,"bold")).pack(anchor=tk.W, pady=(8,0))
            adj_frame = ttk.Frame(left); adj_frame.pack(fill=tk.BOTH, expand=True, pady=(4,8))

            adj_tree = ttk.Treeview(adj_frame, columns=('id','kind','note','amount','user','created'), show='headings', height=7)
            for c,name in [('id','ID'),('kind','Tipo'),('note','Nota'),('amount','Monto'),('user','Usuario'),('created','Fecha')]:
                adj_tree.heading(c, text=name
                                 )
            adj_tree.column('id', width=5, anchor=tk.CENTER)
            adj_tree.column('kind', width=5)
            adj_tree.column('note', width=5, anchor=tk.CENTER)
            adj_tree.column('amount', width=5, anchor=tk.E)
            adj_tree.column('user', width=5, anchor=tk.CENTER)
            adj_tree.column('created', width=5, anchor=tk.CENTER)
            adj_tree.pack(fill=tk.BOTH, expand=True)
    
            # RIGHT: resumen y controles
            summary_box = ttk.LabelFrame(right, text="Resumen", padding=10); summary_box.pack(fill=tk.BOTH, padx=4, pady=4, expand=False)
    
            total_sales_var = tk.StringVar(value="$0")
            cash_in_var = tk.StringVar(value="$0")
            transfer_in_var = tk.StringVar(value="$0")
            paid_orders_var = tk.StringVar(value="$0")
            expenses_var = tk.StringVar(value="$0")
            credits_var = tk.StringVar(value="$0")
            debts_var = tk.StringVar(value="$0")
            net_cash_var = tk.StringVar(value="$0")
            cash_left_var = tk.StringVar(value="$0")      # efectivo que queda en caja
            transfer_left_var = tk.StringVar(value="$0")  # total en transferencias
    
            ttk.Label(summary_box, text="Total ventas:").grid(row=0, column=0, sticky=tk.W)
            ttk.Label(summary_box, textvariable=total_sales_var).grid(row=0, column=1, sticky=tk.E)
            ttk.Label(summary_box, text="Efectivo en ventas:").grid(row=1, column=0, sticky=tk.W)
            ttk.Label(summary_box, textvariable=cash_in_var).grid(row=1, column=1, sticky=tk.E)
            ttk.Label(summary_box, text="Transferencias:").grid(row=2, column=0, sticky=tk.W)
            ttk.Label(summary_box, textvariable=transfer_in_var).grid(row=2, column=1, sticky=tk.E)
            ttk.Label(summary_box, text="Pedidos pagados:").grid(row=3, column=0, sticky=tk.W)
            ttk.Label(summary_box, textvariable=paid_orders_var).grid(row=3, column=1, sticky=tk.E)
            ttk.Label(summary_box, text="Gastos (salidas):").grid(row=4, column=0, sticky=tk.W)
            ttk.Label(summary_box, textvariable=expenses_var).grid(row=4, column=1, sticky=tk.E)
            ttk.Label(summary_box, text="Créditos (nos deben):").grid(row=5, column=0, sticky=tk.W)
            ttk.Label(summary_box, textvariable=credits_var).grid(row=5, column=1, sticky=tk.E)
            ttk.Label(summary_box, text="Deudas (debemos):").grid(row=6, column=0, sticky=tk.W)
            ttk.Label(summary_box, textvariable=debts_var).grid(row=6, column=1, sticky=tk.E)

            ttk.Label(summary_box, text="Efectivo en caja (estimado):").grid(row=7, column=0, sticky=tk.W)
            ttk.Label(summary_box, textvariable=cash_left_var).grid(row=7, column=1, sticky=tk.E)
            # ttk.Label(summary_box, text="Transferencias (acumulado):").grid(row=8, column=0, sticky=tk.W)
            # ttk.Label(summary_box, textvariable=transfer_left_var).grid(row=8, column=1, sticky=tk.E)
            ttk.Label(summary_box, text="Efectivo disponible:      ",font=(None,15,"bold")).grid(row=9, column=0, sticky=tk.W, pady=(6,0))
            ttk.Label(summary_box, textvariable=net_cash_var, font=(None,15,"bold")).grid(row=9, column=1, sticky=tk.E, pady=(6,0))
    
            # registrar cierre: apertura, contado y notas
            ttk.Separator(right, orient='horizontal').pack(fill=tk.X, pady=8)
            rc_frame = ttk.Frame(right); rc_frame.pack(fill=tk.X, pady=(4,4))
            ttk.Label(rc_frame, text="Apertura caja:").grid(row=0, column=0, sticky=tk.W)
            opening_var = tk.StringVar(value="0"); ttk.Entry(rc_frame, textvariable=opening_var, width=16).grid(row=0, column=1, sticky=tk.E)
            ttk.Label(rc_frame, text="Efectivo contado:").grid(row=1, column=0, sticky=tk.W, pady=(6,0))
            counted_var = tk.StringVar(value="0"); ttk.Entry(rc_frame, textvariable=counted_var, width=16).grid(row=1, column=1, sticky=tk.E, pady=(6,0))
            ttk.Label(rc_frame, text="Notas:").grid(row=2, column=0, sticky=tk.W, pady=(6,0))
            notes_var = tk.StringVar(); ttk.Entry(rc_frame, textvariable=notes_var, width=22).grid(row=2, column=1, sticky=tk.E, pady=(6,0))
    
            btnf = ttk.Frame(right); btnf.pack(fill=tk.X, pady=(12,0))
            ttk.Button(btnf, text="Registrar cierre", command=lambda: do_register_closure()).pack(fill=tk.X, pady=4)
            # ejemplo: justo antes de los botones de acción (donde ya tienes Register closure)
            ttk.Button(btnf, text="Registrar gasto", command=lambda: (self.open_outflow_dialog(), win.after(150, do_calculate))).pack(fill=tk.X, pady=4)
            # mantén tus otros botones (Registrar cierre, Cerrar)
            
            ttk.Button(btnf, text="Cerrar", command=win.destroy).pack(fill=tk.X, pady=(6,0))
    
            # helper: cargar último cierre para proponer apertura predeterminada
            try:
                cur = conn.cursor()
                cur.execute("SELECT opening_cash, cash_counted, created_at FROM cash_closures ORDER BY id DESC LIMIT 1")
                last = cur.fetchone()
                if last:
                    try:
                        last_counted = last['cash_counted'] if isinstance(last, dict) else last[1]
                        opening_var.set(str(last_counted))
                    except:
                        pass
            except:
                pass
    
            def clear_views():
                for t in (paid_tree, adj_tree):
                    for i in t.get_children(): t.delete(i)


            def do_calculate():
                clear_views()
                start_dt = from_var.get().strip(); end_dt = to_var.get().strip()
                if not start_dt or not end_dt:
                    messagebox.showwarning("Fechas", "Ingresa rango válido")
                    return
            
                # total ventas
                total_sales = get_sales_total_for_period(conn, start_dt, end_dt) or 0
                total_sales_var.set(f"${format_money(total_sales)}")
            
                # pagos por método (desde sale_payments)
                pays = get_payments_summary_for_period(conn, start_dt, end_dt) or []
                cash_total = 0; transfer_total = 0
                payments_summary = {}
                for p in pays:
                    rp = dict(p) if hasattr(p, 'keys') else p
                    method = rp.get('method') if isinstance(rp, dict) else p[0]
                    tot = int(rp.get('total') if isinstance(rp, dict) else (p[1] or 0))
                    payments_summary[str(method)] = payments_summary.get(str(method), 0) + tot
                    mlow = str(method).lower() if method else ""
                    if "efectivo" in mlow or mlow == "cash" or "cash" in mlow:
                        cash_total += tot
                    elif "transfer" in mlow or "dep" in mlow or "transferencia" in mlow or "bank" in mlow or "tarjeta" in mlow:
                        transfer_total += tot
            
                cash_in_var.set(f"${format_money(cash_total)}")
                transfer_in_var.set(f"${format_money(transfer_total)}")
            
                # pedidos pagados
                paid_rows = get_paid_orders_for_period(conn, start_dt, end_dt) or []
                paid_total = sum_paid_orders_for_period(conn, start_dt, end_dt) or 0
                for r in paid_rows:
                    rr = dict(r) if hasattr(r, 'keys') else r
                    paid_tree.insert('', tk.END, values=(rr.get('id') if isinstance(rr, dict) else rr[0],
                                                         rr.get('customer_name') if isinstance(rr, dict) else rr[1],
                                                         f"${format_money(rr.get('amount') if isinstance(rr, dict) else rr[2])}",
                                                         rr.get('note') if isinstance(rr, dict) else rr[3],
                                                         rr.get('created_at') if isinstance(rr, dict) else rr[4]))
                paid_orders_var.set(f"-${format_money(paid_total)}")
            
                # ajustes (tabla adjustments) -> intentamos leer monto con detección tolerante
                try:
                    adjustments = get_adjustments_for_period(conn, start_dt, end_dt) or []
                    adj_total = sum_adjustments_for_period(conn, start_dt, end_dt) or 0
                    adj_total = abs(int(adj_total))
                except Exception as ex:
                    adjustments = []
                    adj_total = 0
                    print("Error cargando ajustes:", ex)
            
                # outflows (salidas) -> get_outflows_in_range devuelve (rows, total)
                try:
                    # get_outflows_in_range espera fechas tipo 'YYYY-MM-DD'; extraemos la parte fecha
                    s_date = (start_dt.split(" ")[0]) if start_dt and " " in start_dt else start_dt
                    e_date = (end_dt.split(" ")[0]) if end_dt and " " in end_dt else end_dt
                    out_rows, out_total = get_outflows_in_range(s_date, e_date)
                    outflows = out_rows or []
                    outflows_total = int(out_total or 0)
                except Exception as ex:
                    outflows = []
                    outflows_total = 0
                    print("Error cargando outflows:", ex)
            
                # mostrar detalles: primero ajustes, luego outflows (como "Salida")
                for a in adjustments:
                    aa = dict(a) if hasattr(a, 'keys') else a
                    try:
                        amt = aa.get('amount') if isinstance(aa, dict) else (a[3] if len(a)>3 else 0)
                        amt_int = abs(int(amt))
                    except:
                        try:
                            amt_int = abs(int(a[3]))
                        except:
                            amt_int = 0
                    adj_tree.insert('', tk.END, values=(aa.get('id') if isinstance(aa, dict) else aa[0],
                                                        aa.get('kind') if isinstance(aa, dict) else aa[1],
                                                        aa.get('note') if isinstance(aa, dict) else aa[2],
                                                        f"${format_money(amt_int)}",
                                                        aa.get('user') if isinstance(aa, dict) else (aa[4] if len(a)>4 else ""),
                                                        aa.get('created_at') if isinstance(aa, dict) else (aa[5] if len(a)>5 else "")))
            
                for o in outflows:
                    oo = dict(o) if hasattr(o, 'keys') else o
                    oid = oo.get('id') if isinstance(oo, dict) else (o[0] if len(o)>0 else "")
                    when = oo.get('created_at') if isinstance(oo, dict) else (o[1] if len(o)>1 else "")
                    amt = oo.get('amount') if isinstance(oo, dict) else (o[2] if len(o)>2 else 0)
                    desc = oo.get('description') if isinstance(oo, dict) else (o[3] if len(o)>3 else "")
                    try:
                        amt_int = abs(int(amt))
                    except:
                        try: amt_int = abs(int(float(amt)))
                        except: amt_int = 0
                    adj_tree.insert('', tk.END, values=(oid, "Salida", desc or "", f"${format_money(amt_int)}", "", when))
            
                # TOTAL gastos que deben restar del efectivo: ajustes + outflows
                total_adjustments_for_closure = adj_total + outflows_total
                expenses_var.set(f"-${format_money(total_adjustments_for_closure)}")
            
                # créditos / deudas
                cr_total, cr_balance = sum_credits_for_period(conn, start_dt, end_dt)
                db_total, db_balance = sum_debts_for_period(conn, start_dt, end_dt)
                credits_var.set(f"${format_money(cr_total or 0)}")
                debts_var.set(f"${format_money(db_total or 0)}")
            
                # net efectivo disponible (apertura + cash_in - gastos_total - paid_orders)
                try:
                    opening = parse_money_to_int(opening_var.get())
                except:
                    opening = 0
                net_cash = opening + cash_total - total_adjustments_for_closure - paid_total
                net_cash_var.set(f"${format_money(net_cash)}")
            
                cash_left = opening + cash_total - total_adjustments_for_closure - paid_total
                transfer_left = transfer_total
                cash_left_var.set(f"${format_money(cash_left)}")
                transfer_left_var.set(f"${format_money(transfer_left)}")
            
                # guardar estado (para export / persistir)
                win._closure_state = {
                    "start": start_dt, "end": end_dt,
                    "total_sales": total_sales,
                    "cash_in": cash_total, "transfer_in": transfer_total,
                    "paid_orders_total": paid_total,
                    "adjustments_total": adj_total,
                    "outflows_total": outflows_total,
                    "adjustments_and_outflows_total": total_adjustments_for_closure,
                    "credits_total": cr_total, "debts_total": db_total,
                    "payments_summary": payments_summary
                }
            



            def do_register_closure():
                st = getattr(win, "_closure_state", None)
                if not st:
                    messagebox.showwarning("Aviso", "Primero calcula el resumen"); return
                try:
                    opening = parse_money_to_int(opening_var.get())
                    counted = parse_money_to_int(counted_var.get())
                except:
                    messagebox.showwarning("Valores", "Valores inválidos"); return
    
                try:
                    # usar helper save_cash_closure para persistir (ya definido en tu archivo)
                    ps = st.get('payments_summary', {})
                    cid = save_cash_closure(
                        getattr(self, 'current_user', 'cajero'),
                        st['start'],
                        st['end'],
                        opening,
                        st['cash_in'],
                        st['adjustments_total'],    # cash_expenses -> guardamos ajustes como gastos
                        counted,
                        st['total_sales'],
                        ps,
                        notes_var.get().strip()
                    )
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo guardar cierre: {e}"); return
    
                # opcional: exportar CSV inmediatamente
                if messagebox.askyesno("Cierre guardado", f"Cierre registrado (ID: {cid}). ¿Exportar CSV?"):
                    from tkinter import filedialog
                    path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=f"cash_closure_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
                    if path:
                        summary = {
                            "closed_at": datetime.now().isoformat(sep=' ', timespec='seconds'),
                            "total_sales": st['total_sales'],
                            "cash_in": st['cash_in'],
                            "transfer_in": st['transfer_in'],
                            "paid_orders_total": st['paid_orders_total'],
                            "adjustments_total": st['adjustments_total'],
                            "credits_total": st['credits_total'],
                            "debts_total": st['debts_total'],
                            "opening": opening,
                            "counted": counted,
                            "cash_diff": counted - (opening + st['cash_in'] - st['adjustments_total'] - st['paid_orders_total'])
                        }
                        
                        lists = {
                            "paid_orders": get_paid_orders_for_period(conn, st['start'], st['end']),
                            "adjustments": get_adjustments_for_period(conn, st['start'], st['end']),
                            "payments": get_payments_summary_for_period(conn, st['start'], st['end'])
                        }
                        try:
                            export_cash_closure_csv(path, summary, lists)
                            messagebox.showinfo("Exportado", f"CSV guardado en:\n{path}")
                        except Exception as e:
                            messagebox.showerror("Error export", str(e))
    
                messagebox.showinfo("Cierre", f"Cierre registrado (ID: {cid}). Efectivo contado: ${format_money(counted)}.")
                # tras guardar, sugerir usar contado como apertura siguiente (no borra ventas)
                try:
                    opening_var.set(str(counted))
                except:
                    pass
                win.destroy()
    
            def do_export_csv():
                st = getattr(win, "_closure_state", None)
                if not st:
                    messagebox.showwarning("Aviso", "Primero calcula el resumen"); return
                from tkinter import filedialog
                path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=f"cash_closure_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
                if not path: return
                summary = {
                    "closed_at": datetime.now().isoformat(sep=' ', timespec='seconds'),
                    "total_sales": st['total_sales'],
                    "cash_in": st['cash_in'],
                    "transfer_in": st['transfer_in'],
                    "paid_orders_total": st['paid_orders_total'],
                    "adjustments_total": st['adjustments_total'],
                    "credits_total": st['credits_total'],
                    "debts_total": st['debts_total'],
                }
                lists = {
                    "paid_orders": get_paid_orders_for_period(conn, st['start'], st['end']),
                    "adjustments": get_adjustments_for_period(conn, st['start'], st['end']),
                    "payments": get_payments_summary_for_period(conn, st['start'], st['end'])
                }
                try:
                    export_cash_closure_csv(path, summary, lists)
                    messagebox.showinfo("Exportado", f"CSV guardado en:\n{path}")
                except Exception as e:
                    messagebox.showerror("Error export", str(e))
    
            win.bind("<Escape>", lambda e: win.destroy())
            win.after(120, lambda: (win.lift(), win.focus_force()))
            return win
    
        # open once helper if present
        if hasattr(self, 'open_window_once'):
            return self.open_window_once("cash_closure", creator)
        else:
            return creator()
    



    def checkout(self):
        if not self.cart:
            messagebox.showinfo("Carrito vacío", "No hay items para cobrar.")
            return
        total = sum(item.total() for item in self.cart.values())
    
        def creator():
            win = tk.Toplevel(self.root)
            win.title("Cobro — Pago múltiple / mixto")
            win.geometry("520x520")
            win.resizable(False, False)
            win.lift()
            win.focus_force()
            win.grab_set()
    
            ttk.Label(win, text=f"Total a cobrar: ${format_money(total)}", font=(None, 13, "bold")).pack(pady=(8,6))
    
            # Frame de pagos añadidos
            payments_frame = ttk.LabelFrame(win, text="Pagos agregados", padding=6)
            payments_frame.pack(fill=tk.BOTH, padx=10, pady=(0,8), expand=False)
            payments_tree = ttk.Treeview(payments_frame, columns=('method','amount','details'), show='headings', height=5)
            payments_tree.heading('method', text='Método'); payments_tree.heading('amount', text='Monto'); payments_tree.heading('details', text='Detalles')
            payments_tree.column('amount', anchor=tk.E, width=120)
            payments_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            ps_scroll = ttk.Scrollbar(payments_frame, orient='vertical', command=payments_tree.yview)
            payments_tree.configure(yscroll=ps_scroll.set)
            ps_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    
            # Frame para crear un pago nuevo
            newf = ttk.Frame(win, padding=8)
            newf.pack(fill=tk.X, padx=10)
            ttk.Label(newf, text="Método:").grid(row=0, column=0, sticky=tk.W)
            method_var = tk.StringVar(value="Efectivo")   # <--- por defecto Efectivo
            methods = ["Efectivo", "Tarjeta", "Transferencia"]
            method_combo = ttk.Combobox(newf, textvariable=method_var, values=methods, state='readonly', width=18)
            method_combo.grid(row=0, column=1, sticky=tk.W, padx=(6,0))
    
            ttk.Label(newf, text="Monto:").grid(row=1, column=0, sticky=tk.W, pady=(6,0))
            amount_var = tk.StringVar(value=format_money(total))  # <--- por defecto el total
            amount_entry = ttk.Entry(newf, textvariable=amount_var)
            amount_entry.grid(row=1, column=1, sticky=tk.W, padx=(6,0), pady=(6,0))
    
            ttk.Label(newf, text="Detalles (opcional):").grid(row=2, column=0, sticky=tk.W, pady=(6,0))
            details_var = tk.StringVar()
            details_entry = ttk.Entry(newf, textvariable=details_var, width=30)
            details_entry.grid(row=2, column=1, sticky=tk.W, padx=(6,0), pady=(6,0))
    
            # botones para añadir/quitar pago
            btnf = ttk.Frame(win); btnf.pack(fill=tk.X, padx=10, pady=(6,4))
            def add_payment_line(event=None):
                try:
                    amt = parse_money_to_int(amount_var.get())
                except:
                    messagebox.showwarning("Monto inválido", "Ingresa un monto válido"); return
                m = method_var.get() or "Efectivo"
                d = details_var.get().strip() or ""
                payments_tree.insert('', tk.END, values=(m, f"${format_money(amt)}", d))
                details_var.set("")
                amount_var.set("")  # para siguiente entrada rápida
                update_totals_display()
    
            def remove_payment_line(event=None):
                sel = payments_tree.selection()
                if not sel:
                    return
                payments_tree.delete(sel[0])
                update_totals_display()
    
            ttk.Button(btnf, text="Agregar pago", command=add_payment_line).pack(side=tk.LEFT, padx=6)
            ttk.Button(btnf, text="Quitar seleccionado", command=remove_payment_line).pack(side=tk.LEFT, padx=6)
    
            # Totales abajo
            totalsf = ttk.Frame(win, padding=8); totalsf.pack(fill=tk.X, padx=10)
            paid_var = tk.StringVar(value=f"${format_money(0)}")
            change_var = tk.StringVar(value=f"${format_money(0)}")
            ttk.Label(totalsf, text="Total pagado:").grid(row=0, column=0, sticky=tk.W)
            ttk.Label(totalsf, textvariable=paid_var).grid(row=0, column=1, sticky=tk.E)
            ttk.Label(totalsf, text="Devolución:").grid(row=1, column=0, sticky=tk.W, pady=(6,0))
            ttk.Label(totalsf, textvariable=change_var).grid(row=1, column=1, sticky=tk.E, pady=(6,0))
    
            def update_totals_display():
                total_paid = 0
                for iid in payments_tree.get_children():
                    vals = payments_tree.item(iid, 'values')
                    amt_str = str(vals[1]).replace("$","").strip()
                    try:
                        amt = parse_money_to_int(amt_str)
                    except:
                        amt = 0
                    total_paid += int(amt)
                paid_var.set(f"${format_money(total_paid)}")
                ch = total_paid - int(total)
                change_var.set(f"${format_money(ch)}" if ch >= 0 else f"-${format_money(abs(ch))}")
    
            # botón para pagar exacto (efectivo restante)
            def add_exact_cash():
                total_paid = 0
                for iid in payments_tree.get_children():
                    vals = payments_tree.item(iid, 'values')
                    amt_str = str(vals[1]).replace("$","").strip()
                    try:
                        total_paid += parse_money_to_int(amt_str)
                    except:
                        pass
                remaining = int(total) - total_paid
                if remaining <= 0:
                    messagebox.showinfo("Ya pagado", "El total ya está cubierto o excedido.")
                    return
                payments_tree.insert('', tk.END, values=("Efectivo", f"${format_money(remaining)}", "Cobro exacto"))
                update_totals_display()
    
            ttk.Button(win, text="Cobrar exacto (efectivo restante)", command=add_exact_cash).pack(fill=tk.X, padx=10, pady=(6,0))
    
            # Finalizadores: guardar venta + pagos
            def finalize_sale(close_after=True):
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
                # preparar pagos desde el tree
                payments = []
                total_paid = 0
                for iid in payments_tree.get_children():
                    mth, amt_s, det = payments_tree.item(iid, 'values')
                    amt = parse_money_to_int(str(amt_s).replace("$",""))
                    payments.append({"method": mth, "amount": int(amt), "details": det})
                    total_paid += int(amt)
    
                # validar: si no alcanza, preguntar si crear credito/fiado o abortar
                if total_paid < int(total):
                    if messagebox.askyesno("Saldo insuficiente", "El monto pagado es menor que el total. ¿Deseas registrar la venta como crédito/fiado para el cliente?"):
                        # Crear crédito: pedimos seleccionar cliente (simple prompt)
                        cwin = tk.Toplevel(win)
                        cwin.title("Seleccionar cliente para fiado")
                        ttk.Label(cwin, text="Ingresa ID del cliente o busca:").pack(padx=8,pady=6)
                        cid_var = tk.StringVar()
                        ttk.Entry(cwin, textvariable=cid_var).pack(padx=8,pady=6)
                        def do_create_credit():
                            try:
                                cid = int(cid_var.get().strip())
                            except:
                                messagebox.showwarning("ID inválido", "Ingresa el ID numérico del cliente"); return
                            try:
                                sale_id = save_sale(items)
                            except Exception as e:
                                messagebox.showerror("Error", f"No se pudo guardar la venta: {e}"); return
                            # guardar pagos parciales si existen
                            for p in payments:
                                try:
                                    add_sale_payment(sale_id, p['method'], p['amount'], p.get('details'))
                                except Exception:
                                    pass
                            credit_amount = int(total) - total_paid
                            create_credit(cid, credit_amount, reference=str(sale_id), description="Venta a crédito (parcial)", due_date=None)
                            messagebox.showinfo("Venta y crédito registrados", f"Venta ID {sale_id} y crédito creado por ${format_money(credit_amount)}")
                            cwin.destroy()
                            if close_after: win.destroy()
                            self.cart.clear(); self.refresh_cart()
                        ttk.Button(cwin, text="Crear crédito y guardar", command=do_create_credit).pack(padx=8,pady=6)
                    else:
                        messagebox.showwarning("Pago incompleto", "No se realizó el cobro.")
                    return
    
                # si alcanza o excede, proceed
                try:
                    sale_id = save_sale(items)
                except Exception as e:
                    messagebox.showerror("Error al guardar venta", str(e)); return
    
                # guardar pagos en BD
                for p in payments:
                    try:
                        add_sale_payment(sale_id, p['method'], p['amount'], p.get('details'))
                    except Exception as e:
                        # si falla un pago, lo registramos en log y continuamos (no abortamos todo)
                        print("Error guardando pago:", e)
    
                # marcar venta como pagada si corresponde
                try:
                    if total_paid >= int(total):
                        # intenta usar helper si existe
                        if hasattr(self, 'mark_sale_paid'):
                            try:
                                self.mark_sale_paid(sale_id)
                            except:
                                pass
                        else:
                            # fallback: actualizar directamente la tabla sales (usa conn global)
                            try:
                                cur = conn.cursor()
                                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                cur.execute("UPDATE sales SET status = ?, paid_at = ? WHERE id = ?", ('paid', now, sale_id))
                                conn.commit()
                            except Exception:
                                try: conn.rollback()
                                except: pass
                except Exception:
                    pass
    
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
                        "product_name": it.get('name'),
                        "qty": qty_int,
                        "price": price_int,
                        "subtotal": price_int * qty_int
                    })
    
                total_amount = sum(r["subtotal"] for r in sale_rows)
                rec_amount = total_paid
                change_amount = max(0, total_paid - int(total))
    
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
                                company_name="Mi Negocio"
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
    
                # limpiar y cerrar
                self.cart.clear(); self.refresh_cart()
                try: self.update_category_buttons_state()
                except: pass
                if close_after: win.destroy()
                return sale_id
    
            # finalize_btn = ttk.Button(win, text="Finalizar y registrar venta", command=lambda: finalize_sale(True))
            finalize_btn = ttk.Button(win, text="Finalizar y registrar venta", command=lambda: on_enter_quickpay(True))
            finalize_btn.pack(fill=tk.X, padx=10, pady=(8,10))
    
            # Bindings
            payments_tree.bind('<Delete>', lambda e: remove_payment_line())
            win.bind('<Escape>', lambda e: win.destroy())
            amount_entry.bind('<Return>', lambda e: add_payment_line())
    
            # ---- Comportamiento rápido con ENTER: si presionas Enter y no hay pagos añadidos,
            # ---- añade el pago en efectivo por el restante y finaliza automáticamente.
            def on_enter_quickpay(event=None):
                focused = win.focus_get()
                # si el foco está en amount_entry, Enter añade esa línea (ya enlazado)
                if focused is amount_entry:
                    add_payment_line()
                    return "break"
                # si hay ya pagos añadidos, simplemente finalizamos
                if payments_tree.get_children():
                    finalize_sale(True)
                else:
                    # no hay pagos: añadir efectivo exacto y finalizar
                    add_exact_cash()
                    finalize_sale(True)
                return "break"
    
            # bind global dentro de la ventana (solo esta win)
            win.bind("<Return>", on_enter_quickpay)
    
            # actualizar totales cuando se inserte/elimine
            win.after(200, update_totals_display)
    
            return win
    
        return self.open_window_once("simple_payment", creator)
    
    




    def show_sale_done_window(self, sale_id, total, received=None, change=None, sale_rows=None, company_name="Mi Negocio"):
        """
        Muestra ventana al finalizar venta con opción (opcional) de ver vista previa.
        - Cerrar será el botón por defecto y capturará Enter.
        - sale_rows: lista de dicts como espera open_receipt_preview.
        """
        win = tk.Toplevel(self.root)
        win.title("Venta realizada")
        win.geometry("420x180")
        win.resizable(False, False)
        try:
            win.transient(self.root)
        except: pass
    
        # Asegurar modal y foco
        win.lift()
        win.focus_force()
        try:
            win.grab_set()
        except: pass
    
        # Contenido
        frm = ttk.Frame(win, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)
    
        ttk.Label(frm, text=f"Venta registrada (ID: {sale_id})", font=(None, 11, "bold")).pack(anchor=tk.W)
        ttk.Label(frm, text=f"Total: ${format_money(total)}").pack(anchor=tk.W, pady=(6,0))
        if received is not None:
            ttk.Label(frm, text=f"Recibido: ${format_money(received)}").pack(anchor=tk.W)
        if change is not None:
            ttk.Label(frm, text=f"Devolución: ${format_money(change)}").pack(anchor=tk.W)
    
        # Botones: Preview (opcional) y Cerrar (por defecto)
        btnf = ttk.Frame(frm)
        btnf.pack(fill=tk.X, pady=(12,0))
    
        def on_close():
            try:
                win.grab_release()
            except:
                pass
            win.destroy()
    
        def on_preview():
            # Abrir vista previa si tenemos rows, si no intentamos construir mínimos
            try:
                rows = sale_rows
                if rows is None:
                    # intentar obtener items desde DB
                    c = conn.cursor()
                    c.execute("SELECT product_name as product_name, product_code as product_code, qty, price, (qty*price) as subtotal FROM sale_items WHERE sale_id=?", (sale_id,))
                    rows = [dict(r) for r in c.fetchall()]
                # abrir preview (tu función debe aceptar estos parámetros)
                self.open_receipt_preview(sale_id, rows, total, received=received, change=change, company_name=company_name)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo abrir vista previa: {e}")
    
        # Preview solo si hay función disponible
        preview_btn = ttk.Button(btnf, text="🧾 Vista previa", command=on_preview)
        preview_btn.pack(side=tk.LEFT, padx=(0,6))
    
        # Botón Cerrar (por defecto)
        close_btn = ttk.Button(btnf, text="Cerrar (Enter)", command=on_close)
        close_btn.pack(side=tk.RIGHT)
    
        # Asegurar que 'Cerrar' sea el widget por defecto capturando Return y dándole foco
        close_btn.focus_set()
        win.bind("<Return>", lambda e: on_close())
        win.bind("<Escape>", lambda e: on_close())
    
        # Evitar que Enter en otros widgets cierre inesperadamente si deseas:
        # por ejemplo, si quieres que Enter en un Entry haga otra cosa, añade excepciones.
    
        return win
    



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