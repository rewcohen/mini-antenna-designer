"""Detailed analysis dialog: tabbed view (segments, NEC geometry, band analysis, chart).

Parses the NEC2 ``GW`` cards (``GW tag segs x1 y1 z1 x2 y2 z2 radius`` in inches)
the same way the exporter does, so the table matches what gets etched.

The "Band Analysis" tab ports the legacy ASCII visualisation from ``ui.py``
(``_create_ascii_charts``, ``_vswr_bar``, ``_get_resonance_type``) as
module-level functions. The "Comparison Chart" tab renders the matplotlib
band chart from ``band_chart.BandAnalysisChart`` (guarded for missing deps).
"""
from __future__ import annotations

import csv
import math
import os
import tempfile
from tkinter import BOTH, X, Y, LEFT, RIGHT, TOP, BOTTOM, END, StringVar, Canvas, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
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


def vswr_bar(vswr):
    """Create a visual VSWR indicator bar. (Ported from ui.py ``_vswr_bar``.)"""
    if vswr < 1.5:
        return "[████████████████] Excellent"
    elif vswr < 2.0:
        return "[████████████    ] Very Good"
    elif vswr < 2.5:
        return "[████████        ] Good     "
    elif vswr < 3.0:
        return "[████            ] Fair     "
    else:
        return "[█               ] Poor     "


def resonance_type(ratio):
    """Get resonance type based on trace/wavelength ratio. (Ported from ui.py ``_get_resonance_type``.)"""
    if 0.23 <= ratio <= 0.27:
        return "Quarter-wave (λ/4)"
    elif 0.48 <= ratio <= 0.52:
        return "Half-wave (λ/2)"
    elif 0.73 <= ratio <= 0.77:
        return "Three-quarter (3λ/4)"
    elif 0.98 <= ratio <= 1.02:
        return "Full-wave (λ)"
    else:
        return "Non-resonant"


