"""Frequency band presets for tri-band antenna design."""
from typing import Dict, List, Tuple, Optional
from enum import Enum
from loguru import logger

class BandType(Enum):
    """Enumeration of frequency band categories."""
    TV_BROADCAST = "tv_broadcast"
    WIFI_ISM = "wifi_ism"
    CELLULAR = "cellular"
    SATELLITE = "satellite"
    CUSTOM = "custom"

class FrequencyBand:
    """Represents a frequency band with descriptive properties."""

    def __init__(self, name: str, band_type: BandType, frequencies_mhz: Tuple[float, float, float],
                 description: str, applications: List[str], wavelength_range: Optional[Tuple[float, float]] = None):
        """Initialize frequency band.

        Args:
            name: Human-readable name
            band_type: Type of band (TV, WiFi, etc.)
            frequencies_mhz: B1, B2, B3 center frequencies in MHz
            description: Detailed description
            applications: List of typical applications
            wavelength_range: Optional wavelength range in meters
        """
        self.name = name
        self.band_type = band_type
        self.frequencies = frequencies_mhz
        self.description = description
        self.applications = applications
        self.wavelength_range = wavelength_range

        # Calculate wavelengths if not provided
        if not wavelength_range:
            wavelengths = []
            for f in frequencies_mhz:
                if f > 0:
                    # Wavelength = c/f where c = 299792458 m/s, convert to MHz and meters
                    wavelength = 299792458 / (f * 1e6)
                    wavelengths.append(wavelength)
            self.wavelength_range = (min(wavelengths), max(wavelengths)) if wavelengths else (0, 0)

    def get_frequency_tuple(self) -> Tuple[float, float, float]:
        """Return the three band frequencies."""
        return self.frequencies

    def get_size_estimate(self) -> Dict[str, float]:
        """Estimate antenna sizes for this band."""
        f1, f2, f3 = self.frequencies
        min_freq = min(f for f in [f1, f2, f3] if f > 0)

        # Quarter wave lengths for resonant elements
        quarter_wave_m = 299792458 / (min_freq * 1e6) / 4
        quarter_wave_inch = quarter_wave_m * 39.37  # Convert to inches

        return {
            'quarter_wave_m': quarter_wave_m,
            'quarter_wave_inch': quarter_wave_inch,
            'electrical_length_factor': min_freq  # Higher frequency = smaller size
        }

