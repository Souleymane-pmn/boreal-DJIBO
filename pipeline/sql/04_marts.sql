-- =====================================================================
-- COUCHE MARTS : tables d'usage, seules sources du dashboard et du dossier
-- Paramètres : {DATE_EXTRACTION}, {SEUIL_GRAVE}
-- =====================================================================

-- ---------- Portefeuille mensuel (grain : mois × produit × région × canal × zone × formule × âge) ----------
CREATE OR REPLACE TABLE mart.portefeuille_mensuel AS
WITH e AS (
  SELECT f.mois, s.produit, c.region, s.canal, s.zone_risque, s.formule, s.tranche_age,
         SUM(f.exposition_annees) AS exposition, SUM(f.prime_acquise) AS primes_acquises,
         SUM(f.actif_fin_mois) AS contrats_actifs_fin_mois, SUM(f.resiliation) AS resiliations,
         SUM(f.nouvelle_souscription) AS souscriptions
  FROM core.fact_exposition_mensuelle f
  JOIN core.dim_segment s USING (segment_key) JOIN core.dim_client c USING (client_id)
  GROUP BY ALL
), x AS (
  SELECT f.mois_survenance AS mois, s.produit, c.region, s.canal, s.zone_risque, s.formule, s.tranche_age,
         COUNT(*) AS nb_sinistres_declares,
         SUM(f.avec_suite::INT) AS nb_sinistres,
         SUM((f.statut = 'SANS_SUITE')::INT) AS nb_sans_suite,
         SUM((f.statut = 'REJETE')::INT) AS nb_rejetes,
         SUM((f.statut = 'OUVERT')::INT) AS nb_ouverts,
         SUM(f.charge) AS charge, SUM(f.charge_ecretee) AS charge_ecretee,
         SUM(f.montant_paye) AS montant_paye, SUM(f.reserve_restante) AS reserves,
         SUM((f.charge > {SEUIL_GRAVE})::INT) AS nb_graves
  FROM core.fact_sinistre f
  JOIN core.dim_segment s USING (segment_key) JOIN core.dim_client c USING (client_id)
  GROUP BY ALL
)
SELECT COALESCE(e.mois, x.mois) AS mois, YEAR(COALESCE(e.mois, x.mois)) AS annee,
       COALESCE(e.produit, x.produit) AS produit, COALESCE(e.region, x.region) AS region,
       COALESCE(e.canal, x.canal) AS canal, COALESCE(e.zone_risque, x.zone_risque) AS zone_risque,
       COALESCE(e.formule, x.formule) AS formule, COALESCE(e.tranche_age, x.tranche_age) AS tranche_age,
       COALESCE(exposition, 0) AS exposition, COALESCE(primes_acquises, 0) AS primes_acquises,
       COALESCE(contrats_actifs_fin_mois, 0) AS contrats_actifs_fin_mois,
       COALESCE(resiliations, 0) AS resiliations, COALESCE(souscriptions, 0) AS souscriptions,
       COALESCE(nb_sinistres_declares, 0) AS nb_sinistres_declares, COALESCE(nb_sinistres, 0) AS nb_sinistres,
       COALESCE(nb_sans_suite, 0) AS nb_sans_suite, COALESCE(nb_rejetes, 0) AS nb_rejetes,
       COALESCE(nb_ouverts, 0) AS nb_ouverts, COALESCE(charge, 0) AS charge,
       COALESCE(charge_ecretee, 0) AS charge_ecretee, COALESCE(montant_paye, 0) AS montant_paye,
       COALESCE(reserves, 0) AS reserves, COALESCE(nb_graves, 0) AS nb_graves
FROM e FULL OUTER JOIN x
  ON e.mois = x.mois AND e.produit = x.produit AND e.region = x.region AND e.canal = x.canal
 AND e.zone_risque = x.zone_risque AND e.formule = x.formule AND e.tranche_age = x.tranche_age;