def ascii_charts(freq1, freq2, freq3, vswr1, vswr2, vswr3, total_length, segment_count):
    """Create ASCII charts for band analysis. (Ported from ui.py ``_create_ascii_charts``.)"""
    # Header
    output = "╔═══════════════════════════════════════════════════════════════════════════╗\n"
    output += "║                    BAND ANALYSIS - ASCII VISUALIZATION                     ║\n"
    output += "╚═══════════════════════════════════════════════════════════════════════════╝\n\n"

    # Frequency and VSWR table
    output += "┌─────────────────────────────────────────────────────────────────────────┐\n"
    output += "│ FREQUENCY BANDS & VSWR ANALYSIS                                          │\n"
    output += "├─────────────────────────────────────────────────────────────────────────┤\n"
    output += f"│ Band 1: {freq1:8.2f} MHz  →  VSWR: {vswr1:5.2f}  "
    output += vswr_bar(vswr1) + " │\n"
    if freq2 > 0:
        output += f"│ Band 2: {freq2:8.2f} MHz  →  VSWR: {vswr2:5.2f}  "
        output += vswr_bar(vswr2) + " │\n"
    if freq3 > 0:
        output += f"│ Band 3: {freq3:8.2f} MHz  →  VSWR: {vswr3:5.2f}  "
        output += vswr_bar(vswr3) + " │\n"
    output += "└─────────────────────────────────────────────────────────────────────────┘\n\n"

    # VSWR bar chart with corrected scaling
    output += "VSWR Performance (Target: < 2.0 = Excellent, < 3.0 = Good)\n"
    output += "────────────────────────────────────────────────────────────────────────────\n"

    # Get valid VSWR values (exclude 0 or invalid values)
    valid_vswrs = []
    if vswr1 > 0:
        valid_vswrs.append(('Band 1', freq1, vswr1))
    if freq2 > 0 and vswr2 > 0:
        valid_vswrs.append(('Band 2', freq2, vswr2))
    if freq3 > 0 and vswr3 > 0:
        valid_vswrs.append(('Band 3', freq3, vswr3))

    if valid_vswrs:
        # Use maximum VSWR for scaling, but cap at 5.0 for reasonable display
        max_vswr = max(v[2] for v in valid_vswrs)
        max_display_vswr = min(max_vswr, 5.0)  # Cap at 5.0 for better scaling

        # Scale to 50 chars max, with 5.0 as the reference point
        scale = 50 / max_display_vswr

        for band_name, freq, vswr in valid_vswrs:
            bar_length = int(vswr * scale)
            bar = "█" * min(bar_length, 50)  # Cap at 50 chars
            output += f"{band_name} ({freq:.1f}MHz): {bar:<50} {vswr:.2f}\n"

    output += "────────────────────────────────────────────────────────────────────────────\n"
    output += "Reference: | 1.0   | 1.5   | 2.0   | 2.5   | 3.0   | 4.0   | 5.0   |\n"
    output += "           └───────┴───────┴───────┴───────┴───────┴───────┴───────┘\n\n"

    # Trace length information
    output += "┌─────────────────────────────────────────────────────────────────────────┐\n"
    output += "│ TRACE LENGTH ANALYSIS                                                    │\n"
    output += "├─────────────────────────────────────────────────────────────────────────┤\n"
    output += f"│ Total Trace Length:    {total_length:8.2f} mm  ({total_length/25.4:6.3f} in)       │\n"
    output += f"│ Number of Segments:    {segment_count:8d}                                 │\n"
    if segment_count > 0:
        avg_length = total_length / segment_count
        output += f"│ Average Segment:       {avg_length:8.2f} mm  ({avg_length/25.4:6.3f} in)       │\n"
    output += "└─────────────────────────────────────────────────────────────────────────┘\n\n"

    # Wavelength comparison with corrected units
    if freq1 > 0:
        # Calculate wavelength in meters, then convert to mm
        wavelength1 = 299.792458 / freq1  # meters
        wavelength1_mm = wavelength1 * 1000  # convert to mm  # convert to mm
        ratio1 = total_length / wavelength1_mm

        output += "┌─────────────────────────────────────────────────────────────────────────┐\n"
        output += "│ WAVELENGTH COMPARISON                                                    │\n"
        output += "├─────────────────────────────────────────────────────────────────────────┤\n"
        output += f"│ Band 1 ({freq1:.1f} MHz):                                                  │\n"
        output += f"│   Wavelength (λ):       {wavelength1_mm:8.2f} mm                          │\n"
        output += f"│   Trace / Wavelength:   {ratio1:8.3f} λ                                │\n"
        output += f"│   Resonance:            {resonance_type(ratio1):25s}            │\n"

        if freq2 > 0:
            wavelength2 = 299.792458 / freq2  # meters
            wavelength2_mm = wavelength2 * 1000  # convert to mm
            ratio2 = total_length / wavelength2_mm
            output += f"│ Band 2 ({freq2:.1f} MHz):                                                  │\n"
            output += f"│   Wavelength (λ):       {wavelength2_mm:8.2f} mm                          │\n"
            output += f"│   Trace / Wavelength:   {ratio2:8.3f} λ                                │\n"
            output += f"│   Resonance:            {resonance_type(ratio2):25s}            │\n"

        if freq3 > 0:
            wavelength3 = 299.792458 / freq3  # meters
            wavelength3_mm = wavelength3 * 1000  # convert to mm
            ratio3 = total_length / wavelength3_mm
            output += f"│ Band 3 ({freq3:.1f} MHz):                                                  │\n"
            output += f"│   Wavelength (λ):       {wavelength3_mm:8.2f} mm                          │\n"
            output += f"│   Trace / Wavelength:   {ratio3:8.3f} λ                                │\n"
            output += f"│   Resonance:            {resonance_type(ratio3):25s}            │\n"

        output += "└─────────────────────────────────────────────────────────────────────────┘\n\n"

    # Performance summary with corrected thresholds
    output += "PERFORMANCE SUMMARY\n"
    output += "────────────────────────────────────────────────────────────────────────────\n"

    # Count bands with valid VSWR values
    excellent = sum(1 for v in [vswr1, vswr2, vswr3] if 0 < v < 2.0)
    good = sum(1 for v in [vswr1, vswr2, vswr3] if 2.0 <= v < 3.0)
    poor = sum(1 for v in [vswr1, vswr2, vswr3] if v >= 3.0 or v <= 0)

    # Only count bands that actually have valid data
    valid_bands = sum(1 for v in [vswr1, vswr2, vswr3] if v > 0)
    total_bands = max(valid_bands, 1)  # Avoid division by zero

    output += f"  Excellent (VSWR < 2.0): {excellent} band(s)\n"
    output += f"  Good (2.0 ≤ VSWR < 3.0): {good} band(s)\n"
    output += f"  Poor (VSWR ≥ 3.0):       {poor} band(s)\n"
    output += f"  Total Valid Bands:       {total_bands}\n\n"

    # Performance rating based on percentage of bands meeting targets
    if valid_bands > 0:
        excellent_percentage = (excellent / total_bands) * 100
        good_percentage = (good / total_bands) * 100

        if excellent_percentage >= 66.7:  # 2/3 or more bands excellent
            output += "  ✓ Overall Rating: EXCELLENT - Design meets performance targets\n"
        elif excellent_percentage >= 33.3:  # 1/3 or more bands excellent
            output += "  ✓ Overall Rating: GOOD - Design is functional with acceptable VSWR\n"
        elif good_percentage >= 66.7:  # 2/3 or more bands good
            output += "  ✓ Overall Rating: ACCEPTABLE - Design functional but needs optimization\n"
        else:
            output += "  ⚠ Overall Rating: NEEDS IMPROVEMENT - Consider redesign or optimization\n"
    else:
        output += "  ⚠ Overall Rating: NO VALID DATA - Generate design to see performance metrics\n"

    return output


