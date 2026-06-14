"""SVG rendering helpers shared by the canvas and library thumbnail.

Wraps the optional svglib -> reportlab -> PIL pipeline. All entry points return
``None`` when the libraries are missing or rendering fails, so callers can show a
graceful "preview unavailable" placeholder instead of crashing.
"""
from __future__ import annotations

from io import BytesIO
from typing import Dict, Optional, Tuple

from loguru import logger

try:
    from PIL import Image, ImageTk
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPM
    PIL_AVAILABLE = True
except ImportError as e:  # pragma: no cover - environment dependent
    PIL_AVAILABLE = False
    logger.warning(f"SVG rendering libraries unavailable: {e}")


def geometry_to_svg(exporter, geometry: str, metadata: Optional[Dict] = None) -> Optional[str]:
    """Build an SVG string for NEC2 ``geometry`` in memory (no disk write).

    Reuses ``VectorExporter`` internals so the on-screen drawing matches exports.
    """
    try:
        segments = exporter._parse_geometry(geometry)
        return exporter._generate_svg_content(segments, metadata)
    except Exception:
        logger.exception("geometry_to_svg failed")
        return None


def render_svg_to_photoimage(svg_string: str, zoom: float = 1.0,
                             max_size: Tuple[int, int] = (1600, 1100)):
    """Rasterize ``svg_string`` to an ``ImageTk.PhotoImage`` at ``zoom``.

    Renders at 2x base resolution for crisp zoom, then scales to ``zoom`` and
    clamps to ``max_size``. Returns ``None`` if unavailable/failed.
    """
    if not PIL_AVAILABLE:
        return None
    try:
        svg_bytes = svg_string.encode("utf-8")
        drawing = svg2rlg(BytesIO(svg_bytes))
        if drawing is None:
            return None

        base_scale = 2.0
        png_buffer = BytesIO()
        renderPM.drawToFile(drawing, png_buffer, fmt="PNG", dpi=144)
        png_buffer.seek(0)
        img = Image.open(png_buffer)

        w, h = img.size
        zw = max(1, int(w * zoom / base_scale))
        zh = max(1, int(h * zoom / base_scale))

        max_w, max_h = max_size
        if zw > max_w:
            zh = int(zh * max_w / zw)
            zw = max_w
        if zh > max_h:
            zw = int(zw * max_h / zh)
            zh = max_h
        zw, zh = max(zw, 60), max(zh, 40)

        img = img.resize((zw, zh), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception:
        logger.exception("render_svg_to_photoimage failed")
        return None
