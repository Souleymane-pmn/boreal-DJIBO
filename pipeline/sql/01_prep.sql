-- =====================================================================
-- COUCHE PRÉPARATION (prep) : typage, normalisation, indicateurs qualité
-- Reconstruite intégralement à chaque exécution depuis raw → idempotente.
-- Aucune ligne n'est supprimée ici : les exclusions sont décidées par les
-- règles qualité (02_quality) et tracées en quarantaine.
-- =====================================================================

-- ---------- Contrats ----------
CREATE OR REPLACE TABLE prep.contrats AS
SELECT
    TRY_CAST(contrat_id AS INTEGER)                    AS contrat_id,
    TRY_CAST(client_id AS INTEGER)                     AS client_id_source,
    UPPER(TRIM(produit))                               AS produit,
    TRY_CAST(date_effet AS DATE)                       AS date_effet,
    TRY_CAST(date_resiliation AS DATE)                 AS date_resiliation,
    UPPER(TRIM(formule))                               AS formule,
    UPPER(TRIM(canal_distribution))                    AS canal,
    TRY_CAST(zone_risque AS INTEGER)                   AS zone_risque,
    TRY_CAST(franchise AS INTEGER)                     AS franchise,
    TRY_CAST(bonus_malus AS DOUBLE)                    AS bonus_malus,
    TRY_CAST(TRY_CAST(puissance_cv AS DOUBLE) AS INTEGER) AS puissance_cv,
    TRY_CAST(TRY_CAST(surface_m2 AS DOUBLE) AS INTEGER)   AS surface_m2,
    TRY_CAST(prime_annuelle AS DOUBLE)                 AS prime_annuelle,
    date_effet       AS date_effet_brute,
    date_resiliation AS date_resiliation_brute,
    _source_file, _row_num
FROM raw.contrats;

-- ---------- Clients ----------
-- Date de naissance au format JJ/MM/AAAA dans le CRM ; 01/01/1890 = valeur sentinelle.
CREATE OR REPLACE TABLE prep.clients AS
WITH typed AS (
    SELECT
        TRY_CAST(client_id AS INTEGER)                         AS client_id,
        date_naissance                                         AS date_naissance_brute,
        TRY_STRPTIME(date_naissance, '%d/%m/%Y')::DATE         AS dn_parse,
        UPPER(TRIM(region))                                    AS region,
        UPPER(TRIM(csp))                                       AS csp,
        TRY_CAST(consent_marketing AS INTEGER) = 1             AS consentement_marketing,
        TRIM(email_hash)                                       AS email_hash,
        _source_file, _row_num
    FROM raw.clients
),
premier_contrat AS (
    SELECT client_id_source AS client_id, MIN(date_effet) AS date_premier_contrat
    FROM prep.contrats GROUP BY 1
)
SELECT t.*,
       p.date_premier_contrat,
       DATE_DIFF('year', t.dn_parse, p.date_premier_contrat)
         - CASE WHEN STRFTIME(p.date_premier_contrat, '%m%d') < STRFTIME(t.dn_parse, '%m%d') THEN 1 ELSE 0 END
                                                               AS age_premier_contrat,
       (t.date_naissance_brute IS NULL)                        AS fl_dn_manquante,
       (t.date_naissance_brute IS NOT NULL AND t.dn_parse IS NULL) AS fl_dn_format,
       (t.dn_parse = DATE '1890-01-01')                        AS fl_dn_sentinelle
FROM typed t LEFT JOIN premier_contrat p USING (client_id);

-- Date de naissance retenue : NULL si manquante, sentinelle ou âge invraisemblable
-- (moins de 18 ans ou plus de 100 ans à la souscription du premier contrat).
CREATE OR REPLACE TABLE prep.clients AS
SELECT *,
       (NOT fl_dn_sentinelle AND age_premier_contrat IS NOT NULL
            AND (age_premier_contrat < 18 OR age_premier_contrat > 100)) AS fl_age_invraisemblable,
       CASE WHEN dn_parse IS NULL OR fl_dn_sentinelle
                 OR age_premier_contrat < 18 OR age_premier_contrat > 100 THEN NULL
            ELSE dn_parse END                                         AS date_naissance
