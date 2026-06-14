"""Vertically scrollable container (tk Canvas + inner ttk Frame)."""
from __future__ import annotations

from tkinter import Canvas, NW, BOTH, LEFT, RIGHT, Y, VERTICAL
import ttkbootstrap as ttk


class ScrollFrame:
    """Use ``.body`` as the parent for scrollable content."""

    def __init__(self, parent):
        self.outer = ttk.Frame(parent)
        self._canvas = Canvas(self.outer, highlightthickness=0, borderwidth=0)
        bar = ttk.Scrollbar(self.outer, orient=VERTICAL, command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=bar.set)
        bar.pack(side=RIGHT, fill=Y)
        self._canvas.pack(side=LEFT, fill=BOTH, expand=True)

        self.body = ttk.Frame(self._canvas)
        self._win = self._canvas.create_window((0, 0), window=self.body, anchor=NW)

        self.body.bind("<Configure>",
                       lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
                          lambda e: self._canvas.itemconfigure(self._win, width=e.width))
        self._canvas.bind("<MouseWheel>", self._on_wheel)

    def _on_wheel(self, e):
        self._canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
