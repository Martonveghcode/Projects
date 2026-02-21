# TI-Nspire CX II-T CAS (Python) — Geometría Analítica “todo-en-uno”
# Menu tool that covers the items on your sheet:
# - Line forms: vector / parametric / symmetric / slope-intercept / point-slope / general
# - Haz de rectas (pencil through a point): K(x-x0)+K'(y-y0)=0
# - Distances: point-point, point-line
# - Midpoint, symmetry of a point w.r.t. another point
# - 3 points aligned (collinear)
# - Angles between lines
# - Relative position of two lines (parallel / coincident / intersect)
# - Triangle: centroid (baricentro), circumcenter (circuncentro), orthocenter (ortocentro)
#
# Notes:
# - Uses floats; you can type fractions like 1/3.
# - For vertical lines, slope form is shown as x = constant.

import math

# ------------------ numeric parsing ------------------
def num(s: str) -> float:
    """Parse numbers like 3, -2.5, 1/3, (7-1)/2. Restrict to safe chars."""
    s = s.strip()
    allowed = set("0123456789+-*/(). ")
    if any(ch not in allowed for ch in s):
        raise ValueError("Invalid characters. Use numbers and +-*/(). only.")
    return float(eval(s, {"__builtins__": None}, {}))

def fmt(x: float) -> str:
    if abs(x) < 1e-12:
        x = 0.0
    if abs(x - round(x)) < 1e-10:
        return str(int(round(x)))
    return "{:.10g}".format(x)

# ------------------ geometry helpers ------------------
def dist_pp(x1,y1,x2,y2):
    return math.hypot(x2-x1, y2-y1)

def midpoint(x1,y1,x2,y2):
    return ( (x1+x2)/2.0, (y1+y2)/2.0 )

def sym_point_about_point(x,y, x0,y0):
    # reflection of (x,y) about (x0,y0)
    return (2*x0 - x, 2*y0 - y)

def line_general_from_point_dir(x0,y0, dx,dy):
    # normal n=(dy,-dx): A=dy, B=-dx, C=-(Ax0+By0)
    A = dy
    B = -dx
    C = -(A*x0 + B*y0)
    return A,B,C

def line_point_dir_from_general(A,B,C):
    if abs(A) < 1e-12 and abs(B) < 1e-12:
        raise ValueError("Invalid: A and B cannot both be 0.")
    # pick point
    if abs(B) > 1e-12:
        x0 = 0.0
        y0 = -C/B
    else:
        y0 = 0.0
        x0 = -C/A
    # direction perpendicular to normal (A,B)
    dx,dy = -B, A
    return x0,y0,dx,dy

def slope_intercept_from_point_dir(x0,y0, dx,dy):
    if abs(dx) < 1e-12:
        return None, x0  # vertical => x = const (store const in "b" slot)
    m = dy/dx
    b = y0 - m*x0
    return m,b

def point_slope_from_point_dir(x0,y0, dx,dy):
    if abs(dx) < 1e-12:
        return None, x0  # vertical x = const
    m = dy/dx
    return m,(x0,y0)

def symmetric_form_str(x0,y0, dx,dy):
    if abs(dx) < 1e-12:
        return f"x = {fmt(x0)}"
    if abs(dy) < 1e-12:
        return f"y = {fmt(y0)}"
    return f"(x - {fmt(x0)})/({fmt(dx)}) = (y - {fmt(y0)})/({fmt(dy)})"

def line_from_two_points(x1,y1,x2,y2):
    dx = x2-x1
    dy = y2-y1
    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        raise ValueError("Points must be distinct.")
    return x1,y1,dx,dy

def dist_point_line_general(x,y,A,B,C):
    return abs(A*x + B*y + C)/math.hypot(A,B)

def collinear(x1,y1,x2,y2,x3,y3):
    # area*2 = determinant
    det = (x2-x1)*(y3-y1) - (y2-y1)*(x3-x1)
    return abs(det) < 1e-10, det

def angle_between_lines_dir(dx1,dy1, dx2,dy2):
    # angle between directions
    dot = dx1*dx2 + dy1*dy2
    n1 = math.hypot(dx1,dy1)
    n2 = math.hypot(dx2,dy2)
    if n1 < 1e-12 or n2 < 1e-12:
        raise ValueError("Invalid direction.")
    c = max(-1.0, min(1.0, dot/(n1*n2)))
    ang = math.degrees(math.acos(c))
    # usually take acute angle:
    if ang > 90:
        ang = 180 - ang
    return ang

