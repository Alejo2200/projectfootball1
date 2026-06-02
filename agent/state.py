import math
from perception.parse import estimate_self_pos


class WorldModel:
    def __init__(self):
        self.unum          = 0
        self.side          = "l"
        self.self_role     = "midfielder"
        self.play_mode     = "before_kick_off"
        self.ball_pos      = None
        self.ball_dist     = 9999.0
        self.ball_angle    = 0.0
        self.ball_kickable = False
        self.self_pos      = (0.0, 0.0)
        self.self_angle    = 0.0
        self.stamina       = 8000.0
        self.stamina_pct   = 1.0
        self.teammates     = []
        self.opponents     = []
        self._pos_history  = []
        self.ball_vel      = (0.0, 0.0)
        self.ball_pred     = None
        self.last_ball_pos = None
        self.ticks_no_ball = 0

    def update_from_see(self, obs):
        self.teammates = obs.get("teammates", [])
        self.opponents = obs.get("opponents", [])

        flags = obs.get("flags", [])
        estimated = estimate_self_pos(flags, self.self_angle)
        if estimated:
            self._pos_history.append(estimated)
            if len(self._pos_history) > 4:
                self._pos_history.pop(0)
            self.self_pos = (
                sum(p[0] for p in self._pos_history) / len(self._pos_history),
                sum(p[1] for p in self._pos_history) / len(self._pos_history),
            )

        ball = obs.get("ball")
        if ball:
            self.ball_dist     = ball.get("dist", 9999.0)
            self.ball_angle    = ball.get("angle", 0.0)
            bx = self.self_pos[0] + self.ball_dist * math.cos(
                math.radians(self.self_angle + self.ball_angle))
            by = self.self_pos[1] + self.ball_dist * math.sin(
                math.radians(self.self_angle + self.ball_angle))
            self.ball_pos      = (bx, by)
            self.last_ball_pos = (bx, by)
            self.ball_pred     = self.ball_pos
            self.ball_vel      = (0.0, 0.0)
            self.ball_kickable = self.ball_dist <= 1.0
            self.ticks_no_ball = 0
        else:
            # No vemos el balón — mantener último ángulo conocido
            # para que _chase siga corriendo en la misma dirección
            self.ball_dist     = 9999.0
            self.ball_kickable = False
            self.ball_pos      = None
            self.ball_pred     = None
            self.ball_vel      = (0.0, 0.0)
            self.ticks_no_ball += 1
            # ball_angle NO se resetea — mantiene el último valor

    def update_from_sense_body(self, stamina=None, angle=None):
        if stamina is not None:
            self.stamina     = stamina
            self.stamina_pct = min(1.0, stamina / 8000.0)
        if angle is not None:
            self.self_angle  = angle

    def angle_to_last_ball(self):
        if self.last_ball_pos is None:
            return None
        lx, ly = self.last_ball_pos
        sx, sy = self.self_pos
        abs_a  = math.degrees(math.atan2(ly - sy, lx - sx))
        diff   = abs_a - self.self_angle
        while diff >  180: diff -= 360
        while diff < -180: diff += 360
        return diff
