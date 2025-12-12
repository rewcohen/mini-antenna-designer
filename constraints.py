"""Substrate and manufacturing constraints for antenna design."""
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
from loguru import logger

class SubstrateConstraints:
    """Define physical constraints for 2x4 inch copper substrate."""

    def __init__(self, width: float = 4.0, height: float = 2.0):
        """Initialize with substrate dimensions in inches."""
        self.width = width
        self.height = height
        self.area = width * height

        # Manufacturing tolerances (inches)
        self.edge_clearance = 0.050  # 50 mil clearance from edges
        self.min_feature_size = 0.005  # 5 mil minimum trace width
        self.min_spacing = 0.008  # 8 mil minimum spacing between traces

        # Electrical properties (assuming typical PCB substrate)
        self.dielectric_constant = 4.3  # FR-4 substrate
        self.tangent_loss = 0.025  # Loss tangent
        self.copper_thickness = 0.0014  # 1 oz copper (1.4 mil)

        # Laser etching limitations
        self.spot_size_min = 0.003  # Minimum laser spot size
        self.etch_resolution = 0.005  # Best achievable resolution

        logger.info(f"Substrate constraints initialized: {width}x{height} inches")

    def get_usable_area(self) -> Tuple[float, float]:
        """Get usable area after edge clearance."""
        usable_width = self.width - 2 * self.edge_clearance
        usable_height = self.height - 2 * self.edge_clearance
        return usable_width, usable_height

    def is_point_valid(self, x: float, y: float) -> bool:
        """Check if a point (x,y) is within usable substrate area."""
        usable_width, usable_height = self.get_usable_area()
        return (self.edge_clearance <= x <= self.width - self.edge_clearance and
                self.edge_clearance <= y <= self.height - self.edge_clearance)

    def check_geometry_bounds(self, geometry: str) -> Dict[str, Any]:
        """Validate geometry against substrate constraints."""
        validation = {
            'within_bounds': True,
            'max_extent': {'x': 0.0, 'y': 0.0},
            'utilization_percent': 0.0,
            'violations': [],
            'warnings': []
        }

        try:
            # Parse geometry to extract coordinates
            lines = geometry.split('\n')
            coords = []

            for line in lines:
                parts = line.split()
                if len(parts) >= 8 and parts[0] == 'GW':
                    x1, y1 = float(parts[3]), float(parts[4])
                    x2, y2 = float(parts[6]), float(parts[7])
                    coords.extend([(x1, y1), (x2, y2)])
                elif len(parts) >= 4 and parts[0] == 'SP':
                    # Handle surface patches
                    i = 3
                    while i < len(parts) - 2:
                        x, y = float(parts[i]), float(parts[i+1])
                        coords.append((x, y))
                        i += 3

            if coords:
                x_coords = [c[0] for c in coords]
                y_coords = [c[1] for c in coords]

                max_x = max(abs(min(x_coords)), abs(max(x_coords)))
                max_y = max(abs(min(y_coords)), abs(max(y_coords)))

                validation['max_extent'] = {'x': max_x, 'y': max_y}

                # Check bounds - coordinates go from -width/2 to +width/2 around origin (0,0)
                if max_x > self.width / 2:
                    validation['within_bounds'] = False
                    validation['violations'].append(f"X extent {max_x:.3f} exceeds substrate width {self.width/2:.3f}")

                if max_y > self.height / 2:
                    validation['within_bounds'] = False
                    validation['violations'].append(f"Y extent {max_y:.3f} exceeds substrate height {self.height/2:.3f}")

                # Calculate utilization
                used_area_estimate = len(coords) * 0.01  # Rough estimate
                validation['utilization_percent'] = min(used_area_estimate / self.area * 100, 100.0)

                # Warnings for high utilization
                if validation['utilization_percent'] > 80:
                    validation['warnings'].append("High substrate utilization may reduce etching quality")

        except Exception as e:
            validation['violations'].append(f"Geometry parsing error: {str(e)}")

        return validation

