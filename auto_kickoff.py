#!/usr/bin/env python3
"""
Se conecta como coach online y manda kick-off cada tiempo.
Ejecutar en paralelo con los equipos.
"""
import socket
import time
import re

COACH_PORT = 6002
HOST       = "127.0.0.1"

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)
    addr = (HOST, COACH_PORT)

    print("[Coach] Conectando...")
    sock.sendto(b"(init (version 16))", addr)
    time.sleep(1.0)

    # Intentar recibir confirmación
    try:
        data, _ = sock.recvfrom(4096)
        print(f"[Coach] Respuesta: {data.decode(errors='ignore')[:80]}")
    except socket.timeout:
        print("[Coach] Sin respuesta, continuando igual...")

    kicks_sent = 0
    last_mode  = ""

    while True:
        # Mandar kick_off cada vez que el modo lo requiera
        sock.sendto(b"(start)", addr)
        time.sleep(0.5)

        try:
            data, _ = sock.recvfrom(4096)
            msg = data.decode(errors="ignore")
            m   = re.search(r'play_mode\s+(\w+)', msg)
            if m:
                mode = m.group(1)
                if mode != last_mode:
                    print(f"[Coach] Modo: {mode}")
                    last_mode = mode
                if mode in ("time_over", "game_over"):
                    print("[Coach] Partido terminado.")
                    break
        except socket.timeout:
            pass

        time.sleep(2.0)

    sock.close()
    print("[Coach] Listo.")

if __name__ == "__main__":
    main()
