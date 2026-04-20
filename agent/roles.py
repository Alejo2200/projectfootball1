import json
import os
 
 
class RoleManager:
    CHASE_RADIUS = {
        "goalkeeper": 13.0,
        "defender":   25.0,
        "midfielder": 32.0,
        "forward":    40.0,
    }
    DASH_BASE = {
        "goalkeeper": 80.0,
        "defender":   90.0,
        "midfielder": 95.0,
        "forward":   100.0,
    }
 
    def __init__(self, conf_file):
        self.roles     = {}
        self.positions = {}
        self.names     = {}
        if not os.path.exists(conf_file):
            return
        with open(conf_file, "r") as f:
            data = json.load(f)
        for r in data.get("role", []):
            unum = r["number"]
            self.names[unum] = r["name"]
            self.roles[unum] = r.get("type", "midfielder")
        for key, val in data["data"][0].items():
            if key in ("index", "ball"):
                continue
            unum = int(key)
            self.positions[unum] = (float(val["x"]), float(val["y"]))
 
    def get_role(self, unum):
        return self.roles.get(unum, "midfielder")
 
    def get_home_position(self, unum):
        return self.positions.get(unum, (0.0, 0.0))
 
    def get_chase_radius(self, unum):
        return self.CHASE_RADIUS.get(self.get_role(unum), 25.0)
 
    def get_dash_base(self, unum):
        return self.DASH_BASE.get(self.get_role(unum), 90.0)
