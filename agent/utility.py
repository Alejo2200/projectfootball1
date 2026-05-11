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
    bx, by = wm.ball_pos
    best       = None
    best_score = -999.0
    for tm in wm.teammates:
        dist = tm.get("dist", 999)
        if dist < 1.5 or dist > 35.0:
            continue
        tx, ty = _teammate_abs_pos(wm, tm)
        adelanto = tx - bx

        # Contar rivales cerca del receptor
        opp_cerca = 0
        for o in wm.opponents:
            abs_a = wm.self_angle + o.get("angle", 0)
            ox = wm.self_pos[0] + o["dist"] * math.cos(math.radians(abs_a))
            oy = wm.self_pos[1] + o["dist"] * math.sin(math.radians(abs_a))
            if math.hypot(ox - tx, oy - ty) < 3.0:
                opp_cerca += 1

        # Score: adelanto cuenta mucho, distancia moderada, rivales penalizan
        score = (adelanto * 0.6) - (dist * 0.05) - (opp_cerca * 6.0)
        if score > best_score:
            best_score = score
            best = (tx, ty, dist, score)

    return best if best_score > -8.0 else None


def compute_utilities(wm):
    if not wm.ball_pos:
        return {"DRIBBLE_FWD": 0.0}

    bx, by   = wm.ball_pos
    pressure = _opp_pressure(wm, radius=6.0)
    tm_best  = _best_teammate(wm)
    utilities = {}

    # ── PASS ──────────────────────────────────────────────────────
    if tm_best:
        tx, ty, tm_dist, tm_score = tm_best
        # PASS es la acción base — siempre tiene alta utilidad si hay compañero
        u_pass = (
            6.0                          # base alta — pasar es preferido
            + tm_score * 0.4             # calidad del compañero
            + pressure * 4.0             # bajo presión pasar es urgente
            - (1.0 if tm_dist < 3.0 else 0.0)  # no pasar a quien está muy cerca
        )
        utilities["PASS"] = round(u_pass, 3)
    else:
        utilities["PASS"] = -5.0

    # ── DRIBBLE_FWD ───────────────────────────────────────────────
    # Solo bueno cuando no hay presión Y no hay compañero claro adelante
    u_drib_fwd = (
        (1.0 - pressure) * 3.0
        + (bx / 52.5) * 1.0
        - (3.0 if tm_best and tm_best[3] > 0 else 0.0)  # penalizar si hay pase
    )
    utilities["DRIBBLE_FWD"] = round(u_drib_fwd, 3)

    # ── DRIBBLE_ESC ───────────────────────────────────────────────
    # Solo cuando hay mucha presión y no hay compañero libre
    u_drib_esc = (
        pressure * 4.0
        - (4.0 if tm_best else 0.0)   # si hay compañero, pasar es mejor
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
