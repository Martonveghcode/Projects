# ==========================================
# TI-Nspire CX II-T CAS Friendly LINE SOLVER
# - Stores up to 9 lines (A..I)
# - Accepts many input forms (including vector/parametric)
# - Converts to common forms
# - Computes intersections + distances
# (Menu style similar to your physics solver)
# ==========================================

import math

EPS = 1e-10
PI = 3.141592653589793

# ----------------------------
# UI helpers (same vibe)
# ----------------------------

def pause():
    input("\nPress ENTER to return to menu...")

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

def ask_choice(prompt, allowed, default_val=None):
    # allowed: list of strings
    while True:
        s = input(prompt).strip().lower()
        if s == "" and default_val is not None:
            return default_val
        for a in allowed:
            if s == a:
                return s
        print("Type one of:", ", ".join(allowed))

def _abs(x):
    return -x if x < 0 else x

def _is_zero(x):
    return _abs(x) < EPS

# ----------------------------
# Line core (store as Ax+By+C=0)
# canonicalize so sqrt(A^2+B^2)=1 and sign fixed
# ----------------------------

def canon_ABC(A, B, C):
    n = math.sqrt(A*A + B*B)
    if _is_zero(n):
        raise ValueError("Invalid line: A and B cannot both be 0.")
    A, B, C = A/n, B/n, C/n
    # fix sign: A>0 or (A==0 and B>0)
    if (A < -EPS) or (_is_zero(A) and B < -EPS):
        A, B, C = -A, -B, -C
    return A, B, C

def line_from_standard(A, B, C, name=""):
    A, B, C = canon_ABC(A, B, C)
    return {"name": name, "A": A, "B": B, "C": C}

def line_from_slope_intercept(m, b, name=""):
    # y = mx + b => mx - y + b = 0
    return line_from_standard(m, -1.0, b, name)

def line_from_point_slope(m, x1, y1, name=""):
    # y - y1 = m(x - x1) => mx - y + (y1 - m x1) = 0
    C = y1 - m*x1
    return line_from_standard(m, -1.0, C, name)

def line_from_two_points(x1, y1, x2, y2, name=""):
    if _is_zero(x1-x2) and _is_zero(y1-y2):
        raise ValueError("Two-point form needs two distinct points.")
    dx = x2 - x1
    dy = y2 - y1
    # normal (dy, -dx): dy(x-x1) - dx(y-y1)=0
    A = dy
    B = -dx
    C = dx*y1 - dy*x1
    return line_from_standard(A, B, C, name)

def line_from_intercept(a, b, name=""):
    # x/a + y/b = 1 => (1/a)x + (1/b)y - 1 = 0
    if _is_zero(a) or _is_zero(b):
        raise ValueError("Intercept form needs nonzero a and b.")
    return line_from_standard(1.0/a, 1.0/b, -1.0, name)

def line_from_vector(x0, y0, dx, dy, name=""):
    # (x,y)=(x0,y0)+t(dx,dy)
    if _is_zero(dx) and _is_zero(dy):
        raise ValueError("Vector form needs a nonzero direction (dx,dy).")
    # normal (dy, -dx)
    A = dy
    B = -dx
    C = dx*y0 - dy*x0
    return line_from_standard(A, B, C, name)

def line_from_normal_point(nx, ny, x0, y0, name=""):
    # n·( (x,y) - (x0,y0) ) = 0 => nx x + ny y + C = 0
    # C = -(nx x0 + ny y0)
    if _is_zero(nx) and _is_zero(ny):
        raise ValueError("Normal vector cannot be (0,0).")
    C = -(nx*x0 + ny*y0)
    return line_from_standard(nx, ny, C, name)

# ----------------------------
# Derived properties / operations
# ----------------------------

def point_on_line(L):
    A, B, C = L["A"], L["B"], L["C"]
    if not _is_zero(B):
        return (0.0, -C/B)
    else:
        return (-C/A, 0.0)

def direction_of_line(L):
    # for Ax+By+C=0, direction vector can be (B, -A)
    return (L["B"], -L["A"])

def parallel(L1, L2):
    A1, B1 = L1["A"], L1["B"]
    A2, B2 = L2["A"], L2["B"]
    return _is_zero(A1*B2 - A2*B1)

def same_line(L1, L2):
    return (_is_zero(L1["A"]-L2["A"]) and
            _is_zero(L1["B"]-L2["B"]) and
            _is_zero(L1["C"]-L2["C"]))

