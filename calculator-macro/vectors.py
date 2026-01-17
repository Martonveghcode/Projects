# ==========================================
# Vector Toolkit (2D/3D) - TI-Nspire friendly
# - NO auto-scroll: pauses after results
# - Safe: prevents using empty vector slots
# ==========================================

import math

PI = 3.141592653589793
EPS = 1e-9

def deg2rad(d): return d * PI / 180.0
def rad2deg(r): return r * 180.0 / PI

def pause():
    input("\nPress ENTER to return to menu...")

def ask_int(prompt, lo, hi, default=None):
    while True:
        s = input(prompt).strip()
        if s == "" and default is not None:
            return default
        try:
            v = int(s)
            if lo <= v <= hi:
                return v
        except:
            pass
        print("Invalid.")

def ask_float(prompt, default=None):
    while True:
        s = input(prompt).strip()
        if s == "" and default is not None:
            return default
        try:
            return float(s)
        except:
            print("Invalid.")

def ask_choice(prompt, a, b, default=None):
    while True:
        s = input(prompt).strip().lower()
        if s == "" and default is not None:
            return default
        if s == a or s == b:
            return s
        print("Type", a, "or", b)

# -------- Vector math --------

def v_add(a, b): return [a[i] + b[i] for i in range(len(a))]
def v_sub(a, b): return [a[i] - b[i] for i in range(len(a))]
def v_scale(k, a): return [k * a[i] for i in range(len(a))]
def v_dot(a, b): return sum(a[i] * b[i] for i in range(len(a)))
def v_mag(a): return math.sqrt(v_dot(a, a))

def v_unit(a):
    m = v_mag(a)
    if m < EPS:
        return None
    return [x / m for x in a]

def v_cross(a, b):
    return [
        a[1]*b[2] - a[2]*b[1],
        a[2]*b[0] - a[0]*b[2],
        a[0]*b[1] - a[1]*b[0]
    ]

def v_angle(a, b):
    ma, mb = v_mag(a), v_mag(b)
    if ma < EPS or mb < EPS:
        return None
    c = v_dot(a, b) / (ma * mb)
    c = max(-1.0, min(1.0, c))
    return rad2deg(math.acos(c))

def is_perp(a, b):
    return abs(v_dot(a, b)) < EPS

def is_parallel_2d(a, b):
    return abs(a[0]*b[1] - a[1]*b[0]) < EPS

def is_parallel_3d(a, b):
    c = v_cross(a, b)
    return v_mag(c) < 1e-8

def v_proj(u, v):
    vv = v_dot(v, v)
    if vv < EPS:
        return None, None
    k = v_dot(u, v) / vv
    return v_scale(k, v), k

def read_vec(dim):
    labels = ["x", "y", "z"]
    out = []
    for i in range(dim):
        out.append(ask_float(labels[i] + " = "))
    return out

def print_vec(name, v):
    if v is None:
        print(name, "= undefined")
        return
    if len(v) == 2:
        print(name, "= <%.6f, %.6f>" % (v[0], v[1]))
    else:
        print(name, "= <%.6f, %.6f, %.6f>" % (v[0], v[1], v[2]))

def from_mag_angle_2d():
    m = ask_float("Magnitude: ")
    ang = ask_float("Angle from +x (deg): ")
    a = deg2rad(ang)
    return [m * math.cos(a), m * math.sin(a)]

def pick_slot(vecs, prompt):
    idx = ask_int(prompt, 1, 9) - 1
    if vecs[idx] is None:
        print("That slot is empty. Create the vector first (Menu 1).")
        return None
    return idx

def list_vectors(vecs):
    print("\n--- Stored vectors ---")
    for i in range(9):
        name = chr(65 + i)
        if vecs[i] is None:
            print(name + ": empty")
        else:
            print(name + ":", vecs[i])
    print("----------------------")