class BandPresets:
    """Collection of predefined frequency band combinations."""

    @staticmethod
    def get_all_bands() -> Dict[str, FrequencyBand]:
        """Return all predefined frequency bands."""
        return {
            # TV Broadcast Bands (VHF/UHF)
            'tv_vhf_low': FrequencyBand(
                name='TV VHF Low',
                band_type=BandType.TV_BROADCAST,
                frequencies_mhz=(54, 72, 88),
                description='TV channels 2-6 (VHF Low band)',
                applications=['Television broadcasting', 'Aviation communication']
            ),
            'tv_vhf_high': FrequencyBand(
                name='TV VHF High',
                band_type=BandType.TV_BROADCAST,
                frequencies_mhz=(174, 200, 216),
                description='TV channels 7-13 (VHF High band)',
                applications=['Television broadcasting', 'FM radio backup']
            ),
            'tv_uhf': FrequencyBand(
                name='TV UHF',
                band_type=BandType.TV_BROADCAST,
                frequencies_mhz=(470, 650, 698),
                description='TV channels 14-51 (UHF band)',
                applications=['Digital television', 'Wireless microphones']
            ),

            # WiFi/ISM Bands
            'wifi_2g_extend': FrequencyBand(
                name='WiFi 2.4GHz Extended',
                band_type=BandType.WIFI_ISM,
                frequencies_mhz=(2412, 2437, 2462),
                description='802.11b/g/n channels across 2.4GHz ISM band',
                applications=['WiFi routers', 'Bluetooth devices', 'Smart home']
            ),
            'wifi_dual': FrequencyBand(
                name='WiFi Dual Band',
                band_type=BandType.WIFI_ISM,
                frequencies_mhz=(2437, 5500, 5800),
                description='2.4GHz + 5.8GHz WiFi combination',
                applications=['Dual-band routers', 'High-performance networking']
            ),
            'wifi_tri': FrequencyBand(
                name='WiFi Tri Band',
                band_type=BandType.WIFI_ISM,
                frequencies_mhz=(2437, 5500, 5945),
                description='2.4GHz + 5GHz + 6GHz WiFi',
                applications=['Tri-band WiFi systems', 'Next-gen networking']
            ),

            # Cellular Bands
            'cellular_lte': FrequencyBand(
                name='LTE Tri Band',
                band_type=BandType.CELLULAR,
                frequencies_mhz=(700, 1800, 2600),
                description='Common LTE frequency bands',
                applications=['4G cellular', 'Mobile broadband']
            ),
            'cellular_5g_low': FrequencyBand(
                name='5G Low Band',
                band_type=BandType.CELLULAR,
                frequencies_mhz=(600, 3600, 4200),
                description='Sub-6GHz 5G with C-band focus',
                applications=['5G NR', 'Fixed wireless access']
            ),
            'cellular_gsm_multi': FrequencyBand(
                name='GSM Multi Band',
                band_type=BandType.CELLULAR,
                frequencies_mhz=(900, 1800, 1900),
                description='Global GSM bands (GSM-900, DCS-1800, PCS-1900)',
                applications=['Global cellular coverage', 'GSM devices']
            ),

            # Satellite/GPS Bands
            'gps_gnss': FrequencyBand(
                name='GPS/GNSS',
                band_type=BandType.SATELLITE,
                frequencies_mhz=(1575.42, 1227.6, 1176.45),
                description='L1/L2/L5 GNSS frequencies',
                applications=['GPS navigation', 'Precision timing']
            ),
            'satellite_weather': FrequencyBand(
                name='Weather Satellite',
                band_type=BandType.SATELLITE,
                frequencies_mhz=(137, 400, 1680),
                description='NOAA/GOES satellite frequencies',
                applications=['Weather monitoring', 'Earth observation']
            ),
        }

    @staticmethod
    def get_bands_by_type(band_type: BandType) -> List[FrequencyBand]:
        """Get all bands of a specific type."""
        all_bands = BandPresets.get_all_bands()
        return [band for band in all_bands.values() if band.band_type == band_type]

    @staticmethod
    def create_custom_band(name: str, freq1: float, freq2: float, freq3: float,
                          description: str = "") -> FrequencyBand:
        """Create a custom frequency band."""
        try:
            # Validate frequencies
            for freq in [freq1, freq2, freq3]:
                if not (1 <= freq <= 10000):  # Reasonable frequency range 1MHz to 10GHz
                    raise ValueError(f"Frequency {freq} MHz out of valid range (1-10000 MHz)")

            if description == "":
                description = f"Custom tri-band: {freq1}/{freq2}/{freq3} MHz"

            return FrequencyBand(
                name=name,
                band_type=BandType.CUSTOM,
                frequencies_mhz=(freq1, freq2, freq3),
                description=description,
                applications=['Custom application']
            )

        except Exception as e:
            logger.error(f"Custom band creation error: {str(e)}")
            raise ValueError(f"Invalid custom band parameters: {str(e)}")

    @staticmethod
    def get_recommended_bands() -> List[str]:
        """Get list of recommended band preset keys."""
        return [
            'tv_vhf_low',
            'tv_vhf_high',
            'tv_uhf',
            'wifi_dual',
            'cellular_lte',
            'gps_gnss'
        ]

