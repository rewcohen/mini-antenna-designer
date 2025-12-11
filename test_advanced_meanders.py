#!/usr/bin/env python3
"""Test script to verify advanced meander functionality."""

import sys
from pathlib import Path
from loguru import logger

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

def test_advanced_meanders():
    """Test advanced meander generation with different frequency combinations."""
    logger.info("Starting advanced meander functionality test")
    
    try:
        # Import required modules
        from presets import BandPresets
        from design_generator import AntennaDesignGenerator
        from core import NEC2Interface
        
        logger.info("✓ All modules imported successfully")
        
        # Initialize components
        nec_interface = NEC2Interface()
        generator = AntennaDesignGenerator(nec_interface)
        
        logger.info("✓ Design generator initialized")
        
        # Test cases that should trigger different advanced meander types
        test_cases = [
            {
                'name': 'Close frequencies (should trigger tri-band meander)',
                'frequencies': (2400, 2450, 2500),  # Very close frequencies
                'expected_type': 'advanced_meander_tri_band'
            },
            {
                'name': 'Medium separation (should trigger dual-band meander)',
                'frequencies': (2400, 3500, 5500),  # Medium separation
                'expected_type': 'advanced_meander_dual'
            },
            {
                'name': 'Large separation (should trigger compound meander)',
                'frequencies': (900, 2400, 5800),  # Large separation
                'expected_type': 'advanced_meander_compound'
            },
            {
                'name': 'WiFi 2.4GHz Extended (close frequencies)',
                'frequencies': (2412, 2437, 2462),  # Real WiFi band
                'expected_type': 'advanced_meander_tri_band'
            },
            {
                'name': 'Cellular LTE (medium separation)',
                'frequencies': (700, 1800, 2600),  # Real LTE band
                'expected_type': 'advanced_meander_dual'
            }
        ]
        
        # Run test cases
        results = []
        for i, test_case in enumerate(test_cases, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Test Case {i}: {test_case['name']}")
            logger.info(f"{'='*60}")
            
            # Create frequency band
            band = BandPresets.create_custom_band(
                name=test_case['name'],
                freq1=test_case['frequencies'][0],
                freq2=test_case['frequencies'][1], 
                freq3=test_case['frequencies'][2]
            )
            
            logger.info(f"Created band: {band.name}")
            logger.info(f"Frequencies: {band.frequencies}")
            
            # Generate design
            design_result = generator.generate_design(band)
            
            # Check results
            success = design_result.get('success', False)
            design_type = design_result.get('design_type', 'unknown')
            geometry = design_result.get('geometry', '')
            
            logger.info(f"Design success: {success}")
            logger.info(f"Design type: {design_type}")
            logger.info(f"Expected type: {test_case['expected_type']}")
            
            # Validate geometry
            if geometry and geometry.strip():
                lines = geometry.split('\n')
                gw_lines = [line for line in lines if line.strip().startswith('GW')]
                logger.info(f"Geometry generated: {len(lines)} total lines, {len(gw_lines)} wire segments")
                
                # Check for advanced meander characteristics
                has_meander = False
                for line in gw_lines[:5]:  # Check first few lines
                    parts = line.split()
                    if len(parts) >= 8:
                        x1, y1 = float(parts[3]), float(parts[4])
                        x2, y2 = float(parts[6]), float(parts[7])
                        
                        # Look for meander patterns (multiple direction changes)
                        if abs(x2 - x1) > 0.1 and abs(y2 - y1) > 0.1:
                            has_meander = True
                            break
                
                if has_meander:
                    logger.info("✓ Advanced meander pattern detected in geometry")
                else:
                    logger.warning("⚠ No obvious meander pattern detected")
            
            # Store results
            result = {
                'test_case': test_case['name'],
                'frequencies': test_case['frequencies'],
                'expected_type': test_case['expected_type'],
                'actual_type': design_type,
                'success': success,
                'has_geometry': bool(geometry and geometry.strip()),
                'geometry_lines': len(geometry.split('\n')) if geometry else 0,
                'wire_segments': len([line for line in geometry.split('\n') if line.strip().startswith('GW')]) if geometry else 0
            }
            results.append(result)
            
            # Check if type matches expectation
            if design_type == test_case['expected_type']:
                logger.info(f"✓ Design type matches expectation: {design_type}")
            else:
                logger.warning(f"✗ Design type mismatch: expected {test_case['expected_type']}, got {design_type}")
        
        # Summary report
        logger.info(f"\n{'='*60}")
        logger.info("ADVANCED MEANDER TEST SUMMARY")
        logger.info(f"{'='*60}")
        
        total_tests = len(results)
        successful_tests = sum(1 for r in results if r['success'] and r['has_geometry'])
        type_matches = sum(1 for r in results if r['actual_type'] == r['expected_type'])
        
        logger.info(f"Total tests: {total_tests}")
        logger.info(f"Successful designs: {successful_tests}/{total_tests}")
        logger.info(f"Type matches: {type_matches}/{total_tests}")
        
        # Detailed results
        for result in results:
            status = "✓ PASS" if result['success'] and result['has_geometry'] else "✗ FAIL"
            type_match = "✓" if result['actual_type'] == result['expected_type'] else "✗"
            
            logger.info(f"{result['test_case']:<40} {status}")
            logger.info(f"  {'':<40} Type: {result['actual_type']} {type_match}")
            logger.info(f"  {'':<40} Geometry: {result['wire_segments']} wire segments")
        
        # Overall assessment
        success_rate = successful_tests / total_tests
        type_match_rate = type_matches / total_tests
        
        logger.info(f"\nSuccess rate: {success_rate:.1%}")
        logger.info(f"Type match rate: {type_match_rate:.1%}")
        
        if success_rate >= 0.8 and type_match_rate >= 0.8:
            logger.info("✓ Advanced meander functionality is working correctly!")
            return True
        else:
            logger.warning("⚠ Advanced meander functionality needs improvement")
            return False
            
    except Exception as e:
        logger.error(f"Advanced meander test failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Main test entry point."""
    try:
        logger.info("Advanced Meander Test Script")
        logger.info("=" * 50)
        
        success = test_advanced_meanders()
        
        if success:
            print("\n✓ Advanced meander test PASSED")
            print("The advanced meander functionality is working correctly!")
        else:
            print("\n✗ Advanced meander test FAILED")
            print("Check the log file for details.")
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
        return 0
    except Exception as e:
        print(f"Unexpected test error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
