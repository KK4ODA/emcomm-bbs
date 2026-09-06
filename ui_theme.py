"""
Emcomm BBS - Shared Tk look and feel

``apply_theme(root)`` configures ttk styles once; the widget helpers below
(Card, LogPanel, ScrollFrame, StatusBar, header) give both GUIs the same
visual language without repeating style names everywhere.
"""

import sys
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
from datetime import datetime

PALETTE = {
    "bg":         "#eef1f5",   # window background
    "card":       "#ffffff",   # panels
    "border":     "#d6dbe3",
    "text":       "#1c2431",
    "muted":      "#6b7482",
    "accent":     "#f2a23a",   # amber - primary actions
    "accent_hi":  "#e8931f",
    "accent_dk":  "#8a4b00",
    "header":     "#152238",   # navy header bar
    "header_fg":  "#f5f7fa",
    "header_mut": "#9aa8bd",
    "ok":         "#1f8a4c",
    "warn":       "#b7791f",
    "err":        "#c0392b",
    "info":       "#2b6cb0",
    "log_bg":     "#111a2b",
    "log_fg":     "#d8e0ea",
    "log_ts":     "#5f6f87",
    "log_ok":     "#5fd38a",
    "log_warn":   "#f6c453",
    "log_err":    "#ff7b72",
    "log_head":   "#8fb3ff",
}

if sys.platform == "win32":
    UI_FONT, MONO_FONT = "Segoe UI", "Consolas"
elif sys.platform == "darwin":
    UI_FONT, MONO_FONT = "Helvetica Neue", "Menlo"
else:
    UI_FONT, MONO_FONT = "DejaVu Sans", "DejaVu Sans Mono"

FONTS = {}


def apply_theme(root):
    """Configure fonts and ttk styles. Call once, right after ``tk.Tk()``."""
    p = PALETTE
    FONTS.update({
        "base":   (UI_FONT, 10),
        "bold":   (UI_FONT, 10, "bold"),
        "small":  (UI_FONT, 9),
        "title":  (UI_FONT, 15, "bold"),
        "h2":     (UI_FONT, 11, "bold"),
        "big":    (UI_FONT, 22, "bold"),
        "mono":   (MONO_FONT, 10),
    })
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        try:
            tkfont.nametofont(name).configure(family=UI_FONT, size=10)
        except tk.TclError:
            pass

    root.configure(bg=p["bg"])
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".", background=p["bg"], foreground=p["text"], font=FONTS["base"],
                    bordercolor=p["border"], focuscolor=p["bg"])
    style.configure("TFrame", background=p["bg"])
    style.configure("TLabel", background=p["bg"], foreground=p["text"])
    style.configure("Muted.TLabel", foreground=p["muted"], font=FONTS["small"])
    style.configure("H2.TLabel", font=FONTS["h2"])
    style.configure("Big.TLabel", font=FONTS["big"])

    # Card variants (white background)
    style.configure("Card.TFrame", background=p["card"])
    style.configure("Card.TLabel", background=p["card"], foreground=p["text"])
    style.configure("CardMuted.TLabel", background=p["card"], foreground=p["muted"], font=FONTS["small"])
    style.configure("CardH2.TLabel", background=p["card"], font=FONTS["h2"])
    style.configure("CardBig.TLabel", background=p["card"], font=FONTS["big"])
    style.configure("CardOk.TLabel", background=p["card"], foreground=p["ok"], font=FONTS["bold"])
    style.configure("CardWarn.TLabel", background=p["card"], foreground=p["warn"], font=FONTS["bold"])
    style.configure("CardPath.TLabel", background=p["card"], foreground=p["info"], font=FONTS["small"])

    style.configure("Card.TCheckbutton", background=p["card"], foreground=p["text"], padding=(2, 3))
    style.map("Card.TCheckbutton", background=[("active", p["card"])])
    try:
        # Borrow the native Windows checkbox glyph; clam's own is a crude "x".
        style.element_create("Native.Checkbutton.indicator", "from", "vista", "Checkbutton.indicator")
        style.layout("Card.TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [
            ("Native.Checkbutton.indicator", {"side": "left", "sticky": ""}),
            ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [
                ("Checkbutton.label", {"sticky": "nswe"})]})]})])
    except tk.TclError:  # not on Windows: tint clam's indicator instead
        style.configure("Card.TCheckbutton", indicatormargin=(0, 0, 8, 0))
        style.map("Card.TCheckbutton",
                  indicatorbackground=[("selected", p["accent_hi"]), ("!selected", p["card"])],
                  indicatorforeground=[("selected", "#ffffff")])

    # Buttons
    style.configure("TButton", background=p["card"], foreground=p["text"], padding=(12, 6),
                    borderwidth=1, relief="flat", bordercolor=p["border"], focusthickness=0)
    style.map("TButton",
              background=[("disabled", p["bg"]), ("active", "#f7f8fa"), ("pressed", "#e9ecf1")],
              foreground=[("disabled", p["muted"])],
              bordercolor=[("active", "#b9c1cc")])
    style.configure("Accent.TButton", background=p["accent"], foreground=p["text"],
                    font=FONTS["bold"], bordercolor=p["accent"], padding=(16, 7))
    style.map("Accent.TButton",
              background=[("disabled", "#f5d9ad"), ("active", p["accent_hi"]), ("pressed", "#d9861a")],
              bordercolor=[("disabled", "#f5d9ad"), ("active", p["accent_hi"])],
              foreground=[("disabled", "#9a7b52")])
    style.configure("Link.TButton", background=p["card"], foreground=p["info"], padding=(6, 3),
                    borderwidth=0, font=FONTS["small"])
    style.map("Link.TButton", background=[("active", p["card"])], foreground=[("active", p["accent_dk"])])

    # Inputs
    style.configure("TEntry", fieldbackground=p["card"], bordercolor=p["border"],
                    lightcolor=p["card"], darkcolor=p["card"], padding=(6, 5), insertcolor=p["text"])
    style.map("TEntry", bordercolor=[("focus", p["accent_hi"])], lightcolor=[("focus", p["accent_hi"])],
              darkcolor=[("focus", p["accent_hi"])])
    style.configure("TSpinbox", fieldbackground=p["card"], bordercolor=p["border"], arrowsize=13,
                    lightcolor=p["card"], darkcolor=p["card"], padding=(6, 4), background=p["card"])
    style.map("TSpinbox", bordercolor=[("focus", p["accent_hi"])])

    # Notebook
    style.configure("TNotebook", background=p["bg"], borderwidth=0, tabmargins=(0, 0, 0, 0))
    style.configure("TNotebook.Tab", background=p["bg"], foreground=p["muted"], padding=(18, 9),
                    font=FONTS["bold"], borderwidth=0,
                    bordercolor=p["bg"], lightcolor=p["bg"], darkcolor=p["bg"])
    style.map("TNotebook.Tab",
              background=[("selected", p["card"])],
              foreground=[("selected", p["accent_dk"])],
              bordercolor=[("selected", p["border"])],
              lightcolor=[("selected", p["card"])],
              darkcolor=[("selected", p["card"])],
              padding=[("selected", (18, 9))],
              expand=[("selected", (0, 0, 0, 0))])
    style.layout("TNotebook.Tab", [("Notebook.tab", {"sticky": "nswe", "children": [
        ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [
            ("Notebook.label", {"side": "top", "sticky": ""})]})]})])

    style.configure("TSeparator", background=p["border"])
    style.configure("Vertical.TScrollbar", background=p["bg"], troughcolor=p["bg"],
                    bordercolor=p["bg"], arrowcolor=p["muted"])
    return p


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------

