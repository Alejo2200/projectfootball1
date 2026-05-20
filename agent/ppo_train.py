"""
Entrena el agente PPO para maximizar posesión del balón.
Uso: python3 agent/ppo_train.py 10000
Requiere: rcssserver corriendo + RivalFC conectado
"""
import os
import sys

from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.callbacks import CheckpointCallback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.ppo_env import RoboCupEnv

MODEL_DIR = "models"
LOG_DIR   = "logs/ppo"
os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(LOG_DIR,   exist_ok=True)


def train(total_steps=10_000):
    print("=" * 50)
    print("  Entrenando PPO para posesión de balón")
    print(f"  Steps totales: {total_steps:,}")
    print("=" * 50)
    print()
    print("IMPORTANTE: Antes de correr esto asegúrate de:")
    print("  1. rcssserver corriendo en terminal 1")
    print("  2. python3 run_team.py --team RivalFC en terminal 2")
    print()
    input("Presiona Enter cuando el servidor y el rival estén listos...")

    env = RoboCupEnv(team_name="PPOTeam", port=6000, unum=11)
    env = Monitor(env, LOG_DIR)

    model_path = f"{MODEL_DIR}/ppo_robocup_latest"
    if os.path.exists(model_path + ".zip"):
        print(f"[PPO] Cargando modelo existente: {model_path}")
        model = PPO.load(model_path, env=env)
        print("[PPO] Continuando entrenamiento desde donde quedó...")
    else:
        print("[PPO] Creando modelo nuevo...")
        model = PPO(
            policy        = "MlpPolicy",
            env           = env,
            learning_rate = 3e-4,
            n_steps       = 512,
            batch_size    = 64,
            n_epochs      = 10,
            gamma         = 0.95,
            gae_lambda    = 0.95,
            clip_range    = 0.2,
            ent_coef      = 0.01,
            vf_coef       = 0.5,
            max_grad_norm = 0.5,
            verbose       = 1,
        )

    # Guardar cada 5000 steps para no perder progreso
    checkpoint_cb = CheckpointCallback(
        save_freq   = 5_000,
        save_path   = MODEL_DIR,
        name_prefix = "ppo_robocup",
        verbose     = 1,
    )

    print("[PPO] Iniciando entrenamiento...")
    model.learn(
        total_timesteps     = total_steps,
        callback            = checkpoint_cb,
        reset_num_timesteps = False,
        progress_bar        = True,
    )

    # Guardar siempre al terminar
    model.save(f"{MODEL_DIR}/ppo_robocup_latest")
    print(f"[PPO] ✅ Modelo guardado en {MODEL_DIR}/ppo_robocup_latest.zip")

    try:
        pct = (env.env._possession_ticks / max(1, env.env._total_ticks)) * 100
        print(f"[PPO] Posesión durante entrenamiento: {pct:.1f}%")
    except Exception:
        pass

    env.close()
    print("[PPO] Entrenamiento completo.")


if __name__ == "__main__":
    steps = int(sys.argv[1]) if len(sys.argv) > 1 else 10_000
    train(steps)
