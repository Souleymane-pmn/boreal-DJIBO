"""Configuration centrale du pipeline Boréal Assurances."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
LANDING = Path(os.getenv("BOREAL_LANDING", ROOT / "data" / "landing"))
ARCHIVE = ROOT / "data" / "archive" / "sources_boreal.zip"
DB_PATH = Path(os.getenv("BOREAL_DB", ROOT / "data" / "warehouse" / "boreal.duckdb"))
LOG_DIR = ROOT / "logs"
SQL_DIR = ROOT / "pipeline" / "sql"

# Date d'extraction de l'archive : borne d'observation de toutes les analyses
DATE_EXTRACTION = "2025-06-30"
# Seuil de sinistre grave (écrêtement) : au-delà, la charge est traitée à part
SEUIL_GRAVE = 150_000
# Seuil d'alerte du ratio S/P (dashboard) : 70 % = 100 % - ~30 % de frais de gestion
# et d'acquisition, ordre de grandeur usuel en IARD des particuliers.
SEUIL_ALERTE_SP = 0.70

# Description des sources : un descripteur par source, aucune intervention manuelle.
SOURCES = {
    "clients":    {"pattern": "crm/clients.csv",        "format": "csv",   "sep": ";", "encoding": "latin-1"},
    "contrats":   {"pattern": "contrats/contrats.csv",  "format": "csv",   "sep": ",", "encoding": "utf-8"},
    "sinistres":  {"pattern": "sinistres/sinistres.jsonl", "format": "jsonl"},
    "reglements": {"pattern": "reglements/reglements_*.csv", "format": "csv", "sep": None, "encoding": None},
    "audits":     {"pattern": "antifraude/audits.csv",  "format": "csv",   "sep": None, "encoding": None},
}

# Colonnes attendues dans la couche brute (toutes stockées en texte : copie fidèle)
RAW_COLUMNS = {
    "clients":    ["client_id", "date_naissance", "region", "csp", "consent_marketing", "email_hash"],
    "contrats":   ["contrat_id", "client_id", "produit", "date_effet", "date_resiliation", "formule",
                   "canal_distribution", "zone_risque", "franchise", "bonus_malus", "puissance_cv",
                   "surface_m2", "prime_annuelle"],
    "sinistres":  ["sinistre_id", "contrat_id", "date_survenance", "date_declaration", "garantie",
                   "statut", "reserve_initiale"],
    "reglements": ["paiement_id", "sinistre_id", "date_paiement", "montant"],
    "audits":     ["sinistre_id", "date_audit", "fraude_confirmee"],
}

# Synonymes d'en-têtes rencontrés (dérive de schéma entre fichiers d'une même source)
HEADER_ALIASES = {
    "montant_eur": "montant",
    "amount": "montant",
}
