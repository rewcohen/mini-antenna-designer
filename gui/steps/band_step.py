"""Step 1: visual band gallery (replaces the dropdown) + custom frequencies."""
from __future__ import annotations

from tkinter import X, TOP, LEFT, BOTH, StringVar
import ttkbootstrap as ttk
from ttkbootstrap.constants import PRIMARY, SECONDARY, SUCCESS

from presets import BandPresets, BandType
from gui.session import DesignSession, EVT_BAND, EVT_INPUTS
from gui.scrollframe import ScrollFrame

PAD_S, PAD_M = 4, 8

_CATEGORY_LABEL = {
    BandType.TV_BROADCAST: "TV / Broadcast",
    BandType.WIFI_ISM: "WiFi / ISM",
    BandType.CELLULAR: "Cellular",
    BandType.SATELLITE: "Satellite / GNSS",
    BandType.CUSTOM: "Custom",
}
_CATEGORY_ORDER = [BandType.TV_BROADCAST, BandType.WIFI_ISM, BandType.CELLULAR,
                   BandType.SATELLITE, BandType.CUSTOM]


class BandStep:
    """Scrollable category sections of clickable band cards + a custom-freq row."""

    def __init__(self, parent, session: DesignSession):
        self.session = session
        self.bands = BandPresets.get_all_bands()
        self._cards = {}  # band_key -> Button

        scroll = ScrollFrame(parent)
        self.frame = scroll.outer
        body = scroll.body

        self._build_custom_row(body)

        # Group bands by category.
        by_cat = {}
        for key, band in self.bands.items():
            by_cat.setdefault(band.band_type, []).append((key, band))

        for cat in _CATEGORY_ORDER:
            items = by_cat.get(cat)
            if not items:
                continue
            ttk.Label(body, text=_CATEGORY_LABEL.get(cat, cat.value),
                      bootstyle=SECONDARY, font=("", 10, "bold")).pack(
                anchor="w", pady=(PAD_M, PAD_S))
            grid = ttk.Frame(body)
            grid.pack(fill=X)
            for idx, (key, band) in enumerate(items):
                f1, f2, f3 = band.frequencies
                text = f"{band.name}\n{f1:g}/{f2:g}/{f3:g} MHz"
                b = ttk.Button(grid, text=text, bootstyle=SECONDARY, width=24,
                               command=lambda k=key: self._pick(k))
                r, c = divmod(idx, 2)
                b.grid(row=r, column=c, sticky="ew", padx=PAD_S, pady=PAD_S)
                grid.columnconfigure(c, weight=1)
                self._cards[key] = b

        session.subscribe(self._refresh)

    def _build_custom_row(self, body):
        box = ttk.LabelFrame(body, text="Custom Frequencies (MHz)", padding=PAD_M)
        box.pack(fill=X)
        self._f = [StringVar(value=v) for v in ("2400", "5500", "5800")]
        for i, var in enumerate(self._f):
            ttk.Entry(box, textvariable=var, width=8).grid(row=0, column=i, padx=PAD_S)
        ttk.Button(box, text="Use Custom", bootstyle=PRIMARY,
                   command=self._use_custom).grid(row=0, column=3, padx=(PAD_M, 0))

    def _pick(self, key: str):
        self.session.band_key = key
        self.session.band = self.bands[key]
        self.session.custom_freqs = None
        self.session.notify(EVT_BAND)
        self.session.notify(EVT_INPUTS)

    def _use_custom(self):
        try:
            freqs = tuple(float(v.get()) for v in self._f)
        except ValueError:
            return
        self.session.custom_freqs = freqs
        self.session.band_key = None
        self.session.band = BandPresets.create_custom_band(
            "Custom", freqs[0], freqs[1], freqs[2], "User-defined frequencies")
        self.session.notify(EVT_BAND)
        self.session.notify(EVT_INPUTS)

    def _refresh(self, event: str):
        if event != EVT_BAND:
            return
        sel = self.session.band_key
        for key, b in self._cards.items():
            b.configure(bootstyle=SUCCESS if key == sel else SECONDARY)
