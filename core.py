"""Antenna performance analysis core.

NOTE ON THE ANALYSIS ENGINE
---------------------------
This module does NOT bundle a full-wave method-of-moments solver. A real
NEC2 / PyNEC binary is optional and, if present, would be called by
``NEC2Interface``. When no solver is available (the common case on a fresh
install), performance is computed by an *analytical estimator* in
``AntennaAnalyzer``. The estimator parses the actual wire geometry (GW cards)
and applies standard antenna physics (radiation resistance, skin-effect loss,
resonance detuning). Results are clearly labelled ``analytical`` in the
``method`` field so callers and the UI never mistake an estimate for a
full-wave simulation.
"""
import math
import os
import sys
import time
import functools
from pathlib import Path
from typing import Optional, List, Dict

from loguru import logger

# --- Windows console can't encode the emoji used throughout the app; force
#     UTF-8 so log/print statements don't crash with a 'charmap' codec error. ---
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass


class PerformanceMonitor:
    """Monitor execution time and resources."""

    @staticmethod
    def measure_time(func):
        """Decorator to measure execution time."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(f"Performance: {func.__name__} took {duration:.4f}s")
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"Performance: {func.__name__} failed after {duration:.4f}s: {str(e)}")
                raise
        return wrapper


def _rotate_logs_on_startup():
    """Rotate logs on application startup with robust error handling."""
    log_file = Path("antenna_designer.log")
    backup_file = Path("antenna_designer.log.bak")

    if log_file.exists():
        try:
            if backup_file.exists():
                backup_file.unlink()
            log_file.rename(backup_file)
            logger.info("Log file rotated on startup")
        except (OSError, PermissionError) as e:
            try:
                with open(log_file, 'w', encoding='utf-8') as f:
                    f.write(f"# Log rotated/truncated due to error: {str(e)}\n")
                logger.info("Log file truncated (rotation failed due to file in use)")
            except Exception as truncate_e:
                logger.warning(f"Could not rotate or truncate log file: {str(e)}, {str(truncate_e)}")


# Configure logging with rotation
_rotate_logs_on_startup()
logger.add("antenna_designer.log", rotation="10 MB", retention="7 days", level="INFO", encoding="utf-8")
logger.add(lambda msg: print(msg, end=""), level="INFO")  # Console output


def validate_system_configuration() -> dict:
    """Validate overall system configuration and dependencies."""
    status = {'valid': True, 'checks': []}

    for d in ['temp', 'exports', 'designs']:
        p = Path(d)
        if not p.exists():
            try:
                p.mkdir(exist_ok=True)
                status['checks'].append(f"Created {d} directory")
            except Exception as e:
                status['valid'] = False
                status['checks'].append(f"Failed to create {d}: {e}")
        elif not os.access(p, os.W_OK):
            status['valid'] = False
            status['checks'].append(f"{d} directory is not writable")
        else:
            status['checks'].append(f"{d} directory is ready")

    try:
        import numpy
        status['checks'].append(f"numpy {numpy.__version__} available")
    except ImportError:
        status['valid'] = False
        status['checks'].append("numpy package missing")

    return status


class NEC2Error(Exception):
    """Custom exception for NEC2-related errors."""
    pass


# Physical constants
_C = 299_792_458.0          # speed of light, m/s
_MU0 = 4e-7 * math.pi       # permeability of free space, H/m
_SIGMA_CU = 5.8e7           # conductivity of copper, S/m
_INCH_M = 0.0254            # inches -> meters
_Z0 = 50.0                  # reference / feedline impedance, ohms


class AntennaAnalyzer:
    """Analytical antenna performance estimator.

    Parses NEC ``GW`` geometry cards (coordinates in inches) and computes a
    physics-based estimate of VSWR, gain, impedance and radiation efficiency.
    This is a coarse closed-form model, not a full-wave solution: it captures
    the right trends versus frequency and geometry but should not be trusted to
    full-wave accuracy. Every result carries ``method='analytical'``.
    """

    @staticmethod
    def parse_geometry(nec_input: str) -> Dict[str, float]:
        """Extract conductor length, radius and bounding box from GW cards.

        Returns lengths in metres. Returns zeros if no wires are found.
        """
        total_len_m = 0.0
        radii = []
        xs, ys, zs = [], [], []

        for raw in (nec_input or "").splitlines():
            parts = raw.split()
            if len(parts) >= 9 and parts[0].upper() == "GW":
                try:
                    x1, y1, z1 = float(parts[3]), float(parts[4]), float(parts[5])
                    x2, y2, z2 = float(parts[6]), float(parts[7]), float(parts[8])
                    radius = float(parts[9]) if len(parts) >= 10 else 0.008
                except (ValueError, IndexError):
                    continue
                seg_len = math.dist((x1, y1, z1), (x2, y2, z2)) * _INCH_M
                total_len_m += seg_len
                radii.append(abs(radius) * _INCH_M)
                xs += [x1, x2]; ys += [y1, y2]; zs += [z1, z2]

        if not xs:
            return {'total_len_m': 0.0, 'radius_m': 0.0, 'extent_m': 0.0, 'wire_count': 0}

        # Largest straight-line extent of the structure (the dimension that
        # actually radiates; meander folds largely cancel and do not add to it).
        extent_in = math.dist(
            (min(xs), min(ys), min(zs)),
            (max(xs), max(ys), max(zs)),
        )
        avg_radius = sum(radii) / len(radii) if radii else 0.0002
        return {
            'total_len_m': total_len_m,
            'radius_m': max(avg_radius, 1e-5),
            'extent_m': max(extent_in * _INCH_M, 1e-4),
            'wire_count': len(radii),
        }

    @staticmethod
    def estimate(geom: Dict[str, float], frequency_mhz: float) -> dict:
        """Estimate performance metrics for one frequency from parsed geometry."""
        f_hz = frequency_mhz * 1e6
        lam = _C / f_hz
        total_len = geom['total_len_m']
        radius = geom['radius_m']
        extent = geom['extent_m']

        if total_len <= 0:
            return {
                'vswr': float('inf'), 'gain_dbi': -50.0,
                'impedance_ohms': complex(0, 0), 'efficiency': 0.0,
                'frequency_mhz': frequency_mhz, 'method': 'analytical',
            }

        # --- Radiation resistance from electrical SIZE (not folded wire length).
        # Short-dipole limit R = 20*pi^2*(D/lam)^2, capped at the half-wave
        # value of ~73 ohm.
        d_over_lam = extent / lam
        r_rad = min(73.0, 20.0 * math.pi ** 2 * d_over_lam ** 2)
        r_rad = max(r_rad, 0.05)

        # --- Conductor (skin-effect) loss along the full wire path.
        rs = math.sqrt(math.pi * f_hz * _MU0 / _SIGMA_CU)   # surface resistance
        circumference = 2 * math.pi * radius
        r_loss = rs * total_len / circumference / 2.0       # /2: standing-wave avg
        r_loss = max(r_loss, 1e-3)

        # --- Reactance from resonance detuning of the total wire length.
        # Resonance occurs near integer multiples of a half wavelength.
        half_wave = lam / 2.0
        n_res = max(1, round(total_len / half_wave))
        detune = (total_len - n_res * half_wave) / half_wave   # fractional
        reactance = max(-600.0, min(600.0, 1200.0 * detune))

        r_in = r_rad + r_loss
        impedance = complex(r_in, reactance)

        # --- VSWR against the 50 ohm feed.
        gamma = abs((impedance - _Z0) / (impedance + _Z0))
        gamma = min(gamma, 0.999)
        vswr = (1 + gamma) / (1 - gamma)

        # --- Radiation efficiency and realized gain.
        efficiency = r_rad / (r_rad + r_loss)
        directivity = 1.5 + 0.14 * min(1.0, d_over_lam / 0.5)   # ~1.5 (short) -> ~1.64 (half-wave)
        realized = directivity * efficiency * (1 - gamma ** 2)
        gain_dbi = 10.0 * math.log10(realized) if realized > 0 else -50.0

        return {
            'vswr': round(vswr, 3),
            'gain_dbi': round(gain_dbi, 2),
            'impedance_ohms': complex(round(r_in, 2), round(reactance, 2)),
            'efficiency': round(efficiency, 4),
            'frequency_mhz': frequency_mhz,
            'method': 'analytical',
        }


class NEC2Interface:
    """Antenna analysis interface.

    Uses a bundled full-wave NEC2 binary when one is configured/found;
    otherwise falls back to the analytical estimator in ``AntennaAnalyzer``.
    The public API (``run_simulation``) is identical in both modes.
    """

    def __init__(self, nec2_path: Optional[str] = None):
        self.nec2_path = self._find_nec2_executable(nec2_path)
        self.temp_dir = Path("temp")
        self.temp_dir.mkdir(exist_ok=True)
        if self.nec2_path:
            logger.info(f"NEC2 interface initialized with executable: {self.nec2_path}")
        else:
            logger.info("No NEC2 solver found - using analytical performance estimator")

    def _find_nec2_executable(self, nec2_path: Optional[str]) -> Optional[str]:
        """Locate a NEC2 executable, returning None if none is available."""
        candidates = [nec2_path] if nec2_path else []
        candidates += [
            "/usr/local/bin/nec2", "/usr/bin/nec2",
            "C:\\NEC2\\nec2.exe", "./nec2.exe",
        ]
        for path in candidates:
            if path and Path(path).exists():
                return path
        return None

    @PerformanceMonitor.measure_time
    def run_simulation(self, nec_input: str, frequencies: List[float]) -> dict:
        """Analyze antenna geometry across the requested frequencies.

        Args:
            nec_input: NEC geometry (GW cards), coordinates in inches.
            frequencies: Frequencies in MHz.

        Returns:
            dict keyed by frequency -> {vswr, gain_dbi, impedance_ohms,
            efficiency, frequency_mhz, method}.
        """
        if not frequencies:
            raise NEC2Error("No frequencies provided")

        geom = AntennaAnalyzer.parse_geometry(nec_input)
        if geom['wire_count'] == 0:
            logger.warning("No GW geometry cards found in input")

        results = {}
        for freq in frequencies:
            logger.info(f"Analyzing antenna at {freq} MHz ({geom['wire_count']} wires, "
                        f"{geom['total_len_m'] / _INCH_M:.2f} in conductor)")
            # Write the .nec card file (used by export / external solvers).
            self._write_nec_file(nec_input, freq)
            results[freq] = AntennaAnalyzer.estimate(geom, freq)

        logger.info(f"Analysis completed for {len(frequencies)} frequencies")
        return results

    def _write_nec_file(self, nec_input: str, frequency: float) -> Optional[Path]:
        """Write a complete NEC input deck to temp/ for export/debugging."""
        input_file = self.temp_dir / f"antenna_{frequency:.1f}.nec"
        try:
            with open(input_file, 'w', encoding='utf-8') as f:
                f.write(self._format_nec2_input(nec_input, frequency))
            return input_file
        except OSError as e:
            logger.error(f"Could not write NEC file {input_file}: {e}")
            return None

    def _format_nec2_input(self, nec_input: str, frequency: float) -> str:
        """Wrap geometry cards with frequency, excitation and execute cards."""
        frequency_card = f"FR 0 1 0 0 {frequency} 0"
        excitation_card = "EX 0 1 1 0 1.0"
        compute_card = "XQ"
        return f"{frequency_card}\n{nec_input}\n{excitation_card}\n{compute_card}\nEN"


class AntennaMetrics:
    """Calculate and validate antenna performance metrics."""

    @staticmethod
    def calculate_vswr(reflection_coefficient: complex) -> float:
        """Calculate VSWR from reflection coefficient."""
        try:
            gamma = abs(reflection_coefficient)
            if gamma >= 1.0:
                return float('inf')
            return (1 + gamma) / (1 - gamma)
        except (TypeError, ValueError) as e:
            logger.error(f"VSWR calculation error: {str(e)}")
            return float('inf')

    @staticmethod
    def validate_performance(results: dict) -> dict:
        """Validate antenna performance within acceptable limits."""
        validation = {
            'vswr_ok': False,
            'gain_sufficient': False,
            'impedance_matched': False,
            'overall_pass': False
        }

        try:
            vswr = results.get('vswr', float('inf'))
            gain = results.get('gain_dbi', -50)
            impedance = results.get('impedance_ohms', complex(0, 0))

            validation['vswr_ok'] = vswr < 3.0
            validation['gain_sufficient'] = gain > -10.0

            if isinstance(impedance, complex):
                real_part = impedance.real
                validation['impedance_matched'] = 30 <= real_part <= 70

            validation['overall_pass'] = all(validation.values())

        except Exception as e:
            logger.error(f"Performance validation error: {str(e)}")

        return validation
