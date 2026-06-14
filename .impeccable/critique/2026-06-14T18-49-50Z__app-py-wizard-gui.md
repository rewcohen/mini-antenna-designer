---
target: app.py + gui/ (wizard CAD GUI), 2nd pass w/ screenshots
total_score: 23
p0_count: 0
p1_count: 3
timestamp: 2026-06-14T18-49-50Z
slug: app-py-wizard-gui
---
# Critique — Wizard CAD GUI (`app.py` + `gui/`)

Desktop Tkinter/ttkbootstrap product UI. Web detector + browser overlay N/A (no markup); evidence is 7 real screenshots of the running app (light + dark, every step, a generated design) plus source review against the product register and PRODUCT.md. Second pass on this surface — adds live visual evidence the first (code-only) pass lacked.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Status bar + ✓ marks good; progress bar now honest (indeterminate→settle). But VSWR numbers print unrounded |
| 2 | Match System / Real World | 3 | Strong for experts; balun/VSWR/mil unexplained for newcomers |
| 3 | User Control and Freedom | 2 | Stop still a no-op; no undo; New wipes design with no confirm |
| 4 | Consistency and Standards | 2 | Two "selected" colors (green card vs blue rail); dark-mode canvas is a glaring white box; clipped labels |
| 5 | Error Prevention | 2 | Custom-freq entry swallows ValueError silently; size clamps silently |
| 6 | Recognition Rather Than Recall | 3 | Persistent rail + visual gallery + always-on properties |
| 7 | Flexibility and Efficiency | 2 | No keyboard shortcuts; no Enter-to-generate; no Esc on dialogs |
| 8 | Aesthetic and Minimalist | 2 | **Canvas — the declared product — renders tiny in a vast empty center; preview labels overlap into black bars; large dead vertical space** |
| 9 | Error Recovery | 2 | showerror dumps raw `str(exception)`; custom-freq fails silently |
| 10 | Help and Documentation | 2 | One-line inline help per step; nothing deeper |
| **Total** | | **23/40** | **Acceptable** |

Down 2 from the prior 25: the progress-bar fix landed (+), but live screenshots exposed contrast, canvas-scale, label-overlap and number-formatting failures the code-only pass could not see (−).

## Anti-Patterns Verdict

**LLM:** Does not read as AI web-slop (native Tk). Product slop test (would a KiCad/Altium user trust it?): the structure earns trust; the rendered output does not. The hero canvas shows the antenna as overlapping black bars with collided labels (`ANT1 (54 MHz)` / `TRACE VALIDATION` / `DIMENSIONS` stacked on top of each other) — the one artifact the whole tool exists to produce looks broken. Avg VSWR prints `557.2886666666667`. Both are trust leaks an RF engineer notices in one glance.

**Deterministic scan:** `detect.mjs --json gui app.py` → `[]` (real attempt; the markup detector has nothing to parse in a Python/Tk app). Not a skipped run — N/A by platform.

**Visual evidence:** 7 screenshots captured from the live app at 1320×880. No browser overlay (non-web); the screenshots themselves are the deterministic visual record.

## What's Working
- Persistent step rail with ✓ completion state, active highlight, and inline help — real recognition-over-recall.
- Visual band gallery grouped by category replaces a dropdown — discoverable, on-brand for "guided surface."
- Honest motion (since last pass): indeterminate striped bar while the backend thread runs, ease-out settle to a green full bar on success, `ANTENNA_REDUCED_MOTION` opt-out. The prior fake-40%-then-100 bar is resolved.
- Dark theme reads well: dark buttons + white text have strong contrast; semantic VSWR chips (red/orange/green) carry the number as text, not color alone (colorblind-safe).

## Priority Issues

