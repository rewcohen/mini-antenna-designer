#!/usr/bin/env python3
"""Test with lower frequency to force actual meandering."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from presets import BandPresets
from design_generator import AntennaDesignGenerator
from core import NEC2Interface
from export import VectorExporter

# Initialize
nec = NEC2Interface()
generator = AntennaDesignGenerator(nec)
exporter = VectorExporter()

# Try TV VHF band - much lower frequency, needs meandering!
all_bands = BandPresets.get_all_bands()

# Find a band that will require meandering
test_bands = [
    ('tv_vhf_high', 'TV VHF High'),
    ('tv_vhf_low', 'TV VHF Low'),
    ('fm_radio', 'FM Radio'),
]

for band_key, band_name in test_bands:
    if band_key in all_bands:
        print(f"\n{'='*60}")
        print(f"Testing: {band_name}")
        print(f"{'='*60}")

        band = all_bands[band_key]
        print(f"Frequencies: {band.frequencies}")

        # Generate design
        result = generator.generate_design(band)
        geometry = result.get('geometry', '')

        if not geometry:
            print("  No geometry generated!")
            continue

        print(f"  Design type: {result.get('design_type')}")
        print(f"  Geometry length: {len(geometry)} chars")

        # Analyze geometry
        gw_lines = [l for l in geometry.split('\n') if l.strip().startswith('GW')]
        print(f"  Wire segments: {len(gw_lines)}")

        if len(gw_lines) > 0:
            # Check first few segments
            print(f"\n  First 5 wire segments:")
            for i, line in enumerate(gw_lines[:5], 1):
                parts = line.split()
                if len(parts) >= 8:
                    x1, y1 = float(parts[3]), float(parts[4])
                    x2, y2 = float(parts[6]), float(parts[7])
                    dx = abs(x2-x1)
                    dy = abs(y2-y1)

                    if dy < 0.01:
                        seg_type = "HORIZONTAL"
                    elif dx < 0.01:
                        seg_type = "VERTICAL  "
                    else:
                        seg_type = "DIAGONAL  "

                    print(f"    {i}. {seg_type} dx={dx:.3f} dy={dy:.3f}")

            # Export it
            try:
                svg_path = exporter.export_geometry(geometry, f'{band_key}_meander', 'svg')
                print(f"\n  ✓ Exported to: {svg_path}")

                if Path(svg_path).exists():
                    size = Path(svg_path).stat().st_size
                    print(f"  ✓ File size: {size} bytes")
            except Exception as e:
                print(f"  ✗ Export failed: {e}")

        break  # Just test first available band