FROM prep.clients;

-- ---------- Déduplication des clients ----------
-- Clé de rapprochement : empreinte e-mail + date de naissance brute.
-- Règle de survie : on conserve l'identifiant qui porte des contrats ; à égalité,
-- le plus petit identifiant (le plus ancien dans le CRM). Les contrats des
-- identifiants absorbés sont rattachés au survivant.
CREATE OR REPLACE TABLE prep.client_mapping AS
WITH nb AS (
    SELECT c.client_id, c.email_hash, COALESCE(c.date_naissance_brute, '∅') AS dn_key,
           COUNT(k.contrat_id) AS nb_contrats
    FROM prep.clients c LEFT JOIN prep.contrats k ON k.client_id_source = c.client_id
    GROUP BY ALL
),
ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY email_hash, dn_key
                              ORDER BY (nb_contrats > 0) DESC, client_id) AS rang,
           COUNT(*) OVER (PARTITION BY email_hash, dn_key) AS taille_groupe
    FROM nb
)
SELECT r.client_id,
       FIRST_VALUE(r.client_id) OVER (PARTITION BY email_hash, dn_key ORDER BY rang) AS client_id_survivant,
       r.rang, r.taille_groupe, r.nb_contrats
FROM ranked r;

ALTER TABLE prep.contrats ADD COLUMN client_id INTEGER;
UPDATE prep.contrats k SET client_id = m.client_id_survivant
FROM prep.client_mapping m WHERE m.client_id = k.client_id_source;

-- ---------- Sinistres ----------
CREATE OR REPLACE TABLE prep.sinistres AS
SELECT
    TRY_CAST(sinistre_id AS INTEGER)       AS sinistre_id,
    TRY_CAST(contrat_id AS INTEGER)        AS contrat_id,
    TRY_CAST(date_survenance AS DATE)      AS date_survenance,
    TRY_CAST(date_declaration AS DATE)     AS date_declaration,
    UPPER(TRIM(garantie))                  AS garantie,
    UPPER(TRIM(statut))                    AS statut,
    TRY_CAST(reserve_initiale AS DOUBLE)   AS reserve_initiale,
    _source_file, _row_num
FROM raw.sinistres;

-- ---------- Règlements ----------
-- Le rang de livraison permet d'identifier les paiements livrés plusieurs fois :
-- la première livraison (fichier le plus ancien) est conservée.
CREATE OR REPLACE TABLE prep.reglements AS
SELECT
    TRY_CAST(paiement_id AS INTEGER)       AS paiement_id,
    TRY_CAST(sinistre_id AS INTEGER)       AS sinistre_id,
    TRY_CAST(date_paiement AS DATE)        AS date_paiement,
    TRY_CAST(montant AS DOUBLE)            AS montant,
    REGEXP_EXTRACT(_source_file, '(\d{4})_(\d{2})', 1) || '-' ||
    REGEXP_EXTRACT(_source_file, '(\d{4})_(\d{2})', 2) AS mois_fichier,
    ROW_NUMBER() OVER (PARTITION BY TRY_CAST(paiement_id AS INTEGER)
                       ORDER BY _source_file, _row_num) AS rang_livraison,
    _source_file, _row_num, _header_original
FROM raw.reglements;

-- ---------- Audits antifraude ----------
CREATE OR REPLACE TABLE prep.audits AS
SELECT
    TRY_CAST(sinistre_id AS INTEGER)       AS sinistre_id,
    TRY_CAST(date_audit AS DATE)           AS date_audit,
    TRY_CAST(fraude_confirmee AS INTEGER)  AS fraude_confirmee,
    _source_file, _row_num
FROM raw.audits;
