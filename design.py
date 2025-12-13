"""Antenna geometry generation for 2D planar designs."""
from typing import List, Tuple, Optional, Dict, Any
import numpy as np
import math
from shapely.geometry import LineString, Point, Polygon
from shapely.affinity import rotate, translate
from loguru import logger

class AntennaGeometryError(Exception):
    """Custom exception for geometry generation errors."""
    pass

class AntennaDesign:
    """Generate 2D planar antenna geometries with substrate constraints."""

    def __init__(self, substrate_width: float = 4.0, substrate_height: float = 2.0):
        """Initialize with 2x4 inch substrate constraints."""
        self.substrate_width = substrate_width  # inches
        self.substrate_height = substrate_height  # inches
        self.min_feature_size = 0.005  # 5 mil minimum trace width
        logger.info(f"Antenna design initialized for {substrate_width}x{substrate_height} inch substrate")

    def generate_dipole(self, frequency_mhz: float, length_ratio: float = 0.95, 
                        use_meandering: bool = True) -> str:
        """Generate dipole antenna geometry with optional meandering for space efficiency.

        Args:
            frequency_mhz: Operating frequency in MHz
            length_ratio: Ratio of actual length to theoretical quarter wavelength
            use_meandering: Whether to use meandering to fit in limited space

        Returns:
            str: NEC2 geometry card format
        """
        try:
            # Calculate dimensions in inches
            wavelength = 11802.7 / frequency_mhz  # Speed of light / frequency in inches
            total_length = (wavelength / 2) * length_ratio  # Full dipole length
            logger.debug(f"Target dipole length for {frequency_mhz} MHz: {total_length:.3f} inches")

            # Check if meandering is needed
            max_straight_length = self.substrate_width * 0.8  # Leave margins
            needs_meandering = use_meandering and total_length > max_straight_length

            if needs_meandering:
                logger.info(f"Using meandering for {frequency_mhz} MHz dipole (length: {total_length:.3f} > {max_straight_length:.3f})")
                geometry = self._generate_meandered_dipole(total_length, frequency_mhz)
            else:
                logger.info(f"Using straight dipole for {frequency_mhz} MHz (length: {total_length:.3f})")
                geometry = self._generate_straight_dipole(total_length, frequency_mhz)

            logger.info(f"Generated dipole antenna for {frequency_mhz} MHz: {len(geometry.split(chr(10)))} wire segments")
            return geometry

        except Exception as e:
            logger.error(f"Dipole generation error: {str(e)}")
            raise AntennaGeometryError(f"Failed to generate dipole: {str(e)}")

    def _generate_straight_dipole(self, total_length: float, frequency_mhz: float) -> str:
        """Generate a straight dipole antenna."""
        geometry = []
        gw_tag = 1
        segments = 21  # More segments for better accuracy

        # Single continuous wire from left to right through feed point
        half_length = total_length / 2
        geometry.append(f"GW {gw_tag} {segments} {-half_length:.4f} 0 0 {half_length:.4f} 0 0 {self.min_feature_size:.4f}")

        return "\n".join(geometry)

    def _generate_meandered_dipole(self, total_length: float, frequency_mhz: float) -> str:
        """Generate a meandered dipole to fit in limited space."""
        geometry = []
        gw_tag = 1
        
        # Meandering parameters
        available_width = self.substrate_width * 0.8
        available_height = self.substrate_height * 0.3  # Use 30% of height for meandering
        trace_width = self.min_feature_size * 2  # Wider traces for better etching
        min_spacing = trace_width * 2  # Minimum spacing between traces

        # Calculate meander parameters - FIXED to use full width for each pass
        import math

        # Each pass uses the full available width (leave small margin)
        segment_length = available_width * 0.95

        # Calculate how many passes needed to achieve required total length
        num_passes = max(2, math.ceil(total_length / segment_length))

        # Vertical spacing between passes (minimum 2.5x trace width for isolation)
        vertical_spacing = max(min_spacing, trace_width * 2.5)

        # Total height required for all passes
        meander_height = (num_passes - 1) * vertical_spacing

        # Check if meander fits in available height
        if meander_height > available_height:
            # Reduce spacing to fit, but warn if too tight
            vertical_spacing = available_height / (num_passes - 1) if num_passes > 1 else 0
            if vertical_spacing < min_spacing:
                logger.warning(f"Meander requires {meander_height:.3f}\" height but only {available_height:.3f}\" available")
        
        logger.debug(f"Meander parameters: {num_passes} passes, {segment_length:.3f}\" per pass, {vertical_spacing:.3f}\" spacing")
        
        # Generate meander pattern for left half (starting from center going left)
        current_length = 0
        x_pos = 0
        y_pos = 0
        direction = -1  # Start going left
        
        # Left half meander
        left_segments = []
        while current_length < total_length / 2:
            # Horizontal segment
            segment_end_x = x_pos + direction * segment_length
            segment_end_y = y_pos
            
            # Clamp to substrate bounds
            segment_end_x = max(-available_width/2, min(0, segment_end_x))
            
            segment_length_actual = abs(segment_end_x - x_pos)
            if segment_length_actual > 0.001:  # Skip very small segments
                left_segments.append(f"GW {gw_tag} 1 {x_pos:.4f} {y_pos:.4f} 0 {segment_end_x:.4f} {segment_end_y:.4f} 0 {trace_width:.4f}")
                gw_tag += 1
                current_length += segment_length_actual
            
            x_pos = segment_end_x
            
            # Vertical segment (if not at end)
            if current_length < total_length / 2 and direction != 0:
                y_pos += vertical_spacing if direction == -1 else -vertical_spacing
                segment_end_y = y_pos
                
                if abs(y_pos) > meander_height / 2:
                    break
                    
                left_segments.append(f"GW {gw_tag} 1 {x_pos:.4f} {y_pos - (vertical_spacing if direction == -1 else -vertical_spacing):.4f} 0 {x_pos:.4f} {segment_end_y:.4f} 0 {trace_width:.4f}")
                gw_tag += 1
                current_length += abs(vertical_spacing)
                
                direction *= -1  # Reverse direction
        
        # Right half meander (mirror of left)
        right_segments = []
        x_pos = 0
        y_pos = 0
        direction = 1  # Start going right
        current_length = 0
        
        while current_length < total_length / 2:
            # Horizontal segment
            segment_end_x = x_pos + direction * segment_length
            segment_end_y = y_pos
            
            # Clamp to substrate bounds
            segment_end_x = max(0, min(available_width/2, segment_end_x))
            
            segment_length_actual = abs(segment_end_x - x_pos)
            if segment_length_actual > 0.001:  # Skip very small segments
                right_segments.append(f"GW {gw_tag} 1 {x_pos:.4f} {y_pos:.4f} 0 {segment_end_x:.4f} {segment_end_y:.4f} 0 {trace_width:.4f}")
                gw_tag += 1
                current_length += segment_length_actual
            
            x_pos = segment_end_x
            
            # Vertical segment (if not at end)
            if current_length < total_length / 2 and direction != 0:
                y_pos += vertical_spacing if direction == 1 else -vertical_spacing
                segment_end_y = y_pos
                
                if abs(y_pos) > meander_height / 2:
                    break
                    
                right_segments.append(f"GW {gw_tag} 1 {x_pos:.4f} {y_pos - (vertical_spacing if direction == 1 else -vertical_spacing):.4f} 0 {x_pos:.4f} {segment_end_y:.4f} 0 {trace_width:.4f}")
                gw_tag += 1
                current_length += abs(vertical_spacing)
                
                direction *= -1  # Reverse direction
        
        # Combine all segments
        all_segments = left_segments + right_segments
        geometry = "\n".join(all_segments)

        # Verify actual trace length achieved
        actual_total_length = sum(self._calculate_segment_length(seg) for seg in all_segments)
        length_error_percent = abs(actual_total_length - total_length) / total_length * 100 if total_length > 0 else 0

        logger.info(f"Generated meandered dipole: {len(all_segments)} segments")
        logger.info(f"Target length: {total_length:.3f}\", Achieved: {actual_total_length:.3f}\" ({length_error_percent:.1f}% error)")

        if length_error_percent > 10:
            logger.warning(f"Meander length error exceeds 10%: target={total_length:.3f}\", actual={actual_total_length:.3f}\"")

        return geometry

    def _calculate_segment_length(self, gw_line: str) -> float:
        """Calculate physical length of a wire segment from GW line.

        Args:
            gw_line: NEC2 GW geometry card string

        Returns:
            float: Physical length of the segment in inches
        """
        import math
        parts = gw_line.split()
        if len(parts) >= 8:
            try:
                x1, y1, z1 = float(parts[3]), float(parts[4]), float(parts[5])
                x2, y2, z2 = float(parts[6]), float(parts[7]), float(parts[8])
                return math.sqrt((x2-x1)**2 + (y2-y1)**2 + (z2-z1)**2)
            except (ValueError, IndexError):
                return 0.0
        return 0.0

    def generate_monopole(self, frequency_mhz: float, ground_length: float = 1.0) -> str:
        """Generate quarter-wave monopole antenna with ground plane.

        Args:
            frequency_mhz: Operating frequency in MHz
            ground_length: Length of ground plane elements

        Returns:
            str: NEC2 geometry card format
        """
        try:
            wavelength = 11802.7 / frequency_mhz
            element_length = (wavelength / 4) * 0.95

            if element_length > self.substrate_height * 0.8:
                element_length = self.substrate_height * 0.8
                logger.warning(f"Reduced monopole length for substrate: {element_length:.3f} inches")

            geometry = []
            gw_tag = 1

            # Vertical element
            geometry.append(f"GW {gw_tag} 7 0 0 0 0 {element_length:.4f} 0 {self.min_feature_size:.4f}")
            gw_tag += 1

            # Ground plane elements
            ground_radius = 0.2  # Ground plane size
            angles = np.linspace(0, 2*np.pi, 5)[:-1]  # 4 ground elements

            for angle in angles:
                x = ground_radius * np.cos(angle)
                y = ground_radius * np.sin(angle)
                geometry.append(f"GW {gw_tag} 5 0 0 0 {x:.4f} {y:.4f} 0 {self.min_feature_size:.4f}")
                gw_tag += 1

            nec_geometry = "\n".join(geometry)
            logger.info(f"Generated monopole antenna: {element_length:.3f} inches for {frequency_mhz} MHz")

            return nec_geometry

        except Exception as e:
            logger.error(f"Monopole generation error: {str(e)}")
            raise AntennaGeometryError(f"Failed to generate monopole: {str(e)}")

    def generate_spiral_coil(self, frequency_mhz: float, turns: int = 3,
                           min_radius: float = 0.05, spacing: float = 0.01) -> str:
        """Generate high-resolution spiral coil for size compensation.

        Args:
            frequency_mhz: Operating frequency in MHz
            turns: Number of spiral turns
            min_radius: Inner radius in inches
            spacing: Spacing between turns in inches

        Returns:
            str: NEC2 wire geometry cards
        """
        try:
            geometry = []
            gw_tag = 1

            # Calculate electrical length for loading
            target_length = 11802.7 / frequency_mhz  # Full wavelength

            # Generate spiral coordinates
            theta = np.linspace(0, turns * 2 * np.pi, max(turns * 20, 50))
            radius = min_radius + (spacing / (2 * np.pi)) * theta

            x_coords = radius * np.cos(theta)
            y_coords = radius * np.sin(theta)

            # Check bounds
            max_extent = np.max([np.max(np.abs(x_coords)), np.max(np.abs(y_coords))])
            if max_extent > min(self.substrate_width, self.substrate_height) / 2:
                scale_factor = min(self.substrate_width, self.substrate_height) / 2 / max_extent * 0.9
                x_coords *= scale_factor
                y_coords *= scale_factor
                logger.warning(f"Scaled spiral coil to fit substrate: scale factor {scale_factor:.2f}")

            # Convert to wire segments
            segments_per_turn = 10
            for i in range(len(x_coords) - 1):
                x1, y1 = x_coords[i], y_coords[i]
                x2, y2 = x_coords[i+1], y_coords[i+1]

                # Skip segments that are too short
                if np.sqrt((x2-x1)**2 + (y2-y1)**2) < self.min_feature_size * 2:
                    continue

                geometry.append(f"GW {gw_tag} 1 {x1:.4f} {y1:.4f} 0 {x2:.4f} {y2:.4f} 0 {self.min_feature_size:.4f}")
                gw_tag += 1

            nec_geometry = "\n".join(geometry)
            logger.info(f"Generated {turns}-turn spiral coil for {frequency_mhz} MHz")
            return nec_geometry

        except Exception as e:
            logger.error(f"Spiral coil generation error: {str(e)}")
            raise AntennaGeometryError(f"Failed to generate spiral coil: {str(e)}")

    def generate_patch_antenna(self, frequency_mhz: float, substrate_epsilon: float = 4.0) -> str:
        """Generate microstrip patch antenna.

        Args:
            frequency_mhz: Operating frequency in MHz
            substrate_epsilon: Dielectric constant of substrate

        Returns:
            str: NEC2 surface geometry cards
        """
        try:
            # Calculate patch dimensions using standard formulas
            wavelength = 11802.7 / frequency_mhz / np.sqrt(substrate_epsilon)
            length = wavelength / 2 * 0.98  # Effective length
            width = wavelength / 2 * 0.4    # Width for good radiation

            # Scale to fit substrate
            max_dim = max(length, width)
            if max_dim > min(self.substrate_width, self.substrate_height) * 0.8:
                scale_factor = min(self.substrate_width, self.substrate_height) * 0.8 / max_dim
                length *= scale_factor
                width *= scale_factor
                logger.warning(f"Scaled patch antenna to fit substrate")

            # Generate SP card (surface patch)
            # SP tag segments x1 y1 z1 x2 y2 z2 x3 y3 z3 x4 y4 z4
            x1, y1 = -width/2, -length/2
            x2, y2 = width/2, -length/2
            x3, y3 = width/2, length/2
            x4, y4 = -width/2, length/2

            nec_geometry = f"SP 0 4 {x1:.4f} {y1:.4f} 0 {x2:.4f} {y2:.4f} 0 {x3:.4f} {y3:.4f} 0 {x4:.4f} {y4:.4f} 0"

            logger.info(f"Generated patch antenna: {width:.3f}x{length:.3f} inches for {frequency_mhz} MHz")
            return nec_geometry

        except Exception as e:
            logger.error(f"Patch antenna generation error: {str(e)}")
            raise AntennaGeometryError(f"Failed to generate patch: {str(e)}")

    def generate_tri_band_geometry(self, freq1: float, freq2: float, freq3: float) -> str:
        """Generate tri-band antenna combining multiple elements.

        Args:
            freq1, freq2, freq3: Three operating frequencies in MHz

        Returns:
            str: Combined NEC2 geometry for tri-band operation
        """
        try:
            geometries = []

            # Low frequency: Monopole with ground plane
            geometries.append(self.generate_monopole(freq1))

            # Mid frequency: Dipole
            geometries.append(self.generate_dipole(freq2))

            # High frequency: Patch or spiral
            if freq3 > 1000:  # GHz range
                geometries.append(self.generate_spiral_coil(freq3, turns=2))
            else:
                geometries.append(self.generate_patch_antenna(freq3))

            # Combine all geometries (adjust wire tags to avoid conflicts)
            combined = []
            tag_offset = 0
            for geom in geometries:
                lines = geom.split('\n')
                for line in lines:
                    if line.strip():
                        parts = line.split()
                        if len(parts) > 1 and parts[0] in ['GW', 'SP']:
                            # Adjust tag numbers
                            parts[1] = str(int(parts[1]) + tag_offset)
                            combined.append(' '.join(parts))

                # Increment tag offset (rough estimate)
                tag_offset += 10

            nec_geometry = "\n".join(combined)
            logger.info(f"Generated tri-band antenna for {freq1}/{freq2}/{freq3} MHz")
            return nec_geometry

        except Exception as e:
            logger.error(f"Tri-band geometry generation error: {str(e)}")
            raise AntennaGeometryError(f"Failed to generate tri-band antenna: {str(e)}")

