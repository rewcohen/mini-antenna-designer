#!/usr/bin/env python3
"""
Meander Pattern Visualization and Debugging Tool
===========================================
Provides ASCII art and simple SVG visualization to verify meander patterns.
"""

import math
import sys
from typing import List, Tuple, Dict, Any
from loguru import logger

class MeanderVisualizer:
    """Visualize meander and spiral antenna patterns for debugging."""
    
    def __init__(self, scale: float = 100):
        """Initialize visualizer with pixel scale."""
        self.scale = scale  # pixels per inch
        self.debug_mode = True
    
    def parse_nec2_geometry(self, geometry: str) -> List[Dict[str, Any]]:
        """Parse NEC2 geometry into segment data.
        
        Args:
            geometry: NEC2 geometry string
            
        Returns:
            List of segment dictionaries
        """
        segments = []
        lines = geometry.split('\n')
        
        for line in lines:
            if not line.strip():
                continue
                
            parts = line.split()
            if len(parts) >= 8 and parts[0] == 'GW':
                try:
                    segment = {
                        'tag': int(float(parts[1])),
                        'x1': float(parts[3]),
                        'y1': float(parts[4]),
                        'z1': float(parts[5]),
                        'x2': float(parts[6]),
                        'y2': float(parts[7]),
                        'z2': float(parts[8]),
                        'radius': float(parts[9]) if len(parts) > 9 else 0.010,
                        'raw': line
                    }
                    segments.append(segment)
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse segment: {line} - {e}")
                    
        logger.info(f"Parsed {len(segments)} segments from geometry")
        return segments
    
    def analyze_pattern(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze the meander pattern characteristics.
        
        Args:
            segments: List of segment dictionaries
            
        Returns:
            Analysis results
        """
        if not segments:
            return {'error': 'No segments to analyze'}
        
        # Calculate bounds
        all_x = []
        all_y = []
        total_length = 0.0
        
        for seg in segments:
            all_x.extend([seg['x1'], seg['x2']])
            all_y.extend([seg['y1'], seg['y2']])
            
            # Calculate segment length
            seg_length = math.sqrt((seg['x2']-seg['x1'])**2 + (seg['y2']-seg['y1'])**2)
            total_length += seg_length
        
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        
        # Analyze pattern type
        pattern_type = self._detect_pattern_type(segments)
        
        # Check for connectivity issues
        connectivity_issues = self._check_connectivity(segments)
        
        # Calculate space utilization
        substrate_area = (max_x - min_x) * (max_y - min_y)
        trace_area = total_length * 0.010  # Assuming 10 mil trace width
        space_utilization = (trace_area / substrate_area * 100) if substrate_area > 0 else 0
        
        analysis = {
            'total_segments': len(segments),
            'total_length_inches': total_length,
            'bounds': {
                'min_x': min_x, 'max_x': max_x,
                'min_y': min_y, 'max_y': max_y,
                'width': max_x - min_x,
                'height': max_y - min_y
            },
            'pattern_type': pattern_type,
            'connectivity_issues': connectivity_issues,
            'space_utilization_percent': space_utilization,
            'average_segment_length': total_length / len(segments) if segments else 0
        }
        
        return analysis
    
    def _detect_pattern_type(self, segments: List[Dict[str, Any]]) -> str:
        """Detect the type of meander pattern."""
        if len(segments) < 3:
            return "insufficient_segments"
        
        # Count direction changes
        direction_changes = 0
        horizontal_segments = 0
        vertical_segments = 0
        
        for i, seg in enumerate(segments):
            dx = seg['x2'] - seg['x1']
            dy = seg['y2'] - seg['y1']
            
            if abs(dx) > abs(dy):
                horizontal_segments += 1
            else:
                vertical_segments += 1
        
        # Determine pattern type
        if horizontal_segments > vertical_segments * 2:
            return "horizontal_dominant"
        elif vertical_segments > horizontal_segments * 2:
            return "vertical_dominant"
        elif horizontal_segments > 5 and vertical_segments > 5:
            return "spiral_meander"
        elif horizontal_segments > 3 and vertical_segments > 0:
            return "simple_meander"
        else:
            return "unknown_pattern"
    
    def _check_connectivity(self, segments: List[Dict[str, Any]]) -> List[str]:
        """Check for connectivity issues in the pattern."""
        issues = []
        
        # Build connectivity map
        connections = {}
        for i, seg in enumerate(segments):
            start = (seg['x1'], seg['y1'])
            end = (seg['x2'], seg['y2'])
            
            if i not in connections:
                connections[i] = {'starts': [], 'ends': []}
            connections[i]['starts'].append(start)
            connections[i]['ends'].append(end)
        
        # Check for gaps
        for i, seg in enumerate(segments):
            if i < len(segments) - 1:
                current_end = (seg['x2'], seg['y2'])
                next_start = (segments[i+1]['x1'], segments[i+1]['y1'])
                
                distance = math.sqrt((current_end[0]-next_start[0])**2 + (current_end[1]-next_start[1])**2)
                if distance > 0.01:  # More than 0.01 inch gap
                    issues.append(f"gap_between_segments_{i+1}_{i+2}")
        
        # Check for intersections (except at feed point)
        for i, seg1 in enumerate(segments):
            for j, seg2 in enumerate(segments):
                if i >= j:  # Don't compare with self or previous segments
                    continue
                
                # Check if segments intersect
                if self._segments_intersect(seg1, seg2):
                    # Check if intersection is at feed point (0,0)
                    intersection = self._find_intersection(seg1, seg2)
                    if intersection:
                        dist_to_feed = math.sqrt(intersection[0]**2 + intersection[1]**2)
                        if dist_to_feed > 0.01:  # Not at feed point
                            issues.append(f"short_circuit_segments_{i+1}_{j+1}")
        
        return issues
    
    def _segments_intersect(self, seg1: Dict, seg2: Dict) -> bool:
        """Check if two line segments intersect."""
        x1, y1 = seg1['x1'], seg1['y1']
        x2, y2 = seg1['x2'], seg1['y2']
        x3, y3 = seg2['x1'], seg2['y1']
        x4, y4 = seg2['x2'], seg2['y2']
        
        # Line segment intersection algorithm
        denom = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)
        if abs(denom) < 1e-10:
            return False
        
        t = ((x1-x3)*(y3-y4) - (y1-y3)*(x3-x4)) / denom
        u = -((x1-x2)*(y1-y3) - (y1-y2)*(x1-x3)) / denom
        
        return 0 <= t <= 1 and 0 <= u <= 1
    
    def _find_intersection(self, seg1: Dict, seg2: Dict) -> Tuple[float, float]:
        """Find intersection point of two line segments."""
        x1, y1 = seg1['x1'], seg1['y1']
        x2, y2 = seg1['x2'], seg1['y2']
        x3, y3 = seg2['x1'], seg2['y1']
        x4, y4 = seg2['x2'], seg2['y2']
        
        denom = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)
        if abs(denom) < 1e-10:
            return None
        
        t = ((x1-x3)*(y3-y4) - (y1-y3)*(x3-x4)) / denom
        
        x = x1 + t * (x2 - x1)
        y = y1 + t * (y2 - y1)
        
        return (x, y)
    
    def render_ascii(self, segments: List[Dict[str, Any]], 
                  width: int = 80, height: int = 25) -> str:
        """Render ASCII art visualization of the meander pattern.
        
        Args:
            segments: List of segment dictionaries
            width, height: ASCII canvas dimensions
            
        Returns:
            ASCII string representation
        """
        if not segments:
            return "No segments to render"
        
        # Calculate bounds and scaling
        all_x = []
        all_y = []
        for seg in segments:
            all_x.extend([seg['x1'], seg['x2']])
            all_y.extend([seg['y1'], seg['y2']])
        
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        
        # Create ASCII canvas
        canvas = [[' ' for _ in range(width)] for _ in range(height)]
        
        # Scaling function
        def scale_x(x):
            return int((x - min_x) / (max_x - min_x + 0.001) * (width - 4)) + 2
        
        def scale_y(y):
            return int((y - min_y) / (max_y - min_y + 0.001) * (height - 4)) + 2
        
        # Draw segments
        for seg in segments:
            x1, y1 = scale_x(seg['x1']), scale_y(seg['y1'])
            x2, y2 = scale_x(seg['x2']), scale_y(seg['y2'])
            
            # Draw line using Bresenham's algorithm
            points = self._get_line_points(x1, y1, x2, y2)
            for px, py in points:
                if 0 <= px < width and 0 <= py < height:
                    if canvas[py][px] == ' ':
                        canvas[py][px] = '#'
                    elif canvas[py][px] == '#':
                        canvas[py][px] = '+'  # Intersection point
        
        # Mark feed point
        feed_x, feed_y = scale_x(0), scale_y(0)
        if 0 <= feed_x < width and 0 <= feed_y < height:
            canvas[feed_y][feed_x] = 'F'
        
        # Convert to string
        ascii_art = []
        for row in canvas:
            ascii_art.append(''.join(row))
        
        # Add header with analysis
        analysis = self.analyze_pattern(segments)
        header = f"""
MEANDER PATTERN VISUALIZATION
===========================
Pattern Type: {analysis['pattern_type']}
Total Length: {analysis['total_length_inches']:.2f}" 
Bounds: {analysis['bounds']['width']:.3f}" x {analysis['bounds']['height']:.3f}"
Space Utilization: {analysis['space_utilization_percent']:.1f}%
Segments: {analysis['total_segments']}
Issues: {', '.join(analysis['connectivity_issues']) if analysis['connectivity_issues'] else 'None'}

Legend: # = Trace, F = Feed Point, + = Intersection

"""
        return header + '\n'.join(ascii_art)
    
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
    
    def generate_debug_svg(self, segments: List[Dict[str, Any]], 
                       filename: str = "debug_meander.svg") -> str:
        """Generate simple debug info (SVG removed for dependency issues)."""
        if not segments:
            return ""
        
        analysis = self.analyze_pattern(segments)
        print(f"\nDEBUG ANALYSIS for {filename}:")
        print(f"Pattern Type: {analysis['pattern_type']}")
        print(f"Total Length: {analysis['total_length_inches']:.2f}\"")
        print(f"Bounds: {analysis['bounds']['width']:.3f}\" x {analysis['bounds']['height']:.3f}\"")
        print(f"Space Utilization: {analysis['space_utilization_percent']:.1f}%")
        print(f"Segments: {analysis['total_segments']}")
        print(f"Issues: {', '.join(analysis['connectivity_issues']) if analysis['connectivity_issues'] else 'None'}")
        return filename
    
    def generate_comparison_report(self, before_segments: List[Dict[str, Any]], 
                            after_segments: List[Dict[str, Any]]) -> str:
        """Generate before/after comparison report."""
        before_analysis = self.analyze_pattern(before_segments)
        after_analysis = self.analyze_pattern(after_segments)
        
        report = f"""
MEANDER PATTERN COMPARISON REPORT
=====================================

BEFORE FIX:
-----------
Pattern Type: {before_analysis['pattern_type']}
Total Length: {before_analysis['total_length_inches']:.2f}"
Bounds: {before_analysis['bounds']['width']:.3f}" x {before_analysis['bounds']['height']:.3f}"
Space Utilization: {before_analysis['space_utilization_percent']:.1f}%
Connectivity Issues: {len(before_analysis['connectivity_issues'])}

AFTER FIX:
----------
Pattern Type: {after_analysis['pattern_type']}
Total Length: {after_analysis['total_length_inches']:.2f}"
Bounds: {after_analysis['bounds']['width']:.3f}" x {after_analysis['bounds']['height']:.3f}"
Space Utilization: {after_analysis['space_utilization_percent']:.1f}%
Connectivity Issues: {len(after_analysis['connectivity_issues'])}

IMPROVEMENTS:
-------------
Space Utilization: {after_analysis['space_utilization_percent'] - before_analysis['space_utilization_percent']:+.1f}%
Connectivity Issues: {len(before_analysis['connectivity_issues']) - len(after_analysis['connectivity_issues']):+d}
"""
        
        return report


def main():
    """Main function for testing visualizer."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python visualize_meanders.py <geometry_file>")
        print("   or: python visualize_meanders.py test")
        return
    
    if sys.argv[1] == 'test':
        # Generate test patterns
        viz = MeanderVisualizer()
        
        print("Generating test meander patterns...")
        
        # Test 1: Simple horizontal lines (current broken pattern)
        test_segments = [
            {'tag': 1, 'x1': -1.5, 'y1': 0.5, 'z1': 0, 'x2': 1.5, 'y2': 0.5, 'z2': 0, 'radius': 0.01},
            {'tag': 2, 'x1': 1.5, 'y1': 0.5, 'z1': 0, 'x2': 1.5, 'y2': -0.5, 'z2': 0, 'radius': 0.01},
            {'tag': 3, 'x1': 1.5, 'y1': -0.5, 'z1': 0, 'x2': -1.5, 'y2': -0.5, 'z2': 0, 'radius': 0.01},
        ]
        
        print("\n" + "="*60)
        print("TEST 1: Current Broken Pattern")
        print("="*60)
        print(viz.render_ascii(test_segments))
        viz.generate_debug_svg(test_segments, "test_before.svg")
        
        # Test 2: Proper spiral meander
        test_spiral = [
            {'tag': 1, 'x1': 0, 'y1': 0, 'z1': 0, 'x2': 1.5, 'y2': 0, 'z2': 0, 'radius': 0.01},
            {'tag': 2, 'x1': 1.5, 'y1': 0, 'z1': 0, 'x2': 1.5, 'y2': 0.5, 'z2': 0, 'radius': 0.01},
            {'tag': 3, 'x1': 1.5, 'y1': 0.5, 'z1': 0, 'x2': -1.5, 'y2': 0.5, 'z2': 0, 'radius': 0.01},
            {'tag': 4, 'x1': -1.5, 'y1': 0.5, 'z1': 0, 'x2': -1.5, 'y2': -0.5, 'z2': 0, 'radius': 0.01},
            {'tag': 5, 'x1': -1.5, 'y1': -0.5, 'z1': 0, 'x2': 1.0, 'y2': -0.5, 'z2': 0, 'radius': 0.01},
            {'tag': 6, 'x1': 1.0, 'y1': -0.5, 'z1': 0, 'x2': 1.0, 'y2': 0.3, 'z2': 0, 'radius': 0.01},
            {'tag': 7, 'x1': 1.0, 'y1': 0.3, 'z1': 0, 'x2': -1.0, 'y2': 0.3, 'z2': 0, 'radius': 0.01},
        ]
        
        print("\n" + "="*60)
        print("TEST 2: Proper Spiral Meander")
        print("="*60)
        print(viz.render_ascii(test_spiral))
        viz.generate_debug_svg(test_spiral, "test_after.svg")
        
        print("\nTest files generated: test_before.svg, test_after.svg")
        
    else:
        # Load geometry from file
        filename = sys.argv[1]
        try:
            with open(filename, 'r') as f:
                geometry = f.read()
            
            viz = MeanderVisualizer()
            segments = viz.parse_nec2_geometry(geometry)
            
            print(f"Analyzing geometry from {filename}")
            print("="*60)
            print(viz.render_ascii(segments))
            viz.generate_debug_svg(segments, "debug_meander.svg")
            
        except FileNotFoundError:
            print(f"Error: File {filename} not found")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
