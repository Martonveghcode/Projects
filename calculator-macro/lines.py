# TI-Nspire CX II-T CAS (TI-Python)
# Line toolbox: define multiple lines and convert between forms + intersections/distances.

from math import sqrt

EPS = 1e-10

def _abs(x):
    return -x if x < 0 else x

def _is_zero(x):
    return _abs(x) < EPS

def _canon_ABC(A, B, C):
    """
    Canonicalize Ax + By + C = 0 so that:
      - sqrt(A^2 + B^2) == 1
      - (A > 0) or (A == 0 and B > 0)
    This makes distances easy and parallel checks stable.
    """
    n = sqrt(A*A + B*B)
    if _is_zero(n):
        raise ValueError("Invalid line: A and B cannot both be 0.")
    A, B, C = A/n, B/n, C/n

    # Fix sign to have a consistent orientation
    if (A < -EPS) or (_is_zero(A) and B < -EPS):
        A, B, C = -A, -B, -C
    return A, B, C

def _parallel(L1, L2):
    A1, B1, _ = L1["A"], L1["B"], L1["C"]
    A2, B2, _ = L2["A"], L2["B"], L2["C"]
    # cross of normals ~ 0 => parallel
    return _is_zero(A1*B2 - A2*B1)

def _same_line(L1, L2):
    # With canonical normalization, same line <=> A,B,C all match (approximately)
    return (_is_zero(L1["A"]-L2["A"]) and
            _is_zero(L1["B"]-L2["B"]) and
            _is_zero(L1["C"]-L2["C"]))

def line_from_standard(A, B, C, name=""):
    A, B, C = _canon_ABC(A, B, C)
    return {"name": name, "A": A, "B": B, "C": C}

def line_from_slope_intercept(m, b, name=""):
    # y = m x + b  =>  m x - y + b = 0
    return line_from_standard(m, -1.0, b, name)

def line_from_point_slope(m, x1, y1, name=""):
    # y - y1 = m(x - x1) => m x - y + (y1 - m x1) = 0
    C = y1 - m*x1
    return line_from_standard(m, -1.0, C, name)

def line_from_two_points(x1, y1, x2, y2, name=""):
    if _is_zero(x1-x2) and _is_zero(y1-y2):
        raise ValueError("Two-point form needs two distinct points.")
    # Direction (dx, dy) = (x2-x1, y2-y1)
    dx, dy = x2-x1, y2-y1
    # Normal can be (dy, -dx) so that dy(x-x1) - dx(y-y1)=0
    # => dy x - dx y + (dx y1 - dy x1) = 0
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
    if _is_zero(dx) and _is_zero(dy):
        raise ValueError("Vector form needs a nonzero direction (dx, dy).")
    # Points: (x, y) = (x0, y0) + t(dx, dy)
    # Normal n = (dy, -dx), line: dy(x-x0) - dx(y-y0)=0
    A = dy
    B = -dx
    C = dx*y0 - dy*x0
    return line_from_standard(A, B, C, name)

def point_on_line(L):
    """
    Return a convenient point on the line Ax + By + C = 0.
    Choose x=0 if possible, else y=0.
    """
    A, B, C = L["A"], L["B"], L["C"]
    if not _is_zero(B):
        x, y = 0.0, -C/B
    else:
        # B ~ 0 => A != 0
        x, y = -C/A, 0.0
    return (x, y)

def direction_of_line(L):
    """
    For Ax+By+C=0, a direction vector is (B, -A).
    """
    A, B = L["A"], L["B"]
    return (B, -A)

def intersection(L1, L2):
    """
    Solve:
      A1 x + B1 y + C1 = 0
      A2 x + B2 y + C2 = 0
    """
    A1, B1, C1 = L1["A"], L1["B"], L1["C"]
    A2, B2, C2 = L2["A"], L2["B"], L2["C"]

    D = A1*B2 - A2*B1
    if _is_zero(D):
        return None  # parallel or same line
    x = (B1*C2 - B2*C1) / D
    y = (C1*A2 - C2*A1) / D
    return (x, y)

def distance_point_line(x, y, L):
    # With canonical A,B: distance = |Ax+By+C|
    return _abs(L["A"]*x + L["B"]*y + L["C"])

def distance_between_lines(L1, L2):
    """
    If not parallel -> intersect -> distance 0
    If parallel -> |C2 - C1| (because canonical normalization and aligned sign)
    """
    if not _parallel(L1, L2):
        return 0.0
    if _same_line(L1, L2):
        return 0.0
    return _abs(L2["C"] - L1["C"])

def pretty_forms(L):
    A, B, C = L["A"], L["B"], L["C"]
    x0, y0 = point_on_line(L)
    dx, dy = direction_of_line(L)

    out = []
    out.append("Standard:  A x + B y + C = 0")
    out.append("  A={:.10g}, B={:.10g}, C={:.10g}".format(A, B, C))

    # Slope-intercept if possible (B != 0 => y = (-A/B)x + (-C/B))
    if not _is_zero(B):
        m = -A/B
        b = -C/B
        out.append("Slope-intercept:  y = m x + b")
        out.append("  m={:.10g}, b={:.10g}".format(m, b))
        out.append("Point-slope (using point x0,y0):  y - y0 = m(x - x0)")
        out.append("  y - ({:.10g}) = ({:.10g}) (x - ({:.10g}))".format(y0, m, x0))
    else:
        out.append("Slope-intercept:  not possible (vertical line)")

    # Two-point (use x0,y0 and x0+dx,y0+dy)
    x1, y1 = x0 + dx, y0 + dy
    out.append("Two-point (one option):")
    out.append("  P1=({:.10g},{:.10g}), P2=({:.10g},{:.10g})".format(x0, y0, x1, y1))

    # Intercept form if A and B both nonzero:
    # Ax + By + C = 0 => x/(-C/A) + y/(-C/B) = 1 when C != 0
    if (not _is_zero(A)) and (not _is_zero(B)) and (not _is_zero(C)):
        a = -C/A
        b_int = -C/B
        out.append("Intercept form:  x/a + y/b = 1")
        out.append("  a={:.10g}, b={:.10g}".format(a, b_int))
    else:
        out.append("Intercept form:  not available (needs A,B,C all nonzero)")

    # Vector/parametric form:
    out.append("Vector/Parametric:")
    out.append("  (x,y) = ({:.10g},{:.10g}) + t({:.10g},{:.10g})".format(x0, y0, dx, dy))

    return "\n".join(out)

