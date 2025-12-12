#!/usr/bin/env python3
"""
Comprehensive Test Suite for Spiral Dipole Validation
==================================================
Tests the improved dual-side spiral dipole generation against various frequencies.
"""

import sys
import os
from visualize_meanders import MeanderVisualizer
from design import AdvancedMeanderTrace
from presets import BandPresets
from design_generator import AntennaDesignGenerator
from core import NEC2Interface

def test_tv_vhf_frequencies():
    """Test TV VHF frequencies to validate spiral dipole generation."""
    print("=" * 60)
    print("TESTING TV VHF FREQUENCIES (174-216 MHz)")
    print("=" * 60)
    
    # Initialize components
    viz = MeanderVisualizer()
    trace = AdvancedMeanderTrace()
    generator = AntennaDesignGenerator(NEC2Interface())
    
    # Test frequencies
    test_frequencies = [174, 200, 216]  # TV VHF High band
    
    results = {}
    
    for freq in test_frequencies:
        print(f"\n{'='*20}")
        print(f"TESTING {freq} MHz")
        print(f"{'='*20}")
        
        try:
            # Generate antenna design
            band = BandPresets.get_all_bands()[f'tv_vhf_{freq}' if freq in [174, 200, 216] else 'tv_vhf_high']
            result = generator.generate_design(band)
            
            if result and result.get('geometry'):
                # Parse and analyze geometry
                segments = viz.parse_nec2_geometry(result['geometry'])
                analysis = viz.analyze_pattern(segments)
                
                # Store results
                results[freq] = {
                    'frequency': freq,
                    'band_name': band.get('band_name', 'Unknown'),
                    'segments': len(segments),
                    'total_length': analysis['total_length_inches'],
                    'bounds': analysis['bounds'],
                    'pattern_type': analysis['pattern_type'],
                    'space_utilization': analysis['space_utilization_percent'],
                    'connectivity_issues': len(analysis['connectivity_issues']),
                    'geometry': result['geometry']
                }
                
                # Print analysis
                print(f"Pattern Type: {analysis['pattern_type']}")
                print(f"Total Length: {analysis['total_length_inches']:.2f}\"")
                print(f"Bounds: {analysis['bounds']['width']:.3f}\" x {analysis['bounds']['height']:.3f}\"")
                print(f"Space Utilization: {analysis['space_utilization_percent']:.1f}%")
                print(f"Segments: {len(segments)}")
                if analysis['connectivity_issues']:
                    print(f"Issues: {', '.join(analysis['connectivity_issues'])}")
                else:
                    print("Issues: None")
                
                # Expected targets for TV VHF
                expected_length = 11802.7 / freq * 0.95 / 2  # Half-wave dipole
                print(f"Expected Target: {expected_length:.2f}\"")
                
                # Validation checks
                length_ok = abs(analysis['total_length_inches'] - expected_length) / expected_length < 0.1
                utilization_ok = analysis['space_utilization_percent'] > 50  # Should be >50% for good spiral
                connectivity_ok = len(analysis['connectivity_issues']) == 0
                
                print(f"VALIDATION:")
                print(f"  Length Accuracy: {'✓ PASS' if length_ok else '✗ FAIL'}")
                print(f"  Space Utilization: {'✓ PASS' if utilization_ok else '✗ FAIL'} (>50%)")
                print(f"  Connectivity: {'✓ PASS' if connectivity_ok else '✗ FAIL'} (no issues)")
                
                # Overall result
                overall_pass = length_ok and utilization_ok and connectivity_ok
                print(f"  Overall: {'✓ PASS' if overall_pass else '✗ FAIL'}")
                
                if overall_pass:
                    print(f"  🎉 SUCCESS: {freq} MHz spiral dipole working correctly!")
                else:
                    print(f"  ❌ ISSUES FOUND: {freq} MHz needs attention")
                
        except Exception as e:
            print(f"ERROR: Failed to generate design for {freq} MHz")
            results[freq] = {'error': 'Generation failed'}
    
    return results

