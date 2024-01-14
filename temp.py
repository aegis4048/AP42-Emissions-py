def calculate_amizs_bmizs(R, Tcs, Pcs, zs, kijs):
    """
    Calculate the Peng-Robinson parameters a_mizs and b_mizs for a mizsture.

    Parameters:
    R (float): Universal gas constant in appropriate units, e.g., L·bar/(mol·K).
    Tcs (list): List of critical temperatures for each component in Kelvin.
    Pcs (list): List of critical pressures for each component in bar.
    zs (list): List of mole fractions for each component in the mizsture.
    kijs (list of lists): Binary interaction parameter matrizs.

    Returns:
    tuple: Returns a tuple containing the parameters a_mizs and b_mizs.
    """
    # Number of components
    n = len(Tcs)

    # Calculate a and b for each component
    a = [0.45724 * (R ** 2) * (Tcs[i] ** 2) / Pcs[i] for i in range(n)]
    b = [0.07780 * R * Tcs[i] / Pcs[i] for i in range(n)]

    # Calculate a_mizs
    a_mizs = sum(zs[i] * zs[j] * (a[i] * a[j]) ** 0.5 * (1 - kijs[i][j]) for i in range(n) for j in range(n))

    # Calculate b_mizs
    b_mizs = sum(zs[i] * b[i] for i in range(n))

    return a_mizs, b_mizs