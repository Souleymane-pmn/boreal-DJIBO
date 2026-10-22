"""Orchestrateur du pipeline Boréal : ingestion → préparation → qualité → cœur → marts → tests.

Usage :
    python -m pipeline.run                       # exécution standard (incrémentale)
    python -m pipeline.run --reload-month 2023-04  # rechargement forcé d'un mois de règlements
    python -m pipeline.run --rebuild             # repart d'un entrepôt vide

Garanties :
- l'ingestion de chaque fichier est une transaction (journal meta.ingestion_log) ;
- préparation, qualité, cœur, marts ET tests s'exécutent dans UNE transaction :
  un test bloquant en échec → ROLLBACK, l'entrepôt publié reste l'état précédent ;
- tout échec déclenche une alerte (logs/alertes.log + webhook si BOREAL_WEBHOOK défini).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.request
import uuid
from datetime import datetime

import duckdb

from pipeline.config import DATE_EXTRACTION, DB_PATH, LANDING, LOG_DIR, SEUIL_GRAVE, SQL_DIR
from pipeline.ingest import ingest_all, init_meta
from pipeline.quality import QualityBlockingError, run_quality
from pipeline.tests_bloquants import run_tests

LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler(LOG_DIR / "pipeline.log", encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("boreal")


class TestsFailedError(Exception):
    pass


def alert(run_id: str, etape: str, message: str) -> None:
    """Alerte en cas d'échec : fichier d'alertes + webhook optionnel (Slack/Teams/e-mail via relais)."""
    payload = {"run_id": run_id, "etape": etape, "message": message, "horodatage": datetime.now().isoformat()}
    with open(LOG_DIR / "alertes.log", "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    log.error("ALERTE pipeline : %s", payload)
    url = os.getenv("BOREAL_WEBHOOK")
    if url:
        try:
            req = urllib.request.Request(url, data=json.dumps({"text": f"[Boréal] Échec {etape} : {message}"}).encode(),
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:  # noqa: BLE001
            log.warning("Webhook injoignable : %s", e)


def run_sql_file(con, name: str) -> None:
    sql = (SQL_DIR / name).read_text(encoding="utf-8")
    sql = sql.replace("{DATE_EXTRACTION}", DATE_EXTRACTION).replace("{SEUIL_GRAVE}", str(SEUIL_GRAVE))
    con.execute(sql)


def build_exploitation_marts(con) -> None:
    """Marts d'exploitation (état de la chaîne), construits hors transaction après publication."""
    con.execute("""CREATE OR REPLACE TABLE mart.exploitation_chargements AS
        SELECT source, MAX(charge_le) FILTER (WHERE statut LIKE 'OK%') AS dernier_chargement_reussi,
               MAX(charge_le) AS derniere_tentative,
               COUNT(DISTINCT fichier) AS nb_fichiers,
               SUM(lignes_chargees) FILTER (WHERE statut LIKE 'OK%') AS lignes_chargees_cumul,
               SUM(lignes_rejetees) AS lignes_rejetees_cumul,
               SUM((statut = 'ECHEC')::INT) AS nb_echecs,
               MAX(fichier) FILTER (WHERE statut LIKE 'OK%') AS dernier_fichier
        FROM meta.ingestion_log GROUP BY 1""")
    con.execute("""CREATE OR REPLACE TABLE mart.exploitation_qualite AS
        SELECT r.rule_id, r.entite, r.dimension, r.libelle, r.gravite, r.traitement,
               d.volume, d.volume_total, d.taux, d.statut, d.controle_le
        FROM meta.dq_rules r JOIN meta.dq_results d USING (rule_id)
        WHERE d.run_id = (SELECT run_id FROM meta.dq_results ORDER BY controle_le DESC LIMIT 1)""")
    con.execute("""CREATE OR REPLACE TABLE mart.exploitation_tests AS
        SELECT * FROM meta.test_results
        WHERE run_id = (SELECT run_id FROM meta.test_results ORDER BY execute_le DESC LIMIT 1)""")
    con.execute(f"""CREATE OR REPLACE TABLE mart.exploitation_fraicheur AS
        SELECT 'reglements' AS source, MAX(date_paiement) AS derniere_date_metier FROM core.fact_reglement
        UNION ALL SELECT 'sinistres', MAX(date_declaration) FROM core.fact_sinistre
        UNION ALL SELECT 'contrats', GREATEST(MAX(date_effet), MAX(date_resiliation)) FROM core.dim_contrat
        UNION ALL SELECT 'audits', MAX(date_audit) FROM core.fact_sinistre
        UNION ALL SELECT 'extraction', DATE '{DATE_EXTRACTION}'""")
    con.execute("""CREATE OR REPLACE TABLE mart.exploitation_runs AS
        SELECT * FROM meta.runs ORDER BY debut DESC LIMIT 50""")


