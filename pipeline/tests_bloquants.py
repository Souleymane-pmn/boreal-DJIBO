"""Livrable 2.4 · Tests automatisés bloquants, exécutés à chaque lancement.

Chaque test est une requête qui renvoie le NOMBRE D'ÉCARTS : 0 = succès.
Les tests s'exécutent à l'intérieur de la transaction de chargement : un seul échec
provoque un ROLLBACK, l'entrepôt reste dans son état précédent (cohérent).
"""
from __future__ import annotations

from pipeline.config import DATE_EXTRACTION as D

TESTS = [
    ("T01", "Unicité de la clé de substitution et d'une version courante par contrat",
     """SELECT (SELECT COUNT(*) - COUNT(DISTINCT contrat_sk) FROM core.dim_contrat)
             + (SELECT COUNT(*) FROM (SELECT contrat_id FROM core.dim_contrat WHERE is_current GROUP BY 1 HAVING COUNT(*)>1))"""),
    ("T02", "Unicité des clés client, sinistre et paiement",
     """SELECT (SELECT COUNT(*) - COUNT(DISTINCT client_id) FROM core.dim_client)
             + (SELECT COUNT(*) - COUNT(DISTINCT sinistre_id) FROM core.fact_sinistre)
             + (SELECT COUNT(*) - COUNT(DISTINCT paiement_id) FROM core.fact_reglement)"""),
    ("T03", "Unicité du grain des faits d'exposition (contrat × mois, contrat × année)",
     """SELECT (SELECT COUNT(*) FROM (SELECT contrat_id, mois FROM core.fact_exposition_mensuelle GROUP BY ALL HAVING COUNT(*)>1))
             + (SELECT COUNT(*) FROM (SELECT contrat_id, annee FROM core.fact_exposition_annuelle GROUP BY ALL HAVING COUNT(*)>1))"""),
    ("T04", "Intégrité référentielle des faits vers les dimensions",
     """SELECT (SELECT COUNT(*) FROM core.fact_sinistre f WHERE NOT EXISTS (SELECT 1 FROM core.dim_contrat d WHERE d.contrat_sk=f.contrat_sk))
             + (SELECT COUNT(*) FROM core.fact_sinistre f WHERE NOT EXISTS (SELECT 1 FROM core.dim_garantie g WHERE g.garantie=f.garantie))
             + (SELECT COUNT(*) FROM core.fact_reglement r WHERE NOT EXISTS (SELECT 1 FROM core.fact_sinistre s WHERE s.sinistre_id=r.sinistre_id))
             + (SELECT COUNT(*) FROM core.fact_exposition_mensuelle e WHERE NOT EXISTS (SELECT 1 FROM core.dim_client c WHERE c.client_id=e.client_id))
             + (SELECT COUNT(*) FROM core.fact_exposition_mensuelle e WHERE NOT EXISTS (SELECT 1 FROM core.dim_segment s WHERE s.segment_key=e.segment_key))
             + (SELECT COUNT(*) FROM core.dim_contrat k WHERE is_current AND NOT EXISTS (SELECT 1 FROM core.dim_client c WHERE c.client_id=k.client_id))
             + (SELECT COUNT(*) FROM core.fact_sinistre f WHERE NOT EXISTS (SELECT 1 FROM core.dim_date d WHERE d.date_key=f.date_survenance_key))"""),
    ("T05", "Réconciliation règlements : brut = cœur + quarantaine (lignes et montants au centime)",
     """SELECT (SELECT COUNT(*) FROM raw.reglements)
             - (SELECT COUNT(*) FROM core.fact_reglement)
             - (SELECT COUNT(DISTINCT _source_file||'#'||_row_num) FROM quarantine.reglements)
             + (SELECT CAST(ROUND(ABS(
                   (SELECT SUM(CAST(montant AS DECIMAL(18,2))) FROM raw.reglements)
                 - (SELECT SUM(CAST(montant AS DECIMAL(18,2))) FROM core.fact_reglement)
                 - COALESCE((SELECT SUM(CAST(b.montant AS DECIMAL(18,2))) FROM raw.reglements b
                    WHERE (b._source_file, b._row_num) IN (SELECT _source_file, _row_num FROM quarantine.reglements)), 0)
               ) * 100) AS BIGINT))"""),
    ("T06", "Réconciliation contrats, sinistres, clients et audits : brut = cœur + quarantaine",
     """SELECT ABS((SELECT COUNT(*) FROM raw.contrats) - (SELECT COUNT(*) FROM core.dim_contrat WHERE is_current)
                - (SELECT COUNT(DISTINCT cle) FROM quarantine.contrats))
             + ABS((SELECT COUNT(*) FROM raw.sinistres) - (SELECT COUNT(*) FROM core.fact_sinistre)
                - (SELECT COUNT(DISTINCT cle) FROM quarantine.sinistres))
             + ABS((SELECT COUNT(*) FROM raw.clients) - (SELECT COUNT(*) FROM core.dim_client)
                - (SELECT COUNT(DISTINCT cle) FROM quarantine.clients))
             + ABS((SELECT COUNT(*) FROM raw.audits) - (SELECT SUM(audite::INT) FROM core.fact_sinistre)
                - (SELECT COUNT(DISTINCT _source_file||'#'||_row_num) FROM quarantine.audits))"""),
    ("T07", "Exposition strictement positive et au plus égale à la durée du mois",
     """SELECT COUNT(*) FROM core.fact_exposition_mensuelle
        WHERE exposition_annees <= 0 OR jours_couverts > 31 OR prime_acquise < 0"""),
    ("T08", "Aucune date d'événement postérieure à l'extraction",
     f"""SELECT (SELECT COUNT(*) FROM core.fact_sinistre WHERE date_survenance > DATE '{D}' OR date_declaration > DATE '{D}')
             + (SELECT COUNT(*) FROM core.fact_reglement WHERE date_paiement > DATE '{D}')
             + (SELECT COUNT(*) FROM core.fact_exposition_mensuelle WHERE mois > DATE '{D}')"""),
    ("T09", "Cohérence cœur ↔ marts (primes, exposition, charge, au centime)",
     """SELECT CAST(ROUND(ABS((SELECT SUM(prime_acquise) FROM core.fact_exposition_mensuelle) - (SELECT SUM(primes_acquises) FROM mart.portefeuille_mensuel))*100) AS BIGINT)
             + CAST(ROUND(ABS((SELECT SUM(exposition_annees) FROM core.fact_exposition_mensuelle) - (SELECT SUM(exposition) FROM mart.portefeuille_mensuel))*100) AS BIGINT)
             + CAST(ROUND(ABS((SELECT SUM(charge) FROM core.fact_sinistre) - (SELECT SUM(charge) FROM mart.portefeuille_mensuel))*100) AS BIGINT)
             + CAST(ROUND(ABS((SELECT SUM(prime_acquise) FROM core.fact_exposition_annuelle) - (SELECT SUM(prime_acquise) FROM core.fact_exposition_mensuelle))*100) AS BIGINT)"""),
    ("T10", "Montant payé des sinistres = somme des règlements",
     """SELECT CAST(ROUND(ABS((SELECT SUM(montant_paye) FROM core.fact_sinistre) - (SELECT SUM(montant) FROM core.fact_reglement))*100) AS BIGINT)"""),
    ("T11", "Toute ligne en quarantaine a un motif et une référence source",
     """SELECT (SELECT COUNT(*) FROM quarantine.clients WHERE motif IS NULL OR _source_file IS NULL)
             + (SELECT COUNT(*) FROM quarantine.contrats WHERE motif IS NULL OR _source_file IS NULL)
             + (SELECT COUNT(*) FROM quarantine.sinistres WHERE motif IS NULL OR _source_file IS NULL)
             + (SELECT COUNT(*) FROM quarantine.reglements WHERE motif IS NULL OR _source_file IS NULL)
             + (SELECT COUNT(*) FROM quarantine.audits WHERE motif IS NULL OR _source_file IS NULL)"""),
    ("T12", "Ratio S/P du mart = ratio recalculé depuis le cœur (écart < 0,01 point)",
     """SELECT (ABS((SELECT ratio_sp FROM mart.kpi_segment WHERE axe='total' AND periode='2020-2025')
             - (SELECT SUM(charge) FROM core.fact_sinistre) / (SELECT SUM(prime_acquise) FROM core.fact_exposition_mensuelle)) > 0.0001)::INT"""),
    ("T13", "Une version de dim_contrat par contrat sans chevauchement de validité",
     """SELECT COUNT(*) FROM core.dim_contrat a JOIN core.dim_contrat b
        ON a.contrat_id=b.contrat_id AND a.contrat_sk<b.contrat_sk AND a.valid_from<=b.valid_to AND b.valid_from<=a.valid_to"""),
]


def run_tests(con, run_id: str) -> list[dict]:
    out = []
    for tid, label, sql in TESTS:
        try:
            n = con.execute(sql).fetchone()[0]
            n = int(n or 0)
            out.append(dict(run_id=run_id, test_id=tid, libelle=label, ecarts=n, statut="OK" if n == 0 else "ECHEC"))
        except Exception as e:  # noqa: BLE001
            out.append(dict(run_id=run_id, test_id=tid, libelle=label, ecarts=-1, statut=f"ERREUR: {e}"[:300]))
    return out
