"""Shared application state for the wizard GUI.

``DesignSession`` is a plain (Tk-free) data holder plus a tiny observer bus.
Step panels write into it and call :meth:`notify`; the canvas, properties panel
and step rail subscribe and refresh themselves. Keeping it free of Tk widgets
means the data flow is easy to test and reason about.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple


# Event names broadcast through the session bus.
EVT_INPUTS = "inputs"          # any design input changed (band/board/trace/advanced)
EVT_BAND = "band"              # band selection changed
EVT_GENERATED = "generated"    # a new design was generated (results/geometry/svg set)
EVT_STEP = "step"              # active wizard step changed


class DesignSession:
    """Single source of truth for the current design and wizard position."""

    def __init__(self):
        # --- Design inputs ---
        self.band_key: Optional[str] = None
        self.band = None  # presets.FrequencyBand
        self.custom_freqs: Optional[Tuple[float, float, float]] = None

        self.substrate_width: float = 4.0   # inches
        self.substrate_height: float = 2.0  # inches

        self.trace_width_mil: float = 10.0
        self.coupling_factor: float = 0.90
        self.bend_radius_mm: float = 1.0
        self.substrate_epsilon: float = 4.3
        self.substrate_thickness_mm: float = 1.6
        self.meander_density: float = 1.0
        self.add_contact_pads: bool = False

        # --- Generated outputs ---
        self.results: Optional[Dict] = None
        self.geometry: Optional[str] = None   # NEC2 string
        self.svg: Optional[str] = None        # in-memory SVG of current design
        self.svg_metadata: Optional[Dict] = None  # base SVG metadata; canvas rebuilds layered previews

        # --- Wizard position ---
        self.active_step: int = 0

        self._subs: List[Callable[[str], None]] = []

    # --- observer bus ---
    def subscribe(self, callback: Callable[[str], None]) -> None:
        """Register ``callback(event_name)`` to run on every :meth:`notify`."""
        self._subs.append(callback)

    def notify(self, event: str) -> None:
        """Broadcast ``event`` to all subscribers (exceptions are isolated)."""
        for cb in list(self._subs):
            try:
                cb(event)
            except Exception:  # a broken listener must not break the others
                import loguru
                loguru.logger.exception(f"session listener failed on '{event}'")

    # --- convenience ---
    @property
    def has_design(self) -> bool:
        return bool(self.geometry)

    def frequencies_mhz(self) -> Optional[Tuple[float, float, float]]:
        """Active frequencies: custom override if set, else the chosen band's."""
        if self.custom_freqs:
            return self.custom_freqs
        if self.band is not None:
            return tuple(self.band.frequencies)
        return None