def run(reload_month: str | None = None, rebuild: bool = False) -> int:
    run_id = datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:6]
    if rebuild and DB_PATH.exists():
        DB_PATH.unlink()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    init_meta(con)
    con.execute("""CREATE TABLE IF NOT EXISTS meta.test_results (run_id VARCHAR, test_id VARCHAR, libelle VARCHAR,
                   ecarts BIGINT, statut VARCHAR, execute_le TIMESTAMP)""")
    t0 = time.time()
    con.execute("INSERT INTO meta.runs VALUES (?, now(), NULL, 'EN_COURS', 'debut', NULL)", [run_id])
    etape = "ingestion"
    try:
        log.info("[%s] Ingestion depuis %s", run_id, LANDING)
        if reload_month:
            f = f"reglements/reglements_{reload_month.replace('-', '_')}.csv"
            log.info("Rechargement forcé de %s", f)
            entries = ingest_all(con, run_id, only_file=f, force=True)
            if not entries:
                raise FileNotFoundError(f"Fichier introuvable dans la zone d'atterrissage : {f}")
        entries = ingest_all(con, run_id)
        nouveaux = [e for e in entries if e["mode"] != "SKIP"]
        log.info("Ingestion : %d fichiers examinés, %d chargés, %d ignorés (déjà chargés)",
                 len(entries), len(nouveaux), len(entries) - len(nouveaux))

        con.execute("BEGIN TRANSACTION")
        etape = "preparation"; run_sql_file(con, "01_prep.sql")
        etape = "qualite"; dq = run_quality(con, run_id)
        log.info("Qualité : %d règles, %d avec anomalies", len(dq), sum(1 for r in dq if r["volume"]))
        etape = "coeur"
        n_before = con.execute("SELECT COUNT(*) FROM core.fact_reglement").fetchone()[0] \
            if con.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='core' AND table_name='fact_reglement'").fetchone()[0] else 0
        run_sql_file(con, "03_core.sql")
        n_after = con.execute("SELECT COUNT(*) FROM core.fact_reglement").fetchone()[0]
        log.info("fact_reglement : %d → %d lignes (%+d)", n_before, n_after, n_after - n_before)
        etape = "marts"; run_sql_file(con, "04_marts.sql")
        etape = "tests"; results = run_tests(con, run_id)
        failed = [r for r in results if r["statut"] != "OK"]
        if failed:
            raise TestsFailedError("Tests bloquants en échec : " + ", ".join(f"{r['test_id']} ({r['ecarts']})" for r in failed))
        con.execute("COMMIT")
        for r in results:
            con.execute("INSERT INTO meta.test_results VALUES (?,?,?,?,?, now())", list(r.values()))
        log.info("Tests : %d/%d OK", len(results), len(results))
        build_exploitation_marts(con)
        con.execute("UPDATE meta.runs SET fin = now(), statut = 'SUCCES', etape = 'fin', message = ? WHERE run_id = ?",
                    [f"{time.time() - t0:.1f}s", run_id])
        build_exploitation_marts(con)
        log.info("[%s] Pipeline terminé avec succès en %.1fs", run_id, time.time() - t0)
        return 0
    except Exception as e:  # noqa: BLE001
        try:
            con.execute("ROLLBACK")
        except Exception:  # noqa: BLE001
            pass
        if isinstance(e, TestsFailedError):
            for r in results:  # noqa: F821  (défini à l'étape tests)
                con.execute("INSERT INTO meta.test_results VALUES (?,?,?,?,?, now())", list(r.values()))
        con.execute("UPDATE meta.runs SET fin = now(), statut = 'ECHEC', etape = ?, message = ? WHERE run_id = ?",
                    [etape, str(e)[:500], run_id])
        alert(run_id, etape, str(e))
        return 1
    finally:
        con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reload-month", help="AAAA-MM : recharge le fichier de règlements de ce mois")
    ap.add_argument("--rebuild", action="store_true", help="supprime l'entrepôt et recharge tout")
    a = ap.parse_args()
    sys.exit(run(a.reload_month, a.rebuild))
