import numpy as np
import pandas as pd
from fuzzywuzzy import process
from itertools import combinations
import utilities
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
                 rt=None,
                 insulation='uninsulated',
                 sc=None,
                 spc=None,
                 rc=None,
                 rpc=None,
                 timeframe='Annual',
                 Tb=None,
                 ):

        self._validate_Fl(Fl)
        self.tg = self._validate_tg(tg)  # tank geometry
        self.insulation = self._validate_insulation(insulation)  # tank insulation
        if rt is not None:
            self.rt = self._validate_rt(rt)  # roof type

        if rt == 'dome':
            if Sr != 0.0625:
                raise ValueError("Sr should not be provided when rt is 'dome'")
        else:  # rt = 'cone
            if Rrd != 1:
                raise ValueError("Rrd should not be provided when rt is 'cone'")

        self.Sr = Sr  # tank cone roof slope, ft/ft, default = 0.0625  [*confirmed]
        self.Rrd = Rrd  # ratio between tank dome roof radius to tank shell diameter. Typically 0.8D ~ 1.2D

        self.H = H  # tank shell height, ft
        self.D = D  # tank shell diameter, ft

        self.Fl = Fl  # fraction fill of liquid. in a tank, assumed to be 50% by default  [not sure for horiz vs vert]
        self.Hl = self.H * self.Fl  # liquid height, ft, assumed to be 50% by default  [not sure for horiz vs vert]
        self.Rs = self.D / 2  # tank shell radius, ft [not sure which tg]

        if tg == 'vertical cylinder':

            if rt == 'cone':
                self.Hr = self.Sr * self.Rs  # tank roof height, ft, eq 1-18 [*confirmed]
                self.Hro = 1/3 * self.Hr  # roof outage (or shell height equivalent to the volume contained under the roof), ft, eq 1-17  [*confirmed]

            else:  # rt = 'dome'
                self.Rr = self.Rrd * self.D  # radius of tank dome roof, ft.
                self.Hr = self.Rr - (self.Rr ** 2 - self.Rs ** 2) ** 0.5  # tank roof height, ft, eq 1-20
                self.Hro = self.Hr * (1/2 + 1/6 * (self.Hr / self.Rs) ** 2)  # dome roof tank outage, ft, eq 1-19

            self.Hvo = self.H - self.Hl + self.Hro  # vapor space outage for vertical tank, ft, eq 1-16  [*confirmed]

        elif tg == 'horizontal cylinder':
            if rt is not None:
                raise ValueError("rt should not be provided when tg='horizontal cylinder'.")
            if rc is not None:
                raise ValueError("rc should not be provided when tg='horizontal cylinder'. "
                                 "Only shell color (sc) is used.")
            if rpc is not None:
                raise ValueError("rpc should not be provided when tg='horizontal cylinder'. "
                                 "Only shell paint condition (spc) is used.")
            self.De = np.sqrt(self.H * self.D / (np.pi / 4))  # effective tank diameter for horiz. tank, ft, eq 1-14
            self.He = (np.pi / 4) * self.D  # effective tank height for horiz. tank, ft, eq 1-15
            self.Hvo = self.He / 2  # vapor space outage for horizontal tank, ft, eq 1-16

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

        # Table 7-1-6 Paint solar absortance
        self.alpha_s = PAINT_DATA[PAINT_DATA['surface color'] == self.sc][self.spc].values[0]  # tank shell paint solar absortance, dimensionless
        self.alpha_r = PAINT_DATA[PAINT_DATA['surface color'] == self.rc][self.rpc].values[0]  # tank roof paint solar absortance, dimensionless

        # Table 7-1-7: Meteorological data for the select US location.
        self.loc_geodata = self._validate_location(loc)  # type = dataframe
        if timeframe != 'Annual':
            self.timeframe = self._validate_timeframe(timeframe)

        # Table 7-1-7 Meteorological data for selected US locations
        self.Tax = utilities.calc_F_to_R(self.loc_geodata[self.loc_geodata['Symbol'] == 'TAX'][self.timeframe].values[0])  # average daily maximum ambient temperature, R
        self.Tan = utilities.calc_F_to_R(self.loc_geodata[self.loc_geodata['Symbol'] == 'TAN'][self.timeframe].values[0])  # average daily minimum ambient temperature, R
        self.Taa = (self.Tax + self.Tan) / 2  # average daily ambient temperature, R, eq 1-30
        self.V = self.loc_geodata[self.loc_geodata['Symbol'] == 'V'][self.timeframe].values[0]  # average wind speed, mi/hr
        self.I = self.loc_geodata[self.loc_geodata['Symbol'] == 'I'][self.timeframe].values[0]  # average daily total insolation factor, btu/ft^2/day
        self.Pa = self.loc_geodata[self.loc_geodata['Symbol'] == 'PA']['Annual'].values[0]  # average atmospheric pressure, psi

        self.Taa_delta = self.Tax - self.Tan  # average daily ambient temperature range, R, eq 1-11

        # liquid bulk temperature, R
        if Tb is not None:
            self.Tb = utilities.calc_F_to_R(Tb)
        else:
            self.Tb = self.Taa + 0.003 * self.alpha_s * self.I  # eq 1-31

        self.Tv_delta = self.calc_Tv_delta(insulation)  # average daily temperature range, R, eq 1-6

        self.Tla = self.calc_Tl(self.Taa, self.insulation)  # average daily liquid surface temperature, R,
        self.Tlx = self.Tla + 0.25 * self.Tv_delta  # maximum daily liquid surface temperature, R
        self.Tln = self.Tla - 0.25 * self.Tv_delta  # minimum daily liquid surface temperature, R

    def calc_Tv(self, insulation):
        """average daily vapor temperature R"""

        # eq 1-32
        if insulation == 'uninsulated':
            _1 = (2.2 * (self.H / self.D) + 1.1) * self.Taa
            _2 = 0.8 * self.Tb
            _3 = 0.021 * self.alpha_r * self.I
            _4 = 0.013 * (self.H / self.D) * self.alpha_s * self.I
            denom = 2.2 * (self.H / self.D) + 1.9
            return (_1 + _2 + _3 + _4) / denom

        # eq 1-34
        elif insulation == 'partial':  # shell is insulated, but roof is not.
            return 0.6 * self.Taa + 0.4 * self.Tb + 0.01 * self.alpha_r * self.I

        elif insulation == 'full':
            return self.Tb
        else:
            self._validate_insulation(insulation)  # this line should never be triggered

    def calc_Tv_delta(self, insulation):
        """average daily vapor temperature range, R, eq 1-6"""

        # eq 1-6
        if insulation == 'uninsulated':
            _1 = (1 - 0.8 / (2.2 * (self.H / self.D) + 1.9)) * self.Taa_delta
            _2 = (0.042 * self.alpha_r * self.I + 0.026 * (self.H / self.D) * self.alpha_s * self.I) / (2.2 * (self.H / self.D) + 1.9)
            return _1 + _2

        # eq 1-8
        elif insulation == 'partial':  # shell is insulated, but roof is not.
            return 0.6 * self.Taa_delta + 0.02 * self.alpha_r * self.I

        elif insulation == 'full':
            return 0
        else:
            self._validate_insulation(insulation)  # this line should never be triggered

    def calc_Tl(self, Ta, insulation):
        """daily liquid surface temperature, R. Ta = Ambient air temperature, R. insulation = string'"""

        # eq 1-27
        if insulation == 'uninsulated':
            _1 = (0.5 - 0.8 / (4.4 * (self.H / self.D) + 3.8)) * Ta
            _2 = (0.5 + 0.8 / (4.4 * (self.H / self.D) + 3.8)) * self.Tb
            _3 = (0.021 * self.alpha_r * self.I + 0.013 * (self.H / self.D) * self.alpha_s * self.I) / (4.4 * (self.H / self.D) + 3.8)
            return _1 + _2 + _3

        # eq 1-29
        elif insulation == 'partial':  # shell is insulated, but roof is not.
            return 0.3 * Ta + 0.7 * self.Tb + 0.005 * self.alpha_r * self.I

        elif insulation == 'full':
            return self.Tb

        else:
            self._validate_insulation(insulation)  # this line should never be triggered

    def _validate_insulation(self, insulation):
        """Validate insulation type"""
        self._is_string(insulation)
        valid_options = {'uninsulated', 'partial', 'full'}
        if insulation.lower() not in {option.lower() for option in valid_options}:
            quoted_options = ', '.join(f"'{option}'" for option in valid_options)
            raise ValueError(f"Invalid input: '{insulation}'. Accepted insulation types are: {quoted_options}.")

        return insulation.lower()

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
            raise ValueError(f"Invalid input: '{c}'. Accepted color or material types are: {quoted_options}.")

        return c.lower()

    def _validate_pc(self, pc):
        """Validate pc (property condition)"""
        self._is_string(pc)
        valid_conditions = {'new', 'average', 'aged'}
        if pc.lower() not in {condition.lower() for condition in valid_conditions}:
            quoted_conditions = ', '.join(f"'{condition}'" for condition in valid_conditions)
            raise ValueError(f"Invalid input: '{pc}'. Accepted paint conditions are: {quoted_conditions}.")

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
            # Check if the string can be converted to an integer
            if tf_input.isdigit():
                # Convert to integer
                int_input = int(tf_input)
                # Validate the integer input
                if int_input > 12:
                    raise ValueError(
                        "Invalid input: The number exceeds 12. There are only 12 months in a year plus 0 for 'Annual'.")
                normalized_input = int_input
            else:
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
                "Timeframe not found, check for a typo. Examples of accepted string inputs: 'Annual', 'Sep', 'September', 'Feb', 'February', 'Dec', 'December'.... Alternatively, pass integer inputs [0, 12]. Ex: 0='Annual', 1='Jan', 12='Dec'.")

        raise ValueError("Timeframe not found.")

    def _is_string(self, item):
        if not isinstance(item, str):
            raise TypeError("The arugment type must be a string")

    @staticmethod
    def get_locations_list():
        return list(set(GEO_DATA['Location']))


