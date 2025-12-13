"""
Band Analysis Chart Module

Creates comprehensive charts showing all frequency bands with their mathematically
calculated antenna lengths, including theoretical electrical lengths vs actual
meandered trace lengths within substrate constraints.
"""

import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Optional, Any
import math
from loguru import logger

from presets import BandPresets, FrequencyBand
from design import AdvancedMeanderTrace


class BandAnalysisChart:
    """Creates charts comparing antenna lengths for all frequency bands using meandering."""

    def __init__(self, substrate_width: float = 4.0, substrate_height: float = 2.0):
        """Initialize with substrate dimensions."""
        self.substrate_width = substrate_width
        self.substrate_height = substrate_height
        self.advanced_meander = AdvancedMeanderTrace(substrate_width, substrate_height)

        # Color scheme for bands
        self.colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                      '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']

        logger.info(f"BandAnalysisChart initialized for {substrate_width}x{substrate_height} inch substrate")

    def calculate_band_lengths(self, frequency_band: FrequencyBand) -> Dict[str, Any]:
        """Calculate antenna lengths for a frequency band using meandering algorithms.

        Args:
            frequency_band: FrequencyBand from presets

        Returns:
            dict: Length calculations including theoretical and meandered lengths
        """
        try:
            f1, f2, f3 = frequency_band.frequencies
            frequencies_mhz = [f for f in [f1, f2, f3] if f > 0]

            logger.info(f"Calculating lengths for {frequency_band.name}: {frequencies_mhz} MHz")

            # Calculate theoretical electrical lengths (quarter-wave, half-wave, full-wave)
            electrical_lengths_quarter = []  # λ/4
            electrical_lengths_half = []     # λ/2
            electrical_lengths_full = []     # λ

            c = 299792458  # Speed of light in m/s
            inches_to_m = 0.0254

            for freq_mhz in frequencies_mhz:
                freq_hz = freq_mhz * 1e6
                wavelength_m = c / freq_hz

                # Calculate electrical lengths in inches
                lambda_quarter = (wavelength_m / 4) / inches_to_m       # λ/4 (inches)
                lambda_half = (wavelength_m / 2) / inches_to_m          # λ/2 (inches)
                lambda_full = wavelength_m / inches_to_m                # λ (inches)

                electrical_lengths_quarter.append(lambda_quarter)
                electrical_lengths_half.append(lambda_half)
                electrical_lengths_full.append(lambda_full)

            # Calculate actual meandered trace lengths using AdvancedMeanderTrace
            # This uses the same algorithms as the design generator
            trace_lengths = []
            meandering_ratios = []
            substrate_utilizations = []

            # Use multi-band meander generation for accurate length calculation
            constraints = {
                'substrate_epsilon': 4.3,
                'substrate_thickness': 0.0016,
                'coupling_factor': 0.90,
                'trace_width': 0.001,
            }

            multi_result = self.advanced_meander.generate_multi_band_meanders(frequencies_mhz, constraints)

            if multi_result.get('combined_geometry'):
                # Extract actual trace length from generated geometry
                geometry = multi_result['combined_geometry']
                total_trace_length = self._calculate_geometry_trace_length(geometry)

                # For multi-band designs, distribute the total length across frequencies
                avg_trace_length = total_trace_length / len(frequencies_mhz)
                trace_lengths = [avg_trace_length] * len(frequencies_mhz)

                # Calculate meandering ratio for each frequency
                for i, freq_mhz in enumerate(frequencies_mhz):
                    # Target electrical length (half-wave dipole equivalent)
                    target_electrical = electrical_lengths_half[i]
                    actual_trace = trace_lengths[i]
                    ratio = actual_trace / target_electrical if target_electrical > 0 else 1.0
                    meandering_ratios.append(ratio)

                    # Substrate utilization estimate
                    substrate_area = self.substrate_width * self.substrate_height
                    utilization = (actual_trace * 0.002) / substrate_area * 100  # Rough estimate
                    substrate_utilizations.append(min(100, utilization))

            else:
                # Fallback: Estimate trace lengths individually
                logger.warning("Multi-band geometry generation failed, using individual estimates")
                for i, freq_mhz in enumerate(frequencies_mhz):
                    # Estimate trace length using the same algorithm as advanced meander
                    target_length = self.advanced_meander.extract_target_length(freq_mhz)
                    trace_lengths.append(target_length)

                    # Meandering ratio (actual should be higher than electrical)
                    electrical_half = electrical_lengths_half[i]
                    meandering_ratio = target_length / electrical_half if electrical_half > 0 else 1.0
                    meandering_ratios.append(meandering_ratio)

                    # Estimate substrate utilization
                    substrate_area = self.substrate_width * self.substrate_height
                    utilization = (target_length * 0.002) / substrate_area * 100
                    substrate_utilizations.append(min(100, utilization))

            # Calculate central frequency for sorting
            center_freq = sum(frequencies_mhz) / len(frequencies_mhz)

            return {
                'band_name': frequency_band.name,
                'band_type': frequency_band.band_type.value,
                'frequencies_mhz': frequencies_mhz,
                'center_frequency_mhz': center_freq,
                'electrical_lengths_quarter': electrical_lengths_quarter,  # λ/4 (inches)
                'electrical_lengths_half': electrical_lengths_half,       # λ/2 (inches)
                'electrical_lengths_full': electrical_lengths_full,       # λ (inches)
                'trace_lengths_inches': trace_lengths,                    # Actual meandered lengths
                'meandering_ratios': meandering_ratios,                   # trace_length / electrical_length
                'substrate_utilizations': substrate_utilizations,         # % of substrate used
                'band_count': len(frequencies_mhz)
            }

        except Exception as e:
            logger.error(f"Error calculating lengths for {frequency_band.name}: {str(e)}")
            return None

    def _calculate_geometry_trace_length(self, geometry: str) -> float:
        """Calculate total trace length from NEC2 geometry string.

        Args:
            geometry: NEC2 geometry string

        Returns:
            float: Total trace length in inches
        """
        try:
            total_length = 0.0
            lines = geometry.split('\n')

            for line in lines:
                line = line.strip()
                if line.startswith('GW') and len(line.split()) >= 8:
                    parts = line.split()
                    try:
                        x1, y1 = float(parts[3]), float(parts[4])
                        x2, y2 = float(parts[6]), float(parts[7])
                        segment_length = math.sqrt((x2-x1)**2 + (y2-y1)**2)
                        total_length += segment_length
                    except (ValueError, IndexError):
                        continue

            return total_length
        except Exception as e:
            logger.error(f"Error calculating geometry length: {str(e)}")
            return 0.0

    def create_custom_comparison_chart(self, custom_bands: Dict[str, FrequencyBand], save_path: str = "band_analysis_custom.png",
                                     figsize: tuple = (16, 10)) -> str:
        """Create chart comparing only custom frequency bands (not all presets).

        Args:
            custom_bands: Dict of band_name -> FrequencyBand for custom bands
            save_path: Path to save the chart image
            figsize: Figure size (width, height) in inches

        Returns:
            str: Path to saved chart file
        """
        try:
            band_data = []

            # Calculate lengths for each custom band
            for band_name, frequency_band in custom_bands.items():
                band_result = self.calculate_band_lengths(frequency_band)
                if band_result:
                    band_data.append(band_result)

            if not band_data:
                logger.error("No custom band data calculated")
                return ""

            # Sort by center frequency for better visualization
            band_data.sort(key=lambda x: x['center_frequency_mhz'])

            return self._generate_comparison_chart_content(band_data, save_path, figsize, "Custom Band Analysis")

        except Exception as e:
            logger.error(f"Error creating custom comparison chart: {str(e)}")
            return ""

    def _generate_comparison_chart_content(self, band_data: List[Dict], save_path: str,
                                         figsize: tuple, title: str) -> str:
        """Generate the actual comparison chart content (shared by regular and custom charts).

        Args:
            band_data: List of band data dictionaries
            save_path: Path to save the chart image
            figsize: Figure size (width, height) in inches
            title: Chart title

        Returns:
            str: Path to saved chart file
        """
        try:
            # Create figure with subplots
            fig, axes = plt.subplots(2, 2, figsize=figsize)
            fig.suptitle(f'{title} - {self.substrate_width}"×{self.substrate_height}" Substrate',
                        fontsize=16, fontweight='bold')

            # Color mapping for different band types
            band_types = list(set(bd['band_type'] for bd in band_data))
            type_colors = {bt: self.colors[i % len(self.colors)] for i, bt in enumerate(band_types)}

            # Extract data for plotting
            # Use frequency labels instead of band names
            band_labels = []
            for bd in band_data:
                freqs = bd['frequencies_mhz']
                if len(freqs) == 3:
                    band_labels.append(f"{freqs[0]}/{freqs[1]}/{freqs[2]} MHz")
                else:
                    band_labels.append(f"{freqs[0]} MHz" if freqs else "Unknown")

            center_freqs = [bd['center_frequency_mhz'] for bd in band_data]

            # Convert trace lengths from inches to mm for display (multiply by 25.4)
            max_trace_lengths_mm = [max(bd['trace_lengths_inches']) * 25.4 if bd['trace_lengths_inches'] else 0
                                  for bd in band_data]

            avg_meandering_ratios = [np.mean(bd['meandering_ratios']) if bd['meandering_ratios'] else 1.0
                                   for bd in band_data]
            band_colors = [type_colors[bd['band_type']] for bd in band_data]

            # Subplot 1: Frequency vs Trace Length (in mm)
            ax1 = axes[0, 0]
            bars1 = ax1.bar(range(len(band_labels)), max_trace_lengths_mm, color=band_colors, alpha=0.7)
            ax1.set_xlabel('Frequency (MHz)')
            ax1.set_ylabel('Maximum Trace Length (mm)')
            ax1.set_title('Actual Trace Length by Frequency')
            ax1.set_xticks(range(len(band_labels)))
            ax1.set_xticklabels(band_labels, rotation=45, ha='right')

            # Add value labels on bars (in mm)
            for bar, length_mm in zip(bars1, max_trace_lengths_mm):
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height + 2,
                        f'{length_mm:.0f}mm', ha='center', va='bottom', fontsize=8)

            # Subplot 2: Meandering Ratio Comparison
            ax2 = axes[0, 1]
            bars2 = ax2.bar(range(len(band_labels)), avg_meandering_ratios, color=band_colors, alpha=0.7)
            ax2.set_xlabel('Frequency (MHz)')
            ax2.set_ylabel('Meandering Ratio')
            ax2.set_title('Trace Length / Electrical Length Ratio')
            ax2.set_xticks(range(len(band_labels)))
            ax2.set_xticklabels(band_labels, rotation=45, ha='right')

            # Add reference line at ratio = 1.0
            ax2.axhline(y=1.0, color='red', linestyle='--', alpha=0.5, label='No Meandering')
            ax2.legend()

            # Add value labels
            for bar, ratio in zip(bars2, avg_meandering_ratios):
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2., height + 0.02,
                        f'{ratio:.1f}x', ha='center', va='bottom', fontsize=8)

            # Subplot 3: Theoretical vs Actual Lengths for key bands (in mm)
            ax3 = axes[1, 0]

            # Select all bands for detailed comparison (typically 3 frequencies)
            key_bands = band_data

            freq_labels = []
            theoretical_half_wave_mm = []  # Convert to mm
            actual_trace_lengths_mm = []   # Convert to mm

            for i, bd in enumerate(key_bands):
                if bd['electrical_lengths_half'] and bd['trace_lengths_inches']:
                    # Use maximum electrical half-wave length (convert to mm)
                    max_theoretical_mm = max(bd['electrical_lengths_half']) * 25.4
                    # Use maximum actual trace length (convert to mm)
                    max_actual_mm = max(bd['trace_lengths_inches']) * 25.4

                    freq_labels.append(band_labels[i])
                    theoretical_half_wave_mm.append(max_theoretical_mm)
                    actual_trace_lengths_mm.append(max_actual_mm)

            if freq_labels:
                x = np.arange(len(freq_labels))
                width = 0.35

                bars3a = ax3.bar(x - width/2, theoretical_half_wave_mm, width,
                               label='Theoretical λ/2', color='#ff7f0e', alpha=0.7)
                bars3b = ax3.bar(x + width/2, actual_trace_lengths_mm, width,
                               label='Actual Trace Length', color='#1f77b4', alpha=0.7)

                ax3.set_xlabel('Frequency (MHz)')
                ax3.set_ylabel('Length (mm)')
                ax3.set_title('Theoretical vs Actual Antenna Lengths')
                ax3.set_xticks(x)
                ax3.set_xticklabels(freq_labels, rotation=45, ha='right')
                ax3.legend()

                # Add value annotations (in mm)
                for bar, value in zip(bars3a, theoretical_half_wave_mm):
                    height = bar.get_height()
                    ax3.text(bar.get_x() + bar.get_width()/2., height + 10,
                            f'{value:.0f}mm', ha='center', va='bottom', fontsize=7, rotation=90)

                for bar, value in zip(bars3b, actual_trace_lengths_mm):
                    height = bar.get_height()
                    ax3.text(bar.get_x() + bar.get_width()/2., height + 10,
                            f'{value:.0f}mm', ha='center', va='bottom', fontsize=7, rotation=90)

            # Subplot 4: Frequency vs Length Trend (in mm)
            ax4 = axes[1, 1]

            # Plot trend of frequency vs maximum trace length
            freq_mhz = [bd['center_frequency_mhz'] for bd in band_data]
            trace_lengths_mm = [max(bd['trace_lengths_inches']) * 25.4 if bd['trace_lengths_inches'] else 0
                              for bd in band_data]

            # Sort by frequency
            freq_sorted = sorted(zip(freq_mhz, trace_lengths_mm))

            ax4.scatter([x[0] for x in freq_sorted], [x[1] for x in freq_sorted],
                       s=50, c=band_colors[:len(freq_sorted)], alpha=0.7)

            # Add trend line
            if len(freq_sorted) > 2:
                x_trend = [x[0] for x in freq_sorted]
                y_trend = [x[1] for x in freq_sorted]
                try:
                    coeffs = np.polyfit(x_trend, y_trend, 1)
                    poly = np.poly1d(coeffs)
                    x_line = np.linspace(min(x_trend), max(x_trend), 100)
                    ax4.plot(x_line, poly(x_line), 'r--', alpha=0.5, label='Trend')
                except np.RankWarning:
                    pass  # Skip trend line if data is too sparse

            ax4.set_xlabel('Center Frequency (MHz)')
            ax4.set_ylabel('Maximum Trace Length (mm)')
            ax4.set_title('Frequency vs Required Trace Length')
            ax4.set_xscale('log')
            ax4.grid(True, alpha=0.3)

            # Add frequency annotations
            for i, (freq, length_mm) in enumerate(zip(freq_mhz, trace_lengths_mm)):
                if i < len(band_data):
                    bd = band_data[i]
                    freqs = bd['frequencies_mhz']
                    label = f"{freqs[0]}" if len(freqs) == 1 else f"{freqs[0]}/{freqs[1]}/{freqs[2]}"
                    ax4.annotate(label, (freq, length_mm),
                               xytext=(5, 5), textcoords='offset points', fontsize=8)

            # Create legend for band types
            legend_elements = []
            for band_type, color in type_colors.items():
                from matplotlib.patches import Patch
                legend_elements.append(Patch(facecolor=color, alpha=0.7, label=band_type.replace('_', ' ').title()))

            # Add legend at the bottom
            fig.legend(handles=legend_elements, loc='lower center', ncol=3, bbox_to_anchor=(0.5, -0.05))

            # Add summary text with mm units
            total_bands = len(band_data)
            avg_ratio = np.mean([r for bd in band_data for r in bd['meandering_ratios'] if r > 0])
            substrate_area = self.substrate_width * self.substrate_height

            summary_text = f"""
Custom Band Analysis Summary:
• Total bands analyzed: {total_bands}
• Substrate size: {self.substrate_width}" × {self.substrate_height}" ({substrate_area:.1f}"² area)
• Average meandering ratio: {avg_ratio:.1f}x
• Trace lengths shown in mm for manufacturing precision.
"""

            # Add summary as text box
            fig.text(0.02, 0.02, summary_text, fontsize=8, verticalalignment='bottom',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

            plt.tight_layout()
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()

            logger.info(f"Chart saved to {save_path}")
            return save_path

        except Exception as e:
            logger.error(f"Error generating comparison chart content: {str(e)}")
            return ""

    def create_comparison_chart(self, save_path: str = "band_analysis_chart.png",
                               figsize: tuple = (16, 10)) -> str:
        """Create comprehensive chart comparing all frequency bands.

        Args:
            save_path: Path to save the chart image
            figsize: Figure size (width, height) in inches

        Returns:
            str: Path to saved chart file
        """
        try:
            # Get all frequency bands
            all_bands = BandPresets.get_all_bands()
            band_data = []

            # Calculate lengths for each band
            for band_key, frequency_band in all_bands.items():
                band_result = self.calculate_band_lengths(frequency_band)
                if band_result:
                    band_data.append(band_result)

            if not band_data:
                logger.error("No band data calculated")
                return ""

            # Sort by center frequency for better visualization
            band_data.sort(key=lambda x: x['center_frequency_mhz'])

            return self._generate_comparison_chart_content(band_data, save_path, figsize, "Band Analysis")

        except Exception as e:
            logger.error(f"Error creating comparison chart: {str(e)}")
            return ""

    def create_detailed_band_chart(self, band_name: str = None, save_path: str = "detailed_band_chart.png",
                                  figsize: tuple = (14, 8)) -> str:
        """Create detailed chart for a specific band showing all length relationships.

        Args:
            band_name: Name of specific band to chart (if None, shows all)
            save_path: Path to save the chart
            figsize: Figure size

        Returns:
            str: Path to saved chart file
        """
        try:
            all_bands = BandPresets.get_all_bands()

            if band_name:
                if band_name not in all_bands:
                    logger.error(f"Band '{band_name}' not found")
                    return ""
                bands_to_chart = [all_bands[band_name]]
            else:
                bands_to_chart = list(all_bands.values())[:3]  # First 3 bands

            fig, axes = plt.subplots(len(bands_to_chart), 1, figsize=figsize)
            if len(bands_to_chart) == 1:
                axes = [axes]

            for i, frequency_band in enumerate(bands_to_chart):
                ax = axes[i]

                # Get band data
                band_result = self.calculate_band_lengths(frequency_band)
                if not band_result:
                    continue

                freqs = band_result['frequencies_mhz']
                quarter_wave = band_result['electrical_lengths_quarter']
                half_wave = band_result['electrical_lengths_half']
                full_wave = band_result['electrical_lengths_full']
                trace_lengths = band_result['trace_lengths_inches']

                x = np.arange(len(freqs))
                width = 0.2

                # Plot theoretical lengths
                ax.bar(x - 1.5*width, quarter_wave, width, label='λ/4 (Quarter-wave)', alpha=0.7, color='#1f77b4')
                ax.bar(x - 0.5*width, half_wave, width, label='λ/2 (Half-wave)', alpha=0.7, color='#ff7f0e')
                ax.bar(x + 0.5*width, full_wave, width, label='λ (Full-wave)', alpha=0.7, color='#2ca02c')

                # Plot actual trace lengths
                ax.bar(x + 1.5*width, trace_lengths, width, label='Actual Trace Length', alpha=0.7, color='#d62728')

                ax.set_xlabel('Frequency (MHz)')
                ax.set_ylabel('Length (inches)')
                ax.set_title(f'{frequency_band.name}: Theoretical vs Actual Antenna Lengths')
                ax.set_xticks(x)
                ax.set_xticklabels([f'{f:.0f}' for f in freqs])

                if i == 0:  # Only add legend to first subplot
                    ax.legend()

                # Add substrate boundary line
                substrate_diagonal = math.sqrt(self.substrate_width**2 + self.substrate_height**2)
                ax.axhline(y=substrate_diagonal, color='red', linestyle=':', alpha=0.5,
                          label=f'Substrate diagonal ({substrate_diagonal:.1f}")')

            plt.tight_layout()
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.close()

            logger.info(f"Detailed band chart saved to {save_path}")
            return save_path

        except Exception as e:
            logger.error(f"Error creating detailed band chart: {str(e)}")
            return ""


def create_band_analysis_chart(save_path: str = "band_analysis.png",
                              substrate_width: float = 4.0,
                              substrate_height: float = 2.0) -> str:
    """Convenience function to create the main band analysis chart.

    Args:
        save_path: Path to save the chart
        substrate_width: Substrate width in inches
        substrate_height: Substrate height in inches

    Returns:
        str: Path to saved chart file
    """
    try:
        chart = BandAnalysisChart(substrate_width, substrate_height)
        return chart.create_comparison_chart(save_path)
    except Exception as e:
        logger.error(f"Error in convenience function: {str(e)}")
        return ""


# For direct testing
if __name__ == "__main__":
    import sys

    # Create chart for default substrate
    chart_path = create_band_analysis_chart()
    if chart_path:
        print(f"Band analysis chart created: {chart_path}")
    else:
        print("Failed to create chart")
