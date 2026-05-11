import math
from agent.coordinator import get_coordinator
from agent.utility import best_action, _best_teammate


class AgentFSM:
    GOAL_X     =  52.5
    GOAL_Y     =   0.0
    OWN_GOAL_X = -52.5

    DEAD_BALL_MODES = (
        "kick_in_l", "kick_in_r",
        "corner_kick_l", "corner_kick_r",
        "free_kick_l", "free_kick_r",
        "goal_kick_l", "goal_kick_r",
        "back_pass_l", "back_pass_r",
        "indirect_free_kick_l", "indirect_free_kick_r",
        "offside_l", "offside_r",
        "free_kick_fault_l", "free_kick_fault_r",
    )

    def __init__(self, unum, role, role_manager, team_name="team"):
        self.unum      = unum
        self.role      = role
        self.rm        = role_manager
        self.team_name = team_name
        self.state     = "WAIT"
        self._tick     = 0
        self.coord     = get_coordinator(team_name)

    def step(self, wm):
        self._tick += 1

        if not hasattr(wm, 'ball_vel'):
            wm.ball_vel = (0.0, 0.0)
        if not hasattr(wm, 'ball_pred'):
            wm.ball_pred = wm.ball_pos

        self.coord.update(self.unum, wm.self_pos, wm.ball_pos,
                          wm.ball_kickable, wm.ball_dist)

        # Modos de pausa total
        if wm.play_mode in ("before_kick_off", "half_time",
                            "time_over", "game_over"):
            self.state = "WAIT"
            return self._go_home(wm)

        # Kick-off
        if wm.play_mode in ("kick_off_l", "kick_off_r"):
            if self.unum == 11:
                if wm.ball_kickable:
                    self.state = "KICKOFF"
                    return {"kick": (30.0, 0.0)}
                return self._chase(wm)
            self.state = "WAIT"
            return self._go_home(wm)

        # Balón parado
        if wm.play_mode in self.DEAD_BALL_MODES:
            return self._dead_ball(wm)

        # Sin balón visible — girar buscándolo
        if wm.ball_pos is None or wm.ball_dist > 990:
            self.state = "SEARCH"
            return {"turn": 30.0, "dash": 30.0}

        if self.role == "goalkeeper":
            return self._goalkeeper(wm)
        elif self.role == "defender":
            return self._defender(wm)
        elif self.role == "midfielder":
            return self._midfielder(wm)
        elif self.role == "forward":
            return self._forward(wm)
        return self._chase(wm)

    # ═══════════════════════════════════════════════════════════════
    # BALÓN PARADO
    # ═══════════════════════════════════════════════════════════════

    def _dead_ball(self, wm):
        is_our_ball = (
            (wm.play_mode.endswith("_l") and wm.side == "l") or
            (wm.play_mode.endswith("_r") and wm.side == "r")
        )
        if is_our_ball:
            if wm.ball_kickable:
                self.state = "DEADBALL_KICK"
                return self._deadball_kick(wm)
            else:
                i_am_chaser = self.coord.elect_chaser(
                    self.unum, wm.ball_pos, self.role)
                if i_am_chaser and self.role != "goalkeeper":
                    self.state = "CHASE"
                    return self._chase(wm)
                self.state = "OPEN"
                return self._move_to(self._open_position(wm), wm)
        else:
            self.state = "DEFEND_DEAD"
            home = self.rm.get_home_position(self.unum)
            if wm.ball_pos and self.role != "goalkeeper":
                bx, by = wm.ball_pos
                tx = home[0] * 0.5 + bx * 0.5
                ty = home[1] * 0.5 + by * 0.5
                tx = max(-51.0, min(51.0, tx))
                ty = max(-32.0, min(32.0, ty))
                return self._move_to((tx, ty), wm)
            return self._move_to(home, wm)

    def _deadball_kick(self, wm):
        if not wm.ball_pos:
            return {"kick": (60.0, 0.0)}
        bx, by = wm.ball_pos
        tm = _best_teammate(wm)
        if tm:
            tx, ty, dist, _ = tm
            abs_angle = math.degrees(math.atan2(ty - by, tx - bx))
            rel_angle = self._rel_angle(abs_angle, wm.self_angle)
            if abs(rel_angle) < 90.0:
                power = min(90.0, max(40.0, dist * 3.0))
                return {"kick": (power, rel_angle)}
        goal_abs = math.degrees(math.atan2(self.GOAL_Y - by, self.GOAL_X - bx))
        goal_rel = self._rel_angle(goal_abs, wm.self_angle)
        lateral  = 25.0 if by < 0 else -25.0
        final    = goal_rel * 0.6 + lateral * 0.4
        return {"kick": (70.0, final)}

    def _open_position(self, wm):
        home = self.rm.get_home_position(self.unum)
        if not wm.ball_pos:
            return home
        bx, by = wm.ball_pos
        hx, hy = home
        tx = max(hx, min(50.0, bx + 8.0))
        if hy >= 0:
            ty = max(2.0, min(30.0, by + 6.0))
        else:
            ty = min(-2.0, max(-30.0, by - 6.0))
        return (tx, ty)

    # ═══════════════════════════════════════════════════════════════
    # ROLES
    # ═══════════════════════════════════════════════════════════════

    def _goalkeeper(self, wm):
        if wm.ball_kickable:
            self.state = "CLEAR"
            side_angle = 35.0 if (wm.ball_pos and wm.ball_pos[1] >= 0) else -35.0
            return {"kick": (85.0, side_angle)}
        in_own_area = wm.ball_pos and wm.ball_pos[0] < -38.0
        if in_own_area and wm.ball_dist < 15.0:
            self.state = "CHASE"
            return self._chase(wm)
        self.state = "POSITION"
        gk_x = max(-50.0, min(-42.0,
               self.OWN_GOAL_X + 0.3 * (wm.ball_pos[0] - self.OWN_GOAL_X)
               if wm.ball_pos else -50.0))
        gk_y = max(-6.0, min(6.0,
               wm.ball_pos[1] * 0.2 if wm.ball_pos else 0.0))
        return self._move_to((gk_x, gk_y), wm)

    def _defender(self, wm):
        if wm.ball_kickable:
            self.state = "CLEAR"
            tm = _best_teammate(wm)
            if tm:
                tx, ty, dist, _ = tm
                bx = wm.ball_pos[0] if wm.ball_pos else 0
                by = wm.ball_pos[1] if wm.ball_pos else 0
                abs_a = math.degrees(math.atan2(ty - by, tx - bx))
                rel_a = self._rel_angle(abs_a, wm.self_angle)
                power = min(90.0, max(40.0, dist * 3.2))
                return {"kick": (power, rel_a)}
            side = 20.0 if (wm.ball_pos and wm.ball_pos[1] >= 0) else -20.0
            return {"kick": (85.0, side)}

        i_am_chaser = self.coord.elect_chaser(self.unum, wm.ball_pos, self.role)
        if i_am_chaser:
            self.state = "CHASE"
            return self._chase(wm)

        # Solo posicionarse si ve el balón
        if wm.ball_pos is not None and wm.ball_dist < 60.0:
            self.state = "SUPPORT"
            home = self.rm.get_home_position(self.unum)
            bx, by = wm.ball_pos
            zx = max(self.OWN_GOAL_X + 3, min(0.0,
                 home[0] * 0.7 + bx * 0.3))
            zy = max(-30.0, min(30.0, home[1] * 0.6 + by * 0.4))
            return self._move_to((zx, zy), wm)

        # Sin ver el balón — girar buscándolo
        self.state = "SEARCH"
        return {"turn": 30.0, "dash": 20.0}

    def _midfielder(self, wm):
        if wm.ball_kickable:
            action, utils = best_action(wm)
            self.state = action
            return self._execute_action(action, wm)

        i_am_chaser = self.coord.elect_chaser(self.unum, wm.ball_pos, self.role)
        if i_am_chaser:
            self.state = "CHASE"
            return self._chase(wm)

        # Solo ir a soporte si ve el balón
        if wm.ball_pos is not None and wm.ball_dist < 60.0:
            self.state = "SUPPORT"
            home   = self.rm.get_home_position(self.unum)
            target = self.coord.get_support_positions(
                self.unum, wm.ball_pos, home, wm.side)
            return self._move_to(target, wm)

        # Sin ver el balón — girar buscándolo
        self.state = "SEARCH"
        return {"turn": 30.0, "dash": 20.0}

    def _forward(self, wm):
        if wm.ball_kickable:
            action, utils = best_action(wm)
            self.state = action
            return self._execute_action(action, wm)

        i_am_chaser = self.coord.elect_chaser(self.unum, wm.ball_pos, self.role)
        if i_am_chaser:
            self.state = "CHASE"
            return self._chase(wm)

        # Solo correr en profundidad si ve el balón
        if wm.ball_pos is not None and wm.ball_dist < 50.0:
            self.state = "RUN"
            return self._move_to(self._run_depth(wm), wm)

        # Sin ver el balón — girar buscándolo
        self.state = "SEARCH"
        return {"turn": 30.0, "dash": 20.0}

    # ═══════════════════════════════════════════════════════════════
    # EJECUTOR DE ACCIONES
    # ═══════════════════════════════════════════════════════════════

    def _execute_action(self, action, wm):
        if action == "PASS":
            return self._pass_to_best(wm)
        elif action == "SHOOT":
            return self._shoot(wm)
        elif action == "DRIBBLE_ESC":
            return self._dribble_away(wm)
        else:
            return self._dribble_forward(wm)

    # ═══════════════════════════════════════════════════════════════
    # ACCIONES DE BALÓN
    # ═══════════════════════════════════════════════════════════════

    def _chase(self, wm):
        angle = wm.ball_angle
        if abs(angle) < 5.0:
            return {"turn": 0.0, "dash": self.rm.get_dash_base(self.unum)}
        turn  = self._smooth_turn(angle, 60.0)
        power = max(60.0, self._dash_power(wm, abs(angle)))
        return {"turn": turn, "dash": power}

    def _shoot(self, wm):
        bx = wm.ball_pos[0] if wm.ball_pos else 0
        by = wm.ball_pos[1] if wm.ball_pos else 0
        abs_angle = math.degrees(math.atan2(self.GOAL_Y - by, self.GOAL_X - bx))
        rel_angle = self._rel_angle(abs_angle, wm.self_angle)
        return {"kick": (100.0, rel_angle)}

    def _pass_to_best(self, wm):
        tm = _best_teammate(wm)
        if not tm or not wm.ball_pos:
            return self._dribble_forward(wm)
        tx, ty, dist, _ = tm
        bx, by = wm.ball_pos
        abs_angle = math.degrees(math.atan2(ty - by, tx - bx))
        rel_angle = self._rel_angle(abs_angle, wm.self_angle)
        power = min(95.0, max(40.0, dist * 3.5))
        return {"kick": (power, rel_angle)}

    def _dribble_forward(self, wm):
        bx = wm.ball_pos[0] if wm.ball_pos else 0
        by = wm.ball_pos[1] if wm.ball_pos else 0
        abs_angle = math.degrees(math.atan2(self.GOAL_Y - by, self.GOAL_X - bx))
        rel_angle = self._rel_angle(abs_angle, wm.self_angle)
        return {"kick": (35.0, rel_angle), "dash": 80.0}

    def _dribble_away(self, wm):
        if not wm.opponents or not wm.ball_pos:
            return self._dribble_forward(wm)
        closest   = min(wm.opponents, key=lambda o: o.get("dist", 999))
        opp_angle = closest.get("angle", 0)
        escape    = opp_angle + 180 + self._jitter() * 5
        bx, by    = wm.ball_pos
        goal_abs  = math.degrees(math.atan2(self.GOAL_Y - by, self.GOAL_X - bx))
        goal_rel  = self._rel_angle(goal_abs, wm.self_angle)
        final     = goal_rel * 0.6 + escape * 0.4
        return {"kick": (30.0, final), "dash": 90.0}

    def _go_home(self, wm):
        return {"move": self.rm.get_home_position(self.unum)}

    def _move_to(self, target, wm):
        tx, ty = target
        sx, sy = wm.self_pos
        dist   = math.hypot(tx - sx, ty - sy)
        if dist < 1.0:
            if wm.ball_pos:
                abs_a = math.degrees(math.atan2(
                    wm.ball_pos[1] - sy, wm.ball_pos[0] - sx))
                return {"turn": self._smooth_turn(
                    self._rel_angle(abs_a, wm.self_angle), 20.0), "dash": 0.0}
            return {"turn": 0.0, "dash": 0.0}
        abs_angle = math.degrees(math.atan2(ty - sy, tx - sx))
        rel_angle = self._rel_angle(abs_angle, wm.self_angle)
        turn  = self._smooth_turn(rel_angle, 35.0)
        power = self._dash_power(wm, abs(rel_angle))
        return {"turn": turn, "dash": power}

    def _run_depth(self, wm):
        home = self.rm.get_home_position(self.unum)
        if wm.ball_pos:
            return (max(home[0], min(45.0, wm.ball_pos[0] + 10.0)), home[1])
        return home

    # ═══════════════════════════════════════════════════════════════
    # UTILIDADES
    # ═══════════════════════════════════════════════════════════════

    def _rel_angle(self, abs_angle, self_angle):
        diff = abs_angle - self_angle
        while diff >  180: diff -= 360
        while diff < -180: diff += 360
        return diff

    def _smooth_turn(self, angle, max_turn=35.0):
        while angle >  180: angle -= 360
        while angle < -180: angle += 360
        return max(-max_turn, min(max_turn, angle))

    def _dash_power(self, wm, angle_diff):
        base = self.rm.get_dash_base(self.unum)
        if   angle_diff > 60: base *= 0.2
        elif angle_diff > 30: base *= 0.6
        elif angle_diff > 15: base *= 0.85
        if   wm.stamina_pct < 0.3: base *= 0.6
        elif wm.stamina_pct < 0.6: base *= 0.85
        return round(base, 1)

    def _jitter(self):
        return (self._tick % 7 - 3)