#a = Tank(12, 6, loc='Cedar City, UT', Rrd=1, Sr=0.0625, Fl=0.5, tg='vertical cylinder', rt='dome', rc='white', sc='Brown',
#         timeframe='1')

# vertical dome
a = Tank(12, 6, loc='Cedar City, UT', Rrd=1, Fl=0.5, tg='vertical cylinder', rt='dome', rc='white', sc='Brown',
         timeframe='1')

# vertical cone
a = Tank(12, 6, loc='Cedar City, UT', Sr=0.0625, Fl=0.5, tg='vertical cylinder', rt='cone', rc='white', sc='Brown',
         timeframe='1')

# horiz
a = Tank(12, 6, loc='Cedar City, UT', Sr=0.0625, Fl=0.5, tg='horizontal cylinder', sc='Brown', timeframe='1')


print('Wv   : Vapor Density                                              : ')
print('Ke   : Vapor Space Expansion Factor                               : ')
print('Ks   : Vented Vapor Saturation Factor                             : ')
print('D    : Shell Diameter                                             : ', a.D)
print('De   : Effective Shell Diameter                                   : ')
try: print('Hvo  : Vapor Space Outage                                         : ', round(a.Hvo, 3))
except: print('Hvo  : Vapor Space Outage                                         : ')
print('ΔTv  : Average Daily Vapor Temperature Range                      : ', round(a.Tv_delta, 3))
print('ΔPv  : Average Daily Vapor Pressure Range                         : ')
print('ΔPb  : Breather Vent Pressure Setting Range                       : ')
print('Pa   : Atmospheric Pressure at Tank Location                      : ', a.Pa)
print('Pva  : Vapor Pressure at Average Daily Liquid Surface Temperature : ')
print('Tla  : Average Daily Liquid Surface Temperature                   : ', round(a.Tla, 3))
print('Hs   : Shell Length                                               : ', a.H)
print('ΔTa  : Average Daily Ambient Temperature Range                    : ')
print('αr   : Tank Roof Surface Solar Absorptance                        : ', a.alpha_r)
print('αs   : Tank Shell Surface Solar Absorptance                       : ', a.alpha_s)
print('I    : Daily Solar Insolation                                     : ', a.I)
print('Pvx  : Vapor Pressure at Maximum Liquid Surface Temperature       : ')
print('Pvn  : Vapor Pressure at Minimum Liquid Surface Temperature       : ')
print('Tlx  : Maximum Liquid Surface Temperature                         : ', round(a.Tlx, 3))
print('Tln  : Minimum Liquid Surface Temperature                         : ', round(a.Tln, 3))
print('Pbp  : Breather Vent Pressure                                     : ')
print('Pbv  : Breather Vacuum Pressure                                   : ')
print('Tax  : Average Daily Maximum Ambient Temperature                  : ', a.Tax)
print('Tan  : Average Daily Minimum Ambient Temperature                  : ', a.Tan)
print('He   : Effective Height                                           : ')
print('Hl   : Liquid Height                                              : ')
try: print('Hro  : Roof Outage                                                : ', np.round(a.Hro, 3))
except: print('Hro  : Roof Outage                                                : ')
try: print('Hr   : Tank Roof Height                                           : ', np.round(a.Hr, 3))
except: print('Hr   : Tank Roof Height                                           : ')
print('Sr   : Slope of Coned Roof                                        : ', a.Sr)
print('Rs   : Tank Shell Radius                                          : ', a.Rs)
try: print('Rr   : Radius of Domed Roof                                       : ', a.Rr)
except: print('Rr   : Radius of Domed Roof                                       : ')
print('Mv   : Vapor Molecular Weight                                     : ')
print('Tv   : Average Vapor Temperature                                  : ')
print('Taa  : Average Daily Ambient Temperature                          : ', a.Taa)
print('Tb   : Liquid Bulk Temperature                                    : ', np.round(a.Tb, 3))
print('Tbx  : Maximum Liquid Bulk Temperature                            : ')
print('Tbn  : Minimum Liquid Bulk Temperature                            : ')
