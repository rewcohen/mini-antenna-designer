#!/usr/bin/env python3
"""Test script to verify meandering and export functionality."""

import sys
from pathlib import Path
from loguru import logger

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

def test_meander_export():
    """Test meandering generation and vector export."""
    logger.info("Testing meander generation and export functionality")

    try:
        # Import required modules
        from presets import BandPresets
        from design_generator import AntennaDesignGenerator
        from core import NEC2Interface
        from export import VectorExporter

        logger.info("All modules imported successfully")

        # Initialize components
        nec_interface = NEC2Interface()
        generator = AntennaDesignGenerator(nec_interface)
        exporter = VectorExporter(output_dir="exports")

        logger.info("Components initialized")

        # Test WiFi 2.4GHz band (should trigger advanced meander)
        wifi_band = BandPresets.get_all_bands()['wifi_2g_extend']
        logger.info(f"Testing band: {wifi_band.name}")
        logger.info(f"Frequencies: {wifi_band.frequencies}")

        # Generate design
        logger.info("Generating antenna design...")
        design_result = generator.generate_design(wifi_band)

        # Check results
        success = design_result.get('success', False)
        design_type = design_result.get('design_type', 'unknown')
        geometry = design_result.get('geometry', '')

        logger.info(f"Design generation: {'SUCCESS' if success else 'FAILED'}")
        logger.info(f"Design type: {design_type}")
        logger.info(f"Geometry length: {len(geometry)} characters")
        logger.info(f"Geometry lines: {len(geometry.split()) if geometry else 0}")

        if not geometry or not geometry.strip():
            logger.error("No geometry generated!")
            return False

        # Count GW lines (wire segments)
        gw_lines = [line for line in geometry.split('\n') if line.strip().startswith('GW')]
        logger.info(f"Wire segments (GW lines): {len(gw_lines)}")

        # Export to all formats
        metadata = {
            'band_name': wifi_band.name,
            'freq1_mhz': wifi_band.frequencies[0],
            'freq2_mhz': wifi_band.frequencies[1],
            'freq3_mhz': wifi_band.frequencies[2],
            'design_type': design_type
        }

        logger.info("Exporting to vector formats...")

        # Export SVG
        try:
            svg_path = exporter.export_geometry(geometry, 'wifi_meander_antenna', 'svg', metadata)
            logger.info(f"SVG exported to: {svg_path}")
            print(f"\nSVG file created: {svg_path}")

            # Verify file exists
            if Path(svg_path).exists():
                file_size = Path(svg_path).stat().st_size
                logger.info(f"SVG file verified: {file_size} bytes")
                print(f"SVG file size: {file_size} bytes")
            else:
                logger.error(f"SVG file not found at: {svg_path}")

        except Exception as e:
            logger.error(f"SVG export failed: {str(e)}")
            import traceback
            traceback.print_exc()

        # Export DXF
        try:
            dxf_path = exporter.export_geometry(geometry, 'wifi_meander_antenna', 'dxf', metadata)
            logger.info(f"DXF exported to: {dxf_path}")
            print(f"DXF file created: {dxf_path}")

            if Path(dxf_path).exists():
                file_size = Path(dxf_path).stat().st_size
                logger.info(f"DXF file verified: {file_size} bytes")
                print(f"DXF file size: {file_size} bytes")

        except Exception as e:
            logger.error(f"DXF export failed: {str(e)}")
            import traceback
            traceback.print_exc()

        # Export PDF
        try:
            pdf_path = exporter.export_geometry(geometry, 'wifi_meander_antenna', 'pdf', metadata)
            logger.info(f"PDF exported to: {pdf_path}")
            print(f"PDF file created: {pdf_path}")

            if Path(pdf_path).exists():
                file_size = Path(pdf_path).stat().st_size
                logger.info(f"PDF file verified: {file_size} bytes")
                print(f"PDF file size: {file_size} bytes")

        except Exception as e:
            logger.error(f"PDF export failed: {str(e)}")
            import traceback
            traceback.print_exc()

        print(f"\n{'='*60}")
        print(f"Meander Export Test Results")
        print(f"{'='*60}")
        print(f"Band: {wifi_band.name}")
        print(f"Design Type: {design_type}")
        print(f"Wire Segments: {len(gw_lines)}")
        print(f"Success: {'YES' if success and len(gw_lines) > 0 else 'NO'}")
        print(f"\nCheck the 'exports' directory for your vector files!")

        return True

    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test entry point."""
    try:
        logger.info("Meander Export Test Script")
        logger.info("=" * 50)

        success = test_meander_export()

        return 0 if success else 1

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