def header(parent, title, subtitle=""):
    """Dark banner across the top of the window. Returns (frame, right_label)."""
    p = PALETTE
    bar = tk.Frame(parent, bg=p["header"], padx=20, pady=14)
    tk.Label(bar, text=title, bg=p["header"], fg=p["header_fg"], font=FONTS["title"]).pack(side="left")
    if subtitle:
        tk.Label(bar, text=subtitle, bg=p["header"], fg=p["header_mut"],
                 font=FONTS["small"]).pack(side="left", padx=(12, 0), pady=(4, 0))
    right = tk.Label(bar, text="", bg=p["header"], fg=p["header_mut"], font=FONTS["small"])
    right.pack(side="right")
    return bar, right


class Card(tk.Frame):
    """White panel with a border and optional title. Put content in ``.body``."""

    def __init__(self, parent, title=None, subtitle=None, padding=14, **kw):
        p = PALETTE
        super().__init__(parent, bg=p["card"], highlightbackground=p["border"],
                         highlightthickness=1, bd=0, **kw)
        inner = tk.Frame(self, bg=p["card"], padx=padding, pady=padding - 2)
        inner.pack(fill="both", expand=True)
        if title:
            head = tk.Frame(inner, bg=p["card"])
            head.pack(fill="x", pady=(0, 8))
            tk.Label(head, text=title, bg=p["card"], fg=p["text"], font=FONTS["h2"]).pack(side="left")
            if subtitle:
                tk.Label(head, text=subtitle, bg=p["card"], fg=p["muted"],
                         font=FONTS["small"]).pack(side="left", padx=(10, 0), pady=(2, 0))
            self.head = head
        self.body = tk.Frame(inner, bg=p["card"])
        self.body.pack(fill="both", expand=True)


