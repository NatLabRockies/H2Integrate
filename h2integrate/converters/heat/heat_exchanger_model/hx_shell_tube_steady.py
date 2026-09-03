"""
Created on Wed Dec 10 09:34:19 2025

@author: psaini
"""

from math import log

import numpy as np
from CoolProp.CoolProp import PropsSI


# ----------------------------------------------------------------------
# 1) CoolProp-based generic fluid properties
# ----------------------------------------------------------------------
def make_coolprop_fluid(fluid_name="Water", P_bar=1.0):
    """
    Returns a function fluid_fun(T_c) that uses CoolProp for fluid properties.

    Parameters
    ----------
    fluid_name : str
        CoolProp fluid name, e.g. 'Water', 'Ethanol', 'R134a', 'MEG', etc.
    P_bar : float
        Operating pressure in bar (absolute). Converted internally to Pa.

    Returns
    -------
    fluid_fun : callable
        fluid_fun(T_c) -> dict(rho, mu, cp, k, Pr)
        where T_c is in degC and properties are SI units:
            - rho : density [kg/m^3]
            - mu  : dynamic viscosity [Pa·s]
            - cp  : specific heat at constant pressure [J/kg-K]
            - k   : thermal conductivity [W/m-K]
            - Pr  : Prandtl number [-]
    """
    P_Pa = P_bar * 1e5  # bar -> Pa

    def fluid_fun(T_c):
        T_c_arr = np.asarray(T_c, dtype=float)
        T_K = T_c_arr + 273.15

        rho = PropsSI("D", "T", T_K, "P", P_Pa, fluid_name)  # density [kg/m^3]
        mu = PropsSI("V", "T", T_K, "P", P_Pa, fluid_name)  # dyn. visc. [Pa·s]
        cp_ = PropsSI("C", "T", T_K, "P", P_Pa, fluid_name)  # cp [J/kg-K]
        k = PropsSI("L", "T", T_K, "P", P_Pa, fluid_name)  # k [W/m-K]
        Pr = PropsSI("Prandtl", "T", T_K, "P", P_Pa, fluid_name)  # Pr [-]

        return {"rho": rho, "mu": mu, "cp": cp_, "k": k, "Pr": Pr}

    return fluid_fun


# Default fluids (both sides = liquid water @ 1 bar)
DEFAULT_WATER_FLUID = make_coolprop_fluid("Water", P_bar=1.0)


# ----------------------------------------------------------------------
# 2) Metal properties, helper functions
# ----------------------------------------------------------------------
def metal_props(name: str):
    key = name.lower().replace(" ", "_")
    if key in ("carbon_steel", "cs"):
        return 45.0, 7850.0, 480.0
    elif key in ("stainless_304", "ss304", "stainless"):
        return 16.0, 8000.0, 500.0
    elif key in ("copper", "cu"):
        return 390.0, 8960.0, 385.0
    else:
        # default carbon steel
        return 45.0, 7850.0, 480.0


def LMTD_calc(dT1, dT2):
    if dT1 <= 0 or dT2 <= 0:
        raise ValueError("Non-positive temperature difference in LMTD_calc.")
    if abs(dT1 - dT2) < 1e-6:
        return 0.5 * (dT1 + dT2)
    return (dT1 - dT2) / log(dT1 / dT2)


def classify_regime(Re_min, Re_max, Re_laminar_max, Re_turb_min):
    if Re_max < Re_laminar_max:
        return "laminar"
    elif Re_min > Re_turb_min:
        return "turbulent"
    else:
        return "transition"


def shell_h_local(cold_props, m_dot_c, geom, shell, F_shell, model):
    S_m = geom["S_m"]
    D_o = geom["D_o"]
    p_t = shell["pitch"]
    D_e = 4.0 * (p_t**2 - np.pi * D_o**2 / 4.0) / (np.pi * D_o)

    G_s = m_dot_c / S_m
    Re_s = G_s * D_e / cold_props["mu"]
    Pr_c = cold_props["cp"] * cold_props["mu"] / cold_props["k"]

    model_l = model.lower()
    if model_l == "kern":
        if Re_s < 2000.0:
            L_char = max(1e-6, shell["baffle_spacing"])
            Nu_fd = 3.66
            Gz_s = Re_s * Pr_c * D_e / L_char
            Nu_s = Nu_fd * (1.0 - np.exp(-Gz_s / 20.0))
            Nu_s = max(1.0, min(Nu_fd, Nu_s))
        else:
            Nu_s = 0.36 * Re_s**0.55 * Pr_c ** (1.0 / 3.0)
    elif model_l == "bell_delaware":
        # Placeholder: same as Kern, can refine later
        if Re_s < 2000.0:
            L_char = max(1e-6, shell["baffle_spacing"])
            Nu_fd = 3.66
            Gz_s = Re_s * Pr_c * D_e / L_char
            Nu_s = Nu_fd * (1.0 - np.exp(-Gz_s / 20.0))
            Nu_s = max(1.0, min(Nu_fd, Nu_s))
        else:
            Nu_s = 0.36 * Re_s**0.55 * Pr_c ** (1.0 / 3.0)
    else:
        raise ValueError(f"Unknown shell_model '{model}'")

    h_o = Nu_s * cold_props["k"] / D_e
    h_o *= F_shell
    return h_o, Re_s, Nu_s


