# Antenna Meander Export Guide

## Overview

Your Mini Antenna Designer successfully generates **meandered antennas** (worm-like patterns) that fit long antenna designs onto your 2"×4" copper substrate. The system automatically exports these designs as vector files ready for laser etching.

## What is Meandering?

Meandering is a technique that folds a long antenna trace into a compact, worm-like pattern using:
- **Horizontal runs** across the substrate
- **U-turns** to reverse direction
- **Optimized spacing** to maintain electrical performance

This allows you to fit antennas that would normally require 32+ inches onto a 4-inch substrate!

## How It Works

### 1. Automatic Meander Generation

The system automatically applies meandering when:
- Antenna length exceeds available substrate width
- Frequencies are closely spaced (ratio < 1.8)
- Design type is `advanced_meander_tri_band`, `advanced_meander_dual`, or `advanced_meander_compound`

**Example from logs:**
```
Using meandering for 174 MHz dipole (length: 32.220 > 3.200)
Generated meandered dipole: 206 segments, total length ~32.220 inches
```

### 2. Using the GUI

#### Steps to Generate and Export:

1. **Launch the application:**
   ```bash
   python main.py
   ```

2. **Select a frequency band:**
   - Choose from predefined bands (WiFi, TV, etc.)
   - Or enter custom frequencies

3. **Generate the design:**
   - Click "Generate Design"
   - System automatically applies meandering if needed
   - Check the Results tab for performance metrics

4. **Export vector files:**
   - Go to the "Export" tab
   - Choose your format:
     - **SVG** - Best for laser cutters, Inkscape, Adobe Illustrator
     - **DXF** - Best for AutoCAD, CAM software
     - **PDF** - Best for viewing, documentation

5. **Find your files:**
   - Located in the `exports/` directory
   - Files include professional annotations and dimensions

### 3. Using the Test Script

For command-line export:

```bash
python test_export_meander.py
```

This will:
- Generate a WiFi 2.4GHz meandered antenna
- Export to all three formats (SVG, DXF, PDF)
- Verify file creation
- Display success messages

## Export File Specifications

### SVG Files
- **Scale:** 1:1 (ready for production)
- **Dimensions:** Labeled in inches and mils
- **Features:**
  - Professional title and frequency labels
  - Grid lines for alignment (0.5" spacing)
  - Feed point marked in red
  - Manufacturing notes
  - Dimension lines with measurements
  - Black traces on white background

### DXF Files
- **Format:** AutoCAD R2010 compatible
- **Layers:**
  - ETCH (Red): Lines to etch/remove
  - KEEP (Green): Areas to preserve
- **Scale:** In mils (1 inch = 1000 mils)
- **Coordinates:** Absolute positioning

### PDF Files
- **Page size:** Letter (8.5" × 11")
- **Scale:** 72 points per inch
- **Content:**
  - Antenna traces
  - Metadata
  - Dimensions
  - Ready for printing/documentation

## Example Export

### WiFi 2.4GHz Meander Antenna

**Generated files:**
```
exports/
├── wifi_meander_antenna.svg   (6.8 KB)
├── wifi_meander_antenna.dxf   (24 KB)
└── wifi_meander_antenna.pdf   (1.8 KB)
```

**Design specifications:**
- **Frequencies:** 2412, 2437, 2462 MHz
- **Design type:** Advanced meander tri-band
- **Dimensions:** 3.743" × 0.602"
- **Wire segments:** 33
- **Trace width:** 15.7 mil (0.0157 inches)
- **Fits substrate:** ✓ YES (within 4"×2" bounds)

## Laser Etching Tips

### Recommended Settings:
- **Trace width:** 10-20 mil minimum
- **Spacing:** 2× trace width minimum
- **Material:** FR-4 copper-clad PCB
- **Power:** Start low, test on scrap material
- **Feed point:** Solder coax at the marked red circle

### Manufacturing Validation:
The system automatically checks:
- Minimum feature size (5 mil)
- Trace width consistency
- Isolation clearance
- Complexity score (for etching time)

## Troubleshooting

### No geometry exported?
- Make sure you clicked "Generate Design" first
- Check that the design succeeded (not failed)
- Look in the Results tab for geometry preview

### File not found?
- Check the `exports/` directory
- Verify file permissions
- Try running `python test_export_meander.py`

### Antenna too large?
- System automatically applies meandering
- Check validation warnings
- Consider higher frequency (shorter wavelength)

### Export fails?
- Check log file: `antenna_designer.log`
- Verify Python dependencies:
  ```bash
  pip install ezdxf reportlab svglib
  ```

## Advanced Usage

### Custom Meander Parameters

Edit `design.py` to adjust meander constraints:

```python
constraints = {
    'substrate_epsilon': 4.3,      # FR-4 dielectric
    'substrate_thickness': 0.0016, # 1.6mm
    'coupling_factor': 0.88,       # 0.80-0.98
    'bend_radius': 0.0008,         # 0.8mm
    'trace_width': 0.001,          # 1mm
}
```

### Multi-Band Optimization

The system uses different layout strategies:
- **2 bands:** Vertical split
- **3 bands:** Triple vertical
- **4+ bands:** Grid layout

Each band gets optimized trace width based on frequency:
- **High freq (>1 GHz):** 0.4-0.5mm traces
- **Mid freq (100-1000 MHz):** 0.8-1mm traces
- **Low freq (<100 MHz):** 1.2-1.5mm traces

## Files Generated

Recent successful export:
```
Design Type: advanced_meander_tri_band
Frequencies: 2412/2437/2462 MHz
Wire Segments: 33
Quality Score: 45.0
Status: ✓ SUCCESS
```

## Next Steps

1. Open SVG in your laser software (e.g., LightBurn, LaserCut)
2. Set material to copper-clad FR-4
3. Configure power/speed for copper removal
4. Run a test etch on scrap material
5. Etch your antenna design
6. Solder coax to feed point (red circle)
7. Test with antenna analyzer

## Support

For issues or questions:
- Check `antenna_designer.log` for detailed logging
- Review validation warnings in Results tab
- Run `python test_export_meander.py` for diagnostics
- Verify all exports are created successfully

---

**Your meander export system is fully operational and ready to create antennas for laser etching!**
