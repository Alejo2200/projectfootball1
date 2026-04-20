#!/usr/bin/env python3
import argparse, logging, os, sys
 
def parse_args():
    p = argparse.ArgumentParser(description="SoccerIA — RoboCup 2D")
    p.add_argument("--conf",    "-c", default="conf_file.conf")
    p.add_argument("--host",    "-H", default="127.0.0.1")
    p.add_argument("--port",    "-P", type=int, default=6000)
    p.add_argument("--players", "-n", type=int, default=11)
    p.add_argument("--team",    "-t", default="Alejo2200")
    p.add_argument("--logdir",  "-l", default="logs")
    return p.parse_args()
 
def main():
    args = parse_args()
    os.makedirs(args.logdir, exist_ok=True)
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(f"{args.logdir}/run_team.log"),
                  logging.StreamHandler(sys.stdout)])
    logging.info(f"Iniciando equipo: {args.team}")
    if not os.path.exists(args.conf):
        logging.error(f"Config no encontrada: {args.conf}"); sys.exit(2)
    try:
        import teams_full_connection as tfc
    except Exception as e:
        logging.exception(f"Error importando: {e}"); sys.exit(1)
    tfc.CONF_FILE   = args.conf
    tfc.SERVER_HOST = args.host
    tfc.SERVER_PORT = args.port
    tfc.NUM_PLAYERS = args.players
    tfc.TEAM_NAME   = args.team
    try:
        tfc.main()
    except KeyboardInterrupt:
        logging.info("Detenido.")
    except Exception as e:
        logging.exception(f"Error: {e}")
    finally:
        logging.info("Finalizado.")
 
if __name__ == "__main__":
    main()
