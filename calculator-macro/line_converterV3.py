# TI-Nspire CX II-T CAS (Python) — Line Form Converter
# Converts between:
# 1 Vector, 2 Parametric, 3 Symmetric, 4 Slope-Intercept, 5 Point-Slope, 6 General

# ---------- helpers ----------
def parse_num(s):
    """
    Allows inputs like: 3, -2.5, 1/3, (7-1)/2
    Uses eval in a restricted environment (numbers + operators only).
    """
    s = s.strip()
    allowed = set("0123456789+-*/(). ")
    for ch in s:
        if ch not in allowed:
            raise ValueError("Invalid character in number.")
    return float(eval(s, {"__builtins__": None}, {}))

def fmt(x):
    # Pretty-ish formatting: avoid "-0.0" and trailing .0 when near integers
    if abs(x) < 1e-12:
        x = 0.0
    if abs(x - round(x)) < 1e-10:
        return str(int(round(x)))
    # limit long floats
    return "{:.10g}".format(x)

def normalize_direction(dx, dy):
    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        raise ValueError("Direction vector cannot be (0,0).")
    return dx, dy

# ---------- canonical representation ----------
# We convert everything to: point P(x0,y0) and direction d(dx,dy)
def canonical_from_vector(x0, y0, dx, dy):
    dx, dy = normalize_direction(dx, dy)
    return x0, y0, dx, dy

def canonical_from_parametric(p1, p2, d1, d2):
    return canonical_from_vector(p1, p2, d1, d2)

def canonical_from_symmetric(p1, p2, d1, d2):
    return canonical_from_vector(p1, p2, d1, d2)

def canonical_from_slope_intercept(m, b):
    # y = m x + b  => point (0,b), direction (1,m)
    return canonical_from_vector(0.0, b, 1.0, m)

def canonical_from_point_slope(m, x0, y0):
    # y - y0 = m(x - x0) => direction (1,m)
    return canonical_from_vector(x0, y0, 1.0, m)

def canonical_from_general(A, B, C):
    if abs(A) < 1e-12 and abs(B) < 1e-12:
        raise ValueError("Invalid line: A and B cannot both be 0.")
    # Choose an easy point on the line
    if abs(B) > 1e-12:
        x0 = 0.0
        y0 = -C / B
    else:
        y0 = 0.0
        x0 = -C / A
    # Direction is perpendicular to normal (A,B): d = (-B, A)
    dx, dy = -B, A
    return canonical_from_vector(x0, y0, dx, dy)

# ---------- produce all 6 forms from canonical ----------
def forms_from_canonical(x0, y0, dx, dy):
    # Vector / Parametric
    vec = "Vector: OX = ({x0},{y0}) + t({dx},{dy})".format(
        x0=fmt(x0), y0=fmt(y0), dx=fmt(dx), dy=fmt(dy)
    )
    par = "Parametric: x = {x0} + t({dx}) ,  y = {y0} + t({dy})".format(
        x0=fmt(x0), y0=fmt(y0), dx=fmt(dx), dy=fmt(dy)
    )

    # Symmetric (handle dx=0 or dy=0)
    if abs(dx) < 1e-12 and abs(dy) >= 1e-12:
        sym = "Symmetric: x = {x0}".format(x0=fmt(x0))
    elif abs(dy) < 1e-12 and abs(dx) >= 1e-12:
        sym = "Symmetric: y = {y0}".format(y0=fmt(y0))
    else:
        sym = "Symmetric: (x - {x0})/({dx}) = (y - {y0})/({dy})".format(
            x0=fmt(x0), y0=fmt(y0), dx=fmt(dx), dy=fmt(dy)
        )

    # General form using normal n = (dy, -dx):
    # dy(x-x0) - dx(y-y0)=0  =>  A x + B y + C = 0
    A = dy
    B = -dx
    C = -(A * x0 + B * y0)
    gen = "General: {A}x + {B}y + {C} = 0".format(A=fmt(A), B=fmt(B), C=fmt(C))

    # Slope-intercept and point-slope (handle vertical)
    if abs(dx) < 1e-12:
        # vertical line x = x0
        si = "Slope-Intercept: (vertical) x = {x0}".format(x0=fmt(x0))
        ps = "Point-Slope: (vertical) x = {x0}".format(x0=fmt(x0))
    else:
        m = dy / dx
        b = y0 - m * x0
        si = "Slope-Intercept: y = {m}x + {b}".format(m=fmt(m), b=fmt(b))
        ps = "Point-Slope: y - {y0} = {m}(x - {x0})".format(
            y0=fmt(y0), m=fmt(m), x0=fmt(x0)
        )

    return vec, par, sym, si, ps, gen

# ---------- UI ----------
def menu():
    print("Line Form Converter")
    print("1) Vector      OX=(p1,p2)+t(d1,d2)")
    print("2) Parametric  x=p1+t d1 , y=p2+t d2")
    print("3) Symmetric   (x-p1)/d1=(y-p2)/d2")
    print("4) Slope-Int   y=mx+b")
    print("5) Point-Slope y-y0=m(x-x0)")
    print("6) General     Ax+By+C=0")
    s = input("Choose input form (1-6): ").strip()
    return int(s)

def read_point_dir():
    p1 = parse_num(input("p1 (x0) = "))
    p2 = parse_num(input("p2 (y0) = "))
    d1 = parse_num(input("d1 (dx) = "))
    d2 = parse_num(input("d2 (dy) = "))
    return p1, p2, d1, d2

def main():
    try:
        choice = menu()
        if choice == 1:
            p1, p2, d1, d2 = read_point_dir()
            x0, y0, dx, dy = canonical_from_vector(p1, p2, d1, d2)
        elif choice == 2:
            p1, p2, d1, d2 = read_point_dir()
            x0, y0, dx, dy = canonical_from_parametric(p1, p2, d1, d2)
        elif choice == 3:
            p1, p2, d1, d2 = read_point_dir()
            x0, y0, dx, dy = canonical_from_symmetric(p1, p2, d1, d2)
        elif choice == 4:
            m = parse_num(input("m = "))
            b = parse_num(input("b = "))
            x0, y0, dx, dy = canonical_from_slope_intercept(m, b)
        elif choice == 5:
            m = parse_num(input("m = "))
            x0 = parse_num(input("x0 = "))
            y0 = parse_num(input("y0 = "))
            x0, y0, dx, dy = canonical_from_point_slope(m, x0, y0)
        elif choice == 6:
            A = parse_num(input("A = "))
            B = parse_num(input("B = "))
            C = parse_num(input("C = "))
            x0, y0, dx, dy = canonical_from_general(A, B, C)
        else:
            print("Invalid choice.")
            return

        print("\n--- All 6 forms ---")
        vec, par, sym, si, ps, gen = forms_from_canonical(x0, y0, dx, dy)
        print("1)", vec)
        print("2)", par)
        print("3)", sym)
        print("4)", si)
        print("5)", ps)
        print("6)", gen)

    except Exception as e:
        print("Error:", e)

# Run
main()
