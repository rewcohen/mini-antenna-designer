"""Step 1: visual band gallery (replaces the dropdown) + custom frequencies."""
from __future__ import annotations

from tkinter import X, TOP, LEFT, BOTH, StringVar
import ttkbootstrap as ttk
from ttkbootstrap.constants import PRIMARY, DANGER

from presets import BandPresets, BandType
from gui.session import DesignSession, EVT_BAND, EVT_INPUTS
from gui.scrollframe import ScrollFrame
from gui.band_analysis_view import BandAnalysisDialog

from gui.constants import PAD_S, PAD_M

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
                      font=("", 10, "bold")).pack(
                anchor="w", pady=(PAD_M, PAD_S))
            grid = ttk.Frame(body)
            grid.pack(fill=X)
            grid.columnconfigure(0, weight=1)
            for idx, (key, band) in enumerate(items):
                f1, f2, f3 = band.frequencies
                text = f"{band.name}\n{f1:g}/{f2:g}/{f3:g} MHz"
                b = ttk.Button(grid, text=text, bootstyle="secondary-outline",
                               command=lambda k=key: self._pick(k))
                b.grid(row=idx, column=0, sticky="ew", padx=PAD_S, pady=PAD_S)
                self._cards[key] = b

        session.subscribe(self._refresh)

        # Preselect a sensible default so the app never starts with no band.
        if self.session.band is None:
            default_key = self._default_band_key()
            if default_key is not None:
                self._pick(default_key)

    def _default_band_key(self):
        """Pick a sensible default band key.

        Prefer a WiFi/2.4 GHz band (key/name containing 'wifi' and '2.4'/'2_4'),
        else the first WIFI_ISM band, else the first band overall.
        """
        for key, band in self.bands.items():
            hay = f"{key} {band.name}".lower()
            if "wifi" in hay and ("2.4" in hay or "2_4" in hay):
                return key
        for key, band in self.bands.items():
            if band.band_type == BandType.WIFI_ISM:
                return key
        return next(iter(self.bands), None)

    def _build_custom_row(self, body):
        box = ttk.LabelFrame(body, text="Custom Frequencies (MHz)", padding=PAD_M)
        box.pack(fill=X)
        self._f = [StringVar(value=v) for v in ("2400", "5500", "5800")]
        for i, var in enumerate(self._f):
            ttk.Entry(box, textvariable=var, width=7).grid(row=0, column=i, padx=PAD_S)
        ttk.Button(box, text="Use Custom", bootstyle=PRIMARY,
                   command=self._use_custom).grid(
            row=1, column=0, columnspan=3, sticky="ew", pady=(PAD_S, 0))
        ttk.Button(box, text="Analyze Band", bootstyle="info-outline",
                   command=self._analyze_band).grid(
            row=2, column=0, columnspan=3, sticky="ew", pady=(PAD_S, 0))
        self._custom_status = StringVar(value="")
        ttk.Label(box, textvariable=self._custom_status, bootstyle=DANGER).grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(PAD_S, 0))

    def _pick(self, key: str):
        band = self.bands[key]
        self.session.band_key = key
        self.session.band = band
        self.session.custom_freqs = None
        # Mirror the band's frequencies into the custom entries (display only;
        # the band remains the source of truth, custom_freqs stays None).
        for var, freq in zip(self._f, band.frequencies):
            var.set(f"{freq:g}")
        self.session.notify(EVT_BAND)
        self.session.notify(EVT_INPUTS)

    def _use_custom(self):
        try:
            freqs = tuple(float(v.get()) for v in self._f)
        except ValueError:
            self._custom_status.set("Enter three frequencies in MHz.")
            return
        self._custom_status.set("")
        self.session.custom_freqs = freqs
        self.session.band_key = None
        self.session.band = BandPresets.create_custom_band(
            "Custom", freqs[0], freqs[1], freqs[2], "User-defined frequencies")
        self.session.notify(EVT_BAND)
        self.session.notify(EVT_INPUTS)

    def _analyze_band(self):
        """Open a pre-generation feasibility dialog for the selected band."""
        if self.session.band is None:
            self._custom_status.set("Select a band (or use custom) to analyze.")
            return
        self._custom_status.set("")
        BandAnalysisDialog(self.frame, self.session.band,
                           self.session.substrate_width,
                           self.session.substrate_height)

    def _refresh(self, event: str):
        if event != EVT_BAND:
            return
        sel = self.session.band_key
        for key, b in self._cards.items():
            b.configure(bootstyle=PRIMARY if key == sel else "secondary-outline")
