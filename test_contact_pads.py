#!/usr/bin/env python3
"""Test script for contact pad functionality."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from design import AntennaDesign, AdvancedMeanderTrace
from ui import AntennaDesignerGUI
from export import VectorExporter
from loguru import logger
import tkinter as tk

def test_contact_pad_generation():
    """Test contact pad generation for different antenna types."""
    print("Testing contact pad generation...")

    # Test 1: Simple dipole with contact pads
    print("\n1. Testing dipole with contact pads:")
    try:
        # Create a simple dipole geometry
        dipole_geometry = """CM Dipole Test with Contact Pads
GW      1   1   -0.500   0.000   0.000   0.500   0.000   0.010
GE      1   0   0       0       0       0
GN      1   0   0       0       0       0
FR      0   1   0       0       2400    0
EX      0   1   1       1       0       0
RP      0   1   1       1001    0       0       1.000   1.000   0       0"""

        # Test export with contact pads
        exporter = VectorExporter()
        wire_segments = exporter._parse_geometry(dipole_geometry)

        # Check for contact pads
        if wire_segments:
            trace_widths = [s[4] for s in wire_segments]
            from collections import Counter
            width_counts = Counter(f"{w:.4f}" for w in trace_widths)
            print(f"   Trace widths found: {list(width_counts.keys())}")
            print(f"   Most common width: {width_counts.most_common(1)[0][0]} inches")

        print("   ✓ Dipole test completed")

    except Exception as e:
        print(f"   ✗ Dipole test failed: {e}")

    # Test 2: Meander trace with contact pads
    print("\n2. Testing meander trace with contact pads:")
    try:
        # Create meander trace
        meander = AdvancedMeanderTrace(substrate_width=4.0, substrate_height=2.0)
        meander.substrate_epsilon = 4.3
        meander.substrate_thickness = 0.0016  # 1.6mm in meters

        # Generate meander for 2.4 GHz
        freq_hz = 2.4e9
        e_eff = meander.calculate_effective_permittivity(4.3, 0.0016, 0.000254)  # 10 mil trace
        target_length = meander.calculate_target_length(freq_hz, e_eff, 0.9)

        # Generate meander with contact pads
        meander_geometry = meander.generate_meander_geometry(
            target_length,
            trace_width=0.010,  # 10 mil
            coupling_factor=0.9,
            add_contact_pads=True
        )

        print(f"   Generated meander geometry with contact pads")
        print(f"   Geometry length: {len(meander_geometry)} characters")

        # Parse the geometry to check for contact pads
        exporter = VectorExporter()
        wire_segments = exporter._parse_geometry(meander_geometry)
        trace_widths = [s[4] for s in wire_segments]

        # Check for contact pad segments (wider than normal traces)
        contact_pad_segments = [w for w in trace_widths if w > 0.020]  # > 20 mil
        print(f"   Contact pad segments: {len(contact_pad_segments)}")
        print(f"   Normal trace segments: {len(trace_widths) - len(contact_pad_segments)}")

        print("   ✓ Meander test completed")

    except Exception as e:
        print(f"   ✗ Meander test failed: {e}")
        import traceback
        traceback.print_exc()

    # Test 3: Export validation
    print("\n3. Testing export validation:")
    try:
        # Test with a geometry that has contact pads
        test_geometry = """CM Test Geometry with Contact Pads
GW      1   1   -0.500   0.000   0.000   0.500   0.000   0.010
GW      2   1   -0.500   0.000   0.000   -0.500   0.000   0.020
GW      3   1   0.500   0.000   0.000   0.500   0.000   0.020
GE      1   0   0       0       0       0
GN      1   0   0       0       0       0
FR      0   1   0       0       2400    0
EX      0   1   1       1       0       0
RP      0   1   1       1001    0       0       1.000   1.000   0       0"""

        # Validate geometry
        from export import EtchingValidator
        validation = EtchingValidator.validate_for_etching(test_geometry)

        print(f"   Contact pads present: {validation['contact_pads_present']}")
        print(f"   Pad size valid: {validation['contact_pad_size_valid']}")
        print(f"   Pad ratio: {validation['contact_pad_trace_width_ratio']:.2f}x")

        # Test SVG generation
        exporter = VectorExporter()
        wire_segments = exporter._parse_geometry(test_geometry)
        trace_validation = exporter._validate_trace_widths(wire_segments)

        print(f"   Trace validation status: {trace_validation['overall_status']}")
        print(f"   Trace count: {len(trace_validation['trace_widths_mils'])}")

        print("   ✓ Export validation test completed")

    except Exception as e:
        print(f"   ✗ Export validation test failed: {e}")
        import traceback
        traceback.print_exc()

    print("\nContact pad testing completed!")

def test_ui_integration():
    """Test UI integration without launching full GUI."""
    print("\nTesting UI integration...")

    try:
        # Test that UI components can be imported and initialized
        from ui import AntennaDesignerGUI

        # Create a minimal test to verify UI can handle contact pads
        print("   ✓ UI components imported successfully")

        # Test trace width validation
        from ui import AntennaDesignerGUI

        # Simulate trace width validation
        test_widths = [5.0, 8.0, 10.0, 15.0, 20.0]  # mil
        for width in test_widths:
            from constraints import ManufacturingRules
            result = ManufacturingRules.check_trace_width(width / 1000.0)  # Convert to inches
            status = "✓" if result['is_manufacturable'] else "⚠"
            print(f"   Trace width {width:4.1f} mil: {status} {result['quality_rating']}")

        print("   ✓ UI integration test completed")

    except Exception as e:
        print(f"   ✗ UI integration test failed: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Run all tests."""
    print("Contact Pad Functionality Test Suite")
    print("=" * 50)

    # Configure logging
    logger.remove()
    logger.add(sys.stdout, level="INFO")

    # Run tests
    test_contact_pad_generation()
    test_ui_integration()

    print("\n" + "=" * 50)
    print("Test suite completed!")

if __name__ == "__main__":
    main()