def shell_dp_Kern(m_dot_c, cold_props, geom, shell):
    S_m = geom["S_m"]
    D_o = geom["D_o"]
    p_t = shell["pitch"]
    D_e = 4.0 * (p_t**2 - np.pi * D_o**2 / 4.0) / (np.pi * D_o)

    G_s = m_dot_c / S_m
    Re_s = G_s * D_e / cold_props["mu"]

    if Re_s < 2000.0:
        f_s = 64.0 / Re_s
    else:
        f_s = 0.14 * Re_s ** (-0.2)

    N_b = max(1, int(geom["L_tube"] / shell["baffle_spacing"]) - 1)
    dp_shell = 4.0 * f_s * (G_s**2 / (2.0 * cold_props["rho"])) * N_b
    return dp_shell


# ----------------------------------------------------------------------
# 3) Main HX model
# ----------------------------------------------------------------------
def hx_shell_tube_steady(params=None):
    if params is None:
        params = {}
    get = params.get

    # Inlet temps [°C] and mass flow rates [kg/s]
    Th_in = float(get("Th_in", 90.0))
    Tc_in = float(get("Tc_in", 30.0))
    m_dot_h = float(get("m_dot_h", 18.0))
    m_dot_c = float(get("m_dot_c", 40.0))

    # Geometry
    N_tubes = int(get("N_tubes", 192))
    N_passes = int(get("N_passes", 2))
    L_tube = float(get("L_tube", 4.9))
    D_o = float(get("D_o", 0.01905))
    t_wall = float(get("t_wall", 0.002))
    D_i = D_o - 2.0 * t_wall
    k_wall = float(get("k_wall", 45.0))
    D_shell = float(get("D_shell", 0.591))

    # Discretization
    N_seg = int(get("N_seg", 20))

    # Fouling
    R_fi = float(get("R_fi", 1e-4))
    R_fo = float(get("R_fo", 2e-4))

    # Shell-side parameters
    shell = {
        "pitch": get("pitch", 1.1 * D_o),
        "baffle_spacing": get("baffle_spacing", 0.20),
        "baffle_cut": get("baffle_cut", 0.20),
        "layout": get("layout", "triangular"),
    }

    # Pump efficiency
    eta_pump = float(get("eta_pump", 0.7))

    # Pinch threshold
    pinch_threshold = float(get("pinch_threshold", 3.0))

    # Physics switches
    use_SiederTate_tube = bool(get("use_SiederTate_tube", True))
    use_wall_viscosity_correction = bool(get("use_wall_viscosity_correction", True))
    F_shell = float(get("F_shell", 0.8))
    shell_model = get("shell_model", "kern")
    T0_env = float(get("T0_env", 298.15))

    # External shell loss
    U_loss = float(get("U_loss", 0.0))
    T_amb = float(get("T_amb", 25.0))

    # Property functions (now CoolProp-based by default)
    fluid_hot_fun = get("fluid_hot", DEFAULT_WATER_FLUID)
    fluid_cold_fun = get("fluid_cold", DEFAULT_WATER_FLUID)

    # fzero options
    fzero_tol = float(get("fzero_tol", 1e-6))
    fzero_maxit = int(get("fzero_maxit", 50))

    # Materials
    tube_material = get("tube_material", "carbon_steel")
    shell_material = get("shell_material", "carbon_steel")

    t_shell = float(get("t_shell", 0.02))

    # Reynolds thresholds
    Re_laminar_max = float(get("Re_laminar_max", 2300.0))
    Re_turb_min = float(get("Re_turb_min", 4000.0))

    # Metal props
    tube_k, tube_rho, tube_cp = metal_props(tube_material)
    shell_k, shell_rho, shell_cp = metal_props(shell_material)

    if "k_wall" not in params:
        k_wall = tube_k

    # Geometry and areas
    A_tube_flow = (np.pi * D_i**2 / 4.0) * (N_tubes / N_passes)
    A_o_total = np.pi * D_o * L_tube * N_tubes
    A_seg = A_o_total / N_seg

    A_shell_free = (np.pi * D_shell**2 / 4.0) - N_tubes * (np.pi * D_o**2 / 4.0)
    if A_shell_free <= 0.0:
        raise ValueError("Shell is too small for the given number/size of tubes.")

    P_wet_shell = np.pi * D_shell + N_tubes * np.pi * D_o
    D_h_shell = 4.0 * A_shell_free / P_wet_shell

    D_shell_in = D_shell
    D_shell_out = D_shell + 2.0 * t_shell

    V_tube_metal = (np.pi / 4.0) * (D_o**2 - D_i**2) * L_tube * N_tubes
    V_shell_metal = (np.pi / 4.0) * (D_shell_out**2 - D_shell_in**2) * L_tube

    V_tube_fluid = (np.pi / 4.0) * D_i**2 * L_tube * N_tubes
    V_shell_fluid = A_shell_free * L_tube

    S_m = D_shell * shell["baffle_spacing"] * (1.0 - shell["baffle_cut"])

    geom = {
        "N_tubes": N_tubes,
        "N_passes": N_passes,
        "L_tube": L_tube,
        "D_i": D_i,
        "D_o": D_o,
        "D_shell": D_shell,
        "A_tube_flow": A_tube_flow,
        "A_shell_free": A_shell_free,
        "D_h_shell": D_h_shell,
        "A_o_total": A_o_total,
        "A_seg": A_seg,
        "N_seg": N_seg,
        "A_shell_outer_total": np.pi * D_shell * L_tube,
        "S_m": S_m,
    }
    geom["A_shell_outer_seg"] = geom["A_shell_outer_total"] / N_seg

    # ------------------------------------------------------------------
    # Shooting for counter-current
    # ------------------------------------------------------------------
    Tc_out0_min = Tc_in + 1e-3
    Tc_out0_max = Th_in - 1e-3
    Tc_out0_guess = Tc_in + 0.7 * (Th_in - Tc_in)

    def march_segments(Th_in_local, Tc_out0_local):
        N_seg = geom["N_seg"]
        A_seg = geom["A_seg"]
        A_tube_flow = geom["A_tube_flow"]
        D_i = geom["D_i"]

        Th = np.zeros(N_seg + 1)
        Tc = np.zeros(N_seg + 1)
        Tw = np.zeros(N_seg)
        U_seg = np.zeros(N_seg)
        Q_seg = np.zeros(N_seg)
        Q_loss_seg = np.zeros(N_seg)
        Re_t_seg = np.zeros(N_seg)
        Re_s_seg = np.zeros(N_seg)
        h_i_seg = np.zeros(N_seg)
        h_o_seg = np.zeros(N_seg)
        Nu_t_seg = np.zeros(N_seg)
        Nu_s_seg = np.zeros(N_seg)
        S_gen_seg = np.zeros(N_seg)

        Th[0] = Th_in_local
        Tc[0] = Tc_out0_local

        A_loss = geom["A_shell_outer_seg"]
        L_seg = geom["L_tube"] / geom["N_seg"]

        for i in range(N_seg):
            Th_i = Th[i]
            Tc_i = Tc[i]

            hot = fluid_hot_fun(Th_i)
            cold = fluid_cold_fun(Tc_i)

            # Tube-side Re, Nu, h_i
            V_tube = m_dot_h / (hot["rho"] * A_tube_flow)
            Re_t = hot["rho"] * V_tube * D_i / hot["mu"]
            Pr_h = hot["cp"] * hot["mu"] / hot["k"]

            if Re_t < Re_laminar_max:
                Nu_fd = 3.66
                Gz_t = Re_t * Pr_h * D_i / max(1e-9, L_seg)
                Nu_t = Nu_fd * (1.0 - np.exp(-Gz_t / 20.0))
                Nu_t = max(1.0, min(Nu_fd, Nu_t))
            else:
                if use_SiederTate_tube:
                    mu_b = hot["mu"]
                    if use_wall_viscosity_correction:
                        Tw_guess = 0.5 * (Th_i + Tc_i)
                        wall_hot = fluid_hot_fun(Tw_guess)
                        mu_w = wall_hot["mu"]
                    else:
                        mu_w = mu_b
                    Nu_t = 0.027 * Re_t**0.8 * Pr_h ** (1.0 / 3.0) * (mu_b / mu_w) ** 0.14
                else:
                    Nu_t = 0.023 * Re_t**0.8 * Pr_h**0.4
            h_i = Nu_t * hot["k"] / D_i

            Re_t_seg[i] = Re_t
            h_i_seg[i] = h_i
            Nu_t_seg[i] = Nu_t

            # Shell-side
            h_o, Re_s, Nu_s = shell_h_local(cold, m_dot_c, geom, shell, F_shell, shell_model)
            Re_s_seg[i] = Re_s
            h_o_seg[i] = h_o
            Nu_s_seg[i] = Nu_s

            # Overall U
            R_o = 1.0 / h_o + R_fo
            R_w = (geom["D_o"] * log(geom["D_o"] / geom["D_i"])) / (2.0 * k_wall)
            R_i = geom["D_o"] / (geom["D_i"] * h_i) + R_fi * geom["D_o"] / geom["D_i"]

            U_i = 1.0 / (R_o + R_w + R_i)
            U_seg[i] = U_i

            dT_i = Th_i - Tc_i
            Q_i = U_i * A_seg * dT_i

            # External loss (from shell to ambient)
            Q_loss_i = U_loss * A_loss * (Tc_i - T_amb)
            Q_loss_seg[i] = Q_loss_i

            cp_h = hot["cp"]
            cp_c = cold["cp"]

            # Energy balances
            Th[i + 1] = Th_i - Q_i / (m_dot_h * cp_h)
            Tc[i + 1] = Tc_i - (Q_i - Q_loss_i) / (m_dot_c * cp_c)

            # Wall temperature
            Tw[i] = (h_i * Th_i + h_o * Tc_i) / (h_i + h_o)
            Q_seg[i] = Q_i

            # Local entropy generation
            Th_iK = Th_i + 273.15
            Tc_iK = Tc_i + 273.15
            S_gen_seg[i] = Q_i * (1.0 / Tc_iK - 1.0 / Th_iK)

        return (
            Th,
            Tc,
            Tw,
            U_seg,
            Q_seg,
            Q_loss_seg,
            Re_t_seg,
            Re_s_seg,
            h_i_seg,
            h_o_seg,
            Nu_t_seg,
            Nu_s_seg,
            S_gen_seg,
        )

    def residual_Tc_out(Tc_out0):
        Th_, Tc_, *_ = march_segments(Th_in, Tc_out0)
        Tc_at_L = Tc_[-1]
        return Tc_at_L - Tc_in

    # Simple bisection
    def find_root_bisect(f, a, b, tol, maxit):
        fa = f(a)
        fb = f(b)
        if fa * fb > 0:
            return None, fa, fb
        for _ in range(maxit):
            c = 0.5 * (a + b)
            fc = f(c)
            if abs(fc) < tol or 0.5 * (b - a) < tol:
                return c, fa, fb
            if fa * fc < 0:
                b = c
                fb = fc
            else:
                a = c
                fa = fc
        return c, fa, fb

    Tc_root, r_min, r_max = find_root_bisect(
        residual_Tc_out, Tc_out0_min, Tc_out0_max, fzero_tol, fzero_maxit
    )
    shooting_bracket_ok = True
    if Tc_root is None:
        shooting_bracket_ok = False
        Tc_root = Tc_out0_guess

    # March with final
    (
        Th,
        Tc,
        Tw,
        U_seg,
        Q_seg,
        Q_loss_seg,
        Re_t_seg,
        Re_s_seg,
        h_i_seg,
        h_o_seg,
        Nu_t_seg,
        Nu_s_seg,
        S_gen_seg,
    ) = march_segments(Th_in, Tc_root)

    x = np.linspace(0.0, L_tube, N_seg + 1)
    x_mid = 0.5 * (x[:-1] + x[1:])

    Q_total = float(np.sum(Q_seg))
    Q_loss_tot = float(np.sum(Q_loss_seg))
    Th_out = float(Th[-1])
    Tc_out = float(Tc[0])

    # Global metrics
    dT1 = Th_in - Tc_out
    dT2 = Th_out - Tc_in
    LMTD_global = LMTD_calc(dT1, dT2)
    U_global = Q_total / (A_o_total * LMTD_global)

    hot_in = fluid_hot_fun(Th_in)
    cold_in = fluid_cold_fun(Tc_in)
    cp_h_in = hot_in["cp"]
    cp_c_in = cold_in["cp"]
    C_hot = m_dot_h * cp_h_in
    C_cold = m_dot_c * cp_c_in
    C_min = min(C_hot, C_cold)
    C_max = max(C_hot, C_cold)
    C_r = C_min / C_max

    epsilon = Q_total / (C_min * (Th_in - Tc_in))
    NTU = U_global * A_o_total / C_min

    # Energy-balance checks
    Q_hot = m_dot_h * cp_h_in * (Th_in - Th_out)
    Q_cold = m_dot_c * cp_c_in * (Tc_out - Tc_in)

    Q_ref_hot = Q_total
    Q_ref_cold = Q_total - Q_loss_tot

    energy_balance_error_hot = (Q_hot - Q_ref_hot) / abs(Q_ref_hot)
    energy_balance_error_cold = (Q_cold - Q_ref_cold) / abs(Q_ref_cold)

    # Lumped U & LMTD check
    Th_mean_bulk = 0.5 * (Th_in + Th_out)
    Tc_mean_bulk = 0.5 * (Tc_in + Tc_out)
    hot_m = fluid_hot_fun(Th_mean_bulk)
    cold_m = fluid_cold_fun(Tc_mean_bulk)
    Tw_mean = 0.5 * (Th_mean_bulk + Tc_mean_bulk)

    V_tube_mean = m_dot_h / (hot_m["rho"] * A_tube_flow)
    Re_t_mean = hot_m["rho"] * V_tube_mean * D_i / hot_m["mu"]
    Pr_h_mean = hot_m["cp"] * hot_m["mu"] / hot_m["k"]

    if Re_t_mean < Re_laminar_max:
        Nu_t_mean = 3.66
    else:
        if use_SiederTate_tube:
            mu_b = hot_m["mu"]
            if use_wall_viscosity_correction:
                wall_hot_mean = fluid_hot_fun(Tw_mean)
                mu_w = wall_hot_mean["mu"]
            else:
                mu_w = mu_b
            Nu_t_mean = 0.027 * Re_t_mean**0.8 * Pr_h_mean ** (1.0 / 3.0) * (mu_b / mu_w) ** 0.14
        else:
            Nu_t_mean = 0.023 * Re_t_mean**0.8 * Pr_h_mean**0.4
    h_i_mean = Nu_t_mean * hot_m["k"] / D_i

    h_o_mean, _, _ = shell_h_local(cold_m, m_dot_c, geom, shell, F_shell, shell_model)

    R_o_mean = 1.0 / h_o_mean + R_fo
    R_w_mean = (D_o * log(D_o / D_i)) / (2.0 * k_wall)
    R_i_mean = D_o / (D_i * h_i_mean) + R_fi * D_o / D_i

    U_lumped = 1.0 / (R_o_mean + R_w_mean + R_i_mean)
    Q_LMTD_lumped = U_lumped * A_o_total * LMTD_global
    Q_error_frac = (Q_total - Q_LMTD_lumped) / Q_total

    # Pressure drops & pump power
    Th_mean = float(np.mean(Th))
    Tc_mean = float(np.mean(Tc))
    hot_mean = fluid_hot_fun(Th_mean)
    cold_mean = fluid_cold_fun(Tc_mean)

    V_tube = m_dot_h / (hot_mean["rho"] * A_tube_flow)
    Re_t = hot_mean["rho"] * V_tube * D_i / hot_mean["mu"]

    if Re_t < Re_laminar_max:
        f_t = 64.0 / Re_t
    else:
        f_t = 0.3164 * Re_t ** (-0.25)

    L_equiv_tube = L_tube * N_passes
    dp_fric_tube = f_t * (L_equiv_tube / D_i) * 0.5 * hot_mean["rho"] * V_tube**2

    K_inlet = 1.0
    K_exit = 1.0
    K_bends = 1.5 * (N_passes - 1)
    K_total = K_inlet + K_exit + K_bends
    dp_minor_tube = K_total * 0.5 * hot_mean["rho"] * V_tube**2

    dp_tube_total = dp_fric_tube + dp_minor_tube

    dp_shell_total = shell_dp_Kern(m_dot_c, cold_mean, geom, shell)

    P_pump_tube = (m_dot_h / hot_mean["rho"]) * dp_tube_total / eta_pump
    P_pump_shell = (m_dot_c / cold_mean["rho"]) * dp_shell_total / eta_pump
    P_pump_total = P_pump_tube + P_pump_shell

    # Inventories + time constants
    rho_hot_mean = hot_mean["rho"]
    rho_cold_mean = cold_mean["rho"]
    cp_hot_mean = hot_mean["cp"]
    cp_cold_mean = cold_mean["cp"]

    m_tube_metal = tube_rho * V_tube_metal
    m_shell_metal = shell_rho * V_shell_metal
    m_tube_fluid = rho_hot_mean * V_tube_fluid
    m_shell_fluid = rho_cold_mean * V_shell_fluid

    C_tube_metal = m_tube_metal * tube_cp
    C_shell_metal = m_shell_metal * shell_cp
    C_tube_fluid = m_tube_fluid * cp_hot_mean
    C_shell_fluid = m_shell_fluid * cp_cold_mean

    C_hot_total = C_tube_metal + C_tube_fluid
    C_cold_total = C_shell_metal + C_shell_fluid

    tau_hot = C_hot_total / (U_global * A_o_total)
    tau_cold = C_cold_total / (U_global * A_o_total)

    # Pinch & crossing
    deltaT = Th - Tc
    min_deltaT = float(np.min(deltaT))
    has_cross = bool(np.any(deltaT <= 0.0))
    pinch_warning = (not has_cross) and (min_deltaT < pinch_threshold)

    # 2nd law metrics
    Th_in_K = Th_in + 273.15
    Th_out_K = Th_out + 273.15
    Tc_in_K = Tc_in + 273.15
    Tc_out_K = Tc_out + 273.15

    hot_in2 = fluid_hot_fun(Th_in)
    hot_out2 = fluid_hot_fun(Th_out)
    cold_in2 = fluid_cold_fun(Tc_in)
    cold_out2 = fluid_cold_fun(Tc_out)

    cp_h_bar = 0.5 * (hot_in2["cp"] + hot_out2["cp"])
    cp_c_bar = 0.5 * (cold_in2["cp"] + cold_out2["cp"])

    S_gen_dot_bulk = m_dot_h * cp_h_bar * log(Th_out_K / Th_in_K) + m_dot_c * cp_c_bar * log(
        Tc_out_K / Tc_in_K
    )
    Ex_dest_dot_bulk = T0_env * S_gen_dot_bulk

    S_gen_dot_seg = float(np.sum(S_gen_seg))
    Ex_dest_dot_seg = T0_env * S_gen_dot_seg

    # Regimes
    Re_tube_min = float(np.min(Re_t_seg))
    Re_tube_max = float(np.max(Re_t_seg))
    Re_shell_min = float(np.min(Re_s_seg))
    Re_shell_max = float(np.max(Re_s_seg))

    tube_regime = classify_regime(Re_tube_min, Re_tube_max, Re_laminar_max, Re_turb_min)
    shell_regime = classify_regime(Re_shell_min, Re_shell_max, Re_laminar_max, Re_turb_min)

    V_tube_mean2 = V_tube
    G_s_mean = m_dot_c / S_m
    V_shell_mean = G_s_mean / cold_mean["rho"]

    flags = {
        "has_cross": has_cross,
        "small_pinch": pinch_warning,
        "tube_laminar": (tube_regime == "laminar"),
        "shell_laminar": (shell_regime == "laminar"),
        "low_NTU": (NTU < 0.1),
        "high_dp_tube": (dp_tube_total > 1e5),
        "high_dp_shell": (dp_shell_total > 1e4),
        "Q_LMTD_mismatch": (abs(Q_error_frac) > 0.05),
        "shooting_ok": shooting_bracket_ok,
        "V_tube_low": (V_tube_mean2 < 1.0),
        "V_tube_high": (V_tube_mean2 > 3.0),
        "V_shell_low": (V_shell_mean < 0.3),
        "V_shell_high": (V_shell_mean > 1.5),
    }

    inventory = {
        "tube_material": tube_material,
        "shell_material": shell_material,
        "t_shell": t_shell,
        "V_tube_metal": V_tube_metal,
        "V_shell_metal": V_shell_metal,
        "V_tube_fluid": V_tube_fluid,
        "V_shell_fluid": V_shell_fluid,
        "m_tube_metal": m_tube_metal,
        "m_shell_metal": m_shell_metal,
        "m_tube_fluid": m_tube_fluid,
        "m_shell_fluid": m_shell_fluid,
        "C_tube_metal": C_tube_metal,
        "C_shell_metal": C_shell_metal,
        "C_tube_fluid": C_tube_fluid,
        "C_shell_fluid": C_shell_fluid,
        "C_hot_total": C_hot_total,
        "C_cold_total": C_cold_total,
    }

    res = {
        "x": x,
        "x_mid": x_mid,
        "Th": Th,
        "Tc": Tc,
        "Tw": Tw,
        "Q_seg": Q_seg,
        "Q_total": Q_total,
        "Q_loss_seg": Q_loss_seg,
        "Q_loss_tot": Q_loss_tot,
        "U_seg": U_seg,
        "U_global": U_global,
        "LMTD_global": LMTD_global,
        "epsilon": epsilon,
        "NTU": NTU,
        "C_r": C_r,
        "Q_hot": Q_hot,
        "Q_cold": Q_cold,
        "energy_balance_error_hot": energy_balance_error_hot,
        "energy_balance_error_cold": energy_balance_error_cold,
        "dp_tube_total": dp_tube_total,
        "dp_shell_total": dp_shell_total,
        "P_pump_tube": P_pump_tube,
        "P_pump_shell": P_pump_shell,
        "P_pump_total": P_pump_total,
        "min_deltaT": min_deltaT,
        "has_cross": has_cross,
        "pinch_warning": pinch_warning,
        "Re_tube": Re_t_seg,
        "Re_shell": Re_s_seg,
        "Re_tube_min": Re_tube_min,
        "Re_tube_max": Re_tube_max,
        "Re_shell_min": Re_shell_min,
        "Re_shell_max": Re_shell_max,
        "tube_regime": tube_regime,
        "shell_regime": shell_regime,
        "h_i_seg": h_i_seg,
        "h_o_seg": h_o_seg,
        "Nu_t_seg": Nu_t_seg,
        "Nu_s_seg": Nu_s_seg,
        "U_lumped": U_lumped,
        "Q_LMTD_lumped": Q_LMTD_lumped,
        "Q_error_frac": Q_error_frac,
        "S_gen_seg": S_gen_seg,
        "S_gen_dot": S_gen_dot_seg,
        "Ex_dest_dot": Ex_dest_dot_seg,
        "S_gen_dot_bulk": S_gen_dot_bulk,
        "Ex_dest_dot_bulk": Ex_dest_dot_bulk,
        "tau_hot": tau_hot,
        "tau_cold": tau_cold,
        "inventory": inventory,
        "V_tube_mean": V_tube_mean2,
        "V_shell_mean": V_shell_mean,
        "flags": flags,
        "geom": geom,
        "shell": shell,
        "params": {
            "Th_in": Th_in,
            "Tc_in": Tc_in,
            "m_dot_h": m_dot_h,
            "m_dot_c": m_dot_c,
            "N_tubes": N_tubes,
            "N_passes": N_passes,
            "L_tube": L_tube,
            "D_o": D_o,
            "t_wall": t_wall,
            "D_i": D_i,
            "D_shell": D_shell,
            "N_seg": N_seg,
            "R_fi": R_fi,
            "R_fo": R_fo,
            "eta_pump": eta_pump,
            "pinch_threshold": pinch_threshold,
            "use_SiederTate_tube": use_SiederTate_tube,
            "use_wall_viscosity_correction": use_wall_viscosity_correction,
            "F_shell": F_shell,
            "shell_model": shell_model,
            "T0_env": T0_env,
            "U_loss": U_loss,
            "T_amb": T_amb,
            "fzero_tol": fzero_tol,
            "fzero_maxit": fzero_maxit,
            "tube_material": tube_material,
            "shell_material": shell_material,
            "t_shell": t_shell,
            "Re_laminar_max": Re_laminar_max,
            "Re_turb_min": Re_turb_min,
        },
    }
    return res