def main():
    print("=== VECTOR TOOLKIT ===")
    print("Stop anytime: Ctrl + C")

    dim = ask_int("Dimension (2 or 3) [2]: ", 2, 3, 2)
    V = [None] * 9

    while True:
        print("\nMenu")
        print("1 Create/Update vector")
        print("2 List vectors")
        print("3 Add (u+v)")
        print("4 Subtract (u−v)")
        print("5 Scalar multiply (k*u)")
        print("6 Magnitude & unit")
        print("7 Dot / angle / perpendicular")
        print("8 Parallel?")
        print("9 Projection (proj_v(u))")
        if dim == 3:
            print("10 Cross product (u×v)")
        print("0 Exit")

        hi = 10 if dim == 3 else 9
        ch = ask_int("Choose: ", 0, hi)

        if ch == 0:
            break

        # 1) Create/update
        if ch == 1:
            i = ask_int("Slot 1–9 (A..I): ", 1, 9) - 1
            name = chr(65 + i)

            mode = ask_choice("Enter as components or mag/angle? (c/m): ", "c", "m", "c")
            if mode == "m":
                if dim != 2:
                    print("Mag/angle entry only supported for 2D.")
                else:
                    V[i] = from_mag_angle_2d()
                    print_vec(name, V[i])
            else:
                print("Enter vector", name, "components:")
                V[i] = read_vec(dim)
                print_vec(name, V[i])

            pause()

        # 2) List
        elif ch == 2:
            list_vectors(V)
            pause()

        # 3) Add
        elif ch == 3:
            list_vectors(V)
            u = pick_slot(V, "Pick u (1–9): ")
            if u is None:
                pause(); continue
            v = pick_slot(V, "Pick v (1–9): ")
            if v is None:
                pause(); continue

            r = v_add(V[u], V[v])
            print("\nFormula: r = u + v")
            print_vec("u", V[u])
            print_vec("v", V[v])
            print_vec("r", r)
            pause()

        # 4) Subtract
        elif ch == 4:
            list_vectors(V)
            u = pick_slot(V, "Pick u (1–9): ")
            if u is None:
                pause(); continue
            v = pick_slot(V, "Pick v (1–9): ")
            if v is None:
                pause(); continue

            r = v_sub(V[u], V[v])
            print("\nFormula: r = u − v")
            print_vec("u", V[u])
            print_vec("v", V[v])
            print_vec("r", r)
            pause()

        # 5) Scalar multiply
        elif ch == 5:
            list_vectors(V)
            u = pick_slot(V, "Pick u (1–9): ")
            if u is None:
                pause(); continue
            k = ask_float("Scalar k = ")

            r = v_scale(k, V[u])
            print("\nFormula: r = k u")
            print("k =", k)
            print_vec("u", V[u])
            print_vec("r", r)
            pause()

        # 6) Magnitude & unit
        elif ch == 6:
            list_vectors(V)
            u = pick_slot(V, "Pick u (1–9): ")
            if u is None:
                pause(); continue

            print("\nFormulas: |u| = sqrt(u·u),  û = u/|u|")
            print_vec("u", V[u])
            print("|u| =", v_mag(V[u]))
            print_vec("û", v_unit(V[u]))
            pause()

        # 7) Dot/angle/perp
        elif ch == 7:
            list_vectors(V)
            u = pick_slot(V, "Pick u (1–9): ")
            if u is None:
                pause(); continue
            v = pick_slot(V, "Pick v (1–9): ")
            if v is None:
                pause(); continue

            d = v_dot(V[u], V[v])
            ang = v_angle(V[u], V[v])

            print("\nFormulas: u·v = Σ u_i v_i,  cosθ=(u·v)/(|u||v|)")
            print_vec("u", V[u])
            print_vec("v", V[v])
            print("u·v =", d)
            if ang is None:
                print("Angle: undefined (one vector is zero).")
            else:
                print("Angle θ =", ang, "deg")
            print("Perpendicular? ", "YES" if is_perp(V[u], V[v]) else "NO")
            pause()

        # 8) Parallel
        elif ch == 8:
            list_vectors(V)
            u = pick_slot(V, "Pick u (1–9): ")
            if u is None:
                pause(); continue
            v = pick_slot(V, "Pick v (1–9): ")
            if v is None:
                pause(); continue

            if dim == 2:
                par = is_parallel_2d(V[u], V[v])
                print("\nFormula (2D): u || v if u_x v_y − u_y v_x = 0")
            else:
                par = is_parallel_3d(V[u], V[v])
                print("\nFormula (3D): u || v if |u×v| = 0")

            print_vec("u", V[u])
            print_vec("v", V[v])
            print("Parallel? ", "YES" if par else "NO")
            pause()

        # 9) Projection
        elif ch == 9:
            list_vectors(V)
            u = pick_slot(V, "Pick u (1–9): ")
            if u is None:
                pause(); continue
            v = pick_slot(V, "Pick v (1–9): ")
            if v is None:
                pause(); continue

            p, k = v_proj(V[u], V[v])
            print("\nFormula: proj_v(u) = ((u·v)/(v·v)) v")
            if p is None:
                print("Projection undefined (v is zero vector).")
            else:
                print("k =", k)
                print_vec("proj_v(u)", p)
            pause()

        # 10) Cross (3D only)
        elif ch == 10 and dim == 3:
            list_vectors(V)
            u = pick_slot(V, "Pick u (1–9): ")
            if u is None:
                pause(); continue
            v = pick_slot(V, "Pick v (1–9): ")
            if v is None:
                pause(); continue

            c = v_cross(V[u], V[v])
            print("\nFormulas: u×v (right-hand rule),  |u×v| = area of parallelogram")
            print_vec("u", V[u])
            print_vec("v", V[v])
            print_vec("u×v", c)
            print("|u×v| =", v_mag(c))
            pause()

main()
