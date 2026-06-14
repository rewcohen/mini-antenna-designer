"""Antenna selection wizard.

Walks a user from "what do you want to do" to a buildable antenna spec:

    1. Pick a service (WiFi, GPS, 433 MHz remote, ham 2 m, ...).
    2. Say whether they transmit, receive, or both.
    3. The wizard works out the frequency, then which designs are physically
       possible on the chosen substrate (meander if it radiates well enough,
       otherwise hand-built copper-wire designs).
    4. The user picks an option and the wizard emits a complete build spec.

This module is pure logic (no GUI) so it can be driven by the desktop dialog or
tested directly.
"""
from typing import Dict, List, Optional

from loguru import logger

from presets import FrequencyBand, BandType
from design_generator import AntennaDesignGenerator
from core import NEC2Interface, compute_feed_requirements
from wire_antennas import assess_meander_feasibility, recommend_alternatives, wavelength_in


# Transmit/receive modes and the matching minimum efficiency for a meander to be
# offered. Receive tolerates a small, inefficient antenna; transmit does not.
MODES = {
    'rx': {'label': 'Receive only', 'min_efficiency': 0.02},
    'tx': {'label': 'Transmit only', 'min_efficiency': 0.15},
    'both': {'label': 'Transmit and receive', 'min_efficiency': 0.15},
}


# Service catalog: what people actually build antennas for. freqs in MHz.
# 'mode' is the typical default; the user can still override.
SERVICES: Dict[str, Dict] = {
    'wifi_24':   {'name': 'Wi-Fi / Bluetooth 2.4 GHz', 'freqs': [2442], 'mode': 'both',
                  'notes': '2.4 GHz ISM - Wi-Fi b/g/n, Bluetooth, Zigbee, many IoT radios.'},
    'wifi_5':    {'name': 'Wi-Fi 5 GHz', 'freqs': [5500], 'mode': 'both',
                  'notes': '5 GHz Wi-Fi a/n/ac.'},
    'lora_915':  {'name': 'LoRa / ISM 915 MHz (US)', 'freqs': [915], 'mode': 'both',
                  'notes': 'US 902-928 ISM: LoRa, Meshtastic, RFID, remotes.'},
    'lora_868':  {'name': 'LoRa / ISM 868 MHz (EU)', 'freqs': [868], 'mode': 'both',
                  'notes': 'EU 863-870 ISM: LoRa, smart meters.'},
    'ism_433':   {'name': 'ISM 433 MHz remotes', 'freqs': [433.92], 'mode': 'both',
                  'notes': 'Garage doors, key fobs, weather stations (EU/worldwide ISM).'},
    'ism_315':   {'name': 'ISM 315 MHz remotes (US)', 'freqs': [315], 'mode': 'both',
                  'notes': 'US car key fobs, TPMS, remotes.'},
    'gps':       {'name': 'GPS / GNSS (L1)', 'freqs': [1575.42], 'mode': 'rx',
                  'notes': 'Satellite navigation, receive only.'},
    'ads_b':     {'name': 'ADS-B aircraft 1090 MHz', 'freqs': [1090], 'mode': 'rx',
                  'notes': 'Track aircraft, receive only.'},
    'noaa':      {'name': 'NOAA weather satellite 137 MHz', 'freqs': [137.5], 'mode': 'rx',
                  'notes': 'APT weather imagery, receive only.'},
    'ais':       {'name': 'Marine AIS 162 MHz', 'freqs': [162], 'mode': 'rx',
                  'notes': 'Ship tracking, receive only.'},
    'fm_rx':     {'name': 'FM broadcast radio', 'freqs': [98], 'mode': 'rx',
                  'notes': '88-108 MHz FM, receive only.'},
    'airband':   {'name': 'Airband (VHF aircraft)', 'freqs': [128], 'mode': 'rx',
                  'notes': '118-137 MHz AM aviation voice, receive.'},
    'ham_2m':    {'name': 'Ham 2 m (144-148 MHz)', 'freqs': [146], 'mode': 'both',
                  'notes': 'Amateur VHF - licence required to transmit.'},
    'ham_70cm':  {'name': 'Ham 70 cm (430-440 MHz)', 'freqs': [435], 'mode': 'both',
                  'notes': 'Amateur UHF - licence required to transmit.'},
    'ham_6m':    {'name': 'Ham 6 m (50-54 MHz)', 'freqs': [52], 'mode': 'both',
                  'notes': 'Amateur low-VHF - large antenna.'},
    'ham_10m':   {'name': 'Ham 10 m (28-29.7 MHz)', 'freqs': [28.5], 'mode': 'both',
                  'notes': 'Amateur HF - large antenna.'},
    'ham_20m':   {'name': 'Ham 20 m (14 MHz)', 'freqs': [14.2], 'mode': 'both',
                  'notes': 'Amateur HF - very large antenna.'},
}


