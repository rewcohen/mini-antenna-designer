"""Design storage system for saving and loading antenna designs."""
import json
import os
import uuid
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
import base64
from loguru import logger

from export import VectorExporter

class DesignMetadata:
    """Represents metadata for a saved antenna design."""

    def __init__(self,
                 design_id: str = None,
                 name: str = "",
                 frequencies_mhz: tuple = (2400, 5500, 5800),
                 substrate_width: float = 4.0,
                 substrate_height: float = 2.0,
                 trace_width_mil: float = 10.0,
                 design_type: str = "",
                 band_name: str = "",
                 performance_metrics: Dict[str, Any] = None,
                 custom_notes: str = "",
                 thumbnail_svg: str = "",
                 created_date: str = None):
        """Initialize design metadata.

        Args:
            design_id: Unique identifier (auto-generated if not provided)
            name: Human-readable design name
            frequencies_mhz: Tuple of three frequencies in MHz
            substrate_width: Substrate width in inches
            substrate_height: Substrate height in inches
            trace_width_mil: Trace width in mils
            design_type: Type of antenna design (e.g., 'advanced_meander_tri_band')
            band_name: Frequency band name
            performance_metrics: Dictionary of performance data
            custom_notes: User notes about the design
            thumbnail_svg: Base64-encoded SVG thumbnail
            created_date: ISO format date string
        """
        self.design_id = design_id or str(uuid.uuid4())
        self.name = name or f"Design_{self.design_id[:8]}"
        self.frequencies_mhz = frequencies_mhz
        self.substrate_width = substrate_width
        self.substrate_height = substrate_height
        self.trace_width_mil = trace_width_mil
        self.design_type = design_type
        self.band_name = band_name
        self.performance_metrics = performance_metrics or {}
        self.custom_notes = custom_notes
        self.thumbnail_svg = thumbnail_svg
        self.created_date = created_date or datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary for JSON serialization."""
        return {
            'design_id': self.design_id,
            'name': self.name,
            'frequencies_mhz': list(self.frequencies_mhz),
            'substrate_width': self.substrate_width,
            'substrate_height': self.substrate_height,
            'trace_width_mil': self.trace_width_mil,
            'design_type': self.design_type,
            'band_name': self.band_name,
            'performance_metrics': self.performance_metrics,
            'custom_notes': self.custom_notes,
            'thumbnail_svg': self.thumbnail_svg,
            'created_date': self.created_date
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DesignMetadata':
        """Create metadata object from dictionary."""
        return cls(
            design_id=data.get('design_id'),
            name=data.get('name', ''),
            frequencies_mhz=tuple(data.get('frequencies_mhz', [2400, 5500, 5800])),
            substrate_width=data.get('substrate_width', 4.0),
            substrate_height=data.get('substrate_height', 2.0),
            trace_width_mil=data.get('trace_width_mil', 10.0),
            design_type=data.get('design_type', ''),
            band_name=data.get('band_name', ''),
            performance_metrics=data.get('performance_metrics', {}),
            custom_notes=data.get('custom_notes', ''),
            thumbnail_svg=data.get('thumbnail_svg', ''),
            created_date=data.get('created_date')
        )

    def update_from_design_result(self, design_result: Dict[str, Any]):
        """Update metadata from design generation result."""
        self.frequencies_mhz = (design_result.get('freq1_mhz', self.frequencies_mhz[0]),
                               design_result.get('freq2_mhz', self.frequencies_mhz[1]),
                               design_result.get('freq3_mhz', self.frequencies_mhz[2]))
        self.design_type = design_result.get('design_type', self.design_type)
        self.band_name = design_result.get('band_name', self.band_name)

        # Update performance metrics
        if 'metrics' in design_result:
            self.performance_metrics.update(design_result['metrics'])

        # Update validation info
        if 'validation' in design_result:
            self.performance_metrics['validation'] = design_result['validation']


class DesignStorage:
    """Handles saving and loading antenna designs with metadata."""

    def __init__(self, storage_dir: str = None):
        """Initialize design storage.

        Args:
            storage_dir: Directory for storing designs (default: ~/designs)
        """
        try:
            if storage_dir is None:
                home_dir = Path.home()
                storage_dir = home_dir / "mini-antenna-designer" / "designs"

            self.storage_dir = Path(storage_dir)

            # Create storage directory with error handling
            try:
                self.storage_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Design storage directory created/verified: {self.storage_dir}")
            except PermissionError as e:
                logger.error(f"Permission denied creating storage directory {self.storage_dir}: {str(e)}")
                raise Exception(f"Cannot create design storage directory. Check permissions: {str(e)}")
            except Exception as e:
                logger.error(f"Failed to create storage directory {self.storage_dir}: {str(e)}")
                raise Exception(f"Cannot initialize design storage: {str(e)}")

            # Verify directory is writable
            try:
                test_file = self.storage_dir / ".storage_test"
                test_file.touch()
                test_file.unlink()
                logger.info("Storage directory is writable")
            except Exception as e:
                logger.error(f"Storage directory is not writable: {str(e)}")
                raise Exception(f"Design storage directory is not writable: {str(e)}")

            # Initialize SVG exporter for thumbnails
            self.thumbnail_exporter = VectorExporter()

            logger.info(f"Design storage initialized at: {self.storage_dir}")

        except Exception as e:
            logger.critical(f"Failed to initialize design storage: {str(e)}")
            raise

    def generate_timestamp_filename(self, base_name: str, design_metadata: DesignMetadata) -> str:
        """Generate unique filename with timestamp.

        Args:
            base_name: Base filename
            design_metadata: Design metadata for context

        Returns:
            str: Unique timestamped filename
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        freq_part = "_".join([f"{f:g}" for f in design_metadata.frequencies_mhz])
        clean_name = base_name.replace(" ", "_").replace("/", "_")
        return f"design_{timestamp}_{freq_part}_{clean_name}"

    def save_design(self, geometry: str, metadata: DesignMetadata,
                   design_result: Optional[Dict] = None) -> str:
        """Save antenna design with metadata.

        Args:
            geometry: NEC2 geometry string
            metadata: Design metadata
            design_result: Optional full design result from generator

        Returns:
            str: Path to saved design file

        Raises:
            Exception: If save fails
        """
        try:
            # Update metadata from design result if provided
            if design_result:
                metadata.update_from_design_result(design_result)

            # Generate thumbnail
            metadata.thumbnail_svg = self._generate_thumbnail(geometry, metadata)

            # Create design data structure
            design_data = {
                'metadata': metadata.to_dict(),
                'geometry': geometry,
                'version': '1.0',
                'software': 'Mini Antenna Designer v1.0'
            }

            # Generate unique filename
            base_name = metadata.name or "antenna_design"
            filename = f"{self.generate_timestamp_filename(base_name, metadata)}.json"
            design_path = self.storage_dir / filename

            # Save to JSON file
            with open(design_path, 'w', encoding='utf-8') as f:
                json.dump(design_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Saved design '{metadata.name}' to {design_path}")
            return str(design_path)

        except Exception as e:
            logger.error(f"Failed to save design '{metadata.name}': {str(e)}")
            raise

    def load_design(self, design_path: str) -> tuple:
        """Load antenna design from file.

        Args:
            design_path: Path to design file

        Returns:
            tuple: (DesignMetadata, geometry_string)

        Raises:
            FileNotFoundError: If design file doesn't exist
            Exception: If load fails
        """
        try:
            design_path = Path(design_path)
            if not design_path.exists():
                raise FileNotFoundError(f"Design file not found: {design_path}")

            with open(design_path, 'r', encoding='utf-8') as f:
                design_data = json.load(f)

            # Extract metadata and geometry
            metadata_dict = design_data.get('metadata', {})
            metadata = DesignMetadata.from_dict(metadata_dict)
            geometry = design_data.get('geometry', '')

            logger.info(f"Loaded design '{metadata.name}' from {design_path}")
            return metadata, geometry

        except Exception as e:
            logger.error(f"Failed to load design from {design_path}: {str(e)}")
            raise

    def list_designs(self, sort_by: str = 'created_date', reverse: bool = True) -> List[Dict[str, Any]]:
        """List all saved designs with metadata.

        Args:
            sort_by: Field to sort by ('name', 'created_date', 'band_name', etc.)
            reverse: Sort in reverse order (newest first)

        Returns:
            List of design dictionaries with metadata
        """
        try:
            designs = []

            # Find all design files
            for design_file in self.storage_dir.glob("*.json"):
                try:
                    with open(design_file, 'r', encoding='utf-8') as f:
                        design_data = json.load(f)

                    metadata_dict = design_data.get('metadata', {})
                    metadata_dict['file_path'] = str(design_file)
                    metadata_dict['file_size'] = design_file.stat().st_size

                    designs.append(metadata_dict)

                except Exception as e:
                    logger.warning(f"Failed to load design file {design_file}: {str(e)}")
                    continue

            # Sort designs
            if sort_by in ['name', 'created_date', 'band_name', 'design_type']:
                designs.sort(key=lambda x: x.get(sort_by, ''), reverse=reverse)
            elif sort_by == 'file_size':
                designs.sort(key=lambda x: x.get('file_size', 0), reverse=reverse)

            logger.info(f"Listed {len(designs)} designs from {self.storage_dir}")
            return designs

        except Exception as e:
            logger.error(f"Failed to list designs: {str(e)}")
            return []

    def delete_design(self, design_path: str) -> bool:
        """Delete a saved design.

        Args:
            design_path: Path to design file

        Returns:
            bool: True if deleted successfully
        """
        try:
            design_path = Path(design_path)
            if design_path.exists():
                design_path.unlink()
                logger.info(f"Deleted design file: {design_path}")
                return True
            else:
                logger.warning(f"Design file not found for deletion: {design_path}")
                return False

        except Exception as e:
            logger.error(f"Failed to delete design {design_path}: {str(e)}")
            return False

    def search_designs(self, query: str, search_fields: List[str] = None) -> List[Dict[str, Any]]:
        """Search designs by query string.

        Args:
            query: Search query string
            search_fields: Fields to search in (default: all text fields)

        Returns:
            List of matching design dictionaries
        """
        try:
            if search_fields is None:
                search_fields = ['name', 'band_name', 'design_type', 'custom_notes']

            query_lower = query.lower()
            all_designs = self.list_designs()

            matches = []
            for design in all_designs:
                for field in search_fields:
                    field_value = str(design.get(field, '')).lower()
                    if query_lower in field_value:
                        matches.append(design)
                        break  # Found match, no need to check other fields

            logger.info(f"Search for '{query}' found {len(matches)} matches")
            return matches

        except Exception as e:
            logger.error(f"Search failed for query '{query}': {str(e)}")
            return []

    def get_design_stats(self) -> Dict[str, Any]:
        """Get statistics about saved designs.

        Returns:
            Dictionary with design library statistics
        """
        try:
            designs = self.list_designs()

            stats = {
                'total_designs': len(designs),
                'total_size_bytes': sum(d.get('file_size', 0) for d in designs),
                'design_types': {},
                'band_types': {},
                'frequency_ranges': {},
                'date_range': {}
            }

            if designs:
                # Count design types
                for design in designs:
                    design_type = design.get('design_type', 'unknown')
                    band_name = design.get('band_name', 'unknown')

                    stats['design_types'][design_type] = stats['design_types'].get(design_type, 0) + 1
                    stats['band_types'][band_name] = stats['band_types'].get(band_name, 0) + 1

                # Get date range
                dates = [d.get('created_date', '') for d in designs if d.get('created_date')]
                if dates:
                    stats['date_range'] = {
                        'oldest': min(dates),
                        'newest': max(dates)
                    }

            logger.info(f"Generated stats for {stats['total_designs']} designs")
            return stats

        except Exception as e:
            logger.error(f"Failed to generate design stats: {str(e)}")
            return {}

    def _generate_thumbnail(self, geometry: str, metadata: DesignMetadata) -> str:
        """Generate SVG thumbnail for design.

        Args:
            geometry: NEC2 geometry string
            metadata: Design metadata

        Returns:
            str: Base64-encoded SVG thumbnail
        """
        try:
            # Create small SVG thumbnail (200x100 pixels)
            # Scale down the design for thumbnail view

            if not geometry or not geometry.strip():
                return ""

            # Use existing SVG export logic but scale for thumbnail
            wire_segments = self.thumbnail_exporter._parse_geometry(geometry)

            if not wire_segments:
                return ""

            # Calculate bounds
            coords = []
            for x1, y1, x2, y2, _ in wire_segments:
                coords.extend([(x1, y1), (x2, y2)])

            if not coords:
                return ""

            x_coords = [c[0] for c in coords]
            y_coords = [c[1] for c in coords]

            min_x, max_x = min(x_coords), max(x_coords)
            min_y, max_y = min(y_coords), max(y_coords)

            # Thumbnail dimensions
            thumb_width, thumb_height = 200, 100
            margin = 10

            # Scale to fit thumbnail
            design_width = max_x - min_x
            design_height = max_y - min_y

            if design_width > 0 and design_height > 0:
                scale_x = (thumb_width - 2 * margin) / design_width
                scale_y = (thumb_height - 2 * margin) / design_height
                scale = min(scale_x, scale_y)
            else:
                scale = 1.0

            # Generate simplified SVG paths
            paths = []
            for x1, y1, x2, y2, radius in wire_segments:
                # Scale coordinates for thumbnail
                tx1 = margin + (x1 - min_x) * scale
                ty1 = thumb_height - margin - (y1 - min_y) * scale  # Flip Y for SVG coordinates
                tx2 = margin + (x2 - min_x) * scale
                ty2 = thumb_height - margin - (y2 - min_y) * scale

                stroke_width = max(radius * scale * 0.5, 1.0)  # Thin lines for thumbnail

                path = f'M {tx1:.1f} {ty1:.1f} L {tx2:.1f} {ty2:.1f}'
                paths.append(f'<path d="{path}" stroke="black" stroke-width="{stroke_width}" fill="none"/>')

            paths_str = '\n      '.join(paths)

            # Create minimal SVG
            svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{thumb_width}" height="{thumb_height}" viewBox="0 0 {thumb_width} {thumb_height}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{thumb_width}" height="{thumb_height}" fill="white"/>
  <g stroke-linecap="round">
    {paths_str}
  </g>
</svg>'''

            # Convert to base64 for storage
            svg_bytes = svg.encode('utf-8')
            b64_svg = base64.b64encode(svg_bytes).decode('utf-8')

            return f"data:image/svg+xml;base64,{b64_svg}"

        except Exception as e:
            logger.warning(f"Failed to generate thumbnail: {str(e)}")
            return ""

    def import_designs(self, import_dir: Path) -> int:
        """Import designs from another directory.

        Args:
            import_dir: Directory to import designs from

        Returns:
            int: Number of designs imported
        """
        try:
            import_count = 0
            import_path = Path(import_dir)

            for json_file in import_path.glob("*.json"):
                try:
                    # Copy file to storage directory
                    dest_file = self.storage_dir / json_file.name
                    dest_file.write_bytes(json_file.read_bytes())
                    import_count += 1

                except Exception as e:
                    logger.warning(f"Failed to import {json_file}: {str(e)}")
                    continue

            logger.info(f"Imported {import_count} designs from {import_dir}")
            return import_count

        except Exception as e:
            logger.error(f"Import failed from {import_dir}: {str(e)}")
            return 0


logger.info("Design storage system initialized with thumbnail generation and JSON serialization")
