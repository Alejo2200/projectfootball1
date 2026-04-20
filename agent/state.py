import math
 
 
class WorldModel:
    def __init__(self):
        self.ball_pos   = None
        self.ball_dist  = 999.0
        self.ball_angle = 0.0
        self.ball_vel   = None
        self.self_pos   = (0.0, 0.0)
        self.self_angle = 0.0
        self.stamina    = 8000.0
        self.stamina_max = 8000.0
        self.unum       = None
        self.side       = None
        self.self_role  = "midfielder"
        self.teammates  = []
        self.opponents  = []
        self.play_mode  = "before_kick_off"
        self.ball_kickable    = False
        self.possession_ticks = 0
        self.total_ticks      = 0
 
    def update_from_see(self, obs):
        self.total_ticks += 1
        ball = obs.get("ball")
        if ball is not None:
            d = ball.get("dist", 999.0)
            a = ball.get("angle", 0.0)
            self.ball_dist  = d
            self.ball_angle = a
            rad = math.radians(a)
            self.ball_pos   = (d * math.cos(rad), d * math.sin(rad))
            self.ball_kickable = d < 1.085
            if self.ball_kickable:
                self.possession_ticks += 1
        else:
            self.ball_kickable = False
            self.ball_dist = 999.0
        self.teammates = obs.get("teammates", [])
        self.opponents  = obs.get("opponents",  [])
 
    def update_from_sense_body(self, stamina=None, angle=None):
        if stamina is not None:
            self.stamina = stamina
        if angle is not None:
            self.self_angle = angle
 
    @property
    def stamina_pct(self):
        return self.stamina / self.stamina_max
 
    @property
    def possession_pct(self):
        if self.total_ticks == 0:
            return 0.0
        return 100.0 * self.possession_ticks / self.total_ticks
