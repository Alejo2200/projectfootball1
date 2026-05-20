"""
Jugador que usa el modelo PPO entrenado.
Se integra con el FSM existente — PPO decide la acción cuando
el jugador es el chaser o tiene el balón.
"""
import os
import numpy as np
import math

MODEL_PATH = "models/ppo_robocup_latest"
_model     = None


def load_model():
    global _model
    if _model is not None:
        return _model
    if not os.path.exists(MODEL_PATH + ".zip"):
        print("[PPO] Sin modelo entrenado, usando FSM base")
        return None
    try:
        from stable_baselines3 import PPO
        _model = PPO.load(MODEL_PATH)
        print("[PPO] Modelo cargado correctamente")
        return _model
    except Exception as e:
        print(f"[PPO] Error cargando modelo: {e}")
        return None


def wm_to_obs(wm):
    """Convierte WorldModel a observación para PPO."""
    bd   = min(wm.ball_dist, 100.0) / 100.0
    ba   = (wm.ball_angle or 0.0) / 180.0
    kick = 1.0 if wm.ball_kickable else 0.0
    stam = wm.stamina_pct

    opp_d = 1.0
    if wm.opponents:
        opp_d = min(o.get("dist", 100) for o in wm.opponents) / 100.0

    tm_d = 1.0
    if wm.teammates:
        tm_d = min(t.get("dist", 100) for t in wm.teammates) / 100.0

    press = max(0.0, 1.0 - opp_d * 5.0)
    zona  = ba

    bx = 0.0
    if wm.ball_pos:
        bx = wm.ball_pos[0] / 52.5

    obs = np.array([
        bd, ba, kick, stam,
        opp_d, tm_d, press, zona,
        bx, 0.0
    ], dtype=np.float32)
    return np.clip(obs, -1.0, 1.0)


ACTIONS = ["CHASE", "PASS", "DRIBBLE_FWD", "DRIBBLE_ESC", "SHOOT", "POSITION"]


def ppo_decide(wm):
    """
    Usa el modelo PPO para decidir la acción.
    Retorna nombre de acción como string.
    """
    model = load_model()
    if model is None:
        return "CHASE"
    obs        = wm_to_obs(wm)
    action, _  = model.predict(obs, deterministic=True)
    return ACTIONS[int(action)]