def intersect_general(A1,B1,C1, A2,B2,C2):
    det = A1*B2 - A2*B1
    if abs(det) < 1e-12:
        # parallel or coincident
        # check proportionality with C
        # if A1:B1:C1 proportional to A2:B2:C2 => coincident
        # handle zero cases robustly by using cross products:
        if abs(A1*C2 - A2*C1) < 1e-10 and abs(B1*C2 - B2*C1) < 1e-10:
            return None, "coincident"
        return None, "parallel"
    x = (B1*C2 - B2*C1)/det
    y = (C1*A2 - C2*A1)/det
    return (x,y), "intersect"

# ------------------ triangle centers ------------------
def centroid(x1,y1,x2,y2,x3,y3):
    return ((x1+x2+x3)/3.0, (y1+y2+y3)/3.0)

def perpendicular_bisector_general(x1,y1,x2,y2):
    # midpoint M, normal along segment direction (dx,dy)
    mx,my = midpoint(x1,y1,x2,y2)
    dx = x2-x1
    dy = y2-y1
    # line through M perpendicular to segment => direction is (-dy, dx)
    # general from point+dir:
    A,B,C = line_general_from_point_dir(mx,my, -dy, dx)
    return A,B,C

def altitude_general(vertex, other1, other2):
    # altitude from vertex V to line through other1->other2
    vx,vy = vertex
    x1,y1 = other1
    x2,y2 = other2
    dx = x2-x1
    dy = y2-y1
    # altitude direction is perpendicular to side direction => direction = (-dy, dx)
    A,B,C = line_general_from_point_dir(vx,vy, -dy, dx)
    return A,B,C

def circumcenter(x1,y1,x2,y2,x3,y3):
    # intersection of perpendicular bisectors of (1,2) and (1,3)
    L12 = perpendicular_bisector_general(x1,y1,x2,y2)
    L13 = perpendicular_bisector_general(x1,y1,x3,y3)
    p, kind = intersect_general(*L12, *L13)
    if kind != "intersect":
        raise ValueError("Circumcenter undefined (points may be collinear).")
    return p

def orthocenter(x1,y1,x2,y2,x3,y3):
    # intersection of two altitudes
    alt1 = altitude_general((x1,y1),(x2,y2),(x3,y3))
    alt2 = altitude_general((x2,y2),(x1,y1),(x3,y3))
    p, kind = intersect_general(*alt1, *alt2)
    if kind != "intersect":
        raise ValueError("Orthocenter undefined (points may be collinear).")
    return p

# ------------------ line converter (6 forms) ------------------
def show_all_forms(x0,y0, dx,dy):
    A,B,C = line_general_from_point_dir(x0,y0, dx,dy)
    m,b = slope_intercept_from_point_dir(x0,y0, dx,dy)

    print("\n--- 1) Vector ---")
    print(f"r = ({fmt(x0)},{fmt(y0)}) + t({fmt(dx)},{fmt(dy)})")

    print("\n--- 2) Parametric ---")
    print(f"x = {fmt(x0)} + t*{fmt(dx)}")
    print(f"y = {fmt(y0)} + t*{fmt(dy)}")

    print("\n--- 3) Symmetric ---")
    print(symmetric_form_str(x0,y0, dx,dy))

    print("\n--- 4) Slope–Intercept ---")
    if m is None:
        print(f"x = {fmt(b)}")
    else:
        print(f"y = {fmt(m)}x + {fmt(b)}")

    print("\n--- 5) Point–Slope ---")
    if m is None:
        print(f"x = {fmt(b)}")
    else:
        print(f"y - {fmt(y0)} = {fmt(m)}(x - {fmt(x0)})")

    print("\n--- 6) General ---")
    print(f"{fmt(A)}x + {fmt(B)}y + {fmt(C)} = 0")

def input_point(prompt="Point"):
    x = num(input(f"{prompt} x = "))
    y = num(input(f"{prompt} y = "))
    return x,y

def input_line_by_form():
    print("\nLine input form:")
    print("1 Vector/Param/Symmetric by (x0,y0,dx,dy)")
    print("2 Two points (P1,P2)")
    print("3 General (A,B,C)")
    choice = input("Choose 1/2/3: ").strip()
    if choice == "1":
        x0 = num(input("x0 = ")); y0 = num(input("y0 = "))
        dx = num(input("dx = ")); dy = num(input("dy = "))
        if abs(dx) < 1e-12 and abs(dy) < 1e-12:
            raise ValueError("Direction cannot be (0,0).")
        return x0,y0,dx,dy
    if choice == "2":
        x1,y1 = input_point("P1")
        x2,y2 = input_point("P2")
        return line_from_two_points(x1,y1,x2,y2)
    if choice == "3":
        A = num(input("A = ")); B = num(input("B = ")); C = num(input("C = "))
        return line_point_dir_from_general(A,B,C)
    raise ValueError("Invalid choice.")

