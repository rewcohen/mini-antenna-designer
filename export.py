"""Vector export for laser etching - SVG and DXF formats."""
from typing import Dict, List, Optional
import os
import math
import platform
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path
from loguru import logger
import ezdxf
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

class ExportError(Exception):
    """Custom exception for export failures."""
    pass

class VectorExporter:
    """Export optimized antenna designs to vector formats for laser etching."""

    def __init__(self, output_dir: str = "exports"):
        """Initialize exporter with output directory."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Scaling and precision settings
        self.svg_scale = 100      # SVG units per inch (standard: 100)
        self.dxf_scale = 1000     # DXF units per inch (mils: 1 inch = 1000 mils)
        self.scale_factor = 1000  # Default scale factor (legacy, kept for compatibility)
        self.precision = 4        # Decimal places for coordinates
        self.min_trace_width = 0.005  # Minimum trace width in inches
        self.etch_clearance = 0.010  # Clearance around traces for etching

        logger.info(f"Vector exporter initialized with output dir: {output_dir}")

    def generate_timestamp_filename(self, base_filename: str, frequency: str = "unknown") -> str:
        """Generate timestamp-based filename to prevent duplicates.

        Args:
            base_filename: Base filename without extension
            frequency: Frequency band for the filename

        Returns:
            str: Timestamped filename with format: antenna_export_[YYYYMMDD]_[HHMMSS]_[frequency]
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Clean frequency string for filename
        clean_freq = frequency.replace(".", "").replace("/", "_").replace(" ", "")
        return f"antenna_export_{timestamp}_{clean_freq}_{base_filename}"

    def export_geometry(self, geometry: str, filename: str, format_type: str = 'svg',
                       metadata: Optional[Dict] = None) -> str:
        """Export geometry to specified vector format.

        Args:
            geometry: NEC2 geometry string
            filename: Output filename (without extension)
            format_type: Export format ('svg', 'dxf', 'pdf')
            metadata: Optional metadata to embed

        Returns:
            str: Path to exported file

        Raises:
            ExportError: If export fails
        """
        try:
            format_type = format_type.lower()

            if format_type == 'svg':
                output_path = self._export_svg(geometry, filename, metadata)
            elif format_type == 'dxf':
                output_path = self._export_dxf(geometry, filename, metadata)
            elif format_type == 'pdf':
                output_path = self._export_pdf(geometry, filename, metadata)
            else:
                raise ExportError(f"Unsupported format: {format_type}")

            logger.info(f"Exported {filename} to {format_type.upper()} format")
            return str(output_path)

        except Exception as e:
            logger.error(f"Export error: {str(e)}")
            raise ExportError(f"Failed to export geometry: {str(e)}")

    def _export_svg(self, geometry: str, filename: str, metadata: Optional[Dict] = None) -> Path:
        """Export geometry to SVG format for laser etching."""
        try:
            svg_path = self.output_dir / f"{filename}.svg"

            # Parse geometry and extract wire segments
            wire_segments = self._parse_geometry(geometry)

            # Create SVG content
            svg_content = self._generate_svg_content(wire_segments, metadata)

            # Write SVG file
            with open(svg_path, 'w') as f:
                f.write(svg_content)

            logger.debug(f"SVG exported to {svg_path}")
            return svg_path

        except Exception as e:
            logger.error(f"SVG export error: {str(e)}")
            raise

    def _export_dxf(self, geometry: str, filename: str, metadata: Optional[Dict] = None) -> Path:
        """Export geometry to DXF format for CAD software."""
        try:
            dxf_path = self.output_dir / f"{filename}.dxf"

            # Create DXF document
            doc = ezdxf.new('R2010')
            msp = doc.modelspace()

            # Parse geometry
            wire_segments = self._parse_geometry(geometry)

            # Add wire segments to DXF
            for segment in wire_segments:
                x1, y1, x2, y2, radius = segment

                if abs(x2 - x1) < 0.0001 and abs(y2 - y1) < 0.0001:
                    # Point representation for very small segments
                    msp.add_point((x1 * self.dxf_scale, y1 * self.dxf_scale))
                else:
                    # Line segment
                    msp.add_line(
                        (x1 * self.dxf_scale, y1 * self.dxf_scale),
                        (x2 * self.dxf_scale, y2 * self.dxf_scale)
                    )

            # Add layer information for etching
            doc.layers.new('ETCH', dxfattribs={'color': 1})  # Red layer for etch lines
            doc.layers.new('KEEP', dxfattribs={'color': 3})  # Green layer for keep areas

            # Add metadata as text if provided
            if metadata:
                self._add_metadata_to_dxf(msp, metadata)

            # Save DXF file
            doc.saveas(dxf_path)

            logger.debug(f"DXF exported to {dxf_path}")
            return dxf_path

        except Exception as e:
            logger.error(f"DXF export error: {str(e)}")
            raise

    def _export_pdf(self, geometry: str, filename: str, metadata: Optional[Dict] = None) -> Path:
        """Export geometry to PDF format with dimensions."""
        try:
            pdf_path = self.output_dir / f"{filename}.pdf"

            # Create PDF with proper dimensions
            c = canvas.Canvas(str(pdf_path), pagesize=letter)

            # Parse and draw geometry
            wire_segments = self._parse_geometry(geometry)
            self._draw_geometry_to_pdf(c, wire_segments)

            # Add metadata and dimensions
            if metadata:
                self._add_metadata_to_pdf(c, metadata)

            # Add dimension annotations
            self._add_dimensions_to_pdf(c, wire_segments)

            c.save()

            logger.debug(f"PDF exported to {pdf_path}")
            return pdf_path

        except Exception as e:
            logger.error(f"PDF export error: {str(e)}")
            raise

    def _parse_geometry(self, geometry: str) -> List[tuple]:
        """Parse NEC2 geometry string into wire segments."""
        try:
            segments = []
            lines = geometry.split('\n')

            tag_offset = 0
            for line in lines:
                if not line.strip():
                    continue

                parts = line.split()
                if len(parts) >= 8 and parts[0] == 'GW':
                    # Parse GW card: GW tag segments x1 y1 z1 x2 y2 z2 radius
                    try:
                        tag = int(float(parts[1]))
                        segments_count = int(float(parts[2]))
                        x1 = float(parts[3])
                        y1 = float(parts[4])
                        z1 = float(parts[5])  # Usually 0 for planar antennas
                        x2 = float(parts[6])
                        y2 = float(parts[7])
                        z2 = float(parts[8])  # Usually 0 for planar antennas
                        radius = float(parts[9]) if len(parts) > 9 else self.min_trace_width

                        segments.append((x1, y1, x2, y2, radius))

                    except (ValueError, IndexError) as e:
                        logger.warning(f"Failed to parse GW line: {line} - {str(e)}")
                        continue

                elif len(parts) >= 4 and parts[0] == 'SP':
                    # Handle surface patches (SP cards)
                    try:
                        # Convert surface patch to outline wires
                        patch_segments = self._surface_patch_to_wires(parts)
                        segments.extend(patch_segments)
                    except Exception as e:
                        logger.warning(f"Failed to parse SP line: {line} - {str(e)}")
                        continue

            logger.debug(f"Parsed {len(segments)} wire segments from geometry")
            return segments

        except Exception as e:
            logger.error(f"Geometry parsing error: {str(e)}")
            return []

    def _surface_patch_to_wires(self, sp_parts: List[str]) -> List[tuple]:
        """Convert surface patch (SP) to outline wires."""
        try:
            # SP format: SP tag segments x1 y1 z1 x2 y2 z2 x3 y3 z3 x4 y4 z4
            coords = []
            i = 3  # Skip SP tag segments
            while i < len(sp_parts) - 2:
                x = float(sp_parts[i])
                y = float(sp_parts[i+1])
                z = float(sp_parts[i+2])  # Usually 0 for planar
                coords.append((x, y))
                i += 3

            # Create wire segments for patch outline
            segments = []
            radius = self.min_trace_width

            if len(coords) >= 3:
                for i in range(len(coords)):
                    x1, y1 = coords[i]
                    x2, y2 = coords[(i + 1) % len(coords)]
                    segments.append((x1, y1, x2, y2, radius))

            return segments

        except Exception as e:
            logger.warning(f"Surface patch to wires conversion error: {str(e)}")
            return []

    def _generate_svg_content(self, wire_segments: List[tuple],
                            metadata: Optional[Dict] = None) -> str:
        """Generate SVG content for wire segments with professional labeling."""
        try:
            # Calculate bounds
            coords = []
            for x1, y1, x2, y2, _ in wire_segments:
                coords.extend([(x1, y1), (x2, y2)])

            if not coords:
                return self._get_empty_svg()

            x_coords = [c[0] for c in coords]
            y_coords = [c[1] for c in coords]

            min_x, max_x = min(x_coords), max(x_coords)
            min_y, max_y = min(y_coords), max(y_coords)

            # Calculate dimensions
            total_width = max_x - min_x
            total_height = max_y - min_y

            # Add margins for labels
            margin = 0.2  # 0.2 inch margin for labels
            label_space = 0.5  # 0.5 inch space for labels
            width = (max_x - min_x + 2 * margin + label_space) * self.svg_scale
            height = (max_y - min_y + 2 * margin) * self.svg_scale

            # Transform function for coordinates
            def transform(x, y):
                return ((x - min_x + margin) * self.svg_scale,
                       height - ((y - min_y + margin) * self.svg_scale))

            # Generate SVG paths for antenna traces
            paths = []
            for x1, y1, x2, y2, radius in wire_segments:
                tx1, ty1 = transform(x1, y1)
                tx2, ty2 = transform(x2, y2)
                stroke_width = max(radius * self.svg_scale, 2.0)  # Minimum 2 unit for visibility

                path = f'M {tx1:.{self.precision}f} {ty1:.{self.precision}f} L {tx2:.{self.precision}f} {ty2:.{self.precision}f}'
                paths.append(f'<path d="{path}" stroke="black" stroke-width="{stroke_width}" fill="none"/>')

            # Combine all paths
            paths_str = '\n    '.join(paths)

            # Generate professional labels and annotations
            annotations = self._generate_svg_annotations(wire_segments, transform, total_width, total_height, metadata)

            # Generate SVG with professional layout
            svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width:.1f}" height="{height:.1f}" viewBox="0 0 {width:.1f} {height:.1f}" xmlns="http://www.w3.org/2000/svg">
  <title>Professional PCB Antenna Design - Laser Etching Ready</title>
  <desc>Log-Periodic Antenna for TV VHF Bands - Generated by Mini Antenna Designer</desc>
  
  <defs>
    <style>
      .dimension-text {{ font-family: Arial, sans-serif; font-size: 12px; fill: #333; }}
      .label-text {{ font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; fill: #000; }}
      .title-text {{ font-family: Arial, sans-serif; font-size: 18px; font-weight: bold; fill: #000; }}
      .subtitle-text {{ font-family: Arial, sans-serif; font-size: 12px; fill: #666; }}
      .dimension-line {{ stroke: #666; stroke-width: 1; fill: none; }}
      .feed-point {{ fill: red; stroke: darkred; stroke-width: 2; }}
    </style>
  </defs>
  
  <!-- Background -->
  <rect width="{width:.1f}" height="{height:.1f}" fill="white" stroke="black" stroke-width="2"/>
  
  <!-- Grid lines for alignment (optional) -->
  <g stroke="#e0e0e0" stroke-width="0.5" opacity="0.5">
    {self._generate_grid_lines(width, height, transform)}
  </g>
  
  <!-- Antenna wire segments -->
  <g stroke-linecap="round" stroke-linejoin="round" id="antenna-traces">
    {paths_str}
  </g>
  
  <!-- Professional annotations -->
  {annotations}
  
  <!-- Origin marker (feed point) -->
  <circle cx="{transform(0, 0)[0]:.1f}" cy="{transform(0, 0)[1]:.1f}" r="8" class="feed-point"/>
  <text x="{transform(0, 0)[0] + 15:.1f}" y="{transform(0, 0)[1]:.1f}" class="label-text">FEED POINT</text>
  
</svg>'''

            return svg

        except Exception as e:
            logger.error(f"SVG content generation error: {str(e)}")
            return self._get_empty_svg()

    def _generate_svg_annotations(self, wire_segments: List[tuple], transform_func,
                               total_width: float, total_height: float, metadata: Optional[Dict] = None) -> str:
        """Generate professional SVG annotations including dimensions and labels."""
        try:
            annotations = []

            # Title and information
            title_x = 20
            title_y = 30
            annotations.append(f'<text x="{title_x}" y="{title_y}" class="title-text">LOG-PERIODIC TV ANTENNA</text>')

            # Frequency information
            band_name = "Unknown"
            if metadata and 'band_name' in metadata:
                band_name = metadata["band_name"]
                freq_y = title_y + 20
                annotations.append(f'<text x="{title_x}" y="{freq_y}" class="subtitle-text">Band: {metadata["band_name"]}</text>')

            if metadata and 'freq1_mhz' in metadata:
                freq_y = (title_y + 20) if 'band_name' not in metadata else freq_y + 15
                freq_range = f"{metadata['freq1_mhz']:.0f}-{metadata.get('freq3_mhz', metadata['freq1_mhz']):.0f} MHz"
                annotations.append(f'<text x="{title_x}" y="{freq_y}" class="subtitle-text">Frequency: {freq_range}</text>')

            # Overall dimensions
            dim_y = title_y + 60
            annotations.append(f'<text x="{title_x}" y="{dim_y}" class="label-text">DIMENSIONS:</text>')
            annotations.append(f'<text x="{title_x}" y="{dim_y + 15}" class="dimension-text">Design Width: {total_width:.3f} inches ({total_width*1000:.0f} mils)</text>')
            annotations.append(f'<text x="{title_x}" y="{dim_y + 30}" class="dimension-text">Design Height: {total_height:.3f} inches ({total_height*1000:.0f} mils)</text>')

            # Manufacturing information
            manuf_y = dim_y + 60
            annotations.append(f'<text x="{title_x}" y="{manuf_y}" class="label-text">MANUFACTURING:</text>')
            annotations.append(f'<text x="{title_x}" y="{manuf_y + 15}" class="dimension-text">Trace Width: 10-20 mil (laser etching)</text>')

            # Use configured substrate size from metadata, fallback to calculated size
            substrate_width = total_width
            substrate_height = total_height
            if metadata and 'substrate_width' in metadata and 'substrate_height' in metadata:
                substrate_width = metadata['substrate_width']
                substrate_height = metadata['substrate_height']

            annotations.append(f'<text x="{title_x}" y="{manuf_y + 30}" class="dimension-text">Substrate: {substrate_width:.1f}" x {substrate_height:.1f}" FR-4 PCB</text>')
            annotations.append(f'<text x="{title_x}" y="{manuf_y + 45}" class="dimension-text">Scale: 1:1 (ready for production)</text>')
            
            # Dimension lines
            annotations.append(self._generate_dimension_lines(total_width, total_height, transform_func))
            
            return '\n  '.join(annotations)
            
        except Exception as e:
            logger.warning(f"Failed to generate SVG annotations: {str(e)}")
            return ""

    def _generate_grid_lines(self, width: float, height: float, transform_func) -> str:
        """Generate alignment grid lines."""
        try:
            grid_lines = []
            grid_spacing = 0.5 * self.scale_factor  # 0.5 inch grid
            
            # Vertical lines
            for x in range(0, int(width), int(grid_spacing)):
                grid_lines.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{height}"/>')
            
            # Horizontal lines
            for y in range(0, int(height), int(grid_spacing)):
                grid_lines.append(f'<line x1="0" y1="{y}" x2="{width}" y2="{y}"/>')
            
            return '\n    '.join(grid_lines)
            
        except Exception as e:
            logger.warning(f"Failed to generate grid lines: {str(e)}")
            return ""

    def _generate_dimension_lines(self, total_width: float, total_height: float, transform_func) -> str:
        """Generate dimension lines for the antenna."""
        try:
            dimensions = []
            
            # Get transformed coordinates for dimension lines
            origin_x, origin_y = transform_func(0, 0)
            
            # Width dimension line (bottom)
            width_start = transform_func(-total_width/2, -total_height/2 - 0.3)
            width_end = transform_func(total_width/2, -total_height/2 - 0.3)
            dimensions.append(f'<line x1="{width_start[0]:.1f}" y1="{width_start[1]:.1f}" x2="{width_end[0]:.1f}" y2="{width_end[1]:.1f}" class="dimension-line"/>')
            dimensions.append(f'<line x1="{width_start[0]:.1f}" y1="{width_start[1]-5:.1f}" x2="{width_start[0]:.1f}" y2="{width_start[1]+5:.1f}" class="dimension-line"/>')
            dimensions.append(f'<line x1="{width_end[0]:.1f}" y1="{width_end[1]-5:.1f}" x2="{width_end[0]:.1f}" y2="{width_end[1]+5:.1f}" class="dimension-line"/>')
            
            # Height dimension line (right side)
            height_start = transform_func(total_width/2 + 0.3, -total_height/2)
            height_end = transform_func(total_width/2 + 0.3, total_height/2)
            dimensions.append(f'<line x1="{height_start[0]:.1f}" y1="{height_start[1]:.1f}" x2="{height_end[0]:.1f}" y2="{height_end[1]:.1f}" class="dimension-line"/>')
            dimensions.append(f'<line x1="{height_start[0]-5:.1f}" y1="{height_start[1]:.1f}" x2="{height_start[0]+5:.1f}" y2="{height_start[1]:.1f}" class="dimension-line"/>')
            dimensions.append(f'<line x1="{height_end[0]-5:.1f}" y1="{height_end[1]:.1f}" x2="{height_end[0]+5:.1f}" y2="{height_end[1]:.1f}" class="dimension-line"/>')
            
            return '\n  '.join(dimensions)
            
        except Exception as e:
            logger.warning(f"Failed to generate dimension lines: {str(e)}")
            return ""

    def _get_empty_svg(self) -> str:
        """Generate empty SVG for error cases."""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="400" height="200" viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg">
  <text x="200" y="100" text-anchor="middle" font-family="Arial" font-size="16" fill="red">
    Error: No geometry to export
  </text>
</svg>'''

    def _add_metadata_to_dxf(self, msp, metadata: Dict) -> None:
        """Add metadata text to DXF file."""
        try:
            y_offset = 0
            for key, value in metadata.items():
                msp.add_text(f"{key}: {value}", dxfattribs={
                    'insert': (0, y_offset),
                    'height': 0.1 * self.scale_factor
                })
                y_offset -= 0.15 * self.scale_factor
        except Exception as e:
            logger.warning(f"Failed to add metadata to DXF: {str(e)}")

    def _draw_geometry_to_pdf(self, c, wire_segments: List[tuple]) -> None:
        """Draw geometry to PDF canvas."""
        try:
            c.setLineWidth(0.5)
            c.setStrokeColorRGB(0, 0, 0)

            for x1, y1, x2, y2, radius in wire_segments:
                # Convert inches to points (72 points per inch)
                px1 = (x1 + 2) * 72  # Offset for page margins
                py1 = (y1 + 1) * 72
                px2 = (x2 + 2) * 72
                py2 = (y2 + 1) * 72

                c.line(px1, py1, px2, py2)

        except Exception as e:
            logger.warning(f"PDF geometry drawing error: {str(e)}")

    def _add_metadata_to_pdf(self, c, metadata: Dict) -> None:
        """Add metadata text to PDF."""
        try:
            c.setFont("Helvetica", 10)
            y_position = 750

            for key, value in metadata.items():
                c.drawString(50, y_position, f"{key}: {value}")
                y_position -= 15

        except Exception as e:
            logger.warning(f"Failed to add metadata to PDF: {str(e)}")

    def _add_dimensions_to_pdf(self, c, wire_segments: List[tuple]) -> None:
        """Add dimension annotations to PDF."""
        try:
            c.setFont("Helvetica", 8)
            c.setStrokeColorRGB(0.5, 0.5, 0.5)

            if wire_segments:
                # Calculate overall dimensions
                coords = []
                for x1, y1, x2, y2, _ in wire_segments:
                    coords.extend([(x1, y1), (x2, y2)])

                x_coords = [c[0] for c in coords]
                y_coords = [c[1] for c in coords]

                total_width = max(x_coords) - min(x_coords)
                total_height = max(y_coords) - min(y_coords)

                # Add dimension text
                c.drawString(50, 50, f"Design Dimensions: {total_width:.3f} x {total_height:.3f} inches")
                c.drawString(50, 35, f"Scale: 1:1 (ready for laser etching)")

        except Exception as e:
            logger.warning(f"Failed to add dimensions to PDF: {str(e)}")

    def open_exports_folder(self) -> bool:
        """Open the exports folder in the system's file explorer.

        Returns:
            bool: True if folder was opened successfully, False otherwise
        """
        try:
            if not self.output_dir.exists():
                logger.warning(f"Output directory does not exist: {self.output_dir}")
                return False

            logger.info(f"Opening exports folder: {self.output_dir}")

            # Use platform-specific method to open the folder
            if platform.system() == "Windows":
                # Windows: use explorer command
                os.startfile(str(self.output_dir))
            elif platform.system() == "Darwin":
                # macOS: use open command
                subprocess.run(["open", str(self.output_dir)])
            elif platform.system() == "Linux":
                # Linux: try different file managers
                try:
                    subprocess.run(["xdg-open", str(self.output_dir)])
                except Exception:
                    # Fallback to nautilus if xdg-open fails
                    try:
                        subprocess.run(["nautilus", str(self.output_dir)])
                    except Exception:
                        logger.warning("No suitable file manager found for Linux")
                        return False
            else:
                logger.warning(f"Unsupported platform: {platform.system()}")
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to open exports folder: {str(e)}")
            return False

class EtchingValidator:
    """Validate exported designs for laser etching feasibility."""

    @staticmethod
    def validate_for_etching(geometry: str) -> Dict:
        """Check design against etching constraints."""
        validation = {
            'minimum_feature_size': True,
            'trace_width_consistent': True,
            'isolation_clearance': True,
            'total_area': 0.0,
            'complexity_score': 0,
            'warnings': [],
            'etching_ready': True,
            'element_count': 0  # Add missing key
        }

        try:
            from export import VectorExporter
            exporter = VectorExporter()
            segments = exporter._parse_geometry(geometry)

            if not segments:
                validation['warnings'].append("No valid antenna elements found in geometry")
                validation['etching_ready'] = False
                return validation

            min_radius = float('inf')
            trace_widths = []
            total_length = 0
            wire_count = 0

            for x1, y1, x2, y2, radius in segments:
                min_radius = min(min_radius, radius)
                trace_widths.append(radius)
                wire_count += 1
                
                # Calculate actual segment length
                segment_length = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                total_length += segment_length

            validation['element_count'] = wire_count
            validation['minimum_feature_size'] = min_radius >= 0.003  # 3 mil minimum
            validation['trace_width_consistent'] = len(set(f"{w:.3f}" for w in trace_widths)) <= 3
            validation['total_area'] = total_length * 0.005  # Rough estimate
            validation['complexity_score'] = min(wire_count // 10, 4)  # Cap at 4

            # Generate warnings
            if not validation['minimum_feature_size']:
                validation['warnings'].append("Some features may be below minimum laser resolution")
                validation['etching_ready'] = False

            if wire_count == 0:
                validation['warnings'].append("No wire segments found in geometry")
                validation['etching_ready'] = False
            elif wire_count < 3:
                validation['warnings'].append("Very simple antenna design - may not be effective")

            if wire_count > 50:
                validation['warnings'].append("High complexity may require multiple etching passes")

            if min_radius < 0.005:  # 5 mil minimum for good quality
                validation['warnings'].append("Trace width below recommended minimum (5 mil)")

        except Exception as e:
            validation['warnings'].append(f"Validation error: {str(e)}")
            validation['etching_ready'] = False

        return validation