class BandAnalysis:
    """Analyze frequency band characteristics for antenna design."""

    @staticmethod
    def analyze_band_compatibility(band: FrequencyBand) -> Dict[str, any]:
        """Analyze band characteristics for antenna design feasibility."""
        analysis = {
            'feasibility_score': 0.0,  # 0-10 scale
            'design_complexity': 'medium',
            'size_constraints': 'normal',
            'expected_performance': 'good',
            'recommended_antenna_types': [],
            'warnings': [],
            'optimization_notes': []
        }

        f1, f2, f3 = band.frequencies
        freq_range = max(f1, f2, f3) / min(f for f in [f1, f2, f3] if f > 0)

        # Analyze frequency separation
        if freq_range < 2:  # Close frequencies
            analysis['feasibility_score'] = 8.0
            analysis['design_complexity'] = 'low'
            analysis['recommended_antenna_types'] = ['dipole', 'monopole']
            analysis['optimization_notes'].append("Close frequencies allow simple broadband designs")

        elif 2 <= freq_range <= 5:  # Moderate separation
            analysis['feasibility_score'] = 9.0
            analysis['design_complexity'] = 'medium'
            analysis['recommended_antenna_types'] = ['dipole', 'patch', 'coil']
            analysis['optimization_notes'].append("Multi-element designs needed for good performance")

        else:  # Large frequency separation
            analysis['feasibility_score'] = 6.0  # Challenging
            analysis['design_complexity'] = 'high'
            analysis['recommended_antenna_types'] = ['coil', 'patch', 'compound']
            analysis['optimization_notes'].append("High frequency ratio requires advanced compensation techniques")
            analysis['warnings'].append("Large frequency separation may limit achievable bandwidth")

        # Size analysis
        size_est = band.get_size_estimate()
        substrate_size = 4.0 * 2.0  # 4x2 inch substrate
        electrical_size = size_est['quarter_wave_inch']

        if electrical_size > substrate_size * 1.5:
            analysis['size_constraints'] = 'tight'
            analysis['warnings'].append("Antenna may require loading for size reduction")
            analysis['feasibility_score'] -= 0.2  # Slightly reduced feasibility due to size constraints

        elif electrical_size < substrate_size * 0.1:
            analysis['size_constraints'] = 'loose'
            analysis['optimization_notes'].append("Size constraints not limiting factor")

        # Band-specific analysis
        if band.band_type == BandType.TV_BROADCAST:
            analysis['optimization_notes'].append("TV bands often require omnidirectional patterns")
            analysis['recommended_antenna_types'].insert(0, 'broadband')

        elif band.band_type == BandType.WIFI_ISM:
            analysis['optimization_notes'].append("Consider interference from other ISM devices")
            analysis['recommended_antenna_types'].append('directional')

        elif band.band_type == BandType.SATELLITE:
            analysis['optimization_notes'].append("Satellite antennas often require hemispherical patterns")
            analysis['recommended_antenna_types'] = ['helical', 'patch']
            if any(f < 1000 for f in band.frequencies):
                analysis['warnings'].append("Very low frequencies may be challenging in small form factor")

        return analysis

    @staticmethod
    def suggest_alternatives(band: FrequencyBand) -> List[Tuple[str, str]]:
        """Suggest alternative frequency bands based on similarity."""
        alternatives = []

        # For TV bands, suggest cellular/WiFi equivalents
        if band.band_type == BandType.TV_BROADCAST:
            alternatives.extend([
                ('cellular_lte', 'Similar frequency range to VHF/UHF'),
                ('wifi_2g_extend', 'Nearby frequency range with different applications')
            ])

        # For WiFi, suggest cellular alternatives
        elif band.band_type == BandType.WIFI_ISM:
            alternatives.extend([
                ('cellular_5g_low', 'Modern cellular frequencies in similar range'),
            ])

        # For cellular, suggest WiFi alternatives
        elif band.band_type == BandType.CELLULAR:
            alternatives.extend([
                ('wifi_tri', 'Wireless communication in different frequency ranges'),
            ])

        return alternatives

class FrequencyValidator:
    """Validate frequency selections for tri-band design."""

    @staticmethod
    def validate_triplet(freq1: float, freq2: float, freq3: float) -> Dict[str, any]:
        """Validate a triplet of frequencies for tri-band antenna design."""
        validation = {
            'is_valid': True,
            'frequency_order': True,
            'frequency_spacing': 'optimal',
            'warnings': [],
            'design_recommendations': []
        }

        try:
            frequencies = [freq1, freq2, freq3]

            # Check valid frequency range
            for freq in frequencies:
                if not (1 <= freq <= 10000):
                    validation['is_valid'] = False
                    validation['warnings'].append(f"Frequency {freq} MHz out of range (1-10000 MHz)")
                    return validation

            # Check frequency order (should be ascending for optimization)
            if sorted(frequencies) != frequencies:
                validation['frequency_order'] = False
                validation['warnings'].append("Frequencies not in ascending order")
                validation['design_recommendations'].append("Sort frequencies in ascending order for better optimization")

            # Analyze frequency spacing
            ratios = []
            for i in range(len(frequencies)-1):
                if frequencies[i] > 0:
                    ratio = frequencies[i+1] / frequencies[i]
                    ratios.append(ratio)

            avg_ratio = sum(ratios) / len(ratios) if ratios else 1.0

            if avg_ratio <= 2:
                validation['frequency_spacing'] = 'close'
                validation['design_recommendations'].append("Close frequencies suitable for broadband design")

            elif 2 < avg_ratio <= 5:
                validation['frequency_spacing'] = 'optimal'
                validation['design_recommendations'].append("Good frequency separation for tri-band operation")

            else:
                validation['frequency_spacing'] = 'wide'
                validation['warnings'].append("Large frequency separation may reduce performance")

        except Exception as e:
            validation['is_valid'] = False
            validation['warnings'].append(f"Validation error: {str(e)}")

        return validation

logger.info("Frequency band presets initialized with comprehensive band definitions")
