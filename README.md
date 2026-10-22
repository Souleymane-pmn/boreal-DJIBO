# boreal-DJIBO · Entrepôt et analyse du portefeuille Boréal Assurances

Chaîne de données reproductible (DuckDB + Python) : ingestion des 68 fichiers sources, contrôles qualité
avec quarantaine, schéma en étoile, marts, tests bloquants, analyses et dashboard Streamlit.

Projet réalisé seul par Souleymane DJIBO, M2 Data Analyst, PMN.

## Exécution en 5 commandes (machine propre, Python 3.10+)

```bash
python3 -m venv .venv && source .venv/bin/activate   # 1. environnement isolé
pip install -r requirements.txt                      # 2. dépendances
make data                                            # 3. dépose sources_boreal.zip dans data/landing/
make all                                             # 4. pipeline + 18 tests + analyses + dossier PDF
make dashboard                                       # 5. dashboard sur http://localhost:8501
```

Sans `make` (Windows) : `python -m pipeline.run --rebuild`, `python -m pytest tests`, `python -m analysis.analyses`,
`python -m rapport.build_report`, `python -m streamlit run dashboard/app.py`.

## Commandes d'exploitation

| Besoin | Commande |
|---|---|
| Exécution incrémentale (nouveaux fichiers seulement) | `make run` |
| Rejouer un mois de règlements | `make reload MONTH=2023-04` |
| Vérifier qu'un fichier est arrivé et lancer le pipeline | `make watch` |
| Planification mensuelle (cron, toutes les 15 min) | `*/15 * * * * cd /opt/boreal && .venv/bin/python -m pipeline.watch --once` |
| Alertes d'échec | `logs/alertes.log` + webhook si la variable `BOREAL_WEBHOOK` est définie |

## Organisation du dépôt

```
data/archive/        archive source (sources_boreal.zip)
data/landing/        zone d'atterrissage (fichiers livrés, surveillée par pipeline.watch)
data/warehouse/      entrepôt DuckDB (boreal.duckdb)
pipeline/            ingest.py · sql/01_prep · quality.py (34 règles) · sql/03_core · sql/04_marts
                     tests_bloquants.py (13 tests) · run.py (orchestrateur) · watch.py (déclencheur)
tests/               pytest : idempotence, rejeu, double livraison, nouveau mois, rollback
analysis/            analyses.py → output/results.json (chaque chiffre + sa requête), figures, CSV
dashboard/app.py     Streamlit, 3 pages + définitions, lit uniquement mart.*
docs/                catalogue_donnees.md, architecture.md, lignage_sp.md, rgpd.md
rapport/             build_report.py → dossier PDF + note exécutive
```

## Garanties

- **Idempotence** : un fichier déjà chargé (même empreinte SHA-256) est ignoré ; un rejeu remplace les lignes du fichier
  (DELETE + INSERT dans une transaction) ; `fact_reglement` n'insère que les `paiement_id` absents.
- **Tests bloquants** : préparation, qualité, cœur, marts et tests sont exécutés dans une seule transaction ;
  un échec → ROLLBACK, l'entrepôt publié reste intact, une alerte est émise.
- **Traçabilité** : aucune ligne supprimée ; toute ligne écartée est en `quarantine.*` avec règle, motif et ligne brute.
