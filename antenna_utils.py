"""Shared utilities for antenna drawing and visualization functionality.

This module consolidates repeated functionality across the antenna design codebase,
providing unified interfaces for NEC2 geometry parsing, visualization, and validation.
"""

from typing import List, Tuple, Optional, Dict, Any
import math
import numpy as np
from loguru import logger

class NEC2GeometryParser:
    """Unified NEC2 geometry parsing with validation and analysis."""

    @staticmethod
    def parse_geometry(geometry: str) -> List[Tuple[float, float, float, float, float]]:
        """Parse NEC2 geometry string into wire segments.
        
        Args:
            geometry: NEC2 geometry string with GW cards
            
        Returns:
            List of (x1, y1, x2, y2, radius) tuples for each wire segment
            
        Raises:
            ValueError: If geometry string is invalid or empty
        """
        try:
            if not geometry or not geometry.strip():
                raise ValueError("Empty geometry string provided")

            segments = []
            lines = geometry.split('\n')
            tag_offset = 0

            for line in lines:
                if not line.strip():
                    continue

                parts = line.split()
                if len(parts) >= 8 and parts[0] == 'GW':
                    # Parse GW card: GW tag segments x1 y1 z1 x2 y2 z2 radius
                    try:
                        tag = int(float(parts[1]))
                        segments_count = int(float(parts[2]))
                        x1 = float(parts[3])
                        y1 = float(parts[4])
                        z1 = float(parts[5])  # Usually 0 for planar antennas
                        x2 = float(parts[6])
                        y2 = float(parts[7])
                        z2 = float(parts[8])  # Usually 0 for planar antennas
                        radius = float(parts[9]) if len(parts) > 9 else 0.005  # Default 5 mil

                        segments.append((x1, y1, x2, y2, radius))

                    except (ValueError, IndexError) as e:
                        logger.warning(f"Failed to parse GW line: {line} - {str(e)}")
                        continue

                elif len(parts) >= 4 and parts[0] == 'SP':
                    # Handle surface patches (SP cards)
                    try:
                        patch_segments = NEC2GeometryParser._surface_patch_to_wires(parts)
                        segments.extend(patch_segments)
                    except Exception as e:
                        logger.warning(f"Failed to parse SP line: {line} - {str(e)}")
                        continue

            if not segments:
                logger.warning("No valid wire segments found in geometry")

            logger.debug(f"Parsed {len(segments)} wire segments from geometry")
            return segments

        except Exception as e:
            logger.error(f"Geometry parsing error: {str(e)}")
            raise ValueError(f"Failed to parse NEC2 geometry: {str(e)}") from e

    @staticmethod
    def _surface_patch_to_wires(sp_parts: List[str]) -> List[Tuple[float, float, float, float, float]]:
        """Convert surface patch (SP) to outline wires."""
        try:
            # SP format: SP tag segments x1 y1 z1 x2 y2 z2 x3 y3 z3 x4 y4 z4
            coords = []
            i = 3  # Skip SP tag segments
            while i < len(sp_parts) - 2:
                x = float(sp_parts[i])
                y = float(sp_parts[i+1])
                z = float(sp_parts[i+2])  # Usually 0 for planar
                coords.append((x, y))
                i += 3

            # Create wire segments for patch outline
            segments = []
            radius = 0.005  # Default radius for patches

            if len(coords) >= 3:
                for i in range(len(coords)):
                    x1, y1 = coords[i]
                    x2, y2 = coords[(i + 1) % len(coords)]
                    segments.append((x1, y1, x2, y2, radius))

            return segments

        except Exception as e:
            logger.warning(f"Surface patch to wires conversion error: {str(e)}")
            return []

    @staticmethod
    def calculate_total_length(segments: List[Tuple[float, ...]]) -> float:
        """Calculate total trace length from wire segments.

        Args:
            segments: List of (x1, y1, x2, y2) or (x1, y1, x2, y2, radius) tuples

        Returns:
            float: Total trace length in inches
        """
        try:
            total_length = 0.0
            for seg in segments:
                x1, y1, x2, y2 = seg[0], seg[1], seg[2], seg[3]
                segment_length = math.sqrt((x2-x1)**2 + (y2-y1)**2)
                total_length += segment_length
            return total_length
        except Exception as e:
            logger.error(f"Total length calculation error: {str(e)}")
            return 0.0

    @staticmethod
    def extract_bounds(segments: List[Tuple[float, ...]]) -> Tuple[float, float, float, float]:
        """Calculate bounding box for wire segments.

        Args:
            segments: List of (x1, y1, x2, y2) or (x1, y1, x2, y2, radius) tuples

        Returns:
            Tuple of (min_x, min_y, max_x, max_y)
        """
        try:
            if not segments:
                return 0, 0, 0, 0

            all_x = []
            all_y = []
            for seg in segments:
                x1, y1, x2, y2 = seg[0], seg[1], seg[2], seg[3]
                all_x.extend([x1, x2])
                all_y.extend([y1, y2])

            return min(all_x), min(all_y), max(all_x), max(all_y)
        except Exception as e:
            logger.error(f"Bounds calculation error: {str(e)}")
            return 0, 0, 0, 0

    @staticmethod
    def calculate_segment_length(gw_line: str) -> float:
        """Calculate physical length of a wire segment from GW line.
        
        Args:
            gw_line: NEC2 GW geometry card string
            
        Returns:
            float: Physical length of the segment in inches
        """
        try:
            parts = gw_line.split()
            if len(parts) >= 8:
                x1, y1, z1 = float(parts[3]), float(parts[4]), float(parts[5])
                x2, y2, z2 = float(parts[6]), float(parts[7]), float(parts[8])
                return math.sqrt((x2-x1)**2 + (y2-y1)**2 + (z2-z1)**2)
            return 0.0
        except (ValueError, IndexError):
            return 0.0


