import re
 
_BALL_FULL  = re.compile(r'\(\(b\)\s+([\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\)')
_BALL_SHORT = re.compile(r'\(\(b\)\s+([\d.]+)\s+([-\d.]+)\)')
_PLAYER     = re.compile(r'\(\(p\s+"([^"]+)"\s+(\d+)(?:\s+goalie)?\)\s+([\d.]+)\s+([-\d.]+)')
_PLAYER_UNK = re.compile(r'\(\(p\s+"([^"]+)"\)\s+([\d.]+)\s+([-\d.]+)')
 
 
def parse_see(msg):
    result = {"ball": None, "teammates": [], "opponents": [], "flags": []}
    m = _BALL_FULL.search(msg)
    if m:
        result["ball"] = {"dist": float(m.group(1)), "angle": float(m.group(2)),
                          "vx": float(m.group(3)), "vy": float(m.group(4))}
    else:
        m = _BALL_SHORT.search(msg)
        if m:
            result["ball"] = {"dist": float(m.group(1)), "angle": float(m.group(2))}
    for m in _PLAYER.finditer(msg):
        result["teammates"].append({"team": m.group(1), "unum": int(m.group(2)),
                                    "dist": float(m.group(3)), "angle": float(m.group(4))})
    for m in _PLAYER_UNK.finditer(msg):
        result["teammates"].append({"team": m.group(1), "unum": -1,
                                    "dist": float(m.group(2)), "angle": float(m.group(3))})
    return result
