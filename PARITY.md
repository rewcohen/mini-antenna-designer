# UI Parity Checklist — legacy `ui.py` vs new wizard GUI (`app.py` + `gui/`)

_Generated from a multi-agent audit (200 features). **74 ported ✅ · 59 partial 🟡 · 67 missing ❌**._

Status legend: ✅ ported (equivalent) · 🟡 partial (present but reduced/redesigned) · ❌ missing.

> Verdict: **do not flip `main.py`'s default to `app.py` yet** — the new GUI is not at feature parity. Many 🟡 are deliberate redesigns (step rail vs tabs, card gallery vs dropdown) and not regressions; the ❌ list is the real backlog. See the curated priority section the assistant maintains separately.

## Curated read (assistant)

Not all 🟡/❌ are regressions. Splitting the backlog:

### Intentional redesigns — NOT regressions, won't port
The wizard rewrite deliberately replaced these; counting them as "missing/partial" is an artifact of comparing against the old shape.
- Tabbed notebook → persistent **step rail**.
- Band dropdown (+ auto-widen popup) → **card gallery**.
- Bottom Previous/Next nav → clickable step rail.
- Messages log pane / in-app message log → **status bar**.
- "Calculate Preview" / substrate "Update" buttons → **live** recompute.
- Comparison-vs-detailed analysis toggle → single comparison chart.