class AntennaVisualizer:
    """Unified visualization with multiple output modes and advanced rendering."""

    def __init__(self, mode: str = 'production'):
        """Initialize visualizer with output mode.
        
        Args:
            mode: Output mode - 'debug', 'analysis', 'production'
        """
        self.mode = mode
        self.scale = 100  # SVG units per inch (default)
        self.precision = 4  # Decimal places for coordinates
        
        # Mode-specific styling
        self.styles = {
            'debug': {
                'background': 'white',
                'trace_color': 'black',
                'trace_width': 2,
                'show_labels': True,
                'show_grid': True
            },
            'analysis': {
                'background': 'lightgray',
                'trace_color': 'blue',
                'trace_width': 3,
                'show_labels': True,
                'show_grid': False
            },
            'production': {
                'background': 'white',
                'trace_color': 'black',
                'trace_width': 4,
                'show_labels': True,
                'show_grid': False
            }
        }

    def render_ascii(self, segments: List[Tuple[float, float, float, float, float]], 
                    width: int = 80, height: int = 25) -> str:
        """Generate ASCII art representation of antenna pattern.
        
        Args:
            segments: List of wire segment tuples (x1, y1, x2, y2, radius)
            width, height: ASCII canvas dimensions
            
        Returns:
            str: ASCII art representation
        """
        try:
            if not segments:
                return "No segments to render"

            # Calculate bounds and scaling
            min_x, min_y, max_x, max_y = NEC2GeometryParser.extract_bounds(segments)
            width_range = max_x - min_x
            height_range = max_y - min_y

            if width_range == 0 or height_range == 0:
                return "Invalid geometry bounds"

            # Create ASCII canvas
            canvas = [[' ' for _ in range(width)] for _ in range(height)]

            # Scaling function
            def scale_x(x):
                return int((x - min_x) / (width_range + 0.001) * (width - 4)) + 2

            def scale_y(y):
                return int((y - min_y) / (height_range + 0.001) * (height - 4)) + 2

            # Draw segments using Bresenham's algorithm
            for seg_idx, (x1, y1, x2, y2, radius) in enumerate(segments):
                px1, py1 = scale_x(x1), scale_y(y1)
                px2, py2 = scale_x(x2), scale_y(y2)

                # Draw line using Bresenham's algorithm
                points = self._get_line_points(px1, py1, px2, py2)
                for px, py in points:
                    if 0 <= px < width and 0 <= py < height:
                        if canvas[py][px] == ' ':
                            canvas[py][px] = '#'
                        elif canvas[py][px] == '#':
                            canvas[py][px] = '+'  # Intersection point

            # Mark feed point (origin)
            feed_x, feed_y = scale_x(0), scale_y(0)
            if 0 <= feed_x < width and 0 <= feed_y < height:
                canvas[feed_y][feed_x] = 'F'

            # Convert to string with mode-specific header
            ascii_art = []
            header = self._get_ascii_header(segments, width_range, height_range)
            ascii_art.append(header)

            for row in canvas:
                ascii_art.append(''.join(row))

            return '\n'.join(ascii_art)

        except Exception as e:
            logger.error(f"ASCII rendering error: {str(e)}")
            return f"Error rendering ASCII: {str(e)}"

    def _get_line_points(self, x1: int, y1: int, x2: int, y2: int) -> List[Tuple[int, int]]:
        """Get all points on a line using Bresenham's algorithm."""
        points = []
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy

        x, y = x1, y1
        while True:
            points.append((x, y))
            if x == x2 and y == y2:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

        return points

    def _get_ascii_header(self, segments: List[Tuple], width_range: float, height_range: float) -> str:
        """Generate ASCII header with analysis information."""
        total_length = NEC2GeometryParser.calculate_total_length(segments)
        segment_count = len(segments)
        
        if self.mode == 'debug':
            header = f"""
DEBUG ANTENNA VISUALIZATION
===========================
Segments: {segment_count}
Total Length: {total_length:.3f}"
Bounds: {width_range:.3f}" x {height_range:.3f}"
Legend: # = Trace, F = Feed Point, + = Intersection
"""
        elif self.mode == 'analysis':
            header = f"""
ANTENNA PATTERN ANALYSIS
========================
Segments: {segment_count}
Total Length: {total_length:.3f}"
Bounds: {width_range:.3f}" x {height_range:.3f}"
Pattern Analysis Active
"""
        else:  # production
            header = f"""
PRODUCTION ANTENNA LAYOUT
=========================
Segments: {segment_count}
Total Length: {total_length:.3f}"
Bounds: {width_range:.3f}" x {height_range:.3f}"
Ready for Manufacturing
"""

        return header

    def generate_svg(self, segments: List[Tuple[float, float, float, float, float]], 
                    metadata: Optional[Dict[str, Any]] = None) -> str:
        """Generate SVG visualization with mode-specific styling.
        
        Args:
            segments: List of wire segment tuples (x1, y1, x2, y2, radius)
            metadata: Optional metadata for annotations
            
        Returns:
            str: SVG content
        """
        try:
            if not segments:
                return self._get_empty_svg()

            # Calculate bounds and transform coordinates
            min_x, min_y, max_x, max_y = NEC2GeometryParser.extract_bounds(segments)
            total_width = max_x - min_x
            total_height = max_y - min_y

            # Add margins for labels
            margin = 0.2  # 0.2 inch margin for labels
            label_space = 0.8  # Space for trace validation info
            width = (total_width + 2 * margin + label_space) * self.scale
            height = (total_height + 2 * margin) * self.scale

            # Transform function for coordinates
            def transform(x, y):
                return ((x - min_x + margin) * self.scale,
                       height - ((y - min_y + margin) * self.scale))

            # Generate SVG paths with mode-specific styling
            paths = self._generate_svg_paths(segments, transform)
            paths_str = '\n    '.join(paths)

            # Generate annotations based on mode
            annotations = self._generate_svg_annotations(segments, transform, 
                                                       total_width, total_height, metadata)

            # Generate SVG with mode-specific styling
            style_defs = self._get_svg_styles()
            svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width:.1f}" height="{height:.1f}" viewBox="0 0 {width:.1f} {height:.1f}" xmlns="http://www.w3.org/2000/svg">
  <title>Antenna Visualization - {self.mode.title()} Mode</title>
  <desc>Generated by Mini Antenna Designer</desc>
  
  {style_defs}
  
  <!-- Background -->
  <rect width="{width:.1f}" height="{height:.1f}" fill="{self.styles[self.mode]['background']}" stroke="black" stroke-width="2"/>
  
  <!-- Grid lines for alignment (debug mode only) -->
  {self._generate_grid_lines(width, height, transform) if self.styles[self.mode]['show_grid'] else ''}
  
  <!-- Antenna wire segments -->
  <g stroke-linecap="round" stroke-linejoin="round" id="antenna-traces">
    {paths_str}
  </g>
  
  <!-- Professional annotations -->
  {annotations}
  
  <!-- Origin marker (feed point) -->
  <circle cx="{transform(0, 0)[0]:.1f}" cy="{transform(0, 0)[1]:.1f}" r="8" class="feed-point"/>
  <text x="{transform(0, 0)[0] + 15:.1f}" y="{transform(0, 0)[1]:.1f}" class="label-text">FEED POINT</text>
  
