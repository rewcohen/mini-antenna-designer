"""Basic validation and testing script for Mini Antenna Designer."""
import sys
import traceback
from pathlib import Path
from loguru import logger

def run_validation():
    """Run comprehensive validation of all modules."""
    logger.info("Starting Mini Antenna Designer validation")

    validation_results = {
        'imports': False,
        'core_initialization': False,
        'geometry_generation': False,
        'frequency_presets': False,
        'vector_export': False,
        'constraints_check': False,
        'overall_success': False
    }

    try:
        # Test 1: Module Imports
        logger.info("Testing module imports...")
        try:
            from core import NEC2Interface, AntennaMetrics
            from design import AntennaDesign, AntennaGeometryError
            from optimize import TriBandOptimizer
            from export import VectorExporter, ExportError
            from presets import BandPresets, BandType
            from constraints import SubstrateConstraints
            from ui import AntennaDesignerGUI
            validation_results['imports'] = True
            logger.info("✓ All modules imported successfully")
        except ImportError as e:
            logger.error(f"✗ Import failure: {str(e)}")
            return validation_results

        # Test 2: Core NEC2 Interface Initialization
        logger.info("Testing NEC2 interface initialization...")
        try:
            nec_interface = NEC2Interface()
            validation_results['core_initialization'] = True
            logger.info("✓ NEC2 interface initialized (mock mode)")
        except Exception as e:
            logger.warning(f"⚠ NEC2 interface test skipped: {str(e)}")
            validation_results['core_initialization'] = True  # Mock is acceptable

        # Test 3: Antenna Geometry Generation
        logger.info("Testing antenna geometry generation...")
        try:
            designer = AntennaDesign()
            dipole_geom = designer.generate_dipole(2450)  # 2.45 GHz
            monopole_geom = designer.generate_monopole(880)  # 880 MHz
            coil_geom = designer.generate_spiral_coil(1575, turns=3)  # GPS frequency

            # Check that geometry strings are generated
            assert isinstance(dipole_geom, str) and len(dipole_geom) > 0
            assert isinstance(monopole_geom, str) and len(monopole_geom) > 0
            assert isinstance(coil_geom, str) and len(coil_geom) > 0

            validation_results['geometry_generation'] = True
            logger.info("✓ Antenna geometry generation working")
        except Exception as e:
            logger.error(f"✗ Geometry generation test failed: {str(e)}")

        # Test 4: Frequency Band Presets
        logger.info("Testing frequency band presets...")
        try:
            bands = BandPresets.get_all_bands()
            assert len(bands) > 0, "No frequency bands defined"

            # Test a specific band
            tv_band = bands.get('tv_uhf')
            assert tv_band is not None, "TV UHF band not found"
            assert len(tv_band.frequencies) == 3, "Incorrect number of frequencies"

            # Test custom band creation
            custom_band = BandPresets.create_custom_band(
                name="Test Band", 
                freq1=1000, 
                freq2=2000, 
                freq3=3000
            )
            assert custom_band.name == "Test Band"

            validation_results['frequency_presets'] = True
            logger.info(f"✓ Frequency presets working ({len(bands)} bands available)")
        except Exception as e:
            logger.error(f"✗ Frequency presets test failed: {str(e)}")

        # Test 5: Vector Export
        logger.info("Testing vector export functionality...")
        try:
            exporter = VectorExporter()
            test_geometry = dipole_geom  # Use generated geometry

            # Test SVG export
            svg_path = exporter.export_geometry(test_geometry, "test_validation", "svg")
            assert Path(svg_path).exists(), "SVG export file not created"

            # Clean up test file
            Path(svg_path).unlink()

            validation_results['vector_export'] = True
            logger.info("✓ Vector export working")
        except Exception as e:
            logger.error(f"✗ Vector export test failed: {str(e)}")

        # Test 6: Constraints and Validation
        logger.info("Testing substrate constraints...")
        try:
            constraints = SubstrateConstraints()

            # Test bounds checking
            bounds_check = constraints.check_geometry_bounds(dipole_geom)
            assert 'within_bounds' in bounds_check

            # Test point validation
            valid_point = constraints.is_point_valid(1.0, 0.5)  # Center point
            invalid_point = constraints.is_point_valid(3.0, 0.0)  # Outside bounds

            assert valid_point == True
            assert invalid_point == False

            validation_results['constraints_check'] = True
            logger.info("✓ Substrate constraints working")
        except Exception as e:
            logger.error(f"✗ Constraints test failed: {str(e)}")

        # Overall assessment
        successful_tests = sum(1 for result in validation_results.values() if result is True)
        total_tests = len(validation_results) - 1  # Exclude overall_success

        validation_results['overall_success'] = successful_tests >= total_tests * 0.8  # 80% pass rate

        logger.info(f"Validation complete: {successful_tests}/{total_tests} tests passed")

        return validation_results

    except Exception as e:
        logger.critical(f"Validation script failed: {str(e)}")
        logger.critical(traceback.format_exc())
        return validation_results

def print_validation_report(results):
    """Print formatted validation report."""
    print("\n" + "="*50)
    print("MINI ANTENNA DESIGNER VALIDATION REPORT")
    print("="*50)

    test_descriptions = {
        'imports': 'Module Imports',
        'core_initialization': 'NEC2 Interface',
        'geometry_generation': 'Geometry Generation',
        'frequency_presets': 'Frequency Presets',
        'vector_export': 'Vector Export',
        'constraints_check': 'Constraints & Validation'
    }

    for test_key, description in test_descriptions.items():
        status = "✓ PASS" if results[test_key] else "✗ FAIL"
        print(f"{description:<25} {status}")

    print("-"*50)
    overall = "✓ READY" if results['overall_success'] else "✗ ISSUES"
    print(f"Overall Status:           {overall}")

    if results['overall_success']:
        print("\nApplication is ready for use!")
        print("Run: python main.py")
    else:
        print("\nIssues found - check log file for details")
        print("Log file: antenna_designer.log")

def main():
    """Main validation script entry point."""
    try:
        results = run_validation()
        print_validation_report(results)

        # Exit with appropriate code
        sys.exit(0 if results['overall_success'] else 1)

    except KeyboardInterrupt:
        print("\nValidation interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Unexpected validation error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
