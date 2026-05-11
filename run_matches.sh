#!/bin/bash
PARTIDAS=${1:-5}
TEAM1="MiEquipo"
TEAM2="RivalFC"

echo "=== Entrenamiento: $PARTIDAS partidas ==="

for i in $(seq 1 $PARTIDAS); do
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  PARTIDA $i de $PARTIDAS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    rcssserver server::auto_mode=true server::kick_off_wait=5 &
    SERVER_PID=$!
    sleep 3

    python3 run_team.py --team $TEAM1 &
    PID1=$!
    sleep 2

    python3 run_team.py --team $TEAM2 &
    PID2=$!
    sleep 3

    python3 auto_kickoff.py &
    PID_COACH=$!
    sleep 2

    echo "  Partido corriendo (~8 min)..."
    sleep 480

    echo "  Deteniendo y guardando tabla Q..."
    kill -SIGTERM $PID1 $PID2 2>/dev/null
    sleep 5
    kill -SIGKILL $PID1 $PID2 $PID_COACH $SERVER_PID 2>/dev/null
    wait $PID1 $PID2 $PID_COACH $SERVER_PID 2>/dev/null
    sleep 2

    echo "  Partida $i terminada."

    # Fusionar tablas y mostrar progreso
    python3 -c "
import sys
sys.path.insert(0, '.')
from agent.qlearning import merge_tables
q = merge_tables()
print(f'  [Q-Learning] Estados aprendidos: {len(q)}')
"
    sleep 1
done

echo ""
echo "======================================="
echo "  ENTRENAMIENTO COMPLETO"
echo "======================================="
python3 -c "
import sys, json, os
sys.path.insert(0, '.')
from agent.qlearning import merge_tables
q = merge_tables()
acciones = ['PASS','DRIBBLE_FWD','DRIBBLE_ESC','SHOOT']
print(f'Estados aprendidos: {len(q)}')
print()
for k,v in sorted(q.items()):
    mejor = acciones[v.index(max(v))]
    vals  = [round(x,2) for x in v]
    print(f'  Estado {k}')
    print(f'    Mejor accion : {mejor}')
    print(f'    PASS={vals[0]}  DRIB_FWD={vals[1]}  DRIB_ESC={vals[2]}  SHOOT={vals[3]}')
    print()
"
