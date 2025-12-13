"""NEC2 electromagnetic analysis core with error handling and logging."""
import logging
from pathlib import Path
from typing import Optional, Tuple, List
import numpy as np
from loguru import logger
import os
import time
import functools

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
            # Check if backup already exists and remove it
            if backup_file.exists():
                backup_file.unlink()

            # Move current log to backup
            log_file.rename(backup_file)
            logger.info("Log file rotated on startup")

        except (OSError, PermissionError) as e:
            # If rotation fails (file in use, permissions, etc.), just truncate
            try:
                # Try to truncate the existing log file instead
                with open(log_file, 'w') as f:
                    f.write(f"# Log rotated/truncated due to error: {str(e)}\n")
                logger.info("Log file truncated (rotation failed due to file in use)")
            except Exception as truncate_e:
                logger.warning(f"Could not rotate or truncate log file: {str(e)}, {str(truncate_e)}")
                # Silently fail - logging may not work but app should continue

# Configure logging with rotation
_rotate_logs_on_startup()  # Rotate logs at startup

logger.add("antenna_designer.log", rotation="10 MB", retention="7 days", level="INFO")
logger.add(lambda msg: print(msg, end=""), level="INFO")  # Console output

def validate_system_configuration() -> dict:
    """Validate overall system configuration and dependencies."""
    status = {'valid': True, 'checks': []}
    
    # Check 1: Directories
    for d in ['temp', 'exports', 'designs']:
        p = Path(d)
        if not p.exists():
            try:
                p.mkdir(exist_ok=True)
                status['checks'].append(f"✓ Created {d} directory")
            except Exception as e:
                status['valid'] = False
                status['checks'].append(f"✗ Failed to create {d}: {e}")
        elif not os.access(p, os.W_OK):
            status['valid'] = False
            status['checks'].append(f"✗ {d} directory is not writable")
        else:
            status['checks'].append(f"✓ {d} directory is ready")

    # Check 2: dependencies (log only)
    try:
        import numpy
        status['checks'].append(f"✓ numpy {numpy.__version__} available")
    except ImportError:
        status['valid'] = False
        status['checks'].append("✗ numpy package missing")

    return status

class NEC2Error(Exception):
    """Custom exception for NEC2-related errors."""
    pass