class ManufacturingRules:
    """Define laser etching manufacturability rules."""

    @staticmethod
    def check_trace_width(width: float) -> Dict[str, Any]:
        """Check if trace width is manufacturable."""
        min_width = 0.005  # 5 mil
        optimal_width = 0.010  # 10 mil
        max_width = 0.100  # 100 mil (unnecessarily wide)

        result = {
            'is_manufacturable': True,
            'quality_rating': 'good',
            'recommendations': [],
            'warnings': []
        }

        if width < min_width:
            result['is_manufacturable'] = False
            result['warnings'].append(f"Trace width {width*1000:.1f} mil below minimum {min_width*1000:.1f} mil")
            result['recommendations'].append("Increase trace width for reliability")

        elif width < optimal_width:
            result['quality_rating'] = 'acceptable'
            result['warnings'].append(f"Trace width {width*1000:.1f} mil is narrow, etching may be challenging")

        elif width > max_width:
            result['quality_rating'] = 'acceptable'
            result['warnings'].append(f"Trace width {width*1000:.1f} mil is very wide, consider reducing")

        return result

    @staticmethod
    def check_spacing(spacing: float) -> Dict[str, Any]:
        """Check if trace spacing meets manufacturing requirements."""
        min_spacing = 0.008  # 8 mil for laser etching
        recommended_spacing = 0.015  # 15 mil for reliability

        result = {
            'is_manufacturable': True,
            'signal_integrity': 'good',
            'recommendations': []
        }

        if spacing < min_spacing:
            result['is_manufacturable'] = False
            result['signal_integrity'] = 'poor'
            result['recommendations'].append(f"Increase spacing to minimum {min_spacing*1000:.1f} mil for manufacturability")

        elif spacing < recommended_spacing:
            result['signal_integrity'] = 'acceptable'
            result['recommendations'].append(f"Consider increasing spacing to {recommended_spacing*1000:.1f} mil for better performance")

        return result

    @staticmethod
    def check_feature_complexity(geometry: str) -> Dict[str, Any]:
        """Analyze geometric complexity for manufacturability."""
        result = {
            'complexity_score': 0,
            'manufacturability_rating': 'excellent',
            'processing_time_estimate': 'fast',
            'recommended_settings': {},
            'warnings': []
        }

        try:
            # Count different element types
            lines = geometry.split('\n')
            wire_count = 0
            segment_count = 0

            for line in lines:
                parts = line.split()
                if len(parts) >= 8 and parts[0] == 'GW':
                    wire_count += 1
                    segments = int(float(parts[2]))
                    segment_count += segments

            # Assess complexity
            total_elements = wire_count

            if total_elements < 10:
                result['complexity_score'] = 1
                result['manufacturability_rating'] = 'excellent'
                result['processing_time_estimate'] = 'fast'
                result['recommended_settings'] = {'power': 'medium', 'speed': 'fast'}

            elif total_elements < 50:
                result['complexity_score'] = 2
                result['manufacturability_rating'] = 'good'
                result['processing_time_estimate'] = 'medium'
                result['recommended_settings'] = {'power': 'medium', 'speed': 'medium'}

            elif total_elements < 200:
                result['complexity_score'] = 3
                result['manufacturability_rating'] = 'acceptable'
                result['processing_time_estimate'] = 'slow'
                result['recommended_settings'] = {'power': 'high', 'speed': 'slow'}
                result['warnings'].append("High complexity may require multiple etching passes")

            else:
                result['complexity_score'] = 4
                result['manufacturability_rating'] = 'challenging'
                result['processing_time_estimate'] = 'very_slow'
                result['recommended_settings'] = {'power': 'high', 'speed': 'very_slow'}
                result['warnings'].append("Very high complexity - consider simplifying design")

            result['element_count'] = total_elements
            result['segment_count'] = segment_count

        except Exception as e:
            result['warnings'].append(f"Complexity analysis error: {str(e)}")

        return result

