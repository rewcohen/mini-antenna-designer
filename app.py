"""Entry point for the wizard-driven CAD-style Mini Antenna Designer GUI.

Layout:  toolbar  /  [step rail | active-step panel | SVG canvas | properties]
         /  status bar.

New front end; ``ui.py`` remains as a fallback until parity. Run with
``python app.py``.
"""
import threading
from tkinter import (BOTTOM, X, W, SUNKEN, LEFT, RIGHT, BOTH, Y, TOP, StringVar,
                     filedialog, messagebox)
import ttkbootstrap as ttk
from ttkbootstrap import Style
from ttkbootstrap.constants import PRIMARY, SECONDARY, INFO
from loguru import logger

ttk.LabelFrame = ttk.Labelframe  # ttkbootstrap leaks the tk spelling

from gui.constants import PAD_S, PAD_M, PAD_L

from core import NEC2Interface
from design_generator import AntennaDesignGenerator
from export import VectorExporter, ExportError
from storage import DesignStorage, DesignMetadata

from gui.session import DesignSession, EVT_STEP, EVT_GENERATED, EVT_INPUTS
from gui.canvas_view import CanvasView
from gui.step_rail import StepRail
from gui.properties_panel import PropertiesPanel
from gui.steps.band_step import BandStep
from gui.steps.board_step import BoardStep
from gui.steps.trace_step import TraceStep
from gui.steps.generate_step import GenerateStep
from gui.steps.export_step import ExportStep


