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
            self._tick       += 1
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
                if other_dist < my_dist - 2.0:
                    return False
            self.ball_chaser = unum
            return True

    def get_support_positions(self, unum, ball_pos, home_pos, side):
        """
        Posición de apoyo inteligente:
        - Formar triángulos alrededor del balón
        - Moverse a recibir, no esperar
        - Mantener separación entre compañeros
        """
        if ball_pos is None:
            return home_pos

        bx, by = ball_pos
        hx, hy = home_pos

        # Offset base hacia el balón
        dx = bx - hx
        dy = by - hy
        dist_to_ball = math.hypot(dx, dy)

        if dist_to_ball < 0.1:
            return home_pos

        # Moverse hasta 60% del camino hacia el balón
        # pero mantener la estructura del equipo
        factor = min(0.6, 15.0 / max(dist_to_ball, 1.0))
        tx = hx + dx * factor
        ty = hy + dy * factor

        # Separación lateral para triángulos
        # Jugadores arriba del eje van más arriba, abajo van más abajo
        # Esto crea ángulos de pase naturales
        if hy > 1.0:
            ty += 3.0   # abrirse hacia arriba
        elif hy < -1.0:
            ty -= 3.0   # abrirse hacia abajo

        # Evitar amontonarse — separación mínima de otros jugadores
        with self._lock:
            for other_unum, other_pos in self.positions.items():
                if other_unum == unum:
                    continue
                sep = math.hypot(other_pos[0] - tx, other_pos[1] - ty)
                if sep < 5.0:
                    # Alejarse lateralmente del compañero
                    if other_pos[1] > ty:
                        ty -= 3.0
                    else:
                        ty += 3.0

        # Respetar zona del rol — no salir demasiado de casa
        tx = hx + (tx - hx) * 0.8
        ty = hy + (ty - hy) * 0.8

        # Límites del campo
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
