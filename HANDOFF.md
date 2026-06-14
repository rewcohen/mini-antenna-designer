# Handoff — Wizard-Driven CAD GUI Rewrite

Branch: `wizard-cad-gui` (pushed). Legacy `ui.py` untouched as default.
PR: https://github.com/rewcohen/mini-antenna-designer/pull/new/wizard-cad-gui

## What this is
Ground-up rewrite of the front end from a tab + dropdown layout into a
wizard-driven, paint/CAD-style workspace. Backend (`core`, `design`,
`design_generator`, `export`, `presets`, `storage`, `wizard`, `tune`) is
**unchanged** — the new UI only calls into it.

User decisions that shaped it:
- Full ground-up rewrite (new files, keep `ui.py` until parity).
- Big SVG preview canvas (reuse svglib→PIL pipeline).
- Persistent step rail (not a modal wizard).
- Visual band card gallery (no dropdown).

## How to run
```
python main.py --new          # new wizard GUI
ANTENNA_GUI=new python main.py # same, via env
python main.py                 # legacy ui.py (still the default)
python app.py                  # new GUI directly
```

## Layout
`toolbar / [step rail | active-step panel | SVG canvas | properties] / status bar`

- Toolbar: New, Open Library, Save, Wizard, Tune, Theme, Generate.
- Step rail: Band → Board → Trace → Generate → Export (clickable, ✓ state, inline help).
- Canvas: live SVG of current design, zoom/pan/fit, theme-aware.
- Properties: VSWR chips, warnings, feed/pattern, "Analysis…" button.

## File map (all under repo root)
| File | Role |
|---|---|
| `app.py` | Main window `AntennaDesignerApp`; toolbar; threaded generate; export/save; wizard/tune/library wiring; `_apply_design()` = single path adopting any design dict into session+canvas |
| `gui/session.py` | `DesignSession` — Tk-free state + observer bus (events `EVT_INPUTS/EVT_BAND/EVT_GENERATED/EVT_STEP`) |
| `gui/svg_render.py` | `geometry_to_svg()` (in-memory SVG via `VectorExporter._generate_svg_content`) + `render_svg_to_photoimage()` |
| `gui/canvas_view.py` | `CanvasView` — SVG preview, zoom/pan/fit, `apply_theme()` |
| `gui/step_rail.py` | `StepRail` — persistent left rail |
| `gui/scrollframe.py` | `ScrollFrame` — scrollable container helper |
| `gui/properties_panel.py` | `PropertiesPanel` — metrics/warnings/feed/pattern + Analysis launcher |
| `gui/steps/band_step.py` | Card gallery by category + custom freqs |
| `gui/steps/board_step.py` | Substrate size + material |
| `gui/steps/trace_step.py` | Trace width + advanced + contact pads |
| `gui/steps/generate_step.py` | Generate/Stop + progress + summary |
| `gui/steps/export_step.py` | SVG/DXF/PDF export + Save to Library |
| `gui/library_view.py` | `LibraryDialog` — list/search/load/delete |
| `gui/analysis_view.py` | `AnalysisDialog` — per-segment trace table + CSV |
| `gui/dialogs.py` | `WizardDialog`, `TuneDialog` (ported from `ui.py`) |

## Key backend calls (unchanged)
- `BandPresets.get_all_bands()` → cards; `create_custom_band(...)` for custom.
- `AntennaDesignGenerator(NEC2Interface(), substrate_width, substrate_height).generate_design(band, trace_width_inches, add_contact_pads)` — runs in a daemon thread; result marshalled back via `root.after`.
- `VectorExporter.export_geometry(geom, name, fmt, metadata)`; in-memory SVG via `_parse_geometry` + `_generate_svg_content`.
- `DesignStorage`: `save_design`, `list_designs`, `load_design`, `delete_design`, `search_designs`. Saved dir `designs/` (gitignored).
- `AntennaWizard`, `tune.evaluate_design` — drive the helper dialogs.

## Verification done (headless Tk smoke tests, all OK)
- Construct app; pick band card; threaded generate → `session.svg` set; design_type `meander_array_medium`.
- In-memory SVG generation (3844 chars, PIL available).
- Library save → list → dialog load → canvas SVG.
- Analysis dialog: 3 segments, totals match backend (4.06 in).
- Wizard: 5 options, spec built. Tune: result + bands, apply → svg.
- Theme toggle: canvas bg follows (#2f2f2f dark / #fff light).
- Fixed: properties panel crashed on non-numeric VSWR from tuned designs (now guarded).

## Remaining work (not yet ported from `ui.py`)
~~1. ASCII band-analysis charts~~ — DONE (analysis dialog "Band Analysis" tab).
~~2. Matplotlib band-comparison charts~~ — DONE (analysis dialog "Comparison Chart" tab, on-demand, guarded).
~~3. Contact-pad live info text~~ — DONE (trace step, tracks toggle + width slider).
~~4. Raw NEC geometry text view~~ — DONE (analysis dialog "NEC Geometry" tab + Copy).
~~5. Target-length preview estimate~~ — DONE (generate step shows per-band est. length + total + tight-fit hint).
~~6. feature-parity checklist + flip default + retire ui.py~~ — DONE:
   - Parity audited in `PARITY.md` (200 features); P1+P2+P3 regressions ported.
   - `main.py` now defaults to the wizard GUI; legacy is opt-in via
     `python main.py --legacy` (or `ANTENNA_GUI=legacy`). `ui.py` kept one
     cycle as the fallback — delete on confirmation.
   - Substrate material now affects resonant length (velocity factor added to
     `design.calculate_target_length`).

## Design-critique polish (commit 705d95e)
A `/impeccable critique` pass (pass 2, with live screenshots; snapshot in
`.impeccable/critique/`) drove a polish round:
- Canvas now fits-to-viewport + centers; toggleable overlay layers
  (Feed/Pattern/Grid/Details) — clean traces+feed preview by default.
- `export._generate_svg_content` gates layers via `metadata['layers']`
  (default all-on → exports/thumbnails unchanged); fixed a text y-collision.
- Light-theme contrast fixed (`secondary-outline` buttons, dark body text);
  unified selected state to PRIMARY; keyboard shortcuts + Esc on dialogs.
- VSWR formatted (`>10` cap) + "barely radiates" note; New confirms; Stop
  disabled when idle; band cards one-column (no clipping).
- `PAD_*` spacing centralized in `gui/constants.py`.

## Notes / gotchas
- `FrequencyBand` field is `.frequencies` (not `.frequencies_mhz`); `DesignMetadata` uses `frequencies_mhz` / `trace_width_mil`.
- SVG rendering deps optional (svglib/reportlab/PIL); canvas degrades to a "preview unavailable" placeholder if missing.
- Generation is ~1–3 s, synchronous in backend; UI threads it. `Stop` is a no-op (nothing to cancel mid-run).
- Line-ending warnings (LF→CRLF) on commit are expected on Windows; harmless.
