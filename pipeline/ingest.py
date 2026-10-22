"""Livrable 1 · Ingestion des sources dans la couche brute (raw).

Principes :
- copie fidèle : toutes les valeurs sont stockées en texte, sans transformation ;
- chaque ligne porte son fichier d'origine, son numéro de ligne, l'empreinte du fichier
  et la date de chargement ;
- format, encodage et séparateur sont détectés automatiquement fichier par fichier ;
- les colonnes sont alignées par NOM d'en-tête (un fichier dont les colonnes sont
  permutées ou renommées est chargé correctement, l'en-tête d'origine est conservé) ;
- incrémental : un fichier déjà chargé avec la même empreinte est ignoré ; un fichier
  re-livré avec un contenu différent remplace ses lignes (DELETE + INSERT dans une
  même transaction) → idempotent ;
- toute ligne illisible part en quarantaine (quarantine.raw_rejets) avec son motif.
"""
from __future__ import annotations

import csv
import glob
import hashlib
import io
import json
import time
import uuid
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

from pipeline.config import HEADER_ALIASES, LANDING, RAW_COLUMNS, SOURCES

META_COLS = ["_source_file", "_row_num", "_file_hash", "_header_original", "_loaded_at", "_run_id"]


def init_meta(con: duckdb.DuckDBPyConnection) -> None:
    for s in ["raw", "prep", "core", "mart", "quarantine", "meta"]:
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {s}")
    for src, cols in RAW_COLUMNS.items():
        coldefs = ", ".join(f'"{c}" VARCHAR' for c in cols)
        con.execute(
            f"""CREATE TABLE IF NOT EXISTS raw.{src} ({coldefs},
                _source_file VARCHAR, _row_num INTEGER, _file_hash VARCHAR,
                _header_original VARCHAR, _loaded_at TIMESTAMP, _run_id VARCHAR)"""
        )
    con.execute(
        """CREATE TABLE IF NOT EXISTS meta.ingestion_log (
            run_id VARCHAR, source VARCHAR, fichier VARCHAR, file_hash VARCHAR,
            encodage VARCHAR, separateur VARCHAR, lignes_lues INTEGER, lignes_rejetees INTEGER,
            lignes_chargees INTEGER, duree_s DOUBLE, statut VARCHAR, mode VARCHAR,
            message VARCHAR, charge_le TIMESTAMP)"""
    )
    con.execute(
        """CREATE TABLE IF NOT EXISTS quarantine.raw_rejets (
            run_id VARCHAR, source VARCHAR, fichier VARCHAR, num_ligne INTEGER,
            contenu VARCHAR, motif VARCHAR, rejete_le TIMESTAMP)"""
    )
    con.execute(
        """CREATE TABLE IF NOT EXISTS meta.runs (
            run_id VARCHAR, debut TIMESTAMP, fin TIMESTAMP, statut VARCHAR, etape VARCHAR,
            message VARCHAR)"""
    )


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def detect_encoding(raw: bytes) -> str:
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "latin-1"


def detect_sep(text: str) -> str:
    first = text.splitlines()[0]
    try:
        return csv.Sniffer().sniff(first, delimiters=",;|\t").delimiter
    except csv.Error:
        return ","


def read_csv_file(path: Path, src: str, cfg: dict):
    """Lit un CSV en texte. Retourne (df_ok, rejets, encodage, separateur, entete)."""
    raw = path.read_bytes()
    enc = detect_encoding(raw)  # détection systématique, la config n'est qu'indicative
    text = raw.decode(enc).lstrip("\ufeff")
    sep = detect_sep(text)
    reader = csv.reader(io.StringIO(text), delimiter=sep)
    header = next(reader)
    header_orig = sep.join(header)
    norm = [HEADER_ALIASES.get(h.strip().lower(), h.strip().lower()) for h in header]
    expected = RAW_COLUMNS[src]
    missing = set(expected) - set(norm)
    if missing:
        raise ValueError(f"Colonnes manquantes dans {path.name}: {sorted(missing)}")
    rows, rejets = [], []
    for i, rec in enumerate(reader, start=2):  # ligne 1 = en-tête
        if not rec or all(v.strip() == "" for v in rec):
            continue
        if len(rec) != len(norm):
            rejets.append((i, sep.join(rec), f"NB_CHAMPS_{len(rec)}_ATTENDU_{len(norm)}"))
            continue
        d = dict(zip(norm, rec))
        rows.append([d[c] if d[c] != "" else None for c in expected] + [i])
    df = pd.DataFrame(rows, columns=expected + ["_row_num"], dtype="string")
    df["_row_num"] = df["_row_num"].astype(int) if len(df) else df["_row_num"]
    return df, rejets, enc, sep, header_orig


