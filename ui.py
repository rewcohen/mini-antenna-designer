"""Desktop user interface for the Mini Antenna Designer."""
from tkinter import *
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
import threading
import time
from typing import Optional, Dict, Any
import base64
from io import BytesIO
try:
    from PIL import Image, ImageTk
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPM
    PIL_AVAILABLE = True
except ImportError as e:
    PIL_AVAILABLE = False
    logger.warning(f"PIL libraries not available for SVG rendering: {str(e)}")
from loguru import logger

from core import NEC2Interface, NEC2Error, AntennaMetrics
from design import AntennaDesign, AntennaGeometryError
from design_generator import AntennaDesignGenerator
from export import VectorExporter, ExportError
from presets import BandPresets, BandType, FrequencyBand
from storage import DesignStorage, DesignMetadata

class AntennaDesignerGUI:
    """Main GUI application for antenna design."""

    def __init__(self, root):
        """Initialize the GUI."""
        self.root = root
        self.root.title("Mini Antenna Designer - Tri-Band Design")
        self.root.geometry("1200x800")
        self.root.resizable(True, True)

        # Initialize backend components
        self.nec = NEC2Interface()
        self.generator = AntennaDesignGenerator(self.nec)
        self.exporter = VectorExporter()
        self.design_storage = DesignStorage()

        # State variables
        self.current_geometry: Optional[str] = None
        self.current_results: Optional[Dict] = None
        self.selected_band_key: Optional[str] = None
        self.processing_thread: Optional[threading.Thread] = None
        self.current_thumbnail: Optional[ImageTk.PhotoImage] = None

        # Substrate size variables (default to 4x2 inches)
        self.substrate_width_var = StringVar(value="4.0")
        self.substrate_height_var = StringVar(value="2.0")

        # Trace width variables (default to 10 mil, minimum 5 mil)
        self.trace_width_var = DoubleVar(value=10.0)
        self.trace_width_label_var = StringVar(value="10.0 mil - Good")

        # Create GUI components
        self._create_menu()
        self._create_main_layout()

        # Status bar
        self.status_var = StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(root, textvariable=self.status_var, relief=SUNKEN, anchor=W)
        status_bar.pack(side=BOTTOM, fill=X)

        logger.info("GUI initialized")

    def _create_menu(self):
        """Create application menu."""
        menubar = Menu(self.root)

        # File menu
        file_menu = Menu(menubar, tearoff=0)
        file_menu.add_command(label="New Design", command=self._new_design)
        file_menu.add_command(label="Load Geometry", command=self._load_geometry)
        file_menu.add_command(label="Save Geometry", command=self._save_geometry)
        file_menu.add_command(label="Save Design to Library", command=self._save_current_design)
        file_menu.add_separator()
        file_menu.add_command(label="Export SVG", command=lambda: self._export_geometry('svg'))
        file_menu.add_command(label="Export DXF", command=lambda: self._export_geometry('dxf'))
        file_menu.add_command(label="Export PDF", command=lambda: self._export_geometry('pdf'))
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # Tools menu
        tools_menu = Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Validate Geometry", command=self._validate_geometry)
        tools_menu.add_command(label="Analyze Performance", command=self._analyze_performance)
        tools_menu.add_command(label="View Logs", command=self._show_logs)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        # Help menu
        help_menu = Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        help_menu.add_command(label="User Guide", command=self._show_help)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    def _create_main_layout(self):
        """Create the main GUI layout with tabs."""
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=5, pady=5)

        # Design tab
        design_frame = ttk.Frame(notebook)
        notebook.add(design_frame, text='Design')
        self._create_design_tab(design_frame)

        # Results tab
        results_frame = ttk.Frame(notebook)
        notebook.add(results_frame, text='Results')
        self._create_results_tab(results_frame)

        # Export tab
        export_frame = ttk.Frame(notebook)
        notebook.add(export_frame, text='Export')
        self._create_export_tab(export_frame)

        # My Designs tab
        designs_frame = ttk.Frame(notebook)
        notebook.add(designs_frame, text='My Designs')
        self._create_designs_tab(designs_frame)

    def _create_design_tab(self, parent):
        """Create the antenna design tab."""
        # Band selection
        band_frame = ttk.LabelFrame(parent, text="Frequency Band Selection")
        band_frame.pack(fill='x', padx=5, pady=5)

        ttk.Label(band_frame, text="Predefined Bands:").grid(row=0, column=0, sticky='w', padx=5, pady=2)
        self.band_var = StringVar()
        self.band_combo = ttk.Combobox(band_frame, textvariable=self.band_var, state='readonly', width=50)
        self.band_combo.grid(row=0, column=1, padx=5, pady=2)
        self.band_combo.bind('<<ComboboxSelected>>', self._on_band_selected)
        self._populate_band_selection()

        ttk.Button(band_frame, text="Analyze Band", command=self._analyze_selected_band).grid(row=0, column=2, padx=5, pady=2)

        # Custom frequencies
        custom_frame = ttk.LabelFrame(parent, text="Custom Frequencies (MHz)")
        custom_frame.pack(fill='x', padx=5, pady=5)

        ttk.Label(custom_frame, text="Band 1:").grid(row=0, column=0, padx=5, pady=2)
        self.freq1_var = StringVar(value="2400")
        ttk.Entry(custom_frame, textvariable=self.freq1_var, width=10).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(custom_frame, text="Band 2:").grid(row=0, column=2, padx=5, pady=2)
        self.freq2_var = StringVar(value="5500")
        ttk.Entry(custom_frame, textvariable=self.freq2_var, width=10).grid(row=0, column=3, padx=5, pady=2)

        ttk.Label(custom_frame, text="Band 3:").grid(row=0, column=4, padx=5, pady=2)
        self.freq3_var = StringVar(value="5800")
        ttk.Entry(custom_frame, textvariable=self.freq3_var, width=10).grid(row=0, column=5, padx=5, pady=2)

        ttk.Button(custom_frame, text="Use Custom", command=self._use_custom_frequencies).grid(row=0, column=6, padx=5, pady=2)

        # Substrate size controls
        substrate_frame = ttk.LabelFrame(parent, text="Substrate Size (inches)")
        substrate_frame.pack(fill='x', padx=5, pady=5)

        ttk.Label(substrate_frame, text="Width:").grid(row=0, column=0, padx=5, pady=2)
        ttk.Entry(substrate_frame, textvariable=self.substrate_width_var, width=10).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(substrate_frame, text="Height:").grid(row=0, column=2, padx=5, pady=2)
        ttk.Entry(substrate_frame, textvariable=self.substrate_height_var, width=10).grid(row=0, column=3, padx=5, pady=2)

        ttk.Button(substrate_frame, text="Update Substrate", command=self._update_substrate_size).grid(row=0, column=4, padx=5, pady=2)

        # Trace width controls
        trace_frame = ttk.LabelFrame(parent, text="Trace Width (mil)")
        trace_frame.pack(fill='x', padx=5, pady=5)

        ttk.Label(trace_frame, text="Width:").grid(row=0, column=0, padx=5, pady=2)
        self.trace_width_slider = ttk.Scale(trace_frame, from_=5, to=100, orient='horizontal',
                                          variable=self.trace_width_var, command=self._on_trace_width_changed)
        self.trace_width_slider.grid(row=0, column=1, padx=5, pady=2, sticky='ew')

        self.trace_width_entry = ttk.Entry(trace_frame, textvariable=self.trace_width_var, width=8)
        self.trace_width_entry.grid(row=0, column=2, padx=5, pady=2)
        self.trace_width_entry.bind('<FocusOut>', lambda e: self._validate_trace_width())
        self.trace_width_entry.bind('<Return>', lambda e: self._validate_trace_width())

        self.trace_width_status_label = ttk.Label(trace_frame, textvariable=self.trace_width_label_var,
                                                foreground='green')
        self.trace_width_status_label.grid(row=0, column=3, padx=5, pady=2, sticky='w')

        # Configure grid weights for trace frame
        trace_frame.columnconfigure(1, weight=1)

        # Design generation controls
        opt_frame = ttk.LabelFrame(parent, text="Antenna Design Generation")
        opt_frame.pack(fill='x', padx=5, pady=5)

        self.progress_var = DoubleVar()
        self.progress_bar = ttk.Progressbar(opt_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=0, column=0, padx=5, pady=2, sticky='ew')

        self.optimize_button = ttk.Button(opt_frame, text="Generate Design", command=self._generate_design)
        self.optimize_button.grid(row=0, column=1, padx=5, pady=2)

        ttk.Button(opt_frame, text="Stop", command=self._stop_optimization).grid(row=0, column=2, padx=5, pady=2)

        # Messages area
        msg_frame = ttk.LabelFrame(parent, text="Messages")
        msg_frame.pack(fill='both', expand=True, padx=5, pady=5)

        self.message_text = ScrolledText(msg_frame, height=10, wrap=WORD)
        self.message_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Configure grid weights
        opt_frame.columnconfigure(0, weight=1)

    def _create_results_tab(self, parent):
        """Create the results visualization tab."""
        # Results display
        results_frame = ttk.LabelFrame(parent, text="Design Results")
        results_frame.pack(fill='both', expand=True, padx=5, pady=5)

        self.results_text = ScrolledText(results_frame, height=15, wrap=WORD)
        self.results_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Performance metrics
        perf_frame = ttk.LabelFrame(parent, text="Performance Metrics")
        perf_frame.pack(fill='x', padx=5, pady=5)

        # Status indicators
        self.status_indicators = {}
        metrics = ['VSWR Band 1', 'VSWR Band 2', 'VSWR Band 3', 'Fitness Score', 'Status']

        for i, metric in enumerate(metrics):
            ttk.Label(perf_frame, text=f"{metric}:").grid(row=0, column=i*2, padx=5, pady=2, sticky='w')
            indicator = ttk.Label(perf_frame, text="--", background='gray', width=10)
            indicator.grid(row=0, column=i*2+1, padx=5, pady=2)
            self.status_indicators[metric] = indicator

    def _create_export_tab(self, parent):
        """Create the export tab."""
        # Export options
        export_frame = ttk.LabelFrame(parent, text="Export Options")
        export_frame.pack(fill='x', padx=5, pady=5)

        self.export_filename_var = StringVar(value="antenna_design")
        ttk.Label(export_frame, text="Filename:").grid(row=0, column=0, padx=5, pady=2)
        ttk.Entry(export_frame, textvariable=self.export_filename_var).grid(row=0, column=1, padx=5, pady=2, sticky='ew')

        # Export buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill='x', padx=5, pady=5)

        ttk.Button(button_frame, text="Export SVG", command=lambda: self._export_geometry('svg')).pack(side=LEFT, padx=5)
        ttk.Button(button_frame, text="Export DXF", command=lambda: self._export_geometry('dxf')).pack(side=LEFT, padx=5)
        ttk.Button(button_frame, text="Export PDF", command=lambda: self._export_geometry('pdf')).pack(side=LEFT, padx=5)

        # Preview area
        preview_frame = ttk.LabelFrame(parent, text="Design Preview")
        preview_frame.pack(fill='both', expand=True, padx=5, pady=5)

        self.preview_text = ScrolledText(preview_frame, height=20, wrap=WORD, font=('Courier', 9))
        self.preview_text.pack(fill='both', expand=True, padx=5, pady=5)

        export_frame.columnconfigure(1, weight=1)

    def _populate_band_selection(self):
        """Populate the band selection dropdown."""
        try:
            self.band_map = {}  # Map display name to band key
            all_bands = BandPresets.get_all_bands()
            band_names = []

            # Add bands with full descriptions from the all_bands dict
            for band_key, band in all_bands.items():
                display_name = f"{band.name}: {band.frequencies[0]}/{band.frequencies[1]}/{band.frequencies[2]} MHz - {band.description}"
                band_names.append(display_name)
                self.band_map[display_name] = band_key

            self.band_combo['values'] = band_names
            # Set default to WiFi 2.4GHz if available
            default_selection = None
            for name in band_names:
                if "2.4GHz" in name or "WiFi" in name:
                    default_selection = name
                    break
            if default_selection:
                self.band_combo.set(default_selection)
            elif band_names:
                self.band_combo.set(band_names[0])

        except Exception as e:
            self._show_error(f"Error loading band presets: {str(e)}")

    def _on_band_selected(self, event):
        """Handle band selection from dropdown - populate frequency fields."""
        try:
            selected_display = self.band_combo.get()
            if selected_display and selected_display in self.band_map:
                band_key = self.band_map[selected_display]
                bands = BandPresets.get_all_bands()
                if band_key in bands:
                    band = bands[band_key]
                    # Populate the frequency fields
                    self.freq1_var.set(str(band.frequencies[0]))
                    self.freq2_var.set(str(band.frequencies[1]))
                    self.freq3_var.set(str(band.frequencies[2]))
                    # Set selected band key for generation
                    self.selected_band_key = band_key
                    # Clear custom frequencies flag
                    if hasattr(self, 'current_frequencies'):
                        delattr(self, 'current_frequencies')
                    self._log_message(f"Selected band: {band.name} ({band.frequencies[0]}/{band.frequencies[1]}/{band.frequencies[2]} MHz)")
                    self.status_var.set(f"Band selected: {band.name}")
        except Exception as e:
            logger.warning(f"Error handling band selection: {str(e)}")

    def _analyze_selected_band(self):
        """Analyze the selected frequency band."""
        try:
            selection = self.band_combo.get().split(' - ')[0]  # Get just the name
            bands = BandPresets.get_all_bands()

            selected_band = None
            for band in bands.values():
                if band.name == selection:
                    selected_band = band
                    break

            if not selected_band:
                self._show_error("Band not found")
                return

            self.selected_band_key = None
            for key, band in bands.items():
                if band.name == selection:
                    self.selected_band_key = key
                    break

            # Show analysis
            from presets import BandAnalysis
            try:
                analysis = BandAnalysis.analyze_band_compatibility(selected_band)
            except Exception as e:
                logger.error(f"Band analysis failed: {str(e)}")
                # Provide fallback analysis
                analysis = {
                    'feasibility_score': 5,
                    'design_complexity': 'Medium',
                    'size_constraints': 'Within limits',
                    'recommended_antenna_types': ['Dipole', 'Monopole'],
                    'warnings': ['Analysis temporarily unavailable'],
                    'optimization_notes': ['Try generating design directly']
                }

            info_msg = f"""Band Analysis: {selected_band.name}
Description: {selected_band.description}
Frequencies: {selected_band.frequencies[0]}/{selected_band.frequencies[1]}/{selected_band.frequencies[2]} MHz

Feasibility Score: {analysis['feasibility_score']}/10
Design Complexity: {analysis['design_complexity']}
Size Constraints: {analysis['size_constraints']}

Recommended Antennas: {', '.join(analysis['recommended_antenna_types'][:3])}

Warnings:
{chr(10).join('- ' + w for w in analysis['warnings'])}

Notes:
{chr(10).join('- ' + n for n in analysis['optimization_notes'][:3])}
"""
            messagebox.showinfo("Band Analysis", info_msg)

        except Exception as e:
            self._show_error(f"Error analyzing band: {str(e)}")

    def _use_custom_frequencies(self):
        """Use custom frequency values."""
        try:
            f1 = float(self.freq1_var.get())
            f2 = float(self.freq2_var.get())
            f3 = float(self.freq3_var.get())

            custom_band = BandPresets.create_custom_band(
                f"Custom {f1}/{f2}/{f3} MHz",
                f1, f2, f3
            )

            self.current_frequencies = (f1, f2, f3)
            self.selected_band_key = None

            self._log_message(f"Using custom frequencies: {f1}/{f2}/{f3} MHz")
            self.status_var.set("Custom frequencies set")

        except ValueError as e:
            self._show_error("Invalid frequency values. Please enter numeric values.")
        except Exception as e:
            self._show_error(f"Error setting custom frequencies: {str(e)}")

    def _update_substrate_size(self):
        """Update the substrate size for design generation."""
        try:
            width = float(self.substrate_width_var.get())
            height = float(self.substrate_height_var.get())

            # Validate reasonable bounds
            if width < 1.0 or width > 12.0:
                self._show_error("Substrate width must be between 1.0 and 12.0 inches")
                return
            if height < 1.0 or height > 12.0:
                self._show_error("Substrate height must be between 1.0 and 12.0 inches")
                return

            # Update the generator with new substrate dimensions
            self.generator = AntennaDesignGenerator(self.nec, width, height)

            self._log_message(f"Updated substrate size to {width}\" × {height}\"")
            self.status_var.set(f"Substrate: {width}\" × {height}\"")

        except ValueError as e:
            self._show_error("Invalid substrate dimensions. Please enter numeric values.")
        except Exception as e:
            self._show_error(f"Error updating substrate size: {str(e)}")

    def _generate_design(self):
        """Generate antenna design for selected band."""
        try:
            # Get frequency band either from selection or custom frequencies
            selected_band = None

            # First check if a band is selected from dropdown
            selected_display = self.band_combo.get()
            if selected_display and selected_display in getattr(self, 'band_map', {}):
                band_key = self.band_map[selected_display]
                bands = BandPresets.get_all_bands()
                if band_key in bands:
                    selected_band = bands[band_key]

            # If no band selected, try using custom frequencies
            if not selected_band:
                try:
                    f1 = float(self.freq1_var.get())
                    f2 = float(self.freq2_var.get())
                    f3 = float(self.freq3_var.get())
                    selected_band = BandPresets.create_custom_band(
                        f"Custom {f1}/{f2}/{f3} MHz", f1, f2, f3
                    )
                except (ValueError, TypeError):
                    self._show_error("Please select a frequency band from the dropdown or enter valid custom frequencies.")
                    return

            if not selected_band:
                self._show_error("Please select a frequency band or set custom frequencies first.")
                return

            self._log_message(f"Generating design for {selected_band.name}")
            self.optimize_button.config(state='disabled')
            self.progress_var.set(10)
            self.status_var.set("Generating design...")

            # Convert trace width from mil to inches for the design generator
            trace_width_mil = self.trace_width_var.get()
            trace_width_inches = trace_width_mil / 1000.0  # Convert mil to inches

            # Get current substrate dimensions
            substrate_width = float(self.substrate_width_var.get())
            substrate_height = float(self.substrate_height_var.get())

            # Update generator with current substrate dimensions if needed
            self.generator = AntennaDesignGenerator(self.nec, substrate_width, substrate_height)

            # Generate design in background thread
            self.processing_thread = threading.Thread(
                target=self._run_design_generation,
                args=(selected_band, trace_width_inches)
            )
            self.processing_thread.daemon = True
            self.processing_thread.start()

        except Exception as e:
            self._show_error(f"Error starting design generation: {str(e)}")

    def _run_design_generation(self, frequency_band, trace_width_inches):
        """Run design generation in background thread."""
        try:
            # Generate the design
            results = self.generator.generate_design(frequency_band, trace_width_inches)

            # Update UI on completion
            self.root.after(0, self._design_generation_complete, results)

        except Exception as e:
            error_msg = f"Design generation failed: {str(e)}"
            logger.error(error_msg)
            self.root.after(0, self._show_error, error_msg)

    def _design_generation_complete(self, results):
        """Handle design generation completion."""
        try:
            self.current_results = results
            # Fix for missing 'geometry' key
            geometry = results.get('geometry', '') if isinstance(results, dict) else ''
            
            # Set geometry if we have valid geometry content, even if validation has issues
            if geometry and geometry.strip():
                self.current_geometry = geometry
                logger.info(f"Geometry set for export: {len(geometry)} characters")
            else:
                self.current_geometry = ''
                logger.warning("No geometry available after design generation")

            # Update progress and status
            self.progress_var.set(100)
            self.optimize_button.config(state='normal')

            # Always treat as successful unless there's an explicit error
            if not results.get('error'):
                trace_info = f" ({results.get('trace_width_mil', 10):.1f} mil traces)" if results.get('trace_width_mil') is not None else ""
                self.status_var.set("Design generation complete")
                self._log_message(f"Design generated: {results.get('design_type', 'Unknown')} type - {results.get('band_name', 'Unknown')}{trace_info}")
                design_type = results.get('design_type', 'Unknown')
                band_name = results.get('band_name', 'Unknown')
                freqs = f"{results.get('freq1_mhz', 'N/A')}/{results.get('freq2_mhz', 'N/A')}/{results.get('freq3_mhz', 'N/A')} MHz"
                self.status_var.set(f"Generated {design_type} for {band_name} ({freqs}){trace_info}")
            else:
                self.status_var.set("Design generation failed")
                error_msg = results.get('error', 'Unknown error')
                self._log_message(f"Design generation failed: {error_msg}")
                self._show_error(f"Design generation failed: {error_msg}")
                return

            # Display results
            self._display_design_results(results)
            self._update_design_status_indicators(results)
            if self.current_geometry:
                self._show_geometry_preview()

        except Exception as e:
            self._show_error(f"Error processing design results: {str(e)}")

    def _display_design_results(self, results):
        """Display design generation results."""
        try:
            display_text = f"""Tri-Band Antenna Design Results
{'='*50}

Design Type: {results.get('design_type', 'Unknown')}
Band: {results.get('band_name', 'Unknown')}
Frequencies: {results.get('freq1_mhz', 'N/A')}/{results.get('freq2_mhz', 'N/A')}/{results.get('freq3_mhz', 'N/A')} MHz

Validation Results:
- Within Substrate Bounds: {results.get('validation', {}).get('within_bounds', False)}
- Manufacturable: {results.get('validation', {}).get('manufacturable', False)}
- Complexity Score: {results.get('validation', {}).get('complexity_score', 0)}/4
- Estimated Etch Time: {results.get('validation', {}).get('estimated_etch_time', 'Unknown')}

Performance Metrics:
"""

            # Add metrics if available
            metrics = results.get('metrics', {})
            if metrics:
                summary = metrics.get('summary', {})

                display_text += f"""
Average VSWR: {summary.get('avg_vswr', 'N/A')}
Average Gain: {summary.get('avg_gain_dbi', 'N/A')} dBi
Frequency Range: {summary.get('frequency_range_mhz', 'N/A')}
Bandwidth: {summary.get('bandwidth_octaves', 'N/A')} octaves
"""

                # Individual frequency results
                for freq_key in ['freq_1000.0_mhz', 'freq_2400.0_mhz', 'freq_5500.0_mhz',
                                'freq_1575.42_mhz', 'freq_1227.6_mhz', 'freq_1176.45_mhz']:
                    if freq_key in metrics:
                        freq_data = metrics[freq_key]
                        freq_mhz = freq_key.replace('_mhz', '').replace('_', '.')
                        display_text += f"""
{freq_mhz} MHz:
  VSWR: {freq_data.get('vswr', 'N/A')}
  Gain: {freq_data.get('gain_dbi', 'N/A')} dBi
  Impedance: {freq_data.get('impedance', 'N/A')}
"""

            display_text += f"""

Warnings:
{chr(10).join('- ' + w for w in results.get('validation', {}).get('warnings', ['None']))}
"""

            self.results_text.delete(1.0, END)
            self.results_text.insert(END, display_text)

        except Exception as e:
            logger.error(f"Error displaying design results: {str(e)}")

    def _update_design_status_indicators(self, results):
        """Update the performance indicator lights for design results."""
        try:
            # Update status
            status_indicator = self.status_indicators['Status']
            status_indicator.config(text="Complete", background='green')

            # Update fitness score indicator (not applicable for design generator)
            fitness_indicator = self.status_indicators['Fitness Score']
            fitness_indicator.config(text="N/A", background='gray')

            # Get VSWR values from metrics if available
            metrics = results.get('metrics', {})
            vswr_values = []

            # Try to extract VSWR values
            for freq_data in metrics.values():
                if isinstance(freq_data, dict) and 'vswr' in freq_data:
                    try:
                        vswr_val = float(freq_data['vswr'])
                        if 1 <= vswr_val <= 10:  # Reasonable VSWR range
                            vswr_values.append(vswr_val)
                    except (ValueError, TypeError):
                        continue

            # Update VSWR indicators
            for i in range(min(3, len(vswr_values))):
                vswr = vswr_values[i] if i < len(vswr_values) else float('inf')
                indicator = self.status_indicators[f'VSWR Band {i+1}']

                if vswr < 2.0:
                    indicator.config(text=f"{vswr:.1f}", background='green')
                elif vswr < 3.0:
                    indicator.config(text=f"{vswr:.1f}", background='yellow')
                else:
                    indicator.config(text=f"{vswr:.1f}", background='red')

        except Exception as e:
            logger.warning(f"Error updating design status indicators: {str(e)}")

    def _show_geometry_preview(self):
        """Show geometry preview in export tab."""
        try:
            if self.current_geometry:
                self.preview_text.delete(1.0, END)
                self.preview_text.insert(END, self.current_geometry)

        except Exception as e:
            logger.error(f"Error showing geometry preview: {str(e)}")

    def _export_geometry(self, format_type):
        """Export current geometry to specified format."""
        try:
            logger.info(f"Export request received for format: {format_type}")
            
            # Check if we have any geometry at all
            if not self.current_geometry:
                logger.error("No geometry available for export - self.current_geometry is None")
                self._show_error("No valid geometry to export. Please generate design first.")
                return
                
            if not self.current_geometry.strip():
                logger.error("Geometry is empty or whitespace only")
                self._show_error("Generated design appears to be empty. Please try generating a new design.")
                return

            logger.info(f"Geometry available for export: {len(self.current_geometry)} characters")
            
            # Log geometry preview for debugging
            lines = self.current_geometry.split('\n')
            logger.info(f"Geometry has {len(lines)} lines")
            gw_lines = [line for line in lines if line.strip().startswith('GW')]
            sp_lines = [line for line in lines if line.strip().startswith('SP')]
            logger.info(f"Geometry contains {len(gw_lines)} GW lines and {len(sp_lines)} SP lines")
            
            if gw_lines:
                logger.debug(f"First GW line: {gw_lines[0]}")
            if self.current_geometry:
                logger.debug(f"Geometry preview: {self.current_geometry[:200]}...")

            # Additional validation: check if geometry contains meaningful antenna structures
            from export import EtchingValidator
            validation = EtchingValidator.validate_for_etching(self.current_geometry)
            logger.info(f"Etching validation result: {validation}")

            # Check for minimum wire count - antennas should have at least some wires
            wire_count = len(gw_lines)
            if wire_count < 1:
                logger.error(f"Insufficient wire count: {wire_count} wires found")
                logger.error(f"Full geometry content: '{self.current_geometry}'")
                self._show_error("Generated design appears to be empty (no antenna elements). Please try a different frequency band.")
                return

            # Check for very small/truncated elements that wouldn't be usable
            if validation.get('complexity_score', 4) >= 4 or validation.get('etching_ready') == False:
                warning_msg = "Design may have manufacturing issues:\n" + "\n".join(validation.get('warnings', ['High complexity']))
                self._log_message(f"Design validation warnings: {warning_msg}")
                # Continue with export but warn the user

            filename = self.export_filename_var.get()
            if not filename:
                filename = "antenna_design"

            # Export metadata
            metadata = {
                'design_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                'frequencies': str(self.current_results.get('frequencies', [])) if self.current_results else 'Unknown',
                'fitness_score': ".3f" if self.current_results else 'N/A',
                'substrate_width': float(self.substrate_width_var.get()),
                'substrate_height': float(self.substrate_height_var.get())
            }

            output_path = self.exporter.export_geometry(
                self.current_geometry, filename, format_type, metadata
            )

            self._log_message(f"Exported to {output_path}")
            messagebox.showinfo("Export Complete", f"Design exported successfully to:\n{output_path}")

        except ExportError as e:
            self._show_error(f"Export failed: {str(e)}")
        except Exception as e:
            self._show_error(f"Export error: {str(e)}")

    def _log_message(self, message):
        """Add message to the log display."""
        try:
            timestamp = time.strftime('%H:%M:%S')
            self.message_text.insert(END, f"[{timestamp}] {message}\n")
            self.message_text.see(END)
        except Exception as e:
            # Avoid recursive error if logging fails
            pass

    def _show_error(self, message):
        """Display error message to user."""
        logger.error(message)
        self._log_message(f"ERROR: {message}")
        messagebox.showerror("Error", message)

    def _stop_optimization(self):
        """Stop the current optimization process."""
        if self.processing_thread and self.processing_thread.is_alive():
            # Note: In a real implementation, you'd want proper thread cancellation
            self.status_var.set("Stopping optimization...")
            self.optimize_button.config(state='normal')

    def _new_design(self):
        """Clear current design and start fresh."""
        self.current_geometry = None
        self.current_results = None
        self.results_text.delete(1.0, END)
        self.preview_text.delete(1.0, END)
        self.message_text.delete(1.0, END)

        # Reset status indicators
        for indicator in self.status_indicators.values():
            indicator.config(text="--", background='gray')

        self.status_var.set("Ready")

    def _load_geometry(self):
        """Load geometry from file."""
        try:
            filename = filedialog.askopenfilename(
                title="Load Geometry",
                filetypes=[("NEC2 files", "*.nec"), ("All files", "*.*")]
            )
            if filename:
                with open(filename, 'r') as f:
                    self.current_geometry = f.read()
                self._show_geometry_preview()
                self.status_var.set("Geometry loaded")

        except Exception as e:
            self._show_error(f"Error loading geometry: {str(e)}")

    def _save_geometry(self):
        """Save current geometry to file."""
        try:
            if not self.current_geometry:
                self._show_error("No geometry to save.")
                return

            filename = filedialog.asksaveasfilename(
                title="Save Geometry",
                defaultextension=".nec",
                filetypes=[("NEC2 files", "*.nec"), ("All files", "*.*")]
            )
            if filename:
                with open(filename, 'w') as f:
                    f.write(self.current_geometry)
                self.status_var.set("Geometry saved")

        except Exception as e:
            self._show_error(f"Error saving geometry: {str(e)}")

    def _validate_geometry(self):
        """Validate current geometry."""
        try:
            if not self.current_geometry:
                self._show_error("No geometry to validate.")
                return

            # Validate using export validator
            from export import EtchingValidator
            validation = EtchingValidator.validate_for_etching(self.current_geometry)

            if validation['etching_ready']:
                status = "READY"
                bg_color = 'green'
            else:
                status = "ISSUES"
                bg_color = 'red'

            info_msg = f"""Geometry Validation Results
Status: {status}

Features: {validation['minimum_feature_size']} | {validation['trace_width_consistent']} | {validation['isolation_clearance']}
Complexity Score: {validation['complexity_score']}/4
Area Estimate: {validation['total_area']:.3f} in²

Warning: {chr(10).join(validation['warnings']) if validation['warnings'] else 'None'}
"""
            messagebox.showinfo("Validation Results", info_msg)

        except Exception as e:
            self._show_error(f"Validation error: {str(e)}")

    def _analyze_performance(self):
        """Analyze performance of current design."""
        try:
            if not self.current_results or 'performance' not in self.current_results:
                self._show_error("No performance data available.")
                return

            performance = self.current_results['performance']
            from constraints import ElectricalConstraints
            vswr_values = [p.get('vswr', float('inf')) for p in performance.values()]
            analysis = ElectricalConstraints.check_efficiency_requirements(vswr_values)

            info_msg = f"""Performance Analysis

Bands Meeting Spec: {analysis['bands_met']}/3
Estimated Efficiency: {analysis['efficiency_estimate']:.1f}%
Performance Rating: {analysis['average_performance'].upper()}

Band Details:
"""

            for band in analysis['band_ratings']:
                status_icon = "✓" if band['passes'] else "✗"
                info_msg += f"{status_icon} {band['band']}: VSWR={band['vswr']:.2f}, Eff={band['efficiency_percent']:.1f}%\n"

            messagebox.showinfo("Performance Analysis", info_msg)

        except Exception as e:
            self._show_error(f"Performance analysis error: {str(e)}")

    def _show_logs(self):
        """Display the application log file."""
        try:
            from pathlib import Path
            log_file = Path("antenna_designer.log")

            if log_file.exists():
                # Show log in a new window
                log_window = Toplevel(self.root)
                log_window.title("Application Logs")
                log_window.geometry("800x600")

                log_text = ScrolledText(log_window, wrap=WORD, font=('Courier', 9))
                log_text.pack(fill='both', expand=True, padx=5, pady=5)

                with open(log_file, 'r') as f:
                    log_text.insert(END, f.read())

                log_text.see(END)
            else:
                self._show_error("Log file not found.")

        except Exception as e:
            self._show_error(f"Error displaying logs: {str(e)}")

    def _show_about(self):
        """Show about dialog."""
        about_msg = """Mini Antenna Designer v1.0

A NEC2-based tri-band antenna design generator for laser-etched planar antennas.

Features:
- Direct design generation for frequency band selection
- NEC2 electromagnetic analysis of final designs
- Vector export for laser etching (SVG/DXF/PDF)
- 2x4 inch substrate constraints and manufacturing validation
- Real-time performance feedback and etching feasibility

Created for high-resolution antenna prototyping on copper substrates.
"""
        messagebox.showinfo("About", about_msg)

    def _show_help(self):
        """Show user guide."""
        help_msg = """Mini Antenna Designer User Guide

1. Select a frequency band from presets or enter custom frequencies
2. Click "Generate Design" to create the antenna layout using NEC2 theory
3. Review results in the Design Results tab
4. Export design files (SVG/DXF/PDF) ready for laser etching

Tips:
- Designs are automatically validated for your 2x4 inch copper substrate
- VSWR < 3.0 is acceptable for most applications
- Check geometry validation warnings before etching
- Save geometries for future reference
- High-resolution (5 mil minimum) features are generated for manufacturing

Supported Antenna Types:
- Planar Dipoles (close frequencies)
- Dual elements (moderate separation)
- Compound spirals (wide bands with compensation)
"""
        messagebox.showinfo("User Guide", help_msg)

    def _on_trace_width_changed(self, value):
        """Handle trace width slider changes."""
        try:
            width = float(value)
            self._validate_trace_width_display(width)
        except (ValueError, TypeError):
            pass

    def _validate_trace_width(self):
        """Validate trace width entry and slider synchronization."""
        try:
            # Get value from entry
            width = float(self.trace_width_entry.get())

            # Clamp to valid range
            if width < 5.0:
                width = 5.0
                self.trace_width_var.set(width)
            elif width > 100.0:
                width = 100.0
                self.trace_width_var.set(width)

            self._validate_trace_width_display(width)

        except ValueError as e:
            # Reset to current slider value
            self.trace_width_entry.delete(0, END)
            self.trace_width_entry.insert(0, f"{self.trace_width_var.get():.1f}")
            self._validate_trace_width_display(self.trace_width_var.get())

    def _validate_trace_width_display(self, width):
        """Update trace width validation display."""
        try:
            from constraints import ManufacturingRules
            result = ManufacturingRules.check_trace_width(width / 1000.0)  # Convert mil to inches

            # Update label and color based on manufacturability
            status_text = "Invalid"
            color = 'red'

            if result['is_manufacturable']:
                if result['quality_rating'] == 'good':
                    status_text = f"{width:.1f} mil - Good"
                    color = 'green'
                elif result['quality_rating'] == 'acceptable':
                    status_text = f"{width:.1f} mil - Acceptable"
                    color = 'orange'
                else:
                    status_text = f"{width:.1f} mil - Needs Review"
                    color = 'red'
            else:
                status_text = f"{width:.1f} mil - Invalid"
                color = 'red'

            self.trace_width_label_var.set(status_text)
            self.trace_width_status_label.config(foreground=color)

        except Exception as e:
            logger.error(f"Trace width validation error: {str(e)}")
            self.trace_width_label_var.set("Error")
            self.trace_width_status_label.config(foreground='red')

    def _create_designs_tab(self, parent):
        """Create the 'My Designs' tab for managing saved antenna designs."""
        # Use existing design storage from initialization
        # self.design_storage is already created in __init__

        # Top toolbar
        toolbar_frame = ttk.Frame(parent)
        toolbar_frame.pack(fill='x', padx=5, pady=5)

        # Save current design button
        ttk.Button(toolbar_frame, text="Save Current Design",
                  command=self._save_current_design).pack(side=LEFT, padx=2)

        # Refresh button
        ttk.Button(toolbar_frame, text="Refresh List",
                  command=self._refresh_designs_list).pack(side=LEFT, padx=2)

        # Delete button
        ttk.Button(toolbar_frame, text="Delete Selected",
                  command=self._delete_selected_design).pack(side=LEFT, padx=2)

        # Search entry
        search_frame = ttk.Frame(toolbar_frame)
        search_frame.pack(side=RIGHT, padx=2)
        ttk.Label(search_frame, text="Search:").pack(side=LEFT)
        self.design_search_var = StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.design_search_var, width=20)
        search_entry.pack(side=LEFT, padx=2)
        search_entry.bind('<KeyRelease>', lambda e: self._search_designs())

        # Main content area - use simple frames with fallback if paned window fails
        try:
            # Try to use paned window for resizable split
            paned = ttk.PanedWindow(parent, orient='horizontal')
            paned.pack(fill='both', expand=True, padx=5, pady=5)
            logger.info("Successfully created paned window for designs tab")

            # Left panel - designs list
            left_panel = ttk.Frame(paned)
            paned.add(left_panel, weight=2)

            # Right panel - design details
            right_panel = ttk.Frame(paned)
            paned.add(right_panel, weight=3)

        except Exception as e:
            logger.warning(f"Failed to create paned window, using simple layout: {str(e)}")
            # Fallback to simple frame layout without splitter
            main_frame = ttk.Frame(parent)
            main_frame.pack(fill='both', expand=True, padx=5, pady=5)

            # Create panels with fixed sizes
            left_panel = ttk.Frame(main_frame, width=400)
            left_panel.pack(side=LEFT, fill='both', expand=True, padx=(0, 5))

            ttk.Separator(main_frame, orient='vertical').pack(side=LEFT, fill='y')

            right_panel = ttk.Frame(main_frame)
            right_panel.pack(side=RIGHT, fill='both', expand=True)

        # Designs list in left panel
        list_frame = ttk.LabelFrame(left_panel, text="Saved Designs")
        list_frame.pack(fill='both', expand=True)

        # Create treeview for designs
        columns = ('name', 'band', 'frequencies', 'created', 'type')
        self.designs_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        # Configure columns
        self.designs_tree.heading('name', text='Design Name')
        self.designs_tree.heading('band', text='Band')
        self.designs_tree.heading('frequencies', text='Frequencies (MHz)')
        self.designs_tree.heading('created', text='Created')
        self.designs_tree.heading('type', text='Type')

        self.designs_tree.column('name', width=200, minwidth=150)
        self.designs_tree.column('band', width=120, minwidth=100)
        self.designs_tree.column('frequencies', width=120, minwidth=100)
        self.designs_tree.column('created', width=150, minwidth=120)
        self.designs_tree.column('type', width=100, minwidth=80)

        # Scrollbar for treeview
        tree_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.designs_tree.yview)
        self.designs_tree.configure(yscrollcommand=tree_scrollbar.set)

        self.designs_tree.pack(side=LEFT, fill='both', expand=True)
        tree_scrollbar.pack(side=RIGHT, fill='y')

        # Bind selection event
        self.designs_tree.bind('<<TreeviewSelect>>', self._on_design_selected)

        # Design details
        details_frame = ttk.LabelFrame(right_panel, text="Design Details")
        details_frame.pack(fill='x', pady=(0, 5))

        self.details_text = ScrolledText(details_frame, height=8, wrap=WORD, font=('Courier', 9))
        self.details_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Preview area
        preview_frame = ttk.LabelFrame(right_panel, text="Preview")
        preview_frame.pack(fill='both', expand=True)

        # Thumbnail preview (placeholder for SVG)
        self.thumbnail_label = ttk.Label(preview_frame, text="Select a design to view thumbnail", background='lightgray')
        self.thumbnail_label.pack(fill='both', expand=True, padx=5, pady=5)

        # Action buttons
        action_frame = ttk.Frame(preview_frame)
        action_frame.pack(fill='x', pady=(5, 0))

        ttk.Button(action_frame, text="Load Design", command=self._load_selected_design).pack(side=LEFT, padx=2)
        ttk.Button(action_frame, text="Export Design", command=self._export_selected_design).pack(side=LEFT, padx=2)
        ttk.Button(action_frame, text="Edit Notes", command=self._edit_design_notes).pack(side=RIGHT, padx=2)

        # Library stats
        stats_frame = ttk.Frame(parent)
        stats_frame.pack(fill='x', padx=5, pady=(0, 5))

        self.library_stats_var = StringVar()
        stats_label = ttk.Label(stats_frame, textvariable=self.library_stats_var,
                               font=('Arial', 9, 'italic'))
        stats_label.pack(side=RIGHT)

        # Delay initial design loading to ensure UI is fully initialized
        logger.info("GUI creation complete, scheduling design library initialization...")
        # Use after() to delay design loading until mainloop starts
        self.root.after(100, self._delayed_initial_refresh)

    def _save_current_design(self):
        """Save the currently generated design to the library."""
        try:
            if not self.current_geometry:
                self._show_error("No design to save. Generate a design first.")
                return

            if not self.current_results:
                self._show_error("No design results available.")
                return

            # Prompt for design name
            name_dialog = Toplevel(self.root)
            name_dialog.title("Save Design")
            name_dialog.geometry("400x150")
            name_dialog.resizable(False, False)
            name_dialog.transient(self.root)
            name_dialog.grab_set()

            ttk.Label(name_dialog, text="Design Name:").pack(pady=(10, 0))
            name_var = StringVar()
            name_entry = ttk.Entry(name_dialog, textvariable=name_var, width=40)
            name_entry.pack(pady=5, padx=10)

            def save_and_close():
                name = name_var.get().strip()
                if name:
                    try:
                        # Create metadata
                        metadata = DesignMetadata(
                            name=name,
                            substrate_width=float(self.substrate_width_var.get()),
                            substrate_height=float(self.substrate_height_var.get()),
                            trace_width_mil=float(self.trace_width_var.get())
                        )

                        # Save design
                        saved_path = self.design_storage.save_design(
                            self.current_geometry, metadata, self.current_results
                        )

                        self._log_message(f"Design saved: {name}")
                        self.status_var.set(f"Saved design: {name}")
                        self._refresh_designs_list()
                        name_dialog.destroy()

                    except Exception as e:
                        self._show_error(f"Failed to save design: {str(e)}")
                else:
                    messagebox.showerror("Error", "Please enter a design name.")

            ttk.Button(name_dialog, text="Save", command=save_and_close).pack(pady=(0, 10))
            name_entry.focus()

            # Bind Enter key
            name_entry.bind('<Return>', lambda e: save_and_close())
            name_dialog.bind('<Escape>', lambda e: name_dialog.destroy())

        except Exception as e:
            self._show_error(f"Error saving design: {str(e)}")

    def _refresh_designs_list(self):
        """Refresh the designs list from storage."""
        try:
            logger.debug("Starting design list refresh...")

            # Validate UI components exist and are accessible
            if not hasattr(self, 'designs_tree') or self.designs_tree is None:
                logger.error("designs_tree widget not initialized")
                raise Exception("Designs tree widget not available")

            # Test widget accessibility
            try:
                logger.debug(f"Testing designs_tree widget: {self.designs_tree}")
                self.designs_tree.cget('height')  # Test widget access
                logger.debug("Treeview widget is accessible")
            except Exception as widget_e:
                logger.error(f"Treeview widget not accessible: {widget_e}")
                raise Exception(f"Cannot access designs tree widget: {widget_e}")

            # Clear existing items
            try:
                existing_items = self.designs_tree.get_children()
                logger.debug(f"Clearing {len(existing_items)} existing items")
                for item in existing_items:
                    self.designs_tree.delete(item)
                logger.debug("Successfully cleared existing items")
            except Exception as clear_e:
                logger.error(f"Failed to clear existing tree items: {clear_e}")
                raise Exception(f"Cannot clear existing designs: {clear_e}")

            # Load designs
            logger.debug("Loading designs from storage...")
            designs = self.design_storage.list_designs(sort_by='created_date', reverse=True)
            logger.info(f"Storage returned {len(designs)} designs")

            # Add to treeview with individual error handling
            success_count = 0
            failed_count = 0

            for i, design in enumerate(designs):
                try:
                    # Format data
                    frequencies = "/".join([f"{f:g}" for f in design.get('frequencies_mhz', [])])

                    # Prepare values tuple
                    values = (
                        design.get('name', 'Unknown'),
                        design.get('band_name', 'Unknown'),
                        frequencies,
                        design.get('created_date', '')[:19],  # Truncate timestamp
                        design.get('design_type', 'Unknown')
                    )

                    # Insert into tree
                    tags = (design.get('file_path', ''),)
                    logger.debug(f"Inserting design {i+1}: {values[0]}")
                    self.designs_tree.insert('', 'end', values=values, tags=tags)
                    success_count += 1

                except Exception as insert_e:
                    failed_count += 1
                    design_name = design.get('name', f'design_{i+1}')
                    logger.error(f"Failed to insert design '{design_name}' into treeview: {insert_e}")
                    # Continue with next design instead of failing completely

            logger.info(f"Treeview insertion complete: {success_count} successful, {failed_count} failed")

            # Update stats with error handling
            try:
                stats = self.design_storage.get_design_stats()
                stats_text = f"Total designs: {stats.get('total_designs', 0)} | Size: {stats.get('total_size_bytes', 0) / 1024:.1f} KB"
                self.library_stats_var.set(stats_text)
                logger.debug("Stats updated successfully")
            except Exception as stats_e:
                logger.warning(f"Failed to update stats: {stats_e}")
                self.library_stats_var.set(f"Total designs: {len(designs)}")

            status_msg = f"Loaded {success_count} designs"
            if failed_count > 0:
                status_msg += f" ({failed_count} failed)"
            self.status_var.set(status_msg)

            if failed_count > 0:
                logger.warning(f"Design list refresh completed with {failed_count} failures")
                self._show_error(f"Designs list loaded with issues ({failed_count} items failed)")
            else:
                logger.info("Design list refresh completed successfully")

        except Exception as e:
            logger.error(f"Critical failure in design list refresh: {str(e)}")
            # Try to show user-friendly error
            try:
                self._show_error("Failed to load designs list")
            except Exception as ui_e:
                logger.error(f"Could not show error dialog: {ui_e}")

            # Attempt to set fallback status
            try:
                self.status_var.set("Design library unavailable")
            except Exception as status_e:
                logger.error(f"Could not update status: {status_e}")
            raise

    def _render_svg_thumbnail(self, svg_data_uri):
        """Render base64 SVG data to tkinter PhotoImage for display.

        Args:
            svg_data_uri: Base64 encoded SVG data URI (data:image/svg+xml;base64,...)

        Returns:
            ImageTk.PhotoImage or None if rendering failed
        """
        if not PIL_AVAILABLE:
            logger.warning("PIL libraries not available for SVG rendering")
            return None

        try:
            # Extract base64 part from data URI
            if not svg_data_uri.startswith('data:image/svg+xml;base64,'):
                logger.error(f"Invalid SVG data URI format: {svg_data_uri[:50]}...")
                return None

            base64_data = svg_data_uri.split(',', 1)[1]

            # Decode base64 to SVG XML
            svg_bytes = base64.b64decode(base64_data)
            svg_string = svg_bytes.decode('utf-8')

            # Convert SVG to PIL Image using svglib
            svg_buffer = BytesIO(svg_bytes)
            drawing = svg2rlg(svg_buffer)
            png_buffer = BytesIO()
            renderPM.drawToFile(drawing, png_buffer, fmt='PNG')
            png_buffer.seek(0)

            # Load PIL Image and resize if needed
            pil_image = Image.open(png_buffer)

            # Limit thumbnail size
            max_size = (200, 150)  # Max width x height
            pil_image.thumbnail(max_size, Image.LANCZOS)

            # Convert to tkinter PhotoImage
            photo_image = ImageTk.PhotoImage(pil_image)
            return photo_image

        except Exception as e:
            logger.error(f"Failed to render SVG thumbnail: {str(e)}")
            return None

    def _on_design_selected(self, event):
        """Handle design selection in the treeview."""
        try:
            selection = self.designs_tree.selection()
            if not selection:
                return

            item = selection[0]
            values = self.designs_tree.item(item, 'values')
            file_path = self.designs_tree.item(item, 'tags')[0]

            if file_path:
                try:
                    # Load design details
                    metadata, geometry = self.design_storage.load_design(file_path)

                    # Display details
                    details = f"""Design: {metadata.name}
Band: {metadata.band_name}
Frequencies: {metadata.frequencies_mhz[0]}/{metadata.frequencies_mhz[1]}/{metadata.frequencies_mhz[2]} MHz
Substrate: {metadata.substrate_width}" × {metadata.substrate_height}"
Trace Width: {metadata.trace_width_mil} mil
Type: {metadata.design_type}
Created: {metadata.created_date[:19]}

Notes: {metadata.custom_notes}

Performance Metrics:
{self._format_performance_metrics(metadata.performance_metrics)}
"""
                    self.details_text.delete(1.0, END)
                    self.details_text.insert(END, details)

                    # Load thumbnail
                    if metadata.thumbnail_svg and metadata.thumbnail_svg.startswith('data:image'):
                        # Render SVG thumbnail
                        photo_image = self._render_svg_thumbnail(metadata.thumbnail_svg)
                        if photo_image:
                            # Keep reference to prevent garbage collection
                            self.current_thumbnail = photo_image
                            self.thumbnail_label.config(image=photo_image, text="")
                        else:
                            self.thumbnail_label.config(image=None, text="Thumbnail rendering failed")
                    else:
                        self.thumbnail_label.config(image=None, text="No thumbnail available")

                except Exception as e:
                    logger.error(f"Failed to load selected design: {str(e)}")
                    self.details_text.delete(1.0, END)
                    self.details_text.insert(END, "Failed to load design details")

        except Exception as e:
            logger.error(f"Error handling design selection: {str(e)}")

    def _format_performance_metrics(self, metrics):
        """Format performance metrics for display."""
        try:
            if not metrics:
                return "No performance data available"

            formatted = ""
            validation = metrics.get('validation', {})

            if validation:
                formatted += "Validation:\n"
                formatted += f"- Within bounds: {validation.get('within_bounds', False)}\n"
                formatted += f"- Manufacturable: {validation.get('manufacturable', False)}\n"
                formatted += f"- Complexity: {validation.get('complexity_score', 'N/A')}/4\n"

            summary = metrics.get('summary', {})
            if summary:
                formatted += "\nPerformance:\n"
                formatted += f"- Avg VSWR: {summary.get('avg_vswr', 'N/A')}\n"
                formatted += f"- Avg Gain: {summary.get('avg_gain_dbi', 'N/A')} dBi\n"
                formatted += f"- Bandwidth: {summary.get('bandwidth_octaves', 'N/A')} octaves\n"

            return formatted

        except Exception as e:
            return f"Error formatting metrics: {str(e)}"

    def _load_selected_design(self):
        """Load the selected design into the current session."""
        try:
            selection = self.designs_tree.selection()
            if not selection:
                self._show_error("No design selected")
                return

            item = selection[0]
            file_path = self.designs_tree.item(item, 'tags')[0]

            if file_path:
                metadata, geometry = self.design_storage.load_design(file_path)

                # Load into current session
                self.current_geometry = geometry
                self.current_results = metadata.performance_metrics

                # Update UI elements
                self._show_geometry_preview()

                # Update substrate size if different
                if hasattr(metadata, 'substrate_width') and metadata.substrate_width:
                    self.substrate_width_var.set(str(metadata.substrate_width))
                    self.substrate_height_var.set(str(metadata.substrate_height))
                    self.trace_width_var.set(metadata.trace_width_mil)

                    # Update generator with loaded substrate size
                    width = float(metadata.substrate_width)
                    height = float(metadata.substrate_height)
                    self.generator = AntennaDesignGenerator(self.nec, width, height)

                # Update status
                self.status_var.set(f"Loaded design: {metadata.name}")
                self._log_message(f"Loaded design: {metadata.name}")

                # Switch to results tab to show loaded design
                # Note: This would require access to the notebook widget

        except Exception as e:
            logger.error(f"Failed to load selected design: {str(e)}")
            self._show_error(f"Failed to load design: {str(e)}")

    def _delete_selected_design(self):
        """Delete the selected design from storage."""
        try:
            selection = self.designs_tree.selection()
            if not selection:
                self._show_error("No design selected")
                return

            item = selection[0]
            values = self.designs_tree.item(item, 'values')
            file_path = self.designs_tree.item(item, 'tags')[0]

            design_name = values[0] if values else "Unknown"

            # Confirm deletion
            if not messagebox.askyesno("Confirm Delete",
                                     f"Delete design '{design_name}'?\nThis action cannot be undone."):
                return

            # Delete the design
            if self.design_storage.delete_design(file_path):
                self._log_message(f"Deleted design: {design_name}")
                self.status_var.set(f"Deleted design: {design_name}")
                self._refresh_designs_list()
                self.details_text.delete(1.0, END)
                self.thumbnail_label.config(image=None, text="Select a design to view thumbnail")
                self.current_thumbnail = None  # Clear the reference
            else:
                self._show_error("Failed to delete design")

        except Exception as e:
            logger.error(f"Failed to delete design: {str(e)}")
            self._show_error(f"Failed to delete design: {str(e)}")

    def _export_selected_design(self):
        """Export the selected design to vector format."""
        try:
            selection = self.designs_tree.selection()
            if not selection:
                self._show_error("No design selected")
                return

            item = selection[0]
            file_path = self.designs_tree.item(item, 'tags')[0]

            if file_path:
                metadata, geometry = self.design_storage.load_design(file_path)

                # Set as current geometry for export
                self.current_geometry = geometry
                self.current_results = metadata.performance_metrics

                # Use existing export functionality
                self.export_filename_var.set(metadata.name or "exported_design")

                # Switch to export tab (would need notebook access)
                # For now, just export to default format
                self._export_geometry('svg')

        except Exception as e:
            logger.error(f"Failed to export selected design: {str(e)}")
            self._show_error(f"Failed to export design: {str(e)}")

    def _edit_design_notes(self):
        """Edit notes for the selected design."""
        try:
            selection = self.designs_tree.selection()
            if not selection:
                self._show_error("No design selected")
                return

            item = selection[0]
            file_path = self.designs_tree.item(item, 'tags')[0]

            if file_path:
                metadata, geometry = self.design_storage.load_design(file_path)

                # Notes editing dialog
                notes_dialog = Toplevel(self.root)
                notes_dialog.title(f"Edit Notes - {metadata.name}")
                notes_dialog.geometry("500x300")
                notes_dialog.resizable(True, True)
                notes_dialog.transient(self.root)
                notes_dialog.grab_set()

                ttk.Label(notes_dialog, text="Design Notes:").pack(pady=(10, 0))

                notes_text = ScrolledText(notes_dialog, height=15, wrap=WORD)
                notes_text.pack(fill='both', expand=True, padx=10, pady=5)
                notes_text.insert(END, metadata.custom_notes)

                def save_notes():
                    new_notes = notes_text.get(1.0, END).strip()
                    if new_notes != metadata.custom_notes:
                        # Update metadata and save
                        metadata.custom_notes = new_notes

                        # Re-save the design
                        saved_path = self.design_storage.save_design(geometry, metadata)

                        self._log_message(f"Updated notes for design: {metadata.name}")
                        self.status_var.set(f"Updated notes for {metadata.name}")

                    notes_dialog.destroy()

                button_frame = ttk.Frame(notes_dialog)
                button_frame.pack(fill='x', pady=(0, 10))

                ttk.Button(button_frame, text="Save", command=save_notes).pack(side=RIGHT, padx=5)
                ttk.Button(button_frame, text="Cancel", command=notes_dialog.destroy).pack(side=RIGHT, padx=5)

                notes_text.focus()

        except Exception as e:
            logger.error(f"Failed to edit design notes: {str(e)}")
            self._show_error(f"Failed to edit notes: {str(e)}")

    def _search_designs(self):
        """Search designs based on search entry."""
        try:
            query = self.design_search_var.get().strip()

            if not query:
                # Show all designs
                self._refresh_designs_list()
                return

            # Perform search
            results = self.design_storage.search_designs(query)

            # Clear existing items
            for item in self.designs_tree.get_children():
                self.designs_tree.delete(item)

            # Add search results
            for design in results:
                frequencies = "/".join([f"{f:g}" for f in design.get('frequencies_mhz', [])])

                self.designs_tree.insert('', 'end', values=(
                    design.get('name', 'Unknown'),
                    design.get('band_name', 'Unknown'),
                    frequencies,
                    design.get('created_date', '')[:19],
                    design.get('design_type', 'Unknown')
                ), tags=(design.get('file_path', ''),))

            self.status_var.set(f"Search results: {len(results)} matches for '{query}'")

        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            self._show_error("Search failed")

    def _delayed_initial_refresh(self):
        """Delayed initialization of design library after mainloop starts."""
        logger.info("Performing delayed design library initialization...")
        try:
            self._refresh_designs_list()
            logger.info("Design library loaded successfully")
        except Exception as e:
            logger.error(f"Delayed design library initialization failed: {str(e)}")
            # Show error but don't crash application
            self._show_design_storage_error(str(e))
            # Continue with empty design list

    def _show_design_storage_error(self, error_msg):
        """Show design storage initialization error with recovery options."""
        try:
            logger.warning(f"Design storage initialization error: {error_msg}")
            self.library_stats_var.set("Error loading design library")

            # Don't crash, show a warning dialog and continue with empty library
            error_info = f"""Design Library Warning

The application encountered an error while loading your saved designs:

{error_msg}

The design library feature will not be available until the issue is resolved. You can continue using the design and export features normally.

Possible solutions:
• Check that the designs directory exists and is accessible
• Ensure design files are not corrupted
• Try restarting the application

Click OK to continue with an empty design library.
"""
            messagebox.showwarning("Design Library Warning", error_info)
        except Exception as e:
            logger.error(f"Failed to show design storage error dialog: {str(e)}")


