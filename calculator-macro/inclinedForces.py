# ==========================================
# TI-Nspire CX CAS Friendly Physics Solver
# (Updated: waits for ENTER after each result screen)
# ==========================================

import math

PI = 3.141592653589793

def pause():
    input("\nPress ENTER to return to menu...")

def deg2rad(d):
    return d * PI / 180.0

def sgn(x):
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0

def ask_float(prompt, default_val=None):
    while True:
        s = input(prompt)
        if s == "" and default_val is not None:
            return float(default_val)
        try:
            return float(s)
        except:
            print("Enter a number.")

def ask_int(prompt, lo, hi, default_val=None):
    while True:
        s = input(prompt)
        if s == "" and default_val is not None:
            return int(default_val)
        try:
            v = int(s)
            if v < lo or v > hi:
                print("Out of range.")
            else:
                return v
        except:
            print("Enter an integer.")

def ask_choice(prompt, a, b, default_val=None):
    while True:
        s = input(prompt).strip().lower()
        if s == "" and default_val is not None:
            return default_val
        if s == a or s == b:
            return s
        print("Type", a, "or", b)

def body_brief(b):
    if b is None:
        return "(empty)"
    if b["type"] == "hanging":
        return "hanging m=" + str(b["m"]) + "kg"
    up = "up" if b["uphill_pos"] else "down"
    return "incline " + str(b["theta_deg"]) + "deg (+=" + up + ") m=" + str(b["m"]) + "kg"

def show_bodies(bodies):
    print("")
    print("---- Bodies A..I ----")
    for i in range(9):
        name = chr(ord("A") + i)
        print(str(i+1) + ".", name, ":", body_brief(bodies[i]))
    print("---------------------")
    print("")

# ----------------------------
# Create / Update body
# ----------------------------

def make_body(name):
    print("")
    print("Create/Update body", name)

    btype = ask_choice("Type (incline/hanging): ", "incline", "hanging", "incline")
    m = ask_float("Mass m (kg): ")
    mu_s = ask_float("mu_s (0 if none) [0]: ", 0)
    mu_k = ask_float("mu_k (0 if none) [0]: ", 0)

    theta_deg = 0.0
    uphill_pos = True

    if btype == "incline":
        theta_deg = ask_float("Incline angle theta (deg from horizontal): ")
        ud = ask_choice("Define + direction (up/down): ", "up", "down", "up")
        uphill_pos = (ud == "up")

    # Applied force
    F = ask_float("Applied force magnitude F (N) [0]: ", 0)
    F_dir = 1
    F_ang = 0.0

    if abs(F) > 1e-12:
        pm = ask_choice("Force along +axis or -axis? (+/-): ", "+", "-", "+")
        F_dir = 1 if pm == "+" else -1
        if btype == "incline":
            F_ang = ask_float("Force angle relative to surface deg (0=along, +=pull away) [0]: ", 0)
        else:
            F_ang = 0.0

    return {
        "name": name,
        "type": btype,
        "m": m,
        "mu_s": mu_s,
        "mu_k": mu_k,
        "theta_deg": theta_deg,
        "uphill_pos": uphill_pos,
        "F": F,
        "F_dir": F_dir,
        "F_ang": F_ang
    }

# ----------------------------
# Physics helpers
# ----------------------------

def weight_components_magnitudes_incline(b, g):
    theta = deg2rad(b["theta_deg"])
    m = b["m"]
    Px = m * g * math.sin(theta)
    Py = m * g * math.cos(theta)
    return Px, Py

def incline_W_components_signed(b, g):
    Px, Py = weight_components_magnitudes_incline(b, g)
    if b["uphill_pos"]:
        W_along = -Px
    else:
        W_along = Px
    W_into = Py
    return W_along, W_into

def applied_components(b):
    F = b["F"]
    if abs(F) < 1e-12:
        return 0.0, 0.0
    alpha = deg2rad(b["F_ang"])
    F_along = b["F_dir"] * F * math.cos(alpha)
    F_away = F * math.sin(alpha)
    return F_along, F_away

def normal_force(b, g):
    _, Py = incline_W_components_signed(b, g)
    _, F_away = applied_components(b)
    return Py - F_away

def single_accel(b, g):
    m = b["m"]

    if b["type"] == "hanging":
        W = m * g
        Fapp = b["F_dir"] * b["F"]
        a = (W + Fapp) / m
        return a, 0.0, 0.0, "hanging", 0.0, 0.0

    W_along, _ = incline_W_components_signed(b, g)
    Px, Py_mag = weight_components_magnitudes_incline(b, g)
    F_along, _ = applied_components(b)
    N = normal_force(b, g)

    N_eff = N if N > 0 else 0.0
    F_nofric = W_along + F_along

    motion_dir = sgn(F_nofric)
    if motion_dir == 0:
        motion_dir = 1

    f = -motion_dir * b["mu_k"] * N_eff
    a = (F_nofric + f) / m

    if sgn(a) != 0 and sgn(a) != motion_dir:
        motion_dir = sgn(a)
        f = -motion_dir * b["mu_k"] * N_eff
        a = (F_nofric + f) / m

    return a, N, f, "incline", Px, Py_mag