class LogPanel(tk.Frame):
    """Dark, read-only activity log with colored severity tags.

    ``append`` is safe to call from any thread - writes are marshalled onto
    the Tk event loop with ``after``.
    """

    MAX_LINES = 2000

    _PREFIX_LEVELS = (
        ("✓", "ok"), ("✗", "err"), ("⚠", "warn"), ("=" * 10, "head"),
    )

    def __init__(self, parent, height=12):
        p = PALETTE
        super().__init__(parent, bg=p["log_bg"], highlightbackground=p["border"], highlightthickness=1)
        self.text = tk.Text(self, height=height, wrap="word", bg=p["log_bg"], fg=p["log_fg"],
                            insertbackground=p["log_fg"], font=FONTS["mono"], bd=0, padx=10, pady=8,
                            state="disabled", cursor="arrow", selectbackground="#2d3f5e")
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        for tag, color in (("ts", p["log_ts"]), ("ok", p["log_ok"]), ("warn", p["log_warn"]),
                           ("err", p["log_err"]), ("head", p["log_head"]), ("info", p["log_fg"])):
            self.text.tag_configure(tag, foreground=color)

    def append(self, message, level=None):
        self.after(0, self._append, str(message), level)

    def _append(self, message, level):
        if level is None:
            stripped = message.lstrip()
            level = next((lvl for prefix, lvl in self._PREFIX_LEVELS if stripped.startswith(prefix)), "info")
        stamp = datetime.now().strftime("%H:%M:%S")
        self.text.configure(state="normal")
        self.text.insert("end", f"{stamp}  ", "ts")
        self.text.insert("end", message + "\n", level)
        lines = int(self.text.index("end-1c").split(".")[0])
        if lines > self.MAX_LINES:
            self.text.delete("1.0", f"{lines - self.MAX_LINES}.0")
        self.text.configure(state="disabled")
        self.text.see("end")

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")


class ScrollFrame(ttk.Frame):
    """Vertically scrollable container. Put content in ``.body``."""

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.canvas = tk.Canvas(self, bg=PALETTE["bg"], highlightthickness=0, bd=0)
        self.scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.body = ttk.Frame(self.canvas)
        self._win = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll.pack(side="right", fill="y")
        self.body.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        for w in (self.canvas, self.body):
            w.bind("<Enter>", lambda e: self._bind_wheel())
            w.bind("<Leave>", lambda e: self._unbind_wheel())

    def _bind_wheel(self):
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)
        self.canvas.bind_all("<Button-4>", self._on_wheel)
        self.canvas.bind_all("<Button-5>", self._on_wheel)

    def _unbind_wheel(self):
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.unbind_all(seq)

    def _on_wheel(self, event):
        if self.canvas.bbox("all") and self.canvas.bbox("all")[3] <= self.canvas.winfo_height():
            return
        step = -1 if (event.num == 4 or event.delta > 0) else 1
        self.canvas.yview_scroll(step, "units")


class StatusBar(tk.Frame):
    """Thin footer: left-aligned message, right-aligned detail."""

    def __init__(self, parent):
        p = PALETTE
        super().__init__(parent, bg=p["card"], highlightbackground=p["border"], highlightthickness=1)
        self.left = tk.Label(self, text="", bg=p["card"], fg=p["muted"], font=FONTS["small"], anchor="w")
        self.left.pack(side="left", padx=12, pady=4)
        self.right = tk.Label(self, text="", bg=p["card"], fg=p["muted"], font=FONTS["small"], anchor="e")
        self.right.pack(side="right", padx=12, pady=4)

    def set(self, left=None, right=None, tone="muted"):
        color = PALETTE.get(tone, PALETTE["muted"])
        if left is not None:
            self.left.configure(text=left, fg=color)
        if right is not None:
            self.right.configure(text=right)


def field_row(parent, label, widget_factory, hint=None, button=None, row=0, pady=(0, 6)):
    """Grid helper: label | widget [| button] with an optional hint line below.

    ``widget_factory(parent)`` must return the input widget. Returns it.
    """
    p = PALETTE
    tk.Label(parent, text=label, bg=p["card"], fg=p["text"], font=FONTS["base"],
             anchor="w").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=pady)
    widget = widget_factory(parent)
    widget.grid(row=row, column=1, sticky="ew", pady=pady)
    if button is not None:
        button.grid(row=row, column=2, sticky="e", padx=(8, 0), pady=pady)
    if hint:
        tk.Label(parent, text=hint, bg=p["card"], fg=p["muted"], font=FONTS["small"],
                 anchor="w").grid(row=row + 1, column=1, columnspan=2, sticky="w", pady=(0, 10))
    parent.columnconfigure(1, weight=1)
    return widget
