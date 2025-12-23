"""Test suite for antenna_utils module."""
import numpy as np
from antenna_utils import NEC2GeometryParser, AntennaValidator, AntennaVisualizer, analyze_pattern

class TestNEC2GeometryParser:
    """Test NEC2 geometry parsing functionality."""
    
    def test_parse_geometry_basic(self):
        """Test basic geometry parsing."""
        geometry = """GW 1 1 0 0 0 1 0 0 0.005
GW 2 1 1 0 0 2 0 0 0.005"""
        
        segments = NEC2GeometryParser.parse_geometry(geometry)
        assert len(segments) == 2
        assert segments[0] == (0.0, 0.0, 1.0, 0.0, 0.005)
        assert segments[1] == (1.0, 0.0, 2.0, 0.0, 0.005)
    
    def test_parse_geometry_surface_patch(self):
        """Test surface patch parsing."""
        geometry = """SP 0 4 0 0 0 1 0 0 1 1 0 0 1 0"""
        
        segments = NEC2GeometryParser.parse_geometry(geometry)
        assert len(segments) >= 3  # Should create outline segments
    
    def test_parse_geometry_empty(self):
        """Test empty geometry handling."""
        segments = NEC2GeometryParser.parse_geometry("")
        assert segments == []
    
    def test_calculate_total_length(self):
        """Test total length calculation."""
        segments = [(0.0, 0.0, 1.0, 0.0, 0.005), (1.0, 0.0, 1.0, 1.0, 0.005)]
        total_length = NEC2GeometryParser.calculate_total_length(segments)
        expected = 1.0 + 1.0  # 1 inch horizontal + 1 inch vertical
        assert abs(total_length - expected) < 0.001
    
    def test_extract_bounds(self):
        """Test bounds extraction."""
        segments = [(0.0, 0.0, 1.0, 0.0, 0.005), (1.0, 0.0, 1.0, 1.0, 0.005)]
        min_x, min_y, max_x, max_y = NEC2GeometryParser.extract_bounds(segments)
        assert min_x == 0.0
        assert min_y == 0.0
        assert max_x == 1.0
        assert max_y == 1.0
    
    def test_calculate_segment_length(self):
        """Test individual segment length calculation."""
        gw_line = "GW 1 1 0 0 0 1 0 0 0.005"
        length = NEC2GeometryParser.calculate_segment_length(gw_line)
        assert abs(length - 1.0) < 0.001

class TestAntennaValidator:
    """Test antenna validation functionality."""
    
    def test_validate_for_etching_basic(self):
        """Test basic etching validation."""
        geometry = """GW 1 1 0 0 0 1 0 0 0.005
GW 2 1 1 0 0 2 0 0 0.005"""
        
        validation = AntennaValidator.validate_for_etching(geometry)
        assert validation['element_count'] == 2
        assert validation['etching_ready'] is True
    
    def test_validate_for_etching_empty(self):
        """Test validation with empty geometry."""
        validation = AntennaValidator.validate_for_etching("")
        assert validation['warnings']
        assert validation['etching_ready'] is False
    
    def test_validate_geometry_bounds(self):
        """Test bounds validation."""
        segments = [(0.0, 0.0, 1.0, 0.0, 0.005), (1.0, 0.0, 1.0, 1.0, 0.005)]
        validation = AntennaValidator.validate_geometry_bounds("", 2.0, 2.0)
        assert validation['within_bounds'] is True
    
    def test_check_trace_widths(self):
        """Test trace width validation."""
        segments = [(0.0, 0.0, 1.0, 0.0, 0.005), (1.0, 0.0, 2.0, 0.0, 0.010)]
        validation = AntennaValidator.check_trace_widths(segments)
        
        assert len(validation['trace_status']) == 2
        assert validation['trace_widths_mils'] == [5.0, 10.0]
        assert validation['min_trace_width'] == 5.0
        assert validation['max_trace_width'] == 10.0
        assert validation['overall_status'] == 'good'

