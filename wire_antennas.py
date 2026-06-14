"""DIY copper-wire antenna alternatives.

When a meandered planar trace cannot make a usable antenna on the chosen
substrate - either the resonant length will not fit, or the element is so
electrically small that it barely radiates - the tool should stop pretending and
instead suggest a buildable copper-wire design. This module decides whether the
meander is feasible and, if not, recommends straightforward hand-built copper
antennas with computed dimensions.

All dimensions are returned in inches and centimetres. Frequencies are MHz.
"""
import math
from typing import Dict, List

from loguru import logger

from core import AntennaAnalyzer

# Wavelength in inches for a frequency in MHz (free space): c/f converted to in.
# 11802.7 = speed of light in inches/us; lambda_in = 11802.7 / f_MHz.
_WAVELENGTH_CONST_IN = 11802.7
# Velocity factor for thin bare copper wire in air (~0.95-0.98).
_WIRE_VF = 0.95

# Feasibility thresholds for a meander on the substrate.
_MIN_EFFICIENCY = 0.10        # below 10% radiation efficiency it is a dummy load
_MIN_FIT_FRACTION = 0.95      # achieved length must be >=95% of the target


def wavelength_in(freq_mhz: float) -> float:
    """Free-space wavelength in inches."""
    return _WAVELENGTH_CONST_IN / freq_mhz if freq_mhz > 0 else 0.0


def _in_cm(inches: float) -> str:
    return f"{inches:.2f} in ({inches * 2.54:.1f} cm)"


def recommend_alternatives(freq_mhz: float) -> List[Dict]:
    """Recommend buildable copper-wire antennas for a frequency, with dimensions.

    Designs are chosen by frequency range and ordered easiest-first. Each entry
    has a name, key dimensions, feed impedance, balun guidance and build notes.
    """
    if freq_mhz <= 0:
        return []

    lam = wavelength_in(freq_mhz)
    quarter = lam / 4 * _WIRE_VF
    half = lam / 2 * _WIRE_VF
    full = lam * _WIRE_VF

    designs: List[Dict] = []

    # Quarter-wave ground plane / monopole - simplest VHF/UHF performer.
    designs.append({
        'name': 'Quarter-wave ground plane',
        'dimensions': {
            'vertical radiator': _in_cm(quarter),
            'radials (x4, sloping ~45 deg)': _in_cm(quarter),
        },
        'feed_impedance': '~36 Ohm (close enough for direct 50 Ohm coax)',
        'balun': 'None - unbalanced, connect coax directly',
        'gain_dbi': 1.5,
        'notes': ('One vertical copper wire on the centre pin, four radials on the '
                  'shield. Excellent, forgiving antenna for VHF/UHF.'),
    })

    # Half-wave dipole - the reference resonant antenna.
    designs.append({
        'name': 'Half-wave dipole',
        'dimensions': {
            'total tip-to-tip': _in_cm(half),
            'each leg': _in_cm(half / 2),
        },
        'feed_impedance': '~73 Ohm',
        'balun': '1:1 current balun (balanced element on unbalanced coax)',
        'gain_dbi': 2.15,
        'notes': 'Two straight copper wires fed in the centre. Mount clear of metal.',
    })

    # Full-wave loop - quiet, a bit more wire.
    designs.append({
        'name': 'Full-wave loop',
        'dimensions': {'perimeter': _in_cm(full), 'side if square': _in_cm(full / 4)},
        'feed_impedance': '~100-130 Ohm',
        'balun': '1:1 balun; or 4:1 to get nearer 50 Ohm',
        'gain_dbi': 3.0,
        'notes': 'A single closed loop of copper wire. Slightly more gain; lower noise on receive.',
    })

    if freq_mhz >= 100:
        # J-pole / slim-jim - end fed, no radials, popular for VHF/UHF handhelds.
        designs.append({
            'name': 'J-pole (or Slim Jim)',
            'dimensions': {
                'half-wave radiator': _in_cm(half),
                'quarter-wave matching stub': _in_cm(quarter),
                'feed tap from bottom': _in_cm(quarter * 0.05),
            },
            'feed_impedance': '50 Ohm at the matching tap',
            'balun': 'Choke balun (few coax turns) recommended at the feed',
            'gain_dbi': 2.2,
            'notes': 'End-fed half-wave with a quarter-wave matching stub - no radials needed.',
        })
    else:
        # HF compact options when full-size wire is impractical.
        designs.append({
            'name': 'Small transmitting (magnetic) loop',
            'dimensions': {
                'loop circumference (~lambda/8)': _in_cm(full / 8),
                'loop diameter': _in_cm(full / 8 / math.pi),
            },
            'feed_impedance': 'Very low - coupled via a small feed loop or gamma match',
            'balun': 'None; use a coupling loop + tuning capacitor',
            'gain_dbi': -1.0,
            'notes': ('A single turn of thick copper (tube/wire) plus a tuning capacitor. '
                      'Very compact for HF but narrow-band; retune when changing frequency.'),
        })
        designs.append({
            'name': 'Coil-loaded (helically wound) whip',
            'dimensions': {
                'physical whip length': 'as tall as practical (shorter than %s)' % _in_cm(quarter),
                'loading coil': 'wind copper to add the missing electrical length',
            },
            'feed_impedance': 'Low, needs an antenna tuner / matching network',
            'balun': 'None (unbalanced); add a common-mode choke',
            'gain_dbi': -3.0,
            'notes': 'Trades efficiency for size; a base or centre loading coil restores resonance.',
        })

    return designs


