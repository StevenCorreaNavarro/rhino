#!/usr/bin/env python3
# main.py - Registradora POS (Tkinter + SQLite)
# Guarda como main.py y ejecuta: python main.py

import os
import sqlite3
import uuid
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime
import subprocess

# Optional imports for PDF / Windows printing
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas as pdfcanvas
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

try:
    import win32print  # type: ignore
    import win32api  # type: ignore
    WIN32_AVAILABLE = True
except Exception:
    WIN32_AVAILABLE = False

# ---------------- CONFIG ----------------
DB_PATH = os.path.join("app", "database", "punto_ventas.db")

# ---------------- UTILITIES: money parsing/format ----------------
def parse_money_to_int(value):
    """
    Normaliza entradas como:
      '7.000' -> 7000
      '7000'  -> 7000
      '7000.00' -> 7000
      7000.0 -> 7000
    Devuelve int.
    """
    try:
        s = str(value).strip()
        s = s.replace("$", "")
        # Handle "1.234,56" or "1,234.56" or "1.234.56"
        # Strategy: remove thousand separators (dots), convert comma to dot as decimal sep
        # If string contains both '.' and ',', assume dot is thousand separator -> remove dots, replace comma with dot
        if ',' in s and s.count(',') == 1 and s.count('.') > 0:
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace('.', '').replace(',', '.')
        val = float(s)
        return int(round(val))
    except Exception:
        return 0

def format_money(value):
    """Formatea número entero a '7.000' (seguro)."""
    try:
        n = int(round(float(value)))
        return f"{n:,}".replace(",", ".")
    except Exception:
        return "0"