def test_storage():
    """Test design storage system without launching GUI."""
    try:
        print("Testing design storage initialization...")
        from storage import DesignStorage, DesignMetadata

        # Test initialization
        storage = DesignStorage()
        print(f"✓ Storage initialized at: {storage.storage_dir}")

        # Test listing designs
        designs = storage.list_designs()
        print(f"✓ Found {len(designs)} existing designs")

        if designs:
            # Test loading a design
            first_design = designs[0]
            file_path = first_design.get('file_path')
            if file_path:
                metadata, geometry = storage.load_design(file_path)
                print(f"✓ Successfully loaded design: {metadata.name}")
            else:
                print("! Could not find file path in design metadata")

        # Test creating and saving a test design
        print("Testing design save...")
        test_metadata = DesignMetadata(
            name="Storage Test Design",
            frequencies_mhz=(2400, 5500, 5800)
        )

        test_geometry = """CM Mini Antenna Designer Storage Test
GW      1   1   0.000   0.000   0.000   1.000   0.000   0.010
GW      2   1   0.000   0.000   0.010   0.000   1.000   0.010
GE      1   0   0       0       0       0
GN      1   0   0       0       0       0
FR      0   1   0       0       2400    0
EX      0   1   1       1       0       0
RP      0   1   1       1001    0       0       1.000   1.000   0       0"""

        saved_path = storage.save_design(test_geometry, test_metadata)
        print(f"✓ Saved test design to: {saved_path}")

        # Test cleanup
        if storage.delete_design(saved_path):
            print("✓ Successfully cleaned up test design")
        else:
            print("! Failed to clean up test design")

        print("\n✓ All storage tests passed!")

    except Exception as e:
        print(f"✗ Storage test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

    return True


def main():
    """Main application entry point."""
    import sys

    # Check for debug flags
    if len(sys.argv) > 1:
        if sys.argv[1] == '--test-storage':
            success = test_storage()
            sys.exit(0 if success else 1)
        elif sys.argv[1] == '--debug-storage':
            print("Running storage diagnostics...")
            success = test_storage()
            if success:
                print("Starting application in debug mode...")
            else:
                print("Storage tests failed, starting application anyway...")
        else:
            print(f"Unknown argument: {sys.argv[1]}")
            print("Usage: python ui.py [--test-storage|--debug-storage]")
            sys.exit(1)

    try:
        root = Tk()
        app = AntennaDesignerGUI(root)

        # Handle window close gracefully
        def on_closing():
            if app.processing_thread and app.processing_thread.is_alive():
                if messagebox.askyesno("Quit", "Optimization in progress. Really quit?"):
                    root.quit()
            else:
                root.quit()

        root.protocol("WM_DELETE_WINDOW", on_closing)
        root.mainloop()

    except Exception as e:
        logger.critical(f"Application startup failed: {str(e)}")
        messagebox.showerror("Startup Error", f"Failed to start application:\n{str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
