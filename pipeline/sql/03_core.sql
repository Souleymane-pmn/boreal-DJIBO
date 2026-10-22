-- =====================================================================
-- COUCHE CŒUR (core) : schéma en étoile
-- Paramètres injectés : {DATE_EXTRACTION}, {SEUIL_GRAVE}
-- Les lignes en quarantaine (clé fichier + n° de ligne) sont exclues.
-- =====================================================================

-- ---------- Vues "valides" (prep moins quarantaine) ----------
CREATE OR REPLACE TEMP VIEW v_clients AS
SELECT * FROM prep.clients p WHERE NOT EXISTS (
  SELECT 1 FROM quarantine.clients q WHERE q._source_file = p._source_file AND q._row_num = p._row_num);
CREATE OR REPLACE TEMP VIEW v_contrats AS
SELECT * FROM prep.contrats p WHERE NOT EXISTS (
  SELECT 1 FROM quarantine.contrats q WHERE q._source_file = p._source_file AND q._row_num = p._row_num);
CREATE OR REPLACE TEMP VIEW v_sinistres AS
SELECT * FROM prep.sinistres p WHERE NOT EXISTS (
  SELECT 1 FROM quarantine.sinistres q WHERE q._source_file = p._source_file AND q._row_num = p._row_num);
CREATE OR REPLACE TEMP VIEW v_reglements AS
SELECT * FROM prep.reglements p WHERE NOT EXISTS (
  SELECT 1 FROM quarantine.reglements q WHERE q._source_file = p._source_file AND q._row_num = p._row_num);
CREATE OR REPLACE TEMP VIEW v_audits AS
SELECT * FROM prep.audits p WHERE NOT EXISTS (
  SELECT 1 FROM quarantine.audits q WHERE q._source_file = p._source_file AND q._row_num = p._row_num);

-- ---------- dim_date (grain : jour) ----------
CREATE OR REPLACE TABLE core.dim_date AS
SELECT CAST(STRFTIME(d, '%Y%m%d') AS INTEGER) AS date_key,
       d::DATE AS date, YEAR(d) AS annee, QUARTER(d) AS trimestre, MONTH(d) AS mois,
       STRFTIME(d, '%Y-%m') AS annee_mois, DATE_TRUNC('month', d)::DATE AS debut_mois,
       ISODOW(d) AS jour_semaine, (d::DATE > DATE '{DATE_EXTRACTION}') AS hors_observation
FROM RANGE(DATE '2019-01-01', DATE '2026-01-01', INTERVAL 1 DAY) t(d);

-- ---------- dim_client (SCD type 1 : survivants de la déduplication) ----------
CREATE OR REPLACE TABLE core.dim_client AS
SELECT c.client_id, c.date_naissance, YEAR(c.date_naissance) AS annee_naissance,
       c.region, c.csp, c.consentement_marketing, c.email_hash, c.date_premier_contrat,
       m.taille_groupe - 1 AS nb_identifiants_absorbes
FROM v_clients c JOIN prep.client_mapping m USING (client_id);

-- ---------- dim_garantie ----------
CREATE OR REPLACE TABLE core.dim_garantie AS
SELECT * FROM (VALUES
  ('COLLISION',  'Collision / dommages au véhicule', 'AUTO',       'Dommages'),
  ('RC',         'Responsabilité civile',            'AUTO',       'Responsabilité'),
  ('BRIS_GLACE', 'Bris de glace',                    'AUTO',       'Dommages'),
  ('VOL',        'Vol',                              'AUTO+HABITATION', 'Vol'),
  ('DEGAT_EAUX', 'Dégât des eaux',                   'HABITATION', 'Dommages'),
  ('INCENDIE',   'Incendie',                         'HABITATION', 'Dommages'),
  ('TEMPETE',    'Tempête / événements climatiques', 'HABITATION', 'Climatique')
) t(garantie, libelle, produit, famille);