def intersection(L1, L2):
    A1, B1, C1 = L1["A"], L1["B"], L1["C"]
    A2, B2, C2 = L2["A"], L2["B"], L2["C"]
    D = A1*B2 - A2*B1
    if _is_zero(D):
        return None
    x = (B1*C2 - B2*C1) / D
    y = (C1*A2 - C2*A1) / D
    return (x, y)

def distance_point_line(x, y, L):
    # canonical => distance = |Ax+By+C|
    return _abs(L["A"]*x + L["B"]*y + L["C"])

def distance_between_lines(L1, L2):
    # if intersect => 0; if parallel => |C2-C1| (canonical + aligned sign)
    if not parallel(L1, L2):
        return 0.0
    if same_line(L1, L2):
        return 0.0
    return _abs(L2["C"] - L1["C"])

# ----------------------------
# “6 forms” display (+ vector)
# We show:
# 1 slope-intercept
# 2 point-slope
# 3 standard Ax+By+C=0
# 4 general Ax+By=C (rearranged)
# 5 intercept x/a + y/b = 1 (when possible)
# 6 two-point
# + vector/parametric
# ----------------------------

def show_forms(L):
    A, B, C = L["A"], L["B"], L["C"]
    x0, y0 = point_on_line(L)
    dx, dy = direction_of_line(L)

    print("")
    print("=== Line", L["name"], "===")

    # 3) Standard
    print("3) Standard:  A x + B y + C = 0")
    print("   A={:.10g}, B={:.10g}, C={:.10g}".format(A, B, C))

    # 4) General: Ax + By = D
    print("4) General:   A x + B y = D")
    print("   D={:.10g}".format(-C))

    # 1) Slope-intercept + 2) Point-slope
    if not _is_zero(B):
        m = -A/B
        b = -C/B
        print("1) Slope-intercept:  y = m x + b")
        print("   m={:.10g}, b={:.10g}".format(m, b))
        print("2) Point-slope:      y - y1 = m(x - x1)")
        print("   y - ({:.10g}) = ({:.10g})(x - ({:.10g}))".format(y0, m, x0))
    else:
        # vertical line: x = constant
        xv = -C/A
        print("1) Slope-intercept:  (not possible: vertical line)")
        print("2) Point-slope:      (not in y= form; vertical)")
        print("   Vertical form:    x = {:.10g}".format(xv))

    # 5) Intercept form (needs A,B,C all nonzero)
    if (not _is_zero(A)) and (not _is_zero(B)) and (not _is_zero(C)):
        a = -C/A
        b_int = -C/B
        print("5) Intercept:        x/a + y/b = 1")
        print("   a={:.10g}, b={:.10g}".format(a, b_int))
    else:
        print("5) Intercept:        (not available for this line)")

    # 6) Two-point (one convenient choice)
    x1, y1 = x0 + dx, y0 + dy
    print("6) Two-point (one option): through P1 and P2")
    print("   P1=({:.10g},{:.10g})".format(x0, y0))
    print("   P2=({:.10g},{:.10g})".format(x1, y1))

    # Vector/parametric
    print("Vector/Parametric:")
    print("   (x,y) = ({:.10g},{:.10g}) + t({:.10g},{:.10g})".format(x0, y0, dx, dy))
    print("")

# ----------------------------
# Storage: 9 slots A..I
# ----------------------------

def line_brief(L):
    if L is None:
        return "(empty)"
    # show standard quickly
    return "Ax+By+C=0 with A={:.4g}, B={:.4g}, C={:.4g}".format(L["A"], L["B"], L["C"])

def show_lines(lines):
    print("")
    print("---- Lines A..I ----")
    for i in range(9):
        name = chr(ord("A")+i)
        L = lines[i]
        if L is None:
            print(str(i+1) + ".", name, ":", "(empty)")
        else:
            print(str(i+1) + ".", name, ":", line_brief(L))
    print("--------------------")
    print("")

# ----------------------------
# Create / Update line
# ----------------------------