-- ---------- Indicateurs techniques par année et par axe ----------
CREATE OR REPLACE TABLE mart.kpi_segment AS
WITH base AS (
  SELECT CAST(annee AS VARCHAR) AS periode, * FROM mart.portefeuille_mensuel
  UNION ALL SELECT '2020-2025' AS periode, * FROM mart.portefeuille_mensuel
), g AS (
  SELECT periode,
         CASE WHEN GROUPING(produit)=0 THEN 'produit' WHEN GROUPING(zone_risque)=0 THEN 'zone_risque'
              WHEN GROUPING(formule)=0 THEN 'formule' WHEN GROUPING(canal)=0 THEN 'canal'
              WHEN GROUPING(tranche_age)=0 THEN 'tranche_age' WHEN GROUPING(region)=0 THEN 'region'
              ELSE 'total' END AS axe,
         COALESCE(produit, CAST(zone_risque AS VARCHAR), formule, canal, tranche_age, region, 'Ensemble') AS modalite,
         SUM(exposition) exposition, SUM(primes_acquises) primes_acquises, SUM(nb_sinistres) nb_sinistres,
         SUM(nb_sinistres_declares) nb_sinistres_declares, SUM(nb_sans_suite) nb_sans_suite, SUM(nb_rejetes) nb_rejetes,
         SUM(charge) charge, SUM(charge_ecretee) charge_ecretee, SUM(montant_paye) montant_paye,
         SUM(reserves) reserves, SUM(resiliations) resiliations, SUM(nb_graves) nb_graves
  FROM base
  GROUP BY GROUPING SETS ((periode), (periode, produit), (periode, zone_risque), (periode, formule),
                          (periode, canal), (periode, tranche_age), (periode, region))
)
SELECT *,
       nb_sinistres / NULLIF(exposition, 0)        AS frequence,
       charge / NULLIF(nb_sinistres, 0)            AS cout_moyen,
       charge_ecretee / NULLIF(nb_sinistres, 0)    AS cout_moyen_ecrete,
       primes_acquises / NULLIF(exposition, 0)     AS prime_moyenne,
       charge / NULLIF(primes_acquises, 0)         AS ratio_sp,
       charge_ecretee / NULLIF(primes_acquises, 0) AS ratio_sp_ecrete,
       resiliations / NULLIF(exposition, 0)        AS taux_resiliation
FROM g;

