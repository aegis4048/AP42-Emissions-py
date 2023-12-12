import numpy as np
import pandas as pd
from fuzzywuzzy import process
from itertools import combinations

import constants


GEO_DATA = pd.read_pickle("Table 7-1-7 Meteorological data for selected US locations.pkl")
PAINT_DATA = pd.read_pickle("Table 7-1-6 Paint solar absortance.pkl")
R = constants.R
STATE_DICT = constants.state_dict
TIMEFRAMES = constants.timeframes


class Tank(object):

    def __init__(self, H, D, loc, 
                 Rrd=1,
                 Sr=0.0625,
                 Fl=0.5,
                 tg='vertical cylinder',
                 rt='cone',
                 sc='white',
                 spc='average',
                 rc=None,
                 rpc=None,
                 timeframe=None,
                 ):

        self._validate_Fl(Fl)
        self.tg = self._validate_tg(tg)  # tank geometry
        self.rt = self._validate_rt(rt)  # roof type

        self.H = H  # tank shell height, ft
        self.D = D  # tank shell diameter, ft

        # Set rc and rpc to sc and spc if sc and spc are provided
        if sc is not None:
            rc = sc if rc is None else rc
        if spc is not None:
            rpc = spc if rpc is None else rpc

        # Set sc and spc to rc and rpc if rc and rpc are provided
        if rc is not None:
            sc = rc if sc is None else sc
        if rpc is not None:
            spc = rpc if spc is None else spc

        # Set default values if none are provided
        if sc is None and rc is None:
            sc = rc = 'white'
        if spc is None and rpc is None:
            spc = rpc = 'average'

        spc = self._validate_pc(spc)  # shell paint condition
        rpc = self._validate_pc(rpc)  # roof paint condition
        sc = self._validate_c(sc)  # shell color
        rc = self._validate_c(rc)  # roof color

        # Store the final values in self
        self.sc = sc  # shell color, Table 7-1-6
        self.spc = spc  # shell paint condition, Table 7-1-6
        self.rc = rc  # roof color, Table 7-1-6
        self.rpc = rpc  # roof paint condition, Table 7-1-6

        self.Fl = Fl  # fraction fill of liquid. in a tank, assumed to be 50% by default  [not sure for horiz vs vert]
        self.Hl = self.H * self.Fl  # liquid height, ft, assumed to be 50% by default  [not sure for horiz vs vert]
        self.Rs = self.D / 2  # tank shell radius, ft [not sure which tg]

        self.loc_geodata = self._validate_location(loc)  # (dataframe) Table 7-1-7: Meteorological data for the select US location.
        if timeframe is None:
            self.timeframe = 'Annual'
        else:
            self.timeframe = self._validate_timeframe(timeframe)

        if tg == 'vertical cylinder':

            if rt == 'cone':
                self.Sr = Sr  # tank cone roof slope, ft/ft, default = 0.0625  [*confirmed]
                self.Hr = self.Sr * self.Rs  # tank roof height, ft, eq 1-18 [*confirmed]
                self.Hro = 1/3 * self.Hr  # roof outage (or shell height equivalent to the volume contained under the roof), ft, eq 1-17  [*confirmed]

            else:  # rt = 'dome'
                self.Rrd = Rrd # ratio between tank dome roof radius to tank shell diameter. Typically 0.8D ~ 1.2D
                self.Rr = self.Rrd * self.D  # radius of tank dome roof, ft.
                self.Hr = self.Rr - (self.Rr ** 2 - self.Rs ** 2) ** 0.5  # tank roof height, ft, eq 1-20
                self.Hro = self.Hr * (1/2 + 1/6 * (self.Hr / self.Rs) ** 2) # dome roof tank outage, ft, eq 1-19

            self.Hvo = self.H - self.Hl + self.Hro  # vapor space outage for vertical tank, ft, eq 1-16  [*confirmed]

        elif tg == 'horizontal cylinder':
            self.De = np.sqrt(self.H * self.D / (np.pi / 4))  # effective tank diameter for horiz. tank, ft, eq 1-14
            self.He = (np.pi / 4) * self.D  # effective tank height for horiz. tank, ft, eq 1-15
            self.Hvo = self.He / 2  # vapor space outage for horizontal tank, ft, eq 1-16

    def _validate_c(self, c):
        """Validate color or material type"""
        self._is_string(c)
        valid_options = {
            'white', 'specular aluminum', 'diffuse aluminum', 'beige/cream', 'black',
            'brown', 'light gray', 'medium gray', 'dark green', 'primer red',
            'red iron oxide rust', 'tan', 'unpainted aluminum'
        }
        if c.lower() not in {option.lower() for option in valid_options}:
            quoted_options = ', '.join(f"'{option}'" for option in valid_options)
            raise ValueError(f"Invalid input: '{c}'. Accepted options are: {quoted_options}.")

        return c.lower()

    def _validate_pc(self, pc):
        """Validate pc (property condition)"""
        self._is_string(pc)
        valid_conditions = {'new', 'average', 'aged'}
        if pc.lower() not in {condition.lower() for condition in valid_conditions}:
            quoted_conditions = ', '.join(f"'{condition}'" for condition in valid_conditions)
            raise ValueError(f"Invalid input: '{pc}'. Accepted property conditions are: {quoted_conditions}.")

        return pc.lower()

    def _validate_Fl(self, Fl):
        if not isinstance(Fl, (float, int)) or Fl <= 0 or Fl > 1:
            raise ValueError("Fl must be a number greater than 0 and equal to or smaller than 1")
        return Fl

    def _validate_tg(self, tg):
        """validate tank geometry"""
        self._is_string(tg)
        tank_types = {
            'vertical cylinder',
            'horizontal cylinder',
            'external floating roof tank',
            'internal floating roof tank',
            'domed floating roof tank',
        }
        if tg.lower() not in {type.lower() for type in tank_types}:
            quoted_types = ', '.join(f"'{type}'" for type in tank_types)
            raise ValueError(f"Invalid input: '{tg}'. Accepted tank types are: {quoted_types}.")

        return tg.lower()

    def _validate_rt(self, rt):
        """Validate roof type"""
        self._is_string(rt)
        roof_types = {'dome', 'cone'}
        if rt.lower() not in {type.lower() for type in roof_types}:
            quoted_types = ', '.join(f"'{type}'" for type in roof_types)
            raise ValueError(f"Invalid input: '{rt}'. Accepted roof types are: {quoted_types}.")

        return rt.lower()

    def _validate_location(self, loc):
        # Normalize the input location to uppercase
        input_normalized = loc.upper()

        # Initialize variables to store matched state info
        matched_state_abbr = None
        matched_state_name = None

        # Check if the normalized input is a state abbreviation
        if input_normalized in STATE_DICT:
            matched_state_abbr = input_normalized
            matched_state_name = STATE_DICT[input_normalized]

        # Generate combinations of input parts to match multi-word state names
        if not matched_state_name:
            input_parts = input_normalized.split()
            for i in range(1, len(input_parts) + 1):
                for combo in combinations(input_parts, i):
                    test_str = ' '.join(combo)
                    if test_str in STATE_DICT.values():
                        matched_state_name = test_str
                        matched_state_abbr = [abbr for abbr, name in STATE_DICT.items() if name == test_str][0]
                        break
                if matched_state_name:
                    break

        # Check if input is an exact match for any location
        if input_normalized in GEO_DATA['Location'].str.upper().tolist():
            loc = ' '.join(
                [s.capitalize() for s in loc.split(' ')[:-1]] + [loc.split(' ')[-1].upper()])

            location_GEODATA = GEO_DATA[GEO_DATA['Location'] == loc]
            return location_GEODATA

        elif matched_state_abbr:
            locations_in_state = GEO_DATA[GEO_DATA['State'].str.upper() == matched_state_abbr]['Location'].unique()
            if locations_in_state.size > 0:
                locations_list_str = ', '.join(f"'{location}'" for location in locations_in_state)
                raise TypeError(
                    f"State name/abbreviation '{loc}' -> '{matched_state_abbr}' detected. Full state name is '{matched_state_name}'. List of accepted location parameters for '{matched_state_name}': {locations_list_str}")
            else:
                raise TypeError(f"No data available for the state '{matched_state_name}'.")
        else:
            # Fuzzy matching to suggest the closest match
            locations = set(GEO_DATA['Location'].str.upper())
            closest_match, score = process.extractOne(input_normalized, locations)

            if score > 90:
                # Split the closest match into city and state, and format them correctly
                suggested_city, suggested_state = closest_match.rsplit(',', 1)
                suggested_city = suggested_city.strip().title()  # City in title case
                suggested_state = suggested_state.strip().upper()  # State in uppercase
                suggested_closest_match = f"{suggested_city}, {suggested_state}"
                raise TypeError(
                    f"Invalid location parameter: '{loc}'. Did you mean '{suggested_closest_match}'?")
            else:
                raise TypeError(
                    f"Invalid location parameter: '{loc}'. To view the list of available locations, run: Tank.get_locations_list()")

    def _validate_timeframe(self, tf_input):
        # Normalize the user input
        # Normalize the user input
        if isinstance(tf_input, str):
            normalized_input = tf_input.capitalize()
        elif isinstance(tf_input, int):
            if tf_input > 12:
                raise ValueError(
                    "Invalid input: The number exceeds 12. There are only 12 months in a year plus 0 for 'Annual'.")
            normalized_input = tf_input
        else:
            raise ValueError("Invalid input type")

        # Search for the corresponding timeframe
        for period in TIMEFRAMES:
            if normalized_input in period:
                return period[0]  # Return the true timeframe

        if isinstance(tf_input, str):
            raise ValueError(
                "Timeframe not found, check for a typo. Examples of accepted string inputs: 'Sep', 'September', 'Feb', 'February', 'Dec', 'December'.... Alternatively, pass integer inputs [0, 12]. Ex: 0='Annual', 1='Jan', 12='Dec'.")

        raise ValueError("Timeframe not found.")

    def _is_string(self, item):
        if not isinstance(item, str):
            raise TypeError("The arugment type must be a string")

    @staticmethod
    def get_locations_list():
        return list(set(GEO_DATA['Location']))


a = Tank(30, 15, loc='Evansville, IN', Rrd=1, Sr=0.0625, Fl=0.5, tg='vertical cylinder', rt='dome', rc='black',
         timeframe='Feb')
print(a.timeframe)