def assess_meander_feasibility(resonators: List[Dict],
                               substrate_width_in: float,
                               substrate_height_in: float,
                               min_efficiency: float = _MIN_EFFICIENCY) -> List[Dict]:
    """Decide whether each band's meander is a usable antenna; recommend wire if not.

    Args:
        resonators: list of dicts with 'label', 'freq_mhz', 'geometry',
            'target_in', 'achieved_in' (from generate_separate_band_resonators).
        substrate_width_in, substrate_height_in: board size.
        min_efficiency: minimum acceptable radiation efficiency. Receive-only use
            tolerates much lower (a small inefficient antenna still hears signals);
            transmit needs it higher to avoid wasting power / stressing the radio.

    Returns:
        list of per-band dicts: label, freq, feasible (bool), efficiency_pct,
        reason, and (when not feasible) alternatives.
    """
    diag = math.hypot(substrate_width_in, substrate_height_in)
    out: List[Dict] = []
    for r in resonators or []:
        freq = r.get('freq_mhz', 0) or 0
        geom = AntennaAnalyzer.parse_geometry(r.get('geometry', ''))
        est = AntennaAnalyzer.estimate(geom, freq, velocity_factor=0.90) if freq > 0 else {}
        eff = est.get('efficiency', 0.0)
        target = r.get('target_in', 0.0)
        achieved = r.get('achieved_in', 0.0)

        fit_ok = target <= 0 or achieved >= _MIN_FIT_FRACTION * target
        eff_ok = eff >= min_efficiency
        feasible = fit_ok and eff_ok

        reasons = []
        if not fit_ok:
            reasons.append(f"resonant length {target:.1f} in does not fit the "
                           f"{substrate_width_in:.0f}x{substrate_height_in:.0f} in board")
        if not eff_ok:
            lam = wavelength_in(freq)
            reasons.append(f"element is electrically tiny on this board "
                           f"(extent/wavelength ~= {diag / lam:.3f}, est. efficiency "
                           f"{eff * 100:.1f}% - it would barely radiate)")

        entry = {
            'label': r.get('label'),
            'freq_mhz': freq,
            'feasible': feasible,
            'efficiency_pct': round(eff * 100, 1),
            'reason': '; '.join(reasons) if reasons else 'meander is a usable radiator on this board',
        }
        if not feasible:
            entry['alternatives'] = recommend_alternatives(freq)
            logger.info(f"{r.get('label')} {freq:.0f}MHz: meander not viable ({entry['reason']}); "
                        f"recommending {len(entry['alternatives'])} copper-wire alternatives")
        out.append(entry)
    return out