def read_jsonl_file(path: Path, src: str):
    expected = RAW_COLUMNS[src]
    raw = path.read_bytes()
    enc = detect_encoding(raw)
    rows, rejets = [], []
    for i, line in enumerate(raw.decode(enc).splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            rejets.append((i, line[:500], f"JSON_INVALIDE: {e.msg}"))
            continue
        obj = {HEADER_ALIASES.get(k.lower(), k.lower()): v for k, v in obj.items()}
        if set(expected) - set(obj):
            rejets.append((i, line[:500], f"CLES_MANQUANTES: {sorted(set(expected) - set(obj))}"))
            continue
        # copie fidèle : la valeur JSON est conservée sous sa forme texte
        rows.append([None if obj[c] is None else str(obj[c]) for c in expected] + [i])
    df = pd.DataFrame(rows, columns=expected + ["_row_num"], dtype="string")
    df["_row_num"] = df["_row_num"].astype(int) if len(df) else df["_row_num"]
    return df, rejets, enc, "jsonl", ",".join(expected)


def list_files(src: str, landing: Path) -> list[Path]:
    return sorted(Path(p) for p in glob.glob(str(landing / SOURCES[src]["pattern"])))


def ingest_file(con, src: str, path: Path, run_id: str, landing: Path, force: bool = False) -> dict:
    t0 = time.time()
    rel = str(path.relative_to(landing))
    h = file_hash(path)
    now = datetime.now()
    prev = con.execute(
        """SELECT file_hash FROM meta.ingestion_log
           WHERE fichier = ? AND statut IN ('OK','OK_AVEC_REJETS')
           ORDER BY charge_le DESC LIMIT 1""",
        [rel],
    ).fetchone()
    if prev and prev[0] == h and not force:
        entry = dict(run_id=run_id, source=src, fichier=rel, file_hash=h, encodage=None, separateur=None,
                     lignes_lues=0, lignes_rejetees=0, lignes_chargees=0, duree_s=round(time.time() - t0, 3),
                     statut="IGNORE_DEJA_CHARGE", mode="SKIP", message="empreinte identique", charge_le=now)
        con.execute("INSERT INTO meta.ingestion_log VALUES (" + ",".join("?" * 14) + ")", list(entry.values()))
        return entry
    mode = "REMPLACEMENT" if prev else "INITIAL"
    if force and prev:
        mode = "RECHARGEMENT_FORCE"
    try:
        if SOURCES[src]["format"] == "jsonl":
            df, rejets, enc, sep, header = read_jsonl_file(path, src)
        else:
            df, rejets, enc, sep, header = read_csv_file(path, src, SOURCES[src])
        df["_source_file"] = rel
        df["_file_hash"] = h
        df["_header_original"] = header
        df["_loaded_at"] = now
        df["_run_id"] = run_id
        cols = RAW_COLUMNS[src] + META_COLS
        df = df[cols]
        con.execute("BEGIN TRANSACTION")
        # idempotence : on supprime d'abord tout ce qui provient de ce fichier
        con.execute(f"DELETE FROM raw.{src} WHERE _source_file = ?", [rel])
        con.execute("DELETE FROM quarantine.raw_rejets WHERE fichier = ?", [rel])
        con.register("df_in", df)
        con.execute(f"INSERT INTO raw.{src} SELECT {', '.join(cols)} FROM df_in")
        con.unregister("df_in")
        for (n, contenu, motif) in rejets:
            con.execute("INSERT INTO quarantine.raw_rejets VALUES (?,?,?,?,?,?,?)",
                        [run_id, src, rel, n, contenu, motif, now])
        statut = "OK_AVEC_REJETS" if rejets else "OK"
        entry = dict(run_id=run_id, source=src, fichier=rel, file_hash=h, encodage=enc, separateur=sep,
                     lignes_lues=len(df) + len(rejets), lignes_rejetees=len(rejets), lignes_chargees=len(df),
                     duree_s=round(time.time() - t0, 3), statut=statut, mode=mode,
                     message=f"entete: {header}", charge_le=now)
        con.execute("INSERT INTO meta.ingestion_log VALUES (" + ",".join("?" * 14) + ")", list(entry.values()))
        con.execute("COMMIT")
        return entry
    except Exception as e:  # noqa: BLE001
        try:
            con.execute("ROLLBACK")
        except Exception:  # noqa: BLE001
            pass
        entry = dict(run_id=run_id, source=src, fichier=rel, file_hash=h, encodage=None, separateur=None,
                     lignes_lues=0, lignes_rejetees=0, lignes_chargees=0, duree_s=round(time.time() - t0, 3),
                     statut="ECHEC", mode=mode, message=str(e)[:500], charge_le=now)
        con.execute("INSERT INTO meta.ingestion_log VALUES (" + ",".join("?" * 14) + ")", list(entry.values()))
        raise


def ingest_all(con, run_id: str | None = None, landing: Path = LANDING, only_file: str | None = None,
               force: bool = False) -> list[dict]:
    run_id = run_id or uuid.uuid4().hex[:12]
    init_meta(con)
    out = []
    for src in SOURCES:
        for path in list_files(src, landing):
            rel = str(path.relative_to(landing))
            if only_file and rel != only_file:
                continue
            out.append(ingest_file(con, src, path, run_id, landing, force=force))
    return out
