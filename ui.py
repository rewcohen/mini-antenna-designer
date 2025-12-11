"""Desktop user interface for the Mini Antenna Designer."""
from tkinter import *
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
import threading
import time
from typing import Optional, Dict, Any
from loguru import logger

from core import NEC2Interface, NEC2Error, AntennaMetrics
from design import AntennaDesign, AntennaGeometryError
from design_generator import AntennaDesignGenerator
from export import VectorExporter, ExportError
from presets import BandPresets, BandType, FrequencyBand

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

        # State variables
        self.current_geometry: Optional[str] = None
        self.current_results: Optional[Dict] = None
        self.selected_band_key: Optional[str] = None
        self.processing_thread: Optional[threading.Thread] = None

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

            # Generate design in background thread
            self.processing_thread = threading.Thread(
                target=self._run_design_generation,
                args=(selected_band,)
            )
            self.processing_thread.daemon = True
            self.processing_thread.start()

        except Exception as e:
            self._show_error(f"Error starting design generation: {str(e)}")

    def _run_design_generation(self, frequency_band):
        """Run design generation in background thread."""
        try:
            # Generate the design
            results = self.generator.generate_design(frequency_band)

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
                self.status_var.set("Design generation complete")
                self._log_message(f"Design generated: {results.get('design_type', 'Unknown')} type - {results.get('band_name', 'Unknown')}")
                design_type = results.get('design_type', 'Unknown')
                band_name = results.get('band_name', 'Unknown')
                freqs = f"{results.get('freq1_mhz', 'N/A')}/{results.get('freq2_mhz', 'N/A')}/{results.get('freq3_mhz', 'N/A')} MHz"
                self.status_var.set(f"Generated {design_type} for {band_name} ({freqs})")
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
                'fitness_score': ".3f" if self.current_results else 'N/A'
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

def main():
    """Main application entry point."""
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

if __name__ == "__main__":
    main()
