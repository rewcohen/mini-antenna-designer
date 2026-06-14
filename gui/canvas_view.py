"""Center canvas: large, zoom/pan-able SVG preview of the current design.

Builds its own layered SVG from ``session.geometry`` + ``session.svg_metadata``
so layer toggles (feed/pattern/grid/details) recompose the preview on the fly.
Subscribes to the session and re-renders whenever a design is generated. Shows a
placeholder before the first design (or when SVG libraries are unavailable).
"""
from __future__ import annotations

from tkinter import (Canvas, BooleanVar, BOTH, X, Y, LEFT, RIGHT, BOTTOM, TOP, NW,
                     CENTER, HORIZONTAL, VERTICAL)
import ttkbootstrap as ttk

from gui.session import DesignSession, EVT_GENERATED
from gui.svg_render import render_svg_to_photoimage, geometry_to_svg, PIL_AVAILABLE

from gui.constants import PAD_S, PAD_M

_MIN_ZOOM, _MAX_ZOOM = 0.2, 8.0


class CanvasView:
    """SVG preview surface with zoom in/out/fit, layer toggles and drag-to-pan."""

    def __init__(self, parent, session: DesignSession, exporter):
        self.session = session
        self.exporter = exporter
        self.zoom = 1.0
        self._fit = True            # fit-to-viewport mode (vs. explicit zoom)
        self._svg = None            # cached layered SVG for the current design
        self._photo = None  # keep a ref so Tk doesn't garbage-collect the image
        self._img_id = None
        self._drag = None
        self._cfg_job = None        # debounce handle for <Configure> re-fit

        # Layer toggles: clean default preview (just traces + feed pads).
        self.l_feed = BooleanVar(value=True)
        self.l_pattern = BooleanVar(value=False)
        self.l_grid = BooleanVar(value=False)
        self.l_annot = BooleanVar(value=False)

        self.frame = ttk.Frame(parent)

        zoom_bar = ttk.Frame(self.frame, padding=(0, 0, 0, PAD_S))
        zoom_bar.pack(side=TOP, fill=X)
        ttk.Button(zoom_bar, text="−", width=3, bootstyle="secondary-outline",
                   command=self.zoom_out).pack(side=LEFT, padx=(0, PAD_S))
        ttk.Button(zoom_bar, text="+", width=3, bootstyle="secondary-outline",
                   command=self.zoom_in).pack(side=LEFT, padx=(0, PAD_S))
        ttk.Button(zoom_bar, text="Fit", bootstyle="secondary-outline",
                   command=self.fit).pack(side=LEFT, padx=(0, PAD_S))
        self.zoom_label = ttk.Label(zoom_bar, text="100%")
        self.zoom_label.pack(side=LEFT, padx=PAD_S)

        # Layer toggles on their own row so they never clip on a narrow canvas.
        layer_bar = ttk.Frame(self.frame, padding=(0, 0, 0, PAD_S))
        layer_bar.pack(side=TOP, fill=X)
        ttk.Label(layer_bar, text="Layers:").pack(side=LEFT, padx=(0, PAD_S))
        for text, var in (("Feed", self.l_feed), ("Pattern", self.l_pattern),
                          ("Grid", self.l_grid), ("Details", self.l_annot)):
            ttk.Checkbutton(layer_bar, text=text, variable=var,
                            command=self._on_layer_toggle,
                            bootstyle="round-toggle").pack(side=LEFT, padx=PAD_S)

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
        self.canvas.bind("<Configure>", self._on_configure)

        session.subscribe(self._on_event)
        self._show_placeholder()

    def apply_theme(self, background: str):
        """Re-skin the tk Canvas (ttkbootstrap leaves plain tk widgets alone)."""
        self.canvas.configure(background=background)
        self._render()

    # --- SVG composition ---
    def _build_svg(self):
        """Compose the layered SVG for the current design, or None if no design."""
        if not self.session.has_design:
            return None
        md = dict(self.session.svg_metadata or {})
        md['layers'] = {'feed': self.l_feed.get(), 'pattern': self.l_pattern.get(),
                        'grid': self.l_grid.get(), 'annotations': self.l_annot.get()}
        return geometry_to_svg(self.exporter, self.session.geometry, md)

    def _on_layer_toggle(self):
        self._svg = self._build_svg()
        self._render()

    # --- session ---
    def _on_event(self, event: str):
        if event == EVT_GENERATED:
            self._svg = self._build_svg()
            self._fit = True
            self._render()

    # --- zoom ---
    def zoom_in(self):
        self._fit = False
        self.zoom = min(_MAX_ZOOM, self.zoom * 1.25)
        self._render()

    def zoom_out(self):
        self._fit = False
        self.zoom = max(_MIN_ZOOM, self.zoom / 1.25)
        self._render()

    def fit(self):
        self._fit = True
        self._render()

    # --- pan ---
    def _on_press(self, e):
        self.canvas.scan_mark(e.x, e.y)

    def _on_drag(self, e):
        self.canvas.scan_dragto(e.x, e.y, gain=1)

    def _on_wheel(self, e):
        (self.zoom_in if e.delta > 0 else self.zoom_out)()

    def _on_configure(self, e):
        """Debounce viewport resizes so we re-fit/recenter without thrashing."""
        try:
            if self._cfg_job is not None:
                self.canvas.after_cancel(self._cfg_job)
            self._cfg_job = self.canvas.after(80, self._render)
        except Exception:
            pass

    # --- render ---
    def _render(self):
        self._cfg_job = None
        svg = self._svg
        if not svg:
            self._show_placeholder()
            return
        cw = self.canvas.winfo_width() or 600
        ch = self.canvas.winfo_height() or 400
        photo, z, size = render_svg_to_photoimage(
            svg, zoom=self.zoom, fit_size=((cw, ch) if self._fit else None))
        if photo is None:
            self._show_placeholder(
                "SVG preview unavailable" if not PIL_AVAILABLE else "Could not render design")
            return
        self.zoom = z
        self._photo = photo
        zw, zh = size
        self.zoom_label.configure(text=f"{int(z * 100)}%")
        self.canvas.delete("all")
        if zw <= cw and zh <= ch:
            self._img_id = self.canvas.create_image(
                (cw - zw) // 2, (ch - zh) // 2, anchor=NW, image=photo)
            self.canvas.configure(scrollregion=(0, 0, cw, ch))
        else:
            self._img_id = self.canvas.create_image(0, 0, anchor=NW, image=photo)
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _show_placeholder(self, text="Generate a design to preview it here"):
        self.canvas.delete("all")
        self.canvas.update_idletasks()
        w = self.canvas.winfo_width() or 600
        h = self.canvas.winfo_height() or 400
        self.canvas.create_text(w // 2, h // 2, text=text, fill="#888", anchor=CENTER)