class AnalysisDialog:
    def __init__(self, parent, session):
        self.session = session
        self.geometry_str = session.geometry or ""
        self.segments = parse_segments(self.geometry_str)
        self._chart_photo = None  # keep a reference so PhotoImage isn't GC'd

        self.win = ttk.Toplevel(parent)
        self.win.title("Trace Analysis")
        self.win.geometry("820x560")
        self.win.transient(parent)

        nb = ttk.Notebook(self.win, padding=PAD_S)
        nb.pack(side=TOP, fill=BOTH, expand=True)

        self._build_segments_tab(nb)
        self._build_geometry_tab(nb)
        self._build_band_tab(nb)
        self._build_chart_tab(nb)

        btns = ttk.Frame(self.win, padding=PAD_M)
        btns.pack(side=BOTTOM, fill=X)
        ttk.Button(btns, text="Close", bootstyle=SECONDARY,
                   command=self.win.destroy).pack(side=RIGHT)

        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.focus_set()
        self._populate()

    # ----- TAB 1: Segments -------------------------------------------------
    def _build_segments_tab(self, nb):
        tab = ttk.Frame(nb, padding=PAD_S)
        nb.add(tab, text="Segments")

        self.summary = StringVar()
        ttk.Label(tab, textvariable=self.summary, padding=PAD_M).pack(side=TOP, fill=X)

        body = ttk.Frame(tab, padding=(PAD_M, 0))
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

        sbtns = ttk.Frame(tab, padding=(PAD_M, PAD_S))
        sbtns.pack(side=BOTTOM, fill=X)
        ttk.Button(sbtns, text="Export CSV", bootstyle=PRIMARY,
                   command=self._export_csv).pack(side=LEFT)

    # ----- TAB 2: NEC Geometry ---------------------------------------------
    def _build_geometry_tab(self, nb):
        tab = ttk.Frame(nb, padding=PAD_S)
        nb.add(tab, text="NEC Geometry")

        txt = ScrolledText(tab, font=("Consolas", 9), wrap="none")
        txt.pack(side=TOP, fill=BOTH, expand=True)
        txt.insert("1.0", self.geometry_str)
        txt.configure(state="disabled")

        gbtns = ttk.Frame(tab, padding=(0, PAD_S))
        gbtns.pack(side=BOTTOM, fill=X)
        ttk.Button(gbtns, text="Copy", bootstyle=SECONDARY,
                   command=self._copy_geometry).pack(side=LEFT)

    def _copy_geometry(self):
        try:
            self.win.clipboard_clear()
            self.win.clipboard_append(self.geometry_str)
        except Exception:
            pass

    # ----- TAB 3: Band Analysis --------------------------------------------
    def _build_band_tab(self, nb):
        tab = ttk.Frame(nb, padding=PAD_S)
        nb.add(tab, text="Band Analysis")

        txt = ScrolledText(tab, font=("Consolas", 9), wrap="none")
        txt.pack(side=TOP, fill=BOTH, expand=True)
        try:
            analysis = self._build_ascii_analysis()
        except Exception as e:
            analysis = f"Band analysis unavailable: {e}"
        txt.insert("1.0", analysis)
        txt.configure(state="disabled")

    def _band_inputs(self):
        """Assemble (freq1/2/3, vswr1/2/3, total_length_mm, segment_count) from the session."""
        freqs = self.session.frequencies_mhz() or (0, 0, 0)
        f1 = float(freqs[0]) if len(freqs) > 0 and freqs[0] else 0.0
        f2 = float(freqs[1]) if len(freqs) > 1 and freqs[1] else 0.0
        f3 = float(freqs[2]) if len(freqs) > 2 and freqs[2] else 0.0

        results = self.session.results or {}
        metrics = results.get("metrics", {}) if isinstance(results, dict) else {}

        def vswr_for(f):
            # Match numerically: metric keys carry the raw frequency repr
            # (e.g. "freq_2400.0_mhz", GPS "freq_1575.42_mhz"), so reconstructing
            # the key from int(round(f)) misses custom/float bands. Mirror the
            # properties panel: scan the dict and compare the embedded value.
            if not f or not isinstance(metrics, dict):
                return 0.0
            for key, entry in metrics.items():
                if key == "summary" or not isinstance(entry, dict):
                    continue
                num = key.replace("freq_", "").replace("_mhz", "")
                try:
                    if abs(float(num) - float(f)) <= 0.5:
                        return float(entry.get("vswr"))
                except (TypeError, ValueError):
                    continue
            return 0.0

        v1, v2, v3 = vswr_for(f1), vswr_for(f2), vswr_for(f3)

        total_length_mm = sum(ln for (_x1, _y1, _x2, _y2, ln) in self.segments) * _MM
        segment_count = len(self.segments)
        return f1, f2, f3, v1, v2, v3, total_length_mm, segment_count

    def _build_ascii_analysis(self):
        f1, f2, f3, v1, v2, v3, total_length_mm, segment_count = self._band_inputs()
        return ascii_charts(f1, f2, f3, v1, v2, v3, total_length_mm, segment_count)

    # ----- TAB 4: Comparison Chart -----------------------------------------
    def _build_chart_tab(self, nb):
        tab = ttk.Frame(nb, padding=PAD_S)
        nb.add(tab, text="Comparison Chart")

        cbtns = ttk.Frame(tab, padding=(0, PAD_S))
        cbtns.pack(side=TOP, fill=X)
        ttk.Button(cbtns, text="Generate comparison chart", bootstyle=PRIMARY,
                   command=self._generate_chart).pack(side=LEFT)

        self.chart_host = ttk.Frame(tab)
        self.chart_host.pack(side=TOP, fill=BOTH, expand=True)

    def _clear_chart_host(self):
        for child in self.chart_host.winfo_children():
            child.destroy()

    def _chart_unavailable(self, msg="Chart unavailable (matplotlib/Pillow required)"):
        self._clear_chart_host()
        ttk.Label(self.chart_host, text=msg, padding=PAD_M).pack(side=TOP, anchor="w")

    def _generate_chart(self):
        self._clear_chart_host()
        try:
            from band_chart import BandAnalysisChart
        except Exception:
            self._chart_unavailable()
            return

        try:
            from PIL import Image, ImageTk
        except Exception:
            self._chart_unavailable()
            return

        try:
            chart = BandAnalysisChart(self.session.substrate_width,
                                      self.session.substrate_height)
            path = os.path.join(tempfile.gettempdir(), "mad_band_chart.png")
            band = getattr(self.session, "band", None)
            if band is not None:
                result = chart.create_custom_comparison_chart(
                    {band.name: band}, save_path=path)
            else:
                result = chart.create_comparison_chart(save_path=path)

            if not result or not os.path.exists(path):
                self._chart_unavailable()
                return

            img = Image.open(path)
            # Downscale large (~16x10in @ 300dpi) image to a reasonable width.
            max_w = 900
            if img.width > max_w:
                scale = max_w / float(img.width)
                new_size = (max_w, int(img.height * scale))
                img = img.resize(new_size, Image.LANCZOS)

            self._chart_photo = ImageTk.PhotoImage(img)

            canvas = Canvas(self.chart_host, highlightthickness=0)
            hbar = ttk.Scrollbar(self.chart_host, orient="horizontal", command=canvas.xview)
            vbar = ttk.Scrollbar(self.chart_host, orient="vertical", command=canvas.yview)
            canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
            hbar.pack(side=BOTTOM, fill=X)
            vbar.pack(side=RIGHT, fill=Y)
            canvas.pack(side=LEFT, fill=BOTH, expand=True)
            canvas.create_image(0, 0, anchor="nw", image=self._chart_photo)
            canvas.configure(scrollregion=(0, 0, self._chart_photo.width(),
                                           self._chart_photo.height()))
        except Exception:
            self._chart_unavailable()

    # ----- shared ----------------------------------------------------------
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