def test_space_utilization():
    """Test space utilization across different frequencies."""
    print("\n" + "=" * 60)
    print("SPACE UTILIZATION ANALYSIS")
    print("=" * 60)
    
    # Test various frequencies to compare space utilization
    test_cases = [
        (174, 'TV VHF Low'),
        (200, 'TV VHF Mid'), 
        (216, 'TV VHF High'),
        (900, 'ISM Band'),
        (2400, 'WiFi 2.4GHz'),
    ]
    
    for freq, desc in test_cases:
        # Generate spiral
        trace = AdvancedMeanderTrace()
        generator = AntennaDesignGenerator(NEC2Interface())
        
        band = BandPresets.get_all_bands()[f'tv_vhf_{freq}' if freq in [174, 200, 216] else 'tv_vhf_high']
        result = generator.generate_design(band)
        
        if result and result.get('geometry'):
            # Analyze space utilization
            viz = MeanderVisualizer()
            segments = viz.parse_nec2_geometry(result['geometry'])
            analysis = viz.analyze_pattern(segments)
            
            expected_length = 11802.7 / freq * 0.95 / 2
            actual_length = analysis['total_length_inches']
            
            # Calculate utilization
            substrate_area = 4.0 * 2.0  # 8 square inches
            trace_area = actual_length * 0.010  # 10 mil trace width
            utilization = (trace_area / substrate_area) * 100
            
            print(f"{freq:3d} MHz ({desc}):")
            print(f"  Expected Length: {expected_length:.2f}\"")
            print(f"  Actual Length: {actual_length:.2f}\"")
            print(f"  Space Utilization: {utilization:.1f}%")
            print(f"  Efficiency: {abs(actual_length - expected_length) / expected_length * 100:.1f}%")
            
            # Performance rating
            if utilization > 70 and abs(actual_length - expected_length) / expected_length < 5:
                rating = "🏆 EXCELLENT"
            elif utilization > 50 and abs(actual_length - expected_length) / expected_length < 10:
                rating = "✅ GOOD"
            else:
                rating = "⚠️ NEEDS WORK"
            
            print(f"  Rating: {rating}")
        print()

def test_connectivity():
    """Test positive/negative side isolation."""
    print("\n" + "=" * 60)
    print("CONNECTIVITY TEST")
    print("=" * 60)
    
    # Test with a frequency that should create clear separation
    trace = AdvancedMeanderTrace()
    generator = AntennaDesignGenerator(NEC2Interface())
    
    # Generate TV VHF antenna
    band = BandPresets.get_all_bands()['tv_vhf_high']
    result = generator.generate_design(band)
    
    if result and result.get('geometry'):
        viz = MeanderVisualizer()
        segments = viz.parse_nec2_geometry(result['geometry'])
        analysis = viz.analyze_pattern(segments)
        
        print(f"Generated {len(segments)} segments")
        print(f"Pattern type: {analysis['pattern_type']}")
        print(f"Connectivity issues: {len(analysis['connectivity_issues'])}")
        
        # Check for proper dual-side isolation
        if len(analysis['connectivity_issues']) == 0:
            print("✅ PASS: No short circuits detected")
        else:
            print("❌ FAIL: Short circuits found:")
            for issue in analysis['connectivity_issues']:
                print(f"    - {issue}")
        print()

def main():
    """Main test runner."""
    if len(sys.argv) > 1:
        test_type = sys.argv[1]
        
        if test_type == 'frequencies':
            test_tv_vhf_frequencies()
        elif test_type == 'space':
            test_space_utilization()
        elif test_type == 'connectivity':
            test_connectivity()
        else:
            print("Available test types:")
            print("  frequencies - Test TV VHF frequencies")
            print("  space - Test space utilization across frequencies")
            print("  connectivity - Test positive/negative isolation")
            print("\nUsage: python test_spiral_validation.py [test_type]")
            print("Example: python test_spiral_validation.py frequencies")
    else:
        print("Usage: python test_spiral_validation.py [test_type]")
        print("Example: python test_spiral_validation.py frequencies")

if __name__ == "__main__":
    main()
