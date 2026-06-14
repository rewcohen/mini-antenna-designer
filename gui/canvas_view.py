"""Center canvas: large, zoom/pan-able SVG preview of the current design.

Subscribes to the session and re-renders whenever a design is generated. Shows a
placeholder before the first design (or when SVG libraries are unavailable).
"""
from __future__ import annotations

from tkinter import Canvas, BOTH, X, Y, LEFT, RIGHT, BOTTOM, TOP, NW, CENTER, HORIZONTAL, VERTICAL
import ttkbootstrap as ttk
from ttkbootstrap.constants import SECONDARY

from gui.session import DesignSession, EVT_GENERATED
from gui.svg_render import render_svg_to_photoimage, PIL_AVAILABLE

PAD_S, PAD_M = 4, 8

_MIN_ZOOM, _MAX_ZOOM = 0.2, 8.0


class CanvasView:
    """SVG preview surface with zoom in/out/fit and drag-to-pan."""

    def __init__(self, parent, session: DesignSession):
        self.session = session
        self.zoom = 1.0
        self._photo = None  # keep a ref so Tk doesn't garbage-collect the image
        self._img_id = None
        self._drag = None

        self.frame = ttk.Frame(parent)

        toolbar = ttk.Frame(self.frame, padding=(0, 0, 0, PAD_S))
        toolbar.pack(side=TOP, fill=X)
        ttk.Button(toolbar, text="−", width=3, bootstyle=SECONDARY,
                   command=self.zoom_out).pack(side=LEFT, padx=(0, PAD_S))
        ttk.Button(toolbar, text="+", width=3, bootstyle=SECONDARY,
                   command=self.zoom_in).pack(side=LEFT, padx=(0, PAD_S))
        ttk.Button(toolbar, text="Fit", bootstyle=SECONDARY,
                   command=self.fit).pack(side=LEFT, padx=(0, PAD_S))
        self.zoom_label = ttk.Label(toolbar, text="100%")
        self.zoom_label.pack(side=LEFT, padx=PAD_S)

        body = ttk.Frame(self.frame)
        body.pack(side=TOP, fill=BOTH, expand=True)
        self.canvas = Canvas(body, highlightthickness=0, background="#f4f4f4")
        vbar = ttk.Scrollbar(body, orient=VERTICAL, command=self.canvas.yview)
        hbar = ttk.Scrollbar(body, orient=HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        vbar.pack(side=RIGHT, fill=Y)
        hbar.pack(side=BOTTOM, fill=X)
        self.canvas.pack(side=LEFT, fill=BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<MouseWheel>", self._on_wheel)

        session.subscribe(self._on_event)
        self._show_placeholder()

    # --- session ---
    def _on_event(self, event: str):
        if event == EVT_GENERATED:
            self.zoom = 1.0
            self._render()

    # --- zoom ---
    def zoom_in(self):
        self.zoom = min(_MAX_ZOOM, self.zoom * 1.25)
        self._render()

    def zoom_out(self):
        self.zoom = max(_MIN_ZOOM, self.zoom / 1.25)
        self._render()

    def fit(self):
        self.zoom = 1.0
        self._render()

    # --- pan ---
    def _on_press(self, e):
        self.canvas.scan_mark(e.x, e.y)

    def _on_drag(self, e):
        self.canvas.scan_dragto(e.x, e.y, gain=1)

    def _on_wheel(self, e):
        (self.zoom_in if e.delta > 0 else self.zoom_out)()

    # --- render ---
    def _render(self):
        self.zoom_label.configure(text=f"{int(self.zoom * 100)}%")
        svg = self.session.svg
        if not svg:
            self._show_placeholder()
            return
        photo = render_svg_to_photoimage(svg, self.zoom)
        if photo is None:
            self._show_placeholder(
                "SVG preview unavailable" if not PIL_AVAILABLE else "Could not render design")
            return
        self._photo = photo
        self.canvas.delete("all")
        self._img_id = self.canvas.create_image(0, 0, anchor=NW, image=photo)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _show_placeholder(self, text="Generate a design to preview it here"):
        self.canvas.delete("all")
        self.canvas.update_idletasks()
        w = self.canvas.winfo_width() or 600
        h = self.canvas.winfo_height() or 400
        self.canvas.create_text(w // 2, h // 2, text=text, fill="#888", anchor=CENTER)
