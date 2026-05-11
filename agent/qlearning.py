import json
import os
import random
import math
import threading

ACTIONS       = ["PASS", "DRIBBLE_FWD", "DRIBBLE_ESC", "SHOOT"]
ALPHA         = 0.15
GAMMA         = 0.92
EPSILON_START = 0.4
EPSILON_MIN   = 0.05
EPSILON_DECAY = 0.9995

_global_lock = threading.Lock()


def _get_qfile(team_name):
    return f"logs/qtable_{team_name}.json"


def _discretize(opp_pressure, x_zone, teammate_free):
    p = 1 if opp_pressure else 0
    z = max(0, min(4, x_zone))
    t = 1 if teammate_free else 0
    return (p, z, t)


class QAgent:
    def __init__(self, team_name="team"):
        self.team_name    = team_name
        self.q_file       = _get_qfile(team_name)
        self.q            = {}
        self.epsilon      = EPSILON_START
        self._last_state  = None
        self._last_action = None
        self._lock        = threading.Lock()
        self._load()

    def _load(self):
        os.makedirs("logs", exist_ok=True)
        # Intentar cargar tabla propia del equipo
        if os.path.exists(self.q_file):
            try:
                with open(self.q_file, "r") as f:
                    content = f.read().strip()
                if content:
                    raw = json.loads(content)
                    self.q = {eval(k): v for k, v in raw.items()}
                    print(f"[QAgent-{self.team_name}] Tabla cargada: {len(self.q)} estados")
                    return
            except Exception as e:
                print(f"[QAgent-{self.team_name}] Error cargando: {e}")
                self.q = {}
        # Si no hay tabla propia, intentar cargar la fusionada
        merged = "logs/qtable_merged.json"
        if os.path.exists(merged):
            try:
                with open(merged, "r") as f:
                    content = f.read().strip()
                if content:
                    raw = json.loads(content)
                    self.q = {eval(k): v for k, v in raw.items()}
                    print(f"[QAgent-{self.team_name}] Tabla fusionada cargada: {len(self.q)} estados")
                    return
            except Exception:
                pass
        print(f"[QAgent-{self.team_name}] Tabla nueva")

    def save(self, verbose=False):
        os.makedirs("logs", exist_ok=True)
        try:
            with self._lock:
                data = {str(k): v for k, v in self.q.items()}
            with open(self.q_file, "w") as f:
                json.dump(data, f, indent=2)
            if verbose:
                print(f"[QAgent-{self.team_name}] Tabla guardada: {len(self.q)} estados")
        except Exception as e:
            print(f"[QAgent-{self.team_name}] Error guardando: {e}")

    def __del__(self):
        try:
            self.save(verbose=True)
        except Exception:
            pass

    def _get_q(self, state, action_idx):
        return self.q.get(state, [0.0] * len(ACTIONS))[action_idx]

    def _set_q(self, state, action_idx, value):
        with self._lock:
            if state not in self.q:
                self.q[state] = [0.0] * len(ACTIONS)
            self.q[state][action_idx] = value

    def get_state(self, wm):
        opp_pressure = any(o.get("dist", 999) < 3.5 for o in wm.opponents)
        bx = wm.ball_pos[0] if wm.ball_pos else 0
        if   bx < -30: z = 0
        elif bx < -10: z = 1
        elif bx <  10: z = 2
        elif bx <  30: z = 3
        else:          z = 4
        teammate_free = False
        for tm in wm.teammates:
            if 2 < tm.get("dist", 999) < 20:
                abs_a = wm.self_angle + tm.get("angle", 0)
                tx = wm.self_pos[0] + tm["dist"] * math.cos(math.radians(abs_a))
                if tx > (wm.ball_pos[0] if wm.ball_pos else 0):
                    teammate_free = True
                    break
        return _discretize(opp_pressure, z, teammate_free)

    def choose_action(self, state):
        if random.random() < self.epsilon:
            return random.randint(0, len(ACTIONS) - 1)
        q_vals = self.q.get(state, [0.0] * len(ACTIONS))
        return q_vals.index(max(q_vals))

    def reward(self, wm, action_idx, lost_ball):
        r           = 0.0
        action_name = ACTIONS[action_idx]
        bx          = wm.ball_pos[0] if wm.ball_pos else 0
        if lost_ball:
            r -= 3.0
        else:
            r += 2.0
        if action_name == "SHOOT" and bx > 30:
            r += 1.0
        if action_name == "DRIBBLE_FWD" and bx < -10:
            r -= 1.0
        return r

    def update(self, state, action_idx, reward_val, next_state):
        old_q    = self._get_q(state, action_idx)
        next_max = max(self.q.get(next_state, [0.0] * len(ACTIONS)))
        new_q    = old_q + ALPHA * (reward_val + GAMMA * next_max - old_q)
        self._set_q(state, action_idx, new_q)
        self.epsilon = max(EPSILON_MIN, self.epsilon * EPSILON_DECAY)

    def step_with_ball(self, wm):
        state             = self.get_state(wm)
        action_idx        = self.choose_action(state)
        self._last_state  = state
        self._last_action = action_idx
        return ACTIONS[action_idx]

    def feedback(self, wm, lost_ball):
        if self._last_state is None:
            return
        next_state = self.get_state(wm)
        r          = self.reward(wm, self._last_action, lost_ball)
        self.update(self._last_state, self._last_action, r, next_state)
        self._last_state  = None
        self._last_action = None


_qagents = {}
_qa_lock  = threading.Lock()


def get_qagent(team_name):
    with _qa_lock:
        if team_name not in _qagents:
            _qagents[team_name] = QAgent(team_name)
        return _qagents[team_name]


def merge_tables():
    """Fusiona las tablas de ambos equipos en una sola."""
    os.makedirs("logs", exist_ok=True)
    merged = {}
    for fname in os.listdir("logs"):
        if fname.startswith("qtable_") and fname.endswith(".json") and "merged" not in fname:
            fpath = os.path.join("logs", fname)
            try:
                with open(fpath, "r") as f:
                    content = f.read().strip()
                if not content:
                    continue
                data = json.loads(content)
                for k, v in data.items():
                    state = eval(k)
                    if state not in merged:
                        merged[state] = v
                    else:
                        # Promediar los valores Q de ambos equipos
                        merged[state] = [
                            (merged[state][i] + v[i]) / 2
                            for i in range(len(v))
                        ]
            except Exception as e:
                print(f"[merge] Error con {fname}: {e}")
    if merged:
        with open("logs/qtable_merged.json", "w") as f:
            json.dump({str(k): v for k, v in merged.items()}, f, indent=2)
        print(f"[merge] Tabla fusionada: {len(merged)} estados")
    return merged