def make_line(name):
    print("")
    print("Create/Update line", name)
    print("Choose input form:")
    print("1 Slope-intercept: y = m x + b")
    print("2 Point-slope:     y - y1 = m(x - x1)")
    print("3 Standard:        A x + B y + C = 0")
    print("4 Intercept:       x/a + y/b = 1")
    print("5 Two-point:       through (x1,y1) and (x2,y2)")
    print("6 Vector:          (x,y)=(x0,y0)+t(dx,dy)")
    print("7 Normal-point:    n=(nx,ny) and point (x0,y0)")

    ch = ask_int("Form (1-7): ", 1, 7)

    try:
        if ch == 1:
            m = ask_float("m: ")
            b = ask_float("b: ")
            return line_from_slope_intercept(m, b, name)

        elif ch == 2:
            m = ask_float("m: ")
            x1 = ask_float("x1: ")
            y1 = ask_float("y1: ")
            return line_from_point_slope(m, x1, y1, name)

        elif ch == 3:
            A = ask_float("A: ")
            B = ask_float("B: ")
            C = ask_float("C: ")
            return line_from_standard(A, B, C, name)

        elif ch == 4:
            a = ask_float("a (x-intercept): ")
            b = ask_float("b (y-intercept): ")
            return line_from_intercept(a, b, name)

        elif ch == 5:
            x1 = ask_float("x1: ")
            y1 = ask_float("y1: ")
            x2 = ask_float("x2: ")
            y2 = ask_float("y2: ")
            return line_from_two_points(x1, y1, x2, y2, name)

        elif ch == 6:
            x0 = ask_float("x0: ")
            y0 = ask_float("y0: ")
            dx = ask_float("dx: ")
            dy = ask_float("dy: ")
            return line_from_vector(x0, y0, dx, dy, name)

        else:
            nx = ask_float("nx: ")
            ny = ask_float("ny: ")
            x0 = ask_float("x0: ")
            y0 = ask_float("y0: ")
            return line_from_normal_point(nx, ny, x0, y0, name)

    except Exception as e:
        print("Could not create line:", e)
        return None

# ----------------------------
# Menu actions
# ----------------------------

def do_intersection(lines):
    show_lines(lines)
    i = ask_int("Line 1 number (1-9): ", 1, 9) - 1
    j = ask_int("Line 2 number (1-9): ", 1, 9) - 1
    L1 = lines[i]
    L2 = lines[j]
    if L1 is None or L2 is None:
        print("One slot empty.")
        return

    P = intersection(L1, L2)
    print("")
    if P is None:
        if same_line(L1, L2):
            print("Intersection: infinitely many points (same line).")
        else:
            print("Intersection: none (parallel lines).")
    else:
        print("Intersection point:")
        print("x = {:.10g}".format(P[0]))
        print("y = {:.10g}".format(P[1]))
    print("")

def do_distance_lines(lines):
    show_lines(lines)
    i = ask_int("Line 1 number (1-9): ", 1, 9) - 1
    j = ask_int("Line 2 number (1-9): ", 1, 9) - 1
    L1 = lines[i]
    L2 = lines[j]
    if L1 is None or L2 is None:
        print("One slot empty.")
        return
    d = distance_between_lines(L1, L2)
    print("")
    print("Distance between", chr(ord("A")+i), "and", chr(ord("A")+j), "=", d)
    if parallel(L1, L2) and not same_line(L1, L2):
        print("(parallel lines)")
    elif same_line(L1, L2):
        print("(same line)")
    else:
        print("(they intersect => distance 0)")
    print("")

def do_distance_point(lines):
    show_lines(lines)
    i = ask_int("Line number (1-9): ", 1, 9) - 1
    L = lines[i]
    if L is None:
        print("Empty slot.")
        return
    x = ask_float("Point x: ")
    y = ask_float("Point y: ")
    d = distance_point_line(x, y, L)
    print("")
    print("Distance from ({:.10g},{:.10g}) to line {} = {:.10g}".format(x, y, chr(ord("A")+i), d))
    print("")

def do_show_forms(lines):
    show_lines(lines)
    i = ask_int("Line number (1-9): ", 1, 9) - 1
    L = lines[i]
    if L is None:
        print("Empty slot.")
        return
    show_forms(L)

# ----------------------------
# Main program
# ----------------------------

def main():
    print("=== MULTI-LINE SOLVER (TI-Nspire) ===")
    print("Stop anytime: Ctrl + C")
    lines = [None] * 9

    while True:
        print("Menu")
        print("1 Add/Update line (A..I)")
        print("2 List lines")
        print("3 Show line conversions (all forms + vector)")
        print("4 Intersection of two lines")
        print("5 Distance between two lines")
        print("6 Distance from point to line")
        print("0 Exit")

        ch = ask_int("Choose: ", 0, 6)

        if ch == 0:
            print("Bye.")
            break

        elif ch == 1:
            show_lines(lines)
            i = ask_int("Line number 1-9: ", 1, 9) - 1
            name = chr(ord("A")+i)
            L = make_line(name)
            if L is not None:
                lines[i] = L
                print("Saved line", name)
            pause()

        elif ch == 2:
            show_lines(lines)
            pause()

        elif ch == 3:
            do_show_forms(lines)
            pause()

        elif ch == 4:
            do_intersection(lines)
            pause()

        elif ch == 5:
            do_distance_lines(lines)
            pause()

        elif ch == 6:
            do_distance_point(lines)
            pause()

main()