-- ---------- dim_segment (dimension "junk" du segment de risque) ----------
-- Produit × zone × formule × canal × tranche d'âge à la souscription.
-- Clé stable : produit cartésien des domaines dans un ordre fixe.
CREATE OR REPLACE TABLE core.dim_segment AS
SELECT ROW_NUMBER() OVER (ORDER BY produit, zone_risque, formule, canal, tranche_age) AS segment_key, *
FROM (SELECT * FROM (VALUES ('AUTO'),('HABITATION')) a(produit),
      (SELECT * FROM RANGE(1,6) r(zone_risque)) z,
      (VALUES ('ESSENTIELLE'),('CONFORT'),('PREMIUM')) f(formule),
      (VALUES ('AGENT'),('COURTIER'),('WEB')) c(canal),
      (VALUES ('18-25'),('26-35'),('36-45'),('46-55'),('56-65'),('66+'),('Inconnu')) t(tranche_age));

-- ---------- dim_contrat (SCD type 2 sur les attributs tarifaires) ----------
-- Type 2 : formule, canal, zone, franchise, bonus-malus, puissance, surface, prime
--          → une nouvelle version si l'un d'eux change entre deux livraisons.
-- Type 1 : date de résiliation et client survivant (corrections / cycle de vie).
CREATE TABLE IF NOT EXISTS core.dim_contrat (
  contrat_sk BIGINT, contrat_id INTEGER, version INTEGER, client_id INTEGER, produit VARCHAR,
  formule VARCHAR, canal VARCHAR, zone_risque INTEGER, franchise INTEGER, bonus_malus DOUBLE,
  puissance_cv INTEGER, surface_m2 INTEGER, prime_annuelle DOUBLE, date_effet DATE,
  date_resiliation DATE, tranche_age_souscription VARCHAR, segment_key BIGINT, hash_attr VARCHAR,
  valid_from DATE, valid_to DATE, is_current BOOLEAN);

CREATE OR REPLACE TEMP TABLE stg_contrat AS
SELECT k.*,
       CASE WHEN c.date_naissance IS NULL THEN 'Inconnu'
            ELSE CASE
              WHEN DATE_DIFF('year', c.date_naissance, k.date_effet) <= 25 THEN '18-25'
              WHEN DATE_DIFF('year', c.date_naissance, k.date_effet) <= 35 THEN '26-35'
              WHEN DATE_DIFF('year', c.date_naissance, k.date_effet) <= 45 THEN '36-45'
              WHEN DATE_DIFF('year', c.date_naissance, k.date_effet) <= 55 THEN '46-55'
              WHEN DATE_DIFF('year', c.date_naissance, k.date_effet) <= 65 THEN '56-65'
              ELSE '66+' END END AS tranche_age_souscription,
       MD5(CONCAT_WS('|', k.formule, k.canal, k.zone_risque, k.franchise, k.bonus_malus,
                     k.puissance_cv, k.surface_m2, k.prime_annuelle)) AS hash_attr
FROM v_contrats k LEFT JOIN core.dim_client c ON c.client_id = k.client_id;

-- 1) Type 1 : mise à jour en place
UPDATE core.dim_contrat d SET date_resiliation = s.date_resiliation, client_id = s.client_id
FROM stg_contrat s WHERE d.contrat_id = s.contrat_id
  AND (d.date_resiliation IS DISTINCT FROM s.date_resiliation OR d.client_id IS DISTINCT FROM s.client_id);
-- 2) Type 2 : clôture des versions dont les attributs tarifaires ont changé
UPDATE core.dim_contrat d SET valid_to = CURRENT_DATE - 1, is_current = FALSE
FROM stg_contrat s WHERE d.contrat_id = s.contrat_id AND d.is_current AND d.hash_attr <> s.hash_attr;
-- 3) Insertion des nouvelles versions (contrat nouveau ou version clôturée)
INSERT INTO core.dim_contrat
SELECT COALESCE((SELECT MAX(contrat_sk) FROM core.dim_contrat), 0)
         + ROW_NUMBER() OVER (ORDER BY s.contrat_id) AS contrat_sk,
       s.contrat_id,
       COALESCE((SELECT MAX(version) FROM core.dim_contrat d WHERE d.contrat_id = s.contrat_id), 0) + 1,
       s.client_id, s.produit, s.formule, s.canal, s.zone_risque, s.franchise, s.bonus_malus,
       s.puissance_cv, s.surface_m2, s.prime_annuelle, s.date_effet, s.date_resiliation,
       s.tranche_age_souscription, g.segment_key, s.hash_attr,
       CASE WHEN EXISTS (SELECT 1 FROM core.dim_contrat d WHERE d.contrat_id = s.contrat_id)
            THEN CURRENT_DATE ELSE s.date_effet END,
       DATE '9999-12-31', TRUE
