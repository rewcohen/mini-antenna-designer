"""Help-menu dialogs: About and User Guide.

Two small, self-contained modal dialogs for the Help menu. They depend on
nothing from the app beyond ``gui.constants`` (and ttkbootstrap / tkinter),
so they can be opened repeatedly without side effects. Each is a plain
``ttk.Toplevel`` with Escape-to-close, ``focus_set``, and a Close button,
matching the pattern in ``gui/analysis_view.py`` and ``gui/dialogs.py``.
"""
from __future__ import annotations

from tkinter import BOTH, X, BOTTOM, TOP, RIGHT, CENTER, WORD
from tkinter.scrolledtext import ScrolledText
import ttkbootstrap as ttk
from ttkbootstrap.constants import SECONDARY

from gui.constants import PAD_S, PAD_M


_ABOUT_PURPOSE = (
    "Design compact, manufacturable tri-band planar antennas — meandered onto "
    "small copper substrates — with EM analysis and vector export for laser "
    "etching."
)

_ABOUT_BUILT_WITH = (
    "Built with: Python, Tkinter / ttkbootstrap; SVG/DXF/PDF export via "
    "svglib/reportlab; analysis via the bundled analytical estimator."
)


_USER_GUIDE = """\
WORKFLOW

The app walks through five steps. Move between them from the step rail or
with Ctrl+1..5.

1. Band
   Pick a preset card or enter a custom frequency in MHz. "Analyze Band"
   estimates feasibility before you commit.

2. Board
   Choose the substrate size plus the material and thickness.

3. Trace
   Set the trace width, the advanced meander levers, and the contact pads.

4. Generate
   Runs the design, then review the resulting VSWR and any warnings.

5. Export
   Write out SVG / DXF / PDF, or Save to Library for later.


KEYBOARD SHORTCUTS

   Ctrl+G  or  Ctrl+Enter   Generate the design
   Ctrl+S                   Save to Library
   Ctrl+O                   Open Library
   Ctrl+N                   New
   Ctrl+E                   Export SVG
   Ctrl+1 .. Ctrl+5         Jump to a step
   Esc                      Close dialogs


READING THE NUMBERS (GLOSSARY)

   VSWR     Voltage standing-wave ratio. 1.0 is ideal; under 2 is
            excellent, under 3 is good. ">10" is shown when it is very
            high.

   Gain dBi Strength in the antenna's main direction. Higher is stronger;
            a very negative value means it barely radiates.

   mil      One thousandth of an inch (1/1000 in), used for trace width.

   epsilon_r (er)  The substrate's dielectric constant.

   balun    A feed transformer that some designs require.


TIP

The canvas is the live preview. Use Fit and +/- to frame it, and the layer
toggles (Feed / Pattern / Grid / Details) to control what is drawn.
"""


def show_about(parent):
    """Open a small, modal About dialog. Safe to call repeatedly."""
    win = ttk.Toplevel(parent)
    win.title("About")
    win.geometry("420x300")
    win.transient(parent)

    body = ttk.Frame(win, padding=PAD_M)
    body.pack(side=TOP, fill=BOTH, expand=True)

    ttk.Label(body, text="Mini Antenna Designer",
              font=("", 14, "bold"), anchor=CENTER,
              justify=CENTER).pack(side=TOP, fill=X, pady=(PAD_M, PAD_S))

    ttk.Label(body, text=_ABOUT_PURPOSE, wraplength=380,
              anchor=CENTER, justify=CENTER).pack(side=TOP, fill=X,
                                                  pady=PAD_S)

    ttk.Label(body, text=_ABOUT_BUILT_WITH, wraplength=380,
              bootstyle=SECONDARY, anchor=CENTER,
              justify=CENTER).pack(side=TOP, fill=X, pady=PAD_S)

    btns = ttk.Frame(win, padding=PAD_M)
    btns.pack(side=BOTTOM, fill=X)
    ttk.Button(btns, text="Close", bootstyle=SECONDARY,
               command=win.destroy).pack(side=RIGHT)

    win.bind("<Escape>", lambda e: win.destroy())
    win.focus_set()
    return win


def show_user_guide(parent):
    """Open a modal, scrollable, read-only User Guide. Safe to call repeatedly."""
    win = ttk.Toplevel(parent)
    win.title("User Guide")
    win.geometry("640x560")
    win.transient(parent)

    txt = ScrolledText(win, wrap=WORD, padx=PAD_M, pady=PAD_M)
    txt.pack(side=TOP, fill=BOTH, expand=True)
    txt.insert("1.0", _USER_GUIDE)
    txt.configure(state="disabled")

    btns = ttk.Frame(win, padding=PAD_M)
    btns.pack(side=BOTTOM, fill=X)
    ttk.Button(btns, text="Close", bootstyle=SECONDARY,
               command=win.destroy).pack(side=RIGHT)

    win.bind("<Escape>", lambda e: win.destroy())
    win.focus_set()
    return win
