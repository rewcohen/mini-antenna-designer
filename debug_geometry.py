#!/usr/bin/env python3
"""Debug script to visualize what geometry is being generated."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from presets import BandPresets
from design_generator import AntennaDesignGenerator
from core import NEC2Interface

# Initialize
nec = NEC2Interface()
generator = AntennaDesignGenerator(nec)

# Generate WiFi band
wifi_band = BandPresets.get_all_bands()['wifi_2g_extend']
result = generator.generate_design(wifi_band)

geometry = result.get('geometry', '')

print(f"Design Type: {result.get('design_type')}")
print(f"Geometry length: {len(geometry)} chars")
print(f"\nFirst 50 lines of geometry:")
print("="*60)

lines = geometry.split('\n')[:50]
for i, line in enumerate(lines, 1):
    if line.strip():
        print(f"{i:3d}: {line}")

print(f"\n{'='*60}")
print(f"Total GW lines: {len([l for l in geometry.split('\\n') if 'GW' in l])}")

# Parse and analyze geometry
print(f"\n{'='*60}")
print("Analyzing wire segments:")
print(f"{'='*60}")

gw_lines = [l for l in geometry.split('\n') if l.strip().startswith('GW')]
for i, line in enumerate(gw_lines[:10], 1):
    parts = line.split()
    if len(parts) >= 8:
        x1, y1 = float(parts[3]), float(parts[4])
        x2, y2 = float(parts[6]), float(parts[7])
        length = ((x2-x1)**2 + (y2-y1)**2)**0.5

        # Determine if this is horizontal, vertical, or diagonal
        if abs(y2-y1) < 0.01:
            direction = "HORIZONTAL"
        elif abs(x2-x1) < 0.01:
            direction = "VERTICAL"
        else:
            direction = "DIAGONAL/U-TURN"

        print(f"{i:2d}. {direction:15s} ({x1:7.3f},{y1:7.3f}) -> ({x2:7.3f},{y2:7.3f})  len={length:6.3f}")
