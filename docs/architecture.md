# Architecture cible

```
 Sources (CRM, contrats, sinistres, règlements mensuels, antifraude)
   │  dépôt dans data/landing/  ──► pipeline.watch (cron 15 min) détecte un fichier nouveau / modifié
   ▼
 RAW        copie fidèle en texte + _source_file, _row_num, _file_hash, _loaded_at   (transaction par fichier)
   ▼                                                           meta.ingestion_log
 PREP       typage, normalisation, déduplication clients (client_mapping)
   ▼
 QUALITÉ    34 règles → meta.dq_results / meta.dq_anomalies ; lignes écartées → quarantine.*
   ▼
 CORE       étoile : dim_date, dim_client (SCD1), dim_contrat (SCD2), dim_garantie, dim_segment
            fact_exposition_mensuelle / annuelle, fact_sinistre, fact_reglement (incrémental)
   ▼
 MARTS      portefeuille_mensuel, kpi_segment, decomposition_sp, retention_*, valeur_client, delais, audits, exploitation_*
   ▼        13 tests bloquants (même transaction que PREP→MARTS : échec = ROLLBACK + alerte)
 DASHBOARD Streamlit (lecture seule des marts)    ·    DOSSIER (analysis/results.json)
```

| Composant | Choix | Critère mesurable |
|---|---|---|
| Moteur | DuckDB 1.5 (fichier unique) | 68 fichiers, ~42 000 lignes sources, 610 Ko compressés ; pipeline complet en ~5 s ; 0 € de licence ; aucun serveur à administrer |
| Langage | Python 3.12 + SQL | compétences standard d'une équipe data ; SQL lisible par un actuaire |
| Orchestration | Makefile + `pipeline.watch` planifié par cron | 1 fichier de 40 lignes, zéro infrastructure ; suffit pour 1 livraison/mois |
| Dashboard | Streamlit | gratuit, versionné avec le code, chargement < 2 s mesuré |
| Tests | tests SQL bloquants + pytest | 18 tests exécutés à chaque lancement / à chaque modification |

## Avec 100 fois plus de données (~4 M lignes, ~60 Mo/mois)

DuckDB tient encore sur un poste (il traite des centaines de millions de lignes), mais trois choses changeraient :
la reconstruction complète de prep/core à chaque exécution deviendrait coûteuse → passage en traitement
incrémental partitionné par mois (dbt `incremental`) ; besoin d'accès concurrents (plusieurs analystes, BI)
→ PostgreSQL ou un entrepôt cloud (BigQuery/Snowflake) avec stockage Parquet ; orchestration Airflow/Dagster
avec capteurs de fichiers, reprises et historique des exécutions ; dashboard Power BI/Superset avec cache.
