#!/usr/bin/env python3
"""
Standalone meander visualization module for debugging and development.

This module draws meander patterns from NEC2 geometry to help visualize
and debug antenna trace layouts.

REFACTORED: Now uses shared utilities from antenna_utils.py module.
"""

from typing import List, Tuple
import math
from antenna_utils import (
    NEC2GeometryParser,
    AntennaVisualizer,
    parse_nec2_geometry as _parse_nec2,
    draw_ascii_meander as _draw_ascii,
    generate_simple_svg as _generate_svg,
    analyze_pattern as _analyze
)


def parse_nec2_geometry(geometry_text: str) -> List[Tuple[float, float, float, float]]:
    """
    Parse NEC2 geometry string and extract wire segments.

    NOTE: This is a compatibility wrapper that converts the shared utility's
    5-tuple format (x1, y1, x2, y2, radius) to 4-tuple format (x1, y1, x2, y2).

    Args:
        geometry_text: NEC2 format geometry string with GW cards

    Returns:
        List of (x1, y1, x2, y2) tuples for each wire segment
    """
    # Use shared utility and convert format
    segments_5 = _parse_nec2(geometry_text)
    # Convert from 5-tuple to 4-tuple (drop radius)
    return [(x1, y1, x2, y2) for x1, y1, x2, y2, _ in segments_5]


def calculate_bounds(segments: List[Tuple[float, float, float, float]]) -> Tuple[float, float, float, float]:
    """
    Calculate bounding box for segments.

    NOTE: This is a compatibility wrapper around the shared utility.

    Args:
        segments: List of (x1, y1, x2, y2) tuples

    Returns:
        (min_x, min_y, max_x, max_y) bounding box
    """
    # Use shared utility
    return NEC2GeometryParser.extract_bounds(segments)


def calculate_total_length(segments: List[Tuple[float, float, float, float]]) -> float:
    """
    Calculate total trace length from segments.

    NOTE: This is a compatibility wrapper around the shared utility.

    Args:
        segments: List of (x1, y1, x2, y2) tuples

    Returns:
        Total length in inches
    """
    # Use shared utility
    return NEC2GeometryParser.calculate_total_length(segments)


def draw_ascii_meander(segments: List[Tuple[float, float, float, float]], width: int = 80, height: int = 20) -> str:
    """
    Draw ASCII art representation of meander pattern.

    NOTE: This is a compatibility wrapper around the shared utility.

    Args:
        segments: List of (x1, y1, x2, y2) wire segments
        width: ASCII art width in characters
        height: ASCII art height in characters

    Returns:
        String with ASCII art representation
    """
    # Use shared utility directly
    return _draw_ascii(segments, width, height)


def generate_simple_svg(segments: List[Tuple[float, float, float, float]],
                       filename: str = "meander_debug.svg",
                       scale: float = 100.0) -> str:
    """
    Generate simple SVG file for visualization.

    NOTE: This is a compatibility wrapper around the shared utility.

    Args:
        segments: List of (x1, y1, x2, y2) wire segments
        filename: Output SVG filename
        scale: SVG units per inch (default 100)

    Returns:
        SVG content as string
    """
    # Use shared utility directly
    return _generate_svg(segments, filename, scale)


def analyze_pattern(segments: List[Tuple[float, float, float, float]]) -> dict:
    """
    Analyze meander pattern and return statistics.

    NOTE: This is a compatibility wrapper around the shared utility.

    Returns:
        Dictionary with pattern analysis:
        - total_length: Total trace length in inches
        - bounds: (min_x, min_y, max_x, max_y)
        - dimensions: (width, height) in inches
        - segment_count: Number of wire segments
        - horizontal_count: Number of horizontal segments
        - vertical_count: Number of vertical segments
        - pattern_type: "meander" or "straight" or "unknown"
    """
    # Use shared utility directly
    return _analyze(segments)


def main():
    """Test/demo function."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python draw_meander.py <nec2_geometry_file>")
        print("\nOr use programmatically:")
        print("  from draw_meander import parse_nec2_geometry, draw_ascii_meander, generate_simple_svg")
        return

    # Read geometry from file
    with open(sys.argv[1], 'r') as f:
        geometry_text = f.read()

    # Parse and analyze
    segments = parse_nec2_geometry(geometry_text)
    analysis = analyze_pattern(segments)

    print(f"\nGeometry Analysis:")
    print(f"  Total segments: {analysis['segment_count']}")
    print(f"  Total length: {analysis['total_length']:.3f} inches")
    print(f"  Dimensions: {analysis['dimensions'][0]:.3f}\" × {analysis['dimensions'][1]:.3f}\"")
    print(f"  Horizontal segments: {analysis['horizontal_count']}")
    print(f"  Vertical segments: {analysis['vertical_count']}")
    print(f"  Pattern type: {analysis['pattern_type']}")

    # Draw ASCII
    print(f"\nASCII Visualization:")
    print(draw_ascii_meander(segments, width=80, height=15))

    # Generate SVG
    svg_file = "meander_debug.svg"
    generate_simple_svg(segments, svg_file)
    print(f"\nSVG written to: {svg_file}")


if __name__ == "__main__":
    main()
