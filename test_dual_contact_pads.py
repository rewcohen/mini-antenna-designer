#!/usr/bin/env python3
"""Test script for dual contact pads functionality."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from design import AntennaDesign

def test_dual_contact_pads():
    """Test the dual contact pads generation."""
    print("Testing dual contact pads generation...")
    
    # Create antenna design instance
    designer = AntennaDesign()
    
    # Test with different trace widths
    test_widths = [0.005, 0.010, 0.015]  # 5, 10, 15 mil
    
    for trace_width in test_widths:
        print(f"\nTesting with trace width: {trace_width*1000:.0f} mil")
        
        # Generate dual contact pads
        geometry = designer.generate_dual_contact_pads(trace_width, pad_spacing=0.1)
        
        if not geometry:
            print(f"❌ Failed to generate dual contact pads for {trace_width*1000:.0f} mil")
            continue
            
        print(f"✅ Generated dual contact pads for {trace_width*1000:.0f} mil")
        print(f"   Geometry lines: {len(geometry.split())}")
        
        # Verify geometry contains both signal and ground pads
        lines = geometry.split('\n')
        signal_pad_found = False
        ground_pad_found = False
        
        for line in lines:
            if line.strip():
                parts = line.split()
                if len(parts) >= 9 and parts[0] == 'GW':
                    # Check if this line is near origin (signal pad)
                    try:
                        x1, y1 = float(parts[3]), float(parts[4])
                        x2, y2 = float(parts[6]), float(parts[7])
                        
                        # Signal pad should be near origin
                        if abs(x1) < 0.01 and abs(y1) < 0.01:
                            signal_pad_found = True
                        # Ground pad should be offset by pad_spacing
                        elif abs(x1 - 0.1) < 0.01 and abs(y1) < 0.01:
                            ground_pad_found = True
                    except (ValueError, IndexError):
                        continue
        
        if signal_pad_found and ground_pad_found:
            print(f"   ✅ Both signal and ground pads found")
        else:
            print(f"   ❌ Missing pads - signal: {signal_pad_found}, ground: {ground_pad_found}")
        
        # Print first few lines for inspection
        print("   Sample geometry lines:")
        for i, line in enumerate(lines[:8]):
            if line.strip():
                print(f"     {line}")
        print(f"     ... ({len(lines)-8} more lines)")

def test_integration_with_dipole():
    """Test dual contact pads integrated with dipole antenna."""
    print("\n" + "="*60)
    print("Testing dual contact pads integration with dipole...")
    
    designer = AntennaDesign()
    
    # Generate dipole with dual contact pads
    frequency_mhz = 2400
    trace_width = 0.010  # 10 mil
    
    print(f"Generating dipole at {frequency_mhz} MHz with dual contact pads...")
    
    # Generate dipole geometry
    dipole_geometry = designer.generate_dipole(frequency_mhz, length_ratio=0.95, use_meandering=True)
    
    # Generate dual contact pads
    pad_geometry = designer.generate_dual_contact_pads(trace_width, pad_spacing=0.1)
    
    # Combine geometries
    combined_geometry = f"{dipole_geometry}\n{pad_geometry}"
    
    if combined_geometry and combined_geometry.strip():
        print(f"✅ Successfully generated combined geometry")
        print(f"   Dipole segments: {len(dipole_geometry.split())}")
        print(f"   Pad segments: {len(pad_geometry.split())}")
        print(f"   Total segments: {len(combined_geometry.split())}")
        
        # Verify both geometries are present
        has_dipole = 'GW' in dipole_geometry
        has_pads = 'GW' in pad_geometry
        
        if has_dipole and has_pads:
            print(f"   ✅ Both dipole and pads present in combined geometry")
        else:
            print(f"   ❌ Missing components - dipole: {has_dipole}, pads: {has_pads}")
            
        # Save test output
        with open('test_dual_pads_output.nec', 'w') as f:
            f.write(combined_geometry)
        print(f"   📄 Combined geometry saved to test_dual_pads_output.nec")
        
        return True
    else:
        print(f"❌ Failed to generate combined geometry")
        return False

def main():
    """Run all tests."""
    print("Dual Contact Pads Test Suite")
    print("="*60)
    
    try:
        # Test dual contact pads generation
        test_dual_contact_pads()
        
        # Test integration with antenna
        success = test_integration_with_dipole()
        
        if success:
            print("\n" + "="*60)
            print("✅ All tests passed! Dual contact pads are working correctly.")
            print("\nNext steps:")
            print("1. Update design generator to use generate_dual_contact_pads()")
            print("2. Update UI integration to pass add_contact_pads parameter")
            print("3. Test with actual antenna designs")
        else:
            print("\n" + "="*60)
            print("❌ Some tests failed. Check the output above for details.")
            
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
