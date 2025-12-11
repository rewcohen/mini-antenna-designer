"""
Customizable Pattern/Circuit PDF Generator
==========================================
Generates repeating geometric patterns (like Greek key/meander) or circuit-like designs.
Uses reportlab for PDF generation with path-based drawing for maximum flexibility.
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch, mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import black, white, Color
from dataclasses import dataclass, field
from typing import List, Tuple, Callable, Optional
from enum import Enum
import math


# =============================================================================
# CORE DATA STRUCTURES
# =============================================================================

class Direction(Enum):
    """Cardinal directions for path drawing."""
    UP = (0, 1)
    DOWN = (0, -1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)


@dataclass
class PathCommand:
    """A single drawing command (move or line)."""
    command: str  # 'M' for move, 'L' for line, 'C' for close
    dx: float = 0  # relative x movement (in grid units)
    dy: float = 0  # relative y movement (in grid units)


@dataclass
class PatternCell:
    """
    Defines a single cell of a repeating pattern.
    Paths are defined in relative grid units (0-1 scale within cell).
    """
    paths: List[List[PathCommand]] = field(default_factory=list)
    fill_color: Optional[Color] = None
    stroke_color: Color = black
    stroke_width: float = 1.0


@dataclass 
class PatternConfig:
    """Configuration for pattern rendering."""
    cell_size: float = 50  # Size of each cell in points
    grid_cols: int = 5     # Number of columns
    grid_rows: int = 5     # Number of rows
    line_width: float = 2.0
    stroke_color: Color = black
    fill_color: Color = white
    background_color: Optional[Color] = None
    margin: float = 0.5 * inch
    page_size: Tuple[float, float] = letter


# =============================================================================
# PATTERN DEFINITIONS
# =============================================================================

def create_greek_key_cell(variant: int = 0) -> PatternCell:
    """
    Creates a Greek key (meander) pattern cell.
    Variant controls rotation/mirroring:
        0: spiral from top-right going counterclockwise
        1: spiral from top-left going clockwise  
        2: spiral from bottom-left going counterclockwise
        3: spiral from bottom-right going clockwise
    """
    # Define the spiral path for variant 0 (top-right, counterclockwise inward)
    # Path starts at outer edge and spirals inward
    
    if variant == 0:
        # Spiral from top-right, going left then down
        paths = [[
            PathCommand('M', 1.0, 1.0),   # Start top-right
            PathCommand('L', 0.0, 1.0),   # Line to top-left
            PathCommand('L', 0.0, 0.0),   # Line to bottom-left
            PathCommand('L', 0.8, 0.0),   # Line toward bottom-right
            PathCommand('L', 0.8, 0.8),   # Line up
            PathCommand('L', 0.2, 0.8),   # Line left
            PathCommand('L', 0.2, 0.2),   # Line down
            PathCommand('L', 0.6, 0.2),   # Line right
            PathCommand('L', 0.6, 0.6),   # Line up
            PathCommand('L', 0.4, 0.6),   # Line left (center)
        ]]
    elif variant == 1:
        # Mirror of variant 0 (spiral from top-left, going right)
        paths = [[
            PathCommand('M', 0.0, 1.0),   # Start top-left
            PathCommand('L', 1.0, 1.0),   # Line to top-right
            PathCommand('L', 1.0, 0.0),   # Line to bottom-right
            PathCommand('L', 0.2, 0.0),   # Line toward bottom-left
            PathCommand('L', 0.2, 0.8),   # Line up
            PathCommand('L', 0.8, 0.8),   # Line right
            PathCommand('L', 0.8, 0.2),   # Line down
            PathCommand('L', 0.4, 0.2),   # Line left
            PathCommand('L', 0.4, 0.6),   # Line up
            PathCommand('L', 0.6, 0.6),   # Line right (center)
        ]]
    elif variant == 2:
        # Spiral from bottom-left, going right then up
        paths = [[
            PathCommand('M', 0.0, 0.0),   # Start bottom-left
            PathCommand('L', 1.0, 0.0),   # Line to bottom-right
            PathCommand('L', 1.0, 1.0),   # Line to top-right
            PathCommand('L', 0.2, 1.0),   # Line toward top-left
            PathCommand('L', 0.2, 0.2),   # Line down
            PathCommand('L', 0.8, 0.2),   # Line right
            PathCommand('L', 0.8, 0.8),   # Line up
            PathCommand('L', 0.4, 0.8),   # Line left
            PathCommand('L', 0.4, 0.4),   # Line down
            PathCommand('L', 0.6, 0.4),   # Line right (center)
        ]]
    else:  # variant == 3
        # Spiral from bottom-right, going left then up
        paths = [[
            PathCommand('M', 1.0, 0.0),   # Start bottom-right
            PathCommand('L', 0.0, 0.0),   # Line to bottom-left
            PathCommand('L', 0.0, 1.0),   # Line to top-left
            PathCommand('L', 0.8, 1.0),   # Line toward top-right
            PathCommand('L', 0.8, 0.2),   # Line down
            PathCommand('L', 0.2, 0.2),   # Line left
            PathCommand('L', 0.2, 0.8),   # Line up
            PathCommand('L', 0.6, 0.8),   # Line right
            PathCommand('L', 0.6, 0.4),   # Line down
            PathCommand('L', 0.4, 0.4),   # Line left (center)
        ]]
    
    return PatternCell(paths=paths)


def create_square_spiral_cell(turns: int = 2, inward: bool = True) -> PatternCell:
    """Creates a square spiral with configurable number of turns."""
    paths = [[]]
    step = 1.0 / (turns * 2 + 1)
    
    x, y = 0.0, 0.0
    paths[0].append(PathCommand('M', x, y))
    
    directions = [(1, 0), (0, 1), (-1, 0), (0, -1)]  # right, up, left, down
    
    for turn in range(turns * 4):
        dx, dy = directions[turn % 4]
        length = 1.0 - (turn // 2 + 1) * step
        if length <= 0:
            break
        x += dx * length
        y += dy * length
        paths[0].append(PathCommand('L', x, y))
    
    return PatternCell(paths=paths)


def create_circuit_trace_cell(trace_type: str = "corner") -> PatternCell:
    """
    Creates circuit-board style traces.
    trace_type options: "corner", "t_junction", "cross", "straight_h", "straight_v"
    """
    trace_width = 0.15  # Width of trace as fraction of cell
    
    if trace_type == "corner":
        # L-shaped corner trace
        paths = [[
            PathCommand('M', 0.5 - trace_width, 0.0),
            PathCommand('L', 0.5 - trace_width, 0.5 - trace_width),
            PathCommand('L', 1.0, 0.5 - trace_width),
            PathCommand('L', 1.0, 0.5 + trace_width),
            PathCommand('L', 0.5 + trace_width, 0.5 + trace_width),
            PathCommand('L', 0.5 + trace_width, 0.0),
            PathCommand('C'),  # Close path
        ]]
    elif trace_type == "t_junction":
        paths = [[
            # Horizontal bar
            PathCommand('M', 0.0, 0.5 - trace_width),
            PathCommand('L', 1.0, 0.5 - trace_width),
            PathCommand('L', 1.0, 0.5 + trace_width),
            PathCommand('L', 0.0, 0.5 + trace_width),
            PathCommand('C'),
        ], [
            # Vertical stub down
            PathCommand('M', 0.5 - trace_width, 0.5 - trace_width),
            PathCommand('L', 0.5 + trace_width, 0.5 - trace_width),
            PathCommand('L', 0.5 + trace_width, 0.0),
            PathCommand('L', 0.5 - trace_width, 0.0),
            PathCommand('C'),
        ]]
    elif trace_type == "cross":
        paths = [[
            # Horizontal bar
            PathCommand('M', 0.0, 0.5 - trace_width),
            PathCommand('L', 1.0, 0.5 - trace_width),
            PathCommand('L', 1.0, 0.5 + trace_width),
            PathCommand('L', 0.0, 0.5 + trace_width),
            PathCommand('C'),
        ], [
            # Vertical bar
            PathCommand('M', 0.5 - trace_width, 0.0),
            PathCommand('L', 0.5 + trace_width, 0.0),
            PathCommand('L', 0.5 + trace_width, 1.0),
            PathCommand('L', 0.5 - trace_width, 1.0),
            PathCommand('C'),
        ]]
    elif trace_type == "straight_h":
        paths = [[
            PathCommand('M', 0.0, 0.5 - trace_width),
            PathCommand('L', 1.0, 0.5 - trace_width),
            PathCommand('L', 1.0, 0.5 + trace_width),
            PathCommand('L', 0.0, 0.5 + trace_width),
            PathCommand('C'),
        ]]
    else:  # straight_v
        paths = [[
            PathCommand('M', 0.5 - trace_width, 0.0),
            PathCommand('L', 0.5 + trace_width, 0.0),
            PathCommand('L', 0.5 + trace_width, 1.0),
            PathCommand('L', 0.5 - trace_width, 1.0),
            PathCommand('C'),
        ]]
    
    cell = PatternCell(paths=paths)
    cell.fill_color = black
    return cell


def create_maze_cell(walls: str = "NESW") -> PatternCell:
    """
    Creates a maze-like cell with walls on specified sides.
    walls: string containing N, E, S, W for which walls to draw
    """
    wall_thickness = 0.1
    paths = []
    
    if 'N' in walls:
        paths.append([
            PathCommand('M', 0.0, 1.0 - wall_thickness),
            PathCommand('L', 1.0, 1.0 - wall_thickness),
            PathCommand('L', 1.0, 1.0),
            PathCommand('L', 0.0, 1.0),
            PathCommand('C'),
        ])
    if 'S' in walls:
        paths.append([
            PathCommand('M', 0.0, 0.0),
            PathCommand('L', 1.0, 0.0),
            PathCommand('L', 1.0, wall_thickness),
            PathCommand('L', 0.0, wall_thickness),
            PathCommand('C'),
        ])
    if 'E' in walls:
        paths.append([
            PathCommand('M', 1.0 - wall_thickness, 0.0),
            PathCommand('L', 1.0, 0.0),
            PathCommand('L', 1.0, 1.0),
            PathCommand('L', 1.0 - wall_thickness, 1.0),
            PathCommand('C'),
        ])
    if 'W' in walls:
        paths.append([
            PathCommand('M', 0.0, 0.0),
            PathCommand('L', wall_thickness, 0.0),
            PathCommand('L', wall_thickness, 1.0),
            PathCommand('L', 0.0, 1.0),
            PathCommand('C'),
        ])
    
    cell = PatternCell(paths=paths)
    cell.fill_color = black
    return cell


# =============================================================================
# PATTERN GRID GENERATORS
# =============================================================================

def greek_key_grid(rows: int, cols: int) -> List[List[PatternCell]]:
    """
    Generates a grid of Greek key cells with proper alternation.
    The pattern alternates to create the interlocking meander effect.
    """
    grid = []
    for row in range(rows):
        row_cells = []
        for col in range(cols):
            # Alternate pattern based on position
            # Creates the checkerboard-like alternation seen in the image
            if (row + col) % 2 == 0:
                variant = 0 if row % 2 == 0 else 2
            else:
                variant = 1 if row % 2 == 0 else 3
            row_cells.append(create_greek_key_cell(variant))
        grid.append(row_cells)
    return grid


def circuit_grid(rows: int, cols: int, pattern: Optional[List[List[str]]] = None) -> List[List[PatternCell]]:
    """
    Generates a circuit-like pattern grid.
    If pattern is provided, use it as a template (list of trace_type strings).
    Otherwise, generate a default pattern.
    """
    if pattern is None:
        # Default: create a simple repeating circuit pattern
        pattern = []
        for row in range(rows):
            row_pattern = []
            for col in range(cols):
                if row == 0 and col == 0:
                    row_pattern.append("corner")
                elif row % 2 == 0:
                    row_pattern.append("straight_h")
                else:
                    row_pattern.append("straight_v")
            pattern.append(row_pattern)
    
    grid = []
    for row in range(rows):
        row_cells = []
        for col in range(cols):
            trace_type = pattern[row % len(pattern)][col % len(pattern[0])]
            row_cells.append(create_circuit_trace_cell(trace_type))
        grid.append(row_cells)
    return grid


def custom_grid(rows: int, cols: int, cell_func: Callable[[int, int], PatternCell]) -> List[List[PatternCell]]:
    """
    Creates a custom grid using a provided function.
    cell_func(row, col) should return a PatternCell for that position.
    """
    grid = []
    for row in range(rows):
        row_cells = []
        for col in range(cols):
            row_cells.append(cell_func(row, col))
        grid.append(row_cells)
    return grid


# =============================================================================
# PDF RENDERER
# =============================================================================

class PatternRenderer:
    """Renders pattern grids to PDF."""
    
    def __init__(self, config: PatternConfig):
        self.config = config
    
    def render_cell(self, c: canvas.Canvas, cell: PatternCell, 
                    x: float, y: float, size: float):
        """Renders a single pattern cell at the given position."""
        c.saveState()
        
        for path in cell.paths:
            if not path:
                continue
                
            p = c.beginPath()
            current_x, current_y = x, y
            
            for cmd in path:
                abs_x = x + cmd.dx * size
                abs_y = y + cmd.dy * size
                
                if cmd.command == 'M':
                    p.moveTo(abs_x, abs_y)
                    current_x, current_y = abs_x, abs_y
                elif cmd.command == 'L':
                    p.lineTo(abs_x, abs_y)
                    current_x, current_y = abs_x, abs_y
                elif cmd.command == 'C':
                    p.close()
            
            # Set colors and stroke
            if cell.fill_color:
                c.setFillColor(cell.fill_color)
                c.setStrokeColor(cell.stroke_color or self.config.stroke_color)
                c.setLineWidth(cell.stroke_width or self.config.line_width)
                c.drawPath(p, fill=1, stroke=1)
            else:
                c.setStrokeColor(cell.stroke_color or self.config.stroke_color)
                c.setLineWidth(cell.stroke_width or self.config.line_width)
                c.drawPath(p, fill=0, stroke=1)
        
        c.restoreState()
    
    def render_grid(self, c: canvas.Canvas, grid: List[List[PatternCell]], 
                    start_x: float, start_y: float):
        """Renders the entire grid of pattern cells."""
        size = self.config.cell_size
        
        for row_idx, row in enumerate(grid):
            for col_idx, cell in enumerate(row):
                cell_x = start_x + col_idx * size
                cell_y = start_y - (row_idx + 1) * size  # Y goes down
                self.render_cell(c, cell, cell_x, cell_y, size)
    
    def render_to_pdf(self, grid: List[List[PatternCell]], filename: str,
                      title: Optional[str] = None):
        """Renders the pattern grid to a PDF file."""
        page_width, page_height = self.config.page_size
        c = canvas.Canvas(filename, pagesize=self.config.page_size)
        
        # Draw background if specified
        if self.config.background_color:
            c.setFillColor(self.config.background_color)
            c.rect(0, 0, page_width, page_height, fill=1, stroke=0)
        
        # Add title if provided
        start_y = page_height - self.config.margin
        if title:
            c.setFont("Helvetica-Bold", 16)
            c.setFillColor(black)
            c.drawString(self.config.margin, start_y, title)
            start_y -= 30
        
        # Calculate grid dimensions
        grid_width = len(grid[0]) * self.config.cell_size
        grid_height = len(grid) * self.config.cell_size
        
        # Center the grid
        start_x = (page_width - grid_width) / 2
        start_y = (page_height + grid_height) / 2
        
        # Set line properties
        c.setStrokeColor(self.config.stroke_color)
        c.setLineWidth(self.config.line_width)
        c.setLineCap(1)  # Round caps
        c.setLineJoin(1)  # Round joins
        
        # Draw background fill for the pattern area
        if self.config.fill_color:
            c.setFillColor(self.config.fill_color)
            c.rect(start_x, start_y - grid_height, grid_width, grid_height, 
                   fill=1, stroke=0)
        
        # Render the grid
        self.render_grid(c, grid, start_x, start_y)
        
        c.save()
        return filename


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def generate_greek_key_pdf(filename: str = "greek_key.pdf",
                           rows: int = 5, cols: int = 5,
                           cell_size: float = 80,
                           line_width: float = 4.0,
                           stroke_color: Color = black,
                           fill_color: Color = white,
                           page_size: Tuple[float, float] = letter) -> str:
    """Quick function to generate a Greek key pattern PDF."""
    config = PatternConfig(
        cell_size=cell_size,
        grid_rows=rows,
        grid_cols=cols,
        line_width=line_width,
        stroke_color=stroke_color,
        fill_color=fill_color,
        page_size=page_size
    )
    
    grid = greek_key_grid(rows, cols)
    renderer = PatternRenderer(config)
    return renderer.render_to_pdf(grid, filename, "Greek Key Pattern")


def generate_circuit_pdf(filename: str = "circuit.pdf",
                         rows: int = 8, cols: int = 8,
                         cell_size: float = 40,
                         trace_color: Color = Color(0.2, 0.6, 0.2),  # PCB green
                         background_color: Color = Color(0.1, 0.3, 0.1)) -> str:
    """Quick function to generate a circuit-style pattern PDF."""
    config = PatternConfig(
        cell_size=cell_size,
        grid_rows=rows,
        grid_cols=cols,
        line_width=1.0,
        stroke_color=trace_color,
        fill_color=background_color,
        background_color=background_color,
        page_size=letter
    )
    
    # Create a more interesting circuit pattern
    pattern = [
        ["corner", "straight_h", "t_junction", "straight_h", "corner", "straight_h", "cross", "corner"],
        ["straight_v", "cross", "straight_v", "corner", "straight_h", "t_junction", "straight_v", "straight_v"],
        ["t_junction", "straight_v", "corner", "straight_h", "cross", "straight_v", "corner", "t_junction"],
        ["straight_v", "corner", "straight_h", "t_junction", "straight_v", "corner", "straight_h", "straight_v"],
    ]
    
    grid = circuit_grid(rows, cols, pattern)
    renderer = PatternRenderer(config)
    return renderer.render_to_pdf(grid, filename, "Circuit Pattern")


# =============================================================================
# MAIN - DEMONSTRATION
# =============================================================================

if __name__ == "__main__":
    print("Pattern Generator - Creating sample PDFs...")
    
    # Generate Greek Key pattern (like the uploaded image)
    greek_file = generate_greek_key_pdf(
        filename="/home/claude/greek_key_pattern.pdf",
        rows=5,
        cols=4,
        cell_size=100,
        line_width=5.0
    )
    print(f"Created: {greek_file}")
    
    # Generate Circuit pattern
    circuit_file = generate_circuit_pdf(
        filename="/home/claude/circuit_pattern.pdf",
        rows=10,
        cols=10,
        cell_size=50
    )
    print(f"Created: {circuit_file}")
    
    # Custom pattern example - alternating spirals
    print("\nCreating custom spiral pattern...")
    config = PatternConfig(
        cell_size=60,
        grid_rows=6,
        grid_cols=6,
        line_width=3.0,
        stroke_color=Color(0.2, 0.2, 0.5),
        fill_color=Color(0.95, 0.95, 1.0)
    )
    
    def spiral_cell(row, col):
        return create_square_spiral_cell(turns=2)
    
    grid = custom_grid(6, 6, spiral_cell)
    renderer = PatternRenderer(config)
    spiral_file = renderer.render_to_pdf(grid, "/home/claude/spiral_pattern.pdf", "Spiral Pattern")
    print(f"Created: {spiral_file}")
    
    print("\nAll patterns generated successfully!")
