#!/usr/bin/env python3
"""
Standalone meander visualization module for debugging and development.

This module draws meander patterns from NEC2 geometry to help visualize
and debug antenna trace layouts.
"""

from typing import List, Tuple
import math


def parse_nec2_geometry(geometry_text: str) -> List[Tuple[float, float, float, float]]:
    """
    Parse NEC2 geometry string and extract wire segments.

    Args:
        geometry_text: NEC2 format geometry string with GW cards

    Returns:
        List of (x1, y1, x2, y2) tuples for each wire segment
    """
    segments = []

    for line in geometry_text.split('\n'):
        line = line.strip()
        if not line.startswith('GW'):
            continue

        parts = line.split()
        if len(parts) < 8:
            continue

        try:
            # GW format: GW tag segs x1 y1 z1 x2 y2 z2 radius
            x1 = float(parts[3])
            y1 = float(parts[4])
            x2 = float(parts[6])
            y2 = float(parts[7])

            segments.append((x1, y1, x2, y2))
        except (ValueError, IndexError):
            continue

    return segments


def calculate_bounds(segments: List[Tuple[float, float, float, float]]) -> Tuple[float, float, float, float]:
    """Calculate bounding box for segments."""
    if not segments:
        return 0, 0, 0, 0

    all_x = [x for seg in segments for x in [seg[0], seg[2]]]
    all_y = [y for seg in segments for y in [seg[1], seg[3]]]

    return min(all_x), min(all_y), max(all_x), max(all_y)


def calculate_total_length(segments: List[Tuple[float, float, float, float]]) -> float:
    """Calculate total trace length from segments."""
    total = 0.0
    for x1, y1, x2, y2 in segments:
        length = math.sqrt((x2-x1)**2 + (y2-y1)**2)
        total += length
    return total


def draw_ascii_meander(segments: List[Tuple[float, float, float, float]], width: int = 80, height: int = 20) -> str:
    """
    Draw ASCII art representation of meander pattern.

    Args:
        segments: List of (x1, y1, x2, y2) wire segments
        width: ASCII art width in characters
        height: ASCII art height in characters

    Returns:
        String with ASCII art representation
    """
    if not segments:
        return "No segments to draw"

    # Calculate bounds
    min_x, min_y, max_x, max_y = calculate_bounds(segments)

    width_range = max_x - min_x
    height_range = max_y - min_y

    if width_range == 0 or height_range == 0:
        return "Invalid geometry bounds"

    # Create grid
    grid = [[' ' for _ in range(width)] for _ in range(height)]

    # Draw segments
    for x1, y1, x2, y2 in segments:
        # Normalize to grid coordinates
        gx1 = int((x1 - min_x) / width_range * (width - 1))
        gy1 = int((y1 - min_y) / height_range * (height - 1))
        gx2 = int((x2 - min_x) / width_range * (width - 1))
        gy2 = int((y2 - min_y) / height_range * (height - 1))

        # Flip Y (ASCII coords go down, geometry coords go up)
        gy1 = height - 1 - gy1
        gy2 = height - 1 - gy2

        # Clamp to grid
        gx1 = max(0, min(width - 1, gx1))
        gx2 = max(0, min(width - 1, gx2))
        gy1 = max(0, min(height - 1, gy1))
        gy2 = max(0, min(height - 1, gy2))

        # Draw segment
        dx = abs(gx2 - gx1)
        dy = abs(gy2 - gy1)

        if dx > dy:
            # Horizontal-ish segment
            for x in range(min(gx1, gx2), max(gx1, gx2) + 1):
                if 0 <= x < width and 0 <= gy1 < height:
                    grid[gy1][x] = '-'
        else:
            # Vertical-ish segment
            for y in range(min(gy1, gy2), max(gy1, gy2) + 1):
                if 0 <= gx1 < width and 0 <= y < height:
                    grid[y][gx1] = '|'

    # Convert grid to string
    result = []
    result.append("+" + "-" * width + "+")
    for row in grid:
        result.append("|" + "".join(row) + "|")
    result.append("+" + "-" * width + "+")

    return "\n".join(result)


def generate_simple_svg(segments: List[Tuple[float, float, float, float]],
                       filename: str = "meander_debug.svg",
                       scale: float = 100.0) -> str:
    """
    Generate simple SVG file for visualization.

    Args:
        segments: List of (x1, y1, x2, y2) wire segments
        filename: Output SVG filename
        scale: SVG units per inch (default 100)

    Returns:
        SVG content as string
    """
    if not segments:
        return "<?xml version=\"1.0\"?><svg xmlns=\"http://www.w3.org/2000/svg\"/>"

    # Calculate bounds
    min_x, min_y, max_x, max_y = calculate_bounds(segments)

    margin = 0.2  # 0.2 inch margin
    width = (max_x - min_x + 2 * margin) * scale
    height = (max_y - min_y + 2 * margin) * scale

    # Transform coordinates
    def transform(x, y):
        return (
            (x - min_x + margin) * scale,
            height - ((y - min_y + margin) * scale)  # Flip Y for SVG
        )

    # Generate SVG paths
    paths = []
    for x1, y1, x2, y2 in segments:
        tx1, ty1 = transform(x1, y1)
        tx2, ty2 = transform(x2, y2)

        path = f'<line x1="{tx1:.2f}" y1="{ty1:.2f}" x2="{tx2:.2f}" y2="{ty2:.2f}" stroke="black" stroke-width="2"/>'
        paths.append(path)

    paths_str = '\n    '.join(paths)

    # Generate SVG
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width:.1f}" height="{height:.1f}" viewBox="0 0 {width:.1f} {height:.1f}"
     xmlns="http://www.w3.org/2000/svg">
  <title>Meander Pattern Debug</title>

  <!-- Background -->
  <rect width="{width:.1f}" height="{height:.1f}" fill="white" stroke="black" stroke-width="1"/>

  <!-- Antenna traces -->
  <g>
    {paths_str}
  </g>

  <!-- Info text -->
  <text x="10" y="20" font-family="Arial" font-size="8" fill="black">
    Bounds: {max_x - min_x:.3f}" x {max_y - min_y:.3f}"
  </text>
  <text x="10" y="35" font-family="Arial" font-size="8" fill="black">
    Segments: {len(segments)}
  </text>
  <text x="10" y="50" font-family="Arial" font-size="8" fill="black">
    Total length: {calculate_total_length(segments):.3f}"
  </text>

</svg>'''

    # Write to file
    with open(filename, 'w') as f:
        f.write(svg)

    return svg


def analyze_pattern(segments: List[Tuple[float, float, float, float]]) -> dict:
    """
    Analyze meander pattern and return statistics.

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
    if not segments:
        return {"error": "No segments"}

    total_length = calculate_total_length(segments)
    bounds = calculate_bounds(segments)
    min_x, min_y, max_x, max_y = bounds

    # Count horizontal vs vertical segments
    horizontal = 0
    vertical = 0

    for x1, y1, x2, y2 in segments:
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)

        if dy < 0.01:  # Horizontal (within tolerance)
            horizontal += 1
        elif dx < 0.01:  # Vertical (within tolerance)
            vertical += 1

    # Determine pattern type
    if vertical > horizontal * 0.3:
        pattern_type = "meander"
    elif horizontal > vertical * 3:
        pattern_type = "straight"
    else:
        pattern_type = "mixed"

    return {
        "total_length": total_length,
        "bounds": bounds,
        "dimensions": (max_x - min_x, max_y - min_y),
        "segment_count": len(segments),
        "horizontal_count": horizontal,
        "vertical_count": vertical,
        "pattern_type": pattern_type
    }


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
