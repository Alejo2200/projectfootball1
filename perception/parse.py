import re
import math

FLAGS = {
    "f t l 50": (-50, 34), "f t l 40": (-40, 34), "f t l 30": (-30, 34),
    "f t l 20": (-20, 34), "f t l 10": (-10, 34), "f t 0":    (  0, 34),
    "f t r 10": ( 10, 34), "f t r 20": ( 20, 34), "f t r 30": ( 30, 34),
    "f t r 40": ( 40, 34), "f t r 50": ( 50, 34),
    "f b l 50": (-50,-34), "f b l 40": (-40,-34), "f b l 30": (-30,-34),
    "f b l 20": (-20,-34), "f b l 10": (-10,-34), "f b 0":    (  0,-34),
    "f b r 10": ( 10,-34), "f b r 20": ( 20,-34), "f b r 30": ( 30,-34),
    "f b r 40": ( 40,-34), "f b r 50": ( 50,-34),
    "f l t 30": (-52, 30), "f l t 20": (-52, 20), "f l t 10": (-52, 10),
    "f l 0":    (-52,  0), "f l b 10": (-52,-10), "f l b 20": (-52,-20),
    "f l b 30": (-52,-30),
    "f r t 30": ( 52, 30), "f r t 20": ( 52, 20), "f r t 10": ( 52, 10),
    "f r 0":    ( 52,  0), "f r b 10": ( 52,-10), "f r b 20": ( 52,-20),
    "f r b 30": ( 52,-30),
    "f c":      (  0,  0), "f c t":    (  0, 34), "f c b":    (  0,-34),
    "f p l t":  (-36, 20), "f p l c":  (-36,  0), "f p l b":  (-36,-20),
    "f p r t":  ( 36, 20), "f p r c":  ( 36,  0), "f p r b":  ( 36,-20),
    "f g l b":  (-52,  8), "f g l t":  (-52, -8),
    "f g r b":  ( 52,  8), "f g r t":  ( 52, -8),
    "g l":      (-52,  0), "g r":      ( 52,  0),
}

# Regex principal: captura objetos del mensaje see
# Formato: ((nombre) dist angle ...) con posibles espacios
_OBJ_RE = re.compile(r'\(\(([^)]+)\)\s+([\d.]+)\s+([-\d.]+)[^)]*\)')


def parse_see(msg):
    result = {
        "ball":      None,
        "teammates": [],
        "opponents": [],
        "flags":     [],
    }

    for m in _OBJ_RE.finditer(msg):
        name_raw = m.group(1).strip()
        try:
            dist  = float(m.group(2))
            angle = float(m.group(3))
        except ValueError:
            continue

        # ── BALÓN ── nombre es simplemente "b"
        if name_raw == "b":
            result["ball"] = {"dist": dist, "angle": angle}

        # ── JUGADORES ── formato: p "TeamName" unum
        elif name_raw.startswith("p "):
            parts = name_raw.split(None, 2)
            team_name = parts[1].strip('"\'') if len(parts) > 1 else ""
            try:
                unum = int(parts[2]) if len(parts) > 2 else 0
            except (ValueError, IndexError):
                unum = 0
            result["teammates"].append({
                "team":  team_name,
                "unum":  unum,
                "dist":  dist,
                "angle": angle,
            })

        # ── BANDERAS ──
        elif name_raw in FLAGS:
            result["flags"].append({
                "name": name_raw,
                "dist": dist,
                "angle": angle,
                "pos":  FLAGS[name_raw],
            })
        elif name_raw.startswith("f ") or name_raw.startswith("g"):
            if name_raw in FLAGS:
                result["flags"].append({
                    "name": name_raw,
                    "dist": dist,
                    "angle": angle,
                    "pos":  FLAGS[name_raw],
                })

    return result


def estimate_self_pos(flags, self_angle):
    if len(flags) < 1:
        return None
    estimates = []
    for flag in flags[:8]:
        fx, fy  = flag["pos"]
        dist    = flag["dist"]
        fangle  = flag["angle"]
        abs_ang = math.radians(self_angle + fangle)
        px = fx - dist * math.cos(abs_ang)
        py = fy - dist * math.sin(abs_ang)
        estimates.append((px, py))
    if not estimates:
        return None
    x = sum(e[0] for e in estimates) / len(estimates)
    y = sum(e[1] for e in estimates) / len(estimates)
    return (
        max(-52.0, min(52.0, x)),
        max(-34.0, min(34.0, y))
    )
