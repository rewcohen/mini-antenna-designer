"""Direct antenna design generator based on frequency selection."""

import numpy as np
from typing import Dict, List, Tuple, Optional
from loguru import logger

from core import NEC2Interface, compute_feed_requirements, AntennaAnalyzer
from design import AntennaDesign, AdvancedMeanderTrace
from wire_antennas import assess_meander_feasibility
from presets import FrequencyBand, BandAnalysis

class AntennaDesignGenerator:
    """Generate antenna designs directly based on frequency requirements."""

    def __init__(self, nec_interface: NEC2Interface, substrate_width: float = 4.0, substrate_height: float = 2.0):
        """Initialize design generator with substrate dimensions."""
        self.nec = nec_interface
        self.substrate_width = substrate_width
        self.substrate_height = substrate_height
        self.designer = AntennaDesign(substrate_width=substrate_width, substrate_height=substrate_height)
        self.advanced_meander = AdvancedMeanderTrace(substrate_width=substrate_width, substrate_height=substrate_height)
        logger.info(f"Antenna design generator initialized with advanced meander capability for {substrate_width}x{substrate_height} inch substrate")

    def generate_design(self, frequency_band: FrequencyBand, trace_width_inches: float = None, 
                       add_contact_pads: bool = False) -> Dict:
        """Generate antenna design for given frequency band.

        Args:
            frequency_band: Frequency band with tri-band frequencies
            trace_width_inches: Custom trace width in inches (optional)
            add_contact_pads: Whether to add contact pads for soldering

        Returns:
            dict: Complete design with geometry, metrics, and validation
        """
        try:
            f1, f2, f3 = frequency_band.frequencies
            logger.info(f"Generating design for {frequency_band.name}: {f1}/{f2}/{f3} MHz "
                       f"{'with contact pads' if add_contact_pads else 'without contact pads'}")

            # Analyze frequency relationships
            design_type = self._determine_design_type(f1, f2, f3, frequency_band)

            # Generate geometry based on frequency relationships
            geometry = self._generate_geometry_for_type(design_type, f1, f2, f3, trace_width_inches, add_contact_pads)

            # Validate fits substrate
            validation = self._validate_design(geometry)

            # Generate metrics (with NEC2 analysis)
            metrics = self._analyze_design(geometry, [f1, f2, f3])

            # Per-resonator connection points and feed/balun/impedance advice.
            resonators = getattr(self.advanced_meander, 'last_resonators', []) or []
            feed_advice = compute_feed_requirements(resonators)
            connection_points = [
                {'label': r['label'], 'freq_mhz': r['freq_mhz'],
                 'x_in': r['feed_x_in'], 'y_in': r['feed_y_in'],
                 'x_mm': round(r['feed_x_in'] * 25.4, 2), 'y_mm': round(r['feed_y_in'] * 25.4, 2)}
                for r in resonators
            ]
            # Is the meander actually a usable radiator for each band? If not (band
            # too low for this board), recommend hand-built copper-wire designs.
            feasibility = assess_meander_feasibility(
                resonators, self.advanced_meander.substrate_width,
                self.advanced_meander.substrate_height)

            # Predicted azimuth radiation pattern (for review/overlay). Per resonator
            # at its own band, plus a primary pattern at the lowest frequency.
            primary_freq = min((f for f in [f1, f2, f3] if f > 0), default=f1)
            radiation_pattern = AntennaAnalyzer.radiation_pattern(geometry, primary_freq)
            band_patterns = [
                {'label': r['label'], 'freq_mhz': r['freq_mhz'],
                 **AntennaAnalyzer.radiation_pattern(r['geometry'], r['freq_mhz'])}
                for r in resonators
            ]

            design_result = {
                'geometry': geometry,
                'design_type': design_type,
                'freq1_mhz': f1,
                'freq2_mhz': f2,
                'freq3_mhz': f3,
                'band_name': frequency_band.name,
                'validation': validation,
                'metrics': metrics,
                'connection_points': connection_points,
                'feed_advice': feed_advice,
                'feasibility': feasibility,
                'radiation_pattern': radiation_pattern,
                'band_patterns': band_patterns,
                'success': validation['within_bounds'] or not any(
                    issue.startswith('X extent') or issue.startswith('Y extent')
                    for issue in validation.get('bound_violations', [])
                ),
                'contact_pads_added': add_contact_pads
            }

            logger.info(f"Design generation completed: {design_type} with {'success' if design_result['success'] else 'issues'}")

            return design_result

        except Exception as e:
            logger.error(f"Design generation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'geometry': "",
                'design_type': 'error',
                'contact_pads_added': add_contact_pads
            }

    def _determine_design_type(self, f1: float, f2: float, f3: float,
                              frequency_band: FrequencyBand) -> str:
        """Determine optimal antenna type based on frequency relationships."""
        ratios = []
        if f1 > 0:
            if f2 > 0:
                ratios.append(f2/f1)
            if f3 > 0:
                ratios.append(f3/f1)
                if f2 > 0:
                    ratios.append(f3/f2)

        avg_ratio = sum(ratios)/len(ratios) if ratios else 1.0

        # Debug logging for design selection
        logger.info(f"Design type analysis for {frequency_band.name}:")
        logger.info(f"  Frequencies: {f1}/{f2}/{f3} MHz")
        logger.info(f"  Frequency ratios: {ratios}")
        logger.info(f"  Average ratio: {avg_ratio:.3f}")
        logger.info(f"  Band type: {frequency_band.band_type.value}")

        # Check for special cases
        from presets import BandType
        if frequency_band.band_type == BandType.SATELLITE:
            logger.info(f"  Selected: planar_spiral (satellite band)")
            return 'planar_spiral'  # For GNSS/satellite
        # Removed TV_BROADCAST hardcoding - let it use ratio-based selection for compact designs

        # Determine based on frequency separation (average of pairwise ratios).
        if avg_ratio < 1.5:  # Close frequencies
            logger.info(f"  Selected: meander_array_close (close frequencies, ratio < 1.5)")
            return 'meander_array_close'  # Closely spaced bands
        elif avg_ratio < 3.0:  # Medium separation
            logger.info(f"  Selected: meander_array_medium (medium separation, 1.5 <= ratio < 3.0)")
            return 'meander_array_medium'  # Moderately spaced bands
        else:  # Large separation
            logger.info(f"  Selected: meander_array_wide (large separation, ratio >= 3.0)")
            return 'meander_array_wide'  # Widely spaced bands

    def _generate_geometry_for_type(self, design_type: str, f1: float, f2: float, f3: float, 
                                   trace_width_inches: float = None, add_contact_pads: bool = False) -> str:
        """Generate NEC2 geometry for specific design type."""
        geometrics = []

        logger.info(f"Generating {design_type} geometry for frequencies {f1}/{f2}/{f3} MHz")

        if design_type == 'broadband_dipole':
            # Single broadband dipole arms tuned for center frequency
            center_freq = (f1 + f2 + f3) / 3
            if add_contact_pads:
                geom = self.designer.generate_dipole_with_pads(center_freq, length_ratio=1.0, 
                                                             use_meandering=True, add_contact_pads=True)
            else:
                geom = self.designer.generate_dipole(center_freq, length_ratio=1.0)
            geometrics.append(geom)

        elif design_type == 'dual_element':
            # Monopole + dipole combination
            if add_contact_pads:
                geom1 = self.designer.generate_monopole_with_pads(f1, add_contact_pads=True)
                geom2 = self.designer.generate_dipole_with_pads(f2, add_contact_pads=True)
            else:
                geom1 = self.designer.generate_monopole(f1)
                geom2 = self.designer.generate_dipole(f2)
            geometrics.extend([geom1, geom2])

        elif design_type == 'tri_compound_spiral':
            # Tri-element with spiral loading
            if add_contact_pads:
                geom1 = self.designer.generate_monopole_with_pads(f1, add_contact_pads=True)
                geom2 = self.designer.generate_dipole_with_pads(f2, add_contact_pads=True)
                geom3 = self.designer.generate_spiral_coil_with_pads(f3, turns=3, add_contact_pads=True)
            else:
                geom1 = self.designer.generate_monopole(f1)
                geom2 = self.designer.generate_dipole(f2)
                geom3 = self.designer.generate_spiral_coil(f3, turns=3)
            geometrics.extend([geom1, geom2, geom3])

        elif design_type == 'planar_spiral':
            # Helical design for satellite applications
            if add_contact_pads:
                geom1 = self.designer.generate_spiral_coil_with_pads(f1, turns=5, spacing=0.005, add_contact_pads=True)
            else:
                geom1 = self.designer.generate_spiral_coil(f1, turns=5, spacing=0.005)
            geometrics.append(geom1)

        elif design_type == 'broadband_log':
            # Proper log-periodic antenna design for TV bands
            geometrics = self._generate_proper_log_periodic(f1, f2, f3)

        elif design_type == 'meander_array_close':
            # Advanced meander design for tri-band operation
            geometrics = self._generate_meander_array_close(f1, f2, f3, trace_width_inches)

        elif design_type == 'meander_array_medium':
            # Advanced meander design for dual-band operation
            geometrics = self._generate_meander_array_medium(f1, f2, f3, trace_width_inches)

        elif design_type == 'meander_array_wide':
            # Compound advanced meander design
            geometrics = self._generate_meander_array_wide(f1, f2, f3)

        else:
            # Default to tri-compound
            if add_contact_pads:
                geom = self.designer.generate_tri_band_geometry_with_pads(f1, f2, f3, add_contact_pads=True)
            else:
                geom = self.designer.generate_tri_band_geometry(f1, f2, f3)
            geometrics.append(geom)

        # Validate geometries before combining
        valid_geometries = []
        for i, geom in enumerate(geometrics):
            if geom and geom.strip():
                logger.debug(f"Geometry {i+1}: Valid, {len(geom.split())} lines")
                valid_geometries.append(geom)
            else:
                logger.warning(f"Geometry {i+1}: Empty or invalid")

        if not valid_geometries:
            logger.error("No valid geometries generated!")
            return ""

        # Combine all geometries
        combined = self._combine_geometries(valid_geometries)

        # Debug logging
        logger.info(f"Generated {design_type} geometry with {len(valid_geometries)} element(s), {len(combined)} total characters")

        return combined

    def _offset_geometry(self, geometry: str, x_offset: float, y_offset: float) -> str:
        """Apply offset to geometry coordinates."""
        lines = geometry.split('\n')
        modified_lines = []

        for line in lines:
            if not line.strip():
                continue

            parts = line.split()
            if len(parts) >= 8 and parts[0] == 'GW':
                # Offset wire coordinates
                parts[3] = str(float(parts[3]) + x_offset)  # x1
                parts[4] = str(float(parts[4]) + y_offset)  # y1
                parts[6] = str(float(parts[6]) + x_offset)  # x2
                parts[7] = str(float(parts[7]) + y_offset)  # y2

            modified_lines.append(' '.join(parts))

        return '\n'.join(modified_lines)

    def _combine_geometries(self, geometries: List[str]) -> str:
        """Combine multiple geometries with proper wire tag offsets."""
        combined = []
        tag_offset = 0
        total_wires = 0

        logger.debug(f"Combining {len(geometries)} geometries")

        for i, geom in enumerate(geometries):
            lines = geom.split('\n')
            geom_wires = 0
            
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if len(parts) > 1 and parts[0] in ['GW', 'SP']:
                        # Adjust wire tag to avoid conflicts
                        original_tag = int(float(parts[1]))
                        parts[1] = str(original_tag + tag_offset)
                        combined.append(' '.join(parts))
                        geom_wires += 1
                        total_wires += 1
                        logger.debug(f"Geometry {i+1}: Wire {original_tag} -> {parts[1]}")

            tag_offset += 100  # Conservative offset
            logger.debug(f"Geometry {i+1}: {geom_wires} wires processed")

        result = '\n'.join(combined)
        logger.info(f"Combined {total_wires} total wires from {len(geometries)} geometries")
        
        if not result.strip():
            logger.error("Combined geometry is empty!")
        else:
            logger.debug(f"Combined geometry preview: {result[:100]}...")

        return result

    def _validate_design(self, geometry: str) -> Dict:
        """Validate design fits substrate and manufacturing constraints."""
        from design import GeometryValidation
        from export import EtchingValidator

        # Substrate bounds check - use dynamic substrate dimensions
        substrate_check = GeometryValidation.check_bounds(geometry, self.substrate_width, self.substrate_height)

        # Manufacturing check
        manufacturing_check = EtchingValidator.validate_for_etching(geometry)

        # Calculate max_extent with proper error handling
        max_x = substrate_check.get('max_x', 0)
        max_y = substrate_check.get('max_y', 0)
        max_extent = max(max_x, max_y)

        # Calculate utilization percent if not provided
        utilization_percent = substrate_check.get('utilization_percent', 0)
        if utilization_percent == 0:
            # Estimate utilization based on bounds
            total_area = self.designer.substrate_width * self.designer.substrate_height
            used_area = (max_x * 2) * (max_y * 2)  # Assuming centered design
            utilization_percent = min((used_area / total_area) * 100, 100) if total_area > 0 else 0

        # Add max_extent to avoid KeyError
        validation_result = {
            'within_bounds': substrate_check['within_bounds'],
            'max_extent': max_extent,
            'max_extents': max_extent,
            'utilization_percent': utilization_percent,
            'bound_violations': substrate_check.get('warnings', []),
            'warnings': substrate_check.get('warnings', []) + manufacturing_check.get('warnings', []),
            'manufacturable': manufacturing_check.get('etching_ready', False),
            'complexity_score': manufacturing_check.get('complexity_score', 0),
            'estimated_etch_time': _estimate_etch_time(manufacturing_check.get('element_count', len(geometry.split('\n')) if geometry else 0))
        }

        logger.debug(f"Validation result: max_extent={max_extent}, within_bounds={validation_result['within_bounds']}")
        return validation_result

    def _analyze_design(self, geometry: str, frequencies: List[float]) -> Dict:
        """Analyze design with NEC2 simulation."""
        try:
            # Validate inputs
            if not geometry or not geometry.strip():
                logger.warning("Empty geometry provided for analysis")
                return self._get_fallback_metrics(frequencies, "Empty geometry")

            if not frequencies or len(frequencies) == 0:
                logger.warning("No frequencies provided for analysis")
                return self._get_fallback_metrics(frequencies, "No frequencies")

            # Run NEC2 simulation
            try:
                simulation_results = self.nec.run_simulation(geometry, frequencies)
            except Exception as nec_error:
                logger.warning(f"NEC2 simulation failed: {str(nec_error)}")
                return self._get_fallback_metrics(frequencies, f"NEC2 error: {str(nec_error)}")

            if not simulation_results:
                logger.warning("No simulation results returned")
                return self._get_fallback_metrics(frequencies, "No simulation results")

            # Extract key metrics
            metrics = {}
            vswr_values = []
            gain_values = []
            impedance_values = []

            for freq, result in simulation_results.items():
                # Handle error cases in simulation results
                if isinstance(result, dict) and 'error' in result:
                    logger.warning(f"Simulation error for {freq} MHz: {result['error']}")
                    metrics[f'freq_{freq}_mhz'] = {
                        'vswr': 'Error',
                        'gain_dbi': 'Error',
                        'impedance': 'Error'
                    }
                    continue

                # Extract values with proper error handling
                vswr = result.get('vswr', 'N/A')
                gain = result.get('gain_dbi', 'N/A')
                impedance = result.get('impedance_ohms', 'N/A')

                # Format impedance for display
                if isinstance(impedance, complex):
                    impedance_str = f"{impedance.real:.1f}{'+' if impedance.imag >= 0 else ''}{impedance.imag:.1f}j Ω"
                elif isinstance(impedance, (int, float)):
                    impedance_str = f"{impedance:.1f} Ω"
                else:
                    impedance_str = str(impedance)

                metrics[f'freq_{freq}_mhz'] = {
                    'vswr': vswr,
                    'gain_dbi': gain,
                    'impedance': impedance_str
                }

                # Collect numeric values for averaging
                if isinstance(vswr, (int, float)):
                    vswr_values.append(vswr)
                if isinstance(gain, (int, float)):
                    gain_values.append(gain)

            # Aggregate metrics with proper error handling
            avg_vswr = sum(vswr_values)/len(vswr_values) if vswr_values else 'N/A'
            avg_gain = sum(gain_values)/len(gain_values) if gain_values else 'N/A'

            # Calculate bandwidth safely
            try:
                freq_range = f"{min(frequencies)} - {max(frequencies)}"
                bandwidth = max(frequencies)/min(frequencies) if all(f > 0 for f in frequencies) else 'N/A'
            except (ValueError, ZeroDivisionError):
                freq_range = "Unknown"
                bandwidth = 'N/A'

            metrics['summary'] = {
                'avg_vswr': avg_vswr,
                'avg_gain_dbi': avg_gain,
                'frequency_range_mhz': freq_range,
                'bandwidth_octaves': bandwidth
            }

            return metrics

        except Exception as e:
            logger.error(f"Design analysis failed: {str(e)}")
            return self._get_fallback_metrics(frequencies, f"Analysis error: {str(e)}")

    def _get_fallback_metrics(self, frequencies: List[float], error_reason: str) -> Dict:
        """Get fallback metrics when analysis fails."""
        try:
            # Generate reasonable mock data based on frequency ranges
            if not frequencies:
                freq_range = "Unknown"
                bandwidth = 'N/A'
            else:
                freq_range = f"{min(frequencies)} - {max(frequencies)}"
                bandwidth = max(frequencies)/min(frequencies) if all(f > 0 for f in frequencies) else 'N/A'

            return {
                'freq_estimated_mhz': {'vswr': '~2.5', 'gain_dbi': '~1.5 dBi', 'impedance': '50+5j Ω'},
                'summary': {
                    'avg_vswr': '~2.5',
                    'avg_gain_dbi': '~1.5 dBi',
                    'frequency_range_mhz': freq_range,
                    'bandwidth_octaves': bandwidth
                },
                'note': f'Metrics estimated - {error_reason}'
            }
        except Exception as e:
            logger.error(f"Fallback metrics generation failed: {str(e)}")
            return {
                'summary': {
                    'avg_vswr': 'Error',
                    'avg_gain_dbi': 'Error',
                    'frequency_range_mhz': 'Error',
                    'bandwidth_octaves': 'Error'
                },
                'note': f'Metrics unavailable - {str(e)}'
            }

    def _generate_proper_log_periodic(self, f1: float, f2: float, f3: float) -> List[str]:
        """Generate proper log-periodic antenna with mathematical scaling."""
        try:
            logger.info(f"Generating proper log-periodic antenna for {f1}/{f2}/{f3} MHz")
            
            # Sort frequencies for proper log-periodic design
            frequencies = sorted([f1, f2, f3])
            
            # Log-periodic design parameters
            tau = 0.85  # Scaling factor (typically 0.7-0.9)
            sigma = 0.08  # Spacing factor (typically 0.05-0.15)
            alpha = 30  # Half-angle of antenna apex (degrees)
            
            logger.info(f"Log-periodic parameters: τ={tau}, σ={sigma}, α={alpha}°")
            
            # Calculate longest element (lowest frequency)
            c = 299792458  # Speed of light in m/s
            freq_low = frequencies[0] * 1e6  # Convert to Hz
            wavelength_low = c / freq_low * 39.3701  # Convert to inches
            
            # Calculate element lengths using log-periodic scaling
            elements = []
            total_length = 0
            
            for i, freq in enumerate(frequencies):
                # Element length for this frequency
                wavelength = c / (freq * 1e6) * 39.3701  # inches
                element_length = wavelength / 2 * 0.95  # Half-wave dipole, slightly shortened
                
                # Apply log-periodic scaling
                scaled_length = element_length * (tau ** i)
                
                # Calculate position along boom
                position = i * (scaled_length * sigma) / (2 * np.sin(np.radians(alpha)))
                
                elements.append({
                    'frequency': freq,
                    'length': scaled_length,
                    'position': position,
                    'index': i
                })
                
                total_length += scaled_length
                logger.info(f"Element {i+1}: {freq} MHz, length={scaled_length:.3f}\", position={position:.3f}\"")
            
            # Generate geometry for each element
            geometries = []
            
            for i, element in enumerate(elements):
                # Generate dipole for this element with meandering if needed
                geom = self.designer.generate_dipole(
                    element['frequency'], 
                    length_ratio=0.95,
                    use_meandering=True
                )
                
                # Position element along the boom
                x_offset = element['position']
                y_offset = 0  # All elements on same horizontal line
                
                # Apply offset
                positioned_geom = self._offset_geometry(geom, x_offset, y_offset)
                geometries.append(positioned_geom)
                
                logger.debug(f"Positioned element {i+1} at x={x_offset:.3f}\", {len(positioned_geom)} chars")
            
            # Add feed point and connection geometry
            feed_geometry = self._add_feed_point_geometry()
            if feed_geometry:
                geometries.append(feed_geometry)
            
            # Add boom/structure elements
            boom_geometry = self._add_boom_structure(elements)
            if boom_geometry:
                geometries.append(boom_geometry)
            
            logger.info(f"Generated log-periodic antenna: {len(geometries)} total elements")
            return geometries
            
        except Exception as e:
            logger.error(f"Log-periodic generation failed: {str(e)}")
            # Fallback to simple dipole generation
            return [self.designer.generate_dipole(f1, use_meandering=True)]
    
    def _add_feed_point_geometry(self) -> str:
        """Add feed point connection pads for PCB manufacturing."""
        try:
            geometry = []
            gw_tag = 1000  # High tag number to avoid conflicts
            
            # Feed point at origin
            pad_size = 0.05  # 50 mil pads for soldering
            trace_width = self.designer.min_feature_size * 2
            
            # Center feed point pad
            geometry.append(f"GW {gw_tag} 1 {-pad_size:.4f} 0 0 {pad_size:.4f} 0 0 {trace_width:.4f}")
            gw_tag += 1
            
            # Connection traces to feed points
            geometry.append(f"GW {gw_tag} 1 {pad_size:.4f} 0 0 {0.2:.4f} 0 0 {trace_width:.4f}")  # Right feed
            gw_tag += 1
            geometry.append(f"GW {gw_tag} 1 {-pad_size:.4f} 0 0 {-0.2:.4f} 0 0 {trace_width:.4f}")  # Left feed
            
            logger.debug("Added feed point geometry")
            return "\n".join(geometry)
            
        except Exception as e:
            logger.warning(f"Failed to add feed point geometry: {str(e)}")
            return ""
    
    def _add_boom_structure(self, elements: List[dict]) -> str:
        """Add supporting boom structure for log-periodic antenna."""
        try:
            geometry = []
            gw_tag = 2000  # High tag number to avoid conflicts
            
            trace_width = self.designer.min_feature_size * 1.5
            
            # Calculate boom span
            max_position = max(elem['position'] for elem in elements) if elements else 1.0
            
            # Main boom element
            geometry.append(f"GW {gw_tag} 1 0 0 0 {max_position + 0.2:.4f} 0 0 {trace_width:.4f}")
            gw_tag += 1
            
            # Support elements at each position
            for elem in elements:
                x_pos = elem['position']
                # Vertical support
                geometry.append(f"GW {gw_tag} 1 {x_pos:.4f} 0 0 {x_pos:.4f} 0.1 0 {trace_width:.4f}")
                gw_tag += 1
            
            logger.debug(f"Added boom structure: {len(geometry)} support elements")
            return "\n".join(geometry)
            
        except Exception as e:
            logger.warning(f"Failed to add boom structure: {str(e)}")
            return ""

    def _generate_meander_array_close(self, f1: float, f2: float, f3: float, trace_width_inches: float = None) -> List[str]:
        """Generate a separate meandered resonator for each of the (closely spaced) bands."""
        try:
            logger.info(f"Generating tri-band design (separate resonators) for {f1}/{f2}/{f3} MHz")
            frequencies = [f for f in [f1, f2, f3] if f > 0]
            if not frequencies:
                logger.warning("No valid frequencies for tri-band meander")
                return [self.designer.generate_dipole(f1, use_meandering=True)]

            constraints = {
                'trace_width': trace_width_inches if trace_width_inches is not None else 0.008,
                'bend_radius': 0.0008,  # 0.8mm for good Q-factor
                'coupling_factor': 0.88,
            }
            geometry = self.advanced_meander.generate_separate_band_resonators(frequencies, constraints)
            if geometry:
                logger.info(f"Tri-band: generated {len(frequencies)} separate resonators")
                return [geometry]
            return [self.designer.generate_dipole(f1, use_meandering=True)]

        except Exception as e:
            logger.error(f"Advanced meander tri-band generation failed: {str(e)}")
            return [self.designer.generate_dipole(f1, use_meandering=True)]

    def _generate_meander_array_medium(self, f1: float, f2: float, f3: float, trace_width_inches: float = None) -> List[str]:
        """Generate a separate meandered resonator for each (moderately spaced) band."""
        try:
            logger.info(f"Generating dual-band design (separate resonators) for {f1}/{f2}/{f3} MHz")
            frequencies = [f for f in [f1, f2, f3] if f > 0]
            if not frequencies:
                logger.warning("No valid frequencies for dual-band meander")
                return [self.designer.generate_dipole(f1, use_meandering=True)]

            constraints = {
                'trace_width': trace_width_inches if trace_width_inches is not None else 0.008,
                'bend_radius': 0.001,  # 1mm for balanced performance
                'coupling_factor': 0.90,
            }
            geometry = self.advanced_meander.generate_separate_band_resonators(frequencies, constraints)
            if geometry:
                logger.info(f"Dual-band: generated {len(frequencies)} separate resonators")
                return [geometry]
            return [self.designer.generate_dipole(f1, use_meandering=True)]

        except Exception as e:
            logger.error(f"Advanced meander dual-band generation failed: {str(e)}")
            return [self.designer.generate_dipole(f1, use_meandering=True)]
    
    def _generate_meander_array_wide(self, f1: float, f2: float, f3: float, trace_width_inches: float = None) -> List[str]:
        """Generate a separate meandered resonator for each widely separated band.

        Each band gets its own element in its own substrate stripe, sized to its
        half-wave - the right approach when the bands differ greatly in wavelength.
        """
        try:
            logger.info(f"Generating compound design (separate resonators) for {f1}/{f2}/{f3} MHz" +
                       (f" with custom trace width {trace_width_inches*1000:.1f} mil" if trace_width_inches else ""))
            frequencies = [f for f in [f1, f2, f3] if f > 0]
            if not frequencies:
                logger.warning("No valid frequencies for compound meander")
                return [self.designer.generate_dipole(f1, use_meandering=True, trace_width_inches=trace_width_inches)]

            constraints = {
                'trace_width': trace_width_inches if trace_width_inches is not None else 0.008,
                'bend_radius': 0.001,
                'coupling_factor': 0.90,
            }
            geometry = self.advanced_meander.generate_separate_band_resonators(frequencies, constraints)
            if geometry:
                logger.info(f"Compound: generated {len(frequencies)} separate resonators")
                return [geometry]
            return [self.designer.generate_dipole(f1, use_meandering=True, trace_width_inches=trace_width_inches)]

        except Exception as e:
            logger.error(f"Advanced meander compound generation failed: {str(e)}")
            return [self.designer.generate_dipole(f1, use_meandering=True, trace_width_inches=trace_width_inches)]


def _estimate_etch_time(element_count: int) -> str:
    """Estimate laser etching time based on complexity."""
    if element_count < 10:
        return '~2-3 minutes'
    elif element_count < 50:
        return '~5-8 minutes'
    elif element_count < 200:
        return '~15-25 minutes'
    else:
        return '~30+ minutes'