# ------------------ main menu ------------------
def main():
    while True:
        print("\n==============================")
        print(" GEOMETRIA ANALITICA (TI)")
        print("==============================")
        print("1) Convert line (6 forms)")
        print("2) Haz de rectas through point (K,K')")
        print("3) Distance: point-point")
        print("4) Distance: point-line")
        print("5) Midpoint of two points")
        print("6) Symmetry of a point about a point")
        print("7) 3 points aligned?")
        print("8) Angle between two lines")
        print("9) Position of two lines + intersection")
        print("10) Triangle centers (centroid/circum/ortho)")
        print("0) Exit")
        op = input("Option: ").strip()

        try:
            if op == "0":
                return

            elif op == "1":
                print("\nInput line as point+direction (from any form):")
                x0,y0,dx,dy = input_line_by_form()
                show_all_forms(x0,y0,dx,dy)

            elif op == "2":
                print("\nHaz de rectas: K(x-x0)+K'(y-y0)=0")
                x0 = num(input("x0 = ")); y0 = num(input("y0 = "))
                K = num(input("K = ")); Kp = num(input("K' = "))
                # general: Kx + K'y - (Kx0 + K'y0)=0
                A = K; B = Kp; C = -(K*x0 + Kp*y0)
                print("\nGeneral form of the chosen line:")
                print(f"{fmt(A)}x + {fmt(B)}y + {fmt(C)} = 0")
                # direction is (-B, A)
                dx,dy = -B, A
                show_all_forms(x0,y0,dx,dy)

            elif op == "3":
                x1,y1 = input_point("P1")
                x2,y2 = input_point("P2")
                d = dist_pp(x1,y1,x2,y2)
                print(f"Distance = {fmt(d)}")

            elif op == "4":
                x,y = input_point("Point")
                print("\nLine:")
                x0,y0,dx,dy = input_line_by_form()
                A,B,C = line_general_from_point_dir(x0,y0,dx,dy)
                d = dist_point_line_general(x,y,A,B,C)
                print(f"Distance point-line = {fmt(d)}")

            elif op == "5":
                x1,y1 = input_point("P1")
                x2,y2 = input_point("P2")
                mx,my = midpoint(x1,y1,x2,y2)
                print(f"Midpoint M = ({fmt(mx)},{fmt(my)})")

            elif op == "6":
                x,y = input_point("Point A")
                x0,y0 = input_point("Center (x0,y0)")
                xs,ys = sym_point_about_point(x,y,x0,y0)
                print(f"Symmetric A' = ({fmt(xs)},{fmt(ys)})")

            elif op == "7":
                x1,y1 = input_point("A")
                x2,y2 = input_point("B")
                x3,y3 = input_point("C")
                ok, det = collinear(x1,y1,x2,y2,x3,y3)
                print("Collinear?" , "YES" if ok else "NO")
                print(f"det = {fmt(det)} (0 means aligned)")

            elif op == "8":
                print("\nLine 1:")
                x01,y01,dx1,dy1 = input_line_by_form()
                print("\nLine 2:")
                x02,y02,dx2,dy2 = input_line_by_form()
                ang = angle_between_lines_dir(dx1,dy1,dx2,dy2)
                print(f"Acute angle (deg) = {fmt(ang)}")

            elif op == "9":
                print("\nLine 1:")
                x01,y01,dx1,dy1 = input_line_by_form()
                A1,B1,C1 = line_general_from_point_dir(x01,y01,dx1,dy1)
                print("\nLine 2:")
                x02,y02,dx2,dy2 = input_line_by_form()
                A2,B2,C2 = line_general_from_point_dir(x02,y02,dx2,dy2)

                p, kind = intersect_general(A1,B1,C1,A2,B2,C2)
                print("\nPosition:", kind.upper())
                if p:
                    print(f"Intersection P = ({fmt(p[0])},{fmt(p[1])})")

            elif op == "10":
                print("\nTriangle points A,B,C:")
                x1,y1 = input_point("A")
                x2,y2 = input_point("B")
                x3,y3 = input_point("C")
                ok, _ = collinear(x1,y1,x2,y2,x3,y3)
                if ok:
                    print("Error: points are collinear. No triangle.")
                    continue

                g = centroid(x1,y1,x2,y2,x3,y3)
                o = circumcenter(x1,y1,x2,y2,x3,y3)
                h = orthocenter(x1,y1,x2,y2,x3,y3)

                print(f"Centroid G = ({fmt(g[0])},{fmt(g[1])})")
                print(f"Circumcenter O = ({fmt(o[0])},{fmt(o[1])})")
                print(f"Orthocenter H = ({fmt(h[0])},{fmt(h[1])})")

            else:
                print("Invalid option.")

        except Exception as e:
            print("Error:", e)

# Run
main()