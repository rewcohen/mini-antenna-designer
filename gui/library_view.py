"""Library browser: list, search, load, delete and inspect saved designs (modal).

The left pane lists/searches designs; selecting one populates a Details pane on
the right (metadata, performance metrics, notes, thumbnail) and enables the
per-design actions (export, edit notes). Loading a design pushes its geometry
into the session and renders it on the main canvas.

Everything in the details pane is guarded so a malformed or old saved design can
never crash the dialog -- worst case a field shows a placeholder.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Callable, Optional
from tkinter import (StringVar, Canvas, BOTH, X, Y, LEFT, RIGHT, TOP, BOTTOM,
                     END, WORD, messagebox, filedialog)
import ttkbootstrap as ttk
from ttkbootstrap.constants import PRIMARY, SECONDARY, DANGER, INFO
from loguru import logger

from gui.constants import PAD_S, PAD_M

# Rendering the base64 SVG thumbnail goes through the shared svglib->PIL pipeline;
# it degrades to a placeholder when PIL/svglib are missing or rendering fails.
try:
    from gui.svg_render import render_svg_to_photoimage
except Exception:  # pragma: no cover - import-time guard
    render_svg_to_photoimage = None
    logger.warning("svg_render unavailable; library thumbnails disabled")

_THUMB_W, _THUMB_H = 220, 120


class LibraryDialog:
    """Modal browser over ``DesignStorage``. Calls ``on_load(metadata, geometry)``."""

    def __init__(self, parent, storage, on_load: Callable):
        self.storage = storage
        self.on_load = on_load
        self._rows = {}  # tree iid -> file_path
        self._thumb_image = None  # keep a reference so Tk doesn't GC the preview

        self.win = ttk.Toplevel(parent)
        self.win.title("Design Library")
        self.win.geometry("960x520")
        self.win.transient(parent)

        top = ttk.Frame(self.win, padding=PAD_M)
        top.pack(side=TOP, fill=X)
        self.query = StringVar()
        ttk.Label(top, text="Search").pack(side=LEFT, padx=(0, PAD_S))
        e = ttk.Entry(top, textvariable=self.query)
        e.pack(side=LEFT, fill=X, expand=True)
        e.bind("<KeyRelease>", lambda _e: self._refresh())
        ttk.Button(top, text="Refresh", bootstyle=SECONDARY,
                   command=self._refresh).pack(side=LEFT, padx=(PAD_S, 0))

        # Split layout: list on the left, details on the right.
        body = ttk.Frame(self.win, padding=(PAD_M, 0))
        body.pack(side=TOP, fill=BOTH, expand=True)

        left = ttk.Frame(body)
        left.pack(side=LEFT, fill=BOTH, expand=True)
        cols = ("name", "band", "freqs", "created")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="browse")
        for c, w in zip(cols, (180, 130, 130, 140)):
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=w)
        vbar = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vbar.set)
        vbar.pack(side=RIGHT, fill=Y)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        self.tree.bind("<Double-1>", lambda _e: self._load())
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._show_details())

        self.details = self._build_details(body)

        btns = ttk.Frame(self.win, padding=PAD_M)
        btns.pack(side=BOTTOM, fill=X)
        ttk.Button(btns, text="Load", bootstyle=PRIMARY, command=self._load).pack(
            side=LEFT, padx=(0, PAD_S))
        self.export_btn = ttk.Button(btns, text="Export Selected", bootstyle=INFO,
                                     command=self._export)
        self.export_btn.pack(side=LEFT, padx=(0, PAD_S))
        self.notes_btn = ttk.Button(btns, text="Edit Notes", bootstyle=SECONDARY,
                                    command=self._edit_notes)
        self.notes_btn.pack(side=LEFT, padx=(0, PAD_S))
        ttk.Button(btns, text="Delete", bootstyle=DANGER, command=self._delete).pack(
            side=LEFT)
        ttk.Button(btns, text="Close", bootstyle=SECONDARY,
                   command=self.win.destroy).pack(side=RIGHT)

        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.focus_set()
        self._refresh()

    # ----- details pane ---------------------------------------------------

    def _build_details(self, parent) -> ttk.Labelframe:
        """Build the right-hand details pane (thumbnail + text + stats)."""
        frame = ttk.Labelframe(parent, text="Details", padding=PAD_M)
        frame.pack(side=RIGHT, fill=BOTH, expand=True, padx=(PAD_M, 0))
        frame.configure(width=360)
        frame.pack_propagate(False)

        # Thumbnail preview at the top.
        self.thumb_canvas = Canvas(frame, width=_THUMB_W, height=_THUMB_H,
                                   highlightthickness=1, highlightbackground="#888",
                                   background="#ffffff")
        self.thumb_canvas.pack(side=TOP, pady=(0, PAD_M))

        # Scrollable metadata / metrics / notes text block.
        self.info = ttk.Text(frame, wrap=WORD, height=16, width=44,
                             relief="flat")
        self.info.pack(side=TOP, fill=BOTH, expand=True)
        self.info.configure(state="disabled")

        # Library stats line at the bottom.
        self.stats_var = StringVar(value="")
        ttk.Label(frame, textvariable=self.stats_var, bootstyle=SECONDARY).pack(
            side=BOTTOM, anchor="w", pady=(PAD_S, 0))
        return frame

    def _set_info(self, text: str):
        self.info.configure(state="normal")
        self.info.delete("1.0", END)
        self.info.insert(END, text)
        self.info.configure(state="disabled")

    def _set_thumbnail_placeholder(self, message: str):
        self._thumb_image = None
        self.thumb_canvas.delete("all")
        self.thumb_canvas.create_text(_THUMB_W // 2, _THUMB_H // 2,
                                      text=message, fill="#888",
                                      width=_THUMB_W - 10)

    def _render_thumbnail(self, thumbnail_svg: str):
        """Decode the base64 SVG thumbnail and draw it on the canvas."""
        self.thumb_canvas.delete("all")
        if not thumbnail_svg:
            self._set_thumbnail_placeholder("No preview")
            return
        if render_svg_to_photoimage is None:
            self._set_thumbnail_placeholder("Preview unavailable\n(PIL missing)")
            return
        try:
            # Stored as a "data:image/svg+xml;base64,<...>" URI; strip the prefix.
            payload = thumbnail_svg.split(",", 1)[-1]
            svg = base64.b64decode(payload).decode("utf-8")
            photo, _zoom, _size = render_svg_to_photoimage(
                svg, fit_size=(_THUMB_W - 6, _THUMB_H - 6))
            if photo is None:
                self._set_thumbnail_placeholder("Preview unavailable")
                return
            self._thumb_image = photo  # keep reference to avoid GC
            self.thumb_canvas.create_image(_THUMB_W // 2, _THUMB_H // 2,
                                          image=photo)
        except Exception:
            logger.exception("thumbnail render failed")
            self._set_thumbnail_placeholder("Preview unavailable")

    @staticmethod
    def _fmt_metrics(metrics: dict) -> str:
        """Summarize performance_metrics cleanly, guarding missing keys.

        Numbers are formatted to 2 dp and absurd VSWR is capped at ">10".
        """
        if not isinstance(metrics, dict) or not metrics:
            return "No performance data available"

        def num(value, suffix="", cap_vswr=False):
            try:
                v = float(value)
            except (TypeError, ValueError):
                return "N/A"
            if cap_vswr and v > 10:
                return ">10"
            return f"{v:.2f}{suffix}"

        lines = []
        summary = metrics.get("summary") if isinstance(metrics.get("summary"), dict) else {}
        if summary:
            lines.append(f"  Avg VSWR: {num(summary.get('avg_vswr'), cap_vswr=True)}")
            lines.append(f"  Avg Gain: {num(summary.get('avg_gain_dbi'), ' dBi')}")
            if "bandwidth_octaves" in summary:
                lines.append(f"  Bandwidth: {num(summary.get('bandwidth_octaves'), ' oct')}")

        validation = metrics.get("validation") if isinstance(metrics.get("validation"), dict) else {}
        if validation:
            lines.append(f"  Within bounds: {validation.get('within_bounds', 'N/A')}")
            lines.append(f"  Manufacturable: {validation.get('manufacturable', 'N/A')}")
            if "complexity_score" in validation:
                lines.append(f"  Complexity: {validation.get('complexity_score')}/4")

        # Fall back to any top-level scalar metrics if the expected blocks are absent.
        if not lines:
            for k, v in metrics.items():
                if isinstance(v, (int, float, str)):
                    lines.append(f"  {k}: {v}")
            if not lines:
                return "No summary metrics available"

        return "\n".join(lines)

    def _show_details(self):
        """Populate the details pane for the currently selected design."""
        path = self._selected_path()
        if not path:
            self._set_info("Select a design to view details.")
            self._set_thumbnail_placeholder("No preview")
            return
        try:
            metadata, _geometry = self.storage.load_design(path)
        except Exception:
            logger.exception("library details load failed")
            self._set_info("Failed to load design details.")
            self._set_thumbnail_placeholder("No preview")
            return

        try:
            freqs = metadata.frequencies_mhz or ()
            freq_str = "/".join(f"{float(f):g}" for f in freqs) if freqs else "?"
        except Exception:
            freq_str = "?"

        def attr(name, default="?"):
            value = getattr(metadata, name, default)
            return default if value in (None, "") else value

        notes = getattr(metadata, "custom_notes", "") or "(none)"
        lines = [
            f"Name: {attr('name')}",
            f"Band: {attr('band_name')}",
            f"Frequencies: {freq_str} MHz",
            f"Substrate: {attr('substrate_width')}\" x {attr('substrate_height')}\"",
            f"Trace width: {attr('trace_width_mil')} mil",
            f"Type: {attr('design_type')}",
            "",
            "Performance metrics:",
            self._fmt_metrics(getattr(metadata, "performance_metrics", {}) or {}),
            "",
            "Notes:",
            f"  {notes}",
        ]
        self._set_info("\n".join(lines))
        self._render_thumbnail(getattr(metadata, "thumbnail_svg", "") or "")

    # ----- list / search --------------------------------------------------

    def _refresh(self):
        self.tree.delete(*self.tree.get_children())
        self._rows.clear()
        q = self.query.get().strip()
        try:
            designs = self.storage.search_designs(q) if q else self.storage.list_designs()
        except Exception:
            logger.exception("library list failed")
            designs = []
        for d in designs:
            freqs = d.get("frequencies_mhz") or []
            try:
                freq_str = "/".join(f"{float(f):g}" for f in freqs)
            except Exception:
                freq_str = ""
            created = (d.get("created_date") or "")[:19].replace("T", " ")
            iid = self.tree.insert("", END, values=(
                d.get("name", "?"), d.get("band_name", "?"), freq_str, created))
            self._rows[iid] = d.get("file_path")

        self.stats_var.set(f"{len(designs)} design(s)" + (f" matching '{q}'" if q else ""))
        # Reset the details pane whenever the list changes (selection is cleared).
        self._show_details()

    def _selected_path(self) -> Optional[str]:
        sel = self.tree.selection()
        return self._rows.get(sel[0]) if sel else None

    # ----- actions --------------------------------------------------------

    def _load(self):
        path = self._selected_path()
        if not path:
            return
        try:
            metadata, geometry = self.storage.load_design(path)
        except Exception as e:
            messagebox.showerror("Load failed", str(e), parent=self.win)
            return
        self.on_load(metadata, geometry)
        self.win.destroy()

    def _delete(self):
        path = self._selected_path()
        if not path:
            return
        if not messagebox.askyesno("Delete", "Delete this design?", parent=self.win):
            return
        try:
            self.storage.delete_design(path)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e), parent=self.win)
            return
        self._refresh()

    def _export(self):
        """Load the selected design's geometry and export it via VectorExporter."""
        path = self._selected_path()
        if not path:
            messagebox.showinfo("Export", "Select a design first.", parent=self.win)
            return
        try:
            metadata, geometry = self.storage.load_design(path)
        except Exception as e:
            messagebox.showerror("Export failed", str(e), parent=self.win)
            return
        if not geometry or not geometry.strip():
            messagebox.showwarning("Export", "This design has no geometry to export.",
                                   parent=self.win)
            return

        # Let the user pick the output path; the extension drives the format.
        name = getattr(metadata, "name", "") or "antenna_design"
        save_path = filedialog.asksaveasfilename(
            parent=self.win,
            title="Export Design",
            defaultextension=".svg",
            initialfile=f"{name}.svg",
            filetypes=[("SVG", "*.svg"), ("DXF", "*.dxf"), ("PDF", "*.pdf")])
        if not save_path:
            return

        save_path = Path(save_path)
        fmt = (save_path.suffix.lstrip(".") or "svg").lower()
        if fmt not in ("svg", "dxf", "pdf"):
            fmt = "svg"

        try:
            from export import VectorExporter
            # VectorExporter writes "<filename>.<fmt>" into its own output_dir, so
            # point that dir at the chosen folder and pass the stem as filename.
            exporter = VectorExporter(output_dir=str(save_path.parent))
            metadata_dict = metadata.to_dict() if hasattr(metadata, "to_dict") else {}
            out = exporter.export_geometry(geometry, save_path.stem, fmt, metadata_dict)
        except Exception as e:
            logger.exception("library export failed")
            messagebox.showerror("Export failed", str(e), parent=self.win)
            return
        messagebox.showinfo("Export", f"Exported to:\n{out}", parent=self.win)

    def _edit_notes(self):
        """Edit and persist custom notes for the selected design.

        Persistence is an in-place rewrite of the existing design JSON's
        ``metadata.custom_notes`` field (the same file shape DesignStorage
        writes). This avoids ``save_design``, which would otherwise mint a new
        timestamped file and regenerate the thumbnail rather than update in place.
        """
        path = self._selected_path()
        if not path:
            messagebox.showinfo("Edit Notes", "Select a design first.", parent=self.win)
            return
        try:
            metadata, _geometry = self.storage.load_design(path)
        except Exception as e:
            messagebox.showerror("Edit Notes", str(e), parent=self.win)
            return

        dlg = ttk.Toplevel(self.win)
        dlg.title(f"Edit Notes - {getattr(metadata, 'name', '')}")
        dlg.geometry("460x300")
        dlg.transient(self.win)
        try:
            dlg.grab_set()
        except Exception:
            pass

        ttk.Label(dlg, text="Design Notes:", padding=PAD_M).pack(side=TOP, anchor="w")
        text = ttk.Text(dlg, wrap=WORD, height=12)
        text.pack(side=TOP, fill=BOTH, expand=True, padx=PAD_M)
        text.insert(END, getattr(metadata, "custom_notes", "") or "")
        text.focus_set()

        def save():
            new_notes = text.get("1.0", END).strip()
            if self._persist_notes(path, new_notes):
                dlg.destroy()
                self._show_details()
            else:
                messagebox.showerror("Edit Notes", "Failed to save notes.", parent=dlg)

        bar = ttk.Frame(dlg, padding=PAD_M)
        bar.pack(side=BOTTOM, fill=X)
        ttk.Button(bar, text="Save", bootstyle=PRIMARY, command=save).pack(side=RIGHT)
        ttk.Button(bar, text="Cancel", bootstyle=SECONDARY,
                   command=dlg.destroy).pack(side=RIGHT, padx=(0, PAD_S))
        dlg.bind("<Escape>", lambda _e: dlg.destroy())

    @staticmethod
    def _persist_notes(path: str, notes: str) -> bool:
        """In-place update of ``metadata.custom_notes`` in the design JSON file."""
        try:
            p = Path(path)
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "metadata" not in data:
                logger.warning(f"unexpected design file shape, not updating: {p}")
                return False
            data["metadata"]["custom_notes"] = notes
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"updated notes for {p}")
            return True
        except Exception:
            logger.exception("persist notes failed")
            return False
