import math
 
 
class AgentFSM:
    GOAL_X =  52.5
    GOAL_Y =   0.0
    OWN_GOAL_X = -52.5
 
    def __init__(self, unum, role, role_manager):
        self.unum  = unum
        self.role  = role
        self.rm    = role_manager
        self.state = "WAIT"
        self._tick = 0
 
    def step(self, wm):
        self._tick += 1
        if wm.play_mode in ("before_kick_off", "half_time",
                            "time_over", "game_over",
                            "kick_off_l", "kick_off_r"):
            self.state = "WAIT"
            return self._go_home(wm)
 
        if wm.ball_pos is None or wm.ball_dist > 990:
            return {"turn": 60.0, "dash": 0.0}
 
        if self.role == "goalkeeper":
            return self._goalkeeper(wm)
        elif self.role == "defender":
            return self._defender(wm)
        elif self.role == "midfielder":
            return self._midfielder(wm)
        elif self.role == "forward":
            return self._forward(wm)
        return self._chase(wm)
 
    def _goalkeeper(self, wm):
        if wm.ball_kickable:
            self.state = "CLEAR"
            side_angle = 25.0 if (wm.ball_pos and wm.ball_pos[1] >= 0) else -25.0
            return {"kick": (90.0, side_angle)}
        if wm.ball_dist < self.rm.get_chase_radius(self.unum):
            self.state = "CHASE"
            return self._chase(wm)
        self.state = "POSITION"
        gk_x = max(-50.0, min(-42.0,
               self.OWN_GOAL_X + 0.3 * (wm.ball_pos[0] - self.OWN_GOAL_X)
               if wm.ball_pos else -50.0))
        gk_y = max(-7.0, min(7.0, wm.ball_pos[1] * 0.15 if wm.ball_pos else 0.0))
        return self._move_to((gk_x, gk_y), wm)
 
    def _defender(self, wm):
        if wm.ball_kickable:
            self.state = "CLEAR"
            a = 15.0 if (wm.ball_pos and wm.ball_pos[1] >= 0) else -15.0
            return {"kick": (88.0, a)}
        if wm.ball_dist < self.rm.get_chase_radius(self.unum):
            self.state = "CHASE"
            return self._chase(wm)
        self.state = "POSITION"
        home = self.rm.get_home_position(self.unum)
        if wm.ball_pos:
            zx = max(self.OWN_GOAL_X + 2, min(-10.0,
                 home[0] * 0.6 + wm.ball_pos[0] * 0.4))
            zy = home[1] * 0.7 + wm.ball_pos[1] * 0.3
        else:
            zx, zy = home
        return self._move_to((zx, zy), wm)
 
    def _midfielder(self, wm):
        if wm.ball_kickable:
            opp_near = any(o["dist"] < 3.0 for o in wm.opponents) \
                       if wm.opponents else False
            if opp_near:
                self.state = "DRIBBLE"
                return self._dribble_forward(wm)
            self.state = "PASS"
            return self._pass_forward(wm)
        if wm.ball_dist < self.rm.get_chase_radius(self.unum):
            self.state = "CHASE"
            return self._chase(wm)
        self.state = "POSITION"
        return self._move_to(self._support_pos(wm), wm)
 
    def _forward(self, wm):
        if wm.ball_kickable:
            bx = wm.ball_pos[0] if wm.ball_pos else 0
            if bx > 25.0:
                self.state = "SHOOT"
                return self._shoot(wm)
            elif bx > 10.0:
                self.state = "DRIBBLE"
                return self._dribble_forward(wm)
            self.state = "PASS"
            return self._pass_forward(wm)
        if wm.ball_dist < self.rm.get_chase_radius(self.unum):
            self.state = "CHASE"
            return self._chase(wm)
        self.state = "POSITION"
        return self._move_to(self._run_depth(wm), wm)
 
    def _chase(self, wm):
        angle = wm.ball_angle
        turn  = self._smooth_turn(angle, 35.0)
        power = self._dash_power(wm, abs(angle))
        return {"dash": power, "turn": turn}
 
    def _shoot(self, wm):
        bx = wm.ball_pos[0] if wm.ball_pos else 0
        by = wm.ball_pos[1] if wm.ball_pos else 0
        angle = math.degrees(math.atan2(self.GOAL_Y - by, self.GOAL_X - bx))
        return {"kick": (100.0, angle)}
 
    def _dribble_forward(self, wm):
        bx = wm.ball_pos[0] if wm.ball_pos else 0
        by = wm.ball_pos[1] if wm.ball_pos else 0
        angle = math.degrees(math.atan2(self.GOAL_Y - by, self.GOAL_X - bx))
        return {"kick": (50.0, angle), "dash": 70.0}
 
    def _pass_forward(self, wm):
        bx = wm.ball_pos[0] if wm.ball_pos else 0
        by = wm.ball_pos[1] if wm.ball_pos else 0
        angle = math.degrees(math.atan2(self.GOAL_Y - by, self.GOAL_X - bx))
        return {"kick": (65.0, angle + self._jitter())}
 
    def _go_home(self, wm):
        return {"move": self.rm.get_home_position(self.unum)}
 
    def _move_to(self, target, wm):
        tx, ty = target
        angle  = math.degrees(math.atan2(ty, tx))
        turn   = self._smooth_turn(angle, 25.0)
        power  = self._dash_power(wm, abs(angle))
        return {"dash": power, "turn": turn}
 
    def _support_pos(self, wm):
        home = self.rm.get_home_position(self.unum)
        if wm.ball_pos:
            bx, by = wm.ball_pos
            sx = max(home[0], min(20.0, bx * 0.6 + 8.0))
            sy = max(-25.0, min(25.0, home[1] * 0.5 + by * 0.5))
            return (sx, sy)
        return home
 
    def _run_depth(self, wm):
        home = self.rm.get_home_position(self.unum)
        if wm.ball_pos:
            return (max(home[0], min(45.0, wm.ball_pos[0] + 12.0)), home[1])
        return home
 
    def _smooth_turn(self, angle, max_turn=30.0):
        while angle >  180: angle -= 360
        while angle < -180: angle += 360
        return max(-max_turn, min(max_turn, angle))
 
    def _dash_power(self, wm, angle_diff):
        base = self.rm.get_dash_base(self.unum)
        if angle_diff > 30:
            base *= 0.5
        if wm.stamina_pct < 0.3:
            base *= 0.6
        elif wm.stamina_pct < 0.6:
            base *= 0.85
        return round(base, 1)
 
    def _jitter(self):
        return (self._tick % 7 - 3) * 1.5
