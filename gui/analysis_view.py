"""Detailed analysis dialog: per-segment trace table + summary, CSV export.

Parses the NEC2 ``GW`` cards (``GW tag segs x1 y1 z1 x2 y2 z2 radius`` in inches)
the same way the exporter does, so the table matches what gets etched.
"""
from __future__ import annotations

import csv
import math
from tkinter import BOTH, X, Y, LEFT, RIGHT, TOP, BOTTOM, END, StringVar, filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import SECONDARY, PRIMARY

from gui.constants import PAD_S, PAD_M
_MM = 25.4  # inches -> mm


def parse_segments(geometry: str):
    """Yield (x1, y1, x2, y2, length_in) for each GW card."""
    segs = []
    for line in (geometry or "").splitlines():
        parts = line.split()
        if len(parts) >= 9 and parts[0].upper() == "GW":
            try:
                x1, y1, _z1, x2, y2 = (float(parts[3]), float(parts[4]),
                                       float(parts[5]), float(parts[6]), float(parts[7]))
            except ValueError:
                continue
            length = math.hypot(x2 - x1, y2 - y1)
            segs.append((x1, y1, x2, y2, length))
    return segs


class AnalysisDialog:
    def __init__(self, parent, session):
        self.segments = parse_segments(session.geometry)
        self.win = ttk.Toplevel(parent)
        self.win.title("Trace Analysis")
        self.win.geometry("760x480")
        self.win.transient(parent)

        self.summary = StringVar()
        ttk.Label(self.win, textvariable=self.summary, padding=PAD_M).pack(side=TOP, fill=X)

        body = ttk.Frame(self.win, padding=(PAD_M, 0))
        body.pack(side=TOP, fill=BOTH, expand=True)
        cols = ("#", "x1", "y1", "x2", "y2", "len_mm", "len_in", "cum_mm")
        self.tree = ttk.Treeview(body, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=88, anchor="e")
        vbar = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vbar.set)
        vbar.pack(side=RIGHT, fill=Y)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)

        btns = ttk.Frame(self.win, padding=PAD_M)
        btns.pack(side=BOTTOM, fill=X)
        ttk.Button(btns, text="Export CSV", bootstyle=PRIMARY,
                   command=self._export_csv).pack(side=LEFT)
        ttk.Button(btns, text="Close", bootstyle=SECONDARY,
                   command=self.win.destroy).pack(side=RIGHT)

        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.focus_set()
        self._populate()

    def _populate(self):
        cum_mm = 0.0
        total_in = 0.0
        longest = 0.0
        for i, (x1, y1, x2, y2, ln) in enumerate(self.segments, 1):
            cum_mm += ln * _MM
            total_in += ln
            longest = max(longest, ln)
            self.tree.insert("", END, values=(
                i, f"{x1:.3f}", f"{y1:.3f}", f"{x2:.3f}", f"{y2:.3f}",
                f"{ln * _MM:.2f}", f"{ln:.3f}", f"{cum_mm:.2f}"))
        n = len(self.segments)
        avg = (total_in / n) if n else 0.0
        self.summary.set(f"Segments: {n}   Total: {total_in * _MM:.1f} mm "
                         f"({total_in:.2f} in)   Avg: {avg * _MM:.2f} mm   "
                         f"Longest: {longest * _MM:.2f} mm")

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            parent=self.win, defaultextension=".csv",
            filetypes=[("CSV", "*.csv")], initialfile="trace_segments.csv")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["#", "x1_in", "y1_in", "x2_in", "y2_in", "len_mm", "len_in"])
                for i, (x1, y1, x2, y2, ln) in enumerate(self.segments, 1):
                    w.writerow([i, x1, y1, x2, y2, round(ln * _MM, 3), round(ln, 4)])
            messagebox.showinfo("Exported", f"Saved CSV:\n{path}", parent=self.win)
        except Exception as e:
            messagebox.showerror("Export failed", str(e), parent=self.win)