# ----------------------------
# Detailed printout
# ----------------------------

def body_details(b, g):
    print("")
    print("=== Body details ===")
    print("Type:", b["type"])
    print("m =", b["m"], "kg")
    print("mu_s =", b["mu_s"], "mu_k =", b["mu_k"])
    print("Applied F =", b["F"], "N")

    if b["type"] == "hanging":
        print("Axis: + is downward")
        print("Weight W =", b["m"] * g, "N (down)")
        print("Normal N = 0 (no surface)")
        print("Px/Py not applicable (no incline plane).")
        print("")
        return

    print("theta =", b["theta_deg"], "deg")
    print("+ direction is", ("uphill" if b["uphill_pos"] else "downhill"))

    Px, Py = weight_components_magnitudes_incline(b, g)
    W_along, _ = incline_W_components_signed(b, g)
    F_along, F_away = applied_components(b)
    N = normal_force(b, g)

    print("")
    print("Weight components (magnitudes):")
    print("Px = m g sin(theta) =", Px, "N  (parallel, downhill)")
    print("Py = m g cos(theta) =", Py, "N  (perpendicular, into plane)")
    print("")
    print("Signed forces relative to YOUR +axis:")
    print("W along +axis =", W_along, "N")
    print("Applied F along +axis =", F_along, "N")
    print("Applied F away from plane =", F_away, "N")
    print("")
    print("Normal force:")
    print("N =", N, "N")

    if N < 0:
        print("WARNING: N < 0 => would lose contact with surface.")
        N_eff = 0.0
    else:
        N_eff = N

    print("")
    print("Friction limits (using N >= 0):")
    print("|f_s|max =", b["mu_s"] * N_eff, "N")
    print("f_k magnitude =", b["mu_k"] * N_eff, "N")
    print("")

# ----------------------------
# Two-body rope solver
# ----------------------------

def two_body_rope(A, B, g):
    def drive_nofric(b):
        if b["type"] == "hanging":
            return b["m"] * g + b["F_dir"] * b["F"]
        W_along, _ = incline_W_components_signed(b, g)
        F_along, _ = applied_components(b)
        return W_along + F_along

    def F_noT(b, motion_dir):
        if b["type"] == "hanging":
            return b["m"] * g + b["F_dir"] * b["F"], 0.0, 0.0
        W_along, _ = incline_W_components_signed(b, g)
        F_along, _ = applied_components(b)
        N = normal_force(b, g)
        N_eff = N if N > 0 else 0.0
        f = -motion_dir * b["mu_k"] * N_eff
        return W_along + F_along + f, N, f

    guess = drive_nofric(A) + drive_nofric(B)
    motion_dir = sgn(guess)
    if motion_dir == 0:
        motion_dir = 1

    FA, _, _ = F_noT(A, motion_dir)
    FB, _, _ = F_noT(B, motion_dir)

    a = (FA + FB) / (A["m"] + B["m"])

    if sgn(a) != 0 and sgn(a) != motion_dir:
        motion_dir = sgn(a)
        FA, _, _ = F_noT(A, motion_dir)
        FB, _, _ = F_noT(B, motion_dir)
        a = (FA + FB) / (A["m"] + B["m"])

    T = FA - A["m"] * a
    return a, T

# ----------------------------
# Required force (horizontal, angled)
# ----------------------------

def required_force_horizontal(g):
    print("")
    print("=== Required force on horizontal surface ===")
    m = ask_float("m (kg): ")
    mu = ask_float("mu_k [0]: ", 0)
    a = ask_float("target acceleration a (m/s^2): ")
    ang = ask_float("force angle above horizontal (deg) [0]: ", 0)
    alpha = deg2rad(ang)

    motion = sgn(a)
    if motion == 0:
        motion = 1

    c = math.cos(alpha)
    s = math.sin(alpha)
    denom = c + motion * mu * s

    if abs(denom) < 1e-12:
        print("Cannot solve (bad angle/params; denominator ~ 0).")
        return

    F = (m * a + motion * mu * m * g) / denom
    print("Required force magnitude F =", F, "N")
    print("Apply along the desired motion direction.")
    print("")

# ----------------------------
# System acceleration for N bodies
# ----------------------------

