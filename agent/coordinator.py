import math
import threading


class TeamCoordinator:
    def __init__(self):
        self._lock       = threading.Lock()
        self.ball_chaser = None
        self.positions   = {}
        self.ball_dists  = {}
        self.has_ball    = None
        self._tick       = 0

    def update(self, unum, self_pos, ball_pos, ball_kickable, ball_dist=9999):
        with self._lock:
            self._tick           += 1
            self.positions[unum]  = self_pos
            self.ball_dists[unum] = ball_dist
            if ball_kickable:
                self.has_ball    = unum
                self.ball_chaser = unum

    def elect_chaser(self, unum, ball_pos, role):
        if role == "goalkeeper":
            return False
        if ball_pos is None:
            return False
        with self._lock:
            my_dist = self.ball_dists.get(unum, 9999)
            for other_unum, other_dist in self.ball_dists.items():
                if other_unum == unum:
                    continue
                # Margen de 4m — más jugadores pueden ser chaser
                if other_dist < my_dist - 4.0:
                    return False
            self.ball_chaser = unum
            return True

    def get_support_positions(self, unum, ball_pos, home_pos, side):
        if ball_pos is None:
            return home_pos
        bx, by = ball_pos
        hx, hy = home_pos
        dx   = bx - hx
        dy   = by - hy
        dist = math.hypot(dx, dy)
        if dist < 0.1:
            return home_pos
        factor = min(0.4, 12.0 / max(dist, 1.0))
        tx = hx + dx * factor
        ty = hy + dy * factor
        if hy > 2.0:
            ty += 4.0
        elif hy < -2.0:
            ty -= 4.0
        with self._lock:
            for other_unum, other_pos in self.positions.items():
                if other_unum == unum:
                    continue
                sep = math.hypot(other_pos[0] - tx, other_pos[1] - ty)
                if sep < 6.0:
                    if other_pos[1] > ty:
                        ty -= 4.0
                    else:
                        ty += 4.0
        tx = max(-51.0, min(51.0, tx))
        ty = max(-32.0, min(32.0, ty))
        return (tx, ty)


_coordinators = {}
_coord_lock   = threading.Lock()


def get_coordinator(team_name):
    with _coord_lock:
        if team_name not in _coordinators:
            _coordinators[team_name] = TeamCoordinator()
        return _coordinators[team_name]
