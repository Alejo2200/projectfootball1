"""
Ambiente Gymnasium para entrenar agente PPO en RoboCup 2D.
Observación: [ball_dist, ball_angle, self_x, self_y, stamina_pct,
              opp_dist_min, teammate_dist_min, ball_kickable,
              zona_x, presion]
Acciones: 0=CHASE, 1=PASS, 2=DRIBBLE_FWD, 3=DRIBBLE_ESC, 4=SHOOT, 5=POSITION
"""
import gymnasium as gym
import numpy as np
import socket
import time
import re
import threading
import math
from gymnasium import spaces


class RoboCupEnv(gym.Env):
    metadata = {"render_modes": []}

    OBS_SIZE = 10
    ACT_SIZE = 6

    def __init__(self, team_name="PPOTeam", port=6000, unum=11):
        super().__init__()
        self.team_name  = team_name
        self.port       = port
        self.unum       = unum
        self.sock       = None
        self.server_addr= ("127.0.0.1", port)
        self._side      = "l"
        self._connected = False
        self._last_obs  = np.zeros(self.OBS_SIZE, dtype=np.float32)
        self._tick      = 0
        self._possession_ticks = 0
        self._total_ticks      = 0
        self._play_mode        = "before_kick_off"
        self._ball_kickable    = False
        self._ball_dist        = 9999.0
        self._ball_angle       = 0.0
        self._stamina          = 8000.0
        self._opponents        = []
        self._teammates        = []
        self._lock             = threading.Lock()
        self._msg_buffer       = []
        self._last_action      = 0

        self.observation_space = spaces.Box(
            low=-1.0, high=1.0,
            shape=(self.OBS_SIZE,),
            dtype=np.float32
        )
        self.action_space = spaces.Discrete(self.ACT_SIZE)

    def _connect(self):
        if self.sock:
            try: self.sock.close()
            except: pass
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("", 0))
        self.sock.settimeout(3.0)
        self.sock.sendto(
            f"(init {self.team_name} (version 16))".encode(),
            self.server_addr
        )
        buf = ""
        t0  = time.time()
        while time.time() - t0 < 5.0:
            try:
                data, self.server_addr = self.sock.recvfrom(8192)
                buf += data.decode(errors="ignore")
                m = re.search(r"\(init\s+([lrLR])\s+(\d+)", buf)
                if m:
                    self._side = m.group(1).lower()
                    print(f"[PPOEnv] Conectado side={self._side}")
                    self._connected = True
                    return True
            except socket.timeout:
                continue
        return False

    def _safe_send(self, msg):
        try:
            if not msg.endswith("\n"): msg += "\n"
            self.sock.sendto(msg.encode(), self.server_addr)
        except: pass

    def _recv_all(self, timeout=0.1):
        msgs = []
        self.sock.settimeout(timeout)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                data, _ = self.sock.recvfrom(8192)
                msgs.append(data.decode(errors="ignore"))
            except socket.timeout:
                break
        return msgs

    def _parse_see(self, msg):
        ball = None
        teammates = []
        opponents = []
        obj_re = re.compile(r'\(\(([^)]+)\)\s+([\d.]+)\s+([-\d.]+)')
        for m in obj_re.finditer(msg):
            name = m.group(1).strip()
            dist  = float(m.group(2))
            angle = float(m.group(3))
            if name == "b":
                ball = {"dist": dist, "angle": angle}
            elif name.startswith("p "):
                parts = name.split(None, 2)
                tname = parts[1].strip('"') if len(parts) > 1 else ""
                if tname == self.team_name:
                    teammates.append({"dist": dist, "angle": angle})
                else:
                    opponents.append({"dist": dist, "angle": angle})
        return ball, teammates, opponents

    def _get_obs(self):
        bd    = min(self._ball_dist, 100.0) / 100.0
        ba    = self._ball_angle / 180.0
        kick  = 1.0 if self._ball_kickable else 0.0
        stam  = self._stamina / 8000.0
        bx    = 0.0
        opp_d = 1.0
        if self._opponents:
            opp_d = min(o["dist"] for o in self._opponents) / 100.0
        tm_d  = 1.0
        if self._teammates:
            tm_d = min(t["dist"] for t in self._teammates) / 100.0
        press = max(0.0, 1.0 - opp_d * 5.0)
        zona  = 0.0
        if self._ball_dist < 100:
            zona  = self._ball_angle / 180.0
        obs = np.array([
            bd, ba, kick, stam,
            opp_d, tm_d, press, zona,
            bx, float(self._last_action) / self.ACT_SIZE
        ], dtype=np.float32)
        return np.clip(obs, -1.0, 1.0)

    def _compute_reward(self, action, prev_kickable):
        reward = 0.0
        # Recompensa principal: posesión del balón
        if self._ball_kickable:
            reward += 3.0
            self._possession_ticks += 1
        # Penalización por perder el balón
        if prev_kickable and not self._ball_kickable:
            reward -= 2.0
        # Recompensa por acercarse al balón
        if self._ball_dist < 5.0:
            reward += 0.5
        elif self._ball_dist < 15.0:
            reward += 0.2
        # Penalización por estar lejos del balón
        if self._ball_dist > 30.0:
            reward -= 0.3
        # Recompensa por pase exitoso (compañero recibe)
        if action == 1 and self._teammates:
            min_tm = min(t["dist"] for t in self._teammates)
            if min_tm < 3.0:
                reward += 1.5
        # Penalización por disparar desde lejos
        if action == 4 and self._ball_dist > 20.0:
            reward -= 1.0
        return reward

    def _action_to_cmd(self, action):
        if action == 0:   # CHASE
            if abs(self._ball_angle) < 5:
                return f"(dash 80)"
            turn = max(-60.0, min(60.0, self._ball_angle))
            return f"(turn {turn:.1f})"
        elif action == 1: # PASS
            if self._teammates:
                tm = min(self._teammates, key=lambda t: t["dist"])
                angle = tm["angle"]
                return f"(kick 60 {angle:.1f})"
            return f"(kick 40 0)"
        elif action == 2: # DRIBBLE_FWD
            return f"(kick 20 0)"
        elif action == 3: # DRIBBLE_ESC
            if self._opponents:
                opp = min(self._opponents, key=lambda o: o["dist"])
                esc = opp["angle"] + 90
                return f"(kick 25 {esc:.1f})"
            return f"(kick 20 45)"
        elif action == 4: # SHOOT
            return f"(kick 100 0)"
        else:             # POSITION
            return f"(turn 20)"

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self._tick             = 0
        self._possession_ticks = 0
        self._total_ticks      = 0
        self._last_action      = 0
        self._ball_kickable    = False
        self._ball_dist        = 9999.0
        self._ball_angle       = 0.0

        if not self._connected:
            ok = self._connect()
            if not ok:
                return self._get_obs(), {}

        self._safe_send("(move -5.0 12.0)")
        time.sleep(0.5)
        return self._get_obs(), {}

    def step(self, action):
        self._last_action  = action
        prev_kickable      = self._ball_kickable
        self._total_ticks += 1

        # Enviar acción solo si tiene el balón o está cerca
        if self._ball_kickable or self._ball_dist < 3.0:
            cmd = self._action_to_cmd(action)
        else:
            # Sin balón — siempre perseguir
            if abs(self._ball_angle) < 5:
                cmd = "(dash 80)"
            else:
                turn = max(-60.0, min(60.0, self._ball_angle))
                cmd  = f"(turn {turn:.1f})"

        self._safe_send(cmd)

        # Recibir mensajes del servidor
        msgs = self._recv_all(timeout=0.15)
        for msg in msgs:
            if msg.startswith("(see"):
                ball, tms, opps = self._parse_see(msg)
                if ball:
                    self._ball_dist     = ball["dist"]
                    self._ball_angle    = ball["angle"]
                    self._ball_kickable = ball["dist"] <= 1.0
                else:
                    self._ball_dist     = 9999.0
                    self._ball_kickable = False
                self._teammates = tms
                self._opponents = opps
            elif msg.startswith("(hear"):
                m = re.search(r'\(hear\s+\S+\s+referee\s+(\w+)\)', msg)
                if m:
                    self._play_mode = m.group(1)
            elif msg.startswith("(sense_body"):
                sm = re.search(r'\(stamina\s+([\d.]+)', msg)
                if sm:
                    self._stamina = float(sm.group(1))

        reward   = self._compute_reward(action, prev_kickable)
        obs      = self._get_obs()
        done     = self._play_mode in ("time_over", "game_over")
        truncated= self._total_ticks >= 3000

        return obs, reward, done, truncated, {}

    def close(self):
        if self.sock:
            try: self.sock.close()
            except: pass
        self._connected = False
