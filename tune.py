"""Antenna tuning: recompute expected results as the user adjusts the design.

Given the levers a builder can actually change - substrate size, trace width,
target frequency, and a gain goal - this recomputes the expected performance
(VSWR, gain, impedance, efficiency, radiation pattern) and returns plain-language
tips and warnings. Gain is a first-class lever: the user can set a target gain and
the evaluator reports whether it is met and how to raise it.

Pure logic (no GUI); drives the tuning dialog and is directly testable.
"""
from typing import Dict, List, Optional

from loguru import logger

from core import NEC2Interface, AntennaAnalyzer
from design_generator import AntennaDesignGenerator
from presets import FrequencyBand, BandType

# Manufacturing / performance limits used for tips and warnings.
_MIN_ETCH_MIL = 6.0          # finest trace a hobby laser/etch reliably holds
_MAX_VSWR_OK = 2.0           # good match
_MAX_VSWR_USABLE = 3.0       # usable match
_LOW_EFF_PCT = 20.0          # below this, efficiency is poor


def evaluate_design(frequencies: List[float],
                    substrate_width_in: float,
                    substrate_height_in: float,
                    trace_width_mil: float,
                    mode: str = 'both',
                    target_gain_dbi: Optional[float] = None) -> Dict:
    """Recompute expected results for a set of tuning lever values.

    Args:
        frequencies: band frequencies in MHz (1-3 values, zeros ignored).
        substrate_width_in, substrate_height_in: board size (a lever - bigger
            board generally means more gain).
        trace_width_mil: trace width in mils (a lever).
        mode: 'tx', 'rx' or 'both' (affects how strict the warnings are).
        target_gain_dbi: optional gain goal; reported as met / not met with tips.

    Returns:
        dict with per-band results, the radiation pattern, tips and warnings.
    """
    freqs = [f for f in frequencies if f and f > 0] or [frequencies[0] if frequencies else 0]
    tw_in = max(trace_width_mil, 0.1) / 1000.0

    gen = AntennaDesignGenerator(NEC2Interface(),
                                 substrate_width=substrate_width_in,
                                 substrate_height=substrate_height_in)
    f = list(freqs) + [0, 0, 0]
    band = FrequencyBand('Tuning', BandType.CUSTOM, (f[0], f[1], f[2]), '', [])
    design = gen.generate_design(band, trace_width_inches=tw_in)

    feed_advice = design.get('feed_advice', [])
    feasibility = {b['label']: b for b in design.get('feasibility', [])}
    pattern = design.get('radiation_pattern', {})

    bands = []
    for a in feed_advice:
        feas = feasibility.get(a['label'], {})
        bands.append({
            'label': a['label'],
            'freq_mhz': a['freq_mhz'],
            'gain_dbi': a.get('gain_dbi', -50.0),
            'efficiency_pct': a.get('efficiency_pct', 0.0),
            'impedance': a.get('feed_impedance_str', '?'),
            'feasible': feas.get('feasible', True),
            'matching_advice': a.get('matching_advice', ''),
            'balun_advice': a.get('balun_advice', ''),
        })

    best_gain = max((b['gain_dbi'] for b in bands), default=-50.0)
    worst_eff = min((b['efficiency_pct'] for b in bands), default=0.0)

    tips: List[str] = []
    warnings: List[str] = []

    # Manufacturing.
    if trace_width_mil < _MIN_ETCH_MIL:
        warnings.append(f"Trace width {trace_width_mil:.0f} mil is below ~{_MIN_ETCH_MIL:.0f} mil "
                        f"- hard to laser/etch reliably. Widen the trace.")

    # Match / VSWR (from feed resistance via advice text already; use efficiency + impedance).
    for b in bands:
        if not b['feasible']:
            warnings.append(f"{b['label']} ({b['freq_mhz']:.0f} MHz): not a usable meander on this "
                            f"board - see the copper-wire alternatives.")

    # Efficiency.
    if worst_eff < _LOW_EFF_PCT:
        msg = (f"Lowest band efficiency is {worst_eff:.0f}% (poor). "
               f"Increase the substrate size to give the element more room.")
        (warnings if mode in ('tx', 'both') else tips).append(msg)

    # Gain lever.
    if target_gain_dbi is not None:
        if best_gain >= target_gain_dbi:
            tips.append(f"Gain target met: best band ~{best_gain:.1f} dBi >= {target_gain_dbi:.1f} dBi.")
        else:
            warnings.append(f"Gain target NOT met: best band ~{best_gain:.1f} dBi < "
                            f"{target_gain_dbi:.1f} dBi target.")
            tips += _gain_improvement_tips(substrate_width_in, substrate_height_in)
    elif mode in ('tx', 'both') and best_gain < 0:
        tips += _gain_improvement_tips(substrate_width_in, substrate_height_in)

    if mode in ('tx', 'both'):
        tips.append("For transmit, keep VSWR < 2 to protect the radio; add the matching "
                    "network / balun noted per band.")

    return {
        'frequencies_mhz': freqs,
        'substrate_in': (substrate_width_in, substrate_height_in),
        'trace_width_mil': trace_width_mil,
        'mode': mode,
        'best_gain_dbi': round(best_gain, 1),
        'worst_efficiency_pct': round(worst_eff, 1),
        'target_gain_dbi': target_gain_dbi,
        'gain_target_met': (target_gain_dbi is None) or (best_gain >= target_gain_dbi),
        'bands': bands,
        'pattern': {
            'type': pattern.get('pattern_type'),
            'max_gain_dbi': pattern.get('max_gain_dbi'),
            'max_gain_dir_deg': pattern.get('max_gain_dir_deg'),
        },
        'geometry': design.get('geometry', ''),
        'design': design,
        'tips': tips,
        'warnings': warnings,
    }


def _gain_improvement_tips(sub_w: float, sub_h: float) -> List[str]:
    """Concrete ways to raise gain, given the current board."""
    return [
        f"To raise gain: enlarge the substrate (currently {sub_w:.0f}x{sub_h:.0f} in) - "
        f"more physical extent radiates better.",
        "To raise gain: fewer, longer meander runs (less folding) keep more of the "
        "current adding in phase.",
        "For real gain, a copper-wire dipole/ground-plane or a multi-element design "
        "beats a tightly folded planar meander.",
    ]
