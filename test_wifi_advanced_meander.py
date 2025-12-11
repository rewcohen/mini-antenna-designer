#!/usr/bin/env python3
"""Test script to specifically verify WiFi advanced meander functionality."""

import sys
from pathlib import Path
from loguru import logger

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

def test_wifi_advanced_meander():
    """Test advanced meander specifically for WiFi 2.4GHz band."""
    logger.info("Testing WiFi 2.4GHz advanced meander functionality")
    
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
        
        # Test WiFi 2.4GHz Extended band (should trigger advanced meander)
        wifi_band = BandPresets.get_all_bands()['wifi_2g_extend']
        logger.info(f"Testing WiFi band: {wifi_band.name}")
        logger.info(f"Frequencies: {wifi_band.frequencies}")
        
        # Generate design
        design_result = generator.generate_design(wifi_band)
        
        # Check results
        success = design_result.get('success', False)
        design_type = design_result.get('design_type', 'unknown')
        geometry = design_result.get('geometry', '')
        
        logger.info(f"Design generation: {'SUCCESS' if success else 'FAILED'}")
        logger.info(f"Design type: {design_type}")
        logger.info(f"Expected: advanced_meander_tri_band")
        logger.info(f"Geometry generated: {'YES' if geometry else 'NO'}")
        
        # Print results
        print(f"\n{'='*60}")
        print(f"WiFi 2.4GHz Advanced Meander Test")
        print(f"{'='*60}")
        print(f"Band: {wifi_band.name}")
        print(f"Frequencies: {wifi_band.frequencies}")
        print(f"Expected: advanced_meander_tri_band")
        print(f"Actual: {design_type}")
        print(f"Success: {'✓ PASS' if success else '✗ FAIL'}")
        print(f"Geometry: {'✓ GENERATED' if geometry else '✗ NOT GENERATED'}")
        
        # Check if it's working correctly
        if success and design_type == 'advanced_meander_tri_band':
            print(f"\n✓ WiFi 2.4GHz advanced meander test PASSED")
            print("The advanced meander functionality is working correctly!")
            return True
        else:
            print(f"\n✗ WiFi 2.4GHz advanced meander test FAILED")
            print("Issue detected - design type or generation failed")
            return False
            
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        print(f"\n✗ Test failed with error: {str(e)}")
        return False

def main():
    """Main test entry point."""
    try:
        logger.info("WiFi Advanced Meander Test Script")
        logger.info("=" * 50)
        
        success = test_wifi_advanced_meander()
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
        return 0
    except Exception as e:
        print(f"Unexpected test error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
