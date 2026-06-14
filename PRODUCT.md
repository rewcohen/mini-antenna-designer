# Product

## Register

product

## Platform

Desktop GUI — Python + Tkinter via `ttkbootstrap` (themes `litera` / `darkly`). The
new wizard-driven CAD front end lives in `app.py` + `gui/`; legacy `ui.py` is the
fallback until parity. This is **not** a web frontend, so impeccable's CSS/OKLCH/
browser-screenshot tooling does not apply directly. The strategic layer here —
register, principles, hierarchy, copy, contrast, color semantics — still governs
the work; translate visual rules to ttk styles, fonts, spacing, and canvas drawing.

## Users

Two audiences served by one tool — **guided but deep**:

- **Newcomers / makers** etching their own boards (ham, DIY, hobbyist). They lean on
  the wizard, visual band gallery, and sane defaults. They want to get a
  manufacturable design without knowing antenna theory.
- **RF / hardware engineers** who know the domain, want precise control over
  substrate, trace width, contact pads, and band frequencies, and trust the numbers
  (VSWR, NEC analysis, per-segment trace data) before exporting to manufacturing.

Context: a focused design session at a desk, often iterating toward a target before
exporting SVG/DXF/PDF for laser etching. The interface must let a beginner succeed
on the happy path while never hiding the depth an expert reaches for.

## Product Purpose

Generate compact, manufacturable tri-band planar antennas — folding long antennas
into small copper substrates via meandering — with electromagnetic analysis,
manufacturing validation, and vector export for laser etching. Success = a user
goes band → board → trace → generate → export and walks away with a fabrication-ready
file they trust, the expert verifying the physics and the newcomer trusting the
guidance.

## Brand Personality

**Clean, guided, approachable.** Calm and modern; demystifies a hard domain without
dumbing it down. Confidence comes from clarity and good defaults, not from density or
jargon. Voice in copy: plain, direct, encouraging — explain the "why" in one line of
inline help rather than assuming theory. A guided wizard on the surface, real
engineering depth one click under it.

## Anti-references

- **Dated Tk default look** — gray 1990s system widgets, beveled buttons, system
  gray. The exact thing this rewrite exists to escape.
- **Cluttered EDA overload** — wall-of-toolbars, dozens of always-on panels, nothing
  breathing. Power must not cost clarity. (Contrast: KiCad/Altium density is the
  trap, not the goal.)
- **Consumer / playful app** — rounded gradients, mascots, big friendly bubbles,
  toy aesthetics. Too soft for an engineering instrument.
- **Generic SaaS dashboard** — card-grid + hero-metric template transplanted onto a
  desktop tool. Off-register; this is an instrument, not a metrics page.

## Design Principles

1. **Guided surface, deep core.** The default path (step rail: band → board → trace
   → generate → export) is walkable by a beginner; advanced controls, raw NEC data,
   and analysis are always one deliberate click away, never in the way.
2. **The canvas is the product.** The live SVG preview is the center of gravity — the
   largest, most prominent region. Controls serve it; chrome stays quiet so the
   design reads.
3. **Earn trust with legible numbers.** VSWR, warnings, trace lengths, validation —
   show them plainly and accurately. An expert must be able to verify the physics at
   a glance; a guarded value beats a crash or a guess.
4. **Calm density.** Show what the current step needs, nothing more. Rhythm and
   whitespace over packing; one clear primary action per step.
5. **Two themes, both first-class.** Light (`litera`) and dark (`darkly`) are equals,
   each readable on its own terms; the canvas follows the theme.

## Accessibility & Inclusion

No formal WCAG target set. Apply sensible defaults: keep body/label text at readable
contrast (aim ≥4.5:1) in **both** light and dark themes; don't encode status (VSWR
pass/fail, warnings) in color alone — pair red/green with text, icon, or shape;
legible default font sizes for long design sessions. Revisit if a specific user need
surfaces.
