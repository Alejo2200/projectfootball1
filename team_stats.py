#!/usr/bin/env python3
import sys
import os
import re

team = sys.argv[1] if len(sys.argv) > 1 else "MiEquipo"

print(f"\n{'='*65}")
print(f"  ESTADISTICAS: {team}")
print(f"{'='*65}")
print(f"{'#':<6} {'Rol':<6} {'Posesion':>10} {'Kicks':>8} {'Pases':>8} {'Recup':>8}")
print(f"{'-'*65}")

roles = {1:"GK",2:"DEF",3:"DEF",4:"DEF",5:"DEF",
         6:"MID",7:"MID",8:"MID",9:"FWD",10:"FWD",11:"FWD"}

total_pct   = 0.0
total_kicks = 0
total_pass  = 0
total_recov = 0
count       = 0

for unum in range(1, 12):
    log_file = f"logs/{team}_{unum}.log"
    if not os.path.exists(log_file):
        continue
    with open(log_file) as f:
        content = f.read()

    pct   = 0.0
    kicks = 0
    passes= 0
    recov = 0

    for line in content.split("\n"):
        if "% Posesion" in line:
            m = re.search(r"([\d.]+)%", line)
            if m:
                pct = float(m.group(1))
        elif "Kicks" in line:
            m = re.search(r":\s*(\d+)", line)
            if m:
                kicks = int(m.group(1))
        elif "Pases" in line:
            m = re.search(r":\s*(\d+)", line)
            if m:
                passes = int(m.group(1))
        elif "Recuperaciones" in line:
            m = re.search(r":\s*(\d+)", line)
            if m:
                recov = int(m.group(1))

    rol = roles.get(unum, "?")
    print(f"  #{unum:<4} {rol:<6} {pct:>9.1f}%  {kicks:>8}  {passes:>8}  {recov:>8}")
    total_pct   += pct
    total_kicks += kicks
    total_pass  += passes
    total_recov += recov
    count       += 1

print(f"{'-'*65}")
avg = total_pct / count if count > 0 else 0
print(f"  TOTAL        {avg:>9.1f}%  {total_kicks:>8}  {total_pass:>8}  {total_recov:>8}")
print(f"{'='*65}\n")

