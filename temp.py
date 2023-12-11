import numpy as np
import pandas as np


class Tank(object):

    def __init__(self, H, D, Rrd=1, Sr=0.0625, Fl=0.5, tg='vertical cylinder', rt='cone'):

        self._validate_Fl(Fl)
        self.tg = self._validate_tg(tg)  # tank geometry
        self.rt = self._validate_rt(rt)  # roof type

        self.H = H  # tank shell height, ft
        self.D = D  # tank shell diameter, ft

        self.Fl = Fl  # fraction fill of liquid in a tank, assumed to be 50% unless specified  [not sure for horiz vs vert]
        self.Hl = self.H * self.Fl  # liquid height, ft, assumed to be 50% filled by default  [not sure for horiz vs vert]

        self.Rs = self.D / 2  # tank shell radius, ft [not sure which tg]

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

    def _is_string(self, item):
        if not isinstance(item, str):
            raise TypeError("The arugment type must be a string")

a = Tank(30, 15, Rrd=1, Sr=0.0625, Fl=0.5, tg='vertical cylinder', rt='dome')
