FROM stg_contrat s
JOIN core.dim_segment g ON g.produit = s.produit AND g.zone_risque = s.zone_risque AND g.formule = s.formule
                       AND g.canal = s.canal AND g.tranche_age = s.tranche_age_souscription
WHERE NOT EXISTS (SELECT 1 FROM core.dim_contrat d WHERE d.contrat_id = s.contrat_id AND d.is_current);
-- 4) Contrat disparu de la source ou passé en quarantaine : version courante désactivée
UPDATE core.dim_contrat SET is_current = FALSE, valid_to = CURRENT_DATE - 1
WHERE is_current AND contrat_id NOT IN (SELECT contrat_id FROM stg_contrat);

CREATE OR REPLACE TEMP VIEW v_contrat_courant AS SELECT * FROM core.dim_contrat WHERE is_current;

-- ---------- fact_exposition_mensuelle (grain : contrat × mois civil) ----------
-- Couverture du jour d'effet (inclus) à la résiliation (exclue) ou au 30/06/2025 (inclus).
CREATE OR REPLACE TABLE core.fact_exposition_mensuelle AS
WITH b AS (
  SELECT contrat_sk, contrat_id, client_id, segment_key, prime_annuelle, date_effet, date_resiliation,
         date_effet AS d0,
         LEAST(COALESCE(date_resiliation, DATE '{DATE_EXTRACTION}' + 1), DATE '{DATE_EXTRACTION}' + 1) AS d1
  FROM v_contrat_courant
), m AS (
  SELECT b.*, UNNEST(GENERATE_SERIES(DATE_TRUNC('month', d0), DATE_TRUNC('month', d1 - 1), INTERVAL 1 MONTH))::DATE AS mois
  FROM b WHERE d1 > d0
)
SELECT CAST(STRFTIME(mois, '%Y%m%d') AS INTEGER) AS mois_key, mois, YEAR(mois) AS annee,
       contrat_sk, contrat_id, client_id, segment_key,
       DATE_DIFF('day', GREATEST(d0, mois), LEAST(d1, (mois + INTERVAL 1 MONTH)::DATE)) AS jours_couverts,
       DATE_DIFF('day', GREATEST(d0, mois), LEAST(d1, (mois + INTERVAL 1 MONTH)::DATE)) / 365.25 AS exposition_annees,
       prime_annuelle * DATE_DIFF('day', GREATEST(d0, mois), LEAST(d1, (mois + INTERVAL 1 MONTH)::DATE)) / 365.25 AS prime_acquise,
       (DATE_TRUNC('month', date_effet) = mois)::INTEGER AS nouvelle_souscription,
       (date_resiliation IS NOT NULL AND DATE_TRUNC('month', date_resiliation) = mois)::INTEGER AS resiliation,
       (d1 >= (mois + INTERVAL 1 MONTH)::DATE)::INTEGER AS actif_fin_mois
FROM m;

-- ---------- fact_exposition_annuelle (grain : contrat × année civile) ----------
CREATE OR REPLACE TABLE core.fact_exposition_annuelle AS
SELECT annee, contrat_sk, contrat_id, client_id, segment_key,
       SUM(jours_couverts) AS jours_couverts, SUM(exposition_annees) AS exposition_annees,
       SUM(prime_acquise) AS prime_acquise, MAX(nouvelle_souscription) AS nouvelle_souscription,
       MAX(resiliation) AS resiliation,
       MAX(CASE WHEN mois = (SELECT MAX(mois) FROM core.fact_exposition_mensuelle f2 WHERE f2.annee = f.annee)
                THEN actif_fin_mois END) AS actif_fin_periode
FROM core.fact_exposition_mensuelle f GROUP BY ALL;

-- ---------- fact_reglement (grain : paiement) — chargement incrémental idempotent ----------
CREATE TABLE IF NOT EXISTS core.fact_reglement (
  paiement_id INTEGER, sinistre_id INTEGER, contrat_id INTEGER, date_paiement DATE,
  date_paiement_key INTEGER, montant DOUBLE, _source_file VARCHAR, charge_le TIMESTAMP);
