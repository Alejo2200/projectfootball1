#!/usr/bin/env python3
import socket, time, threading, json, os, re, traceback, signal
from agent import Player
from agent.roles import RoleManager
from agent.logger import GameLogger
from perception.parse import parse_see

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 6000
NUM_PLAYERS = 11
TEAM_NAME   = "Alejo2200"
CONF_FILE   = "conf_file.conf"

_INIT_RE = re.compile(r"\(init\s+([lrLR])\s+(\d+)", re.IGNORECASE)


def _handle_sigterm(signum, frame):
    print("[signal] SIGTERM recibido, guardando tabla Q...")
    try:
        from agent.qlearning import get_qagent
        get_qagent(TEAM_NAME).save(verbose=True)
    except Exception as e:
        print(f"[signal] Error guardando: {e}")
    raise SystemExit(0)

signal.signal(signal.SIGTERM, _handle_sigterm)


def load_positions(conf_file):
    with open(conf_file) as f:
        data = json.load(f)
    positions = {}
    for i in range(1, NUM_PLAYERS + 1):
        e = data["data"][0].get(str(i))
        positions[i] = (float(e["x"]), float(e["y"])) if e else (0.0, 0.0)
    return positions


def safe_send(sock, msg, addr):
    try:
        if not msg.endswith("\n"):
            msg += "\n"
        sock.sendto(msg.encode(), addr)
    except Exception as e:
        print(f"[safe_send] {e}")


def _action_to_commands(action):
    cmds = []
    if "move" in action:
        mx, my = action["move"]
        return [f"(move {mx:.2f} {my:.2f})"]
    kick = action.get("kick")
    if kick is not None:
        p, a = kick
        cmds.append(f"(kick {max(0.0, min(100.0, p)):.1f} {a:.1f})")
    turn = action.get("turn", 0.0)
    dash = action.get("dash", 0.0)
    if abs(turn) > 0.5:
        cmds.append(f"(turn {turn:.1f})")
    if abs(dash) > 0.5:
        cmds.append(f"(dash {dash:.1f})")
    return cmds or ["(turn 0)"]


def player_thread(idx, positions, host, port, role_manager, team_name, conf_file):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", 0))
    sock.settimeout(0.8)
    server_addr = (host, port)

    side, unum, buf = None, None, ""
    for attempt in range(3):
        safe_send(sock, f"(init {team_name} (version 16))", server_addr)
        t0 = time.time()
        while time.time() - t0 < 4.0:
            try:
                data, server_addr = sock.recvfrom(8192)
                buf += data.decode(errors="ignore")
                m = _INIT_RE.search(buf)
                if m:
                    side = m.group(1).lower()
                    unum = int(m.group(2))
                    print(f"[{team_name} #{idx}] Conectado side={side} unum={unum}")
                    break
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[{team_name} #{idx}] Error init: {e}")
                break
        if unum is not None:
            break
        print(f"[{team_name} #{idx}] Reintentando... ({attempt+1}/3)")
        time.sleep(0.5)

    if unum is None:
        print(f"[{team_name} #{idx}] No pudo conectarse.")
        sock.close()
        return

    px, py = positions.get(unum) or positions.get(idx, (0.0, 0.0))
    if side == "r":
        px = -px
        py = -py

    for _ in range(8):
        safe_send(sock, f"(move {px:.2f} {py:.2f})", server_addr)
        time.sleep(0.07)

    if role_manager is None:
        role_manager = RoleManager(conf_file)

    player = Player(side, unum, role_manager, team_name=team_name)
    logger = GameLogger(team_name, unum)
    sock.settimeout(1.0)

    while True:
        try:
            data, server_addr = sock.recvfrom(8192)
            msg = data.decode(errors="ignore")

            if msg.startswith("(see"):
                try:
                    obs          = parse_see(msg)
                    all_players  = obs.get("teammates", [])
                    obs["teammates"] = [p for p in all_players if p["team"] == team_name]
                    obs["opponents"] = [p for p in all_players if p["team"] != team_name]
                    player.world_model.update_from_see(obs)
                    action = player.fsm.step(player.world_model)
                    logger.log_tick(player.world_model, action, state=player.fsm.state)
                    for cmd in _action_to_commands(action):
                        safe_send(sock, cmd, server_addr)
                        time.sleep(0.003)
                except Exception as e:
                    print(f"[{team_name} #{unum}] see error: {e}")
                    traceback.print_exc()

            elif msg.startswith("(hear"):
                try:
                    m = re.search(r'\(hear\s+\S+\s+referee\s+([a-zA-Z0-9_]+)\)', msg)
                    if m:
                        player.world_model.play_mode = m.group(1)
                        if m.group(1) in ("half_time", "time_over", "game_over"):
                            try:
                                from agent.qlearning import get_qagent
                                get_qagent(team_name).save(verbose=True)
                            except Exception:
                                pass
                except Exception:
                    pass

            elif msg.startswith("(sense_body"):
                try:
                    sm = re.search(r'\(stamina\s+([\d.]+)', msg)
                    am = re.search(r'\(head_angle\s+([-\d.]+)\)', msg)
                    player.world_model.update_from_sense_body(
                        stamina=float(sm.group(1)) if sm else None,
                        angle=float(am.group(1)) if am else None)
                except Exception:
                    pass

            elif "(error" in msg:
                print(f"[{team_name} #{unum}] error servidor: {msg.strip()}")

        except socket.timeout:
            continue
        except Exception as e:
            print(f"[{team_name} #{unum}] hilo terminado: {e}")
            break

    logger.close()
    sock.close()


def main():
    try:
        positions = load_positions(CONF_FILE)
        print("[main] Posiciones OK")
    except Exception as e:
        print(f"[main] Error posiciones: {e}")
        positions = {}
    try:
        role_manager = RoleManager(CONF_FILE)
        print("[main] Roles OK")
    except Exception as e:
        print(f"[main] Error roles: {e}")
        role_manager = None

    threads = []
    for i in range(1, NUM_PLAYERS + 1):
        t = threading.Thread(
            target=player_thread,
            args=(i, positions, SERVER_HOST, SERVER_PORT,
                  role_manager, TEAM_NAME, CONF_FILE),
            daemon=True
        )
        t.start()
        threads.append(t)
        time.sleep(0.15)

    print(f"[main] {len(threads)} jugadores para '{TEAM_NAME}'. Ctrl+C para salir.")
    try:
        while True:
            time.sleep(1.0)
    except (KeyboardInterrupt, SystemExit):
        print(f"[main] Guardando tabla Q de '{TEAM_NAME}'...")
        try:
            from agent.qlearning import get_qagent
            get_qagent(TEAM_NAME).save(verbose=True)
        except Exception:
            pass
        print("[main] Detenido.")


if __name__ == "__main__":
    main()