class GeometryValidation:
    """Validate generated geometries against constraints."""

    @staticmethod
    def check_bounds(geometry: str, max_width: float = 4.0, max_height: float = 2.0) -> dict:
        """Check if geometry fits within substrate bounds."""
        validation = {
            'within_bounds': True,
            'max_x': 0.0,
            'max_y': 0.0,
            'warnings': []
        }

        try:
            lines = geometry.split('\n')
            coords = []

            for line in lines:
                parts = line.split()
                if len(parts) >= 8 and parts[0] == 'GW':  # Wire geometry
                    # Extract coordinates: x1,y1,z1,x2,y2,z2
                    try:
                        x1, y1 = float(parts[3]), float(parts[4])
                        x2, y2 = float(parts[6]), float(parts[7])
                        coords.extend([(x1, y1), (x2, y2)])
                    except (ValueError, IndexError):
                        continue

            if coords:
                x_coords = [c[0] for c in coords]
                y_coords = [c[1] for c in coords]

                validation['max_x'] = max(abs(min(x_coords)), abs(max(x_coords)))
                validation['max_y'] = max(abs(min(y_coords)), abs(max(y_coords)))

                if validation['max_x'] > max_width / 2:
                    validation['within_bounds'] = False
                    validation['warnings'].append(f"X extent exceeds substrate: {validation['max_x']:.3f} > {max_width/2:.3f}")

                if validation['max_y'] > max_height / 2:
                    validation['within_bounds'] = False
                    validation['warnings'].append(f"Y extent exceeds substrate: {validation['max_y']:.3f} > {max_height/2:.3f}")

        except Exception as e:
            validation['warnings'].append(f"Geometry validation error: {str(e)}")

        return validation