-- (a) on retire ce qui n'est plus valide (ex. paiement passé en quarantaine)
DELETE FROM core.fact_reglement WHERE paiement_id NOT IN (SELECT paiement_id FROM v_reglements);
-- (b) on n'insère que les paiements absents : au second passage, 0 ligne insérée
INSERT INTO core.fact_reglement
SELECT r.paiement_id, r.sinistre_id, s.contrat_id, r.date_paiement,
       CAST(STRFTIME(r.date_paiement, '%Y%m%d') AS INTEGER), r.montant, r._source_file, NOW()
FROM v_reglements r JOIN v_sinistres s USING (sinistre_id)
WHERE NOT EXISTS (SELECT 1 FROM core.fact_reglement f WHERE f.paiement_id = r.paiement_id);

-- ---------- fact_sinistre (grain : sinistre) ----------
CREATE OR REPLACE TABLE core.fact_sinistre AS
WITH p AS (
  SELECT sinistre_id, SUM(montant) AS montant_paye, COUNT(*) AS nb_paiements,
         MIN(date_paiement) AS date_premier_paiement, MAX(date_paiement) AS date_dernier_paiement
  FROM core.fact_reglement GROUP BY 1
), flags AS (
  SELECT cle, BOOL_OR(rule_id = 'Q18') AS fl_decl_avant_surv, BOOL_OR(rule_id = 'Q19') AS fl_hors_couverture
  FROM meta.dq_anomalies WHERE entite = 'sinistres' GROUP BY 1
)
SELECT s.sinistre_id, s.contrat_id, k.contrat_sk, k.client_id, k.segment_key, s.garantie,
       CAST(STRFTIME(s.date_survenance, '%Y%m%d') AS INTEGER) AS date_survenance_key,
       s.date_survenance, s.date_declaration, YEAR(s.date_survenance) AS annee_survenance,
       DATE_TRUNC('month', s.date_survenance)::DATE AS mois_survenance,
       s.statut, (s.statut IN ('CLOTURE', 'OUVERT')) AS avec_suite,
       s.reserve_initiale,
       COALESCE(p.montant_paye, 0) AS montant_paye, COALESCE(p.nb_paiements, 0) AS nb_paiements,
       CASE WHEN s.statut = 'OUVERT' THEN GREATEST(s.reserve_initiale - COALESCE(p.montant_paye, 0), 0) ELSE 0 END
         AS reserve_restante,
       COALESCE(p.montant_paye, 0)
         + CASE WHEN s.statut = 'OUVERT' THEN GREATEST(s.reserve_initiale - COALESCE(p.montant_paye, 0), 0) ELSE 0 END
         AS charge,
       LEAST(COALESCE(p.montant_paye, 0)
         + CASE WHEN s.statut = 'OUVERT' THEN GREATEST(s.reserve_initiale - COALESCE(p.montant_paye, 0), 0) ELSE 0 END,
         {SEUIL_GRAVE}) AS charge_ecretee,
       p.date_premier_paiement, p.date_dernier_paiement,
       CASE WHEN NOT COALESCE(f.fl_decl_avant_surv, FALSE)
            THEN DATE_DIFF('day', s.date_survenance, s.date_declaration) END AS delai_declaration_j,
       DATE_DIFF('day', s.date_declaration, p.date_premier_paiement) AS delai_premier_reglement_j,
       -- Pas de date de clôture dans la source : proxy = date du dernier règlement (sinistres clôturés)
       CASE WHEN s.statut = 'CLOTURE' THEN DATE_DIFF('day', s.date_declaration, p.date_dernier_paiement) END
         AS delai_cloture_j,
       (a.sinistre_id IS NOT NULL) AS audite, a.date_audit, a.fraude_confirmee,
       COALESCE(f.fl_decl_avant_surv, FALSE) AS fl_decl_avant_surv,
       COALESCE(f.fl_hors_couverture, FALSE) AS fl_hors_couverture
FROM v_sinistres s
JOIN v_contrat_courant k USING (contrat_id)
LEFT JOIN p USING (sinistre_id)
LEFT JOIN v_audits a USING (sinistre_id)
LEFT JOIN flags f ON f.cle = s.sinistre_id::VARCHAR;