# ---------------- DB --------------------
def init_db():
    dirpath = os.path.dirname(DB_PATH)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON")

    c.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE,
        name TEXT,
        price INTEGER,
        stock INTEGER,
        category_id INTEGER,
        FOREIGN KEY(category_id) REFERENCES categories(id)
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        total INTEGER
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS sale_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER,
        product_id INTEGER,
        product_code TEXT,
        product_name TEXT,
        category_id INTEGER,
        qty INTEGER,
        price INTEGER,
        FOREIGN KEY(sale_id) REFERENCES sales(id)
    )
    """)

    # default 10 categories
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
        price_int = int(round(float(price)))
    except:
        price_int = 0
    try:
        stock_int = int(stock)
    except:
        stock_int = 0
    try:
        c = conn.cursor()
        c.execute(
            "INSERT INTO products (code, name, price, stock, category_id) VALUES (?, ?, ?, ?, ?)",
            (code, name, price_int, stock_int, category_id)
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

def save_sale(cart_items):
    """
    Guarda la venta y actualiza stock de forma segura.
    Si alguna cantidad en cart_items excede el stock disponible, lanza ValueError.
    cart_items: lista de dicts con keys: product_id, code, name, price, qty, category_id
    """
    c = conn.cursor()

    # Validar stock primero
    for it in cart_items:
        pid = int(it['product_id'])
        qty = int(it['qty'])
        if qty < 0:
            raise ValueError(f"Cantidad inválida para {it.get('name','?')}: {qty}")

        c.execute("SELECT stock, name FROM products WHERE id=?", (pid,))
        row = c.fetchone()
        if not row:
            raise ValueError(f"Producto no encontrado (id={pid})")
        current_stock = int(row[0])
        prod_name = row[1] if 'name' in row.keys() else it.get('name', 'Producto')
        if qty > current_stock:
            raise ValueError(f"Stock insuficiente para '{prod_name}'. Disponible: {current_stock}, solicitado: {qty}")

    # Guardar venta
    total = sum(int(it['qty']) * int(round(float(it['price']))) for it in cart_items)
    created_at = datetime.now().isoformat(sep=' ', timespec='seconds')
    c.execute("INSERT INTO sales (created_at, total) VALUES (?, ?)", (created_at, total))
    sale_id = c.lastrowid

    for it in cart_items:
        pid = int(it['product_id'])
        qty = int(it['qty'])
        price = int(round(float(it['price'])))
        c.execute(
            "INSERT INTO sale_items (sale_id, product_id, product_code, product_name, category_id, qty, price) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sale_id, pid, it['code'], it['name'], it.get('category_id'), qty, price)
        )
        # disminuir stock
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
        self.product_id = int(product_id)
        self.code = str(code)
        self.name = str(name)
        self.price = int(parse_money_to_int(price))
        self.qty = int(qty)
        self.category_id = category_id

    def total(self):
        return int(self.price) * int(self.qty)

# ---------------- RECEIPT & PRINT HELPERS ----------------
def generate_receipt_text(sale_id, sale_rows, total, received=None, change=None, company_name="Mi Negocio"):
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

def save_receipt_text_file(text, filename):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(text)
    return filename

def save_receipt_pdf(sale_id, sale_rows, total, received=None, change=None, company_name="Mi Negocio", filename=None):
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("reportlab no está instalado. pip install reportlab")
    if filename is None:
        filename = f"receipt_{sale_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
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

def print_text_file_windows(path):
    if not WIN32_AVAILABLE:
        raise RuntimeError("pywin32 no está instalado")
    win32api.ShellExecute(0, "print", path, None, ".", 0)
    return True

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

# ---------------- APP ----------------
class POSApp:
    def __init__(self, master):
        self.master = master
        self.root = master
        self.root.title("Registradora - POS")
        self.root.geometry("1100x640")
        self.open_windows = {}
        self.cart = {}

        # layout
        left = ttk.Frame(self.root, padding=6)
        left.pack(side=tk.LEFT, fill=tk.Y)
        center = ttk.Frame(self.root, padding=6)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right = ttk.Frame(self.root, padding=6)
        right.pack(side=tk.RIGHT, fill=tk.Y)

        # left: categories
        ttk.Label(left, text="Categorías (botones)", font=(None, 12, 'bold')).pack(pady=(0,8))
        self.cat_frame = ttk.Frame(left)
        self.cat_frame.pack()
        ttk.Button(left, text="Administrar Categorías", command=self.manage_categories_window).pack(fill=tk.X, pady=6)
        ttk.Button(left, text="Agregar producto", command=self.open_add_product_window).pack(fill=tk.X, pady=6)
        ttk.Button(left, text="Ver historial", command=self.open_history_window).pack(fill=tk.X, pady=6)

        # center: buscador
        ttk.Label(center, text="Productos - Buscar (Enter para buscar / Enter en lista añade)", font=(None, 12, 'bold')).pack(anchor=tk.W)
        sf = ttk.Frame(center)
        sf.pack(fill=tk.X, pady=6)
        ttk.Label(sf, text="Buscar:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(sf, textvariable=self.search_var)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        # real-time search
        self.search_var.trace_add('write', lambda *a: self.load_products())
        self.search_entry.bind('<Down>', lambda e: (self.products_tree.focus_set() or True) and (self.tree_move(self.products_tree, 1)))
        self.search_entry.bind('<Return>', lambda e: self.load_products())

        ttk.Button(sf, text="Buscar", command=self.load_products).pack(side=tk.LEFT, padx=4)
        ttk.Button(sf, text="Refrescar", command=lambda: self.load_products("")).pack(side=tk.LEFT)

        cols = ("id","code","name","price","stock","cat")
        self.products_tree = ttk.Treeview(center, columns=cols, show='headings', height=20)
        for c in cols:
            self.products_tree.heading(c, text=c.capitalize())
        self.products_tree.column('id', width=60, anchor=tk.CENTER)
        self.products_tree.column('price', width=110, anchor=tk.E)
        self.products_tree.column('stock', width=80, anchor=tk.E)
        self.products_tree.pack(fill=tk.BOTH, expand=True)
        self.products_tree.bind('<Double-1>', self.on_product_double)
        self.products_tree.bind('<Return>', self.on_product_enter)
        self.products_tree.bind('<Down>', lambda e: self.tree_move(self.products_tree, 1))
        self.products_tree.bind('<Up>', lambda e: self.tree_move(self.products_tree, -1))

        self.reload_category_buttons()
        self.load_products()

        # right: cart
        ttk.Label(right, text="Carrito", font=(None, 12, 'bold')).pack()
        self.cart_listbox = tk.Listbox(right, width=60, height=28)
        self.cart_listbox.pack(pady=6)
        ttk.Button(right, text="Eliminar seleccionado", command=self.remove_selected_cart_item).pack(fill=tk.X, pady=3)
        ttk.Button(right, text="Vaciar carrito", command=self.clear_cart).pack(fill=tk.X, pady=3)
        self.total_var = tk.StringVar(value="Total: $0")
        ttk.Label(right, textvariable=self.total_var, font=(None, 11, 'bold')).pack(pady=6)
        ttk.Button(right, text="Finalizar venta", command=self.checkout_simple).pack(fill=tk.X, pady=3)

        self.root.bind('<Control-Return>', lambda e: self.checkout_simple())
        self.root.bind('<Escape>', lambda e: self.close_active_window())

    # ---------- category buttons ----------
    def reload_category_buttons(self):
        for w in self.cat_frame.winfo_children():
            w.destroy()

        cats = get_categories()
        self.category_hotkeys = {}
        keys = ["1","2","3","4","5","6","7","8","9","0"]

        self.cat_buttons_map = {}

        for i, (cid, name) in enumerate(cats):
            if i >= len(keys):
                break
            key = keys[i]
            btn_text = f"{key} - {name}"
            btn = ttk.Button(self.cat_frame, text=btn_text, width=22, command=lambda c=cid, n=name: self.open_search_for_category(c, n))
            btn.pack(pady=3)
            self.cat_buttons_map[cid] = btn
            self.category_hotkeys[key] = (cid, name)

        if not getattr(self, "_category_hotkey_bound", False):
            self.root.bind_all("<Key>", self._handle_category_hotkey)
            self._category_hotkey_bound = True

        # update badges initially
        self.update_category_buttons_state()

    def _handle_category_hotkey(self, event):
        key = event.char
        if key and key in getattr(self, "category_hotkeys", {}):
            cid, name = self.category_hotkeys[key]
            self.open_search_for_category(cid, name)
            return "break"
        ks = event.keysym
        if ks.startswith("KP_"):
            num = ks.split("_", 1)[1]
            hot = '0' if num == '0' else num
            if hot in getattr(self, "category_hotkeys", {}):
                cid, name = self.category_hotkeys[hot]
                self.open_search_for_category(cid, name)
                return "break"

    def update_category_buttons_state(self):
        counts = {}
        for item in self.cart.values():
            cid = item.category_id
            if cid is None:
                continue
            counts[cid] = counts.get(cid, 0) + item.qty
        self.categories = get_categories()
        for cid, btn in getattr(self, "cat_buttons_map", {}).items():
            name = next((n for (i, n) in self.categories if i == cid), f"Categoría {cid}")
            cnt = counts.get(cid, 0)
            if cnt > 0:
                btn.config(text=f"{name} •{cnt}")
            else:
                # restore with its hotkey prefix if available
                key = None
                for k, (id_, nm) in getattr(self, "category_hotkeys", {}).items():
                    if id_ == cid:
                        key = k; break
                if key:
                    btn.config(text=f"{key} - {name}")
                else:
                    btn.config(text=name)

    # ---------- windows single-instance helper ----------
    def open_window_once(self, key, creator):
        if key in self.open_windows and self.open_windows[key].winfo_exists():
            self.open_windows[key].lift()
            return self.open_windows[key]
        win = creator()
        self.open_windows[key] = win
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
        if self.open_windows:
            key = list(self.open_windows.keys())[-1]
            win = self.open_windows.get(key)
            if win and win.winfo_exists():
                win.destroy()
                del self.open_windows[key]

    # ---------- manage categories ----------
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

    # ---------- add product ----------
    def open_add_product_window(self):
        def creator():
            win = tk.Toplevel(self.root)
            win.title('Agregar producto')
            win.geometry('380x320')
            ttk.Label(win, text='Nombre:').pack(anchor=tk.W, padx=8, pady=(8,0))
            name_e = ttk.Entry(win); name_e.pack(fill=tk.X, padx=8); name_e.focus()
            ttk.Label(win, text='Precio:').pack(anchor=tk.W, padx=8, pady=(8,0))
            price_e = ttk.Entry(win); price_e.pack(fill=tk.X, padx=8)
            ttk.Label(win, text='Stock:').pack(anchor=tk.W, padx=8, pady=(8,0))
            stock_e = ttk.Entry(win); stock_e.pack(fill=tk.X, padx=8)
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
                    messagebox.showerror('Error', 'Nombre vacío'); return
                try:
                    # allow "5.000" or "5000.00"
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

    # ---------- search for category ----------
    def open_search_for_category(self, category_id, category_name):
        key = f'search_cat_{category_id}'
        def creator():
            win = tk.Toplevel(self.root)
            win.title(f'Buscar productos - Vender como: {category_name}')
            win.geometry('760x480')
            top = ttk.Frame(win); top.pack(fill=tk.X, padx=8, pady=6)
            ttk.Label(top, text=f'Vender como: {category_name}', font=(None, 11, 'bold')).pack(side=tk.LEFT)
            ttk.Label(top, text='  | Buscar:').pack(side=tk.LEFT, padx=(8,0))
            qvar = tk.StringVar()
            qentry = ttk.Entry(top, textvariable=qvar); qentry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6); qentry.focus()
            cols = ('id','code','name','price','stock','cat')
            tree = ttk.Treeview(win, columns=cols, show='headings', height=16)
            for c in cols:
                tree.heading(c, text=c.capitalize())
            tree.column('id', width=60, anchor=tk.CENTER)
            tree.column('price', width=110, anchor=tk.E)
            tree.pack(fill=tk.BOTH, expand=True, padx=8)
            qty_var = tk.IntVar(value=1)
            qty_frame = ttk.Frame(win); qty_frame.pack(fill=tk.X, padx=8, pady=6)
            ttk.Label(qty_frame, text='Cantidad:').pack(side=tk.LEFT)
            qty_spin = ttk.Spinbox(qty_frame, from_=1, to=999, textvariable=qty_var, width=6); qty_spin.pack(side=tk.LEFT, padx=6)

            def load_list():
                for i in tree.get_children():
                    tree.delete(i)
                rows = get_all_products(qvar.get().strip())
                for r in rows:
                    pid, code, name, price, stock, cid = r
                    tree.insert('', tk.END, values=(pid, code, name, format_money(price), stock, get_category_name(cid)))
                kids = tree.get_children()
                if kids:
                    tree.selection_set(kids[0]); tree.focus(kids[0]); tree.see(kids[0])

            # realtime
            qvar.trace_add('write', lambda *a: load_list())

            def reassign():
                sel = tree.selection()
                if not sel:
                    messagebox.showwarning('Aviso', 'Selecciona un producto'); return
                vals = tree.item(sel[0], 'values')
                pid = int(vals[0])
                cats = get_categories()
                opts = ['0 - Ninguna'] + [f"{cid} - {n}" for cid, n in cats]
                choice = simpledialog.askstring('Reasignar categoría', 'Escribe la opción (ej: 2 - Snacks):\n' + '\n'.join(opts), parent=win)
                if not choice:
                    return
                try:
                    cid = int(choice.split(' - ')[0])
                except:
                    messagebox.showerror('Error', 'Formato inválido'); return
                if cid == 0: cid = None
                update_product_category(pid, cid)
                load_list()
                self.load_products()

            def add_selected(_ev=None):
                sel = tree.selection()
                if not sel:
                    load_list(); return
                vals = tree.item(sel[0], 'values')
                pid = int(vals[0])
                code = vals[1]
                name = vals[2]
                # price shown is formatted; read real DB to be safe
                prod = get_product_by_id(pid)
                if not prod:
                    messagebox.showerror('Error', 'Producto no encontrado'); return
                price = prod['price']
                stock = int(prod['stock'])
                # ask quantity modal
                default_qty = int(qty_var.get()) if qty_var.get() else 1
                qty = simpledialog.askinteger("Cantidad", f"Ingrese la cantidad para '{name}' (stock disponible: {stock}):", parent=win, minvalue=1, initialvalue=default_qty, maxvalue=stock)
                if qty is None:
                    return
                if qty <= 0:
                    messagebox.showwarning('Aviso', 'Cantidad inválida'); return
                if stock < qty:
                    messagebox.showwarning('Stock insuficiente', f'Stock disponible: {stock}'); return
                self.add_to_cart(pid, code, name, price, qty, category_id=category_id)
                self.load_products()
                load_list()

            # keyboard focus helper: if any key typed, go to qentry and insert char
            def focus_search(event):
                if win.focus_get() != qentry:
                    qentry.focus_set()
                    if event.char.isprintable():
                        qentry.delete(0, tk.END)
                        qentry.insert(tk.END, event.char)
                        qentry.icursor(tk.END)
            win.bind("<Key>", focus_search)

            tree.bind('<Double-1>', lambda e: add_selected())
            tree.bind('<Return>', lambda e: add_selected())
            tree.bind('<Down>', lambda e: self.tree_move(tree, 1))
            tree.bind('<Up>', lambda e: self.tree_move(tree, -1))
            qentry.bind('<Return>', lambda e: load_list())
            win.bind('<Escape>', lambda e: win.destroy())

            btnf = ttk.Frame(win); btnf.pack(fill=tk.X, padx=8, pady=6)
            ttk.Button(btnf, text='Reasignar categoría del producto', command=reassign).pack(side=tk.LEFT)
            ttk.Button(btnf, text='Agregar seleccionado al carrito (Enter)', command=add_selected).pack(side=tk.RIGHT)
            load_list()
            return win
        return self.open_window_once(key, creator)

    # ---------- products list center interactions ----------
    def load_products(self, q=None):
        if q is None:
            q = self.search_var.get().strip()
        for i in self.products_tree.get_children():
            self.products_tree.delete(i)
        rows = get_all_products(q)
        for r in rows:
            pid, code, name, price, stock, cid = r
            self.products_tree.insert('', tk.END, values=(pid, code, name, format_money(price), stock, get_category_name(cid)))

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
        prod = get_product_by_id(pid)
        if not prod:
            messagebox.showerror('Error', 'Producto no encontrado'); return
        code = prod['code']; name = prod['name']; price = prod['price']; stock = prod['stock']
        qty = simpledialog.askinteger('Cantidad', f'Cantidad a agregar (stock: {stock}):', parent=self.root, minvalue=1, maxvalue=stock)
        if not qty:
            return
        use_prod_cat = messagebox.askyesno('Categoría', 'Usar la categoría del producto para esta venta? (Sí)')
        cat = prod['category_id'] if use_prod_cat else None
        self.add_to_cart(pid, code, name, price, qty, cat)
        self.load_products()

    # ---------- keyboard tree move helper ----------
    def tree_move(self, tree, delta):
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

    # ---------- cart operations ----------
    def add_to_cart(self, product_id, code, name, price, qty, category_id=None):
        price_int = parse_money_to_int(price)
        qty_int = int(qty)
        if qty_int <= 0:
            messagebox.showwarning("Cantidad inválida", "La cantidad debe ser mayor que 0.")
            return
        if code in self.cart:
            self.cart[code].qty += qty_int
        else:
            self.cart[code] = CartItem(product_id, code, name, price_int, qty_int, category_id)
        self.refresh_cart()
        try:
            self.update_category_buttons_state()
        except Exception:
            pass

    def refresh_cart(self):
        try:
            self.cart_listbox.delete(0, tk.END)
            total = 0
            debug_lines = []
            for item in self.cart.values():
                price_i = int(item.price)
                qty_i = int(item.qty)
                subtotal = price_i * qty_i
                total += subtotal
                catname = get_category_name(item.category_id)
                line = f"{qty_i} x {item.name} ({item.code}) [{catname}] - ${format_money(subtotal)}"
                self.cart_listbox.insert(tk.END, line)
                debug_lines.append(f"{item.code}: price={price_i}, qty={qty_i}, subtotal={subtotal}")
            self.total_var.set(f"Total: ${format_money(total)}")
            # debug print - comment out if undesired
            # print("DEBUG CART CONTENTS:"); [print("  ", dl) for dl in debug_lines]; print("DEBUG TOTAL (int):", total)
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
        try:
            self.update_category_buttons_state()
        except Exception:
            pass

    def clear_cart(self):
        if messagebox.askyesno('Confirmar', 'Vaciar carrito?'):
            self.cart.clear()
            self.refresh_cart()
            try:
                self.update_category_buttons_state()
            except Exception:
                pass

    # ---------- checkout simple (keyboard-friendly) ----------
    def checkout_simple(self):
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

            modes = ["Cobrar exacto", "Ingresar recibido", "Ingresar devuelta"]
            lb = tk.Listbox(win, height=len(modes), exportselection=False)
            for m in modes: lb.insert(tk.END, m)
            lb.pack(fill=tk.X, padx=12)
            lb.selection_set(0); lb.focus_set()

            frame = ttk.Frame(win, padding=(12,8)); frame.pack(fill=tk.X)
            ttk.Label(frame, text="Monto (si aplica):").grid(row=0, column=0, sticky=tk.W)
            amount_var = tk.StringVar(value=format_money(total))
            amount_entry = ttk.Entry(frame, textvariable=amount_var)
            amount_entry.grid(row=0, column=1, sticky=tk.EW, padx=(6,0))
            frame.columnconfigure(1, weight=1)

            change_var = tk.StringVar(value="0")
            ttk.Label(frame, text="Devolución:").grid(row=1, column=0, sticky=tk.W, pady=(8,0))
            ttk.Label(frame, textvariable=change_var, font=(None, 11, "bold")).grid(row=1, column=1, sticky=tk.E, pady=(8,0))
            status_var = tk.StringVar(value="")
            ttk.Label(win, textvariable=status_var, foreground="red").pack(pady=(6,0))

            def update_change_display():
                sel = lb.curselection()
                mode = lb.get(sel[0]) if sel else modes[0]
                val = parse_money_to_int(amount_var.get())
                if mode == "Cobrar exacto":
                    change_var.set("0"); status_var.set("")
                elif mode == "Ingresar recibido":
                    ch = val - total
                    change_var.set(format_money(ch) if ch >= 0 else "—")
                    status_var.set("" if val >= total else "Monto insuficiente")
                else:
                    dev = val
                    change_var.set(format_money(dev)); status_var.set("")

            def on_list_enter(event=None):
                sel = lb.curselection()
                if not sel: return
                mode = lb.get(sel[0])
                if mode == "Cobrar exacto":
                    finalize_payment_exact()
                else:
                    amount_entry.focus_set()
                    try: amount_entry.selection_range(0, tk.END)
                    except: pass

            lb.bind("<Return>", on_list_enter); lb.bind("<Double-1>", on_list_enter)

            def on_entry_enter(event=None):
                sel = lb.curselection()
                mode = lb.get(sel[0]) if sel else modes[0]
                if mode == "Ingresar recibido":
                    finalize_payment_received()
                elif mode == "Ingresar devuelta":
                    finalize_payment_change()

            amount_entry.bind("<Return>", on_entry_enter)
            amount_var.trace_add("write", lambda *a: update_change_display())

            def finalize_payment_exact():
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
                messagebox.showinfo("Venta realizada", f"Venta registrada (ID: {sale_id})\nTotal: ${format_money(total)}")
                # receipt optional
                self._after_sale_receipt_prompt(sale_id, items, total, total, 0)
                self.cart.clear(); self.refresh_cart()
                try: self.update_category_buttons_state()
                except: pass
                win.destroy()

            def finalize_payment_received():
                rec = parse_money_to_int(amount_var.get())
                if rec < total:
                    messagebox.showwarning("Error", f"Monto insuficiente. Total: ${format_money(total)}"); return
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
                change = rec - total
                messagebox.showinfo("Venta realizada",
                                    f"Venta registrada (ID: {sale_id})\nTotal: ${format_money(total)}\nRecibido: ${format_money(rec)}\nDevolución: ${format_money(change)}")
                self._after_sale_receipt_prompt(sale_id, items, total, rec, change)
                self.cart.clear(); self.refresh_cart()
                try: self.update_category_buttons_state()
                except: pass
                win.destroy()

            def finalize_payment_change():
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
                    messagebox.showerror("Error al cobrar", str(e)); return
                messagebox.showinfo("Venta realizada",
                                    f"Venta registrada (ID: {sale_id})\nTotal: ${format_money(total)}\nRecibido: ${format_money(rec)}\nDevolución: ${format_money(dev)}")
                self._after_sale_receipt_prompt(sale_id, items, total, rec, dev)
                self.cart.clear(); self.refresh_cart()
                try: self.update_category_buttons_state()
                except: pass
                win.destroy()

            win.bind("<Escape>", lambda e: win.destroy())
            win.bind("<Return>", lambda e: on_list_enter() if win.focus_get() == lb else on_entry_enter())
            update_change_display()
            return win
        return self.open_window_once("simple_payment", creator)

    # ---------- helper to prompt receipt after sale ----------
    def _after_sale_receipt_prompt(self, sale_id, items, total, rec_amount, change_amount):
        # items: list of dicts saved
        try:
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
            if messagebox.askyesno("Recibo", "¿Desea imprimir o guardar un recibo/factura de esta venta?"):
                if REPORTLAB_AVAILABLE and messagebox.askyesno("Formato", "¿Desea generar PDF? (Si no, se intentará imprimir)"):
                    try:
                        pdf_path = save_receipt_pdf(sale_id, sale_rows, total, received=rec_amount, change=change_amount, company_name="Mi Negocio")
                        messagebox.showinfo("PDF generado", f"PDF guardado en: {pdf_path}")
                    except Exception as e:
                        messagebox.showerror("Error PDF", str(e))
                else:
                    text = generate_receipt_text(sale_id, sale_rows, total, received=rec_amount, change=change_amount, company_name="Mi Negocio")
                    tmp = os.path.join(os.getcwd(), f"receipt_{sale_id}.txt")
                    save_receipt_text_file(text, tmp)
                    try:
                        if os.name == 'nt':
                            print_text_file_windows(tmp)
                        else:
                            print_text_file_lp(tmp)
                        messagebox.showinfo("Impresión", "Enviado a la impresora")
                    except Exception as e:
                        messagebox.showerror("Error impresión", str(e))
        except Exception as e:
            print("Error en bloque de impresión/recibo:", e)

    # ---------- historial ----------
    def open_history_window(self):
        def creator():
            win = tk.Toplevel(self.root)
            win.title('Historial y resumen')
            win.geometry('900x520')
            top = ttk.Frame(win, padding=8); top.pack(fill=tk.X)
            ttk.Label(top, text='Resumen por categoría (unidades vendidas)', font=(None, 11, 'bold')).pack(anchor=tk.W)
            sum_tree = ttk.Treeview(top, columns=('cat','qty'), show='headings', height=6)
            sum_tree.heading('cat', text='Categoría'); sum_tree.heading('qty', text='Unidades')
            sum_tree.column('qty', anchor=tk.E, width=120)
            sum_tree.pack(fill=tk.X, pady=6)
            c = conn.cursor()
            c.execute('SELECT COALESCE(category_id, 0) as cid, SUM(qty) as total_qty FROM sale_items GROUP BY COALESCE(category_id,0) ORDER BY total_qty DESC')
            rows = c.fetchall()
            for r in rows:
                cid = r['cid']; qty = r['total_qty']
                sum_tree.insert('', tk.END, values=(get_category_name(cid), qty if qty else 0))

            ttk.Separator(win, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
            bottom = ttk.Frame(win, padding=8); bottom.pack(fill=tk.BOTH, expand=True)
            ttk.Label(bottom, text='Ventas recientes (doble clic para detalle)', font=(None, 11, 'bold')).pack(anchor=tk.W)
            sales_tree = ttk.Treeview(bottom, columns=('id','created_at','total'), show='headings', height=12)
            sales_tree.heading('id', text='ID'); sales_tree.heading('created_at', text='Fecha / Hora'); sales_tree.heading('total', text='Total')
            sales_tree.column('total', anchor=tk.E, width=120)
            sales_tree.pack(fill=tk.BOTH, expand=True)
            for s in get_sales_recent(200):
                sales_tree.insert('', tk.END, values=(s['id'], s['created_at'], f"${format_money(s['total'])}"))
            def on_double(e):
                sel = sales_tree.selection(); 
                if not sel: return
                sale_id = int(sales_tree.item(sel[0], 'values')[0])
                self.open_sale_detail_window(sale_id)
            sales_tree.bind('<Double-1>', on_double)
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
            tree.heading('name', text='Producto'); tree.heading('qty', text='Cant.'); tree.heading('price', text='Precio'); tree.heading('cat', text='Categoría')
            tree.column('price', anchor=tk.E, width=100); tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
            for r in get_sale_items(sale_id):
                name, qty, price, cid = r
                tree.insert('', tk.END, values=(name, qty, f"${format_money(price)}", get_category_name(cid)))
            btnf = ttk.Frame(win); btnf.pack(fill=tk.X, padx=8, pady=6)
            ttk.Button(btnf, text="Imprimir / Guardar recibo", command=lambda: self.print_from_history(sale_id)).pack(side=tk.RIGHT)
            win.bind('<Escape>', lambda e: win.destroy())
            return win
        return self.open_window_once(f'sale_{sale_id}', creator)

    def print_from_history(self, sale_id):
        c = conn.cursor()
        c.execute("SELECT created_at, total FROM sales WHERE id=?", (sale_id,))
        sale = c.fetchone()
        if not sale:
            messagebox.showerror("Error", "Venta no encontrada"); return
        total = int(round(float(sale['total'])))
        rows = get_sale_items(sale_id)
        sale_rows = []
        for r in rows:
            name, qty, price, cid = r
            sale_rows.append({"product_name": name, "qty": qty, "price": price, "subtotal": int(price)*int(qty)})
        if messagebox.askyesno("Recibo", "¿Desea imprimir o guardar un recibo/factura de esta venta?"):
            if REPORTLAB_AVAILABLE and messagebox.askyesno("Formato", "¿Desea generar PDF? (Si no, se intentará imprimir)"):
                try:
                    pdf_path = save_receipt_pdf(sale_id, sale_rows, total, company_name="Mi Negocio")
                    messagebox.showinfo("PDF generado", f"PDF guardado en: {pdf_path}")
                except Exception as e:
                    messagebox.showerror("Error PDF", str(e))
            else:
                text = generate_receipt_text(sale_id, sale_rows, total, company_name="Mi Negocio")
                tmp = os.path.join(os.getcwd(), f"receipt_{sale_id}.txt")
                save_receipt_text_file(text, tmp)
                try:
                    if os.name == 'nt':
                        print_text_file_windows(tmp)
                    else:
                        print_text_file_lp(tmp)
                    messagebox.showinfo("Impresión", "Enviado a la impresora")
                except Exception as e:
                    messagebox.showerror("Error impresión", str(e))

# ---------------- run ----------------
if __name__ == '__main__':
    root = tk.Tk()
    app = POSApp(root)
    root.mainloop()
