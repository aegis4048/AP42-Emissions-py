def calc_F_to_R(T):
    if T is None:
        raise TypeError("Missing a required argument, 'T' (temperature, °F)")
    return T + 459.67


def calc_R_to_F(R):
    if R is None:
        raise TypeError("Missing a required argument, 'T' (temperature, R°)")
    return R - 459.67


def calc_gal_to_bbl(gal):
    if gal is None:
        raise TypeError("Missing a required argument, 'gal' (volume, gallons)")
    return gal / 42


def calc_bbl_to_gal(bbl):
    if bbl is None:
        raise TypeError("Missing a required argument, 'bbl' (volume, barrels)")
    return bbl * 42