class ElectricalConstraints:
    """Electrical design constraints and validation."""

    @staticmethod
    def check_impedance_matching(impedance_ohms: complex, target: float = 50.0) -> Dict[str, Any]:
        """Validate impedance matching."""
        result = {
            'is_matched': False,
            'return_loss_db': 0.0,
            'vswr': 1.0,
            'reflection_coefficient': 0.0,
            'assessment': 'excellent'
        }

        try:
            real_part = impedance_ohms.real
            imag_part = impedance_ohms.imag

            # Calculate reflection coefficient
            gamma = (impedance_ohms - target) / (impedance_ohms + target)
            gamma_mag = abs(gamma)

            result['reflection_coefficient'] = gamma_mag
            result['vswr'] = (1 + gamma_mag) / (1 - gamma_mag)
            result['return_loss_db'] = -20 * np.log10(gamma_mag) if gamma_mag > 0 else float('inf')

            # Assess matching quality
            if gamma_mag < 0.1:  # |Γ| < 0.1 (-20dB return loss)
                result['is_matched'] = True
                result['assessment'] = 'excellent'
            elif gamma_mag < 0.22:  # |Γ| < 0.22 (-13dB return loss)
                result['is_matched'] = True
                result['assessment'] = 'good'
            elif gamma_mag < 0.33:  # |Γ| < 0.33 (-9.5dB return loss)
                result['is_matched'] = False
                result['assessment'] = 'acceptable'
            else:
                result['is_matched'] = False
                result['assessment'] = 'poor'

        except Exception as e:
            result['assessment'] = f"error: {str(e)}"

        return result

    @staticmethod
    def check_efficiency_requirements(vswr_values: List[float]) -> Dict[str, Any]:
        """Evaluate tri-band efficiency based on VSWR values."""
        result = {
            'bands_met': 0,
            'efficiency_estimate': 0.0,
            'average_performance': 'poor',
            'band_ratings': []
        }

        target_vswr = 3.0  # VSWR < 3:1 acceptable
        efficiency_factors = []  # Rough efficiency estimates

        for i, vswr in enumerate(vswr_values):
            band_rating = {
                'band': f'B{i+1}',
                'vswr': vswr,
                'passes': vswr < target_vswr,
                'efficiency_percent': 0.0
            }

            # Estimate efficiency from VSWR
            if vswr < 1.5:
                band_rating['passes'] = True
                band_rating['efficiency_percent'] = 95.0
            elif vswr < 2.0:
                band_rating['passes'] = True
                band_rating['efficiency_percent'] = 90.0
            elif vswr < 3.0:
                band_rating['passes'] = True
                band_rating['efficiency_percent'] = 80.0
            elif vswr < 5.0:
                band_rating['passes'] = False
                band_rating['efficiency_percent'] = 65.0
            else:
                band_rating['passes'] = False
                band_rating['efficiency_percent'] = 40.0

            result['band_ratings'].append(band_rating)
            efficiency_factors.append(band_rating['efficiency_percent'])

        result['bands_met'] = sum(1 for r in result['band_ratings'] if r['passes'])
        result['efficiency_estimate'] = sum(efficiency_factors) / len(efficiency_factors) if efficiency_factors else 0.0

        # Overall assessment
        if result['bands_met'] == len(vswr_values):
            if result['efficiency_estimate'] > 85:
                result['average_performance'] = 'excellent'
            elif result['efficiency_estimate'] > 75:
                result['average_performance'] = 'good'
            else:
                result['average_performance'] = 'acceptable'
        else:
            result['average_performance'] = 'poor'

        return result

class MaterialProperties:
    """Define material properties for copper and substrate."""

    # Copper properties (1 oz copper clad)
    COPPER_CONDUCTIVITY = 5.8e7  # S/m
    COPPER_THICKNESS_MILS = 1.4
    COPPER_SURFACE_RESISTANCE = 0.00005  # ohms per square

    # Common substrate materials
    SUBSTRATE_MATERIALS = {
        'fr4': {
            'dielectric_constant': 4.3,
            'loss_tangent': 0.025,
            'thermal_conductivity': 0.25,  # W/m·K
            'typical_thickness_mils': 62
        },
        'rogers_ro4003c': {
            'dielectric_constant': 3.55,
            'loss_tangent': 0.0027,
            'thermal_conductivity': 0.71,
            'typical_thickness_mils': 32
        },
        'ceramic': {
            'dielectric_constant': 9.8,
            'loss_tangent': 0.0001,
            'thermal_conductivity': 2.0,
            'typical_thickness_mils': 25
        }
    }

    @staticmethod
    def recommend_substrate(frequency_range: Tuple[float, float]) -> Dict[str, Any]:
        """Recommend substrate material based on frequency requirements."""
        f_min, f_max = frequency_range

        recommendation = {
            'recommended_material': 'fr4',
            'reasoning': '',
            'alternatives': []
        }

        if f_max > 3000:  # Above 3 GHz
            recommendation['recommended_material'] = 'rogers_ro4003c'
            recommendation['reasoning'] = 'Low-loss material required for high frequency performance'
            recommendation['alternatives'] = ['ceramic']

        elif f_max > 1000:  # Above 1 GHz
            if f_min < 500:  # Wide bandwidth
                recommendation['recommended_material'] = 'fr4'
                recommendation['reasoning'] = 'Cost-effective with acceptable performance for wide bandwidth'
                recommendation['alternatives'] = ['rogers_ro4003c']
            else:
                recommendation['recommended_material'] = 'rogers_ro4003c'
                recommendation['reasoning'] = 'Better performance for 1-3 GHz applications'

        else:  # Below 1 GHz
            recommendation['recommended_material'] = 'fr4'
            recommendation['reasoning'] = 'Cost-effective standard substrate suitable for low frequencies'

        return recommendation

logger.info("Substrate and manufacturing constraints initialized")