class AdvancedMeanderTrace:
    """Advanced meander trace generator with mathematical optimization for maximum electrical length."""
    
    def __init__(self, substrate_width: float = 4.0, substrate_height: float = 2.0):
        """Initialize with substrate dimensions in inches."""
        self.substrate_width = substrate_width  # inches
        self.substrate_height = substrate_height  # inches
        self.min_feature_size = 0.005  # 5 mil minimum trace width
        
        # Material properties (default FR-4)
        self.substrate_epsilon = 4.3
        self.substrate_thickness = 0.063  # 63 mil (1.6mm) standard FR-4
        self.copper_thickness = 0.0014  # 1 oz copper (1.4 mil)
        
        # Physical constants
        self.c = 299792458  # Speed of light in m/s
        
        logger.info(f"AdvancedMeanderTrace initialized for {substrate_width}x{substrate_height} inch substrate")
    
    def calculate_effective_permittivity(self, er: float, h: float, w: float) -> float:
        """Calculate effective permittivity using microstrip approximation.
        
        Args:
            er: Substrate relative permittivity
            h: Substrate thickness (same units as w)
            w: Trace width (same units as h)
            
        Returns:
            float: Effective permittivity
        """
        try:
            # Microstrip effective permittivity formula
            # e_eff ≈ (er + 1)/2 + (er - 1)/2 * (1 / sqrt(1 + 12 * (h/w)))
            
            if w <= 0 or h <= 0:
                logger.warning(f"Invalid dimensions: w={w}, h={h}")
                return er
            
            hw_ratio = h / w
            denom = math.sqrt(1 + 12 * hw_ratio)
            
            if denom <= 0:
                logger.warning(f"Invalid denominator in permittivity calculation: {denom}")
                return er
            
            frac = 1 / denom
            mid = (er + 1) / 2
            diff = (er - 1) / 2
            
            e_eff = mid + diff * frac
            logger.debug(f"Effective permittivity: er={er}, h/w={hw_ratio:.3f}, e_eff={e_eff:.3f}")
            
            return e_eff
            
        except Exception as e:
            logger.error(f"Effective permittivity calculation failed: {str(e)}")
            return er  # Fallback to substrate permittivity
    
    def calculate_target_length(self, frequency_hz: float, er_eff: float, kc: float = 0.90) -> float:
        """Calculate target electrical length for meander trace.

        Args:
            frequency_hz: Target frequency in Hz
            er_eff: Effective permittivity
            kc: Coupling/loading factor (0.80-0.98)

        Returns:
            float: Target length in meters
        """
        try:
            # Half-wave electrical length for dipole (same as simple meander)
            # Use same calculation as simple meander: wavelength = 11802.7 / freq_mhz
            # This gives wavelength in inches, then convert to meters

            if frequency_hz <= 0:
                logger.warning(f"Invalid frequency: f={frequency_hz}")
                return 0.0

            # Convert frequency to MHz
            frequency_mhz = frequency_hz / 1e6

            # Calculate wavelength in inches (matches simple meander calculation)
            wavelength_inches = 11802.7 / frequency_mhz

            # Half-wave dipole length with velocity factor
            # Using kc as the velocity/length factor (similar to length_ratio in simple meander)
            target_length_inches = (wavelength_inches / 2) * kc

            # Convert to meters
            target_length_meters = target_length_inches * 0.0254

            logger.info(f"Target length: f={frequency_mhz:.1f}MHz, kc={kc:.2f}, L_target={target_length_inches:.2f}\" ({target_length_meters*1000:.1f}mm)")

            return target_length_meters

        except Exception as e:
            logger.error(f"Target length calculation failed: {str(e)}")
            return 0.0
    
    def optimize_meander_geometry(self, W: float, H: float, L_target: float, 
                                  constraints: Dict[str, Any] = None) -> Dict[str, Any]:
        """Optimize meander geometry to achieve target length within constraints.
        
        Args:
            W: Usable width (meters)
            H: Usable height (meters)
            L_target: Target electrical length (meters)
            constraints: Dictionary of design constraints
            
        Returns:
            dict: Optimized geometry parameters
        """
        try:
            if constraints is None:
                constraints = {}
            
            # Default constraints
            m = constraints.get('margin', 0.002)  # 2mm margin
            r = constraints.get('bend_radius', 0.001)  # 1mm bend radius
            w = constraints.get('trace_width', 0.001)  # 1mm trace width
            min_spacing = constraints.get('min_spacing', w * 2)  # 2x trace width
            kc = constraints.get('coupling_factor', 0.90)
            
            # Convert to inches for internal calculations
            W_in = W * 39.3701
            H_in = H * 39.3701
            m_in = m * 39.3701
            r_in = r * 39.3701
            w_in = w * 39.3701
            L_target_in = L_target * 39.3701
            
            logger.info(f"Optimizing meander: W={W_in:.2f}\", H={H_in:.2f}\", L_target={L_target_in:.2f}\"")
            
            # Design loop - iterate to find optimal parameters
            best_solution = None
            min_error = float('inf')
            
            # Try different pitch values
            pitch_range = np.linspace(w_in * 2.5, min(H_in / 3, W_in / 4), 20)
            
            for p_in in pitch_range:
                # Calculate lane count from height
                N = int(math.floor((H_in - 2 * m_in) / p_in))
                
                if N < 1:
                    continue
                
                # Calculate geometry
                L_lane = W_in - 2 * m_in
                L_U = math.pi * r_in
                L_path_geom = N * L_lane + (N - 1) * L_U
                
                # Calculate error
                error = abs(L_path_geom - L_target_in)
                
                # Calculate coupling factor adjustment based on geometry
                p_w_ratio = p_in / w_in
                if p_w_ratio < 2:
                    kc_adjusted = kc - 0.05  # Strong coupling
                elif p_w_ratio > 4:
                    kc_adjusted = kc + 0.03  # Weak coupling
                else:
                    kc_adjusted = kc
                
                # Store solution if it's better
                if error < min_error:
                    min_error = error
                    best_solution = {
                        'N': N,
                        'pitch_inches': p_in,
                        'pitch_meters': p_in / 39.3701,
                        'margin_inches': m_in,
                        'margin_meters': m_in / 39.3701,
                        'bend_radius_inches': r_in,
                        'bend_radius_meters': r_in / 39.3701,
                        'trace_width_inches': w_in,
                        'trace_width_meters': w_in / 39.3701,
                        'lane_length_inches': L_lane,
                        'lane_length_meters': L_lane / 39.3701,
                        'u_turn_length_inches': L_U,
                        'u_turn_length_meters': L_U / 39.3701,
                        'total_length_inches': L_path_geom,
                        'total_length_meters': L_path_geom / 39.3701,
                        'target_length_inches': L_target_in,
                        'target_length_meters': L_target_in / 39.3701,
                        'error_inches': error,
                        'error_meters': error / 39.3701,
                        'coupling_factor': kc_adjusted,
                        'utilization_percent': (L_path_geom / L_target_in) * 100,
                        'space_efficiency': (N * L_lane) / (W_in * H_in) * 100
                    }
            
            # Add tuning stub if needed
            if best_solution:
                delta_L = best_solution['target_length_meters'] - best_solution['total_length_meters']
                best_solution['tuning_stub_meters'] = max(0, delta_L)
                best_solution['tuning_stub_inches'] = best_solution['tuning_stub_meters'] * 39.3701
                
                logger.info(f"Optimized meander: N={best_solution['N']}, pitch={best_solution['pitch_inches']:.3f}\", "
                          f"error={best_solution['error_inches']:.3f}\", utilization={best_solution['utilization_percent']:.1f}%")
            
            return best_solution or {}
            
        except Exception as e:
            logger.error(f"Meander optimization failed: {str(e)}")
            return {}
    
    def generate_advanced_meander(self, frequency_mhz: float, constraints: Dict[str, Any] = None) -> str:
        """Generate advanced meander trace geometry for given frequency.
        
        Args:
            frequency_mhz: Target frequency in MHz
            constraints: Design constraints dictionary
            
        Returns:
            str: NEC2 geometry cards for the meander trace
        """
        try:
            frequency_hz = frequency_mhz * 1e6
            
            # Set up constraints
            if constraints is None:
                constraints = {}
            
            # Material properties
            er = constraints.get('substrate_epsilon', self.substrate_epsilon)
            h = constraints.get('substrate_thickness', self.substrate_thickness)
            w = constraints.get('trace_width', 0.001)  # 1mm default
            
            # Calculate effective permittivity
            e_eff = self.calculate_effective_permittivity(er, h, w)
            
            # Calculate target length
            kc = constraints.get('coupling_factor', 0.90)
            L_target = self.calculate_target_length(frequency_hz, e_eff, kc)
            
            # Usable substrate area (convert to meters)
            usable_width = (self.substrate_width - 0.1) * 0.0254  # Leave 0.1" margin
            usable_height = (self.substrate_height - 0.1) * 0.0254
            
            # Optimize geometry
            geometry_params = self.optimize_meander_geometry(
                usable_width, usable_height, L_target, constraints
            )
            
            if not geometry_params:
                logger.error("Failed to optimize meander geometry")
                return ""
            
            # Generate NEC2 geometry
            return self._create_meander_geometry(geometry_params)
            
        except Exception as e:
            logger.error(f"Advanced meander generation failed: {str(e)}")
            return ""
    
    def _create_meander_geometry(self, params: Dict[str, Any]) -> str:
        """Create NEC2 geometry from optimized meander parameters.
        
        Args:
            params: Optimized geometry parameters
            
        Returns:
            str: NEC2 geometry cards
        """
        try:
            # Use the new dual-side spiral dipole generator
            return self._create_dual_spiral_dipole(params)
            
        except Exception as e:
            logger.error(f"Meander geometry creation failed: {str(e)}")
            return ""
    
    def _create_dual_spiral_dipole(self, params: Dict[str, Any]) -> str:
        """Create a dual-side spiral dipole antenna for maximum space utilization.
        
        Args:
            params: Optimized geometry parameters
            
        Returns:
            str: NEC2 geometry cards
        """
        try:
            geometry = []
            gw_tag = 1
            
            # Extract parameters
            trace_width = params.get('trace_width_inches', 0.010)
            min_spacing = trace_width * 2.5  # Minimum spacing between positive/negative sides
            target_length = params.get('total_length_inches', 30.0)
            
            logger.info(f"Creating dual-side spiral dipole: target_length={target_length:.2f}\", trace_width={trace_width:.4f}\", min_spacing={min_spacing:.4f}\"")
            
            # Calculate half-length for each dipole side
            half_length = target_length / 2
            
            # Substrate bounds (in inches)
            max_x = self.substrate_width / 2 - 0.1  # Leave margin
            max_y = self.substrate_height / 2 - 0.1
            
            # Generate positive spiral (top side)
            positive_spiral, pos_tag = self._generate_spiral_arm(
                start_x=0, start_y=0,
                target_length=half_length,
                max_x=max_x, max_y=max_y,
                direction='up',  # Spiral upward and to the right
                trace_width=trace_width,
                side_name='positive',
                start_tag=gw_tag
            )
            
            # Generate negative spiral (bottom side)
            negative_spiral, neg_tag = self._generate_spiral_arm(
                start_x=0, start_y=0,
                target_length=half_length,
                max_x=max_x, max_y=max_y,
                direction='down',  # Spiral downward and to the right
                trace_width=trace_width,
                side_name='negative',
                start_tag=pos_tag
            )
            
            # Combine both spirals
            geometry.extend(positive_spiral)
            geometry.extend(negative_spiral)
            
            # Add feed point connection (center point where both sides meet)
            geometry.append(f"GW {neg_tag} 1 0 0 0 0 0 0 {trace_width:.4f}")
            
            nec_geometry = "\n".join(geometry)
            total_segments = len(geometry)
            
            # Calculate actual achieved length
            actual_length = sum(self._calculate_segment_length(seg) for seg in geometry)
            length_error = abs(actual_length - target_length) / target_length * 100
            
            logger.info(f"Generated dual-side spiral dipole: {total_segments} segments")
            logger.info(f"Target length: {target_length:.2f}\", Achieved: {actual_length:.2f}\" ({length_error:.1f}% error)")
            
            return nec_geometry
            
        except Exception as e:
            logger.error(f"Dual-side spiral dipole creation failed: {str(e)}")
            return ""
    
    def _calculate_segment_length(self, gw_line: str) -> float:
        """Calculate physical length of a wire segment from GW line.

        Args:
            gw_line: NEC2 GW geometry card string

        Returns:
            float: Physical length of the segment in inches
        """
        import math
        parts = gw_line.split()
        if len(parts) >= 8:
            try:
                x1, y1, z1 = float(parts[3]), float(parts[4]), float(parts[5])
                x2, y2, z2 = float(parts[6]), float(parts[7]), float(parts[8])
                return math.sqrt((x2-x1)**2 + (y2-y1)**2 + (z2-z1)**2)
            except (ValueError, IndexError):
                return 0.0
        return 0.0

    def _generate_spiral_arm(self, start_x: float, start_y: float, target_length: float,
                            max_x: float, max_y: float, direction: str,
                            trace_width: float, side_name: str, start_tag: int) -> tuple:
        """Generate one arm of a spiral dipole with proper meander pattern that maximizes substrate utilization.

        Args:
            start_x, start_y: Starting coordinates (feed point)
            target_length: Target electrical length for this arm
            max_x, max_y: Maximum bounds for spiral
            direction: 'up' or 'down' - which side of substrate to use
            trace_width: Width of trace
            side_name: 'positive' or 'negative' for logging
            start_tag: Starting GW tag number

        Returns:
            tuple: (list of geometry strings, final tag number)
        """
        try:
            geometry = []
            gw_tag = start_tag
            current_length = 0.0

            # Starting position (feed point)
            current_x = start_x
            current_y = start_y

            # More aggressive substrate utilization for larger substrates
            available_height = max_y * 2  # Total height available
            min_vertical_spacing = trace_width * 2.0  # Reduced minimum spacing for better utilization

            # For larger substrates (>4 inches), use more aggressive spacing
            if max_x > 2.0 or max_y > 2.0:  # Large substrate detected
                min_vertical_spacing = trace_width * 1.5  # Even more aggressive for large substrates
                max_passes = min(30, int(available_height / min_vertical_spacing))  # Allow more passes
            else:
                max_passes = 15  # Conservative limit for smaller substrates

            # Use full substrate width for each meander pass
            segment_length = max_x * 0.95  # Use 95% of available width

            # Strategy: Maximize substrate utilization by calculating optimal vertical distribution
            # Start with the minimum spacing and calculate how many passes we can fit
            max_possible_passes = min(max_passes, int(available_height / min_vertical_spacing))

            # Calculate optimal step size to utilize as much height as possible
            if max_possible_passes > 1:
                # Distribute passes across entire available height
                step_size = available_height / max_possible_passes
                # Ensure minimum spacing is maintained
                step_size = max(min_vertical_spacing, step_size)
            else:
                step_size = min_vertical_spacing

            logger.debug(f"Maximized substrate utilization: max_y={max_y:.3f}\" ({available_height:.3f}\" total), "
                       f"max_passes={max_possible_passes}, step_size={step_size:.3f}\", "
                       f"segment_length={segment_length:.3f}\", target={target_length:.2f}\"")

            # Generate meander pattern with alternating horizontal passes
            meander_pass = 0
            horizontal_direction = 1  # Start going right
            continue_expansion = True

            # Generate passes until we can't fit more or reach practical limits
            while continue_expansion and meander_pass < max_possible_passes:
                # Check if we've exceeded vertical bounds
                next_y = current_y + (step_size if direction == 'up' else -step_size)

                # If this would exceed bounds AND we've already met target length, stop
                if abs(next_y) > max_y and current_length >= target_length * 0.8:  # 80% is acceptable
                    logger.debug(f"{side_name} meander reached vertical bound after adequate length")
                    break

                # Horizontal segment - always use full available width
                segment_end_x = current_x + horizontal_direction * segment_length
                segment_length_actual = abs(segment_end_x - current_x)

                # Ensure we don't exceed horizontal bounds
                if abs(segment_end_x) > max_x:
                    segment_end_x = max_x if horizontal_direction > 0 else -max_x
                    segment_length_actual = abs(segment_end_x - current_x)

                if segment_length_actual > 0.005:  # Skip very small segments
                    geometry.append(f"GW {gw_tag} 1 {current_x:.4f} {current_y:.4f} 0 {segment_end_x:.4f} {current_y:.4f} 0 {trace_width:.4f}")
                    gw_tag += 1
                    current_length += segment_length_actual

                current_x = segment_end_x

                # Move to next vertical level if we haven't filled the substrate
                can_add_vertical = abs(next_y) <= max_y and meander_pass < max_possible_passes - 1
                should_add_vertical = current_length < target_length * 1.2  # Allow 20% extra length

                if can_add_vertical and should_add_vertical:
                    segment_length_vertical = abs(next_y - current_y)

                    if segment_length_vertical > 0.005:
                        geometry.append(f"GW {gw_tag} 1 {current_x:.4f} {current_y:.4f} 0 {current_x:.4f} {next_y:.4f} 0 {trace_width:.4f}")
                        gw_tag += 1
                        current_length += segment_length_vertical

                        current_y = next_y
                        horizontal_direction *= -1  # Reverse direction for next horizontal segment
                    else:
                        # Can't make meaningful vertical move, stop expansion
                        continue_expansion = False
                else:
                    # Can't add more vertical levels, stop expansion
                    continue_expansion = False

                meander_pass += 1

                # Emergency break for runaway generation
                if meander_pass >= max_possible_passes:
                    logger.warning(f"{side_name} meander reached maximum passes ({max_possible_passes})")
                    break

            # Calculate final utilization metrics
            final_y_range = abs(current_y) * 2  # Total Y span used
            height_utilization = min(100.0, (final_y_range / available_height) * 100)
            width_utilization = min(100.0, (segment_length / (max_x * 2)) * 100)  # Based on final segment length
            overall_utilization = (height_utilization + width_utilization) / 2

            logger.info(f"{side_name} spiral arm: {len(geometry)} segments, {current_length:.2f}\" length "
                       f"({current_length/target_length*100:.1f}% of target), {meander_pass} passes, "
                       f"height utilization: {height_utilization:.1f}%, overall: {overall_utilization:.1f}%")

            return geometry, gw_tag

        except Exception as e:
            logger.error(f"Meander arm generation failed for {side_name}: {str(e)}")
            return [], start_tag
    
    def calculate_electrical_metrics(self, params: Dict[str, Any], frequency_hz: float) -> Dict[str, Any]:
        """Calculate electrical metrics for the meander trace.
        
        Args:
            params: Geometry parameters
            frequency_hz: Operating frequency in Hz
            
        Returns:
            dict: Electrical performance metrics
        """
        try:
            # Calculate effective permittivity
            e_eff = self.calculate_effective_permittivity(
                self.substrate_epsilon, 
                self.substrate_thickness,
                params.get('trace_width_meters', 0.001)
            )
            
            # Calculate actual electrical length
            L_physical = params.get('total_length_meters', 0)
            wavelength = self.c / frequency_hz
            lambda_eff = wavelength / math.sqrt(e_eff)
            
            # Electrical length as fraction of wavelength
            electrical_length_wavelengths = L_physical / lambda_eff
            
            # Estimate impedance (simplified)
            # Z ≈ 60 / sqrt(e_eff) * ln(8h/w + w/(4h))
            h = self.substrate_thickness
            w = params.get('trace_width_meters', 0.001)
            if w > 0 and h > 0:
                impedance = 60 / math.sqrt(e_eff) * math.log(8 * h / w + w / (4 * h))
            else:
                impedance = 50  # Default
            
            # Estimate Q factor (simplified)
            # Q ≈ π * f * L / R (where R is radiation resistance)
            # For meander traces, Q is typically 10-50
            Q_factor = min(50, max(10, 25 - params.get('N', 1) * 2))
            
            metrics = {
                'effective_permittivity': e_eff,
                'physical_length_meters': L_physical,
                'electrical_length_wavelengths': electrical_length_wavelengths,
                'estimated_impedance_ohms': impedance,
                'estimated_q_factor': Q_factor,
                'space_efficiency_percent': params.get('space_efficiency', 0),
                'utilization_percent': params.get('utilization_percent', 0),
                'coupling_factor': params.get('coupling_factor', 0.9)
            }
            
            logger.debug(f"Electrical metrics: Z={impedance:.1f}Ω, Q={Q_factor:.1f}, "
                        f"L={electrical_length_wavelengths:.3f}λ")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Electrical metrics calculation failed: {str(e)}")
            return {}
    
    def generate_multi_band_meanders(self, frequencies: List[float], 
                                    constraints: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate optimized meanders for multiple frequencies with spatial optimization.
        
        Args:
            frequencies: List of frequencies in MHz
            constraints: Design constraints dictionary
            
        Returns:
            dict: Multi-band meander geometries and parameters
        """
        try:
            if not frequencies:
                logger.error("No frequencies provided for multi-band meander generation")
                return {}
            
            logger.info(f"Generating multi-band meanders for {len(frequencies)} frequencies: {frequencies}")
            
            # Sort frequencies by wavelength (low to high for optimal spatial arrangement)
            freq_with_index = [(f, i) for i, f in enumerate(frequencies)]
            freq_with_index.sort(key=lambda x: x[0])  # Sort by frequency
            
            multi_band_result = {
                'frequencies_mhz': frequencies,
                'geometries': {},
                'parameters': {},
                'metrics': {},
                'combined_geometry': "",
                'optimization_summary': {}
            }
            
            # Calculate spatial allocation strategy
            substrate_area = self.substrate_width * self.substrate_height
            area_per_band = substrate_area / len(frequencies)
            
            # For large substrates, use a unified approach that fills the entire substrate area
            # instead of separate vertical bands
            logger.info(f"Using unified substrate utilization strategy for large substrate (8x8+)")

            # Create a single large meander that resonates at all frequencies
            # by combining the design requirements
            max_freq = max(frequencies)
            min_freq = min(frequencies)

            # Calculate combined electrical requirements
            combined_length = (self.extract_target_length(max_freq) + self.extract_target_length(min_freq)) * 1.5
            combined_constraints = self._calculate_unified_constraints(frequencies, constraints or {})

            # Position the unified meander to fill the substrate
            combined_constraints.update({
                'substrate_width': self.substrate_width,
                'substrate_height': self.substrate_height,
                'target_area_coverage': 0.8  # Aim for 80% substrate utilization
            })

            # Generate unified meander geometry
            unified_geometry = self._generate_unified_substrate_meander(frequencies, combined_constraints)

            if unified_geometry:
                multi_band_result['combined_geometry'] = unified_geometry
                multi_band_result['geometries']['unified'] = unified_geometry

                # Calculate metrics for the unified design
                freq_hz = sum(f * 1e6 for f in frequencies) / len(frequencies)  # Average frequency
                geometry_params = self._extract_geometry_params(unified_geometry)
                if geometry_params:
                    metrics = self.calculate_electrical_metrics(geometry_params, freq_hz)
                    for i in range(len(frequencies)):
                        multi_band_result['metrics'][f'band_{i+1}'] = metrics

                logger.info(f"Generated unified substrate-filling meander: {len(unified_geometry.split())} segments")
            else:
                logger.warning("Failed to generate unified meander, falling back to individual bands")

                # Fallback: Determine optimal layout based on frequency separation
                if len(frequencies) == 2:
                    layout_strategy = 'vertical_split'
                elif len(frequencies) == 3:
                    layout_strategy = 'triple_vertical'
                else:
                    layout_strategy = 'grid'

                logger.info(f"Using fallback layout strategy: {layout_strategy}")

                # Generate meanders for each frequency
                all_geometries = []
                tag_offset = 0

                for freq_mhz, original_idx in freq_with_index:
                    # Calculate band-specific constraints
                    band_constraints = self._calculate_band_constraints(
                        freq_mhz, original_idx, len(frequencies), layout_strategy, constraints
                    )

                    # Generate meander for this frequency
                    geometry = self.generate_advanced_meander(freq_mhz, band_constraints)

                    if geometry:
                        # Adjust wire tags to avoid conflicts
                        adjusted_geometry = self._adjust_wire_tags(geometry, tag_offset)
                        all_geometries.append(adjusted_geometry)

                        # Store results
                        multi_band_result['geometries'][f'band_{original_idx+1}'] = adjusted_geometry
                        multi_band_result['parameters'][f'band_{original_idx+1}'] = band_constraints

                        # Calculate electrical metrics
                        freq_hz = freq_mhz * 1e6
                        # Extract geometry parameters for metrics calculation
                        geometry_params = self._extract_geometry_params(adjusted_geometry)
                        if geometry_params:
                            metrics = self.calculate_electrical_metrics(geometry_params, freq_hz)
                            multi_band_result['metrics'][f'band_{original_idx+1}'] = metrics

                        # Update tag offset for next band
                        tag_offset += 1000  # Large offset to avoid conflicts

                        logger.info(f"Generated meander for band {original_idx+1} ({freq_mhz} MHz): "
                                  f"{len(adjusted_geometry.split())} segments")
                    else:
                        logger.warning(f"Failed to generate meander for band {original_idx+1} ({freq_mhz} MHz)")

                # Combine all geometries
                if all_geometries:
                    multi_band_result['combined_geometry'] = "\n".join(all_geometries)
                logger.info(f"Combined multi-band geometry: {len(all_geometries)} bands, "
                          f"{len(multi_band_result['combined_geometry'].split())} total segments")
            
            # Calculate optimization summary
            multi_band_result['optimization_summary'] = self._calculate_optimization_summary(
                multi_band_result, frequencies
            )
            
            return multi_band_result
            
        except Exception as e:
            logger.error(f"Multi-band meander generation failed: {str(e)}")
            return {}
    
    def _calculate_band_constraints(self, frequency_mhz: float, band_idx: int, total_bands: int,
                                  layout_strategy: str, base_constraints: Dict[str, Any] = None) -> Dict[str, Any]:
        """Calculate band-specific constraints based on layout strategy.
        
        Args:
            frequency_mhz: Frequency in MHz
            band_idx: Band index (0-based)
            total_bands: Total number of bands
            layout_strategy: Layout strategy for spatial allocation
            base_constraints: Base constraints to modify
            
        Returns:
            dict: Band-specific constraints
        """
        try:
            if base_constraints is None:
                base_constraints = {}
            
            # Start with base constraints
            band_constraints = base_constraints.copy()
            
            # Calculate spatial allocation
            if layout_strategy == 'vertical_split':
                # Split substrate vertically
                usable_width = (self.substrate_width - 0.1) * 0.0254 / total_bands
                usable_height = (self.substrate_height - 0.1) * 0.0254
                
                # Adjust constraints for this band
                band_constraints['usable_width'] = usable_width
                band_constraints['usable_height'] = usable_height
                
                # Adjust trace width based on frequency
                if frequency_mhz > 1000:  # High frequency
                    band_constraints['trace_width'] = 0.0005  # 0.5mm
                elif frequency_mhz > 100:  # Mid frequency
                    band_constraints['trace_width'] = 0.001  # 1mm
                else:  # Low frequency
                    band_constraints['trace_width'] = 0.0015  # 1.5mm
                
            elif layout_strategy == 'triple_vertical':
                # Three-band vertical layout
                usable_width = (self.substrate_width - 0.1) * 0.0254 / 3
                usable_height = (self.substrate_height - 0.1) * 0.0254
                
                band_constraints['usable_width'] = usable_width
                band_constraints['usable_height'] = usable_height
                
                # Frequency-dependent trace width
                if frequency_mhz > 1000:
                    band_constraints['trace_width'] = 0.0004  # 0.4mm for high freq
                elif frequency_mhz > 100:
                    band_constraints['trace_width'] = 0.0008  # 0.8mm for mid freq
                else:
                    band_constraints['trace_width'] = 0.0012  # 1.2mm for low freq
                
            elif layout_strategy == 'grid':
                # Grid layout for 4+ bands
                cols = int(math.ceil(math.sqrt(total_bands)))
                rows = int(math.ceil(total_bands / cols))
                
                usable_width = (self.substrate_width - 0.1) * 0.0254 / cols
                usable_height = (self.substrate_height - 0.1) * 0.0254 / rows
                
                band_constraints['usable_width'] = usable_width
                band_constraints['usable_height'] = usable_height
                band_constraints['trace_width'] = 0.0006  # 0.6mm default for grid
            
            # Frequency-dependent coupling factor
            if frequency_mhz > 1000:
                band_constraints['coupling_factor'] = 0.85  # Lower coupling for high freq
            elif frequency_mhz > 100:
                band_constraints['coupling_factor'] = 0.90  # Standard coupling
            else:
                band_constraints['coupling_factor'] = 0.95  # Higher coupling for low freq
            
            # Adjust bend radius based on frequency
            if frequency_mhz > 1000:
                band_constraints['bend_radius'] = 0.0005  # 0.5mm for high freq
            else:
                band_constraints['bend_radius'] = 0.001  # 1mm for lower freq
            
            logger.debug(f"Band {band_idx+1} constraints: width={band_constraints.get('usable_width', 0)*1000:.1f}mm, "
                        f"trace_width={band_constraints.get('trace_width', 0)*1000:.2f}mm, "
                        f"kc={band_constraints.get('coupling_factor', 0):.2f}")
            
            return band_constraints
            
        except Exception as e:
            logger.error(f"Band constraints calculation failed: {str(e)}")
            return base_constraints or {}
    
    def _adjust_wire_tags(self, geometry: str, tag_offset: int) -> str:
        """Adjust wire tags in geometry to avoid conflicts.
        
        Args:
            geometry: NEC2 geometry string
            tag_offset: Offset to add to wire tags
            
        Returns:
            str: Geometry with adjusted wire tags
        """
        try:
            lines = geometry.split('\n')
            adjusted_lines = []
            
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if len(parts) > 1 and parts[0] in ['GW', 'SP']:
                        # Adjust tag number
                        try:
                            original_tag = int(float(parts[1]))
                            parts[1] = str(original_tag + tag_offset)
                        except (ValueError, IndexError):
                            pass  # Keep original if can't parse
                    
                    adjusted_lines.append(' '.join(parts))
            
            return '\n'.join(adjusted_lines)
            
        except Exception as e:
            logger.error(f"Wire tag adjustment failed: {str(e)}")
            return geometry
    
    def _extract_geometry_params(self, geometry: str) -> Dict[str, Any]:
        """Extract geometry parameters from NEC2 geometry for metrics calculation.
        
        Args:
            geometry: NEC2 geometry string
            
        Returns:
            dict: Extracted geometry parameters
        """
        try:
            lines = geometry.split('\n')
            params = {
                'total_length_meters': 0,
                'trace_width_meters': 0.001,
                'N': 0,
                'space_efficiency': 0,
                'utilization_percent': 0
            }
            
            total_length = 0
            segment_count = 0
            
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 8 and parts[0] == 'GW':
                        # Extract wire segment
                        try:
                            x1, y1 = float(parts[3]), float(parts[4])
                            x2, y2 = float(parts[6]), float(parts[7])
                            segment_length = math.sqrt((x2-x1)**2 + (y2-y1)**2) * 0.0254  # Convert to meters
                            total_length += segment_length
                            segment_count += 1
                            
                            # Extract trace width
                            if len(parts) > 8:
                                trace_width_inches = float(parts[8])
                                params['trace_width_meters'] = trace_width_inches * 0.0254
                        except (ValueError, IndexError):
                            continue
            
            params['total_length_meters'] = total_length
            params['N'] = max(1, segment_count // 10)  # Estimate lane count
            
            # Estimate efficiency metrics
            substrate_area = self.substrate_width * self.substrate_height * 0.0254 * 0.0254
            params['space_efficiency'] = (total_length * params['trace_width_meters']) / substrate_area * 100
            params['utilization_percent'] = min(100, total_length * 100)  # Rough estimate
            
            return params
            
        except Exception as e:
            logger.error(f"Geometry parameter extraction failed: {str(e)}")
            return {}
    
    def _calculate_optimization_summary(self, multi_band_result: Dict[str, Any], 
                                     frequencies: List[float]) -> Dict[str, Any]:
        """Calculate optimization summary for multi-band design.
        
        Args:
            multi_band_result: Results from multi-band generation
            frequencies: List of frequencies in MHz
            
        Returns:
            dict: Optimization summary
        """
        try:
            summary = {
                'total_bands': len(frequencies),
                'frequency_range_mhz': [min(frequencies), max(frequencies)],
                'total_segments': 0,
                'average_efficiency': 0,
                'bandwidth_coverage': {},
                'spatial_utilization': 0,
                'design_quality_score': 0
            }
            
            # Count total segments
            if multi_band_result.get('combined_geometry'):
                summary['total_segments'] = len(multi_band_result['combined_geometry'].split())
            
            # Calculate average efficiency
            efficiencies = []
            for band_key, metrics in multi_band_result.get('metrics', {}).items():
                if isinstance(metrics, dict):
                    efficiency = metrics.get('space_efficiency_percent', 0)
                    efficiencies.append(efficiency)
            
            if efficiencies:
                summary['average_efficiency'] = sum(efficiencies) / len(efficiencies)
            
            # Calculate bandwidth coverage (simplified)
            if len(frequencies) >= 2:
                freq_range = max(frequencies) - min(frequencies)
                center_freq = sum(frequencies) / len(frequencies)
                summary['bandwidth_coverage'] = {
                    'total_range_mhz': freq_range,
                    'center_frequency_mhz': center_freq,
                    'fractional_bandwidth': freq_range / center_freq if center_freq > 0 else 0
                }
            
            # Estimate spatial utilization
            total_length = 0
            for band_key, params in multi_band_result.get('parameters', {}).items():
                if isinstance(params, dict):
                    length = params.get('total_length_meters', 0)
                    total_length += length
            
            substrate_area = self.substrate_width * self.substrate_height * 0.0254 * 0.0254
            summary['spatial_utilization'] = min(100, (total_length * 0.001) / substrate_area * 100)
            
            # Calculate design quality score (0-100)
            score = 0
            score += min(30, summary['average_efficiency'] / 100 * 30)  # Efficiency (30%)
            score += min(25, summary['spatial_utilization'] / 100 * 25)  # Spatial use (25%)
            score += min(25, len(frequencies) * 8.33)  # Band count (25%)
            score += min(20, (100 - summary['total_segments'] / 10) if summary['total_segments'] < 1000 else 10)  # Complexity (20%)
            
            summary['design_quality_score'] = score
            
            logger.info(f"Optimization summary: quality_score={score:.1f}, "
                       f"efficiency={summary['average_efficiency']:.1f}%, "
                       f"spatial_utilization={summary['spatial_utilization']:.1f}%")
            
            return summary

        except Exception as e:
            logger.error(f"Optimization summary calculation failed: {str(e)}")
            return {}

    def extract_target_length(self, frequency_mhz: float) -> float:
        """Extract target electrical length for a frequency (helper method).

        Args:
            frequency_mhz: Frequency in MHz

        Returns:
            float: Target length in inches
        """
        try:
            # Same calculation as used in generate_advanced_meander
            frequency_hz = frequency_mhz * 1e6
            er_eff = self.calculate_effective_permittivity(
                self.substrate_epsilon, self.substrate_thickness, 0.001
            )
            L_target = self.calculate_target_length(frequency_hz, er_eff, 0.90)
            return L_target * 39.3701  # Convert meters to inches
        except Exception:
            return 10.0  # Default fallback

    def _calculate_unified_constraints(self, frequencies: List[float],
                                      base_constraints: Dict[str, Any] = None) -> Dict[str, Any]:
        """Calculate unified constraints for substrate-filling meander.

        Args:
            frequencies: List of frequencies in MHz
            base_constraints: Base constraints to modify

        Returns:
            dict: Unified constraints for full substrate utilization
        """
        try:
            if base_constraints is None:
                base_constraints = {}

            # Unified constraints prioritize substrate utilization over individual band optimization
            unified = base_constraints.copy()

            # Calculate average frequency for unified design
            avg_freq = sum(frequencies) / len(frequencies)

            # Very aggressive trace width for maximum length in substrate
            unified.update({
                'trace_width': 0.008,  # 8 mil traces
                'coupling_factor': 0.92,  # Balanced coupling
                'bend_radius': 0.0008,  # 0.8mm bends
                'target_electrical_length': sum(self.extract_target_length(f) for f in frequencies) * 1.2,
                'substrate_utilization_priority': True
            })

            logger.info(f"Unified constraints for {len(frequencies)} bands: "
                       f"avg_freq={avg_freq:.1f}MHz, trace_width={unified['trace_width']*1000:.0f}mil, "
                       f"target_length={unified['target_electrical_length']:.2f}\"")

            return unified

        except Exception as e:
            logger.error(f"Unified constraints calculation failed: {str(e)}")
            return base_constraints or {}

    def _generate_unified_substrate_meander(self, frequencies: List[float],
                                          constraints: Dict[str, Any]) -> str:
        """Generate a single meander that fills the entire substrate and resonates at multiple frequencies.

        Args:
            frequencies: List of target frequencies in MHz
            constraints: Design constraints

        Returns:
            str: NEC2 geometry for unified substrate-filling meander
        """
        try:
            # Create a massive meander that fills as much of the substrate as possible
            # This approach prioritizes space utilization over precision frequency matching

            # Use combined target length from all frequencies
            target_length = constraints.get('target_electrical_length', 100.0)
            trace_width = constraints.get('trace_width', 0.008)
            bend_radius = constraints.get('bend_radius', 0.0008)

            # Maximize substrate utilization by using nearly full bounds
            max_x = self.substrate_width / 2 - 0.05  # Leave tiny margin
            max_y = self.substrate_height / 2 - 0.05

            logger.info(f"Generating unified substrate meander: target={target_length:.2f}\", "
                       f"bounds=({max_x:.3f}\", {max_y:.3f}\"), trace={trace_width*1000:.0f}mil")

            # Create dual spiral arms that fill the entire substrate
            geometry = []
            gw_tag = 1

            # Create dual spirals that efficiently fill the entire substrate vertically
            # Don't use artificial region restrictions - let spirals fill full height with controlled spacing

            # Generate positive spiral starting from top, filling downward
            positive_segments, pos_tag = self._generate_max_density_spiral(
                center_x=0, center_y=max_y * 0.9, target_length=target_length/2,
                max_x=max_x, max_y=max_y, direction='down',  # Start high, fill downward
                trace_width=trace_width, side_name='unified_positive',
                start_tag=gw_tag
            )

            # Generate negative spiral starting from bottom, filling upward
            negative_segments, neg_tag = self._generate_max_density_spiral(
                center_x=0, center_y=-max_y * 0.9, target_length=target_length/2,
                max_x=max_x, max_y=max_y, direction='up',  # Start low, fill upward
                trace_width=trace_width, side_name='unified_negative',
                start_tag=pos_tag
            )

            # Combine all segments
            geometry.extend(positive_segments)
            geometry.extend(negative_segments)

            # Add feed connection
            geometry.append(f"GW {neg_tag} 1 0 0 0 0 0 0 {trace_width:.4f}")

            result = "\n".join(geometry)
            logger.info(f"Generated unified substrate meander: {len(geometry)} segments, "
                       f"{len(result.split())} total lines")

            return result

        except Exception as e:
            logger.error(f"Unified substrate meander generation failed: {str(e)}")
            return ""

    def _generate_max_density_spiral(self, center_x: float, center_y: float, target_length: float,
                                   max_x: float, max_y: float, direction: str,
                                   trace_width: float, side_name: str, start_tag: int) -> tuple:
        """Generate a maximum-density spiral that fills the entire substrate with dense meanders.
        This version allows unlimited vertical range for optimal substrate utilization.

        Args:
            center_x, center_y: Center coordinates for spiral
            target_length: Target electrical length
            max_x, max_y: Maximum bounds (full substrate limits)
            direction: 'up' or 'down' - preferred direction but can go anywhere
            trace_width: Trace width
            side_name: Name for logging
            start_tag: Starting GW tag

        Returns:
            tuple: (geometry segments, final tag)
        """
        try:
            geometry = []
            gw_tag = start_tag
            current_length = 0.0
            current_x = center_x
            current_y = center_y

            # For maximum density, use the full available substrate area
            available_height = max_y * 2  # Total substrate height

            # Calculate minimum viable vertical spacing for maximum density
            min_vertical_spacing = trace_width * 1.2  # Reduced to maximize packing density
            segment_length = max_x * 0.98  # Use 98% of available width

            # Calculate maximum possible passes across entire substrate
            max_possible_passes = min(50, int(available_height / min_vertical_spacing))

            # Distribute passes evenly across available height for maximum utilization
            if max_possible_passes > 1:
                step_size = available_height / max_possible_passes
                # Ensure minimum spacing is maintained but maximize passes
                step_size = max(min_vertical_spacing, step_size)
            else:
                step_size = min_vertical_spacing

            logger.debug(f"{side_name} max density spiral: full substrate utilization, "
                        f"{max_possible_passes} max passes, step_size={step_size:.3f}\", "
                        f"segment_length={segment_length:.3f}\", start=({center_x:.2f}, {center_y:.2f})")

            meander_pass = 0
            horizontal_direction = 1

            # Fill the substrate completely in a dense meander pattern
            # Continue until we've generated sufficient length or hit maximum passes
            while (current_length < target_length * 1.2) and (meander_pass < max_possible_passes):
                # Check if we've reached substrate bounds
                if abs(current_y) >= max_y:
                    logger.debug(f"{side_name} reached substrate boundary at y={current_y:.3f}, stopping")
                    break

                # Horizontal segment - use full available width per pass
                segment_end_x = current_x + horizontal_direction * segment_length

                # Clamp to substrate horizontal bounds
                if abs(segment_end_x) > max_x:
                    segment_end_x = max_x if horizontal_direction > 0 else -max_x

                segment_length_actual = abs(segment_end_x - current_x)

                # Always create horizontal segment if meaningful
                if segment_length_actual > 0.001:
                    geometry.append(f"GW {gw_tag} 1 {current_x:.4f} {current_y:.4f} 0 "
                                   f"{segment_end_x:.4f} {current_y:.4f} 0 {trace_width:.4f}")
                    gw_tag += 1
                    current_length += segment_length_actual

                current_x = segment_end_x

                # Add vertical segment to fill more height
                # Use preferred direction but switch if needed to stay within bounds
                if direction == 'up':
                    preferred_next_y = current_y + step_size
                    # Switch to down if we'd exceed bounds
                    if preferred_next_y > max_y:
                        preferred_next_y = current_y - step_size
                else:
                    preferred_next_y = current_y - step_size
                    # Switch to up if we'd exceed bounds
                    if preferred_next_y < -max_y:
                        preferred_next_y = current_y + step_size

                # Only add vertical segment if within substrate bounds
                if abs(preferred_next_y) <= max_y:
                    segment_length_vertical = abs(preferred_next_y - current_y)

                    if segment_length_vertical > 0.001:
                        geometry.append(f"GW {gw_tag} 1 {current_x:.4f} {current_y:.4f} 0 "
                                       f"{current_x:.4f} {preferred_next_y:.4f} 0 {trace_width:.4f}")
                        gw_tag += 1
                        current_length += segment_length_vertical
                        current_y = preferred_next_y
                        horizontal_direction *= -1  # Reverse direction for next pass
                    else:
                        logger.debug(f"{side_name} cannot move vertically at pass {meander_pass}, stopping")
                        break
                else:
                    logger.debug(f"{side_name} vertical move would exceed substrate at pass {meander_pass}, stopping")
                    break

                meander_pass += 1

                # Emergency break for runaway generation (shouldn't normally hit this)
                if meander_pass >= max_possible_passes:
                    logger.warning(f"{side_name} reached maximum passes ({max_possible_passes}) at length {current_length:.2f}\"")
                    break

            # Calculate final utilization metrics (across entire substrate)
            final_y_span = abs(current_y - center_y)*2 + step_size  # Actual span used
            height_utilization = min(100.0, (final_y_span / available_height) * 100)
            width_utilization = min(100.0, (segment_length / (max_x * 2)) * 100)
            overall_utilization = (height_utilization + width_utilization) / 2

            logger.info(f"{side_name} max density spiral: {len(geometry)} segments, "
                       f"length={current_length:.2f}\" ({current_length/target_length*100:.1f}% of target), "
                       f"passes={meander_pass}, height_util={height_utilization:.1f}%, "
                       f"width_util={width_utilization:.1f}%, overall={overall_utilization:.1f}%")

            return geometry, gw_tag

        except Exception as e:
            logger.error(f"Max density spiral generation failed for {side_name}: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return [], start_tag