# ----------------------------------------------------------------------
# 4) Printing summary
# ----------------------------------------------------------------------
def print_summary(res, label="Python + CoolProp"):
    Th_in = res["params"]["Th_in"]
    Tc_in = res["params"]["Tc_in"]
    Th_out = res["Th"][-1]
    Tc_out = res["Tc"][0]

    print(f"=== HX summary (detailed, {label}) ===")
    print(f"Hot side:  Th_in  = {Th_in:6.2f} degC, Th_out = {Th_out:6.2f} degC")
    print(f"Cold side: Tc_in  = {Tc_in:6.2f} degC, Tc_out = {Tc_out:6.2f} degC\n")

    print(f"Q_total          = {res['Q_total']/1e3:8.1f} kW")
    print(f"Q_hot (bulk)     = {res['Q_hot']/1e3:8.1f} kW")
    print(f"Q_cold (bulk)    = {res['Q_cold']/1e3:8.1f} kW")
    print(
        f"Q_loss_tot       = {res['Q_loss_tot']/1e3:8.1f} kW "
        f"({100*res['Q_loss_tot']/max(1e-9,res['Q_total']):.2f} %)\n"
    )

    print(f"epsilon          = {res['epsilon']:.3f}")
    print(f"NTU              = {res['NTU']:.3f}")
    print(f"C_r              = {res['C_r']:.3f}")
    print(f"LMTD_global      = {res['LMTD_global']:.2f} K")
    print(f"U_global         = {res['U_global']:.1f} W/m^2-K")
    print(f"U_lumped         = {res['U_lumped']:.1f} W/m^2-K")
    print(f"Q_LMTD_lumped    = {res['Q_LMTD_lumped']/1e3:8.1f} kW")
    print(f"Q_error_frac     = {res['Q_error_frac']:.3f} " f"({100*res['Q_error_frac']:.1f} %)\n")

    print(f"U_seg  min / max = {res['U_seg'].min():.1f} / {res['U_seg'].max():.1f} W/m^2-K")
    print(f"h_i    min / max = {res['h_i_seg'].min():.1f} / {res['h_i_seg'].max():.1f} W/m^2-K")
    print(f"h_o    min / max = {res['h_o_seg'].min():.1f} / {res['h_o_seg'].max():.1f} W/m^2-K\n")

    print(
        f"Re_tube   min/max = {int(res['Re_tube_min']):6d} / {int(res['Re_tube_max']):6d}   "
        f"(regime: {res['tube_regime']})"
    )
    print(
        f"Re_shell  min/max = {int(res['Re_shell_min']):6d} / {int(res['Re_shell_max']):6d}   "
        f"(regime: {res['shell_regime']})"
    )
    print(f"V_tube_mean      = {res['V_tube_mean']:.3f} m/s")
    print(f"V_shell_mean     = {res['V_shell_mean']:.3f} m/s\n")

    print(f"dp_tube_total    = {res['dp_tube_total']/1e3:.2f} kPa")
    print(f"dp_shell_total   = {res['dp_shell_total']/1e3:.2f} kPa")
    print(f"P_pump_tube      = {res['P_pump_tube']/1e3:.3f} kW")
    print(f"P_pump_shell     = {res['P_pump_shell']/1e3:.3f} kW")
    print(f"P_pump_total     = {res['P_pump_total']/1e3:.3f} kW\n")

    print(f"tau_hot          = {res['tau_hot']:.1f} s")
    print(f"tau_cold         = {res['tau_cold']:.1f} s\n")

    print(f"min_deltaT       = {res['min_deltaT']:.2f} K")
    print(f"has_cross        = {int(res['has_cross'])}")
    print(
        f"pinch_warning    = {int(res['pinch_warning'])} "
        f"(threshold = {res['params']['pinch_threshold']:.1f} K)\n"
    )

    print(f"S_gen_dot (seg)  = {res['S_gen_dot']:.2f} W/K")
    print(f"Ex_dest_dot (seg)= {res['Ex_dest_dot']/1e3:.2f} kW")
    print(f"S_gen_dot_bulk   = {res['S_gen_dot_bulk']:.2f} W/K")
    print(f"Ex_dest_dot_bulk = {res['Ex_dest_dot_bulk']/1e3:.2f} kW\n")

    print("Flags:")
    for k, v in res["flags"].items():
        print(f"  {k:15s} = {int(v)}")
    print("============================================")


