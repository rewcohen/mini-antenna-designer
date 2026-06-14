"""Library browser: list, search, load and delete saved designs (modal dialog).

Loading a design pushes its geometry into the session and renders it on the main
canvas, so the dialog stays lightweight (no embedded preview of its own).
"""
from __future__ import annotations

from typing import Callable, Optional
from tkinter import StringVar, BOTH, X, Y, LEFT, RIGHT, TOP, BOTTOM, END, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import PRIMARY, SECONDARY, DANGER
from loguru import logger

PAD_S, PAD_M = 4, 8


class LibraryDialog:
    """Modal browser over ``DesignStorage``. Calls ``on_load(metadata, geometry)``."""

    def __init__(self, parent, storage, on_load: Callable):
        self.storage = storage
        self.on_load = on_load
        self._rows = {}  # tree iid -> file_path

        self.win = ttk.Toplevel(parent)
        self.win.title("Design Library")
        self.win.geometry("720x460")
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

        body = ttk.Frame(self.win, padding=(PAD_M, 0))
        body.pack(side=TOP, fill=BOTH, expand=True)
        cols = ("name", "band", "freqs", "created")
        self.tree = ttk.Treeview(body, columns=cols, show="headings", selectmode="browse")
        for c, w in zip(cols, (200, 160, 160, 150)):
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=w)
        vbar = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vbar.set)
        vbar.pack(side=RIGHT, fill=Y)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        self.tree.bind("<Double-1>", lambda _e: self._load())

        btns = ttk.Frame(self.win, padding=PAD_M)
        btns.pack(side=BOTTOM, fill=X)
        ttk.Button(btns, text="Load", bootstyle=PRIMARY, command=self._load).pack(
            side=LEFT, padx=(0, PAD_S))
        ttk.Button(btns, text="Delete", bootstyle=DANGER, command=self._delete).pack(
            side=LEFT)
        ttk.Button(btns, text="Close", bootstyle=SECONDARY,
                   command=self.win.destroy).pack(side=RIGHT)

        self._refresh()

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
            freq_str = "/".join(f"{f:g}" for f in freqs)
            created = (d.get("created_date") or "")[:19].replace("T", " ")
            iid = self.tree.insert("", END, values=(
                d.get("name", "?"), d.get("band_name", "?"), freq_str, created))
            self._rows[iid] = d.get("file_path")

    def _selected_path(self) -> Optional[str]:
        sel = self.tree.selection()
        return self._rows.get(sel[0]) if sel else None

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
