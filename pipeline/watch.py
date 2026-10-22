"""Déclencheur : lance le pipeline dès qu'un fichier nouveau ou modifié arrive dans la zone d'atterrissage.

    python -m pipeline.watch --once        # une vérification (à planifier par cron, ex. toutes les 15 min)
    python -m pipeline.watch --interval 60 # boucle de surveillance (service)

Exemple de planification (crontab) :
    */15 * * * * cd /opt/boreal && .venv/bin/python -m pipeline.watch --once >> logs/watch.log 2>&1
Livraison mensuelle des règlements → le fichier reglements_AAAA_MM.csv déclenche une exécution.
"""
import argparse
import glob
import time
from pathlib import Path

import duckdb

from pipeline.config import DB_PATH, LANDING, SOURCES
from pipeline.ingest import file_hash
from pipeline.run import run


def pending_files() -> list[str]:
    known = set()
    if DB_PATH.exists():
        con = duckdb.connect(str(DB_PATH), read_only=True)
        try:
            known = {(f, h) for f, h in con.execute(
                "SELECT fichier, file_hash FROM meta.ingestion_log WHERE statut LIKE 'OK%'").fetchall()}
        except duckdb.CatalogException:
            pass
        con.close()
    out = []
    for cfg in SOURCES.values():
        for p in sorted(glob.glob(str(LANDING / cfg["pattern"]))):
            rel = str(Path(p).relative_to(LANDING))
            if (rel, file_hash(Path(p))) not in known:
                out.append(rel)
    return out


def check_once() -> int:
    new = pending_files()
    if not new:
        print("Aucun fichier nouveau.")
        return 0
    print(f"{len(new)} fichier(s) nouveau(x) : {new[:5]}... → exécution du pipeline")
    return run()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=60)
    a = ap.parse_args()
    if a.once:
        raise SystemExit(check_once())
    while True:
        check_once()
        time.sleep(a.interval)