def system_accel_multiple(bodies_list, g):
    total_F = 0.0
    total_m = 0.0

    guess = 0.0
    for b in bodies_list:
        if b["type"] == "hanging":
            guess += b["m"] * g + b["F_dir"] * b["F"]
        else:
            W_along, _ = incline_W_components_signed(b, g)
            F_along, _ = applied_components(b)
            guess += W_along + F_along

    motion_dir = sgn(guess)
    if motion_dir == 0:
        motion_dir = 1

    for b in bodies_list:
        m = b["m"]
        total_m += m

        if b["type"] == "hanging":
            F_net = m * g + b["F_dir"] * b["F"]
        else:
            W_along, _ = incline_W_components_signed(b, g)
            F_along, _ = applied_components(b)
            N = normal_force(b, g)
            N_eff = N if N > 0 else 0.0
            f = -motion_dir * b["mu_k"] * N_eff
            F_net = W_along + F_along + f

        total_F += F_net

    a = total_F / total_m

    if sgn(a) != 0 and sgn(a) != motion_dir:
        motion_dir = sgn(a)
        total_F = 0.0
        total_m = 0.0
        for b in bodies_list:
            m = b["m"]
            total_m += m
            if b["type"] == "hanging":
                F_net = m * g + b["F_dir"] * b["F"]
            else:
                W_along, _ = incline_W_components_signed(b, g)
                F_along, _ = applied_components(b)
                N = normal_force(b, g)
                N_eff = N if N > 0 else 0.0
                f = -motion_dir * b["mu_k"] * N_eff
                F_net = W_along + F_along + f
            total_F += F_net
        a = total_F / total_m

    return a

# ----------------------------
# Main program
# ----------------------------

def main():
    print("=== MULTI-BODY INCLINE SOLVER (TI-Nspire) ===")
    print("Stop anytime: Ctrl + C")
    g = ask_float("g (m/s^2) [9.81]: ", 9.81)

    bodies = [None] * 9

    while True:
        print("Menu")
        print("1 Add/Update body (A..I)")
        print("2 List bodies")
        print("3 Single-body acceleration (prints Px, Py for incline)")
        print("4 Two-body rope: acceleration + tension")
        print("5 Required force (horizontal, angled)")
        print("6 System acceleration (N bodies, same-accel)")
        print("7 Body details (Px, Py, N, friction limits)")
        print("0 Exit")

        ch = ask_int("Choose: ", 0, 7)

        if ch == 0:
            print("Bye.")
            break

        elif ch == 1:
            show_bodies(bodies)
            i = ask_int("Body number 1-9: ", 1, 9) - 1
            name = chr(ord("A") + i)
            bodies[i] = make_body(name)
            pause()

        elif ch == 2:
            show_bodies(bodies)
            pause()

        elif ch == 3:
            show_bodies(bodies)
            i = ask_int("Body number 1-9: ", 1, 9) - 1
            b = bodies[i]
            if b is None:
                print("Empty slot.")
            else:
                a, N, f, mode, Px, Py = single_accel(b, g)
                print("")
                print("Body", chr(ord("A")+i), ":", body_brief(b))
                print("a =", a, "m/s^2 along +axis")
                if mode == "incline":
                    print("Px =", Px, "N  (mg sin(theta), magnitude downhill)")
                    print("Py =", Py, "N  (mg cos(theta), magnitude into plane)")
                    print("N =", N, "N")
                    print("friction (along +axis) =", f, "N")
                    if N < 0:
                        print("WARNING: N < 0 => would lose contact with surface.")
                print("")
            pause()

        elif ch == 4:
            show_bodies(bodies)
            ia = ask_int("Body A number 1-9: ", 1, 9) - 1
            ib = ask_int("Body B number 1-9: ", 1, 9) - 1
            A = bodies[ia]
            B = bodies[ib]
            if A is None or B is None:
                print("One slot empty.")
            else:
                a, T = two_body_rope(A, B, g)
                print("")
                print("A:", body_brief(A))
                print("B:", body_brief(B))
                print("system a =", a, "m/s^2")
                print("tension T =", T, "N")
                print("If sign seems wrong, swap A/B or redefine + direction for incline bodies.")
                print("")
            pause()

        elif ch == 5:
            required_force_horizontal(g)
            pause()

        elif ch == 6:
            show_bodies(bodies)
            n = ask_int("How many bodies in the system (1-9): ", 1, 9)
            chosen = []
            ok = True

            for k in range(n):
                idx = ask_int("Select body number (1-9): ", 1, 9) - 1
                if bodies[idx] is None:
                    print("That body slot is empty. Cancelled.")
                    ok = False
                    break
                chosen.append(bodies[idx])

            if ok:
                a = system_accel_multiple(chosen, g)
                print("")
                print("System acceleration a =", a, "m/s^2")
                print("Interpreted along each chosen body's +axis definition.")
                print("")
            pause()

        elif ch == 7:
            show_bodies(bodies)
            i = ask_int("Body number 1-9: ", 1, 9) - 1
            b = bodies[i]
            if b is None:
                print("Empty slot.")
            else:
                body_details(b, g)
            pause()

main()
