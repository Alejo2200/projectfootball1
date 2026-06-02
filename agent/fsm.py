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

    GOAL_MODES = (
        "goal_l", "goal_r",
        "goal_l_1", "goal_r_1",
        "goal_l_2", "goal_r_2",
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

        if wm.play_mode in ("before_kick_off", "half_time",
                            "time_over", "game_over"):
            self.state = "WAIT"
            return self._go_home(wm)

        if wm.play_mode in self.GOAL_MODES:
            self.state = "WAIT"
            return self._go_home(wm)

        if wm.play_mode in ("kick_off_l", "kick_off_r"):
            if self.unum == 11:
                if wm.ball_kickable:
                    self.state = "KICKOFF"
                    return {"kick": (30.0, 0.0)}
                return self._chase(wm)
            self.state = "WAIT"
            return self._go_home(wm)

        if wm.play_mode in self.DEAD_BALL_MODES:
            return self._dead_ball(wm)

        if wm.ball_pos is None or wm.ball_dist > 990:
            if self.state == "CHASE" and abs(wm.ball_angle) < 180:
                return {"turn": self._smooth_turn(wm.ball_angle, 30.0),
                        "dash": 60.0}
            self.state = "SEARCH"
            return {"turn": 45.0, "dash": 0.0}

        if self.role == "goalkeeper":
            return self._goalkeeper(wm)
        elif self.role == "defender":
            return self._defender(wm)
        elif self.role == "midfielder":
            return self._midfielder(wm)
        elif self.role == "forward":
            return self._forward(wm)
        return self._chase(wm)

    def _dead_ball(self, wm):
        is_our_ball = (
            (wm.play_mode.endswith("_l") and wm.side == "l") or
            (wm.play_mode.endswith("_r") and wm.side == "r")
        )
        if is_our_ball:
            if wm.ball_kickable:
                self.state = "DEADBALL_KICK"
                return self._deadball_kick(wm)
            i_am_chaser = self.coord.elect_chaser(
                self.unum, wm.ball_pos, self.role)
            if i_am_chaser and self.role != "goalkeeper":
                self.state = "CHASE"
                return self._chase(wm)
            self.state = "SUPPORT"
            home = self.rm.get_home_position(self.unum)
            return self._move_to(home, wm)
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

    def _goalkeeper(self, wm):
        if wm.ball_kickable:
            self.state = "CLEAR"
            tm = _best_teammate(wm)
            if tm:
                tx, ty, dist, _ = tm
                bx = wm.ball_pos[0] if wm.ball_pos else 0
                by = wm.ball_pos[1] if wm.ball_pos else 0
                abs_a = math.degrees(math.atan2(ty - by, tx - bx))
                rel_a = self._rel_angle(abs_a, wm.self_angle)
                power = min(85.0, max(50.0, dist * 3.0))
                return {"kick": (power, rel_a)}
            side_angle = 35.0 if (wm.ball_pos and wm.ball_pos[1] >= 0) else -35.0
            return {"kick": (85.0, side_angle)}
        if wm.ball_dist < 20.0:
            self.state = "CHASE"
            return self._chase(wm)
        self.state = "POSITION"
        if wm.ball_pos:
            by   = wm.ball_pos[1]
            gk_y = max(-6.0, min(6.0, by * 0.3))
        else:
            gk_y = 0.0
        gk_x       = -48.0
        target_abs = math.degrees(math.atan2(
            gk_y - wm.self_pos[1], gk_x - wm.self_pos[0]))
        rel    = self._rel_angle(target_abs, wm.self_angle)
        turn   = self._smooth_turn(rel, 35.0)
        dist_t = math.hypot(gk_x - wm.self_pos[0], gk_y - wm.self_pos[1])
        power  = min(60.0, max(20.0, dist_t * 5.0))
        return {"turn": turn, "dash": round(power, 1)}

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
        self.state = "SUPPORT"
        home = self.rm.get_home_position(self.unum)
        if wm.ball_pos:
            bx, by = wm.ball_pos
            zx = max(self.OWN_GOAL_X + 3, min(0.0,
                 home[0] * 0.7 + bx * 0.3))
            zy = max(-30.0, min(30.0, home[1] * 0.6 + by * 0.4))
        else:
            zx, zy = home
        return self._move_to((zx, zy), wm)

    def _midfielder(self, wm):
        if wm.ball_kickable:
            action, _ = best_action(wm)
            self.state = action
            return self._execute_action(action, wm)
        i_am_chaser = self.coord.elect_chaser(self.unum, wm.ball_pos, self.role)
        if i_am_chaser:
            self.state = "CHASE"
            return self._chase(wm)
        # Midfielder va al balón si está cerca
        if wm.ball_dist < 20.0:
            self.state = "CHASE"
            return self._chase(wm)
        self.state = "SUPPORT"
        home   = self.rm.get_home_position(self.unum)
        target = self.coord.get_support_positions(
            self.unum, wm.ball_pos, home, wm.side)
        return self._move_to(target, wm)

    def _forward(self, wm):
        if wm.ball_kickable:
            action, _ = best_action(wm)
            self.state = action
            return self._execute_action(action, wm)
        i_am_chaser = self.coord.elect_chaser(self.unum, wm.ball_pos, self.role)
        if i_am_chaser:
            self.state = "CHASE"
            return self._chase(wm)
        # Forward va al balón si está visible y cerca
        if wm.ball_dist < 40.0:
            self.state = "CHASE"
            return self._chase(wm)
        self.state = "RUN"
        return self._move_to(self._run_depth(wm), wm)

    def _execute_action(self, action, wm):
        if action == "PASS":
            return self._pass_to_best(wm)
        elif action == "SHOOT":
            return self._shoot(wm)
        elif action == "DRIBBLE_ESC":
            return self._dribble_away(wm)
        else:
            return self._dribble_forward(wm)

    def _chase(self, wm):
        angle = wm.ball_angle
        dist  = wm.ball_dist
        if dist < 2.0:
            power = 30.0
        elif dist < 5.0:
            power = 60.0
        elif dist < 15.0:
            power = 85.0
        else:
            power = self.rm.get_dash_base(self.unum)
        if wm.stamina_pct < 0.4:
            power *= 0.6
        elif wm.stamina_pct < 0.6:
            power *= 0.8
        if abs(angle) < 5.0:
            return {"turn": 0.0, "dash": round(power, 1)}
        if abs(angle) > 30:
            power *= 0.5
        turn = self._smooth_turn(angle, 60.0)
        return {"turn": turn, "dash": round(power, 1)}

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
        return {"kick": (20.0, rel_angle), "dash": 70.0}

    def _dribble_away(self, wm):
        if not wm.opponents or not wm.ball_pos:
            return self._dribble_forward(wm)
        closest   = min(wm.opponents, key=lambda o: o.get("dist", 999))
        opp_angle = closest.get("angle", 0)
        escape    = opp_angle + 90 + self._jitter() * 8
        bx, by    = wm.ball_pos
        goal_abs  = math.degrees(math.atan2(self.GOAL_Y - by, self.GOAL_X - bx))
        goal_rel  = self._rel_angle(goal_abs, wm.self_angle)
        final     = goal_rel * 0.5 + escape * 0.5
        return {"kick": (25.0, final), "dash": 80.0}

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
        power = min(100.0, max(30.0, dist * 8.0))
        if wm.stamina_pct < 0.4:
            power *= 0.6
        return {"turn": turn, "dash": round(power, 1)}

    def _run_depth(self, wm):
        home = self.rm.get_home_position(self.unum)
        if wm.ball_pos:
            return (max(home[0], min(45.0, wm.ball_pos[0] + 10.0)), home[1])
        return home

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
