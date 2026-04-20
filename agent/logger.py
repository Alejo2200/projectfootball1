import os
import time
 
 
class GameLogger:
    def __init__(self, team, unum):
        os.makedirs("logs", exist_ok=True)
        self.f    = open(f"logs/{team}_{unum}.log", "w", buffering=1)
        self.team = team
        self.unum = unum
        self.possession_ticks = 0
        self.total_ticks      = 0
        self.kick_count       = 0
        self.dash_count       = 0
        self.start_time       = time.time()
        self.f.write(f"=== {team} | Jugador #{unum} | {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
 
    def log_tick(self, wm, action, state=""):
        self.total_ticks += 1
        has_ball = getattr(wm, "ball_kickable", False)
        if has_ball:
            self.possession_ticks += 1
        if action.get("kick") is not None:
            self.kick_count += 1
        if action.get("dash", 0.0) > 0:
            self.dash_count += 1
        self.f.write(
            f"T={self.total_ticks:<5} mode={wm.play_mode:<18} "
            f"ball={'SI' if has_ball else 'NO'} "
            f"stamina={wm.stamina:.0f} state={state} action={action}\n"
        )
 
    def close(self):
        elapsed = time.time() - self.start_time
        pct = (100.0 * self.possession_ticks / self.total_ticks) \
              if self.total_ticks > 0 else 0.0
        self.f.write("\n" + "=" * 70 + "\n")
        self.f.write(f"RESUMEN #{self.unum}\n")
        self.f.write(f"  Total ticks    : {self.total_ticks}\n")
        self.f.write(f"  Ticks posesion : {self.possession_ticks}\n")
        self.f.write(f"  % Posesion     : {pct:.2f}%\n")
        self.f.write(f"  Kicks          : {self.kick_count}\n")
        self.f.write(f"  Dashes         : {self.dash_count}\n")
        self.f.write(f"  Duracion (s)   : {elapsed:.1f}\n")
        self.f.write("=" * 70 + "\n")
        self.f.close()
        print(f"[Logger #{self.unum}] Posesion: {pct:.1f}% | Kicks: {self.kick_count}")