class AntennaWizard:
    """Step-through helper that ends in a buildable antenna spec."""

    def __init__(self, substrate_width_in: float = 4.0, substrate_height_in: float = 2.0):
        self.substrate_width = substrate_width_in
        self.substrate_height = substrate_height_in
        self.generator = AntennaDesignGenerator(NEC2Interface())

    # --- Step 1/2: catalog -------------------------------------------------
    def list_services(self) -> List[Dict]:
        """Services for the user to choose from (with default mode)."""
        return [{'key': k, **v} for k, v in SERVICES.items()]

    def list_modes(self) -> List[Dict]:
        return [{'key': k, 'label': v['label']} for k, v in MODES.items()]

    # --- Step 3/4: what designs are possible -------------------------------
    def get_design_options(self, service_key: str, mode: str) -> Dict:
        """Return the design options that are physically possible for this choice.

        Always includes copper-wire designs (they work at any frequency). Includes
        the planar meander only when it radiates well enough for the chosen mode on
        this substrate.
        """
        service = SERVICES.get(service_key)
        if not service:
            raise ValueError(f"Unknown service '{service_key}'")
        if mode not in MODES:
            mode = service.get('mode', 'both')

        freqs = service['freqs']
        primary = freqs[0]
        min_eff = MODES[mode]['min_efficiency']

        options: List[Dict] = []

        # Build the meander once to test feasibility.
        band = self._make_band(service, freqs)
        design = self.generator.generate_design(band)
        feasibility = design.get('feasibility', [])
        meander_ok = bool(feasibility) and all(b.get('feasible', False) or
                                               b.get('efficiency_pct', 0) >= min_eff * 100
                                               for b in feasibility)
        # Re-evaluate strictly against the mode threshold.
        resonators = getattr(self.generator.advanced_meander, 'last_resonators', [])
        mode_feas = assess_meander_feasibility(resonators, self.substrate_width,
                                               self.substrate_height, min_efficiency=min_eff)
        meander_ok = bool(mode_feas) and all(b['feasible'] for b in mode_feas)

        if meander_ok:
            eff = min((b['efficiency_pct'] for b in mode_feas), default=0)
            options.append({
                'kind': 'meander',
                'name': 'Planar meander (laser-etched on copper)',
                'feasible': True,
                'summary': f"Fits the {self.substrate_width:.0f}x{self.substrate_height:.0f} in board; "
                           f"est. efficiency >= {eff:.0f}%. Etch and weed the copper.",
                'design': design,
            })
        else:
            why = '; '.join(b['reason'] for b in mode_feas if not b['feasible']) or \
                  'not efficient enough on this board for this mode'
            options.append({
                'kind': 'meander',
                'name': 'Planar meander (laser-etched on copper)',
                'feasible': False,
                'summary': f"Not recommended: {why}.",
                'design': design,
            })

        # Copper-wire designs - always buildable, sized to the band.
        for alt in recommend_alternatives(primary):
            options.append({
                'kind': 'wire',
                'name': alt['name'],
                'feasible': True,
                'summary': alt['notes'],
                'design': alt,
            })

        return {
            'service': service,
            'service_key': service_key,
            'mode': mode,
            'mode_label': MODES[mode]['label'],
            'frequencies_mhz': freqs,
            'wavelength_in': round(wavelength_in(primary), 1),
            'meander_feasible': meander_ok,
            'options': options,
        }

    # --- Step 5/6: final spec ---------------------------------------------
    def build_spec(self, service_key: str, mode: str, option_index: int) -> Dict:
        """Produce the complete build spec for the chosen option."""
        ctx = self.get_design_options(service_key, mode)
        options = ctx['options']
        if not (0 <= option_index < len(options)):
            raise ValueError(f"Option index {option_index} out of range")
        choice = options[option_index]

        header = {
            'service': ctx['service']['name'],
            'mode': ctx['mode_label'],
            'frequencies_mhz': ctx['frequencies_mhz'],
            'antenna': choice['name'],
            'kind': choice['kind'],
        }

        if choice['kind'] == 'meander':
            design = choice['design']
            spec_text = self._format_meander_spec(header, design, ctx)
            return {**header, 'spec_text': spec_text, 'design': design,
                    'connection_points': design.get('connection_points', []),
                    'feed_advice': design.get('feed_advice', []),
                    'geometry': design.get('geometry', '')}
        else:
            spec_text = self._format_wire_spec(header, choice['design'])
            return {**header, 'spec_text': spec_text, 'wire_design': choice['design']}

    # --- helpers -----------------------------------------------------------
    def _make_band(self, service: Dict, freqs: List[float]) -> FrequencyBand:
        f = list(freqs) + [0, 0, 0]
        return FrequencyBand(
            name=service['name'], band_type=BandType.CUSTOM,
            frequencies_mhz=(f[0], f[1], f[2]),
            description=service.get('notes', ''), applications=[])

    def _format_meander_spec(self, header: Dict, design: Dict, ctx: Dict) -> str:
        lines = [
            "ANTENNA BUILD SPEC",
            "=" * 50,
            f"Service:     {header['service']}",
            f"Mode:        {header['mode']}",
            f"Frequency:   {', '.join(f'{f:.1f} MHz' for f in header['frequencies_mhz'])}",
            f"Antenna:     {header['antenna']}",
            f"Substrate:   {self.substrate_width:.0f} x {self.substrate_height:.0f} in copper-clad",
            "",
            "HOW TO MAKE IT",
            "  1. Export the SVG and laser the outline onto the copper.",
            "  2. Weed (remove) all copper that is NOT a trace or solder pad.",
            "  3. Solder the feed at the labelled pad(s) below.",
            "",
            "CONNECTION POINTS (solder pads)",
        ]
        for cp in design.get('connection_points', []):
            lines.append(f"  {cp['label']} @ {cp['freq_mhz']:.0f} MHz: "
                         f"({cp['x_mm']:.1f}, {cp['y_mm']:.1f}) mm from board centre")
        lines.append("")
        lines.append("FEED / IMPEDANCE / BALUN")
        for a in design.get('feed_advice', []):
            lines.append(f"  {a['label']}: feed Z ~= {a['feed_impedance_str']}")
            lines.append(f"     {a['matching_advice']}")
            lines.append(f"     {a['balun_advice']}")
        return "\n".join(lines)

    def _format_wire_spec(self, header: Dict, alt: Dict) -> str:
        lines = [
            "ANTENNA BUILD SPEC",
            "=" * 50,
            f"Service:     {header['service']}",
            f"Mode:        {header['mode']}",
            f"Frequency:   {', '.join(f'{f:.1f} MHz' for f in header['frequencies_mhz'])}",
            f"Antenna:     {header['antenna']}  (hand-built from copper wire)",
            "",
            "DIMENSIONS",
        ]
        for k, v in alt.get('dimensions', {}).items():
            lines.append(f"  {k}: {v}")
        lines += [
            "",
            f"FEED IMPEDANCE:  {alt.get('feed_impedance', 'see notes')}",
            f"BALUN / MATCH:   {alt.get('balun', 'see notes')}",
            "",
            "NOTES",
            f"  {alt.get('notes', '')}",
            "",
            "HOW TO MAKE IT",
            "  1. Cut copper wire to the dimensions above (add a little for trimming).",
            "  2. Form the shape and mount clear of metal objects.",
            "  3. Connect coax at the feed; add the balun/match as noted.",
            "  4. Trim for lowest SWR at the operating frequency.",
        ]
        return "\n".join(lines)
