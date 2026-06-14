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

PAD_S, PAD_M, PAD_L = 4, 8, 12

from core import NEC2Interface
from design_generator import AntennaDesignGenerator
from export import VectorExporter, ExportError
from storage import DesignStorage, DesignMetadata

from gui.session import DesignSession, EVT_STEP, EVT_GENERATED, EVT_INPUTS
from gui.canvas_view import CanvasView
from gui.step_rail import StepRail
from gui.properties_panel import PropertiesPanel
from gui.svg_render import geometry_to_svg
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
        logger.info("Wizard GUI initialized")

    # --- toolbar ---
    def _build_toolbar(self):
        bar = ttk.Frame(self.root, padding=(PAD_M, PAD_S))
        bar.pack(side=TOP, fill=X)
        actions = {"New": self._new, "Open Library": self._open_library,
                   "Save": self._save_design, "Wizard": self._stub, "Tune": self._stub}
        for text, cmd in actions.items():
            ttk.Button(bar, text=text, bootstyle=SECONDARY, command=cmd).pack(
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

        self.canvas_view = CanvasView(canvas_host, self.session)
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
            messagebox.showerror("Generation failed", str(error) if error else "Unknown error")
            return
        self.session.results = result
        self.session.geometry = result.get("geometry")
        meta = {"band_name": result.get("band_name"),
                "frequencies": self.session.frequencies_mhz()}
        self.session.svg = geometry_to_svg(self.exporter, self.session.geometry, meta)
        self.status_var.set(f"Generated: {result.get('design_type', 'design')}")
        self.session.notify(EVT_GENERATED)

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
                {"band_name": self.session.band.name if self.session.band else ""})
            self.status_var.set(f"Exported {fmt.upper()} → {path}")
            messagebox.showinfo("Exported", f"Saved {fmt.upper()}:\n{path}")
        except ExportError as e:
            messagebox.showerror("Export failed", str(e))

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
        except Exception as e:
            logger.exception("save failed")
            messagebox.showerror("Save failed", str(e))

    # --- toolbar stubs (filled in later phases) ---
    def _new(self):
        self.session.results = None
        self.session.geometry = None
        self.session.svg = None
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
        self.session.svg = geometry_to_svg(self.exporter, geometry, meta)
        self.status_var.set(f"Loaded '{getattr(metadata, 'name', 'design')}' from library")
        self.session.notify(EVT_GENERATED)

    def _stub(self):
        messagebox.showinfo("Coming soon", "This tool is not wired up yet.")

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


def main():
    root = ttk.Window(themename=AntennaDesignerApp.LIGHT_THEME)
    AntennaDesignerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
