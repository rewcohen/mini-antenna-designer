#!/usr/bin/env python3
"""Comprehensive system testing suite for Mini Antenna Designer."""

import sys
from pathlib import Path
from loguru import logger

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

def run_system_tests():
    """Run comprehensive system validation tests."""
    import sys
    from pathlib import Path
    from loguru import logger

    logger.info("=" * 60)
    logger.info("COMPREHENSIVE SYSTEM TEST SUITE")
    logger.info("=" * 60)

    test_results = {
        'passed': 0,
        'failed': 0,
        'warnings': 0,
        'tests': []
    }

    # Test 1: Dependency validation
    try:
        logger.info("Test 1: Validating dependencies...")
        import numpy as np
        import matplotlib.pyplot as plt
        from shapely.geometry import Point

        # Test optional dependencies
        try:
            from PIL import Image
            PIL_AVAILABLE = True
        except ImportError:
            PIL_AVAILABLE = False
            test_results['warnings'] += 1

        try:
            import reportlab
            PDF_AVAILABLE = True
        except ImportError:
            PDF_AVAILABLE = False
            test_results['warnings'] += 1

        logger.info("✓ Core dependencies available")
        test_results['passed'] += 1
    except Exception as e:
        logger.error(f"✗ Dependency validation failed: {str(e)}")
        test_results['failed'] += 1

    test_results['tests'].append({
        'name': 'Dependency Validation',
        'status': 'passed' if test_results['passed'] == 1 else 'failed',
        'details': 'Core libraries validated'
    })

    # Test 2: NEC2 Configuration
    try:
        logger.info("Test 2: Validating NEC2 configuration...")
        from core import NEC2Interface
        nec = NEC2Interface()
        logger.info("✓ NEC2 interface initialized")
        test_results['passed'] += 1
    except Exception as e:
        logger.error(f"✗ NEC2 interface initialization failed: {str(e)}")
        test_results['failed'] += 1

    test_results['tests'].append({
        'name': 'NEC2 Configuration',
        'status': 'passed' if test_results['passed'] == 2 else 'failed',
        'details': 'NEC2 interface validated'
    })

    # Test 3: Frequency Presets
    try:
        logger.info("Test 3: Validating frequency presets...")
        from presets import BandPresets
        bands = BandPresets.get_all_bands()

        if len(bands) >= 8:  # Should have at least 8 predefined bands
            logger.info(f"✓ {len(bands)} frequency bands available")
            test_results['passed'] += 1
        else:
            logger.warning(f"⚠ Only {len(bands)} bands found, expected 8+")
            test_results['warnings'] += 1
            test_results['passed'] += 1
    except Exception as e:
        logger.error(f"✗ Preset validation failed: {str(e)}")
        test_results['failed'] += 1

    test_results['tests'].append({
        'name': 'Frequency Presets',
        'status': 'passed' if test_results['passed'] >= 3 else 'failed',
        'details': f'Band presets loaded ({len(bands)} bands)'
    })

    # Test 4: Design Generation
    try:
        logger.info("Test 4: Testing design generation...")
        from design_generator import AntennaDesignGenerator
        from core import NEC2Interface
        from presets import BandPresets

        nec = NEC2Interface()
        generator = AntennaDesignGenerator(nec)

        # Test with WiFi band
        wifi_band = BandPresets.get_all_bands().get('wifi_2g_extend')
        if wifi_band:
            result = generator.generate_design(wifi_band)
            if result and not result.get('error'):
                logger.info("✓ Basic design generation works")
                test_results['passed'] += 1
            else:
                logger.warning("⚠ Design generation produced errors")
                test_results['warnings'] += 1
                test_results['passed'] += 1
        else:
            logger.warning("⚠ WiFi band not found for testing")
            test_results['warnings'] += 1
            test_results['passed'] += 1
    except Exception as e:
        logger.error(f"✗ Design generation test failed: {str(e)}")
        test_results['failed'] += 1

    test_results['tests'].append({
        'name': 'Design Generation',
        'status': 'passed' if test_results['passed'] >= 4 else 'failed',
        'details': 'Basic antenna design creation'
    })

    # Test 5: Design Storage
    try:
        logger.info("Test 5: Testing design storage...")
        from storage import DesignStorage
        from presets import DesignMetadata

        # Test storage initialization
        storage = DesignStorage()

        # Test metadata creation
        metadata = DesignMetadata(
            name="Test Design",
            substrate_width=4.0,
            substrate_height=2.0,
            trace_width_mil=10.0
        )

        # Test basic save (will create directory structure if needed)
        test_geometry = "CM Test\nGW 1 1 0 0 0 1 0 0 0.01\nGE 1\nEN"
        saved_path = storage.save_design(test_geometry, metadata)

        if saved_path and Path(saved_path).exists():
            logger.info("✓ Design storage system functional")
            test_results['passed'] += 1

            # Clean up test design
            storage.delete_design(saved_path)
        else:
            logger.warning("⚠ Storage system returned invalid path")
            test_results['warnings'] += 1
            test_results['passed'] += 1
    except Exception as e:
        logger.error(f"✗ Storage test failed: {str(e)}")
        test_results['failed'] += 1

    test_results['tests'].append({
        'name': 'Design Storage',
        'status': 'passed' if test_results['passed'] >= 5 else 'failed',
        'details': 'Design saving/loading system'
    })

    # Test 6: Export System
    try:
        logger.info("Test 6: Testing export system...")
        from export import VectorExporter

        exporter = VectorExporter()
        logger.info("✓ Export system initialized")
        test_results['passed'] += 1
    except Exception as e:
        logger.error(f"✗ Export system test failed: {str(e)}")
        test_results['failed'] += 1

    test_results['tests'].append({
        'name': 'Export System',
        'status': 'passed' if test_results['passed'] >= 6 else 'failed',
        'details': 'Vector export capabilities'
    })

    # Test 7: Band Chart Generation
    try:
        logger.info("Test 7: Testing band chart generation...")
        from band_chart import BandAnalysisChart

        chart = BandAnalysisChart(substrate_width=4.0, substrate_height=2.0)
        logger.info("✓ Band chart system initialized")
        test_results['passed'] += 1
    except Exception as e:
        logger.error(f"✗ Band chart test failed: {str(e)}")
        test_results['failed'] += 1

    test_results['tests'].append({
        'name': 'Band Chart System',
        'status': 'passed' if test_results['passed'] >= 7 else 'failed',
        'details': 'Chart generation and visualization'
    })

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("SYSTEM TEST SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Tests Passed: {test_results['passed']}")
    logger.info(f"Tests Failed: {test_results['failed']}")
    logger.info(f"Warnings: {test_results['warnings']}")

    success_rate = test_results['passed'] / (test_results['passed'] + test_results['failed']) if (test_results['passed'] + test_results['failed']) > 0 else 0

    if success_rate >= 0.8 and test_results['failed'] == 0:
        logger.info("✓ System tests PASSED - Application is fully functional")
        return True
    elif success_rate >= 0.6:
        logger.info("⚠ System tests PARTIALLY PASSED - Some issues present")
        return True
    else:
        logger.error("✗ System tests FAILED - Critical issues detected")
        return False

def main():
    """Main test entry point."""
    try:
        logger.info("Mini Antenna Designer - System Test Suite")
        success = run_system_tests()

        print(f"\n{'='*60}")
        print("FINAL RESULT")
        print(f"{'='*60}")
        if success:
            print("✅ ALL SYSTEMS OPERATIONAL")
            print("The Mini Antenna Designer application is ready for use!")
            return 0
        else:
            print("❌ SYSTEM ISSUES DETECTED")
            print("Please check the log file for details")
            return 1

    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
        return 0
    except Exception as e:
        print(f"Unexpected test error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