### Genuine regressions — port before flipping the default
**P1 — expert precision & trust**
- Numeric **trace-width entry** (slider-only today; experts need exact mil).
- Numeric **substrate-thickness entry** (mm); only set via material combobox now.
- **Material preset mismatch** — restore the correct εr set incl. a high-εr option (legacy had TMM10 10.2; new set differs).
- **Default band preselection** on launch + band-pick **populates the freq entries** (today they're independent; entries stay at 2400/5500/5800).
- **Infeasible-band copper-wire fallback** recommendations (backend computes them; new GUI drops them) + richer **validation warnings/errors in the summary**.
- Pre-generation **"Analyze Band"** feasibility (score/complexity/recommended types).

**P2 — library depth**
- Design **Details** panel: performance metrics, **thumbnail**, **Edit Notes**, **Export Selected**, preview zoom/fit, library stats line.

**P3 — geometry I/O & shell robustness**
- **Save/Load `.nec`** geometry file; copy trace data / export ASCII / export chart image.
- **Global error handling**, startup config validation, graceful window-close, **View Logs**, **Help/About** (a menu bar or overflow menu — the toolbar covers the common actions).

Full per-area detail below.

## Tally by area

| Area | ✅ | 🟡 | ❌ |
|---|---:|---:|---:|
| Design inputs | 8 | 8 | 7 |
| Band selection | 4 | 4 | 7 |
| Generation & validation | 6 | 10 | 8 |
| Analysis & charts | 10 | 12 | 10 |
| Library / My Designs | 4 | 7 | 13 |
| Wizard & Tune dialogs | 30 | 4 | 0 |
| Export | 9 | 3 | 6 |
| App shell | 3 | 11 | 16 |

## Design inputs

| | Feature | New-GUI location | Notes |
|---|---|---|---|
| ❌ | Analyze Band button | - | No equivalent. BandAnalysis.analyze_band_compatibility (feasibility /10, design complexity, size constraints, recommended antenna types, warnings, optimization notes) is never called anywhere in app.py or gui/. The Anal… |
| ❌ | Trace width entry (mil) | - | There is no numeric Entry synced to the slider. The slider is the only way to set trace width, so typing an exact value (with FocusOut/Return clamp-and-revert behavior) is not possible. |
| ❌ | Substrate thickness entry (mm) | - | No editable thickness entry. session.substrate_thickness_mm is set only as a side effect of the material combobox (_on_material); the user cannot type an arbitrary thickness, and there is no FocusOut-triggered refresh. |
| ❌ | Design Preview - Segment count | - | No estimated segment-count readout anywhere in the design-input/generate flow. (Segment count appears only post-generation in the AnalysisDialog Segments tab, counted from actual GW cards — not the legacy ~50mm/segment … |
| ❌ | Design Preview - Target length | - | No discrete 'Target length' field. The target lengths are embedded in generate_step's estimate line (per-band, in inches) but there is no labeled 'Target length: -- mm' readout. |
| ❌ | Design Preview - Length error | - | No length-error field and no 'Generate for exact value' / 'Invalid frequencies' / 'Error calculating' status readout. _estimate_line just silently returns None and drops the extra line on bad/missing input (errors swall… |
| ❌ | Calculate Preview button | - | No 'Calculate Preview' button and no 'values are estimates' note. The estimate line in generate_step recomputes automatically on input changes (no manual recompute control), and there is no dedicated Design Preview pane… |
| 🟡 | Predefined band dropdown | gui/steps/band_step.py: BandStep (_build_custom_row + categ… | Reimagined as a scrollable gallery of clickable band cards grouped by BandType (TV/WiFi/Cellular/Satellite/Custom), each showing 'Name\nf1/f2/f3 MHz'. Functionally lets you pick any BandPreset, but it is not a readonly … |
| 🟡 | Band selection populates frequency fields | gui/steps/band_step.py: BandStep._pick | _pick sets session.band/band_key, clears custom_freqs, and notifies EVT_BAND/EVT_INPUTS (card highlights via _refresh). But it does NOT copy the band's frequencies into the three custom-frequency StringVars — band selec… |
| 🟡 | Substrate size Update button | gui/steps/board_step.py: BoardStep._on_size | No explicit Update button — changes apply live via var.trace_add on every keystroke. Range is enforced by silently clamping to 1.0-12.0 (max(1.0, min(12.0, ...))) rather than rejecting with an error; out-of-range values… |
| 🟡 | Trace width manufacturability status label | gui/steps/trace_step.py: TraceStep._update_trace_label + mo… | A live label shows 'X.X mil — <quality>', but quality comes from a local _trace_quality heuristic (Invalid<5 / Tight<8 / Good<=50 / Wide) — NOT ManufacturingRules.check_trace_width as legacy used. Wording differs (Tight… |
| 🟡 | Advanced Settings collapsible panel | gui/steps/trace_step.py: TraceStep (the 'Advanced' ttk.Labe… | The advanced controls (coupling, bend radius, density, contact pads) live in a plain 'Advanced' LabelFrame that is always visible. It is NOT collapsible/expandable — no ▸/▾ click-to-toggle and no collapsed-by-default be… |
| 🟡 | Substrate material / epsilon combobox | gui/steps/board_step.py: BoardStep (_MATERIALS, self.materi… | Readonly combobox present and sets session.substrate_epsilon + a matching default thickness with an info label. BUT the preset set differs from legacy: new = FR-4 (4.3,1.6mm), Rogers RO4350B (3.48,1.524), Rogers RO4003C… |
| 🟡 | Meander density slider | gui/steps/trace_step.py: TraceStep._slider('Meander density… | Scale 0.5–2.0 (default 1.0) present and stored on the session. Missing the 'Sparse <- -> Dense' hint and the qualitative live label (Very Sparse / Sparse / Normal / Dense / Very Dense) — it only shows the raw numeric va… |
| 🟡 | Design Preview - Total length | gui/steps/generate_step.py: GenerateStep._estimate_line / _… | There is no dedicated Total-length readout field. _estimate_line computes per-band target lengths and a total ('Est. target length: a / b / c in (total T in, board diag D in)') and folds it into the Generate step's summ… |
| ✅ | Custom frequency entries (Band 1/2/3, MHz) | gui/steps/band_step.py: BandStep._build_custom_row (self._f… | Three ttk.Entry fields in a 'Custom Frequencies (MHz)' LabelFrame, defaulting to 2400 / 5500 / 5800 — matches legacy defaults. |
| ✅ | Use Custom button | gui/steps/band_step.py: BandStep._use_custom | Builds a custom band via BandPresets.create_custom_band, stores session.custom_freqs, clears band_key, notifies. On non-numeric input it shows an inline DANGER label ('Enter three frequencies in MHz.') instead of a mess… |
| ✅ | Substrate width/height entries (inches) | gui/steps/board_step.py: BoardStep (self.w/self.h) | Two entries in a 'Substrate Size (inches)' LabelFrame initialized from session.substrate_width/height (default 4.0 x 2.0). Matches legacy defaults. |
| ✅ | Trace width slider (mil) | gui/steps/trace_step.py: TraceStep.trace_scale / _on_trace | ttk.Scale from 5 to 100 bound to session.trace_width_mil; dragging updates the live status label and pad-info via _on_trace. Equivalent to legacy slider behavior. |
| ✅ | Contact pads toggle | gui/steps/trace_step.py: TraceStep (self.pads Checkbutton, … | round-toggle Checkbutton 'Add contact pads for soldering', default off (session.add_contact_pads=False), wired to generation via the session. Equivalent. |
| ✅ | Contact pads info label | gui/steps/trace_step.py: TraceStep._update_pad_info | Italic-ish helper label updates live: 'Contact pads: 2× trace width (≈ N mil)' when on (computed from current trace width) and 'Contact pads: off' when off. Equivalent behavior; off-state wording differs slightly from l… |
| ✅ | Coupling factor slider | gui/steps/trace_step.py: TraceStep._slider('Coupling factor… | Scale 0.80–0.98 (default from session 0.90) with a live value label 'Coupling factor: X' and feeds the target-length calculation in generate_step._estimate_line. Label is single-line text rather than legacy's separate c… |
| ✅ | Bend radius slider (mm) | gui/steps/trace_step.py: TraceStep._slider('Bend radius (mm… | Scale 0.5–3.0 mm (default 1.0) with a live value label. Matches legacy range/default. |

## Band selection

| | Feature | New-GUI location | Notes |
|---|---|---|---|
| ❌ | Auto-widened dropdown popup | - | No combobox, so no _autosize_combo_popdown equivalent. Card labels can't clip (cards stretch full width via sticky='ew'), so the underlying clipping problem is moot, but the specific feature is absent. |
| ❌ | Default band preselection | - | BandStep starts with no band selected (session.band_key/band default to None in gui/session.py); nothing auto-selects WiFi 2.4GHz or the first band. User must click a card or use custom freqs. |
| ❌ | Selection status/log feedback | - | BandStep has no reference to the app status bar and writes no log/status on selection (no status_var, no logging in band_step.py). It only fires EVT_BAND/EVT_INPUTS. The status bar exists in app.py but is only updated o… |
| ❌ | Analyze Band button | - | No 'Analyze Band' button anywhere in the new GUI. Grep for 'Analyze Band'/analyze_band_compatibility/feasibility in gui/ finds nothing relevant. The analysis_view 'Band Analysis' tab is a different, post-generation VSWR… |
| ❌ | Band Analysis info dialog | - | No popup showing feasibility score/10, design complexity, size constraints, recommended antenna types, warnings, or optimization notes. presets.BandAnalysis.analyze_band_compatibility is never called from the gui/ packa… |
| ❌ | Band-analysis fallback content | - | N/A because the Band Analysis dialog itself is absent. No fallback medium-complexity analysis path exists. |
| ❌ | Custom-frequency status/log feedback | - | On successful custom-freq entry, _use_custom clears the inline status label but writes no 'Using custom frequencies: ...' log and no 'Custom frequencies set' status-bar message. Feedback is only the cards/properties pan… |
| 🟡 | Predefined band dropdown | gui/steps/band_step.py: BandStep.__init__ (band cards grid)… | Re-imagined, not a dropdown. All BandPresets.get_all_bands() are shown, but as a scrollable gallery of clickable Buttons grouped into category sections (TV/Broadcast, WiFi/ISM, Cellular, Satellite, Custom) rather than a… |
| 🟡 | Rich preset display labels | gui/steps/band_step.py:55-56 (card text) | Each card shows name + the three frequencies (f'{band.name}\n{f1:g}/{f2:g}/{f3:g} MHz'), but the band's description is NOT shown anywhere in the picker. Legacy showed name + freqs + description in one line. |
| 🟡 | Band selection auto-fills frequency fields | gui/steps/band_step.py:77-83 (_pick), gui/session.py: custo… | Picking a card sets session.band/band_key and clears custom_freqs, and the effective frequencies come from the band (frequencies_mhz()). But it does NOT populate the three custom-frequency StringVars; the custom entries… |
| 🟡 | Custom frequency validation | gui/steps/band_step.py:85-89 (_use_custom except ValueError) | Non-numeric input is caught (ValueError) and surfaced, but inline as a DANGER-styled label reading 'Enter three frequencies in MHz.' rather than the legacy error messagebox 'Invalid frequency values. Please enter numeri… |
| ✅ | Custom Frequencies section | gui/steps/band_step.py:64-75 (_build_custom_row) | 'Custom Frequencies (MHz)' LabelFrame with three Entry fields defaulting to 2400/5500/5800. Labels are not 'Band 1/2/3' (three unlabeled entries in a row), but the section, defaults, and three-field structure match. |
| ✅ | Use Custom button (custom band creation) | gui/steps/band_step.py:84-96 (_use_custom) | 'Use Custom' button parses the three entries, calls BandPresets.create_custom_band, sets session.custom_freqs + session.band and clears band_key (preset selection), and notifies EVT_BAND/EVT_INPUTS. Equivalent behavior. |
| ✅ | Generation band resolution (preset-or-custom) | app.py:148-168 (_generate/_run_generate), gui/session.py:70… | Both card pick and Use Custom set session.band (custom path uses create_custom_band), so generation always has a resolved band. _generate warns 'Pick a band (or use custom frequencies) first.' if session.band is None. R… |
| ✅ | Step-completion gating on band choice | gui/step_rail.py:62-72 (_is_done); app.py:151-153 (_generat… | Step rail marks step 0 (and 1/2) done when session.band is not None OR session.custom_freqs is not None, mirroring legacy has_band_selection / has_custom_freqs. Generation is additionally guarded against a None band. Eq… |

## Generation & validation

| | Feature | New-GUI location | Notes |
|---|---|---|---|
| ❌ | Messages log pane | - | No timestamped Messages ScrolledText log anywhere in the new GUI (grep for log_message/message_text/Messages returns nothing). Feedback is condensed into the status bar, result StringVar, and loguru file logging only. |
| ❌ | Auto-generate on workflow advance | - | Steps are freely clickable via the rail (step_rail.StepRail._select) and never auto-fire generation. There is no equivalent of legacy _auto_generate_design_for_workflow / _has_valid_design_settings on leaving the Design… |
| ❌ | Validation results in summary | - | The Within Substrate Bounds / Manufacturable / Complexity Score (n/4) / Estimated Etch Time fields from results.validation are not displayed anywhere in the new GUI. Only validation.warnings is consumed (properties_pane… |
| ❌ | Infeasible-band copper-wire warning | - | results['feasibility'] is never read by the new GUI; the 'NOT BUILDABLE AS A MEANDER - USE A COPPER-WIRE ANTENNA' block with reasons and hand-built alternatives is not shown anywhere (app.py _svg_metadata and properties… |
| ❌ | Geometry guard on completion | - | app._generate_done/_apply_design adopt design.get('geometry') unconditionally (app.py:183-191). There is no check that non-empty geometry exists before enabling preview/export, no warning logged, and no clearing of geom… |
| ❌ | Validate Geometry tool | - | No Tools menu and no Validate Geometry action exist; EtchingValidator is never invoked from the GUI package (grep across gui/ finds no EtchingValidator/validate_for_etching usage). There is no 'Validation Results' READY… |
| ❌ | No-geometry validation guard | - | Not applicable — since there is no Validate Geometry tool, there is no 'No geometry to validate.' guard. (Other actions like Export/Save/Analysis do guard on session.has_design with their own warnings, but not the valid… |
| ❌ | Export-time manufacturing validation | app.py _export (lines 209-223) | _export checks only session.has_design then calls exporter.export_geometry directly. No pre-export EtchingValidator re-validation: empty/no-wire designs are not specifically blocked and high-complexity/not-etching-ready… |
| 🟡 | Stop button | gui/steps/generate_step.py stop_btn; app.py AntennaDesigner… | Stop button exists and is enabled during a run. Like legacy it performs no real cancellation, but it does NOT re-enable Generate or change state itself; it only sets status 'Stop requested (generation runs to completion… |
| 🟡 | Generation progress bar | gui/steps/generate_step.py GenerateStep.bar/set_busy/_tween… | Present and arguably better: shows an honest indeterminate striped 'working' bar while the thread runs, then ease-out tweens to a full SUCCESS bar on completion (REDUCED_MOTION opt-out). Differs from legacy determinate … |
| 🟡 | Status bar generation feedback | app.py _generate ('Generating…'), _generate_done ('Generati… | Status bar shows 'Generating…' then 'Generated: {design_type}' or 'Generation failed'. Summary is design-type only; legacy's richer 'Generated {type} for {band} ({freqs}) (mil traces)' and the intermediate 'Design gener… |
| 🟡 | Frequency-source resolution for generate | app.py _generate / _run_generate (uses self.session.band); … | Generation always uses session.band. Custom frequencies are supported but resolved earlier: band_step._use_custom validates the three fields and wraps them into a custom BandPresets band stored in session.band. So there… |
| 🟡 | No-input generation error | app.py _generate (lines 151-153) | Shows a warning dialog 'No band / Pick a band (or use custom frequencies) first.' when session.band is None. Message wording/path differs from legacy ('Please select a frequency band...or enter valid custom frequencies'… |
| 🟡 | Generation failure handling | app.py _run_generate except / _generate_done (lines 170-182) | Thread exceptions and empty results surface an error dialog ('Generation failed') and log via loguru.exception, aborting display. Generic message (no exception text shown to user) and there is no special handling of a r… |
| 🟡 | Design results summary text | gui/properties_panel.py PropertiesPanel._refresh (lines 69-… | A compact properties panel renders design type, avg VSWR, avg gain, per-band VSWR chips, warnings, plus feed/balun + radiation-pattern lines. Missing vs legacy's formatted block: band/frequencies header, per-frequency V… |
| 🟡 | Status indicator chips | gui/properties_panel.py _refresh chips + _vswr_level (lines… | Per-band VSWR chips are rendered and colored SUCCESS/WARNING/DANGER (good/warn/bad) by threshold. Missing the legacy 'Fitness Score' chip (legacy showed N/A) and the explicit 'Status: Complete' chip; chip set is dynamic… |
| 🟡 | Geometry Preview pane | gui/analysis_view.py AnalysisDialog._build_geometry_tab 'NE… | Raw NEC2 geometry text is viewable, but only inside the modal Trace Analysis dialog (opened via 'Analysis…' in the properties panel), with a Copy button. There is no always-visible monospaced Geometry Preview pane on th… |
| 🟡 | Estimated design preview | gui/steps/generate_step.py GenerateStep._estimate_line / su… | There is no 'Design Preview (estimated)' section with a Calculate Preview button or segment/length-error fields. Instead the Generate step auto-shows a one-line target-length estimate ('Est. target length: … in (total …… |
| ✅ | Generate Design button | gui/steps/generate_step.py GenerateStep.gen_btn; app.py Ant… | Primary 'Generate Design' button in the Generate step triggers app._generate -> _run_generate via the shared generator. Equivalent (plus an extra toolbar button and keyboard shortcuts). |
| ✅ | Busy / disabled Generate button | gui/steps/generate_step.py set_busy (lines 62-82); app.py _… | Generate button disabled (text -> 'Generating…') during the run and restored on completion; an app-level _busy flag also blocks concurrent _generate calls. |
| ✅ | Background generation thread | app.py AntennaDesignerApp._run_generate / _generate_done (l… | Generation runs in a daemon thread; completion is marshaled back to the UI thread via root.after(0, self._generate_done, ...). Equivalent to legacy _run_design_generation. |
| ✅ | Design Type display | app.py status 'Generated: {design_type}' (line 183); genera… | design_type shown in the status bar, the Generate step result line ('Design: {type} (OK/check warnings)'), and the Performance summary 'Type:' line. Not shown as a 'Design Type:' header in a results-summary block (there… |
| ✅ | Manufacturing warnings list | gui/properties_panel.py _refresh warn StringVar (lines 49-5… | A 'Warnings' section lists each results.validation.warnings entry (bulleted) or 'None'. Equivalent to legacy's Warnings block. |
| ✅ | Success state / step completion | gui/step_rail.py StepRail._refresh/_is_done (lines 50-72); … | On success the rail marks the Generate (3) and Export (4) steps done (✓) once session.has_design, driven by EVT_GENERATED. No numeric 'overall workflow progress percentage' is shown, but step-completion equivalence is m… |

## Analysis & charts

| | Feature | New-GUI location | Notes |
|---|---|---|---|
| ❌ | Connection points (feed pads) listing | - | Connection points are passed into svg_metadata so the canvas can mark/label pads, but there is no text listing of per-resonator feed-pad label/frequency/X-Y in inches and mm anywhere in the new GUI. Legacy printed this … |
| ❌ | Copper-wire antenna fallback recommendations | - | No 'NOT BUILDABLE AS A MEANDER' block. The new GUI never reads results['feasibility'] / infeasible bands, so recommended hand-built designs, dimensions, feed/balun and notes (ui.py lines 1377-1396) are not surfaced. (Th… |
| ❌ | Alternating-row trace table styling | - | New segments treeview inserts rows with no tags (analysis_view.py line 414); no even/odd row tag configuration. Legacy applied 'evenrow'/'oddrow' tags for theme-driven striping. |
| ❌ | Copy trace data to clipboard | - | The analysis dialog has a 'Copy' button only on the NEC Geometry tab (copies raw geometry text). There is no 'Copy to Clipboard' for the per-segment trace table as tab-separated rows (legacy _copy_trace_data). |
| ❌ | Export ASCII analysis to TXT | - | No 'Export TXT' button on the Band Analysis tab (no .txt save anywhere in the gui package). Legacy had _export_ascii_analysis saving a timestamped .txt. |
| ❌ | Chart zoom in/out and fit-to-view | - | No zoom in/out buttons, no zoom-level readout, and no fit-to-view reset for the embedded chart. (The main SVG canvas in canvas_view.py has zoom/fit, but that is the design preview, not the band-analysis chart.) |
| ❌ | Comparison vs detailed analysis mode toggle | - | No analysis_type selector. _generate_chart hardcodes the comparison path; create_detailed_band_chart / detailed single-band mode is never invoked. |
| ❌ | Export band chart image | - | No 'Export Band Analysis Chart' action. The chart PNG is written to a temp file (mad_band_chart.png) only for display; there is no user-facing save/export of the chart image. |
| ❌ | Analyze Performance dialog | - | No Tools menu and no Analyze Performance command. Nothing in the new GUI calls ElectricalConstraints.check_efficiency_requirements to show bands-meeting-spec, estimated efficiency %, rating and per-band pass/fail. (Some… |
| ❌ | Band feasibility analysis dialog | - | No band-selection feasibility popup. BandStep (gui/steps/band_step.py) just selects a band; it never calls BandAnalysis.analyze_band_compatibility, so feasibility score, design complexity, size constraints, recommended … |
| 🟡 | Results & Analysis tab | gui/analysis_view.py:AnalysisDialog (opened from gui/proper… | No top-level/inner notebook in the main workspace. Replaced by a modal 'Trace Analysis' dialog with tabs Segments / NEC Geometry / Band Analysis / Comparison Chart. Legacy's 'Trace Results' + 'Band Analysis' sub-tab spl… |
| 🟡 | Design Summary text panel | gui/properties_panel.py:PropertiesPanel._refresh | No scrolled read-only text block. The right-hand properties panel shows summary lines (Avg VSWR/gain/type), warnings, and feed/pattern, but it is a compact label layout, not the full multi-section text report. Band/freq… |
| 🟡 | Average VSWR / Gain / Bandwidth summary | gui/properties_panel.py:PropertiesPanel._refresh (lines 93-… | Avg VSWR and Avg gain (dBi) are shown. Frequency range and bandwidth (octaves) from summary are NOT shown anywhere in the new GUI. |
| 🟡 | Per-frequency VSWR/Gain/Impedance breakdown | gui/properties_panel.py:PropertiesPanel._refresh (VSWR chip… | Per-band VSWR is shown as colored chips. Per-band gain (dBi) and impedance values are NOT listed (legacy listed VSWR + gain + impedance per frequency band). |
| 🟡 | Predicted radiation pattern summary | gui/properties_panel.py:PropertiesPanel._refresh (lines 113… | Shows pattern type and max gain (dBi). Missing: max-gain DIRECTION (deg) and the null directions list that legacy printed (_display_design_results lines 1344-1348). |
| 🟡 | Feed / Balun / Impedance advice | gui/properties_panel.py:PropertiesPanel._refresh (lines 118… | Shows one line per feed: label, feed-impedance string, and balun yes/no. Missing the full matching_advice and balun_advice text that legacy printed per resonator (ui.py lines 1369-1373). |
| 🟡 | Performance metric status chips | gui/properties_panel.py:PropertiesPanel (_vswr_level + chip… | VSWR-per-band chips are color-coded good/warn/bad on the same <2.0 / <3.0 / >=3.0 thresholds. Missing: dedicated 'Fitness Score' and 'Status' chips. Chips are dynamic per band rather than fixed Band 1/2/3 slots, but fun… |
| 🟡 | Detailed trace length table | gui/analysis_view.py:AnalysisDialog._build_segments_tab / _… | Per-segment treeview with seg#, start/end X-Y, length mm/in and cumulative mm exists. Missing the 'Width (mil)' column that legacy had (legacy parsed GW radius -> width_mil; new parse_segments drops the radius field ent… |
| 🟡 | Generate ASCII analysis button | gui/analysis_view.py:AnalysisDialog._build_band_tab (auto-c… | Functionally covered: the ASCII analysis is built from current freqs/VSWRs/total length/segment count when the tab is created. But there is no explicit 'Generate Analysis' button to re-run it; it only builds once on dia… |
| 🟡 | Matplotlib band-comparison chart generation | gui/analysis_view.py:AnalysisDialog._generate_chart (lines … | Builds a PNG via band_chart.BandAnalysisChart (custom comparison for current band, else all-band comparison). Differences: it is manual via a 'Generate comparison chart' button rather than auto-generated on entering the… |
| 🟡 | Embedded matplotlib chart viewer | gui/analysis_view.py:AnalysisDialog._generate_chart (lines … | Renders the PNG into a tkinter Canvas with horizontal+vertical scrollbars (scrollbar pan). Missing legacy's mouse drag-to-pan and mouse-wheel-to-zoom bindings; image is statically downscaled to ~900px wide with no inter… |
| 🟡 | Clear chart display placeholder | gui/analysis_view.py:AnalysisDialog._chart_unavailable (lin… | Shows a placeholder when matplotlib/Pillow are missing or generation fails. But there is no 'No current design available' guidance placeholder before generating (the chart area is simply empty until the button is presse… |
| ✅ | Design warnings display | gui/properties_panel.py:PropertiesPanel._refresh (lines 110… | Validation warnings are listed in the properties panel (or 'None'). Equivalent to legacy behavior. |
| ✅ | Trace summary statistics | gui/analysis_view.py:AnalysisDialog._populate (self.summary… | Shows Total Length (mm/in), Segment count, Average and Longest segment. Rendered as one summary label rather than four stat fields, but all four stats are present. |
| ✅ | Export trace data to CSV | gui/analysis_view.py:AnalysisDialog._export_csv (button lin… | 'Export CSV' button saves per-segment rows via a save dialog. Minor diffs: writes width-less columns and no Width(mil)/Cumulative columns in the CSV, and uses a fixed default filename ('trace_segments.csv') instead of a… |
| ✅ | ASCII band analysis sub-tab | gui/analysis_view.py:AnalysisDialog._build_band_tab + ascii… | 'Band Analysis' tab renders the ASCII charts in a Consolas ScrolledText. Difference: it auto-generates on open instead of showing a placeholder-until-generated, and there is no separate 'Generate Analysis' button. |
| ✅ | ASCII frequency bands & VSWR table | gui/analysis_view.py:ascii_charts() (lines 78-89) + vswr_ba… | Boxed ASCII table per band with frequency, VSWR and textual quality bar (Excellent/Very Good/Good/Fair/Poor) ported verbatim from ui.py. |
| ✅ | ASCII VSWR bar chart | gui/analysis_view.py:ascii_charts() (lines 91-119) | Scaled horizontal block-character bar chart with 1.0-5.0 reference scale and target thresholds, ported faithfully. |
| ✅ | ASCII trace length analysis block | gui/analysis_view.py:ascii_charts() (lines 122-130) | Boxed ASCII block with total length (mm/in), number of segments and average segment length, ported faithfully. |
| ✅ | ASCII wavelength comparison | gui/analysis_view.py:ascii_charts() (lines 132-165) + reson… | Per-band wavelength (mm), trace/wavelength ratio and resonance classification (quarter/half/three-quarter/full/non-resonant) ported faithfully. |
| ✅ | ASCII performance summary & rating | gui/analysis_view.py:ascii_charts() (lines 167-199) | Counts of Excellent/Good/Poor bands and overall rating (Excellent/Good/Acceptable/Needs Improvement) based on VSWR percentages, ported faithfully. |
| ✅ | Tune expected-results readout | gui/dialogs.py:TuneDialog._recalc (lines 188-219) | Tune dialog shows best gain, lowest efficiency, pattern type/max-gain direction, and per-band gain/efficiency/impedance/feasibility plus warnings and tips, via tune.evaluate_design. Equivalent to legacy (ui.py ~line 178… |

## Library / My Designs

| | Feature | New-GUI location | Notes |
|---|---|---|---|
| ❌ | File menu > Save Design to Library | - | The new GUI has no menu bar at all (no Menu/add_command anywhere in app.py). Saving is only via the 'Save' toolbar button, the Export step's 'Save to Library' button, and Ctrl+S. |
| ❌ | Save Design dialog | app.py _save_design | No modal prompt for Design Name / Filename. _save_design saves silently, using the band name (or 'Custom') as the design name; the user cannot enter a name, and the auto 'Design - YYYYMMDD' name and 'antenna_YYYYMMDD_<r… |
| ❌ | Auto-prompt save on tab visit | - | No equivalent. The legacy MD5-deduped auto-save prompt fired on switching to the My Designs tab (ui.py ~507-525, _prompt_auto_save_current_design); the new GUI has no tabs and no such prompt. |
| ❌ | Design Details panel | - | No read-only details panel. The dialog shows nothing beyond the four list columns; name/substrate size/trace width/type/created/notes/metrics text is not displayed anywhere (cf. legacy _on_design_selected). |
| ❌ | Performance metrics summary | - | No equivalent of _format_performance_metrics (validation within-bounds/manufacturable/complexity, avg VSWR/gain/bandwidth) is rendered in the library UI. Metrics are carried into the session on load but never shown in t… |
| ❌ | Thumbnail preview | - | The dialog has no preview canvas. By design (module docstring) loading renders on the MAIN canvas instead; but there is no in-library thumbnail render of the stored thumbnail_svg, and no PIL/svglib fallback text. |
| ❌ | Preview Zoom In / Zoom Out | - | No thumbnail in the library, so no 1.3x zoom in/out (clamped 30%-1000%). The main CanvasView has its own zoom for the loaded design, but that is not the library thumbnail zoom feature. |
| ❌ | Preview Fit to View | - | No library thumbnail and thus no 'Fit to View'/reset-to-250% control. |
| ❌ | Zoom level indicator | - | No thumbnail zoom percentage label in the library dialog. |
| ❌ | Edit Notes button | - | No notes-edit dialog. storage supports custom_notes (and search includes it), but the new GUI never reads or writes notes, so saved designs cannot be annotated/re-saved with notes. |
| ❌ | Export Selected Design button | - | No one-click 'load selected + export to SVG' from the library. To export a saved design the user must Load it into the session (closing the dialog) and then use the Export step. The fresh auto-default-filename behavior … |
| ❌ | Library stats line | - | No 'Total designs: N | Size: X KB' line. storage.get_design_stats() exists but is never called by the new GUI. |
| ❌ | Resizable split layout | gui/library_view.py LibraryDialog | No PanedWindow split. The dialog is a simple fixed top/body/bottom pack layout (search row, single tree, button row); there is no list-vs-details split because there is no details/preview side, and thus no paned-window … |
| 🟡 | My Designs tab | gui/library_view.py LibraryDialog; app.py AntennaDesignerAp… | No dedicated tab. The library is a modal Toplevel opened from the 'Open Library' toolbar button / Ctrl+O. The wizard-progress concept ('visiting it = 100%') does not exist in the new step-rail model (gui/step_rail.py). |
| 🟡 | Save validation / guards | app.py _save_design (session.has_design check) | Refuses to save when there is no geometry (has_design is geometry-only). Does not separately guard on 'no results', and there is no design-name-required check because there is no name input. |
| 🟡 | Saved Designs list (treeview) | gui/library_view.py LibraryDialog.tree | Scrollable treeview with columns Name, Band, Freqs, Created (created truncated to 19 chars, T->space). Missing the 5th 'Type' (design_type) column that the legacy list had. |
| 🟡 | Design selection | gui/library_view.py LibraryDialog._selected_path / _load | Selecting a row just records its file path; double-click or Load loads it. It does NOT populate any details text or thumbnail on selection (those panels do not exist in the dialog). |
| 🟡 | Load Design button | gui/library_view.py LibraryDialog._load; app.py _load_from_… | Load button (and double-click) loads geometry + results/metrics into the session and renders on the main canvas. Gap: app.py _load_from_library does NOT restore substrate width/height or trace width into the session, no… |
| 🟡 | Export Options (filename + SVG/DXF/PDF) | gui/steps/export_step.py ExportStep; app.py _export | Filename entry + SVG/DXF/PDF buttons exist, but in the dedicated Export step (step 5) operating on the CURRENT design, not inside the library browser. Difference: default filename is the static 'antenna_design', not the… |
| 🟡 | Designs list error handling | gui/library_view.py LibraryDialog._refresh / _load / _delete | List/load/delete are wrapped: list failures log and fall back to an empty list; load/delete failures show messagebox errors. Missing: per-item insertion try/except with a failure count, and the startup 'continue with em… |
| ✅ | Save Current Design button | app.py _save_design; gui/steps/export_step.py ExportStep ('… | Equivalent save action exists in two places. Guards on no-design. Difference: it saves immediately without the name/filename dialog (see Save Design dialog row). |
| ✅ | Refresh List button | gui/library_view.py LibraryDialog._refresh ('Refresh' butto… | Refresh button reloads from storage. Sorting newest-first is delegated to storage.list_designs (default reverse=True), so order matches; the explicit sort_by argument used in legacy is not passed but the default is equi… |
| ✅ | Delete Selected button | gui/library_view.py LibraryDialog._delete ('Delete' button) | Danger-styled Delete with askyesno confirmation, then _refresh. Minor: confirmation text is generic ('Delete this design?') and omits the design name and the 'cannot be undone' warning; it does not clear a details/thumb… |
| ✅ | Search box | gui/library_view.py LibraryDialog (query StringVar, KeyRele… | Live filter on each KeyRelease via storage.search_designs; empty query restores full list. Gap: it does not show a 'N matches for query' status (no status bar in the dialog). |

## Wizard & Tune dialogs

| | Feature | New-GUI location | Notes |
|---|---|---|---|
| 🟡 | Tools menu: Antenna Selection Wizard entry | app.py:_build_toolbar (line 86), app.py:_open_wizard (line … | Wizard is reachable, but via a toolbar button labeled 'Wizard' (bootstyle secondary-outline) rather than a 'Tools' menu command. The new GUI has no menu bar at all (no tkinter Menu anywhere in app.py). Functionally open… |
| 🟡 | Tools menu: Tune Design entry | app.py:_build_toolbar (line 87), app.py:_open_tune (line 28… | Reachable via a toolbar button labeled 'Tune' instead of a 'Tools' menu 'Tune Design' command. Same dialog opens; only the launch affordance differs. |
| 🟡 | Tune prefill from current design | gui/dialogs.py:TuneDialog.__init__ (lines 144-170) | Frequencies prefill from session.frequencies_mhz() (custom override or chosen band's freqs), falling back to '2442' — equivalent source rather than legacy's results freq1/2/3_mhz keys. Mode prefills from res.get('_mode'… |
| 🟡 | Tune Trace width lever | gui/dialogs.py:TuneDialog vars['tw'] (line 159) | Entry 'Trace width (mil)' present and parsed in _recalc, but default differs: prefilled from session.trace_width_mil (default 10.0) rather than the legacy hardcoded '8'. Lever itself works identically; only the default … |
| ✅ | Wizard window | gui/dialogs.py:WizardDialog.__init__ (lines 20-80) | ttk.Toplevel titled 'Antenna Selection Wizard', geometry 760x620. Seeded with session.substrate_width/height (AntennaWizard ctor) with the same try/except fallback to defaults. Adds transient() + <Escape> close + focus_… |
| ✅ | Wizard step 1: Service selector | gui/dialogs.py:WizardDialog.__init__ svc_cb (lines 46-50), … | Read-only combobox '1. What service is this antenna for?' built from wiz.list_services() names; <<ComboboxSelected>> bound to self._find which re-runs discovery. Equivalent. |
| ✅ | Wizard step 2: TX/RX mode selector | gui/dialogs.py:WizardDialog.__init__ mode_cb (lines 51-55) | Read-only combobox '2. Transmit, receive, or both?' from wiz.list_modes() labels, default mode_labels[-1] ('both'); reselecting re-runs _find. Equivalent. |
| ✅ | Wizard service info line | gui/dialogs.py:WizardDialog.info label (lines 56-57), _find… | Secondary-styled (bootstyle=SECONDARY) wrapped label (wraplength=720) showing service notes + first frequency (MHz, 1 decimal) + wavelength (in). Same format string as legacy. |
| ✅ | Wizard step 3: Possible designs list | gui/dialogs.py:WizardDialog.options Listbox (lines 61-63), … | Listbox '3. Possible designs (select one):' height=7; each row prefixed '[OK]'/'[NO]' by feasibility with name + summary. Identical format. |
| ✅ | Wizard auto-select first feasible option | gui/dialogs.py:_find (lines 102-105) | After repopulating, loops options and selection_set on the first feasible one. Same logic as legacy. |
| ✅ | Wizard spec text view | gui/dialogs.py:WizardDialog.spec_text (lines 64-65), _build… | ScrolledText height=16 wrap=WORD displaying spec['spec_text']. Not explicitly set read-only (state stays normal, same as legacy which also did not disable it), so equivalent. |
| ✅ | Wizard 'Find Designs' button | gui/dialogs.py:_find (lines 88-105), button (line 72) | Recomputes options for current service+mode, repopulates list + info line; surfaces failures via messagebox.showerror('Wizard', ...) (now parented to the dialog). Equivalent. |
| ✅ | Wizard 'Build Spec' button | gui/dialogs.py:_build (lines 107-121), button (line 73) | Auto-finds designs if _ctx missing, warns via showinfo if no selection, builds spec for selected index and renders spec_text; showerror on build failure. Matches legacy. |
| ✅ | Wizard 'Use Meander in Designer' button | gui/dialogs.py:_use (lines 123-131), button (line 74); app.… | Refuses non-meander/unbuilt spec via showinfo; otherwise calls on_apply(spec['design']) -> _apply_design which sets session results/geometry, rebuilds SVG and notifies EVT_GENERATED (canvas refresh), then shows 'Loaded … |
| ✅ | Wizard 'Close' button | gui/dialogs.py:WizardDialog Close button (lines 76-77) | Right-aligned (side=RIGHT) secondary-styled button that destroys the window without applying. Also bound to <Escape>. Equivalent. |
| ✅ | Wizard auto-run on open | gui/dialogs.py:WizardDialog.__init__ (line 80) | self._find() is called at the end of __init__, so list/info populate immediately. Same as legacy. |
| ✅ | Wizard error/info dialogs | gui/dialogs.py:_find (92), _build (112,117), _use (127,130) | messagebox.showerror for load/build failures, showinfo for missing selection, non-meander spec, and successful load. All present (now with parent=self.win). Equivalent set of prompts. |
| ✅ | Tune window | gui/dialogs.py:TuneDialog.__init__ (lines 134-186) | ttk.Toplevel titled 'Tune Antenna Design', geometry 720x640, with top form, large ScrolledText output, and button row. Adds transient + <Escape> + focus_set (enhancements). |
| ✅ | Tune Frequencies lever | gui/dialogs.py:TuneDialog vars['freqs'] (line 156), form ro… | Entry 'Frequencies (MHz, comma-sep)' width=28, comma-split parsed in _recalc. Equivalent. |
| ✅ | Tune Substrate width lever | gui/dialogs.py:TuneDialog vars['sw'] (line 157) | Entry 'Substrate width (in)' prefilled from session.substrate_width, parsed in _recalc. Equivalent. |
| ✅ | Tune Substrate height lever | gui/dialogs.py:TuneDialog vars['sh'] (line 158) | Entry 'Substrate height (in)' prefilled from session.substrate_height, parsed in _recalc. Equivalent. |
| ✅ | Tune Target gain lever | gui/dialogs.py:TuneDialog vars['tg'] (line 160), _recalc (1… | Entry 'Target gain (dBi, blank=none)' default blank; blank -> None, otherwise float, passed as target_gain_dbi. Identical to legacy. |
| ✅ | Tune Mode lever | gui/dialogs.py:TuneDialog mode combobox (lines 169-172) | Read-only combobox 'Mode' values ['tx','rx','both'] default res.get('_mode','both'). Equivalent. |
| ✅ | Tune results output area | gui/dialogs.py:TuneDialog.out (lines 174-175) | ScrolledText height=24 wrap=WORD rendering the report. Not explicitly disabled (same as legacy). Equivalent. |
| ✅ | Tune results summary header | gui/dialogs.py:_recalc (lines 201-206) | 'EXPECTED RESULTS (WxH in, TW mil, mode)' header, '='*56 rule, best gain dBi + lowest efficiency %% line. Identical text/format to legacy. |
| ✅ | Tune pattern summary | gui/dialogs.py:_recalc (lines 205-206) | 'Pattern: <type> (max <gain> dBi @ <dir> deg)' line. Identical format. |
| ✅ | Tune per-band breakdown | gui/dialogs.py:_recalc (lines 209-213) | Per-band lines with label, freq MHz, '[OK]'/'[NOT VIABLE]' flag, gain dBi, eff %%, and impedance Z. Identical to legacy. |
| ✅ | Tune warnings section | gui/dialogs.py:_recalc (line 214) | Appends 'WARNINGS:' block with '! <w>' lines when r['warnings'] present. Equivalent (uses r.get('warnings')). |
| ✅ | Tune tips section | gui/dialogs.py:_recalc (line 216) | Appends 'TIPS:' block with '- <t>' lines when r['tips'] present. Equivalent (uses r.get('tips')). |
| ✅ | Tune 'Recalculate' button | gui/dialogs.py:_recalc (lines 188-219), button (line 179) | Re-evaluates from current lever values via evaluate_design and refreshes output; on bad numeric input shows 'Check numeric fields.' Equivalent. |
| ✅ | Tune 'Apply to Current Design' button | gui/dialogs.py:_apply (lines 221-232), button (line 180); a… | Auto-recalcs if needed, updates session.substrate_width/height from r['substrate_in'], passes design (with geometry) to on_apply -> _apply_design which refreshes canvas/props via EVT_GENERATED. Prompt text adapted to 'S… |
| ✅ | Tune 'Close' button | gui/dialogs.py:TuneDialog Close button (lines 182-183) | Right-aligned (side=RIGHT) secondary button destroying the window without applying; also bound to <Escape>. Equivalent. |
| ✅ | Tune auto-run on open | gui/dialogs.py:TuneDialog.__init__ (line 186) | self._recalc() called at end of __init__ so results show before any interaction. Same as legacy. |
| ✅ | Tune numeric validation dialog | gui/dialogs.py:_recalc (lines 196-198) | On ValueError parsing any field, shows messagebox.showerror('Tune','Check numeric fields.', parent=win) and returns. Identical message. |

## Export

| | Feature | New-GUI location | Notes |
|---|---|---|---|
| ❌ | File menu Export commands | - | The new GUI has no menu bar at all (toolbar + step rail only). There is a Ctrl+E shortcut bound to _export('svg') in app.py _bind_keys (only SVG), but no menu File>Export SVG/DXF/PDF entries. Only DXF/PDF have no keyboa… |
| ❌ | Auto-generated default filename | gui/steps/export_step.py (filename initialized to literal "… | New GUI hardcodes filename StringVar(value="antenna_design"); there is no antenna_<YYYYMMDD>_<5-char random> generation and nothing regenerates it on view/selection. Legacy used datetime + random.choices (ui.py:2460-246… |
| ❌ | Export Selected Design (quick export) | - | The new library browser (gui/library_view.py LibraryDialog) only offers Load/Delete/Close; it has no quick-export button. To export a library design the user must Load it into the session, then use the Export step butto… |
| ❌ | Etching-readiness warning | - | No EtchingValidator usage anywhere in the new GUI (grep for EtchingValidator/validate_for_etching in gui/ and app.py returns nothing). Legacy ran EtchingValidator.validate_for_etching before export and warned on high co… |
| ❌ | Save Geometry to .nec file | - | No raw geometry save-to-.nec anywhere. Grep for asksaveasfilename/.nec/Save Geometry in gui/ returns only analysis_view.py:424 (a CSV trace-segment export, unrelated). The new GUI's 'Save'/'Save to Library' (app.py _sav… |
| ❌ | Load Geometry from file | - | No askopenfilename / load-raw-geometry-from-file in the new GUI. 'Open Library' (app.py _open_library -> LibraryDialog) loads only stored library designs, not an arbitrary .nec file. Legacy file load (ui.py:267,1952-196… |
| 🟡 | Export metadata embedding | app.py AntennaDesignerApp._svg_metadata (passed into export… | New _svg_metadata includes band_name, frequencies, design_type, connection_points, feed_advice, radiation_pattern. It OMITS design_date timestamp, fitness_score, and explicit substrate_width/substrate_height keys that l… |
| 🟡 | Pre-export geometry validation guard | app.py AntennaDesignerApp._export: guards on `if not self.s… | New export only checks session.has_design (warns 'Generate a design first.'). It does NOT replicate legacy's deeper checks for empty/whitespace geometry or zero GW wire lines (ui.py:1840-1875). has_design relies on sess… |
| 🟡 | Export error handling | app.py _export: except ExportError -> logger.exception + me… | Catches ExportError and shows 'Export failed' with a log reference. Unlike legacy (ui.py:1910-1913) it does NOT catch generic Exception, so a non-ExportError failure inside export would propagate uncaught rather than sh… |
| ✅ | Export SVG / DXF / PDF format buttons | gui/steps/export_step.py ExportStep.__init__ (loop over ("s… | Three format buttons in the Export step call _export(fmt), which calls exporter.export_geometry. Equivalent to legacy ui.py:2472-2477. Styled secondary-outline like legacy. |
| ✅ | Export filename field | gui/steps/export_step.py ExportStep.filename (StringVar) + … | User-editable filename Entry exists and its value is passed as the export base name, matching legacy export_filename_var behavior (ui.py:2458-2466,1883). |
| ✅ | Empty-filename fallback | app.py AntennaDesignerApp._export: name = self.steps[4].fil… | Blank filename falls back to literal 'antenna_design', identical to legacy ui.py:1883-1885. |
| ✅ | Feed-pad connection point labels | app.py _svg_metadata: "connection_points": design.get("conn… | connection_points are forwarded in export metadata exactly as legacy ui.py:1896-1897; same exporter consumes them. |
| ✅ | Feed advice annotations | app.py _svg_metadata: "feed_advice": design.get("feed_advic… | feed_advice is included in export metadata, matching legacy ui.py:1898. |
| ✅ | Radiation pattern overlay | app.py _svg_metadata: "radiation_pattern": design.get("radi… | radiation_pattern forwarded to the exporter as in legacy ui.py:1899-1900. (Also separately toggleable as a canvas preview layer in canvas_view.py.) |
| ✅ | Export-complete confirmation dialog | app.py _export: messagebox.showinfo("Exported", f"Saved {fm… | Success messagebox shows the full output path; status bar shows 'Exported <FMT> -> <path>'. Equivalent to legacy 'Export Complete' dialog (ui.py:1907-1908). Note new GUI uses the status bar rather than a scrolling messa… |
| ✅ | Output directory (fixed, no chooser) | app.py _export uses self.exporter (VectorExporter) default … | Same model as legacy: no directory picker; VectorExporter writes to its own default location and the returned path is surfaced (ui.py:98,1903-1908). |
| ✅ | Export Options panel | gui/steps/export_step.py ExportStep: ttk.LabelFrame(text="E… | An 'Export' LabelFrame groups the filename entry and the three format buttons, equivalent to legacy 'Export Options' LabelFrame (ui.py:2450-2482). It does not include the legacy quick 'Export Selected Design' button; 'S… |

## App shell

| | Feature | New-GUI location | Notes |
|---|---|---|---|
| ❌ | Menu bar | - | New GUI has no Tk menu bar at all (app.py never calls root.config(menu=...)). Top-level actions live on a button toolbar (_build_toolbar, app.py:82-95) instead: New, Open Library, Save, Wizard, Tune, Generate, Theme. No… |
| ❌ | Help menu | - | No Help cascade and no About or User Guide commands anywhere in app.py or gui/ (grep for About/User Guide/Help returns nothing). |
| ❌ | Themed-text widget registry | - | No _register_text equivalent. ScrolledText/Text widgets (gui/dialogs.py, gui/analysis_view.py) are created with default tk colors and never tracked or reskinned to match the active theme; they will look out of place in … |
| ❌ | Tabbed notebook | - | No central ttk.Notebook in the main window and no <<NotebookTabChanged>> handler. The Design/Results/My Designs tabs are replaced by the step rail (StepRail) swapping single step panels, the always-on canvas+properties,… |
| ❌ | Workflow percentage display | - | No per-step workflow percentage (25/50/75/99/100%) and no 'NN% ✓ Complete' label anywhere. The only percentage shown is the canvas zoom level (CanvasView zoom_label) and GenerateStep's generation bar, neither of which r… |
| ❌ | Bottom Previous/Next navigation | - | No bottom Previous/Next buttons, no dynamic 'Next: <step>'/'Complete' labels, and no nav tip label. Step navigation is done by clicking step buttons in the left StepRail (_select) or Ctrl+1..5 shortcuts. There is no seq… |
| ❌ | Step gating / jump logic | - | No gating. StepRail._select jumps to any step unconditionally (step_rail.py:45-48); there is no _jump_to_workflow_step block-ahead check and no 'Complete the current step first' error. StepRail._is_done only paints ✓ ma… |
| ❌ | About dialog | - | No _show_about equivalent; no About messagebox with app name/version/feature list anywhere in the new GUI. |
| ❌ | User Guide / Help dialog | - | No _show_help equivalent; no User Guide messagebox with usage steps/tips/supported types. Only per-step one-line hints in StepRail (STEPS help strings) loosely fill this role, but there is no consolidated help. |
| ❌ | View Logs window | - | No log viewer. Nothing reads/displays antenna_designer.log (grep confirms no reference in gui/ or app.py). Errors are only surfaced via messageboxes and loguru file/console output. |
| ❌ | Global error handling | - | No _setup_global_error_handling; root.report_callback_exception is never installed. Uncaught Tk callback exceptions print to console/loguru (or Tk's default handler) instead of showing a user error dialog. Individual ge… |
| ❌ | System configuration validation on startup | - | __init__ never calls validate_system_configuration and never defers a config-issues error dialog. Startup goes straight to building the UI (app.py:43-67). |
| ❌ | In-app timestamped message log | - | No message_text pane and no _log_message; there is no in-app, HH:MM:SS-timestamped scrolling message log. Logging is only via loguru (file/console). |
| ❌ | Graceful window-close protocol | - | No WM_DELETE_WINDOW handler. app.main() just creates the window and calls mainloop (app.py:303-306); closing during a generation thread is not guarded with an 'Optimization in progress. Really quit?' prompt. (Mitigated … |
| ❌ | CLI debug flags | - | app.main() handles no command-line flags; --test-storage / --debug-storage are not implemented for the new GUI. main.py only recognizes --new/ANTENNA_GUI to choose the GUI and then ignores other args (legacy ui.main sti… |
| ❌ | Exit command | - | No explicit Exit action (no File>Exit, no menu, no toolbar quit button). Closing relies entirely on the OS window close button. root.quit is never wired. |
| 🟡 | File menu | app.py _build_toolbar / ExportStep (gui/steps/export_step.p… | No File cascade. Equivalents scattered: New (toolbar _new, app.py:249), Save to Library (toolbar/ExportStep _save_design), Export SVG/DXF/PDF (ExportStep buttons -> _export). Missing entirely: Load Geometry and Save Geo… |
| 🟡 | Tools menu | app.py toolbar + gui/dialogs.py + gui/analysis_view.py | No Tools cascade. Wizard (_open_wizard) and Tune (_open_tune) are toolbar buttons. Analyze Performance maps to PropertiesPanel 'Analysis…' button -> AnalysisDialog (gui/analysis_view.py). Validate Geometry has no standa… |
| 🟡 | View menu (Dark mode toggle) | app.py _build_toolbar / _toggle_theme (app.py:93-94, 294-30… | Theme switching exists but as a toolbar 'Theme' button, not a View-menu checkbutton bound to a BooleanVar. It is a plain toggle with no checked-state indicator (state tracked only by self.dark_mode). |
| 🟡 | Theme reskin of classic widgets | gui/canvas_view.py apply_theme (canvas_view.py:83-86) | Only the main SVG canvas is reskinned on theme change, and even that just sets background + re-renders. No equivalent of _apply_theme_colors: tk Text/ScrolledText panes (in dialogs/analysis), Treeview alternating-row st… |
| 🟡 | Status indicator chip helper | gui/properties_panel.py _refresh (properties_panel.py:73-91) | No reusable _set_status_chip helper. The good/warn/bad color-coded chip concept is reimplemented inline for VSWR chips in PropertiesPanel (via _vswr_level -> SUCCESS/WARNING/DANGER + 'inverse' bootstyle). It is a one-of… |
| 🟡 | Window title and geometry | app.py __init__ (app.py:45-47) | Title is 'Mini Antenna Designer' (legacy adds the '- Tri-Band Design' suffix). Geometry 1320x880 (legacy 1200x850), minsize 1024x700 (legacy 960x680). Resizable by default. Functionally equivalent; only the exact title … |
| 🟡 | Main layout container | app.py _build_workspace (app.py:102-138) | Completely different paradigm. Legacy = vertical stack (progress header / tabbed notebook / bottom nav). New = CAD-style horizontal four-region workspace (step rail | active-step panel | SVG canvas | properties) with to… |
| 🟡 | Workflow progress header band | gui/step_rail.py + gui/steps/generate_step.py | No top header band with bold step title + striped determinate bar + percentage + hint. Step title/hint moved to the left StepRail (active step highlighted, one-line help, STEPS[i][1]). A progress bar exists only inside … |
| 🟡 | Workflow state display sync | app.py _on_session + StepRail._refresh + step _refresh hand… | No single _update_workflow_display. State sync is event-driven and distributed: session.notify(EVT_*) fans out to StepRail (active step + ✓ marks), PropertiesPanel (metrics), GenerateStep (bar/result), and app._on_sessi… |
| 🟡 | Error message dialog helper | app.py (inline in _generate_done/_export/_save_design) | No reusable _show_error helper. Error dialogs are produced inline at each call site as logger.exception(...) + messagebox.showerror(...) (app.py:179, 222, 245; also in dialogs/library/analysis). Behavior (log + dialog) … |
| 🟡 | Startup error guard | main.py main (main.py:11-38) | app.main() itself has NO try/except around window creation/mainloop (app.py:303-306). The guard lives one level up in main.py, which wraps `from app import main; gui_main()` in try/except (ImportError/KeyboardInterrupt/… |
| ✅ | Light/dark theme switching | app.py _toggle_theme (app.py:294-300), LIGHT_THEME/DARK_THE… | Same litera/darkly swap via self.style.theme_use at runtime. Reskins the one non-ttk widget it owns (the canvas) via canvas_view.apply_theme. Equivalent runtime behavior, just driven from a toolbar button. |
| ✅ | Status bar | app.py _build_statusbar (app.py:97-99), status_var (app.py:… | Bottom sunken ttk.Label bound to status_var ('Ready' default), packed side=BOTTOM so it stays visible, updated throughout (_generate, _export, _save_design, _on_session, etc.). Equivalent to legacy. |
| ✅ | No keyboard shortcuts/accelerators | app.py _bind_keys (app.py:69-79) | This legacy 'feature' is the absence of shortcuts. The new GUI actually ADDS global shortcuts (Ctrl+G/Ctrl+Return generate, Ctrl+S save, Ctrl+O library, Ctrl+N new, Ctrl+E export svg, Ctrl+1..5 step select) plus <Escape… |