class AntennaDesignerApp:
    """Main window: toolbar, four-region workspace, status bar."""

    LIGHT_THEME = "litera"
    DARK_THEME = "darkly"

    def __init__(self, root):
        self.root = root
        self.root.title("Mini Antenna Designer")
        self.root.geometry("1320x880")
        self.root.minsize(1024, 700)

        self.style = Style.get_instance() or Style()
        self.dark_mode = False

        # Backend (analytical; no external solver required).
        self.nec = NEC2Interface()
        self.exporter = VectorExporter()
        self.storage = DesignStorage()

        self.session = DesignSession()
        self.status_var = StringVar(value="Ready")
        self._busy = False

        self._build_toolbar()
        self._build_statusbar()
        self._build_workspace()

        self.session.subscribe(self._on_session)
        self._bind_keys()
        logger.info("Wizard GUI initialized")

    def _bind_keys(self):
        """Keyboard shortcuts for the common workflow actions."""
        r = self.root
        r.bind("<Control-g>", lambda e: self._generate())
        r.bind("<Control-Return>", lambda e: self._generate())
        r.bind("<Control-s>", lambda e: self._save_design())
        r.bind("<Control-o>", lambda e: self._open_library())
        r.bind("<Control-n>", lambda e: self._new())
        r.bind("<Control-e>", lambda e: self._export("svg"))
        for i in range(5):
            r.bind(f"<Control-Key-{i+1}>", lambda e, i=i: self.rail._select(i))

    # --- toolbar ---
    def _build_toolbar(self):
        bar = ttk.Frame(self.root, padding=(PAD_M, PAD_S))
        bar.pack(side=TOP, fill=X)
        actions = {"New": self._new, "Open Library": self._open_library,
                   "Save": self._save_design, "Wizard": self._open_wizard,
                   "Tune": self._open_tune}
        for text, cmd in actions.items():
            ttk.Button(bar, text=text, bootstyle="secondary-outline", command=cmd).pack(
                side=LEFT, padx=(0, PAD_S))
        ttk.Button(bar, text="Generate", bootstyle=PRIMARY, command=self._generate).pack(
            side=RIGHT)
        ttk.Button(bar, text="Theme", bootstyle=INFO, command=self._toggle_theme).pack(
            side=RIGHT, padx=(0, PAD_S))
        ttk.Separator(self.root).pack(side=TOP, fill=X)

    def _build_statusbar(self):
        ttk.Label(self.root, textvariable=self.status_var, relief=SUNKEN, anchor=W,
                  padding=(PAD_M, PAD_S)).pack(side=BOTTOM, fill=X)

    # --- workspace ---
    def _build_workspace(self):
        work = ttk.Frame(self.root, padding=PAD_M)
        work.pack(side=TOP, fill=BOTH, expand=True)

        rail_host = ttk.Frame(work, width=150)
        rail_host.pack(side=LEFT, fill=Y, padx=(0, PAD_M))
        rail_host.pack_propagate(False)

        self.step_host = ttk.Frame(work, width=370)
        self.step_host.pack(side=LEFT, fill=Y, padx=(0, PAD_M))
        self.step_host.pack_propagate(False)

        props_host = ttk.Frame(work, width=280)
        props_host.pack(side=RIGHT, fill=Y, padx=(PAD_M, 0))
        props_host.pack_propagate(False)

        canvas_host = ttk.Frame(work)
        canvas_host.pack(side=LEFT, fill=BOTH, expand=True)

        self.rail = StepRail(rail_host, self.session, self._show_step)
        self.rail.frame.pack(fill=BOTH, expand=True)

        self.canvas_view = CanvasView(canvas_host, self.session, self.exporter)
        self.canvas_view.frame.pack(fill=BOTH, expand=True)

        self.props = PropertiesPanel(props_host, self.session)
        self.props.frame.pack(fill=BOTH, expand=True)

        # Build all step panels once; show one at a time.
        self.steps = [
            BandStep(self.step_host, self.session),
            BoardStep(self.step_host, self.session),
            TraceStep(self.step_host, self.session),
            GenerateStep(self.step_host, self.session, self._generate, self._stop),
            ExportStep(self.step_host, self.session, self._export, self._save_design),
        ]
        self._show_step(0)

    def _show_step(self, index: int):
        for i, step in enumerate(self.steps):
            if i == index:
                step.frame.pack(fill=BOTH, expand=True)
            else:
                step.frame.pack_forget()

    # --- generation ---
    def _generate(self):
        if self._busy:
            return
        if self.session.band is None:
            messagebox.showwarning("No band", "Pick a band (or use custom frequencies) first.")
            return
        self._busy = True
        self.steps[3].set_busy(True)
        self.status_var.set("Generating…")
        threading.Thread(target=self._run_generate, daemon=True).start()

    def _run_generate(self):
        try:
            generator = AntennaDesignGenerator(
                self.nec,
                substrate_width=self.session.substrate_width,
                substrate_height=self.session.substrate_height)
            # Carry the chosen material onto the meander instance so the generator
            # reflects the user's substrate (epsilon + thickness in inches, matching
            # AdvancedMeanderTrace's own units). NOTE: the current resonance model
            # (design.calculate_target_length) sizes to free-space lambda/2 x coupling
            # factor and does not yet apply effective permittivity, so material does
            # not change trace length until a velocity-factor term is added.
            generator.advanced_meander.substrate_epsilon = self.session.substrate_epsilon
            generator.advanced_meander.substrate_thickness = self.session.substrate_thickness_mm / 25.4
            result = generator.generate_design(
                self.session.band,
                trace_width_inches=self.session.trace_width_mil / 1000.0,
                add_contact_pads=self.session.add_contact_pads)
            self.root.after(0, self._generate_done, result, None)
        except Exception as e:  # surface failure on the UI thread
            logger.exception("generation failed")
            self.root.after(0, self._generate_done, None, e)

    def _generate_done(self, result, error):
        self._busy = False
        self.steps[3].set_busy(False)
        if error is not None or not result:
            self.status_var.set("Generation failed")
            messagebox.showerror(
                "Generation failed",
                "Could not generate this design. See the log for details.")
            return
        self._apply_design(result, status=f"Generated: {result.get('design_type', 'design')}")

    def _apply_design(self, design: dict, status: str = "Design loaded"):
        """Adopt a design dict (from generate/wizard/tune) into the session + canvas."""
        self.session.results = design
        self.session.geometry = design.get("geometry")
        self.session.svg_metadata = self._svg_metadata(design)  # canvas builds the SVG
        self.status_var.set(status)
        self.session.notify(EVT_GENERATED)

    def _svg_metadata(self, design: dict) -> dict:
        """Metadata so the SVG/export marks feed pads, labels and the pattern overlay."""
        return {
            "band_name": design.get("band_name"),
            "frequencies": self.session.frequencies_mhz(),
            "design_type": design.get("design_type"),
            "connection_points": design.get("connection_points", []),
            "feed_advice": design.get("feed_advice", []),
            "radiation_pattern": design.get("radiation_pattern"),
        }

    def _stop(self):
        # Generation is short (~1-3s); nothing to cancel mid-flight yet.
        self.status_var.set("Stop requested (generation runs to completion)")

    # --- export / save ---
    def _export(self, fmt: str):
        if not self.session.has_design:
            messagebox.showwarning("Nothing to export", "Generate a design first.")
            return
        name = self.steps[4].filename.get() or "antenna_design"
        try:
            path = self.exporter.export_geometry(
                self.session.geometry, name, fmt,
                self._svg_metadata(self.session.results or {}))
            self.status_var.set(f"Exported {fmt.upper()} → {path}")
            messagebox.showinfo("Exported", f"Saved {fmt.upper()}:\n{path}")
        except ExportError:
            logger.exception("export failed")
            messagebox.showerror(
                "Export failed", "Could not export this design. See the log for details.")

    def _save_design(self):
        if not self.session.has_design:
            messagebox.showwarning("Nothing to save", "Generate a design first.")
            return
        freqs = self.session.frequencies_mhz() or (0, 0, 0)
        band_name = self.session.band.name if self.session.band else "Custom"
        meta = DesignMetadata(
            name=band_name,
            band_name=band_name,
            frequencies_mhz=tuple(freqs),
            substrate_width=self.session.substrate_width,
            substrate_height=self.session.substrate_height,
            trace_width_mil=self.session.trace_width_mil,
            design_type=(self.session.results or {}).get("design_type", ""))
        try:
            self.storage.save_design(self.session.geometry, meta, self.session.results)
            self.status_var.set("Design saved to library")
            messagebox.showinfo("Saved", "Design saved to your library.")
        except Exception:
            logger.exception("save failed")
            messagebox.showerror(
                "Save failed", "Could not save this design. See the log for details.")

    # --- toolbar stubs (filled in later phases) ---
    def _new(self):
        if self.session.has_design and not messagebox.askyesno(
                "New design", "Discard the current design and start over?"):
            return
        self.session.results = None
        self.session.geometry = None
        self.session.svg_metadata = None
        self.status_var.set("New design")
        self.session.notify(EVT_GENERATED)

    def _open_library(self):
        from gui.library_view import LibraryDialog
        LibraryDialog(self.root, self.storage, self._load_from_library)

    def _load_from_library(self, metadata, geometry):
        """Bring a saved design into the session and render it on the canvas."""
        self.session.geometry = geometry
        self.session.results = {"design_type": getattr(metadata, "design_type", ""),
                                "metrics": getattr(metadata, "performance_metrics", {}) or {},
                                "validation": {}, "success": True}
        meta = {"band_name": getattr(metadata, "band_name", ""),
                "frequencies": getattr(metadata, "frequencies_mhz", None)}
        self.session.svg_metadata = meta  # canvas builds the SVG
        self.status_var.set(f"Loaded '{getattr(metadata, 'name', 'design')}' from library")
        self.session.notify(EVT_GENERATED)

    def _open_wizard(self):
        from gui.dialogs import WizardDialog
        WizardDialog(self.root, self.session,
                     lambda d: self._apply_design(d, "Loaded from wizard"))

    def _open_tune(self):
        from gui.dialogs import TuneDialog
        TuneDialog(self.root, self.session,
                   lambda d: self._apply_design(d, "Applied tuned design"))

    def _on_session(self, event: str):
        if event == EVT_INPUTS:
            f = self.session.frequencies_mhz()
            if f:
                self.status_var.set(
                    f"{f[0]:g}/{f[1]:g}/{f[2]:g} MHz | "
                    f"{self.session.substrate_width:g}×{self.session.substrate_height:g} in | "
                    f"{self.session.trace_width_mil:.0f} mil")

    def _toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.style.theme_use(self.DARK_THEME if self.dark_mode else self.LIGHT_THEME)
        try:
            self.canvas_view.apply_theme(self.style.colors.inputbg)
        except Exception:
            logger.exception("canvas theme refresh failed")


def main():
    root = ttk.Window(themename=AntennaDesignerApp.LIGHT_THEME)
    AntennaDesignerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
