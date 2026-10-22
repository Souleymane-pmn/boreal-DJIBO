"""Tests de non-régression du pipeline (pytest).

Démontrent :
 1. l'idempotence : relancer le pipeline ne change rien (empreinte des tables du cœur identique) ;
 2. le rejeu d'un mois (--reload-month) ne crée aucun doublon ;
 3. un même mois livré deux fois (sous un autre nom) est neutralisé par la quarantaine ;
 4. l'arrivée d'un nouveau mois n'insère que ses lignes ;
 5. une règle bloquante en échec annule le chargement (ROLLBACK, entrepôt inchangé).
Chaque test travaille sur une copie isolée (zone d'atterrissage + entrepôt temporaires).
"""
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "archive" / "sources_boreal.zip"
CORE_TABLES = ["dim_client", "dim_contrat", "fact_exposition_mensuelle", "fact_sinistre", "fact_reglement"]


def run_pipeline(env, *args):
    r = subprocess.run([sys.executable, "-m", "pipeline.run", *args], cwd=ROOT, env=env,
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def fingerprint(db):
    con = duckdb.connect(str(db), read_only=True)
    fp = {}
    for t in CORE_TABLES:
        cols = [c[0] for c in con.execute(f"DESCRIBE core.{t}").fetchall() if c[0] not in ("charge_le", "valid_from", "valid_to")]
        fp[t] = con.execute(f"SELECT COUNT(*), SUM(HASH({', '.join(cols)})) FROM core.{t}").fetchone()
    fp["sp"] = con.execute("SELECT ROUND(ratio_sp, 8) FROM mart.kpi_segment WHERE axe='total' AND periode='2020-2025'").fetchone()
    con.close()
    return fp


@pytest.fixture()
def env(tmp_path):
    landing = tmp_path / "landing"
    with zipfile.ZipFile(ARCHIVE) as z:
        z.extractall(landing)
    e = os.environ.copy()
    e["BOREAL_LANDING"] = str(landing)
    e["BOREAL_DB"] = str(tmp_path / "test.duckdb")
    return e


def test_idempotence_relance(env):
    code, out = run_pipeline(env, "--rebuild")
    assert code == 0, out
    fp1 = fingerprint(env["BOREAL_DB"])
    code, out = run_pipeline(env)
    assert code == 0, out
    assert "(+0)" in out  # second passage : 0 ligne insérée dans fact_reglement
    assert fingerprint(env["BOREAL_DB"]) == fp1


def test_rejeu_d_un_mois_sans_doublon(env):
    assert run_pipeline(env, "--rebuild")[0] == 0
    fp1 = fingerprint(env["BOREAL_DB"])
    code, out = run_pipeline(env, "--reload-month", "2023-04")
    assert code == 0, out
    con = duckdb.connect(env["BOREAL_DB"], read_only=True)
    dups = con.execute("SELECT COUNT(*) - COUNT(DISTINCT paiement_id) FROM core.fact_reglement").fetchone()[0]
    raw_04 = con.execute("SELECT COUNT(*) FROM raw.reglements WHERE _source_file LIKE '%2023_04%'").fetchone()[0]
    con.close()
    assert dups == 0
    assert raw_04 == 62  # le fichier n'est présent qu'une fois dans le brut après rejeu
    assert fingerprint(env["BOREAL_DB"]) == fp1


def test_mois_livre_deux_fois(env):
    assert run_pipeline(env, "--rebuild")[0] == 0
    fp1 = fingerprint(env["BOREAL_DB"])
    reg = Path(env["BOREAL_LANDING"]) / "reglements"
    shutil.copy(reg / "reglements_2023_04.csv", reg / "reglements_2023_04_relivraison.csv")
    code, out = run_pipeline(env)
    assert code == 0, out
    assert fingerprint(env["BOREAL_DB"]) == fp1  # cœur inchangé
    con = duckdb.connect(env["BOREAL_DB"], read_only=True)
    q = con.execute("SELECT COUNT(*) FROM quarantine.reglements WHERE _source_file LIKE '%relivraison%'").fetchone()[0]
    con.close()
    assert q == 62  # toutes les lignes re-livrées sont en quarantaine (Q23)


def test_arrivee_nouveau_mois(env):
    reg = Path(env["BOREAL_LANDING"]) / "reglements"
    held = reg / "reglements_2025_06.csv"
    tmp = held.with_suffix(".hold")
    held.rename(tmp)
    assert run_pipeline(env, "--rebuild")[0] == 0
    con = duckdb.connect(env["BOREAL_DB"], read_only=True)
    n0 = con.execute("SELECT COUNT(*) FROM core.fact_reglement").fetchone()[0]
    con.close()
    tmp.rename(held)
    code, out = run_pipeline(env)
    assert code == 0, out
    con = duckdb.connect(env["BOREAL_DB"], read_only=True)
    n1 = con.execute("SELECT COUNT(*) FROM core.fact_reglement").fetchone()[0]
    loaded = con.execute("SELECT COUNT(*) FROM meta.ingestion_log WHERE mode <> 'SKIP' "
                         "AND run_id = (SELECT MAX(run_id) FROM meta.runs)").fetchone()[0]
    con.close()
    assert loaded == 1  # seul le nouveau fichier est chargé
    assert n1 > n0


def test_regle_bloquante_annule_le_chargement(env):
    assert run_pipeline(env, "--rebuild")[0] == 0
    fp1 = fingerprint(env["BOREAL_DB"])
    f = Path(env["BOREAL_LANDING"]) / "contrats" / "contrats.csv"
    lines = f.read_text(encoding="utf-8").splitlines()
    f.write_text("\n".join(lines + [lines[1]]) + "\n", encoding="utf-8")  # contrat_id dupliqué → Q07 BLOQUANT
    code, out = run_pipeline(env)
    assert code == 1
    assert "Q07" in out
    assert fingerprint(env["BOREAL_DB"]) == fp1  # ROLLBACK : l'entrepôt publié est intact
