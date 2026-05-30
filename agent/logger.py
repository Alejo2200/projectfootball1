import os
import time
import atexit


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
        self.pass_count       = 0
        self.recovery_count   = 0
        self.loss_count       = 0
        self._had_ball        = False
        self.start_time       = time.time()
        self.f.write(
            f"=== {team} | Jugador #{unum} | "
            f"{time.strftime('%Y-%m-%d %H:%M:%S')} ===\n"
        )
        atexit.register(self.close)

    def log_tick(self, wm, action, state=""):
        self.total_ticks += 1
        has_ball = getattr(wm, "ball_kickable", False)

        # Contar recuperaciones y pérdidas
        if has_ball and not self._had_ball:
            self.recovery_count += 1
        if not has_ball and self._had_ball:
            self.loss_count += 1
        self._had_ball = has_ball

        if has_ball:
            self.possession_ticks += 1
        if action.get("kick") is not None:
            self.kick_count += 1
            if state == "PASS":
                self.pass_count += 1
        if action.get("dash", 0.0) > 0:
            self.dash_count += 1

        self.f.write(
            f"T={self.total_ticks:<5} mode={wm.play_mode:<18} "
            f"ball={'SI' if has_ball else 'NO'} "
            f"stamina={wm.stamina:.0f} state={state} action={action}\n"
        )

        # Resumen parcial cada 500 ticks
        if self.total_ticks % 500 == 0:
            self._write_summary(partial=True)

    def _write_summary(self, partial=False):
        elapsed = time.time() - self.start_time
        pct = (100.0 * self.possession_ticks / self.total_ticks) \
              if self.total_ticks > 0 else 0.0
        tag = "PARCIAL" if partial else "FINAL"
        self.f.write(f"\n--- RESUMEN {tag} T={self.total_ticks} ---\n")
        self.f.write(f"  % Posesion     : {pct:.2f}%\n")
        self.f.write(f"  Ticks posesion : {self.possession_ticks}\n")
        self.f.write(f"  Total ticks    : {self.total_ticks}\n")
        self.f.write(f"  Kicks          : {self.kick_count}\n")
        self.f.write(f"  Pases          : {self.pass_count}\n")
        self.f.write(f"  Recuperaciones : {self.recovery_count}\n")
        self.f.write(f"  Perdidas       : {self.loss_count}\n")
        self.f.write(f"--- FIN RESUMEN {tag} ---\n\n")
        self.f.flush()

    def close(self):
        if self.f.closed:
            return
        elapsed = time.time() - self.start_time
        pct = (100.0 * self.possession_ticks / self.total_ticks) \
              if self.total_ticks > 0 else 0.0
        self.f.write("\n" + "=" * 70 + "\n")
        self.f.write(f"RESUMEN FINAL #{self.unum}\n")
        self.f.write(f"  Total ticks    : {self.total_ticks}\n")
        self.f.write(f"  Ticks posesion : {self.possession_ticks}\n")
        self.f.write(f"  % Posesion     : {pct:.2f}%\n")
        self.f.write(f"  Kicks          : {self.kick_count}\n")
        self.f.write(f"  Pases          : {self.pass_count}\n")
        self.f.write(f"  Recuperaciones : {self.recovery_count}\n")
        self.f.write(f"  Perdidas       : {self.loss_count}\n")
        self.f.write(f"  Dashes         : {self.dash_count}\n")
        self.f.write(f"  Duracion (s)   : {elapsed:.1f}\n")
        self.f.write("=" * 70 + "\n")
        self.f.flush()
        self.f.close()
        print(
            f"[Logger #{self.unum}] Posesion: {pct:.1f}% | "
            f"Kicks: {self.kick_count} | Pases: {self.pass_count} | "
            f"Recuperaciones: {self.recovery_count} | Perdidas: {self.loss_count}"
        )
