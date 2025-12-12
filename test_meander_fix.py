#!/usr/bin/env python3
"""
Test script to verify the meander drawing fix.
This tests the simplified meander generation approach.
"""

import sys
from pathlib import Path
from loguru import logger

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

def test_meander_fix():
    """Test the meander generation fix."""
    logger.info("Testing meander drawing fix...")

    try:
        # Import required modules
        from design import AdvancedMeanderTrace
        from draw_meander import parse_nec2_geometry, draw_ascii_meander, generate_simple_svg, analyze_pattern

        logger.info("✓ All modules imported successfully")

        # Initialize meander trace generator
        trace = AdvancedMeanderTrace()
        logger.info("✓ AdvancedMeanderTrace initialized")

        # Test with a simple frequency
        test_frequency = 200.0  # MHz

        # Generate advanced meander geometry
        logger.info(f"Generating meander for {test_frequency} MHz...")
        geometry = trace.generate_advanced_meander(test_frequency)

        if not geometry or not geometry.strip():
            logger.error("❌ Failed to generate meander geometry")
            return False

        logger.info(f"✓ Generated geometry with {len(geometry.split())} lines")

        # Parse the geometry
        segments = parse_nec2_geometry(geometry)
        logger.info(f"✓ Parsed {len(segments)} wire segments")

        # Analyze the pattern
        analysis = analyze_pattern(segments)
        logger.info(f"Pattern Analysis:")
        logger.info(f"  Total length: {analysis['total_length']:.3f} inches")
        logger.info(f"  Dimensions: {analysis['dimensions'][0]:.3f}\" × {analysis['dimensions'][1]:.3f}\"")
        logger.info(f"  Horizontal segments: {analysis['horizontal_count']}")
        logger.info(f"  Vertical segments: {analysis['vertical_count']}")
        logger.info(f"  Pattern type: {analysis['pattern_type']}")

        # Check if we have a proper meander pattern
        if analysis['pattern_type'] == 'meander':
            logger.info("✓ Proper meander pattern detected")
        else:
            logger.warning(f"⚠ Pattern type is {analysis['pattern_type']}, expected 'meander'")

        # Generate ASCII visualization
        ascii_art = draw_ascii_meander(segments, width=80, height=20)
        logger.info("\nASCII Visualization:")
        logger.info(ascii_art)

        # Generate SVG visualization
        svg_file = "test_meander_fix.svg"
        generate_simple_svg(segments, svg_file)
        logger.info(f"✓ SVG written to: {svg_file}")

        # Check for pattern quality
        success = True
        issues = []

        # Check for reasonable dimensions
        width, height = analysis['dimensions']
        if width < 0.5 or height < 0.1:
            issues.append("Pattern dimensions too small")
            success = False

        # Check for reasonable segment count
        if len(segments) < 10:
            issues.append("Too few segments")
            success = False

        # Check for proper meander characteristics
        if analysis['vertical_count'] < analysis['horizontal_count'] * 0.2:
            issues.append("Not enough vertical segments (should have proper meandering)")
            success = False

        if issues:
            logger.warning("⚠ Issues found:")
            for issue in issues:
                logger.warning(f"  - {issue}")
        else:
            logger.info("✓ All pattern quality checks passed")

        # Visual inspection guidance
        logger.info("\nVisual Inspection Guide:")
        logger.info("1. ASCII art should show a clear meander pattern (alternating lines)")
        logger.info("2. SVG should show continuous meandering, not parallel lines")
        logger.info("3. Pattern should use space efficiently across the substrate")
        logger.info("4. No repeated identical horizontal lines")

        return success

    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Main test entry point."""
    try:
        logger.info("Meander Drawing Fix Test")
        logger.info("=" * 50)

        success = test_meander_fix()

        if success:
            print("\n✅ Meander fix test PASSED")
            print("The meander generation appears to be working correctly!")
            print("Check the ASCII output above and test_meander_fix.svg for visual confirmation.")
        else:
            print("\n❌ Meander fix test FAILED")
            print("Check the log output for details.")

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
        return 0
    except Exception as e:
        print(f"Unexpected test error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