</svg>'''

            return svg

        except Exception as e:
            logger.error(f"SVG generation error: {str(e)}")
            return self._get_empty_svg()

    def _generate_svg_paths(self, segments: List[Tuple], transform_func) -> List[str]:
        """Generate SVG path elements for wire segments."""
        paths = []
        style = self.styles[self.mode]
        stroke_width = style['trace_width']

        for i, (x1, y1, x2, y2, radius) in enumerate(segments):
            tx1, ty1 = transform_func(x1, y1)
            tx2, ty2 = transform_func(x2, y2)
            stroke_color = style['trace_color']

            path = f'M {tx1:.{self.precision}f} {ty1:.{self.precision}f} L {tx2:.{self.precision}f} {ty2:.{self.precision}f}'
            paths.append(f'<path d="{path}" stroke="{stroke_color}" stroke-width="{stroke_width}" fill="none"/>')

        return paths

    def _generate_svg_annotations(self, segments: List[Tuple], transform_func,
                               total_width: float, total_height: float, 
                               metadata: Optional[Dict] = None) -> str:
        """Generate SVG annotations based on visualization mode."""
        try:
            annotations = []
            style = self.styles[self.mode]

            # Title and mode information
            title_x = 20
            title_y = 30
            annotations.append(f'<text x="{title_x}" y="{title_y}" class="title-text">{self.mode.upper()} MODE</text>')

            # Mode-specific information
            if self.mode == 'debug':
                annotations.extend(self._get_debug_annotations(title_y + 40, segments, total_width, total_height))
            elif self.mode == 'analysis':
                annotations.extend(self._get_analysis_annotations(title_y + 40, segments, total_width, total_height))
            else:  # production
                annotations.extend(self._get_production_annotations(title_y + 40, segments, total_width, total_height, metadata))

            # Dimension lines (all modes)
            annotations.append(self._generate_dimension_lines(total_width, total_height, transform_func))

            return '\n  '.join(annotations)

        except Exception as e:
            logger.warning(f"SVG annotations generation failed: {str(e)}")
            return ""

    def _get_debug_annotations(self, start_y: float, segments: List[Tuple], 
                             total_width: float, total_height: float) -> List[str]:
        """Generate debug-specific annotations."""
        annotations = []
        annotations.append(f'<text x="20" y="{start_y}" class="label-text">DEBUG INFORMATION:</text>')
        annotations.append(f'<text x="20" y="{start_y + 15}" class="dimension-text">Segment Count: {len(segments)}</text>')
        annotations.append(f'<text x="20" y="{start_y + 30}" class="dimension-text">Total Length: {NEC2GeometryParser.calculate_total_length(segments):.3f}"</text>')
        annotations.append(f'<text x="20" y="{start_y + 45}" class="dimension-text">Bounds: {total_width:.3f}" x {total_height:.3f}"</text>')
        return annotations

    def _get_analysis_annotations(self, start_y: float, segments: List[Tuple], 
                                total_width: float, total_height: float) -> List[str]:
        """Generate analysis-specific annotations."""
        annotations = []
        annotations.append(f'<text x="20" y="{start_y}" class="label-text">PATTERN ANALYSIS:</text>')
        annotations.append(f'<text x="20" y="{start_y + 15}" class="dimension-text">Pattern Type: {self._detect_pattern_type(segments)}</text>')
        annotations.append(f'<text x="20" y="{start_y + 30}" class="dimension-text">Connectivity: {self._check_connectivity(segments)}</text>')
        annotations.append(f'<text x="20" y="{start_y + 45}" class="dimension-text">Space Utilization: {self._calculate_space_utilization(segments, total_width, total_height):.1f}%</text>')
        return annotations

    def _get_production_annotations(self, start_y: float, segments: List[Tuple], 
                                  total_width: float, total_height: float,
                                  metadata: Optional[Dict] = None) -> List[str]:
        """Generate production-specific annotations."""
        annotations = []
        annotations.append(f'<text x="20" y="{start_y}" class="label-text">MANUFACTURING INFO:</text>')
        annotations.append(f'<text x="20" y="{start_y + 15}" class="dimension-text">Design Width: {total_width:.3f}" ({total_width*1000:.0f} mils)</text>')
        annotations.append(f'<text x="20" y="{start_y + 30}" class="dimension-text">Design Height: {total_height:.3f}" ({total_height*1000:.0f} mils)</text>')
        annotations.append(f'<text x="20" y="{start_y + 45}" class="dimension-text">Scale: 1:1 (ready for production)</text>')
        
        if metadata:
            if 'band_name' in metadata:
                annotations.append(f'<text x="20" y="{start_y + 60}" class="dimension-text">Band: {metadata["band_name"]}</text>')
            if 'freq1_mhz' in metadata:
                freq_range = f"{metadata['freq1_mhz']:.0f}-{metadata.get('freq3_mhz', metadata['freq1_mhz']):.0f} MHz"
                annotations.append(f'<text x="20" y="{start_y + 75}" class="dimension-text">Frequency: {freq_range}</text>')
        
        return annotations

    def _detect_pattern_type(self, segments: List[Tuple]) -> str:
        """Detect the type of antenna pattern."""
        if len(segments) < 3:
            return "Simple"

        # Count direction changes
        horizontal_segments = 0
        vertical_segments = 0

        for x1, y1, x2, y2, _ in segments:
            dx = abs(x2 - x1)
            dy = abs(y2 - y1)

            if dx > dy:
                horizontal_segments += 1
            else:
                vertical_segments += 1

        if horizontal_segments > vertical_segments * 2:
            return "Horizontal"
        elif vertical_segments > horizontal_segments * 2:
            return "Vertical"
        elif horizontal_segments > 5 and vertical_segments > 5:
            return "Spiral/Meander"
        else:
            return "Mixed"

    def _check_connectivity(self, segments: List[Tuple]) -> str:
        """Check pattern connectivity."""
        if not segments:
            return "No segments"

        # Simple connectivity check - count isolated segments
        isolated_count = 0
        for i, seg1 in enumerate(segments):
            is_connected = False
            for j, seg2 in enumerate(segments):
                if i != j and self._segments_connected(seg1, seg2):
                    is_connected = True
                    break
            if not is_connected:
                isolated_count += 1

        if isolated_count == 0:
            return "Fully connected"
        elif isolated_count < len(segments) * 0.1:  # Less than 10% isolated
            return "Mostly connected"
        else:
            return f"{isolated_count} isolated segments"

    def _segments_connected(self, seg1: Tuple, seg2: Tuple) -> bool:
        """Check if two segments are connected."""
        x1, y1, x2, y2, _ = seg1
        x3, y3, x4, y4, _ = seg2

        # Check if endpoints match (within tolerance)
        tolerance = 0.001
        endpoints1 = [(x1, y1), (x2, y2)]
        endpoints2 = [(x3, y3), (x4, y4)]

        for p1 in endpoints1:
            for p2 in endpoints2:
                distance = math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)
                if distance < tolerance:
                    return True
        return False

    def _calculate_space_utilization(self, segments: List[Tuple], width: float, height: float) -> float:
        """Calculate space utilization percentage."""
        if width <= 0 or height <= 0:
            return 0.0

        total_length = NEC2GeometryParser.calculate_total_length(segments)
        trace_width = 0.010  # Default trace width
        total_area = width * height
        trace_area = total_length * trace_width

        return min(100.0, (trace_area / total_area) * 100)

    def _generate_grid_lines(self, width: float, height: float, transform_func) -> str:
        """Generate alignment grid lines for debug mode."""
        try:
            grid_lines = []
            grid_spacing = 0.5 * self.scale  # 0.5 inch grid

            # Vertical lines
            for x in range(0, int(width), int(grid_spacing)):
                grid_lines.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{height}" stroke="#e0e0e0" stroke-width="0.5" opacity="0.5"/>')

            # Horizontal lines
            for y in range(0, int(height), int(grid_spacing)):
                grid_lines.append(f'<line x1="0" y1="{y}" x2="{width}" y2="{y}" stroke="#e0e0e0" stroke-width="0.5" opacity="0.5"/>')

            return '\n    '.join(grid_lines)
        except Exception as e:
            logger.warning(f"Grid lines generation failed: {str(e)}")
            return ""

    def _generate_dimension_lines(self, total_width: float, total_height: float, transform_func) -> str:
        """Generate dimension lines for the antenna."""
        try:
            dimensions = []
            origin_x, origin_y = transform_func(0, 0)

            # Width dimension line (bottom)
            width_start = transform_func(-total_width/2, -total_height/2 - 0.3)
            width_end = transform_func(total_width/2, -total_height/2 - 0.3)
            dimensions.append(f'<line x1="{width_start[0]:.1f}" y1="{width_start[1]:.1f}" x2="{width_end[0]:.1f}" y2="{width_end[1]:.1f}" class="dimension-line"/>')
            dimensions.append(f'<line x1="{width_start[0]:.1f}" y1="{width_start[1]-5:.1f}" x2="{width_start[0]:.1f}" y2="{width_start[1]+5:.1f}" class="dimension-line"/>')
            dimensions.append(f'<line x1="{width_end[0]:.1f}" y1="{width_end[1]-5:.1f}" x2="{width_end[0]:.1f}" y2="{width_end[1]+5:.1f}" class="dimension-line"/>')

            # Height dimension line (right side)
            height_start = transform_func(total_width/2 + 0.3, -total_height/2)
            height_end = transform_func(total_width/2 + 0.3, total_height/2)
            dimensions.append(f'<line x1="{height_start[0]:.1f}" y1="{height_start[1]:.1f}" x2="{height_end[0]:.1f}" y2="{height_end[1]:.1f}" class="dimension-line"/>')
            dimensions.append(f'<line x1="{height_start[0]-5:.1f}" y1="{height_start[1]:.1f}" x2="{height_start[0]+5:.1f}" y2="{height_start[1]:.1f}" class="dimension-line"/>')
            dimensions.append(f'<line x1="{height_end[0]-5:.1f}" y1="{height_end[1]:.1f}" x2="{height_end[0]+5:.1f}" y2="{height_end[1]:.1f}" class="dimension-line"/>')

            return '\n  '.join(dimensions)
        except Exception as e:
            logger.warning(f"Dimension lines generation failed: {str(e)}")
            return ""

    def _get_svg_styles(self) -> str:
        """Generate SVG style definitions based on mode."""
        style = self.styles[self.mode]
        return f'''<defs>
    <style>
      .dimension-text {{ font-family: Arial, sans-serif; font-size: 12px; fill: #333; }}
      .label-text {{ font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; fill: #000; }}
      .title-text {{ font-family: Arial, sans-serif; font-size: 18px; font-weight: bold; fill: #000; }}
      .subtitle-text {{ font-family: Arial, sans-serif; font-size: 12px; fill: #666; }}
      .dimension-line {{ stroke: #666; stroke-width: 1; fill: none; }}
      .feed-point {{ fill: red; stroke: darkred; stroke-width: 2; }}
    </style>
  </defs>'''

    def _get_empty_svg(self) -> str:
        """Generate empty SVG for error cases."""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="400" height="200" viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">
  <text x="200" y="100" text-anchor="middle" font-family="Arial" font-size="16" fill="red">
    Error: No geometry to visualize
  </text>
</svg>'''


class AntennaValidator:
    """Unified validation for different use cases with configurable constraints."""

    @staticmethod
    def validate_for_etching(geometry: str, constraints: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Validate design against laser etching constraints.
        
        Args:
            geometry: NEC2 geometry string
            constraints: Validation constraints dictionary
            
        Returns:
            dict: Validation results with warnings and readiness status
        """
        try:
            if constraints is None:
                constraints = {}

            # Default constraints
            min_feature_size = constraints.get('min_feature_size', 0.005)  # 5 mil
            min_spacing = constraints.get('min_spacing', 0.010)  # 10 mil
            max_trace_width = constraints.get('max_trace_width', 0.050)  # 50 mil
            substrate_width = constraints.get('substrate_width', 4.0)
            substrate_height = constraints.get('substrate_height', 2.0)

            validation = {
                'minimum_feature_size': True,
                'trace_width_consistent': True,
                'isolation_clearance': True,
                'total_area': 0.0,
                'complexity_score': 0,
                'warnings': [],
                'etching_ready': True,
                'element_count': 0
            }

            # Parse geometry
            segments = NEC2GeometryParser.parse_geometry(geometry)
            validation['element_count'] = len(segments)

            if not segments:
                validation['warnings'].append("No valid antenna elements found in geometry")
                validation['etching_ready'] = False
                return validation

            # Analyze segments
            min_radius = float('inf')
            trace_widths = []
            total_length = 0
            wire_count = 0

            for x1, y1, x2, y2, radius in segments:
                min_radius = min(min_radius, radius)
                trace_widths.append(radius)
                wire_count += 1

                # Calculate actual segment length
                segment_length = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
                total_length += segment_length

            # Check minimum feature size
            validation['minimum_feature_size'] = min_radius >= min_feature_size
            if not validation['minimum_feature_size']:
                validation['warnings'].append(f"Some features may be below minimum laser resolution ({min_feature_size*1000:.0f} mil)")

            # Check trace width consistency
            unique_widths = set(f"{w:.3f}" for w in trace_widths)
            validation['trace_width_consistent'] = len(unique_widths) <= 3
            if not validation['trace_width_consistent']:
                validation['warnings'].append(f"Multiple trace widths detected ({len(unique_widths)} different widths)")

            # Check isolation clearance
            validation['isolation_clearance'] = min_radius >= min_spacing
            if not validation['isolation_clearance']:
                validation['warnings'].append(f"Trace spacing below recommended minimum ({min_spacing*1000:.0f} mil)")

            # Calculate metrics
            validation['total_area'] = total_length * 0.005  # Rough estimate
            validation['complexity_score'] = min(wire_count // 10, 4)  # Cap at 4

            # Check dimensions
            dims = AntennaValidator._calculate_dimensions(segments, substrate_width, substrate_height)
            if dims['width'] > substrate_width or dims['height'] > substrate_height:
                validation['warnings'].append(f"Antenna exceeds substrate dimensions: {dims['width']:.3f}\" x {dims['height']:.3f}\" > {substrate_width}\" x {substrate_height}\"")
                validation['etching_ready'] = False

            # Check connectivity
            connectivity = AntennaValidator._check_connectivity(segments)
            validation['component_count'] = connectivity['components']
            if connectivity['components'] > 5 and wire_count > 10:
                validation['warnings'].append(f"High fragmentation detected: {connectivity['components']} disconnected parts")

            if connectivity['isolated_segments'] > 0:
                validation['warnings'].append(f"Found {connectivity['isolated_segments']} isolated single-segment wires")

            # Overall readiness
            if validation['warnings']:
                validation['etching_ready'] = False

            return validation

        except Exception as e:
            logger.error(f"Etching validation error: {str(e)}")
            return {
                'warnings': [f"Validation error: {str(e)}"],
                'etching_ready': False,
                'element_count': 0
            }

    @staticmethod
    def validate_geometry_bounds(geometry: str, max_width: float, max_height: float) -> Dict[str, Any]:
        """Validate geometry fits within specified bounds.
        
        Args:
            geometry: NEC2 geometry string
            max_width: Maximum allowed width in inches
            max_height: Maximum allowed height in inches
            
        Returns:
            dict: Validation results
        """
        try:
            segments = NEC2GeometryParser.parse_geometry(geometry)
            min_x, min_y, max_x, max_y = NEC2GeometryParser.extract_bounds(segments)

            width = max_x - min_x
            height = max_y - min_y

            validation = {
                'within_bounds': True,
                'max_x': max_x,
                'max_y': max_y,
                'width': width,
                'height': height,
                'warnings': []
            }

            if width > max_width:
                validation['within_bounds'] = False
                validation['warnings'].append(f"Width exceeds limit: {width:.3f} > {max_width:.3f}")

            if height > max_height:
                validation['within_bounds'] = False
                validation['warnings'].append(f"Height exceeds limit: {height:.3f} > {max_height:.3f}")

            return validation

        except Exception as e:
            logger.error(f"Bounds validation error: {str(e)}")
            return {
                'within_bounds': False,
                'warnings': [f"Bounds validation error: {str(e)}"]
            }

    @staticmethod
    def check_trace_widths(segments: List[Tuple[float, float, float, float, float]], 
                         min_width: float = 0.005) -> Dict[str, Any]:
        """Validate trace widths for manufacturability.
        
        Args:
            segments: List of wire segment tuples (x1, y1, x2, y2, radius)
            min_width: Minimum acceptable trace width in inches
            
        Returns:
            dict: Validation results with status per trace and summary
        """
        try:
            validation = {
                'trace_status': [],  # List of 'good', 'warning', 'error' for each trace
                'trace_widths_mils': [],
                'min_trace_width': float('inf'),
                'max_trace_width': 0,
                'avg_trace_width': 0,
                'manufacturing_warnings': [],
                'manufacturing_errors': [],
                'overall_status': 'good'
            }

            trace_widths_mils = []

            for segment in segments:
                x1, y1, x2, y2, radius = segment
                trace_width_mils = radius * 1000  # Convert inches to mils
                trace_widths_mils.append(trace_width_mils)

                # Determine validation status
                if trace_width_mils < 5.0:
                    status = 'error'
                    validation['manufacturing_errors'].append(f"Trace width {trace_width_mils:.1f} mil below absolute minimum (5 mil)")
                elif trace_width_mils < 8.0:
                    status = 'warning'
                    validation['manufacturing_warnings'].append(f"Trace width {trace_width_mils:.1f} mil below recommended minimum (8 mil)")
                elif trace_width_mils > 50.0:
                    status = 'warning'
                    validation['manufacturing_warnings'].append(f"Trace width {trace_width_mils:.1f} mil very thick (may reduce performance)")
                else:
                    status = 'good'

                validation['trace_status'].append(status)
                validation['trace_widths_mils'].append(trace_width_mils)

            # Calculate summary statistics
            if trace_widths_mils:
                validation['min_trace_width'] = min(trace_widths_mils)
                validation['max_trace_width'] = max(trace_widths_mils)
                validation['avg_trace_width'] = sum(trace_widths_mils) / len(trace_widths_mils)

            # Determine overall status
            if any(s == 'error' for s in validation['trace_status']):
                validation['overall_status'] = 'error'
            elif any(s == 'warning' for s in validation['trace_status']):
                validation['overall_status'] = 'warning'
            else:
                validation['overall_status'] = 'good'

            return validation

        except Exception as e:
            logger.error(f"Trace width validation failed: {str(e)}")
            return {
                'trace_status': ['error'] * len(segments),
                'overall_status': 'error',
                'manufacturing_errors': [f"Validation error: {str(e)}"]
            }

    @staticmethod
    def _calculate_dimensions(segments: List[Tuple], max_width: float, max_height: float) -> Dict[str, float]:
        """Calculate total width and height of geometry relative to substrate."""
        if not segments:
            return {'width': 0, 'height': 0}

        x_coords = []
        y_coords = []
        for x1, y1, x2, y2, _ in segments:
            x_coords.extend([x1, x2])
            y_coords.extend([y1, y2])

        return {
            'width': max(x_coords) - min(x_coords),
            'height': max(y_coords) - min(y_coords)
        }

    @staticmethod
    def _check_connectivity(segments: List[Tuple]) -> Dict[str, int]:
        """Analyze connectivity of wire segments."""
        if not segments:
            return {'components': 0, 'isolated_segments': 0}

        # Build adjacency graph
        adj = {}

        def add_node(pt):
            # Round coordinates to avoid float precision issues
            key = (round(pt[0], 4), round(pt[1], 4))
            if key not in adj:
                adj[key] = []
            return key

        for x1, y1, x2, y2, _ in segments:
            p1 = add_node((x1, y1))
            p2 = add_node((x2, y2))
            adj[p1].append(p2)
            adj[p2].append(p1)

        # Count connected components
        visited = set()
        components = 0
        isolated_count = 0

        for node in adj:
            if node not in visited:
                components += 1
                # BFS to find component size
                component_nodes = 0
                queue = [node]
                visited.add(node)
                while queue:
                    curr = queue.pop(0)
                    component_nodes += 1
                    for neighbor in adj[curr]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)

                # Check if isolated (2 nodes connected to each other only, i.e. 1 segment)
                if component_nodes <= 2:
                    isolated_count += 1

        return {
            'components': components,
            'isolated_segments': isolated_count
        }


# Convenience functions for backward compatibility
def parse_nec2_geometry(geometry: str) -> List[Tuple[float, float, float, float, float]]:
    """Convenience function for NEC2 geometry parsing."""
    try:
        return NEC2GeometryParser.parse_geometry(geometry)
    except Exception:
        return []

def draw_ascii_meander(segments: List[Tuple[float, ...]],
                      width: int = 80, height: int = 25) -> str:
    """Convenience function for ASCII meander visualization.

    Args:
        segments: List of (x1, y1, x2, y2) or (x1, y1, x2, y2, radius) tuples
        width: ASCII art width in characters
        height: ASCII art height in characters

    Returns:
        ASCII art string
    """
    try:
        # Convert to 5-tuple format if needed
        segments_5: List[Tuple[float, float, float, float, float]] = []
        if len(segments) > 0:
            if len(segments[0]) == 4:
                for seg in segments:
                    segments_5.append((seg[0], seg[1], seg[2], seg[3], 0.005))
            else:
                for seg in segments:
                    segments_5.append((seg[0], seg[1], seg[2], seg[3], seg[4]))

        visualizer = AntennaVisualizer(mode='debug')
        return visualizer.render_ascii(segments_5, width, height)
    except Exception as e:
        logger.error(f"ASCII rendering error: {str(e)}")
        return "Error rendering ASCII visualization"

def generate_simple_svg(segments: List[Tuple[float, ...]],
                       filename: str = "meander_debug.svg",
                       scale: float = 100.0) -> str:
    """Convenience function for simple SVG generation.

    Args:
        segments: List of (x1, y1, x2, y2) or (x1, y1, x2, y2, radius) tuples
        filename: Output SVG filename
        scale: SVG units per inch (ignored, kept for compatibility)

    Returns:
        SVG content string
    """
    try:
        # Convert to 5-tuple format if needed
        segments_5: List[Tuple[float, float, float, float, float]] = []
        if len(segments) > 0:
            if len(segments[0]) == 4:
                for seg in segments:
                    segments_5.append((seg[0], seg[1], seg[2], seg[3], 0.005))
            else:
                for seg in segments:
                    segments_5.append((seg[0], seg[1], seg[2], seg[3], seg[4]))

        visualizer = AntennaVisualizer(mode='debug')
        svg_content = visualizer.generate_svg(segments_5)

        # Write to file if filename provided
        if filename:
            with open(filename, 'w') as f:
                f.write(svg_content)
            logger.info(f"SVG written to: {filename}")

        return svg_content
    except Exception as e:
        logger.error(f"SVG generation error: {str(e)}")
        return '<svg><text>Error generating SVG</text></svg>'

def analyze_pattern(segments: List[Tuple[float, ...]]) -> Dict[str, Any]:
    """Convenience function for pattern analysis.

    Args:
        segments: List of (x1, y1, x2, y2, radius) tuples OR (x1, y1, x2, y2) tuples

    Returns:
        Dictionary with pattern analysis including:
        - total_length: Total trace length in inches
        - bounds: (min_x, min_y, max_x, max_y) tuple
        - dimensions: (width, height) tuple in inches
        - segment_count: Number of wire segments
        - horizontal_count: Number of horizontal segments
        - vertical_count: Number of vertical segments
        - pattern_type: Pattern type classification
    """
    try:
        # Handle both 4-tuple and 5-tuple segment formats
        processed_segments = []
        if len(segments) > 0:
            first_segment = segments[0]
            if len(first_segment) == 4:
                # 4-tuple format: (x1, y1, x2, y2) - add default radius
                for seg in segments:
                    processed_segments.append((seg[0], seg[1], seg[2], seg[3], 0.005))
            else:
                # 5-tuple format: (x1, y1, x2, y2, radius)
                processed_segments = list(segments)
        else:
            processed_segments = []

        visualizer = AntennaVisualizer(mode='analysis')

        # Calculate bounds and total length
        bounds = NEC2GeometryParser.extract_bounds(processed_segments)
        min_x, min_y, max_x, max_y = bounds
        total_length = NEC2GeometryParser.calculate_total_length(processed_segments)

        # Count horizontal vs vertical segments
        horizontal = 0
        vertical = 0
        for seg in processed_segments:
            x1, y1, x2, y2 = seg[0], seg[1], seg[2], seg[3]
            dx = abs(x2 - x1)
            dy = abs(y2 - y1)
            if dy < 0.01:  # Horizontal (within tolerance)
                horizontal += 1
            elif dx < 0.01:  # Vertical (within tolerance)
                vertical += 1

        # Use the pattern detection methods from the visualizer
        pattern_type = visualizer._detect_pattern_type(processed_segments)
        connectivity = visualizer._check_connectivity(processed_segments)
        space_utilization = visualizer._calculate_space_utilization(processed_segments, max_x - min_x, max_y - min_y)

        return {
            'total_length': total_length,
            'bounds': bounds,
            'dimensions': (max_x - min_x, max_y - min_y),
            'segment_count': len(processed_segments),
            'horizontal_count': horizontal,
            'vertical_count': vertical,
            'pattern_type': pattern_type,
            'connectivity': connectivity,
            'space_utilization_percent': space_utilization
        }
    except Exception as e:
        logger.error(f"Pattern analysis error: {str(e)}")
        return {
            'total_length': 0,
            'bounds': (0, 0, 0, 0),
            'dimensions': (0, 0),
            'segment_count': 0,
            'horizontal_count': 0,
            'vertical_count': 0,
            'pattern_type': 'Error',
            'connectivity': 'Error',
            'space_utilization_percent': 0
        }

def validate_for_etching(geometry: str, constraints: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Convenience function for etching validation."""
    try:
        return AntennaValidator.validate_for_etching(geometry, constraints)
    except Exception:
        return {
            'minimum_feature_size': False,
            'trace_width_consistent': False,
            'isolation_clearance': False,
            'total_area': 0.0,
            'complexity_score': 0,
            'warnings': ['Validation failed'],
            'etching_ready': False,
            'element_count': 0
        }
