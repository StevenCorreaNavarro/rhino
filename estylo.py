import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont

def main():
    root = tk.Tk()
    root.title("Demo estilizado - Tkinter")
    root.geometry("520x360")
    root.resizable(False, False)

    # Fuente global
    default_font = tkfont.Font(family="Segoe UI", size=10)
    root.option_add("*Font", default_font)

    # Colores (puedes cambiar aquí)
    PRIMARY = "#2B7A78"    # verde oscuro
    ACCENT = "#17252A"     # casi negro
    BG = "#2B7A78"         # fondo claro
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
    style.configure("TButton",
                    background=PRIMARY,
                    foreground="white",
                    padding=8,
                    relief="flat")
    # botón principal con estilo personalizado
    style.map("TButton",  background=[("active", "#1f5f5d"), ("pressed", "#144F4D")])

    # Contenedor principal
    container = ttk.Frame(root, padding=16, style="TFrame")
    container.pack(fill="both", expand=True)

    # Header
    header = ttk.Label(container, text="Punto de Venta - Demo", style="Header.TLabel")
    header.pack(anchor="w", pady=(0,8))

    # Card (simula tarjeta con fondo blanco)
    card = ttk.Frame(container, style="Card.TFrame", padding=12)
    card.pack(fill="x", pady=(0,12))

    # Contenido de la tarjeta
    name_label = ttk.Label(card, text="Artículo", style="Card.TLabel")
    name_label.grid(row=0, column=0, sticky="w")
    price_label = ttk.Label(card, text="$ 12.000", style="Card.TLabel")
    price_label.grid(row=0, column=1, sticky="e")

    desc = ttk.Label(card, text="Descripción breve del producto.", style="Card.TLabel")
    desc.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6,0))

    # Separador
    sep = ttk.Separator(container, orient="horizontal")
    sep.pack(fill="x", pady=8)

    # Botones
    btn_frame = ttk.Frame(container, style="TFrame")
    btn_frame.pack(fill="x")

    add_btn = ttk.Button(btn_frame, text="Agregar", command=lambda: print("Agregar"))
    add_btn.pack(side="left", padx=(0,10))

    pay_btn = ttk.Button(btn_frame, text="Pagar", command=lambda: print("Pagar"))
    pay_btn.pack(side="left")

    # Pie con info
    footer = ttk.Label(container, text="Status: listo", style="TLabel")
    footer.pack(anchor="w", pady=(12,0))

    root.mainloop()

if __name__ == "__main__":
    main()
