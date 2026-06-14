---
target: app.py + gui/ (wizard CAD GUI)
total_score: 25
p0_count: 0
p1_count: 3
timestamp: 2026-06-14T18-17-01Z
slug: app-py-gui-wizard-cad-gui
---
# Critique — Wizard CAD GUI (`app.py` + `gui/`)

Desktop Tkinter/ttkbootstrap product UI. Web detector + browser overlay N/A; LLM design review against the product register and PRODUCT.md.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Status bar + step ✓ marks good; progress bar is fake (static 40% then jumps to 100) |
| 2 | Match System / Real World | 3 | Strong for experts; balun/VSWR/mil unexplained for the newcomer half |
| 3 | User Control and Freedom | 2 | Stop is a no-op; no undo; New wipes design with no confirm |
| 4 | Consistency and Standards | 3 | Selected band card is SUCCESS green; active rail step is PRIMARY — two "selected" colors |
| 5 | Error Prevention | 2 | Custom-freq entry swallows ValueError silently; New destroys without confirm |
| 6 | Recognition Rather Than Recall | 3 | Persistent rail + visual gallery + always-on properties: good |
| 7 | Flexibility and Efficiency | 2 | No keyboard shortcuts anywhere; no Enter-to-generate |
| 8 | Aesthetic and Minimalist | 3 | Clean 4-region; band grid borders on identical-card but is a real gallery |
| 9 | Error Recovery | 2 | showerror dumps raw `str(exception)`; custom-freq fails silently |
| 10 | Help and Documentation | 2 | One-line inline help per step; nothing deeper |
| **Total** | | **25/40** | **Acceptable** |

## Anti-Patterns Verdict
Does not read as AI web-slop (native Tk). Product slop test (would a KiCad/Altium user trust it?): structure yes, but trust leaks at the fake progress bar, the lying Stop button, silent custom-freq failure, and raw-exception dialogs. The two-color "selected" state (green card vs blue rail) is the clearest visual tell.

## What's Working
- Persistent step rail with ✓ completion state + active highlight + inline help. Real recognition-over-recall.
- Visual band gallery grouped by category replaces a dropdown — discoverable, on-brand for "guided surface."
- Always-on properties panel: VSWR chips carry the number as text (not color-only) — passes colorblind check.

## Priority Issues
- **[P1] Fake progress bar.** `set_busy` parks progress at a static 40% then snaps to 100. Generation is 1–3s with no real percentage, so the bar misinforms. **Fix:** indeterminate animated bar while busy (honest motion). Maps to /impeccable animate.
- **[P1] Stop button is a no-op.** DANGER-styled, prominent, does nothing (`_stop` just sets a status string). Either remove it during the short run or make it an honest disabled/hidden affordance. /impeccable distill or clarify.
- **[P1] Silent custom-frequency failure.** `_use_custom` catches ValueError and returns with zero feedback — a typo in a freq field looks like a dead button. **Fix:** inline validation message. /impeccable harden + clarify.
- **[P2] Raw exception text in dialogs.** `showerror(..., str(error))` leaks Python tracebacks/messages to users. **Fix:** plain-language message + log the detail. /impeccable clarify.
- **[P2] Inconsistent selected-state color.** Band card selected = SUCCESS, rail active = PRIMARY. One "selected" vocabulary. /impeccable colorize or polish.
- **[P2] No keyboard path.** No shortcuts, no Enter-to-generate, no Esc on dialogs. Power-user (Alex) friction. /impeccable audit.

## Persona Red Flags
- **Alex (power user):** zero keyboard shortcuts; Stop button that does nothing; raw NEC geometry view still unported. Will feel slow.
- **Jordan (first-timer):** "balun", "VSWR", "mil" with no inline definition; custom-freq typo fails silently with no hint of why.
- **Sam (a11y):** VSWR chips include the numeric text (good, not color-only); but no documented focus-visible/keyboard traversal of the rail.

## Minor Observations
- `PAD_S/PAD_M` redefined in nearly every module — centralize.
- Generate step `result` label and properties `summary` overlap in info; one source of truth would reduce redundancy.
- `ttk.LabelFrame = ttk.Labelframe` monkeypatch in app.py is a smell worth a comment.

## Questions to Consider
- The progress bar can't show real percent (backend is synchronous). Is an honest indeterminate pulse better than a fake number?
- Half the audience is newcomers — should jargon get hover/inline definitions, or is a glossary panel enough?
- Does Stop earn its place at all for a 1–3s run?
