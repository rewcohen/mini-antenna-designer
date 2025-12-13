"""Desktop user interface for the Mini Antenna Designer."""
from tkinter import *
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
import threading
import time
import random
from typing import Optional, Dict, Any
import base64
from io import BytesIO
import os
import string
try:
    from PIL import Image, ImageTk
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPM
    PIL_AVAILABLE = True
except ImportError as e:
    PIL_AVAILABLE = False
    logger.warning(f"PIL libraries not available for SVG rendering: {str(e)}")
from loguru import logger

from core import NEC2Interface, NEC2Error, AntennaMetrics, validate_system_configuration
from design import AntennaDesign, AntennaGeometryError
from design_generator import AntennaDesignGenerator
from export import VectorExporter, ExportError
from presets import BandPresets, BandType, FrequencyBand
from storage import DesignStorage, DesignMetadata

class AntennaDesignerGUI:
    """Main GUI application for antenna design."""

    # Azure color scheme
    AZURE_COLORS = {
        'primary': '#0078D4',          # Main Azure blue
        'primary_hover': '#106EBE',    # Darker blue for hover
        'primary_light': '#E1E5ED',    # Very light blue background
        'success': '#107C10',          # Green for completed steps
        'current': '#0078D4',          # Current step highlight
        'upcoming': '#B3B3B3',         # Gray for future steps
        'border': '#EDEBE9',           # Light borders
        'background': '#F3F2F1',       # Background gray
        'background_dark': '#EAEAEA',  # Darker background
        'text_primary': '#201F1E',     # Dark text
        'text_secondary': '#605E5C'    # Secondary text
    }

    # Workflow steps
    WORKFLOW_STEPS = [
        {
            'id': 'design',
            'name': 'Design',
            'description': 'Configure antenna parameters',
            'tab_index': 0
        },
        {
            'id': 'results',
            'name': 'Results',
            'description': 'Review generated design',
            'tab_index': 1
        },
        {
            'id': 'analysis',
            'name': 'Analysis',
            'description': 'View band analysis',
            'tab_index': 2
        },
        {
            'id': 'export',
            'name': 'Export',
            'description': 'Export design files',
            'tab_index': 3
        },
        {
            'id': 'designs',
            'name': 'My Designs',
            'description': 'Manage saved designs',
            'tab_index': 4
        }
    ]

    def __init__(self, root):
        """Initialize the GUI."""
        self.root = root
        self.root.title("Mini Antenna Designer - Tri-Band Design")
        self.root.geometry("1200x850")  # Slightly taller for workflow components
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

        # Workflow state variables
        self.workflow_current_step = 0  # 0-based index
        self.workflow_completed_steps = set()  # Set of completed step IDs
        self.workflow_last_generation_hash = None  # Hash of UI settings for change detection

        # Substrate size variables (default to 4x2 inches)
        self.substrate_width_var = StringVar(value="4.0")
        self.substrate_height_var = StringVar(value="2.0")

        # Trace width variables (default to 10 mil, minimum 5 mil)
        self.trace_width_var = DoubleVar(value=10.0)
        self.trace_width_label_var = StringVar(value="10.0 mil - Good")

        # Advanced design parameters
        self.coupling_factor_var = DoubleVar(value=0.90)
        self.bend_radius_var = DoubleVar(value=1.0)  # in mm
        self.substrate_epsilon_var = DoubleVar(value=4.3)  # FR-4
        self.substrate_thickness_var = DoubleVar(value=1.6)  # mm
        self.meander_density_var = DoubleVar(value=1.0)  # 1.0 = normal

        # Design preview variables
        self.preview_total_length_var = StringVar(value="-- mm")
        self.preview_segment_count_var = StringVar(value="--")
        self.preview_target_length_var = StringVar(value="-- mm")
        self.preview_length_error_var = StringVar(value="--")

        # Chart zoom/pan variables
        self.chart_zoom_level = 1.0
        self.chart_pan_x = 0
        self.chart_pan_y = 0
        self.chart_image_path = None
        self.chart_original_image = None
        self.chart_current_photo = None

        # Designs tab zoom variables
        self.designs_zoom_level = 2.5  # Start at 250% zoom for better visibility
        self.current_design_svg_data = None  # Store current SVG for re-rendering on zoom

        # Create GUI components
        self._create_menu()
        self._create_main_layout()

        # Status bar
        self.status_var = StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(root, textvariable=self.status_var, relief=SUNKEN, anchor=W)
        status_bar.pack(side=BOTTOM, fill=X)

        # Setup global error handling
        self._setup_global_error_handling()

        # Validate system configuration
        try:
            config_status = validate_system_configuration()
            if not config_status['valid']:
                logger.warning("Configuration issues detected")
                # Defer showing error until mainloop starts to avoid blocking init
                self.root.after(100, lambda: self._show_error("System Configuration Issues:\n" + "\n".join(config_status['checks'])))
            else:
                logger.info("System configuration validated: " + ", ".join(config_status['checks']))
        except Exception as e:
            logger.error(f"Configuration validation failed: {str(e)}")

        logger.info("GUI initialized")

    def _setup_global_error_handling(self):
        """Setup global error handling for Tkinter."""
        def handle_exception(exc_type, exc_value, exc_traceback):
            error_msg = f"{exc_type.__name__}: {str(exc_value)}"
            logger.critical(f"Uncaught exception: {error_msg}")
            import traceback
            trace_details = "".join(traceback.format_tb(exc_traceback))
            logger.debug(f"Traceback:\n{trace_details}")
            
            # Show error dialog
            self._show_error(f"An unexpected error occurred:\n{error_msg}")
            
        self.root.report_callback_exception = handle_exception

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
        # Create main container with workflow components
        main_container = ttk.Frame(self.root)
        main_container.pack(fill='both', expand=True)

        # Top progress bar
        self.workflow_progress_frame = ttk.Frame(main_container, height=60)
        self.workflow_progress_frame.pack(fill='x', side='top', padx=5, pady=5)
        self._create_workflow_progress_bar()

        # Main content area (tabs)
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        # Add tabs with workflow status indicators
        self._create_tabs()

        # Bottom navigation
        self.workflow_nav_frame = ttk.Frame(main_container, height=50)
        self.workflow_nav_frame.pack(fill='x', side='bottom', padx=5, pady=5)
        self._create_workflow_navigation()

        # Bind tab change event for auto-calculation
        self.notebook.bind('<<NotebookTabChanged>>', self._on_tab_changed)

    def _create_tabs(self):
        """Create all tabs with workflow status indicators."""
        # Design tab
        design_frame = ttk.Frame(self.notebook)
        self.notebook.add(design_frame, text='⚙️ Design')
        self._create_design_tab(design_frame)

        # Results & Analysis tab (combined)
        results_frame = ttk.Frame(self.notebook)
        self.notebook.add(results_frame, text='📊 Results & Analysis')
        self._create_combined_results_tab(results_frame)

        # My Designs tab (with export features)
        designs_frame = ttk.Frame(self.notebook)
        self.notebook.add(designs_frame, text='💾 My Designs')
        self._create_designs_tab(designs_frame)

        # Initialize workflow display
        self._update_workflow_display()

    def _create_workflow_progress_bar(self):
        """Create a horizontal perforated progress bar showing workflow completion."""
        # Main progress container
        progress_container = ttk.Frame(self.workflow_progress_frame)
        progress_container.pack(fill='both', expand=True, padx=10, pady=5)

        # Workflow status area
        status_label = ttk.Label(progress_container, text="",
                               font=('Segoe UI', 11, 'bold'),
                               foreground=self.AZURE_COLORS['text_primary'])
        status_label.pack(anchor='w')
        self.workflow_status_label = status_label

        # Progress bar frame
        progress_frame = ttk.Frame(progress_container)
        progress_frame.pack(fill='x', pady=(5, 0))

        # Apply perforated styling
        self._apply_progress_bar_styling()

        # Progress bar with Azure colors
        self.workflow_progress_var = DoubleVar(value=0.0)
        self.workflow_progress = ttk.Progressbar(
            progress_frame,
            orient='horizontal',
            mode='determinate',
            variable=self.workflow_progress_var,
            maximum=100.0,
            length=600,  # Fixed width for consistency
            style='Azure.Horizontal.TProgressbar'
        )
        self.workflow_progress.pack(side='left', expand=True)

        # Percentage label
        self.progress_percentage_label = ttk.Label(
            progress_frame,
            text="0%",
            font=('Segoe UI', 10, 'bold'),
            foreground=self.AZURE_COLORS['current']
        )
        self.progress_percentage_label.pack(side='left', padx=(10, 0))

        # Current step indicator label
        self.workflow_step_indicator = ttk.Label(
            progress_container,
            text="Design: Configure antenna parameters",
            font=('Segoe UI', 9),
            foreground=self.AZURE_COLORS['text_secondary']
        )
        self.workflow_step_indicator.pack(anchor='w', pady=(2, 0))

    def _create_workflow_navigation(self):
        """Create the bottom navigation buttons with high contrast solid backgrounds."""
        nav_container = ttk.Frame(self.workflow_nav_frame)
        nav_container.pack(anchor='center', pady=5)

        # Previous button - use Label as button for solid background
        self.prev_button = ttk.Label(nav_container,
                                    text="◀ Previous",
                                    font=('Segoe UI', 11, 'bold'),
                                    background='#FFFFFF',
                                    foreground='#0078D4',
                                    anchor='center',
                                    padding=[10, 5],
                                    borderwidth=2,
                                    relief='raised')
        self.prev_button.pack(side='left', padx=10)
        self.prev_button.config(state='disabled')
        self.prev_button.bind('<Button-1>', lambda e: self._previous_workflow_step())
        self.prev_button.bind('<Enter>', lambda e: self.prev_button.config(background='#F0F0F0'))
        self.prev_button.bind('<Leave>', lambda e: self.prev_button.config(background='#FFFFFF'))

        # Separator
        separator = ttk.Frame(nav_container, width=20, height=1)
        separator.pack(side='left')

        # Next button - use Label as button for solid background
        self.next_button = ttk.Label(nav_container,
                                    text="Next: Results ▶",
                                    font=('Segoe UI', 11, 'bold'),
                                    background='#0078D4',
                                    foreground='#FFFFFF',
                                    anchor='center',
                                    padding=[10, 5],
                                    borderwidth=2,
                                    relief='raised')
        self.next_button.pack(side='left', padx=10)
        self.next_button.bind('<Button-1>', lambda e: self._next_workflow_step())
        self.next_button.bind('<Enter>', lambda e: self.next_button.config(background='#005A9E'))
        self.next_button.bind('<Leave>', lambda e: self.next_button.config(background='#0078D4'))

        # Hint label
        hint_label = ttk.Label(self.workflow_nav_frame,
                             text="Tip: Click progress dots above to jump between completed steps",
                             font=('Segoe UI', 8),
                             foreground=self.AZURE_COLORS['text_secondary'])
        hint_label.pack(anchor='center', pady=(5, 0))

    def _apply_azure_button_styling(self):
        """Apply Azure styling to buttons."""
        style = ttk.Style()

        # Azure primary button style with high contrast
        style.configure('Azure.TButton',
                       font=('Segoe UI', 11, 'bold'),
                       background=self.AZURE_COLORS['primary'],
                       foreground='white',
                       padding=[20, 10, 20, 10],
                       borderwidth=2,
                       relief='raised')

        style.map('Azure.TButton',
                 background=[('active', self.AZURE_COLORS['primary_hover']),
                           ('pressed', '#005A9E')],
                 foreground=[('active', 'white'),
                           ('pressed', 'white')])

        # Add themed style for better cross-platform compatibility
        try:
            style.element_create('Azure.Button.back',
                               'from', 'default')
            style.layout('Azure.TButton',
                        [('Azure.Button.back', {'sticky': 'ewnc'}),
                         ('Button.focus', {'children':
                           [('Button.text', {'sticky': ''})]})])
        except:
            # Fallback styling
            pass

    def _apply_progress_bar_styling(self):
        """Apply perforated styling to the progress bar."""
        style = ttk.Style()

        # Create perforated progress bar style with Azure colors
        style.configure('Azure.Horizontal.TProgressbar',
                       background=self.AZURE_COLORS['primary'],
                       troughcolor='#E1E5ED',  # Light background for contrast
                       borderwidth=1,
                       lightcolor=self.AZURE_COLORS['border'],
                       darkcolor=self.AZURE_COLORS['border'])

        # Add segmented appearance to make it look perforated
        try:
            # Try to create a custom element for perforated effect
            style.element_create('AzureProgress.trough', 'from', 'default')
            style.element_create('AzureProgress.pbar', 'from', 'default')

            style.layout('Azure.Horizontal.TProgressbar',
                        [('AzureProgress.trough', {'children':
                          [('AzureProgress.pbar',
                            {'side': 'left', 'sticky': 'ns'})],
                          'sticky': 'nswe'})])

        except Exception:
            # Fallback to basic styling
            pass

    def _get_workflow_progress_percentage(self):
        """Calculate percentage completion based on current workflow state."""
        total_steps = len(self.WORKFLOW_STEPS)
        if total_steps == 0:
            return 0.0

        # Base progress calculation: Design tab = 25%, Results = 50%, Analysis = 75%, Export = 99%, My Designs = 100%
        step_percentages = {
            'design': 25.0,   # Design tab completion
            'results': 50.0,  # Results tab completion
            'analysis': 75.0, # Analysis tab completion
            'export': 99.0,   # Export tab completion (almost complete)
            'designs': 100.0  # My Designs tab = 100% complete
        }

        current_step_id = self.WORKFLOW_STEPS[self.workflow_current_step]['id']
        completion_step_id = self.WORKFLOW_STEPS[self.workflow_current_step]['id']

        # If current step is completed, show its completion percentage
        # If on My Designs tab specifically, always show 100%
        if current_step_id == 'designs':
            return 100.0

        # Otherwise show the completion percentage for the current step
        return step_percentages.get(current_step_id, 0.0)

    def _jump_to_workflow_step(self, step_index):
        """Jump to a specific workflow step if it's accessible."""
        if step_index < 0 or step_index >= len(self.WORKFLOW_STEPS):
            return

        # Check if we can jump to this step (must have completed previous steps or be adjacent)
        current_completed = len(self.workflow_completed_steps)
        if step_index > current_completed and step_index != self.workflow_current_step + 1:
            # Show message that step is not yet accessible
            step_name = self.WORKFLOW_STEPS[step_index]['name']
            self._show_error(f"Complete the current step first to access '{step_name}'")
            return

        # Jump to the step
        self.workflow_current_step = step_index
        self.notebook.select(step_index)
        self._update_workflow_display()

    def _next_workflow_step(self):
        """Advance to the next workflow step."""
        if self.workflow_current_step < len(self.WORKFLOW_STEPS) - 1:
            self.workflow_current_step += 1
            self.notebook.select(self.workflow_current_step)
            self._update_workflow_display()

    def _previous_workflow_step(self):
        """Go back to the previous workflow step."""
        if self.workflow_current_step > 0:
            self.workflow_current_step -= 1
            self.notebook.select(self.workflow_current_step)
            self._update_workflow_display()

    def _mark_workflow_step_completed(self, step_id):
        """Mark a workflow step as completed."""
        self.workflow_completed_steps.add(step_id)

        # Also mark current step as completed if different
        current_step = self.WORKFLOW_STEPS[self.workflow_current_step]
        if current_step['id'] == step_id:
            self.workflow_completed_steps.add(step_id)

        self._update_workflow_display()

    def _on_tab_changed(self, event=None):
        """Handle tab change events for workflow auto-generation and status updates."""
        try:
            # Get the currently selected tab
            current_tab = self.notebook.select()
            if not current_tab:
                return

            tab_text = self.notebook.tab(current_tab, "text")

            # Update workflow current step based on selected tab
            self.workflow_current_step = self.notebook.index(current_tab)
            self._update_workflow_display()

            # Check for design completion - if leaving Design tab with valid settings, auto-generate
            previous_tab = getattr(self, '_previous_tab', None)
            if previous_tab and self.notebook.tab(previous_tab, "text") == "Design":
                if not self.current_geometry and not self.processing_thread:
                    # Check if we have valid settings to auto-generate
                    has_valid_settings = self._has_valid_design_settings()
                    if has_valid_settings and self.workflow_current_step > 0:  # Not staying on design tab
                        self._auto_generate_design_for_workflow()

            # Store current tab as previous for next change
            self._previous_tab = current_tab

            # Auto-generate band analysis when visiting that tab
            if tab_text == "Band Analysis":
                self._log_message("Band Analysis tab selected - generating chart automatically...")
                # Always attempt to generate analysis, it will handle missing data gracefully
                try:
                    self._generate_band_chart()
                except Exception as e:
                    logger.error(f"Auto-generation of band analysis failed: {str(e)}")
                    self._log_message("Failed to auto-generate band analysis chart")
                    self.status_var.set("Band analysis auto-generation failed - use manual button")

            # Auto-trigger save dialog when visiting My Designs tab
            if tab_text == "My Designs":
                # Only trigger if we have a current design that hasn't been flagged as already prompted
                if self.current_geometry and self.current_results:
                    # Check if we've already prompted for this specific design
                    current_design_hash = None
                    try:
                        import hashlib
                        # Create a simple hash of key design parameters to identify this design
                        design_key = f"{self.current_results.get('freq1_mhz', '')}_{self.current_results.get('freq2_mhz', '')}_{self.current_results.get('freq3_mhz', '')}_{self.current_results.get('design_type', '')}"
                        current_design_hash = hashlib.md5(design_key.encode()).hexdigest()
                    except:
                        pass

                    # Check if we've already prompted for this design in this session
                    if not hasattr(self, '_designs_save_prompted_hash') or self._designs_save_prompted_hash != current_design_hash:
                        # Ask user if they want to save the current design
                        self._designs_save_prompted_hash = current_design_hash
                        self.root.after(100, lambda: self._prompt_auto_save_current_design())

        except Exception as e:
            logger.error(f"Error handling tab change: {str(e)}")

    def _has_valid_design_settings(self):
        """Check if current UI settings are sufficient for design generation."""
        try:
            # Check if we have a selected band or custom frequencies
            has_band_selection = bool(self.band_var.get())
            has_custom_freqs = False

            try:
                f1 = float(self.freq1_var.get())
                has_custom_freqs = f1 > 0
            except (ValueError, TypeError):
                pass

            return has_band_selection or has_custom_freqs

        except Exception as e:
            logger.error(f"Error checking design settings: {str(e)}")
            return False

    def _auto_generate_design_for_workflow(self):
        """Auto-generate design when user leaves Design tab to continue workflow."""
        try:
            self._log_message("Auto-generating design for workflow progression...")
            self.status_var.set("Auto-generating design for workflow...")

            # Generate design with current settings
            self._generate_design()
            self.workflow_completed_steps.add('design')

        except Exception as e:
            logger.error(f"Error in auto-generation: {str(e)}")
            self._show_error("Auto-generation failed. Continue manually from Design tab.")

    def _update_workflow_display(self):
        """Update progress bar, percentage display, and navigation based on current workflow state."""
        try:
            # Update progress bar with calculated percentage
            percentage = self._get_workflow_progress_percentage()
            self.workflow_progress_var.set(percentage)

            # Update percentage label with animated transition effect if applicable
            percentage_text = ""
            if percentage < 100:
                percentage_text = f"{int(percentage)}%"
            else:
                percentage_text = f"{int(percentage)}% ✓ Complete"

            self.progress_percentage_label.config(text=percentage_text)

            # Update step indicator text
            current_step_info = self.WORKFLOW_STEPS[self.workflow_current_step]
            step_text = f"{current_step_info['name']}: {current_step_info['description']}"
            self.workflow_step_indicator.config(text=step_text)

            # Update main status label
            completion_count = len(self.workflow_completed_steps)
            total_steps = len(self.WORKFLOW_STEPS)

            if completion_count == total_steps:
                workflow_text = f"[Complete] {current_step_info['name']}: {current_step_info['description']}"
            else:
                workflow_text = f"Step {self.workflow_current_step + 1} of {total_steps} - {current_step_info['name']}: {current_step_info['description']}"

            self.workflow_status_label.config(text=workflow_text)
            self.status_var.set(workflow_text)

            # Update navigation buttons
            if hasattr(self, 'prev_button') and hasattr(self, 'next_button'):
                # Previous button enabled if not at first step
                self.prev_button.config(state='normal' if self.workflow_current_step > 0 else 'disabled')

                # Next button text and enabled state
                if self.workflow_current_step < len(self.WORKFLOW_STEPS) - 1:
                    next_step = self.WORKFLOW_STEPS[self.workflow_current_step + 1]
                    self.next_button.config(
                        text=f"Next: {next_step['name']}",
                        state='normal'
                    )
                else:
                    self.next_button.config(text="Complete", state='disabled')

        except Exception as e:
            logger.error(f"Error updating workflow display: {str(e)}")

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

        # Advanced Settings (collapsible)
        self.advanced_settings_frame = ttk.LabelFrame(parent, text="⊕ Advanced Settings (Click to Expand)")
        self.advanced_settings_frame.pack(fill='x', padx=5, pady=5)
        self.advanced_settings_frame.bind('<Button-1>', self._toggle_advanced_settings)

        # Create advanced settings content (initially hidden)
        self.advanced_content = ttk.Frame(self.advanced_settings_frame)
        self.advanced_settings_visible = False

        # Row 1: Coupling Factor and Bend Radius
        ttk.Label(self.advanced_content, text="Coupling Factor (0.80-0.98):").grid(row=0, column=0, padx=5, pady=2, sticky='w')
        coupling_scale = ttk.Scale(self.advanced_content, from_=0.80, to=0.98, orient='horizontal',
                                  variable=self.coupling_factor_var, command=self._on_advanced_param_changed)
        coupling_scale.grid(row=0, column=1, padx=5, pady=2, sticky='ew')
        self.coupling_value_label = ttk.Label(self.advanced_content, text="0.90")
        self.coupling_value_label.grid(row=0, column=2, padx=5, pady=2)

        ttk.Label(self.advanced_content, text="Bend Radius (mm):").grid(row=0, column=3, padx=5, pady=2, sticky='w')
        bend_scale = ttk.Scale(self.advanced_content, from_=0.5, to=3.0, orient='horizontal',
                             variable=self.bend_radius_var, command=self._on_advanced_param_changed)
        bend_scale.grid(row=0, column=4, padx=5, pady=2, sticky='ew')
        self.bend_value_label = ttk.Label(self.advanced_content, text="1.0")
        self.bend_value_label.grid(row=0, column=5, padx=5, pady=2)

        # Row 2: Substrate Material Properties
        ttk.Label(self.advanced_content, text="Substrate εr:").grid(row=1, column=0, padx=5, pady=2, sticky='w')
        substrate_combo = ttk.Combobox(self.advanced_content, values=[
            "4.3 (FR-4)", "2.2 (Rogers RO4003)", "3.5 (Rogers RO4350)", "10.2 (Rogers TMM10)"
        ], state='readonly', width=20)
        substrate_combo.set("4.3 (FR-4)")
        substrate_combo.grid(row=1, column=1, padx=5, pady=2, sticky='ew')
        substrate_combo.bind('<<ComboboxSelected>>', self._on_substrate_material_changed)

        ttk.Label(self.advanced_content, text="Thickness (mm):").grid(row=1, column=3, padx=5, pady=2, sticky='w')
        thickness_entry = ttk.Entry(self.advanced_content, textvariable=self.substrate_thickness_var, width=8)
        thickness_entry.grid(row=1, column=4, padx=5, pady=2)
        thickness_entry.bind('<FocusOut>', lambda e: self._on_advanced_param_changed())

        # Row 3: Meander Density
        ttk.Label(self.advanced_content, text="Meander Density:").grid(row=2, column=0, padx=5, pady=2, sticky='w')
        density_scale = ttk.Scale(self.advanced_content, from_=0.5, to=2.0, orient='horizontal',
                                variable=self.meander_density_var, command=self._on_advanced_param_changed)
        density_scale.grid(row=2, column=1, padx=5, pady=2, sticky='ew')
        self.density_value_label = ttk.Label(self.advanced_content, text="1.0 (Normal)")
        self.density_value_label.grid(row=2, column=2, padx=5, pady=2)
        ttk.Label(self.advanced_content, text="← Sparse    Dense →", font=('Arial', 8, 'italic')).grid(row=2, column=3, columnspan=2, padx=5, pady=2, sticky='w')

        # Configure grid weights for advanced settings
        self.advanced_content.columnconfigure(1, weight=1)
        self.advanced_content.columnconfigure(4, weight=1)

        # Design Preview Panel
        preview_frame = ttk.LabelFrame(parent, text="📊 Design Preview (Estimated Trace Lengths)")
        preview_frame.pack(fill='x', padx=5, pady=5)

        # Create a grid layout for preview information
        preview_grid = ttk.Frame(preview_frame)
        preview_grid.pack(fill='x', padx=10, pady=5)

        # Column 1: Total Length
        ttk.Label(preview_grid, text="Total Trace Length:", font=('Arial', 9, 'bold')).grid(row=0, column=0, padx=5, pady=2, sticky='w')
        ttk.Label(preview_grid, textvariable=self.preview_total_length_var, font=('Arial', 11, 'bold'), foreground='blue').grid(row=0, column=1, padx=5, pady=2, sticky='w')

        # Column 2: Segment Count
        ttk.Label(preview_grid, text="Estimated Segments:", font=('Arial', 9, 'bold')).grid(row=0, column=2, padx=15, pady=2, sticky='w')
        ttk.Label(preview_grid, textvariable=self.preview_segment_count_var, font=('Arial', 11, 'bold'), foreground='green').grid(row=0, column=3, padx=5, pady=2, sticky='w')

        # Row 2: Target vs Actual
        ttk.Label(preview_grid, text="Target Length:", font=('Arial', 9)).grid(row=1, column=0, padx=5, pady=2, sticky='w')
        ttk.Label(preview_grid, textvariable=self.preview_target_length_var, font=('Arial', 10)).grid(row=1, column=1, padx=5, pady=2, sticky='w')

        ttk.Label(preview_grid, text="Length Error:", font=('Arial', 9)).grid(row=1, column=2, padx=15, pady=2, sticky='w')
        self.preview_error_label = ttk.Label(preview_grid, textvariable=self.preview_length_error_var, font=('Arial', 10))
        self.preview_error_label.grid(row=1, column=3, padx=5, pady=2, sticky='w')

        # Update button
        ttk.Button(preview_frame, text="🔄 Calculate Preview", command=self._update_design_preview).pack(pady=5)

        preview_note = ttk.Label(preview_frame, text="Note: Preview calculates estimated trace lengths based on current settings. Generate design for exact values.",
                               font=('Arial', 8, 'italic'), foreground='gray')
        preview_note.pack(pady=2)

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

    def _create_combined_results_tab(self, parent):
        """Create combined Results & Analysis tab with trace data and ASCII band analysis."""
        # Create notebook for tabbed sections within this tab
        inner_notebook = ttk.Notebook(parent)
        inner_notebook.pack(fill='both', expand=True, padx=2, pady=2)

        # Results Section
        results_section = ttk.Frame(inner_notebook)
        inner_notebook.add(results_section, text='Trace Results')
        self._create_results_section(results_section)

        # Band Analysis Section (ASCII-based)
        analysis_section = ttk.Frame(inner_notebook)
        inner_notebook.add(analysis_section, text='Band Analysis')
        self._create_analysis_section(analysis_section)

    def _create_results_section(self, parent):
        """Create the results section with detailed trace length information."""
        # Top section: Summary information
        summary_frame = ttk.LabelFrame(parent, text="Design Summary")
        summary_frame.pack(fill='x', padx=5, pady=5)

        self.results_text = ScrolledText(summary_frame, height=8, wrap=WORD)
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

        # Detailed Trace Length Information
        trace_frame = ttk.LabelFrame(parent, text="📏 Detailed Trace Lengths (Actual Line Lengths)")
        trace_frame.pack(fill='both', expand=True, padx=5, pady=5)

        # Controls
        control_bar = ttk.Frame(trace_frame)
        control_bar.pack(fill='x', padx=5, pady=2)

        ttk.Button(control_bar, text="Export Trace Data (CSV)", command=self._export_trace_data_csv).pack(side=LEFT, padx=2)
        ttk.Button(control_bar, text="Copy to Clipboard", command=self._copy_trace_data).pack(side=LEFT, padx=2)

        # Summary stats
        stats_frame = ttk.Frame(trace_frame)
        stats_frame.pack(fill='x', padx=5, pady=2)

        self.trace_total_length_var = StringVar(value="--")
        self.trace_count_var = StringVar(value="--")
        self.trace_avg_length_var = StringVar(value="--")
        self.trace_longest_var = StringVar(value="--")

        ttk.Label(stats_frame, text="Total Length:").grid(row=0, column=0, padx=5, sticky='w')
        ttk.Label(stats_frame, textvariable=self.trace_total_length_var, font=('Arial', 10, 'bold'), foreground='blue').grid(row=0, column=1, padx=5, sticky='w')

        ttk.Label(stats_frame, text="Trace Count:").grid(row=0, column=2, padx=10, sticky='w')
        ttk.Label(stats_frame, textvariable=self.trace_count_var, font=('Arial', 10, 'bold'), foreground='green').grid(row=0, column=3, padx=5, sticky='w')

        ttk.Label(stats_frame, text="Average Length:").grid(row=0, column=4, padx=10, sticky='w')
        ttk.Label(stats_frame, textvariable=self.trace_avg_length_var, font=('Arial', 10, 'bold')).grid(row=0, column=5, padx=5, sticky='w')

        ttk.Label(stats_frame, text="Longest Segment:").grid(row=0, column=6, padx=10, sticky='w')
        ttk.Label(stats_frame, textvariable=self.trace_longest_var, font=('Arial', 10, 'bold')).grid(row=0, column=7, padx=5, sticky='w')

        # Create treeview for trace data with scrollbars
        tree_container = ttk.Frame(trace_frame)
        tree_container.pack(fill='both', expand=True, padx=5, pady=5)

        # Scrollbars
        trace_scroll_y = ttk.Scrollbar(tree_container, orient='vertical')
        trace_scroll_y.pack(side=RIGHT, fill=Y)

        trace_scroll_x = ttk.Scrollbar(tree_container, orient='horizontal')
        trace_scroll_x.pack(side=BOTTOM, fill=X)

        # Treeview
        columns = ('Segment', 'Start X (in)', 'Start Y (in)', 'End X (in)', 'End Y (in)',
                   'Length (mm)', 'Length (in)', 'Width (mil)', 'Cumulative (mm)')
        self.trace_tree = ttk.Treeview(tree_container, columns=columns, show='headings',
                                       yscrollcommand=trace_scroll_y.set,
                                       xscrollcommand=trace_scroll_x.set)

        # Configure scrollbars
        trace_scroll_y.config(command=self.trace_tree.yview)
        trace_scroll_x.config(command=self.trace_tree.xview)

        # Define column headings and widths
        self.trace_tree.heading('Segment', text='Seg #')
        self.trace_tree.heading('Start X (in)', text='Start X (in)')
        self.trace_tree.heading('Start Y (in)', text='Start Y (in)')
        self.trace_tree.heading('End X (in)', text='End X (in)')
        self.trace_tree.heading('End Y (in)', text='End Y (in)')
        self.trace_tree.heading('Length (mm)', text='Length (mm) ⭐')
        self.trace_tree.heading('Length (in)', text='Length (in)')
        self.trace_tree.heading('Width (mil)', text='Width (mil)')
        self.trace_tree.heading('Cumulative (mm)', text='Cumulative (mm)')

        self.trace_tree.column('Segment', width=60, anchor='center')
        self.trace_tree.column('Start X (in)', width=85, anchor='e')
        self.trace_tree.column('Start Y (in)', width=85, anchor='e')
        self.trace_tree.column('End X (in)', width=85, anchor='e')
        self.trace_tree.column('End Y (in)', width=85, anchor='e')
        self.trace_tree.column('Length (mm)', width=100, anchor='e')
        self.trace_tree.column('Length (in)', width=85, anchor='e')
        self.trace_tree.column('Width (mil)', width=85, anchor='e')
        self.trace_tree.column('Cumulative (mm)', width=120, anchor='e')

        self.trace_tree.pack(fill='both', expand=True)

        # Add tags for alternating row colors
        self.trace_tree.tag_configure('oddrow', background='white')
        self.trace_tree.tag_configure('evenrow', background='#f0f0f0')

    def _create_analysis_section(self, parent):
        """Create ASCII-based band analysis section."""
        # Band analysis display area
        analysis_frame = ttk.LabelFrame(parent, text="📡 Band Analysis (ASCII Charts)")
        analysis_frame.pack(fill='both', expand=True, padx=5, pady=5)

        # Controls
        control_bar = ttk.Frame(analysis_frame)
        control_bar.pack(fill='x', padx=5, pady=5)

        ttk.Button(control_bar, text="Generate ASCII Analysis", command=self._generate_ascii_band_analysis).pack(side=LEFT, padx=5)
        ttk.Button(control_bar, text="Export Analysis (TXT)", command=self._export_ascii_analysis).pack(side=LEFT, padx=5)

        # ASCII chart display
        self.ascii_analysis_text = ScrolledText(analysis_frame, height=30, wrap=NONE, font=('Courier', 9))
        self.ascii_analysis_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Add initial placeholder text
        placeholder = """
╔═══════════════════════════════════════════════════════════════════════════╗
║                    BAND ANALYSIS - ASCII VISUALIZATION                     ║
╚═══════════════════════════════════════════════════════════════════════════╝

Click "Generate ASCII Analysis" after creating a design to see:
  • Frequency response charts
  • VSWR analysis per band
  • Impedance characteristics
  • Length distribution charts
  • Performance metrics

"""
        self.ascii_analysis_text.insert('1.0', placeholder)
        self.ascii_analysis_text.config(state='disabled')

    # Old tab creation functions removed - functionality merged into _create_combined_results_tab
    # and _create_designs_tab (with export features integrated)

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
            # Get the selected display name from combo box
            selected_display = self.band_combo.get()

            if not selected_display:
                self._show_error("No band selected")
                return

            # Find the band key using the existing band_map
            if selected_display not in self.band_map:
                self._show_error("Band not found")
                return

            band_key = self.band_map[selected_display]
            bands = BandPresets.get_all_bands()

            if band_key not in bands:
                self._show_error("Band data not available")
                return

            selected_band = bands[band_key]
            self.selected_band_key = band_key

            # Show analysis using current substrate size
            from presets import BandAnalysis
            try:
                # Get current substrate dimensions
                substrate_width = float(self.substrate_width_var.get())
                substrate_height = float(self.substrate_height_var.get())

                analysis = BandAnalysis.analyze_band_compatibility(
                    selected_band, substrate_width, substrate_height
                )

                # Log the analysis for debugging
                logger.info(f"Band analysis for '{selected_band.name}': feasibility={analysis['feasibility_score']:.1f}, "
                           f"complexity={analysis['design_complexity']}, constraints={analysis['size_constraints']}")

                # Format analysis message
                info_msg = f"""Band Analysis: {selected_band.name}
Description: {selected_band.description}
Frequencies: {selected_band.frequencies[0]}/{selected_band.frequencies[1]}/{selected_band.frequencies[2]} MHz

Feasibility Score: {analysis['feasibility_score']:.1f}/10
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
                logger.error(f"Band analysis processing failed: {str(e)}")
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
{chr(10).join('- ' + n for n in analysis['optimization_notes'][:3])}"""

                messagebox.showinfo("Band Analysis", info_msg)

        except Exception as e:
            logger.error(f"Band analysis failed: {str(e)}")
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
                # Mark design step as completed in workflow
                self._mark_workflow_step_completed('design')

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

            # Mark results step as completed if we displayed results
            self._mark_workflow_step_completed('results')

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

            # Populate trace length table
            if self.current_geometry:
                self._populate_trace_length_table(self.current_geometry)

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

    def _populate_trace_length_table(self, geometry):
        """Populate the trace length table with actual segment lengths."""
        try:
            import math

            # Clear existing data
            for item in self.trace_tree.get_children():
                self.trace_tree.delete(item)

            # Parse geometry
            lines = geometry.split('\n')
            segments = []

            for line in lines:
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 9 and parts[0] == 'GW':
                    try:
                        x1 = float(parts[3])
                        y1 = float(parts[4])
                        z1 = float(parts[5])
                        x2 = float(parts[6])
                        y2 = float(parts[7])
                        z2 = float(parts[8])
                        radius = float(parts[9]) if len(parts) > 9 else 0.005

                        # Calculate actual line length (Euclidean distance)
                        length_inches = math.sqrt((x2-x1)**2 + (y2-y1)**2 + (z2-z1)**2)
                        length_mm = length_inches * 25.4
                        width_mil = radius * 1000  # Convert inches to mil

                        segments.append({
                            'x1': x1, 'y1': y1, 'z1': z1,
                            'x2': x2, 'y2': y2, 'z2': z2,
                            'length_mm': length_mm,
                            'length_in': length_inches,
                            'width_mil': width_mil
                        })
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Failed to parse GW line: {line} - {str(e)}")
                        continue

            # Calculate statistics
            if segments:
                total_length_mm = sum(s['length_mm'] for s in segments)
                total_length_in = sum(s['length_in'] for s in segments)
                avg_length_mm = total_length_mm / len(segments)
                longest_mm = max(s['length_mm'] for s in segments)

                # Update summary stats
                self.trace_total_length_var.set(f"{total_length_mm:.2f} mm ({total_length_in:.3f} in)")
                self.trace_count_var.set(f"{len(segments)}")
                self.trace_avg_length_var.set(f"{avg_length_mm:.2f} mm")
                self.trace_longest_var.set(f"{longest_mm:.2f} mm")

                # Populate table
                cumulative = 0
                for idx, seg in enumerate(segments, 1):
                    cumulative += seg['length_mm']

                    tag = 'evenrow' if idx % 2 == 0 else 'oddrow'

                    self.trace_tree.insert('', 'end', values=(
                        idx,
                        f"{seg['x1']:.4f}",
                        f"{seg['y1']:.4f}",
                        f"{seg['x2']:.4f}",
                        f"{seg['y2']:.4f}",
                        f"{seg['length_mm']:.3f}",
                        f"{seg['length_in']:.4f}",
                        f"{seg['width_mil']:.1f}",
                        f"{cumulative:.2f}"
                    ), tags=(tag,))

                logger.info(f"Populated trace table with {len(segments)} segments, total length: {total_length_mm:.2f}mm")
            else:
                self.trace_total_length_var.set("No segments found")
                self.trace_count_var.set("0")
                self.trace_avg_length_var.set("--")
                self.trace_longest_var.set("--")

        except Exception as e:
            logger.error(f"Error populating trace length table: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())

    def _export_trace_data_csv(self):
        """Export trace data to CSV file."""
        try:
            if not self.current_geometry:
                self._show_error("No design generated. Please generate a design first.")
                return

            from tkinter import filedialog
            from datetime import datetime
            import csv

            # Ask user for save location
            default_filename = f"trace_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=default_filename
            )

            if not filepath:
                return

            # Collect trace data from tree
            with open(filepath, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow(['Segment', 'Start X (in)', 'Start Y (in)', 'End X (in)', 'End Y (in)',
                               'Length (mm)', 'Length (in)', 'Width (mil)', 'Cumulative (mm)'])

                # Write data
                for item in self.trace_tree.get_children():
                    values = self.trace_tree.item(item)['values']
                    writer.writerow(values)

            self.status_var.set(f"Trace data exported to {filepath}")
            logger.info(f"Trace data exported to CSV: {filepath}")

        except Exception as e:
            self._show_error(f"Error exporting trace data: {str(e)}")
            logger.error(f"CSV export error: {str(e)}")

    def _copy_trace_data(self):
        """Copy trace data to clipboard."""
        try:
            if not self.current_geometry:
                self._show_error("No design generated. Please generate a design first.")
                return

            # Collect trace data from tree
            data = []
            data.append('\t'.join(['Segment', 'Start X', 'Start Y', 'End X', 'End Y',
                                  'Length (mm)', 'Length (in)', 'Width (mil)', 'Cumulative']))

            for item in self.trace_tree.get_children():
                values = self.trace_tree.item(item)['values']
                data.append('\t'.join(str(v) for v in values))

            # Copy to clipboard
            clipboard_text = '\n'.join(data)
            self.root.clipboard_clear()
            self.root.clipboard_append(clipboard_text)

            self.status_var.set("Trace data copied to clipboard")
            logger.info("Trace data copied to clipboard")

        except Exception as e:
            self._show_error(f"Error copying trace data: {str(e)}")
            logger.error(f"Clipboard copy error: {str(e)}")

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

    def _toggle_advanced_settings(self, event=None):
        """Toggle visibility of advanced settings panel."""
        try:
            if self.advanced_settings_visible:
                # Hide advanced settings
                self.advanced_content.pack_forget()
                self.advanced_settings_frame.config(text="⊕ Advanced Settings (Click to Expand)")
                self.advanced_settings_visible = False
            else:
                # Show advanced settings
                self.advanced_content.pack(fill='x', padx=5, pady=5)
                self.advanced_settings_frame.config(text="⊖ Advanced Settings (Click to Collapse)")
                self.advanced_settings_visible = True
        except Exception as e:
            logger.error(f"Error toggling advanced settings: {str(e)}")

    def _on_advanced_param_changed(self, value=None):
        """Handle changes to advanced parameters."""
        try:
            # Update value labels
            self.coupling_value_label.config(text=f"{self.coupling_factor_var.get():.2f}")
            self.bend_value_label.config(text=f"{self.bend_radius_var.get():.1f}")

            density = self.meander_density_var.get()
            if density < 0.8:
                density_text = f"{density:.1f} (Very Sparse)"
            elif density < 1.0:
                density_text = f"{density:.1f} (Sparse)"
            elif density == 1.0:
                density_text = "1.0 (Normal)"
            elif density < 1.5:
                density_text = f"{density:.1f} (Dense)"
            else:
                density_text = f"{density:.1f} (Very Dense)"
            self.density_value_label.config(text=density_text)

            # Optionally auto-update preview
            # self._update_design_preview()
        except Exception as e:
            logger.error(f"Error updating advanced parameters: {str(e)}")

    def _on_substrate_material_changed(self, event=None):
        """Handle substrate material selection changes."""
        try:
            selection = event.widget.get()
            # Extract epsilon value from selection
            if "4.3" in selection:
                self.substrate_epsilon_var.set(4.3)
                self.substrate_thickness_var.set(1.6)  # Standard FR-4
            elif "2.2" in selection:
                self.substrate_epsilon_var.set(2.2)
                self.substrate_thickness_var.set(0.813)  # RO4003
            elif "3.5" in selection:
                self.substrate_epsilon_var.set(3.5)
                self.substrate_thickness_var.set(0.762)  # RO4350
            elif "10.2" in selection:
                self.substrate_epsilon_var.set(10.2)
                self.substrate_thickness_var.set(1.27)  # TMM10

            logger.info(f"Substrate material changed: εr={self.substrate_epsilon_var.get()}, t={self.substrate_thickness_var.get()}mm")
        except Exception as e:
            logger.error(f"Error changing substrate material: {str(e)}")

    def _update_design_preview(self):
        """Calculate and display estimated trace lengths based on current settings."""
        try:
            # Get current settings
            try:
                freq1 = float(self.freq1_var.get())
                freq2 = float(self.freq2_var.get())
                freq3 = float(self.freq3_var.get())
                frequencies = [freq1, freq2, freq3]
            except ValueError:
                self.preview_total_length_var.set("Invalid frequencies")
                return

            substrate_width = float(self.substrate_width_var.get())
            substrate_height = float(self.substrate_height_var.get())
            trace_width_mils = self.trace_width_var.get()

            # Get advanced parameters
            coupling_factor = self.coupling_factor_var.get()
            substrate_epsilon = self.substrate_epsilon_var.get()
            substrate_thickness = self.substrate_thickness_var.get() / 1000.0  # mm to meters

            # Create temporary advanced meander trace calculator
            from design import AdvancedMeanderTrace
            meander = AdvancedMeanderTrace(substrate_width, substrate_height)
            meander.substrate_epsilon = substrate_epsilon
            meander.substrate_thickness = substrate_thickness

            # Calculate target lengths for all frequencies
            total_target_length = 0
            for freq in frequencies:
                freq_hz = freq * 1e6
                e_eff = meander.calculate_effective_permittivity(
                    substrate_epsilon, substrate_thickness, trace_width_mils / 39370.0  # mils to meters
                )
                target = meander.calculate_target_length(freq_hz, e_eff, coupling_factor)
                total_target_length += target

            # Estimate segment count (rough approximation)
            avg_segment_length = 0.05  # 50mm average per segment
            estimated_segments = int(total_target_length / avg_segment_length)

            # Convert to mm for display
            total_length_mm = total_target_length * 1000

            # Update display
            self.preview_total_length_var.set(f"{total_length_mm:.1f} mm ({total_target_length * 39.37:.1f} in)")
            self.preview_segment_count_var.set(f"{estimated_segments}")
            self.preview_target_length_var.set(f"{total_length_mm:.1f} mm")
            self.preview_length_error_var.set("Generate for exact value")
            self.preview_error_label.config(foreground='gray')

            logger.info(f"Preview updated: {total_length_mm:.1f}mm, {estimated_segments} segments")

        except Exception as e:
            logger.error(f"Error updating design preview: {str(e)}")
            self.preview_total_length_var.set("Error calculating")
            self.preview_segment_count_var.set("--")
            import traceback
            logger.error(traceback.format_exc())

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

        # Zoom controls for preview
        zoom_controls_frame = ttk.Frame(preview_frame)
        zoom_controls_frame.pack(fill='x', padx=5, pady=2)

        ttk.Button(zoom_controls_frame, text="Zoom In +", command=self._designs_zoom_in).pack(side=LEFT, padx=2)
        ttk.Button(zoom_controls_frame, text="Zoom Out -", command=self._designs_zoom_out).pack(side=LEFT, padx=2)
        ttk.Button(zoom_controls_frame, text="Fit to View", command=self._designs_fit_to_view).pack(side=LEFT, padx=2)

        # Zoom level display
        self.zoom_level_label = ttk.Label(zoom_controls_frame, text=f"Zoom: {int(self.designs_zoom_level * 100)}%",
                                         font=('Arial', 9, 'bold'), foreground='blue')
        self.zoom_level_label.pack(side=LEFT, padx=10)

        # Scrollable thumbnail preview container
        preview_container = ttk.Frame(preview_frame)
        preview_container.pack(fill='both', expand=True, padx=5, pady=5)

        # Add scrollbars
        preview_scroll_y = ttk.Scrollbar(preview_container, orient='vertical')
        preview_scroll_y.pack(side=RIGHT, fill=Y)

        preview_scroll_x = ttk.Scrollbar(preview_container, orient='horizontal')
        preview_scroll_x.pack(side=BOTTOM, fill=X)

        # Canvas for scrolling
        self.thumbnail_canvas = Canvas(preview_container, background='lightgray',
                                      yscrollcommand=preview_scroll_y.set,
                                      xscrollcommand=preview_scroll_x.set)
        self.thumbnail_canvas.pack(fill='both', expand=True)

        preview_scroll_y.config(command=self.thumbnail_canvas.yview)
        preview_scroll_x.config(command=self.thumbnail_canvas.xview)

        # Label inside canvas for the actual thumbnail
        self.thumbnail_label = Label(self.thumbnail_canvas, text="Select a design to view thumbnail",
                                    background='lightgray', font=('Arial', 10))
        self.thumbnail_canvas_window = self.thumbnail_canvas.create_window(0, 0, anchor='nw', window=self.thumbnail_label)

        # Action buttons
        action_frame = ttk.Frame(preview_frame)
        action_frame.pack(fill='x', pady=(5, 0))

        ttk.Button(action_frame, text="Load Design", command=self._load_selected_design).pack(side=LEFT, padx=2)
        ttk.Button(action_frame, text="Edit Notes", command=self._edit_design_notes).pack(side=RIGHT, padx=2)

        # Export options frame
        export_options_frame = ttk.LabelFrame(right_panel, text="📦 Export Options")
        export_options_frame.pack(fill='x', pady=(5, 0))

        # Filename entry
        filename_frame = ttk.Frame(export_options_frame)
        filename_frame.pack(fill='x', padx=5, pady=5)

        ttk.Label(filename_frame, text="Filename:").pack(side=LEFT, padx=(0, 5))

        # Generate automatic filename with today's date and random suffix
        from datetime import datetime
        today_date = datetime.now().strftime("%Y%m%d")
        random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
        default_filename = f"antenna_{today_date}_{random_suffix}"
        self.export_filename_var = StringVar(value=default_filename)
        ttk.Entry(filename_frame, textvariable=self.export_filename_var, width=30).pack(side=LEFT, fill='x', expand=True)

        # Export format buttons
        export_buttons_frame = ttk.Frame(export_options_frame)
        export_buttons_frame.pack(fill='x', padx=5, pady=5)

        ttk.Button(export_buttons_frame, text="Export SVG",
                  command=lambda: self._export_geometry('svg')).pack(side=LEFT, padx=2)
        ttk.Button(export_buttons_frame, text="Export DXF",
                  command=lambda: self._export_geometry('dxf')).pack(side=LEFT, padx=2)
        ttk.Button(export_buttons_frame, text="Export PDF",
                  command=lambda: self._export_geometry('pdf')).pack(side=LEFT, padx=2)

        # Quick export from selected design
        ttk.Separator(export_buttons_frame, orient='vertical').pack(side=LEFT, fill='y', padx=5)
        ttk.Button(export_buttons_frame, text="Export Selected Design",
                  command=self._export_selected_design,
                  style='Accent.TButton').pack(side=LEFT, padx=2)

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

            # Create automatic filename suggestion
            from datetime import datetime
            today_date = datetime.now().strftime("%Y%m%d")
            random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
            default_filename = f"antenna_{today_date}_{random_suffix}"

            # Prompt for design name and filename
            save_dialog = Toplevel(self.root)
            save_dialog.title("Save Design")
            save_dialog.geometry("450x200")
            save_dialog.resizable(False, False)
            save_dialog.transient(self.root)
            save_dialog.grab_set()

            ttk.Label(save_dialog, text="Design Name:").pack(pady=(10, 0))

            # Generate automatic design name with today's date
            from datetime import datetime
            today_date = datetime.now().strftime("%Y%m%d")
            default_design_name = f"Design - {today_date}"

            name_var = StringVar(value=default_design_name)
            name_entry = ttk.Entry(save_dialog, textvariable=name_var, width=40)
            name_entry.pack(pady=5, padx=10)

            ttk.Label(save_dialog, text="Filename (optional):").pack(pady=(10, 0))
            filename_var = StringVar(value=default_filename)
            filename_entry = ttk.Entry(save_dialog, textvariable=filename_var, width=40)
            filename_entry.pack(pady=5, padx=10)
            ttk.Label(save_dialog, text="(leave blank to auto-generate)", font=('Arial', 8)).pack()

            def save_and_close():
                name = name_var.get().strip()
                filename = filename_var.get().strip()
                if not name:
                    messagebox.showerror("Error", "Please enter a design name.")
                    return

                if not filename.strip():
                    # Use the default filename pattern if left blank
                    filename = default_filename

                try:
                    # Create metadata with custom filename
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

                    self._log_message(f"Design saved: {name} (filename: {filename})")
                    self.status_var.set(f"Saved design: {name}")
                    self._refresh_designs_list()
                    save_dialog.destroy()

                except Exception as e:
                    self._show_error(f"Failed to save design: {str(e)}")

            ttk.Button(save_dialog, text="Save", command=save_and_close).pack(pady=(10, 10))
            name_entry.focus()

            # Bind Enter key to save
            save_dialog.bind('<Return>', lambda e: save_and_close())
            save_dialog.bind('<Escape>', lambda e: save_dialog.destroy())

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
        """Render base64 SVG data to tkinter PhotoImage for display with zoom support.

        Args:
            svg_data_uri: Base64 encoded SVG data URI (data:image/svg+xml;base64,...)

        Returns:
            ImageTk.PhotoImage or None if rendering failed
        """
        if not PIL_AVAILABLE:
            logger.warning("PIL libraries not available for SVG rendering")
            return None

        try:
            # Store the SVG data for re-rendering on zoom changes
            self.current_design_svg_data = svg_data_uri

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

            # Render at higher base resolution for better quality when zoomed
            base_scale = 2.0  # Render at 2x base resolution
            png_buffer = BytesIO()
            renderPM.drawToFile(drawing, png_buffer, fmt='PNG', dpi=144)  # Higher DPI for better quality
            png_buffer.seek(0)

            # Load PIL Image
            pil_image = Image.open(png_buffer)

            # Apply zoom level to the thumbnail
            width, height = pil_image.size
            zoom_width = int(width * self.designs_zoom_level / base_scale)
            zoom_height = int(height * self.designs_zoom_level / base_scale)

            # Set reasonable limits (much larger than before)
            max_width = 1200  # Increased from 400
            max_height = 900  # Increased from 300
            min_width = 100
            min_height = 75

            # Apply limits
            if zoom_width > max_width:
                scale_factor = max_width / zoom_width
                zoom_width = max_width
                zoom_height = int(zoom_height * scale_factor)
            if zoom_height > max_height:
                scale_factor = max_height / zoom_height
                zoom_height = max_height
                zoom_width = int(zoom_width * scale_factor)

            # Ensure minimum size
            if zoom_width < min_width:
                zoom_width = min_width
            if zoom_height < min_height:
                zoom_height = min_height

            # Resize with high-quality resampling
            pil_image = pil_image.resize((zoom_width, zoom_height), Image.Resampling.LANCZOS)

            # Convert to tkinter PhotoImage
            photo_image = ImageTk.PhotoImage(pil_image)

            logger.info(f"Rendered SVG thumbnail: {zoom_width}x{zoom_height} at {self.designs_zoom_level:.1f}x zoom")
            return photo_image

        except Exception as e:
            logger.error(f"Failed to render SVG thumbnail: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
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

                # Generate automatic filename with today's date and random suffix (same as export tab)
                from datetime import datetime
                today_date = datetime.now().strftime("%Y%m%d")
                random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
                default_filename = f"antenna_{today_date}_{random_suffix}"
                self.export_filename_var.set(default_filename)

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

    def _generate_band_chart(self):
        """Generate and display the band analysis chart for current working frequencies."""
        try:
            self._log_message("Generating band analysis chart...")
            self.status_var.set("Generating band analysis chart...")

            # Get current substrate dimensions
            substrate_width = float(self.substrate_width_var.get())
            substrate_height = float(self.substrate_height_var.get())

            # Import the chart module here to avoid circular imports
            from band_chart import BandAnalysisChart
            from presets import BandPresets

            # Create chart analyzer
            chart = BandAnalysisChart(substrate_width, substrate_height)

            # Get current working frequencies for chart
            custom_bands = {}

            # Try to get frequencies from current results first (if design has been generated)
            if self.current_results and 'freq1_mhz' in self.current_results:
                # Extract frequencies from current design results
                freq1 = self.current_results.get('freq1_mhz', 0)
                freq2 = self.current_results.get('freq2_mhz', 0)
                freq3 = self.current_results.get('freq3_mhz', 0)

                # Create custom band from current working frequencies
                current_band_name = f"Current: {freq1}/{freq2}/{freq3} MHz"
                if freq1 > 0:
                    frequencies = [freq1]
                    if freq2 > 0: frequencies.append(freq2)
                    if freq3 > 0: frequencies.append(freq3)

                    # Create FrequencyBand object
                    from presets import FrequencyBand, BandType
                    custom_band = FrequencyBand(
                        name=current_band_name,
                        band_type=BandType.CUSTOM,
                        frequencies_mhz=(freq1, freq2, freq3),
                        description="Current working frequencies",
                        applications=["Current design frequencies"]
                    )
                    custom_bands[current_band_name] = custom_band

                    self._log_message(f"Creating chart for current design: {freq1}/{freq2}/{freq3} MHz")
                else:
                    self._log_message("No valid frequencies in current design, falling back to all bands")

            # If no current results or invalid frequencies, try to get from UI inputs
            if not custom_bands:
                try:
                    freq1 = float(self.freq1_var.get())
                    freq2 = float(self.freq2_var.get())
                    freq3 = float(self.freq3_var.get())

                    if freq1 > 0:
                        current_band_name = f"UI Frequencies: {freq1}/{freq2}/{freq3} MHz"
                        frequencies = [freq1]
                        if freq2 > 0: frequencies.append(freq2)
                        if freq3 > 0: frequencies.append(freq3)

                        # Create FrequencyBand object with correct parameter names
                        from presets import FrequencyBand, BandType
                        try:
                            custom_band = FrequencyBand(
                                name=current_band_name,
                                band_type=BandType.CUSTOM,
                                frequencies_mhz=(freq1, freq2, freq3),
                                description="Frequencies from UI inputs",
                                applications=["Custom frequencies from UI"]
                            )
                            custom_bands[current_band_name] = custom_band
                            self._log_message(f"Creating chart for UI frequencies: {freq1}/{freq2}/{freq3} MHz")
                        except Exception as e:
                            logger.error(f"Failed to create FrequencyBand object: {str(e)}")
                            self._show_error("Failed to create frequency band configuration")
                            custom_bands = None
                    else:
                        # Fall back to all bands if no custom frequencies available
                        self._log_message("No custom frequencies available, showing all bands")
                        custom_bands = None

                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not parse frequencies from UI: {e}")
                    self._log_message("Invalid frequency values entered - using standard band charts")
                    custom_bands = None

            # Determine which type of chart to generate
            analysis_type = self.analysis_type_var.get()

            if analysis_type == "detailed":
                # Generate detailed chart for a specific band
                if custom_bands and len(custom_bands) == 1:
                    band_name = list(custom_bands.keys())[0]
                    chart_path = chart.create_detailed_band_chart(band_name, "band_analysis_detailed.png")
                else:
                    # Fallback to first available band
                    all_bands = BandPresets.get_all_bands()
                    if all_bands:
                        first_band_key = list(all_bands.keys())[0]
                        chart_path = chart.create_detailed_band_chart(first_band_key, "band_analysis_detailed.png")
                    else:
                        self._show_error("No frequency bands available for detailed analysis")
                        return
            else:
                # Generate custom comparison chart (focused on current frequencies)
                if custom_bands:
                    chart_path = chart.create_custom_comparison_chart(custom_bands, "band_analysis.png")
                else:
                    # Fallback to showing all bands
                    chart_path = chart.create_comparison_chart("band_analysis.png")

            if chart_path and os.path.exists(chart_path):
                # Display the chart in the UI using matplotlib embedded in tkinter
                # Use after() to delay display until UI layout is complete
                self.root.after(100, lambda: self._display_matplotlib_chart(chart_path))
                self._log_message(f"Band analysis chart generated: {chart_path}")
                self.status_var.set(f"Chart generated: {chart_path}")
            else:
                self._show_error("Failed to generate band analysis chart")

        except Exception as e:
            logger.error(f"Error generating band chart: {str(e)}")
            self._show_error(f"Failed to generate band analysis chart: {str(e)}")
            self.status_var.set("Chart generation failed")

    def _display_matplotlib_chart(self, chart_path):
        """Display a matplotlib chart in the tkinter canvas."""
        try:
            # Clear existing chart
            for widget in self.chart_container.winfo_children():
                widget.destroy()

            # Try to display the image using PIL
            if PIL_AVAILABLE:
                from PIL import Image, ImageTk

                # Store chart path and load original image
                self.chart_image_path = chart_path
                self.chart_original_image = Image.open(chart_path)

                # Reset zoom and pan for new chart
                self.chart_zoom_level = 0.5
                self.chart_pan_x = 0
                self.chart_pan_y = 0
                self.zoom_level_var.set("50%")

                # Create a canvas with scrollbars for the chart
                v_scrollbar = ttk.Scrollbar(self.chart_container, orient='vertical')
                h_scrollbar = ttk.Scrollbar(self.chart_container, orient='horizontal')

                height = self.chart_container.winfo_height()
                if height <= 1:
                    height = 600  # Default height

                self.chart_canvas = Canvas(self.chart_container,
                                          yscrollcommand=v_scrollbar.set,
                                          xscrollcommand=h_scrollbar.set,
                                          height=height)

                v_scrollbar.config(command=self.chart_canvas.yview)
                h_scrollbar.config(command=self.chart_canvas.xview)

                # Bind mouse events for panning
                self.chart_canvas.bind('<Button-1>', self._on_chart_mouse_down)
                self.chart_canvas.bind('<B1-Motion>', self._on_chart_mouse_drag)
                self.chart_canvas.bind('<MouseWheel>', self._on_chart_mouse_wheel)
                self.chart_canvas.bind('<Button-4>', self._on_chart_mouse_wheel)  # Linux scroll up
                self.chart_canvas.bind('<Button-5>', self._on_chart_mouse_wheel)  # Linux scroll down

                # Pack scrollbars and canvas
                v_scrollbar.pack(side='right', fill='y')
                h_scrollbar.pack(side='bottom', fill='x')
                self.chart_canvas.pack(side='left', fill='both', expand=True)

                # Initial display
                self._update_chart_display()

            else:
                # Fallback: just show the file path
                path_label = ttk.Label(self.chart_container,
                                     text=f"Chart generated successfully:\n{chart_path}\n\nPIL not available for display",
                                     font=('Arial', 10))
                path_label.pack(pady=20)

        except Exception as e:
            logger.error(f"Error displaying chart: {str(e)}")
            # Fallback: show file path
            try:
                fallback_label = ttk.Label(self.chart_container,
                                         text=f"Chart generated but display failed:\n{chart_path}\nError: {str(e)}")
                fallback_label.pack(pady=20)
            except Exception:
                pass  # Can't even show error

    def _export_band_chart(self):
        """Export the current band analysis chart."""
        try:
            from tkinter import filedialog
            import os

            # Ask user for export location and format
            file_types = [
                ("PNG files", "*.png"),
                ("PDF files", "*.pdf"),
                ("SVG files", "*.svg"),
                ("All files", "*.*")
            ]

            export_path = filedialog.asksaveasfilename(
                title="Export Band Analysis Chart",
                defaultextension=".png",
                filetypes=file_types
            )

            if not export_path:
                return  # User cancelled

            # Get the current chart file path (assuming default location)
            current_chart = "band_analysis.png"
            if not os.path.exists(current_chart):
                self._show_error("No chart available to export. Generate a chart first.")
                return

            # Copy the file to the desired location
            import shutil
            shutil.copy2(current_chart, export_path)

            self._log_message(f"Band chart exported to: {export_path}")
            self.status_var.set(f"Chart exported: {export_path}")

            messagebox.showinfo("Export Complete", f"Band analysis chart exported successfully to:\n{export_path}")

        except Exception as e:
            logger.error(f"Error exporting band chart: {str(e)}")
            self._show_error(f"Failed to export chart: {str(e)}")

    def _clear_chart_display(self):
        """Clear the chart display area."""
        try:
            # Clear existing chart content
            for widget in self.chart_container.winfo_children():
                widget.destroy()

            # Show placeholder message
            placeholder_label = ttk.Label(
                self.chart_container,
                text="No current design available.\n\nGenerate a design to automatically see its band analysis chart here,\nor click 'Generate Band Analysis Chart' to view analysis of all frequency bands.",
                font=('Arial', 10),
                justify='center'
            )
            placeholder_label.pack(expand=True, pady=50)

        except Exception as e:
            logger.error(f"Error clearing chart display: {str(e)}")

    def _chart_zoom_in(self):
        """Zoom in on the chart."""
        if self.chart_zoom_level < 5.0:  # Maximum zoom 500%
            self.chart_zoom_level *= 1.2
            self._update_chart_display()
            self.zoom_level_var.set(f"{self.chart_zoom_level*100:.0f}%")

    def _chart_zoom_out(self):
        """Zoom out on the chart."""
        if self.chart_zoom_level > 0.2:  # Minimum zoom 20%
            self.chart_zoom_level /= 1.2
            self._update_chart_display()
            self.zoom_level_var.set(f"{self.chart_zoom_level*100:.0f}%")

    def _chart_fit_to_view(self):
        """Fit the chart to the view by resetting zoom and pan."""
        self.chart_zoom_level = 1.0
        self.chart_pan_x = 0
        self.chart_pan_y = 0
        self._update_chart_display()
        self.zoom_level_var.set(f"{self.chart_zoom_level*100:.0f}%")

    def _generate_ascii_band_analysis(self):
        """Generate ASCII-based band analysis charts."""
        try:
            if not self.current_results:
                self._show_error("No design generated yet. Create a design first.")
                return

            # Extract current design data
            freq1 = self.current_results.get('freq1_mhz', 0)
            freq2 = self.current_results.get('freq2_mhz', 0)
            freq3 = self.current_results.get('freq3_mhz', 0)
            vswr1 = self.current_results.get('vswr1', 0)
            vswr2 = self.current_results.get('vswr2', 0)
            vswr3 = self.current_results.get('vswr3', 0)
            total_length = self.current_results.get('total_trace_length_mm', 0)
            segment_count = self.current_results.get('segment_count', 0)

            # Generate ASCII visualization
            ascii_output = self._create_ascii_charts(freq1, freq2, freq3, vswr1, vswr2, vswr3, total_length, segment_count)

            # Display in text widget
            self.ascii_analysis_text.config(state='normal')
            self.ascii_analysis_text.delete('1.0', 'end')
            self.ascii_analysis_text.insert('1.0', ascii_output)
            self.ascii_analysis_text.config(state='disabled')

            self._log_message("ASCII band analysis generated successfully")
            self.status_var.set("Band analysis generated")

        except Exception as e:
            logger.error(f"Error generating ASCII analysis: {str(e)}")
            self._show_error(f"Error generating analysis: {str(e)}")

    def _create_ascii_charts(self, freq1, freq2, freq3, vswr1, vswr2, vswr3, total_length, segment_count):
        """Create ASCII charts for band analysis."""
        # Header
        output = "╔═══════════════════════════════════════════════════════════════════════════╗\n"
        output += "║                    BAND ANALYSIS - ASCII VISUALIZATION                     ║\n"
        output += "╚═══════════════════════════════════════════════════════════════════════════╝\n\n"

        # Frequency and VSWR table
        output += "┌─────────────────────────────────────────────────────────────────────────┐\n"
        output += "│ FREQUENCY BANDS & VSWR ANALYSIS                                          │\n"
        output += "├─────────────────────────────────────────────────────────────────────────┤\n"
        output += f"│ Band 1: {freq1:8.2f} MHz  →  VSWR: {vswr1:5.2f}  "
        output += self._vswr_bar(vswr1) + " │\n"
        if freq2 > 0:
            output += f"│ Band 2: {freq2:8.2f} MHz  →  VSWR: {vswr2:5.2f}  "
            output += self._vswr_bar(vswr2) + " │\n"
        if freq3 > 0:
            output += f"│ Band 3: {freq3:8.2f} MHz  →  VSWR: {vswr3:5.2f}  "
            output += self._vswr_bar(vswr3) + " │\n"
        output += "└─────────────────────────────────────────────────────────────────────────┘\n\n"

        # VSWR bar chart
        output += "VSWR Performance (Target: < 2.0 = Excellent, < 3.0 = Good)\n"
        output += "────────────────────────────────────────────────────────────────────────────\n"
        max_vswr = max(vswr1, vswr2 if freq2 > 0 else 0, vswr3 if freq3 > 0 else 0)
        scale = 50 / max(max_vswr, 3.0)  # Scale to 50 chars max

        output += f"Band 1 ({freq1:.1f}MHz): "
        output += "█" * int(vswr1 * scale)
        output += f" {vswr1:.2f}\n"

        if freq2 > 0:
            output += f"Band 2 ({freq2:.1f}MHz): "
            output += "█" * int(vswr2 * scale)
            output += f" {vswr2:.2f}\n"

        if freq3 > 0:
            output += f"Band 3 ({freq3:.1f}MHz): "
            output += "█" * int(vswr3 * scale)
            output += f" {vswr3:.2f}\n"

        output += "────────────────────────────────────────────────────────────────────────────\n"
        output += "Reference: | 1.0   | 1.5   | 2.0   | 2.5   | 3.0   |\n"
        output += "           └───────┴───────┴───────┴───────┴───────┘\n\n"

        # Trace length information
        output += "┌─────────────────────────────────────────────────────────────────────────┐\n"
        output += "│ TRACE LENGTH ANALYSIS                                                    │\n"
        output += "├─────────────────────────────────────────────────────────────────────────┤\n"
        output += f"│ Total Trace Length:    {total_length:8.2f} mm  ({total_length/25.4:6.3f} in)       │\n"
        output += f"│ Number of Segments:    {segment_count:8d}                                 │\n"
        if segment_count > 0:
            avg_length = total_length / segment_count
            output += f"│ Average Segment:       {avg_length:8.2f} mm  ({avg_length/25.4:6.3f} in)       │\n"
        output += "└─────────────────────────────────────────────────────────────────────────┘\n\n"

        # Wavelength comparison
        if freq1 > 0:
            wavelength1 = 299.792458 / freq1  # meters
            wavelength1_mm = wavelength1 * 1000
            ratio1 = total_length / wavelength1_mm

            output += "┌─────────────────────────────────────────────────────────────────────────┐\n"
            output += "│ WAVELENGTH COMPARISON                                                    │\n"
            output += "├─────────────────────────────────────────────────────────────────────────┤\n"
            output += f"│ Band 1 ({freq1:.1f} MHz):                                                  │\n"
            output += f"│   Wavelength (λ):       {wavelength1_mm:8.2f} mm                          │\n"
            output += f"│   Trace / Wavelength:   {ratio1:8.3f} λ                                │\n"
            output += f"│   Resonance:            {self._get_resonance_type(ratio1):25s}            │\n"

            if freq2 > 0:
                wavelength2 = 299.792458 / freq2
                wavelength2_mm = wavelength2 * 1000
                ratio2 = total_length / wavelength2_mm
                output += f"│ Band 2 ({freq2:.1f} MHz):                                                  │\n"
                output += f"│   Wavelength (λ):       {wavelength2_mm:8.2f} mm                          │\n"
                output += f"│   Trace / Wavelength:   {ratio2:8.3f} λ                                │\n"
                output += f"│   Resonance:            {self._get_resonance_type(ratio2):25s}            │\n"

            if freq3 > 0:
                wavelength3 = 299.792458 / freq3
                wavelength3_mm = wavelength3 * 1000
                ratio3 = total_length / wavelength3_mm
                output += f"│ Band 3 ({freq3:.1f} MHz):                                                  │\n"
                output += f"│   Wavelength (λ):       {wavelength3_mm:8.2f} mm                          │\n"
                output += f"│   Trace / Wavelength:   {ratio3:8.3f} λ                                │\n"
                output += f"│   Resonance:            {self._get_resonance_type(ratio3):25s}            │\n"

            output += "└─────────────────────────────────────────────────────────────────────────┘\n\n"

        # Performance summary
        output += "PERFORMANCE SUMMARY\n"
        output += "────────────────────────────────────────────────────────────────────────────\n"
        excellent = sum(1 for v in [vswr1, vswr2, vswr3] if 0 < v < 2.0)
        good = sum(1 for v in [vswr1, vswr2, vswr3] if 2.0 <= v < 3.0)
        poor = sum(1 for v in [vswr1, vswr2, vswr3] if v >= 3.0)

        output += f"  Excellent (VSWR < 2.0): {excellent} band(s)\n"
        output += f"  Good (2.0 ≤ VSWR < 3.0): {good} band(s)\n"
        output += f"  Poor (VSWR ≥ 3.0):       {poor} band(s)\n\n"

        if excellent >= 2:
            output += "  ✓ Overall Rating: EXCELLENT - Design meets performance targets\n"
        elif excellent + good >= 2:
            output += "  ✓ Overall Rating: GOOD - Design is functional with acceptable VSWR\n"
        else:
            output += "  ⚠ Overall Rating: NEEDS IMPROVEMENT - Consider redesign or optimization\n"

        return output

    def _vswr_bar(self, vswr):
        """Create a visual VSWR indicator bar."""
        if vswr < 1.5:
            return "[████████████████] Excellent"
        elif vswr < 2.0:
            return "[████████████    ] Very Good"
        elif vswr < 2.5:
            return "[████████        ] Good     "
        elif vswr < 3.0:
            return "[████            ] Fair     "
        else:
            return "[█               ] Poor     "

    def _get_resonance_type(self, ratio):
        """Get resonance type based on trace/wavelength ratio."""
        if 0.23 <= ratio <= 0.27:
            return "Quarter-wave (λ/4)"
        elif 0.48 <= ratio <= 0.52:
            return "Half-wave (λ/2)"
        elif 0.73 <= ratio <= 0.77:
            return "Three-quarter (3λ/4)"
        elif 0.98 <= ratio <= 1.02:
            return "Full-wave (λ)"
        else:
            return "Non-resonant"

    def _export_ascii_analysis(self):
        """Export ASCII analysis to a text file."""
        try:
            from tkinter import filedialog
            from datetime import datetime

            # Get current text
            ascii_text = self.ascii_analysis_text.get('1.0', 'end')

            if "Click \"Generate ASCII Analysis\"" in ascii_text:
                self._show_error("No analysis to export. Generate analysis first.")
                return

            # Ask for save location
            file_path = filedialog.asksaveasfilename(
                title="Export ASCII Analysis",
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"band_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )

            if not file_path:
                return

            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(ascii_text)

            self._log_message(f"ASCII analysis exported to: {file_path}")
            self.status_var.set(f"Analysis exported to {os.path.basename(file_path)}")

        except Exception as e:
            logger.error(f"Error exporting ASCII analysis: {str(e)}")
            self._show_error(f"Error exporting analysis: {str(e)}")

    def _update_chart_display(self):
        """Update the chart display with current zoom and pan settings."""
        if not self.chart_image_path or not os.path.exists(self.chart_image_path):
            return

        try:
            if not PIL_AVAILABLE:
                return

            from PIL import Image, ImageTk

            # Load the original image
            if not self.chart_original_image:
                self.chart_original_image = Image.open(self.chart_image_path)

            # Apply zoom
            zoomed_width = int(self.chart_original_image.width * self.chart_zoom_level)
            zoomed_height = int(self.chart_original_image.height * self.chart_zoom_level)

            if zoomed_width <= 0 or zoomed_height <= 0:
                return

            zoomed_image = self.chart_original_image.resize((zoomed_width, zoomed_height), Image.LANCZOS)

            # Apply pan (crop the image to show only the visible portion)
            container_width = self.chart_container.winfo_width()
            container_height = self.chart_container.winfo_height()

            if container_width <= 0 or container_height <= 0:
                container_width, container_height = 800, 600  # Default fallback

            # Calculate visible region
            left = max(0, self.chart_pan_x)
            top = max(0, self.chart_pan_y)
            right = min(zoomed_width, left + container_width)
            bottom = min(zoomed_height, top + container_height)

            # Create cropped image
            if right > left and bottom > top:
                cropped_image = zoomed_image.crop((left, top, right, bottom))

                # Convert to PhotoImage
                photo = ImageTk.PhotoImage(cropped_image)

                # Clear existing canvas content
                if hasattr(self, 'chart_canvas') and self.chart_canvas:
                    self.chart_canvas.delete("all")

                    # Update canvas
                    self.chart_canvas.config(
                        scrollregion=(0, 0, zoomed_width, zoomed_height),
                        width=min(container_width, zoomed_width),
                        height=min(container_height, zoomed_height)
                    )

                    # Redraw image
                    self.chart_canvas.create_image(0, 0, anchor='nw', image=photo)

                    # Store reference
                    self.chart_canvas.image = photo
                    self.chart_current_photo = photo

        except Exception as e:
            logger.error(f"Error updating chart display: {str(e)}")

    def _on_chart_mouse_down(self, event):
        """Handle mouse button down for panning."""
        self.chart_drag_start_x = event.x_root
        self.chart_drag_start_y = event.y_root
        self.chart_pan_start_x = self.chart_pan_x
        self.chart_pan_start_y = self.chart_pan_y

    def _on_chart_mouse_drag(self, event):
        """Handle mouse drag for panning."""
        dx = event.x_root - self.chart_drag_start_x
        dy = event.y_root - self.chart_drag_start_y

        # Apply panning (invert direction for natural feel)
        self.chart_pan_x = self.chart_pan_start_x - dx
        self.chart_pan_y = self.chart_pan_start_y - dy

        # Clamp pan to valid range
        max_pan_x = max(0, int(self.chart_original_image.width * self.chart_zoom_level - self.chart_container.winfo_width()))
        max_pan_y = max(0, int(self.chart_original_image.height * self.chart_zoom_level - self.chart_container.winfo_height()))
        self.chart_pan_x = max(0, min(self.chart_pan_x, max_pan_x))
        self.chart_pan_y = max(0, min(self.chart_pan_y, max_pan_y))

        self._update_chart_display()

    def _on_chart_mouse_wheel(self, event):
        """Handle mouse wheel for zooming."""
        # Get delta for cross-platform compatibility
        if event.num == 4 or event.delta > 0:  # Scroll up
            self._chart_zoom_in()
        elif event.num == 5 or event.delta < 0:  # Scroll down
            self._chart_zoom_out()

    def _on_analysis_type_changed(self, event=None):
        """Handle analysis type dropdown change."""
        analysis_type = self.analysis_type_var.get()
        if analysis_type == "detailed":
            self._log_message("Switched to detailed band analysis mode")
        else:
            self._log_message("Switched to comparison band analysis mode")

    def _designs_zoom_in(self):
        """Zoom in on the design thumbnail."""
        if self.designs_zoom_level < 10.0:  # Maximum zoom 1000%
            self.designs_zoom_level *= 1.3  # Increased step for faster zooming
            self._update_design_thumbnail_display()
            logger.info(f"Zoom in: {self.designs_zoom_level:.1f}x")

    def _designs_zoom_out(self):
        """Zoom out on the design thumbnail."""
        if self.designs_zoom_level > 0.3:  # Minimum zoom 30%
            self.designs_zoom_level /= 1.3
            self._update_design_thumbnail_display()
            logger.info(f"Zoom out: {self.designs_zoom_level:.1f}x")

    def _designs_fit_to_view(self):
        """Fit the design thumbnail to view by resetting zoom."""
        self.designs_zoom_level = 2.5  # Reset to default 250%
        self._update_design_thumbnail_display()
        logger.info(f"Fit to view: {self.designs_zoom_level:.1f}x")

    def _update_design_thumbnail_display(self):
        """Update the design thumbnail display with current zoom level."""
        try:
            # Only re-render if we have SVG data stored
            if self.current_design_svg_data:
                # Re-render the SVG with the new zoom level
                photo_image = self._render_svg_thumbnail(self.current_design_svg_data)
                if photo_image:
                    self.thumbnail_label.config(image=photo_image, text="")
                    self.thumbnail_label.image = photo_image  # Keep a reference

                    # Update canvas scroll region to match image size
                    self.thumbnail_canvas.config(scrollregion=self.thumbnail_canvas.bbox("all"))

                    # Center the image if it's smaller than the canvas
                    self.thumbnail_canvas.update_idletasks()
                    canvas_width = self.thumbnail_canvas.winfo_width()
                    canvas_height = self.thumbnail_canvas.winfo_height()
                    img_width = photo_image.width()
                    img_height = photo_image.height()

                    # Calculate position to center if image is smaller
                    x_pos = max(0, (canvas_width - img_width) // 2)
                    y_pos = max(0, (canvas_height - img_height) // 2)

                    self.thumbnail_canvas.coords(self.thumbnail_canvas_window, x_pos, y_pos)
                    self.thumbnail_canvas.config(scrollregion=(0, 0, max(canvas_width, img_width), max(canvas_height, img_height)))

                    # Update zoom level display
                    if hasattr(self, 'zoom_level_label'):
                        self.zoom_level_label.config(text=f"Zoom: {int(self.designs_zoom_level * 100)}%")

                    logger.info(f"Thumbnail updated with zoom: {self.designs_zoom_level:.1f}x ({img_width}x{img_height})")
            else:
                logger.warning("No SVG data available to re-render")
        except Exception as e:
            logger.error(f"Error updating thumbnail display: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())

    def _prompt_auto_save_current_design(self):
        """Prompt user to save the current design when visiting My Designs tab."""
        if not self.current_geometry or not self.current_results:
            return

        # Create the auto-save dialog
        save_prompt = Toplevel(self.root)
        save_prompt.title("Save Current Design")
        save_prompt.geometry("500x250")
        save_prompt.resizable(False, False)
        save_prompt.transient(self.root)
        save_prompt.grab_set()
        save_prompt.focus_force()  # Ensure dialog gets focus

        # Center the dialog
        save_prompt.geometry("+{}+{}".format(
            self.root.winfo_x() + self.root.winfo_width()//2 - 250,
            self.root.winfo_y() + self.root.winfo_height()//2 - 125
        ))

        # Content
        ttk.Label(save_prompt, text="Save Current Design to Library?",
                 font=('Segoe UI', 12, 'bold')).pack(pady=(15, 5))

        # Show current design info
        try:
            design_info = f"Design: {self.current_results.get('design_type', 'Unknown')} - {self.current_results.get('band_name', 'Unknown')}\n"
            design_info += f"Frequencies: {self.current_results.get('freq1_mhz', 'N/A')}/{self.current_results.get('freq2_mhz', 'N/A')}/{self.current_results.get('freq3_mhz', 'N/A')} MHz"

            info_label = ttk.Label(save_prompt, text=design_info,
                                  font=('Segoe UI', 9))
            info_label.pack(pady=(0, 10))
        except:
            pass

        # Auto-generated filename suggestion
        from datetime import datetime
        today_date = datetime.now().strftime("%Y%m%d")
        random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
        default_filename = f"antenna_{today_date}_{random_suffix}"

        ttk.Label(save_prompt, text="Suggested filename will be auto-generated.",
                 font=('Segoe UI', 9)).pack(pady=(0, 15))

        # Buttons frame
        button_frame = ttk.Frame(save_prompt)
        button_frame.pack(fill='x', pady=(0, 15), padx=20)

        def save_design():
            """Save the current design and close the prompt."""
            try:
                # Use today's date and random suffix for automatic filename
                from datetime import datetime
                today_date = datetime.now().strftime("%Y%m%d")
                random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
                default_filename = f"antenna_{today_date}_{random_suffix}"

                # Generate automatic design name
                default_design_name = f"Auto-saved Design - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

                # Create metadata
                metadata = DesignMetadata(
                    name=default_design_name,
                    substrate_width=float(self.substrate_width_var.get()),
                    substrate_height=float(self.substrate_height_var.get()),
                    trace_width_mil=float(self.trace_width_var.get())
                )

                # Save design
                saved_path = self.design_storage.save_design(
                    self.current_geometry, metadata, self.current_results
                )

                self._log_message(f"Auto-saved design: {default_design_name}")
                self.status_var.set(f"Design auto-saved as: {default_design_name}")
                self._refresh_designs_list()
                save_prompt.destroy()

            except Exception as e:
                self._show_error(f"Failed to save design: {str(e)}")
                save_prompt.destroy()

        def skip_saving():
            """Skip saving and close the prompt."""
            self._log_message("Auto-save prompt dismissed - continuing to My Designs")
            save_prompt.destroy()

        # Create buttons with proper spacing
        save_button = ttk.Button(button_frame, text="Save to Library", command=save_design)
        save_button.pack(side='left', expand=True, padx=5)

        skip_button = ttk.Button(button_frame, text="Skip for Now", command=skip_saving)
        skip_button.pack(side='right', expand=True, padx=5)

        # Bind Enter to save by default
        save_prompt.bind('<Return>', lambda e: save_design())
        save_prompt.bind('<Escape>', lambda e: skip_saving())

        # Instruction text
        ttk.Label(save_prompt, text="Tip: You can always save designs manually from the toolbar above",
                 font=('Segoe UI', 8), foreground='#666666').pack(pady=(0, 10))


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
