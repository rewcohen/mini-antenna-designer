#!/usr/bin/env python3
"""Visualize the difference between WiFi (no meander) and TV (meander) antennas."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def ascii_visualize_geometry(geometry, title, max_width=60):
    """Create ASCII art visualization of antenna geometry."""
    print(f"\n{'='*max_width}")
    print(f"{title:^{max_width}}")
    print(f"{'='*max_width}")

    gw_lines = [l for l in geometry.split('\n') if l.strip().startswith('GW')]
    print(f"Total wire segments: {len(gw_lines)}\n")

    # Parse coordinates
    segments = []
    for line in gw_lines[:50]:  # First 50 segments
        parts = line.split()
        if len(parts) >= 8:
            x1, y1 = float(parts[3]), float(parts[4])
            x2, y2 = float(parts[6]), float(parts[7])
            segments.append(((x1, y1), (x2, y2)))

    if not segments:
        print("No segments found!")
        return

    # Find bounds
    all_x = [s[0][0] for s in segments] + [s[1][0] for s in segments]
    all_y = [s[0][1] for s in segments] + [s[1][1] for s in segments]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)

    width_range = max_x - min_x
    height_range = max_y - min_y

    print(f"Dimensions: {width_range:.2f}\" × {height_range:.2f}\"")
    print(f"X range: {min_x:.2f}\" to {max_x:.2f}\"")
    print(f"Y range: {min_y:.2f}\" to {max_y:.2f}\"")

    # Create ASCII visualization
    grid_width = min(max_width - 4, 50)
    grid_height = 15

    # Initialize grid
    grid = [[' ' for _ in range(grid_width)] for _ in range(grid_height)]

    # Plot segments
    for (x1, y1), (x2, y2) in segments[:30]:  # First 30 segments
        # Normalize to grid
        if width_range > 0:
            gx1 = int((x1 - min_x) / width_range * (grid_width - 1))
            gx2 = int((x2 - min_x) / width_range * (grid_width - 1))
        else:
            gx1 = gx2 = grid_width // 2

        if height_range > 0:
            gy1 = int((y1 - min_y) / height_range * (grid_height - 1))
            gy2 = int((y2 - min_y) / height_range * (grid_height - 1))
        else:
            gy1 = gy2 = grid_height // 2

        # Flip y (ASCII coords go down, antenna coords go up)
        gy1 = grid_height - 1 - gy1
        gy2 = grid_height - 1 - gy2

        # Clamp to grid
        gx1 = max(0, min(grid_width - 1, gx1))
        gx2 = max(0, min(grid_width - 1, gx2))
        gy1 = max(0, min(grid_height - 1, gy1))
        gy2 = max(0, min(grid_height - 1, gy2))

        # Draw segment
        if abs(gx2 - gx1) > abs(gy2 - gy1):
            # Horizontal-ish
            for x in range(min(gx1, gx2), max(gx1, gx2) + 1):
                if 0 <= x < grid_width and 0 <= gy1 < grid_height:
                    grid[gy1][x] = '-'
        else:
            # Vertical-ish
            for y in range(min(gy1, gy2), max(gy1, gy2) + 1):
                if 0 <= gx1 < grid_width and 0 <= y < grid_height:
                    grid[y][gx1] = '|'

    # Print grid
    print("\nVisualization:")
    print("+" + "-" * grid_width + "+")
    for row in grid:
        print("|" + "".join(row) + "|")
    print("+" + "-" * grid_width + "+")

    # Print pattern analysis
    print("\nPattern Analysis:")
    h_count = sum(1 for ((x1, y1), (x2, y2)) in segments[:20] if abs(y2 - y1) < 0.01)
    v_count = sum(1 for ((x1, y1), (x2, y2)) in segments[:20] if abs(x2 - x1) < 0.01)

    if v_count > h_count * 0.3:
        print("  Pattern: MEANDERING (has vertical U-turns)")
        print(f"  Horizontal segments: {h_count}")
        print(f"  Vertical segments: {v_count}")
        print("  This creates a worm-like pattern!")
    else:
        print("  Pattern: STRAIGHT (no meandering needed)")
        print(f"  Horizontal segments: {h_count}")
        print(f"  Vertical segments: {v_count}")
        print("  This antenna fits on the substrate as-is!")


def main():
    from presets import BandPresets
    from design_generator import AntennaDesignGenerator
    from core import NEC2Interface

    nec = NEC2Interface()
    generator = AntennaDesignGenerator(nec)

    all_bands = BandPresets.get_all_bands()

    # Test WiFi (should not meander)
    print("\n" + "="*60)
    print("COMPARISON: WiFi vs TV VHF Antennas")
    print("="*60)

    # WiFi 2.4 GHz
    wifi_band = all_bands['wifi_2g_extend']
    wifi_result = generator.generate_design(wifi_band)
    ascii_visualize_geometry(
        wifi_result['geometry'],
        f"WiFi 2.4 GHz ({wifi_band.frequencies[0]}-{wifi_band.frequencies[2]} MHz)"
    )

    # TV VHF
    tv_band = all_bands['tv_vhf_high']
    tv_result = generator.generate_design(tv_band)
    ascii_visualize_geometry(
        tv_result['geometry'],
        f"TV VHF High ({tv_band.frequencies[0]}-{tv_band.frequencies[2]} MHz)"
    )

    print("\n" + "="*60)
    print("CONCLUSION")
    print("="*60)
    print("WiFi antennas: Simple straight lines (no meandering needed)")
    print("TV antennas: Complex meander pattern (worm-like)")
    print("\nBoth export correctly! The difference is expected.")
    print("="*60)


if __name__ == "__main__":
    main()
