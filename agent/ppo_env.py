"""
Ambiente Gymnasium para entrenar agente PPO en RoboCup 2D.
Observación: [ball_dist_norm, ball_angle_norm, stamina_norm,
              opp_pressure, teammate_near, ball_kickable,
              zona_x, vel_x, vel_y, accion_anterior]
Acciones: 0=CHASE, 1=PASS, 2=DRIBBLE_FWD, 3=DRIBBLE_ESC, 4=SHOOT, 5=TURN_SEARCH
"""
import gymnasium as gym
import numpy as np
import socket
import time
import re
import math
from gymnasium import spaces


class RoboCupEnv(gym.Env):
    metadata = {"render_modes": []}

    OBS_SIZE = 10
    ACT_SIZE = 6

    def __init__(self, team_name="PPOTeam", port=6000, unum=11):
        super().__init__()
        self.team_name   = team_name
        self.port        = port
        self.unum_target = unum
        self.sock        = None
        self.server_addr = ("127.0.0.1", port)
        self._side       = "l"
        self._connected  = False
        self._unum       = None

        # Estado del jugador
        self._ball_dist     = 9999.0
        self._ball_angle    = 0.0
        self._ball_kickable = False
        self._stamina       = 8000.0
        self._opponents     = []
        self._teammates     = []
        self._play_mode     = "before_kick_off"
        self._head_angle    = 0.0

        # Métricas
        self._possession_ticks = 0
        self._total_ticks      = 0
        self._last_action      = 0
        self._steps_no_ball    = 0

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

        # Intentar conectar
        for attempt in range(3):
            self.sock.sendto(
                f"(init {self.team_name} (version 16))".encode(),
                self.server_addr
            )
            buf = ""
            t0  = time.time()
            while time.time() - t0 < 4.0:
                try:
                    data, self.server_addr = self.sock.recvfrom(8192)
                    buf += data.decode(errors="ignore")
                    m = re.search(r"\(init\s+([lrLR])\s+(\d+)", buf)
                    if m:
                        self._side = m.group(1).lower()
                        self._unum = int(m.group(2))
                        print(f"[PPOEnv] Conectado side={self._side} unum={self._unum}")
                        self._connected = True
                        return True
                except socket.timeout:
                    continue
            print(f"[PPOEnv] Reintentando conexión {attempt+1}/3...")
            time.sleep(1.0)
        return False

    def _safe_send(self, msg):
        try:
            if not msg.endswith("\n"):
                msg += "\n"
            self.sock.sendto(msg.encode(), self.server_addr)
        except Exception as e:
            pass

    def _recv_messages(self, timeout=0.15):
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
        ball      = None
        teammates = []
        opponents = []
        obj_re = re.compile(r'\(\(([^)]+)\)\s+([\d.]+)\s+([-\d.]+)')
        for m in obj_re.finditer(msg):
            name  = m.group(1).strip()
            dist  = float(m.group(2))
            angle = float(m.group(3))
            if name == "b":
                ball = {"dist": dist, "angle": angle}
            elif name.startswith("p "):
                parts = name.split(None, 2)
                tname = parts[1].strip('"\'') if len(parts) > 1 else ""
                if tname == self.team_name:
                    teammates.append({"dist": dist, "angle": angle})
                else:
                    opponents.append({"dist": dist, "angle": angle})
        return ball, teammates, opponents

    def _get_obs(self):
        bd    = min(self._ball_dist, 100.0) / 100.0
        ba    = max(-1.0, min(1.0, self._ball_angle / 180.0))
        kick  = 1.0 if self._ball_kickable else 0.0
        stam  = min(1.0, self._stamina / 8000.0)

        opp_d = 1.0
        if self._opponents:
            opp_d = min(1.0, min(o["dist"] for o in self._opponents) / 30.0)

        tm_d = 1.0
        if self._teammates:
            tm_d = min(1.0, min(t["dist"] for t in self._teammates) / 30.0)

        press   = max(0.0, min(1.0, 1.0 - opp_d))
        no_ball = min(1.0, self._steps_no_ball / 50.0)
        zona    = min(1.0, max(-1.0, self._ball_angle / 90.0))
        act     = self._last_action / self.ACT_SIZE

        return np.array([
            bd, ba, kick, stam,
            opp_d, tm_d, press, no_ball,
            zona, act
        ], dtype=np.float32)

    def _compute_reward(self, prev_dist, prev_kickable):
        r = 0.0

        # Recompensa principal: tener el balón
        if self._ball_kickable:
            r += 5.0
            self._possession_ticks += 1

        # Recompensa por acercarse al balón
        if self._ball_dist < 9990 and prev_dist < 9990:
            delta = prev_dist - self._ball_dist
            r += delta * 0.3   # positivo si se acercó

        # Recompensa por ver el balón
        if self._ball_dist < 9990:
            r += 0.5
            self._steps_no_ball = 0
        else:
            self._steps_no_ball += 1
            r -= 0.2   # penalización leve por no ver el balón

        # Penalización por perder el balón
        if prev_kickable and not self._ball_kickable:
            r -= 3.0

        # Penalización por estar muy lejos
        if self._ball_dist > 30.0:
            r -= 0.3

        return r

    def _action_to_cmd(self, action):
        """Convierte acción a comando RoboCup."""
        self._last_action = action

        if action == 5:  # TURN_SEARCH — girar buscando balón
            return "(turn 30)"

        if not self._ball_kickable and action not in [0, 5]:
            # Sin balón — siempre perseguir
            action = 0

        if action == 0:  # CHASE
            angle = self._ball_angle
            if self._ball_dist > 9990:
                # No ve el balón — girar buscando
                return "(turn 30)"
            if abs(angle) < 5.0:
                return "(dash 80)"
            turn = max(-60.0, min(60.0, angle))
            # También dasha aunque gire
            return f"(turn {turn:.1f})"

        elif action == 1:  # PASS
            if self._teammates:
                tm = min(self._teammates, key=lambda t: t["dist"])
                return f"(kick 65 {tm['angle']:.1f})"
            return "(kick 50 0)"

        elif action == 2:  # DRIBBLE_FWD
            return "(kick 20 0)"

        elif action == 3:  # DRIBBLE_ESC
            if self._opponents:
                opp = min(self._opponents, key=lambda o: o["dist"])
                esc = opp["angle"] + 90
                return f"(kick 25 {esc:.1f})"
            return "(kick 20 45)"

        elif action == 4:  # SHOOT
            return "(kick 100 0)"

        return "(turn 10)"

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self._possession_ticks = 0
        self._total_ticks      = 0
        self._last_action      = 0
        self._ball_kickable    = False
        self._ball_dist        = 9999.0
        self._ball_angle       = 0.0
        self._steps_no_ball    = 0

        if not self._connected:
            ok = self._connect()
            if not ok:
                print("[PPOEnv] ERROR: No se pudo conectar al servidor")
                return self._get_obs(), {}

        # Posicionarse según el lado
        if self._side == "l":
            self._safe_send("(move -5.0 12.0)")
        else:
            self._safe_send("(move 5.0 -12.0)")

        time.sleep(0.3)
        # Recibir mensajes iniciales
        msgs = self._recv_messages(timeout=0.5)
        for msg in msgs:
            self._process_msg(msg)

        return self._get_obs(), {}

    def _process_msg(self, msg):
        """Procesa un mensaje del servidor."""
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
            am = re.search(r'\(head_angle\s+([-\d.]+)\)', msg)
            if am:
                self._head_angle = float(am.group(1))

    def step(self, action):
        self._total_ticks += 1
        prev_dist     = self._ball_dist
        prev_kickable = self._ball_kickable

        # Enviar acción
        cmd = self._action_to_cmd(action)
        self._safe_send(cmd)

        # Si CHASE, también mandar dash en el mismo tick
        if action == 0 and self._ball_dist < 9990 and abs(self._ball_angle) > 5:
            time.sleep(0.02)
            self._safe_send("(dash 80)")

        # Recibir respuesta del servidor
        msgs = self._recv_messages(timeout=0.15)
        for msg in msgs:
            self._process_msg(msg)

        reward   = self._compute_reward(prev_dist, prev_kickable)
        obs      = self._get_obs()
        done     = self._play_mode in ("time_over", "game_over")
        truncated= self._total_ticks >= 3000

        return obs, reward, done, truncated, {}

    def close(self):
        if self.sock:
            try: self.sock.close()
            except: pass
        self._connected = False
