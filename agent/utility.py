import math


def _teammate_abs_pos(wm, tm):
    abs_a = wm.self_angle + tm.get("angle", 0)
    tx = wm.self_pos[0] + tm["dist"] * math.cos(math.radians(abs_a))
    ty = wm.self_pos[1] + tm["dist"] * math.sin(math.radians(abs_a))
    return tx, ty


def _opp_pressure(wm, radius=5.0):
    if not wm.opponents:
        return 0.0
    min_dist = min(o.get("dist", 999) for o in wm.opponents)
    return max(0.0, 1.0 - min_dist / radius)


def _best_teammate(wm):
    if not wm.teammates or not wm.ball_pos:
        return None
    bx, by     = wm.ball_pos
    best       = None
    best_score = -999.0
    for tm in wm.teammates:
        dist = tm.get("dist", 999)
        if dist < 2.0 or dist > 35.0:
            continue
        tx, ty   = _teammate_abs_pos(wm, tm)
        adelanto = tx - bx
        opp_cerca = 0
        for o in wm.opponents:
            abs_a = wm.self_angle + o.get("angle", 0)
            ox = wm.self_pos[0] + o["dist"] * math.cos(math.radians(abs_a))
            oy = wm.self_pos[1] + o["dist"] * math.sin(math.radians(abs_a))
            if math.hypot(ox - tx, oy - ty) < 3.0:
                opp_cerca += 1
        score = (adelanto * 0.5) - (dist * 0.05) - (opp_cerca * 5.0)
        if score > best_score:
            best_score = score
            best       = (tx, ty, dist, score)
    return best if best_score > -4.0 else None


def compute_utilities(wm):
    if not wm.ball_pos:
        return {"DRIBBLE_FWD": 1.0}

    bx, by   = wm.ball_pos
    pressure = _opp_pressure(wm, radius=6.0)
    tm_best  = _best_teammate(wm)
    utilities = {}

    # ── PASS ──────────────────────────────────────────────────────
    if tm_best:
        tx, ty, tm_dist, tm_score = tm_best
        adelanto = tx - bx
        u_pass = (
            4.0
            + pressure * 4.0
            + adelanto * 0.3
            - tm_dist * 0.05
        )
        utilities["PASS"] = round(u_pass, 3)
    else:
        utilities["PASS"] = -5.0

    # ── DRIBBLE_FWD ───────────────────────────────────────────────
    u_drib_fwd = (
        1.5
        + (1.0 - pressure) * 2.0
        + (bx / 52.5) * 1.0
    )
    utilities["DRIBBLE_FWD"] = round(u_drib_fwd, 3)

    # ── DRIBBLE_ESC ───────────────────────────────────────────────
    u_drib_esc = (
        pressure * 4.0
        - (2.0 if tm_best else 0.0)
        + 0.5
    )
    utilities["DRIBBLE_ESC"] = round(u_drib_esc, 3)

    # ── SHOOT ─────────────────────────────────────────────────────
    dist_to_goal = math.hypot(52.5 - bx, 0.0 - by)
    if bx > 25.0:
        u_shoot = (
            (1.0 - dist_to_goal / 52.5) * 10.0
            + (3.0 if bx > 38.0 else 0.0)
            - pressure * 0.5
        )
    else:
        u_shoot = -10.0
    utilities["SHOOT"] = round(u_shoot, 3)

    return utilities


def best_action(wm):
    utils = compute_utilities(wm)
    return max(utils, key=utils.get), utils