# ---------------- UI / menu ----------------

def _get_num(prompt):
    while True:
        try:
            return float(input(prompt))
        except:
            print("Please enter a number.")

def add_line(lines):
    print("\nAdd a line (choose form):")
    print(" 1) Slope-intercept (y = m x + b)")
    print(" 2) Point-slope (y - y1 = m(x - x1))")
    print(" 3) Standard (A x + B y + C = 0)")
    print(" 4) Intercept (x/a + y/b = 1)")
    print(" 5) Two-point (through two points)")
    print(" 6) Vector/parametric (x,y)=(x0,y0)+t(dx,dy)")
    choice = input("Form (1-6): ")

    name = input("Name for this line (e.g. L1): ")
    if name == "":
        name = "L{}".format(len(lines)+1)

    try:
        if choice == "1":
            m = _get_num("m: ")
            b = _get_num("b: ")
            L = line_from_slope_intercept(m, b, name)
        elif choice == "2":
            m = _get_num("m: ")
            x1 = _get_num("x1: ")
            y1 = _get_num("y1: ")
            L = line_from_point_slope(m, x1, y1, name)
        elif choice == "3":
            A = _get_num("A: ")
            B = _get_num("B: ")
            C = _get_num("C: ")
            L = line_from_standard(A, B, C, name)
        elif choice == "4":
            a = _get_num("a (x-intercept): ")
            b_int = _get_num("b (y-intercept): ")
            L = line_from_intercept(a, b_int, name)
        elif choice == "5":
            x1 = _get_num("x1: ")
            y1 = _get_num("y1: ")
            x2 = _get_num("x2: ")
            y2 = _get_num("y2: ")
            L = line_from_two_points(x1, y1, x2, y2, name)
        elif choice == "6":
            x0 = _get_num("x0: ")
            y0 = _get_num("y0: ")
            dx = _get_num("dx: ")
            dy = _get_num("dy: ")
            L = line_from_vector(x0, y0, dx, dy, name)
        else:
            print("Invalid choice.")
            return

        lines.append(L)
        print("Added:", L["name"])
    except Exception as e:
        print("Could not add line:", e)

def list_lines(lines):
    print("\nStored lines:")
    if len(lines) == 0:
        print(" (none)")
        return
    for i, L in enumerate(lines):
        print(" {}: {}".format(i, L["name"]))

def show_line(lines):
    if len(lines) == 0:
        print("\nNo lines stored.")
        return
    list_lines(lines)
    i = int(_get_num("Index of line to show: "))
    if i < 0 or i >= len(lines):
        print("Invalid index.")
        return
    L = lines[i]
    print("\n=== {} ===".format(L["name"]))
    print(pretty_forms(L))

def pick_two(lines):
    if len(lines) < 2:
        print("\nNeed at least 2 lines.")
        return None, None
    list_lines(lines)
    i = int(_get_num("First line index: "))
    j = int(_get_num("Second line index: "))
    if i < 0 or i >= len(lines) or j < 0 or j >= len(lines):
        print("Invalid index.")
        return None, None
    return lines[i], lines[j]

def do_intersection(lines):
    L1, L2 = pick_two(lines)
    if L1 is None:
        return
    P = intersection(L1, L2)
    print("")
    if P is None:
        if _same_line(L1, L2):
            print("Intersection: infinitely many points (same line).")
        else:
            print("Intersection: none (parallel lines).")
    else:
        print("Intersection point: ({:.10g}, {:.10g})".format(P[0], P[1]))

def do_distance_lines(lines):
    L1, L2 = pick_two(lines)
    if L1 is None:
        return
    d = distance_between_lines(L1, L2)
    print("\nDistance between {} and {}: {:.10g}".format(L1["name"], L2["name"], d))

def do_distance_point(lines):
    if len(lines) == 0:
        print("\nNo lines stored.")
        return
    list_lines(lines)
    i = int(_get_num("Line index: "))
    if i < 0 or i >= len(lines):
        print("Invalid index.")
        return
    x = _get_num("Point x: ")
    y = _get_num("Point y: ")
    d = distance_point_line(x, y, lines[i])
    print("\nDistance from ({:.10g},{:.10g}) to {}: {:.10g}".format(x, y, lines[i]["name"], d))

def main():
    lines = []
    while True:
        print("\n--- LINE TOOLBOX ---")
        print("1) Add a line")
        print("2) List lines")
        print("3) Show line in all forms")
        print("4) Intersection of two lines")
        print("5) Distance between two lines")
        print("6) Distance from point to line")
        print("0) Quit")
        c = input("Choice: ")

        if c == "1":
            add_line(lines)
        elif c == "2":
            list_lines(lines)
        elif c == "3":
            show_line(lines)
        elif c == "4":
            do_intersection(lines)
        elif c == "5":
            do_distance_lines(lines)
        elif c == "6":
            do_distance_point(lines)
        elif c == "0":
            break
        else:
            print("Invalid choice.")
