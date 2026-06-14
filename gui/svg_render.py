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
                             fit_size: Optional[Tuple[int, int]] = None,
                             max_size: Tuple[int, int] = (2600, 1800)):
    """Rasterize ``svg_string`` to an ``ImageTk.PhotoImage``, fitting or zooming.

    Renders the base raster at high DPI for crisp upscaling. When ``fit_size`` is
    given, derives a zoom that fits the design into that viewport; otherwise uses
    the passed ``zoom``. Result is clamped to ``max_size`` (aspect preserved).

    Returns a 3-tuple ``(photo_or_None, applied_zoom, size_or_None)`` where size
    is ``(width_px, height_px)`` of the produced image. On failure / no PIL it
    returns ``(None, zoom, None)``.
    """
    if not PIL_AVAILABLE:
        return (None, zoom, None)
    try:
        svg_bytes = svg_string.encode("utf-8")
        drawing = svg2rlg(BytesIO(svg_bytes))
        if drawing is None:
            return (None, zoom, None)

        base_scale = 3.0  # 216 / 72
        png_buffer = BytesIO()
        renderPM.drawToFile(drawing, png_buffer, fmt="PNG", dpi=216)
        png_buffer.seek(0)
        img = Image.open(png_buffer)

        w, h = img.size
        nat_w = w / base_scale
        nat_h = h / base_scale

        # Fit-to-viewport derives the zoom; otherwise honour the passed zoom.
        if fit_size is not None and nat_w > 0 and nat_h > 0:
            fw, fh = fit_size
            if fw > 2 and fh > 2:
                zoom = min(fw / nat_w, fh / nat_h)
                zoom = max(0.05, min(16.0, zoom))

        zw = max(1, int(nat_w * zoom))
        zh = max(1, int(nat_h * zoom))

        max_w, max_h = max_size
        if zw > max_w:
            zh = int(zh * max_w / zw)
            zw = max_w
        if zh > max_h:
            zw = int(zw * max_h / zh)
            zh = max_h
        zw, zh = max(zw, 40), max(zh, 30)

        img = img.resize((zw, zh), Image.Resampling.LANCZOS)
        return (ImageTk.PhotoImage(img), zoom, (zw, zh))
    except Exception:
        logger.exception("render_svg_to_photoimage failed")
        return (None, zoom, None)