# ----------------------------------------------------------------------
# 5) Plotting
# ----------------------------------------------------------------------
def plot_results(res):
    import matplotlib.pyplot as plt

    x = res["x"]
    x_mid = res["x_mid"]
    Th = res["Th"]
    Tc = res["Tc"]
    Tw = res["Tw"]
    Q_seg = res["Q_seg"]
    S_gen_seg = res["S_gen_seg"]
    U_seg = res["U_seg"]
    h_i_seg = res["h_i_seg"]
    h_o_seg = res["h_o_seg"]
    Re_t = res["Re_tube"]
    Re_s = res["Re_shell"]

    geom = res["geom"]
    L_tube = geom["L_tube"]
    N_seg = geom["N_seg"]
    L_seg = L_tube / N_seg

    # Heat-transfer per unit length [W/m]
    q_per_m = Q_seg / L_seg

    # --- Figure 1: Temperature profiles ---
    plt.figure(figsize=(6, 4))
    plt.plot(x, Th, "-r", label="T_h(x)")
    plt.plot(x, Tc, "-b", label="T_c(x)")
    plt.plot(x_mid, Tw, "--k", label="T_w(x)")
    plt.grid(True)
    plt.xlabel("Axial position x [m]")
    plt.ylabel("Temperature [°C]")
    plt.title("Temperature profiles along HX (hot, cold, wall)")
    plt.legend()
    plt.tight_layout()

    # --- Figure 2: Local q' and S_gen ---
    fig, axes = plt.subplots(2, 1, figsize=(6, 6), sharex=True)
    axes[0].plot(x_mid, q_per_m / 1e3, "-o")
    axes[0].grid(True)
    axes[0].set_ylabel("q' [kW/m]")
    axes[0].set_title("Local heat transfer per unit length")

    axes[1].plot(x_mid, S_gen_seg, "-s")
    axes[1].grid(True)
    axes[1].set_xlabel("Axial position x [m]")
    axes[1].set_ylabel("S_gen,seg [W/K]")
    axes[1].set_title("Local entropy generation per segment")

    fig.tight_layout()

    # --- Figure 3: Local h_i, h_o, and U_seg ---
    fig, axes = plt.subplots(2, 1, figsize=(6, 6), sharex=True)
    axes[0].plot(x_mid, h_i_seg, "-r", label="h_i (tube side)")
    axes[0].plot(x_mid, h_o_seg, "-b", label="h_o (shell side)")
    axes[0].grid(True)
    axes[0].set_ylabel("h [W/m²-K]")
    axes[0].set_title("Local film coefficients")
    axes[0].legend()

    axes[1].plot(x_mid, U_seg, "-k")
    axes[1].grid(True)
    axes[1].set_xlabel("Axial position x [m]")
    axes[1].set_ylabel("U [W/m²-K]")
    axes[1].set_title("Local overall heat transfer coefficient U(x)")

    fig.tight_layout()

    # --- Figure 4: Reynolds numbers ---
    plt.figure(figsize=(6, 4))
    plt.plot(x_mid, Re_t, "-r", label="Re_tube")
    plt.plot(x_mid, Re_s, "-b", label="Re_shell")
    plt.axhline(res["params"]["Re_laminar_max"], linestyle="--", color="k", label="Re_laminar,max")
    plt.axhline(res["params"]["Re_turb_min"], linestyle="--", color="k", label="Re_turb,min")
    plt.yscale("log")
    plt.grid(True, which="both", axis="y")
    plt.xlabel("Axial position x [m]")
    plt.ylabel("Re [-]")
    plt.title("Local Reynolds numbers (tube & shell)")
    plt.legend()
    plt.tight_layout()


# ----------------------------------------------------------------------
# 6) Run when executed as a script
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # Example 1: default = Water @ 1 bar on both sides (no need to pass fluids)
    # res = hx_shell_tube_steady({})

    # Example 2: custom CoolProp fluids (e.g., hot water @ 5 bar, cold water @ 2 bar)
    hot_fluid = make_coolprop_fluid("Water", P_bar=5.0)
    cold_fluid = make_coolprop_fluid("Water", P_bar=2.0)

    params = {
        "Th_in": 90.0,
        "Tc_in": 30.0,
        "m_dot_h": 18.0,
        "m_dot_c": 40.0,
        "fluid_hot": hot_fluid,
        "fluid_cold": cold_fluid,
    }

    res = hx_shell_tube_steady(params)
    print_summary(res)
    plot_results(res)