- **[P1] The canvas is not the product.** PRODUCT.md principle #2 says the preview is "the largest, most prominent region." In reality the SVG renders small and top-left-aligned inside an enormous empty center; "Fit" / "100%" leaves ~70% of the canvas blank. The focal point of the whole instrument is the weakest region on screen. **Fix:** make Fit actually fit the SVG to the viewport (scale to fill with margin), center it, and let the canvas column dominate the layout. Maps to /impeccable layout.
- **[P1] The rendered design is illegible.** At the current render size the meander collapses into solid black horizontal bars and the embedded labels (`ANT1 (54 MHz)`, `TRACE VALIDATION:`, `DIMENSIONS:`) overlap into unreadable mush. An expert cannot verify the physics from the preview; a newcomer sees a glitch. **Fix:** larger default render, declutter the SVG overlay (separate label layer, collision-free placement, or hide annotation text below a zoom threshold). /impeccable layout + optimize.
- **[P1] Light-theme contrast fails.** Secondary (gray) buttons with white text — the entire toolbar (New/Open Library/Save/Wizard/Tune), inactive rail steps, and band cards — sit well below 4.5:1. Secondary gray help text and slider labels on a white panel are barely readable. Dark theme is fine; the two themes are not "both first-class" (principle #5). **Fix:** use a darker foreground on secondary controls in `litera`, or restyle inactive controls as outline/light buttons with dark ink. /impeccable colorize + audit.
- **[P2] Numbers undermine trust.** `Avg VSWR: 557.2886666666667` (raw float) and `VSWR 1335.23` printed verbatim. Principle #3 ("earn trust with legible numbers") is violated by formatting. **Fix:** round to 2 dp; cap implausible VSWR (e.g. display `>10`); show a plain-language "barely radiates" note when efficiency is ~4%. /impeccable clarify.
- **[P2] Clipped text.** Band-card labels and their frequency units are cut off (`...2462 [MHz]`, `174/200/216 MH[z]`) by the fixed `width=24`; the **"Use Custom" button is clipped to "U"** because the custom-frequency row overflows the 370 px panel. Reads as unfinished. **Fix:** wrap/auto-size cards; reflow the custom row (stack the button or widen entries). /impeccable adapt + layout.

## Carry-over (still open from the prior pass)
- **[P2] Stop is a no-op** — DANGER-styled, prominent, does nothing. Hide/disable it for the 1–3 s run.
- **[P2] No keyboard path** — no shortcuts, no Enter-to-generate, no Esc on dialogs (Alex friction).
- **[P2] Silent custom-freq failure** + **raw exception text** in error dialogs.
- **[P2] Two selected-state colors** — band card SUCCESS green vs rail PRIMARY blue.

## Persona Red Flags
- **Alex (power user):** still zero keyboard shortcuts; Stop that does nothing; tiny preview forces manual zoom/pan on every generate.
- **Jordan (first-timer):** "balun", "VSWR", "mil" undefined; a freq typo fails silently; light-theme labels are hard to read; the broken-looking preview reads as an error.
- **Sam (a11y):** light-theme secondary text/buttons fail WCAG AA contrast; no documented focus-visible/keyboard traversal. Chips correctly carry text, not color alone (good).
- **Riley (stress tester):** generated a physically absurd result (VSWR 1335, −32 dBi) for a tri-band TV antenna on a 4×2 board and the UI presented it as "OK" with one soft warning — the validity signal is too quiet for how unviable the design is.

## Minor Observations
- Canvas placeholder text ("…to preview it here") renders cut off at the top of the canvas, not centered — it's drawn before the canvas has its real height.
- Dark-mode canvas is a bright white rectangle (the SVG's own white background isn't theme-aware) — jarring against the dark workspace.
- Large dead vertical space under the Board/Trace/Generate/Export panels (fixed-width short columns).
- `PAD_S/PAD_M` redefined in nearly every module; `ttk.LabelFrame = ttk.Labelframe` monkeypatch uncommented.

## Questions to Consider
- If the canvas is the product, should it fill the workspace and the input panels collapse to a slim rail once a design exists?
- The preview embeds validation text, dimensions and a radiation-pattern overlay all at once — is that three views fighting for one surface? Should they be toggleable layers?
- A VSWR of 1335 is mathematically meaningless to show — what's the honest ceiling, and should the UI say "won't radiate" instead of a number?