class TestAntennaVisualizer:
    """Test antenna visualization functionality."""
    
    def test_render_ascii_basic(self):
        """Test ASCII rendering."""
        segments = [(0.0, 0.0, 1.0, 0.0, 0.005), (1.0, 0.0, 1.0, 1.0, 0.005)]
        ascii_art = AntennaVisualizer(mode='debug').render_ascii(segments, 40, 20)
        
        assert isinstance(ascii_art, str)
        assert len(ascii_art) > 0
        assert 'Segments:' in ascii_art
    
    def test_generate_svg_basic(self):
        """Test SVG generation."""
        segments = [(0.0, 0.0, 1.0, 0.0, 0.005), (1.0, 0.0, 1.0, 1.0, 0.005)]
        svg_content = AntennaVisualizer(mode='production').generate_svg(segments)
        
        assert isinstance(svg_content, str)
        assert '<svg' in svg_content
        assert '</svg>' in svg_content
        assert 'trace' in svg_content.lower()
    
    def test_generate_svg_with_metadata(self):
        """Test SVG generation with metadata."""
        segments = [(0.0, 0.0, 1.0, 0.0, 0.005)]
        metadata = {'band_name': 'VHF', 'freq1_mhz': 100}
        svg_content = AntennaVisualizer(mode='analysis').generate_svg(segments, metadata)
        
        assert 'VHF' in svg_content
        assert '100' in svg_content
    
    def test_analyze_pattern(self):
        """Test pattern analysis."""
        segments = [(0.0, 0.0, 1.0, 0.0, 0.005), (1.0, 0.0, 1.0, 1.0, 0.005)]
        analysis = analyze_pattern(segments)
        
        assert isinstance(analysis, dict)
        assert 'pattern_type' in analysis
        assert 'connectivity' in analysis
        assert 'segment_count' in analysis
        assert analysis['segment_count'] == 2

class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_parse_nec2_geometry(self):
        """Test convenience function for geometry parsing."""
        from antenna_utils import parse_nec2_geometry
        
        geometry = "GW 1 1 0 0 0 1 0 0 0.005"
        segments = parse_nec2_geometry(geometry)
        
        assert isinstance(segments, list)
        assert len(segments) == 1
    
    def test_draw_ascii_meander(self):
        """Test convenience function for ASCII rendering."""
        from antenna_utils import draw_ascii_meander
        
        segments = [(0.0, 0.0, 1.0, 0.0, 0.005)]
        ascii_art = draw_ascii_meander(segments, 40, 20)
        
        assert isinstance(ascii_art, str)
        assert len(ascii_art) > 0
    
    def test_generate_simple_svg(self):
        """Test convenience function for SVG generation."""
        from antenna_utils import generate_simple_svg
        
        segments = [(0.0, 0.0, 1.0, 0.0, 0.005)]
        svg_content = generate_simple_svg(segments, "test.svg")
        
        assert isinstance(svg_content, str)
        assert '<svg' in svg_content
    
    def test_analyze_pattern(self):
        """Test convenience function for pattern analysis."""
        from antenna_utils import analyze_pattern
        
        segments = [(0.0, 0.0, 1.0, 0.0, 0.005)]
        analysis = analyze_pattern(segments)
        
        assert isinstance(analysis, dict)
        assert 'pattern_type' in analysis
    
    def test_validate_for_etching(self):
        """Test convenience function for etching validation."""
        from antenna_utils import validate_for_etching
        
        geometry = "GW 1 1 0 0 0 1 0 0 0.005"
        validation = validate_for_etching(geometry)
        
        assert isinstance(validation, dict)
        assert 'element_count' in validation

class TestIntegration:
    """Integration tests for the entire antenna_utils module."""
    
    def test_full_workflow(self):
        """Test complete workflow from geometry to validation to visualization."""
        # Create test geometry
        geometry = """GW 1 1 0 0 0 1 0 0 0.005
GW 2 1 1 0 0 1 1 0 0.005
GW 3 1 1 1 0 0 1 0 0.005"""
        
        # Parse geometry
        segments = NEC2GeometryParser.parse_geometry(geometry)
        assert len(segments) == 3
        
        # Validate for etching
        validation = AntennaValidator.validate_for_etching(geometry)
        assert validation['element_count'] == 3
        assert validation['etching_ready'] is True
        
        # Generate visualizations
        visualizer = AntennaVisualizer(mode='production')
        ascii_art = visualizer.render_ascii(segments, 60, 30)
        svg_content = visualizer.generate_svg(segments)
        
        assert isinstance(ascii_art, str)
        assert isinstance(svg_content, str)
        assert '<svg' in svg_content
        
        # Analyze pattern
        analysis = analyze_pattern(segments)
        assert analysis['segment_count'] == 3
        assert analysis['total_length'] > 0
    
    def test_error_handling(self):
        """Test error handling throughout the module."""
        # Test with invalid geometry
        invalid_geometry = "INVALID LINE"
        segments = NEC2GeometryParser.parse_geometry(invalid_geometry)
        assert segments == []
        
        # Test with empty geometry
        validation = AntennaValidator.validate_for_etching("")
        assert validation['warnings']
        assert validation['etching_ready'] is False
        
        # Test with invalid segments
        invalid_segments = [(0.0, 0.0, 1.0, 1.0, -1.0)]  # Negative radius
        analysis = analyze_pattern(invalid_segments)
        assert analysis['segment_count'] == 1

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