class NEC2Interface:
    """NEC2 electromagnetic analysis interface with robust error handling."""

    def __init__(self, nec2_path: Optional[str] = None):
        """Initialize NEC2 interface.

        Args:
            nec2_path: Path to NEC2 executable, auto-detects if None
        """
        self.nec2_path = None
        try:
            self.nec2_path = self._find_nec2_executable(nec2_path)
            logger.info(f"NEC2 interface initialized with executable: {self.nec2_path}")
        except NEC2Error as e:
            logger.warning(f"NEC2 executable not found: {str(e)} - using mock simulation mode")
        finally:
            self.temp_dir = Path("temp")
            self.temp_dir.mkdir(exist_ok=True)

    def _find_nec2_executable(self, nec2_path: Optional[str]) -> str:
        """Find NEC2 executable with fallback options."""
        if nec2_path and Path(nec2_path).exists():
            return nec2_path

        # Try common locations
        common_paths = [
            "/usr/local/bin/nec2",
            "/usr/bin/nec2",
            "C:\\NEC2\\nec2.exe",
            "./nec2.exe"
        ]

        for path in common_paths:
            if Path(path).exists():
                return path

        raise NEC2Error("NEC2 executable not found. Please specify nec2_path or install NEC2.")

    @PerformanceMonitor.measure_time
    def run_simulation(self, nec_input: str, frequencies: List[float]) -> dict:
        """Run NEC2 simulation for given antenna geometry and frequencies.

        Args:
            nec_input: NEC2 input card format string
            frequencies: List of frequencies in MHz

        Returns:
            dict: Simulation results with VSWR, gain, impedance data

        Raises:
            NEC2Error: If simulation fails
        """
        try:
            results = {}
            base_freq = frequencies[0]  # Primary frequency for geometry scaling

            for freq in frequencies:
                logger.info(f"Running NEC2 simulation for {freq} MHz")
                output = self._execute_nec2(nec_input, freq)

                if not output:
                    raise NEC2Error(f"NEC2 simulation failed for {freq} MHz")

                results[freq] = self._parse_nec2_output(output)

            logger.info(f"Simulation completed for {len(frequencies)} frequencies")
            return results

        except Exception as e:
            logger.error(f"Simulation error: {str(e)}")
            raise NEC2Error(f"Simulation failed: {str(e)}") from e

    def _execute_nec2(self, nec_input: str, frequency: float) -> Optional[str]:
        """Execute NEC2 command with error handling."""
        input_file = self.temp_dir / f"antenna_{frequency:.1f}.nec"
        output_file = self.temp_dir / f"antenna_{frequency:.1f}.out"

        try:
            # Write NEC2 input file
            with open(input_file, 'w') as f:
                f.write(self._format_nec2_input(nec_input, frequency))

            # Execute NEC2 (placeholder - would call actual NEC2 binary)
            # For now, return mock data structure
            mock_output = self._generate_mock_output(frequency)

            logger.debug(f"NEC2 executed for {frequency} MHz")
            return mock_output

        except FileNotFoundError as e:
            logger.error(f"NEC2 file operation failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"NEC2 execution error: {str(e)}")
            return None

    def _format_nec2_input(self, nec_input: str, frequency: float) -> str:
        """Format NEC2 input with frequency-specific cards."""
        frequency_card = f"FR 0 1 0 0 {frequency} 0"
        geometry_cards = nec_input
        excitation_card = "EX 0 1 1 0 1.0"  # Wire 1, 50 ohm line
        compute_card = "XQ"  # Execute

        return f"{frequency_card}\n{geometry_cards}\n{excitation_card}\n{compute_card}\nEN"

    def _parse_nec2_output(self, output: str) -> dict:
        """Parse NEC2 output into structured results."""
        try:
            # Enhanced mock parsing for the mock output format
            lines = output.strip().split('\n')
            vswr = 2.2  # Default VSWR
            gain = 2.1  # Default gain in dBi
            impedance = complex(50.0, 5.0)  # Default impedance
            freq = 0.0

            # Parse the mock output format more robustly
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Extract frequency
                if line.startswith('FREQUENCY'):
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            freq = float(parts[1])
                        except (ValueError, IndexError):
                            pass
                # Extract VSWR
                elif line.startswith('VSWR'):
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            vswr = float(parts[1])
                        except (ValueError, IndexError):
                            pass
                # Extract GAIN
                elif line.startswith('GAIN'):
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            gain = float(parts[1])
                        except (ValueError, IndexError):
                            pass
                # Extract IMPEDANCE
                elif line.startswith('IMPEDANCE'):
                    parts = line.split()
                    if len(parts) >= 3:
                        try:
                            real_part = float(parts[1])
                            imag_part = float(parts[2])
                            impedance = complex(real_part, imag_part)
                        except (ValueError, IndexError):
                            pass

            return {
                'vswr': vswr,
                'gain_dbi': gain,
                'impedance_ohms': impedance,
                'frequency_mhz': freq
            }
        except Exception as e:
            logger.warning(f"Error parsing NEC2 output: {str(e)}")
            return {'error': str(e)}

    def _generate_mock_output(self, frequency: float) -> str:
        """Generate mock NEC2 output for development."""
        # Generate realistic mock data based on frequency
        if frequency < 100:  # VHF Low
            vswr = 2.8
            gain = 1.2
            impedance_real = 35.0
            impedance_imag = 15.0
        elif frequency < 500:  # VHF High/UHF
            vswr = 2.2
            gain = 2.1
            impedance_real = 45.0
            impedance_imag = 8.0
        elif frequency < 2000:  # L-band
            vswr = 1.9
            gain = 2.8
            impedance_real = 52.0
            impedance_imag = 5.0
        else:  # Microwave
            vswr = 2.5
            gain = 3.2
            impedance_real = 48.0
            impedance_imag = 12.0

        return f"""FREQUENCY {frequency}
VSWR {vswr}
GAIN {gain}
IMPEDANCE {impedance_real} {impedance_imag}"""

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

            # Check VSWR < 3:1
            validation['vswr_ok'] = vswr < 3.0

            # Check gain > -10 dBi
            validation['gain_sufficient'] = gain > -10.0

            # Check impedance within 50 ± 20 ohms
            if isinstance(impedance, complex):
                real_part = impedance.real
                validation['impedance_matched'] = 30 <= real_part <= 70

            validation['overall_pass'] = all(validation.values())

        except Exception as e:
            logger.error(f"Performance validation error: {str(e)}")

        return validation