-- ---------- Décomposition de l'évolution annuelle du S/P ----------
-- S/P = fréquence × coût moyen / prime moyenne (volume = exposition, s'annule dans le ratio).
-- Répartition de ΔS/P entre facteurs par la méthode logarithmique (LMDI) :
--   effet_x = ΔS/P × ln(x_t/x_t-1) / ln(SP_t/SP_t-1), la prime moyenne jouant en négatif.
-- La charge, elle, se décompose en volume × fréquence × coût moyen.
CREATE OR REPLACE TABLE mart.decomposition_sp AS
WITH k AS (
  SELECT CAST(periode AS INTEGER) AS annee, 'brut' AS mesure, exposition, primes_acquises, nb_sinistres,
         charge AS charge, frequence, cout_moyen, prime_moyenne, ratio_sp AS sp
  FROM mart.kpi_segment WHERE axe = 'total' AND periode <> '2020-2025'
  UNION ALL
  SELECT CAST(periode AS INTEGER), 'ecrete', exposition, primes_acquises, nb_sinistres,
         charge_ecretee, frequence, cout_moyen_ecrete, prime_moyenne, ratio_sp_ecrete
  FROM mart.kpi_segment WHERE axe = 'total' AND periode <> '2020-2025'
), l AS (
  SELECT *, LAG(sp) OVER w sp_prec, LAG(frequence) OVER w f_prec, LAG(cout_moyen) OVER w c_prec,
         LAG(prime_moyenne) OVER w p_prec, LAG(exposition) OVER w e_prec, LAG(charge) OVER w ch_prec
  FROM k WINDOW w AS (PARTITION BY mesure ORDER BY annee)
)
SELECT annee, mesure, exposition, primes_acquises, nb_sinistres, charge, frequence, cout_moyen, prime_moyenne, sp,
       sp - sp_prec AS delta_sp,
       (sp - sp_prec) * LN(frequence / f_prec) / NULLIF(LN(sp / sp_prec), 0)   AS effet_frequence,
       (sp - sp_prec) * LN(cout_moyen / c_prec) / NULLIF(LN(sp / sp_prec), 0)  AS effet_cout_moyen,
       -(sp - sp_prec) * LN(prime_moyenne / p_prec) / NULLIF(LN(sp / sp_prec), 0) AS effet_prime_moyenne,
       0.0 AS effet_volume_sur_sp,
       charge - ch_prec AS delta_charge,
       (charge - ch_prec) * LN(exposition / e_prec) / NULLIF(LN(charge / ch_prec), 0) AS effet_volume_sur_charge,
       (charge - ch_prec) * LN(frequence / f_prec) / NULLIF(LN(charge / ch_prec), 0)  AS effet_frequence_sur_charge,
       (charge - ch_prec) * LN(cout_moyen / c_prec) / NULLIF(LN(charge / ch_prec), 0) AS effet_cout_sur_charge,
       CASE WHEN annee = 2025 THEN 'incomplète (6 mois, sinistres récents non développés)'
            WHEN annee = 2024 THEN 'à consolider (réserves encore ouvertes)'
            WHEN annee = 2020 THEN 'montée en charge du portefeuille'
            ELSE 'complète' END AS statut_annee
FROM l;

-- ---------- Contribution des segments à la variation du S/P ----------
-- ΔS/P total = Σ_segments (charge_s,t / primes_t − charge_s,t-1 / primes_t-1)  (additif exact)
CREATE OR REPLACE TABLE mart.contribution_segments AS
WITH t AS (SELECT periode, primes_acquises AS primes_tot FROM mart.kpi_segment WHERE axe = 'total'),
s AS (
  SELECT CAST(k.periode AS INTEGER) AS annee, k.axe, k.modalite, k.charge, k.charge_ecretee, k.primes_acquises,
         k.ratio_sp, k.charge / t.primes_tot AS part_sp, k.charge_ecretee / t.primes_tot AS part_sp_ecrete
  FROM mart.kpi_segment k JOIN t USING (periode)
  WHERE k.axe NOT IN ('total') AND k.periode <> '2020-2025'
)
SELECT *, part_sp - LAG(part_sp) OVER w AS contribution_delta_sp,
       part_sp_ecrete - LAG(part_sp_ecrete) OVER w AS contribution_delta_sp_ecrete
FROM s WINDOW w AS (PARTITION BY axe, modalite ORDER BY annee);

-- ---------- Rétention par cohorte annuelle de souscription ----------
-- Cohorte = année de la 1re souscription du client (par produit, et tous produits).
-- Retenu à l'anniversaire k : au moins un contrat du produit actif à cette date.
-- Cellule « complète » seulement si l'anniversaire k de TOUS les membres est ≤ 30/06/2025.
CREATE OR REPLACE TABLE mart.retention_cohorte AS
WITH k AS (SELECT client_id, produit, date_effet, date_resiliation FROM core.dim_contrat WHERE is_current),
k2 AS (SELECT client_id, produit, date_effet, date_resiliation FROM k
       UNION ALL SELECT client_id, 'TOUS', date_effet, date_resiliation FROM k),
o AS (SELECT client_id, produit, MIN(date_effet) AS origine FROM k2 GROUP BY 1, 2),
grid AS (SELECT o.*, YEAR(origine) AS cohorte, h.k, (origine + h.k * INTERVAL 1 YEAR)::DATE AS anniv
         FROM o, RANGE(0, 6) h(k)),
st AS (
  SELECT g.produit, g.cohorte, g.k, g.client_id, g.anniv,
         EXISTS (SELECT 1 FROM k2 WHERE k2.client_id = g.client_id AND k2.produit = g.produit
                 AND k2.date_effet <= g.anniv AND (k2.date_resiliation IS NULL OR k2.date_resiliation > g.anniv)) AS retenu
  FROM grid g WHERE g.anniv <= DATE '{DATE_EXTRACTION}'
)
SELECT g.produit, g.cohorte, g.k AS annee_anciennete,
       (SELECT COUNT(*) FROM o WHERE o.produit = g.produit AND YEAR(o.origine) = g.cohorte) AS taille_cohorte,
       COUNT(*) AS clients_observables, SUM(retenu::INT) AS clients_retenus,
       SUM(retenu::INT) / COUNT(*) AS taux_retention,
       MAKE_DATE(g.cohorte, 12, 31) + g.k * INTERVAL 1 YEAR <= DATE '{DATE_EXTRACTION}' AS cellule_complete
FROM st g GROUP BY ALL;

-- ---------- Multi-détention et rétention ----------
-- Multi-détenteur « à l'origine » : auto ET habitation actifs dans les 90 jours suivant la
-- première souscription (évite le biais du survivant d'une définition « à tout moment »).
CREATE OR REPLACE TABLE mart.client_detention AS
WITH k AS (SELECT client_id, produit, date_effet, date_resiliation FROM core.dim_contrat WHERE is_current),
o AS (SELECT client_id, MIN(date_effet) AS origine, COUNT(DISTINCT produit) AS nb_produits_total FROM k GROUP BY 1)
SELECT o.client_id, o.origine, YEAR(o.origine) AS cohorte, o.nb_produits_total,
       (SELECT COUNT(DISTINCT produit) FROM k WHERE k.client_id = o.client_id
          AND k.date_effet <= o.origine + 90 AND (k.date_resiliation IS NULL OR k.date_resiliation > o.origine)) AS nb_produits_origine,
       CASE WHEN (SELECT COUNT(DISTINCT produit) FROM k WHERE k.client_id = o.client_id
          AND k.date_effet <= o.origine + 90 AND (k.date_resiliation IS NULL OR k.date_resiliation > o.origine)) = 2
            THEN 'Multi-détenteur' ELSE 'Mono-détenteur' END AS detention_origine,
       CASE WHEN o.nb_produits_total = 2 THEN 'Auto + habitation' ELSE 'Un seul produit' END AS detention_tout_temps
FROM o;

CREATE OR REPLACE TABLE mart.retention_detention AS
WITH k AS (SELECT client_id, date_effet, date_resiliation FROM core.dim_contrat WHERE is_current),
g AS (SELECT d.*, h.k, (d.origine + h.k * INTERVAL 1 YEAR)::DATE AS anniv FROM mart.client_detention d, RANGE(1, 5) h(k)),
st AS (SELECT g.*, EXISTS (SELECT 1 FROM k WHERE k.client_id = g.client_id AND k.date_effet <= g.anniv
                     AND (k.date_resiliation IS NULL OR k.date_resiliation > g.anniv)) AS retenu
       FROM g WHERE g.anniv <= DATE '{DATE_EXTRACTION}')
SELECT detention_origine, k AS annee_anciennete, COUNT(*) AS clients_observables,
       SUM(retenu::INT) AS clients_retenus, SUM(retenu::INT) / COUNT(*) AS taux_retention
FROM st GROUP BY ALL;

-- ---------- Valeur observée par client : primes acquises − sinistres payés ----------
CREATE OR REPLACE TABLE mart.valeur_client AS
WITH p AS (SELECT client_id, SUM(prime_acquise) AS primes_acquises, SUM(exposition_annees) AS exposition
           FROM core.fact_exposition_mensuelle GROUP BY 1),
r AS (SELECT k.client_id, SUM(f.montant) AS sinistres_payes, COUNT(DISTINCT f.sinistre_id) AS nb_sinistres_payes
      FROM core.fact_reglement f JOIN core.dim_contrat k ON k.contrat_id = f.contrat_id AND k.is_current GROUP BY 1),
k AS (SELECT client_id, COUNT(*) AS nb_contrats, STRING_AGG(DISTINCT produit, '+' ORDER BY produit) AS produits,
             MODE(canal) AS canal_principal, MAX(zone_risque) AS zone_max, MODE(formule) AS formule_principale
      FROM core.dim_contrat WHERE is_current GROUP BY 1),
v AS (
  SELECT c.client_id, c.region, c.csp,
         CASE WHEN c.date_naissance IS NULL THEN 'Inconnu'
              WHEN DATE_DIFF('year', c.date_naissance, DATE '{DATE_EXTRACTION}') <= 25 THEN '18-25'
              WHEN DATE_DIFF('year', c.date_naissance, DATE '{DATE_EXTRACTION}') <= 35 THEN '26-35'
              WHEN DATE_DIFF('year', c.date_naissance, DATE '{DATE_EXTRACTION}') <= 45 THEN '36-45'
              WHEN DATE_DIFF('year', c.date_naissance, DATE '{DATE_EXTRACTION}') <= 55 THEN '46-55'
              WHEN DATE_DIFF('year', c.date_naissance, DATE '{DATE_EXTRACTION}') <= 65 THEN '56-65'
              ELSE '66+' END AS tranche_age_actuelle,
         k.nb_contrats, k.produits, k.canal_principal, k.zone_max, k.formule_principale,
         COALESCE(p.exposition, 0) AS exposition, COALESCE(p.primes_acquises, 0) AS primes_acquises,
         COALESCE(r.sinistres_payes, 0) AS sinistres_payes, COALESCE(r.nb_sinistres_payes, 0) AS nb_sinistres_payes,
         COALESCE(p.primes_acquises, 0) - COALESCE(r.sinistres_payes, 0) AS valeur_observee
  FROM core.dim_client c JOIN k USING (client_id) LEFT JOIN p USING (client_id) LEFT JOIN r USING (client_id)
)
SELECT *, ROW_NUMBER() OVER (ORDER BY valeur_observee DESC) AS rang,
       ROW_NUMBER() OVER (ORDER BY valeur_observee DESC) / COUNT(*) OVER () AS part_cumulee_clients,
       SUM(valeur_observee) OVER (ORDER BY valeur_observee DESC ROWS UNBOUNDED PRECEDING)
         / SUM(valeur_observee) OVER () AS part_cumulee_valeur,
       NTILE(10) OVER (ORDER BY valeur_observee DESC) AS decile
FROM v;

-- ---------- Délais de gestion des sinistres ----------
CREATE OR REPLACE TABLE mart.delais_sinistres AS
WITH d AS (
  SELECT f.garantie, s.produit, 'Déclaration' AS type_delai, delai_declaration_j AS jours, 1 AS ordre
  FROM core.fact_sinistre f JOIN core.dim_segment s USING (segment_key) WHERE delai_declaration_j IS NOT NULL
  UNION ALL
  SELECT f.garantie, s.produit, 'Premier règlement', delai_premier_reglement_j, 2
  FROM core.fact_sinistre f JOIN core.dim_segment s USING (segment_key) WHERE delai_premier_reglement_j IS NOT NULL
  UNION ALL
  SELECT f.garantie, s.produit, 'Clôture (proxy dernier règlement)', delai_cloture_j, 3
  FROM core.fact_sinistre f JOIN core.dim_segment s USING (segment_key) WHERE delai_cloture_j IS NOT NULL
)
SELECT COALESCE(garantie, 'TOUTES') AS garantie, type_delai, MIN(ordre) AS ordre, COUNT(*) AS n,
       AVG(jours) AS moyenne, QUANTILE_CONT(jours, 0.25) AS p25, MEDIAN(jours) AS mediane,
       QUANTILE_CONT(jours, 0.75) AS p75, QUANTILE_CONT(jours, 0.90) AS p90, MAX(jours) AS maximum
FROM d GROUP BY GROUPING SETS ((garantie, type_delai), (type_delai));

-- ---------- Audits antifraude (population : sinistres audités uniquement) ----------
CREATE OR REPLACE TABLE mart.audits_criteres AS
WITH f AS (
  SELECT f.*, s.produit, s.canal, s.zone_risque,
         CASE WHEN f.reserve_initiale = 0 THEN 'a. 0 €' WHEN f.reserve_initiale < 1000 THEN 'b. < 1 k€'
              WHEN f.reserve_initiale < 5000 THEN 'c. 1-5 k€' WHEN f.reserve_initiale < 20000 THEN 'd. 5-20 k€'
              ELSE 'e. ≥ 20 k€' END AS tranche_reserve,
         CASE WHEN f.delai_declaration_j IS NULL THEN 'Inconnu' WHEN f.delai_declaration_j <= 2 THEN 'a. 0-2 j'
              WHEN f.delai_declaration_j <= 7 THEN 'b. 3-7 j' WHEN f.delai_declaration_j <= 30 THEN 'c. 8-30 j'
              ELSE 'd. > 30 j' END AS tranche_delai_decl,
         CASE WHEN DATE_DIFF('day', k.date_effet, f.date_survenance) < 90 THEN 'a. < 3 mois'
              WHEN DATE_DIFF('day', k.date_effet, f.date_survenance) < 365 THEN 'b. 3-12 mois'
              ELSE 'c. ≥ 1 an' END AS anciennete_contrat
  FROM core.fact_sinistre f JOIN core.dim_segment s USING (segment_key)
  JOIN core.dim_contrat k ON k.contrat_sk = f.contrat_sk
), u AS (
  SELECT 'garantie' AS critere, garantie AS modalite, audite, fraude_confirmee, reserve_initiale, montant_paye FROM f
  UNION ALL
  SELECT 'tranche_reserve' AS critere, tranche_reserve AS modalite, audite, fraude_confirmee, reserve_initiale, montant_paye FROM f
  UNION ALL
  SELECT 'delai_declaration' AS critere, tranche_delai_decl AS modalite, audite, fraude_confirmee, reserve_initiale, montant_paye FROM f
  UNION ALL
  SELECT 'anciennete_contrat' AS critere, anciennete_contrat AS modalite, audite, fraude_confirmee, reserve_initiale, montant_paye FROM f
  UNION ALL
  SELECT 'canal' AS critere, canal AS modalite, audite, fraude_confirmee, reserve_initiale, montant_paye FROM f
  UNION ALL
  SELECT 'statut' AS critere, statut AS modalite, audite, fraude_confirmee, reserve_initiale, montant_paye FROM f
  UNION ALL
  SELECT 'annee_survenance' AS critere, CAST(annee_survenance AS VARCHAR) AS modalite, audite, fraude_confirmee, reserve_initiale, montant_paye FROM f
  UNION ALL
  SELECT 'ensemble' AS critere, 'Tous' AS modalite, audite, fraude_confirmee, reserve_initiale, montant_paye FROM f
)
SELECT critere, modalite, COUNT(*) AS nb_sinistres, SUM(audite::INT) AS nb_audites,
       SUM(audite::INT) / COUNT(*) AS taux_audit,
       SUM(COALESCE(fraude_confirmee, 0)) AS nb_fraudes_confirmees,
       SUM(COALESCE(fraude_confirmee, 0)) / NULLIF(SUM(audite::INT), 0) AS taux_confirmation_audites,
       SUM(CASE WHEN audite THEN reserve_initiale END) AS reserve_auditee,
       SUM(CASE WHEN fraude_confirmee = 1 THEN reserve_initiale END) AS reserve_fraude_confirmee,
       SUM(CASE WHEN fraude_confirmee = 1 THEN montant_paye END) AS paye_sur_fraude_confirmee
FROM u GROUP BY ALL;

-- ---------- Distribution des coûts (sinistres avec suite) ----------
CREATE OR REPLACE TABLE mart.distribution_couts AS
SELECT s.produit, f.garantie, f.annee_survenance, f.charge, f.charge_ecretee, f.statut, f.sinistre_id
FROM core.fact_sinistre f JOIN core.dim_segment s USING (segment_key) WHERE f.avec_suite;
