"""Livrable 2 · Règles de qualité et quarantaine.

Chaque règle = une requête qui renvoie les lignes en anomalie
(cle, _source_file, _row_num, detail), une gravité et un traitement :
  - EXCLURE   : la ligne est écartée du cœur et copiée en quarantaine avec son motif ;
  - FUSIONNER : doublon absorbé par un identifiant survivant (copié en quarantaine) ;
  - CORRIGER  : la valeur est corrigée en préparation (ex. date sentinelle → NULL) ;
  - SIGNALER  : la ligne est conservée et marquée (meta.dq_anomalies).
Une règle BLOQUANTE avec au moins une anomalie interrompt le chargement.
Toutes les anomalies (quel que soit le traitement) sont tracées dans meta.dq_anomalies.
"""
from __future__ import annotations

from dataclasses import dataclass

from pipeline.config import DATE_EXTRACTION


class QualityBlockingError(Exception):
    pass


@dataclass
class Rule:
    id: str
    entite: str
    dimension: str
    libelle: str
    gravite: str  # BLOQUANT | MAJEUR | MINEUR
    traitement: str  # EXCLURE | FUSIONNER | CORRIGER | SIGNALER
    sql: str


D = DATE_EXTRACTION
RULES: list[Rule] = [
    # ------------------------------ CLIENTS ------------------------------
    Rule("Q01", "clients", "COMPLETUDE", "Date de naissance manquante", "MINEUR", "SIGNALER",
         "SELECT client_id::VARCHAR cle, _source_file, _row_num, 'date_naissance vide' detail "
         "FROM prep.clients WHERE fl_dn_manquante"),
    Rule("Q02", "clients", "VALIDITE", "Date de naissance sentinelle 01/01/1890", "MAJEUR", "CORRIGER",
         "SELECT client_id::VARCHAR, _source_file, _row_num, date_naissance_brute "
         "FROM prep.clients WHERE fl_dn_sentinelle"),
    Rule("Q03", "clients", "VALIDITE", "Âge invraisemblable au 1er contrat (<18 ou >100 ans)", "MAJEUR", "CORRIGER",
         "SELECT client_id::VARCHAR, _source_file, _row_num, "
         "'né le '||date_naissance_brute||', âge '||age_premier_contrat FROM prep.clients WHERE fl_age_invraisemblable"),
    Rule("Q04", "clients", "UNICITE", "Identifiant client dupliqué", "BLOQUANT", "EXCLURE",
         "SELECT client_id::VARCHAR, _source_file, _row_num, 'client_id en double' FROM prep.clients "
         "WHERE client_id IN (SELECT client_id FROM prep.clients GROUP BY 1 HAVING COUNT(*)>1) OR client_id IS NULL"),
    Rule("Q05", "clients", "UNICITE", "Doublon métier (même e-mail + date de naissance)", "MAJEUR", "FUSIONNER",
         "SELECT c.client_id::VARCHAR, c._source_file, c._row_num, 'absorbé par client '||m.client_id_survivant "
         "FROM prep.clients c JOIN prep.client_mapping m USING (client_id) WHERE m.rang > 1"),
    Rule("Q06", "clients", "VALIDITE", "Région ou CSP hors référentiel", "MINEUR", "SIGNALER",
         "SELECT client_id::VARCHAR, _source_file, _row_num, region||'/'||csp FROM prep.clients "
         "WHERE region NOT IN ('IDF','ARA','HDF','OCC','NAQ','PACA','GES','BFC','PDL','NOR','BRE','CVL','COR') "
         "OR csp NOT IN ('EMPLOYE','RETRAITE','CADRE','OUVRIER','INDEPENDANT','ETUDIANT')"),
    # ------------------------------ CONTRATS -----------------------------
    Rule("Q07", "contrats", "UNICITE", "Identifiant contrat dupliqué ou vide", "BLOQUANT", "EXCLURE",
         "SELECT contrat_id::VARCHAR, _source_file, _row_num, 'contrat_id en double' FROM prep.contrats "
         "WHERE contrat_id IN (SELECT contrat_id FROM prep.contrats GROUP BY 1 HAVING COUNT(*)>1) OR contrat_id IS NULL"),
    Rule("Q08", "contrats", "COHERENCE_TABLES", "Contrat rattaché à un client inexistant", "MAJEUR", "EXCLURE",
         "SELECT contrat_id::VARCHAR, _source_file, _row_num, 'client '||client_id_source FROM prep.contrats k "
         "WHERE NOT EXISTS (SELECT 1 FROM prep.clients c WHERE c.client_id = k.client_id_source)"),
    Rule("Q09", "contrats", "COHERENCE_TEMPORELLE", "Date de résiliation antérieure à la date d'effet", "MAJEUR", "EXCLURE",
         "SELECT contrat_id::VARCHAR, _source_file, _row_num, date_effet||' > '||date_resiliation "
         "FROM prep.contrats WHERE date_resiliation < date_effet"),
    Rule("Q10", "contrats", "COHERENCE_TEMPORELLE", "Résiliation le jour de l'effet (durée nulle)", "MINEUR", "SIGNALER",
         "SELECT contrat_id::VARCHAR, _source_file, _row_num, 'effet = résiliation = '||date_effet "
         "FROM prep.contrats WHERE date_resiliation = date_effet"),
    Rule("Q11", "contrats", "VALIDITE", "Prime annuelle nulle ou négative", "MAJEUR", "EXCLURE",
         "SELECT contrat_id::VARCHAR, _source_file, _row_num, 'prime = '||prime_annuelle "
         "FROM prep.contrats WHERE prime_annuelle IS NULL OR prime_annuelle <= 0"),
    Rule("Q12", "contrats", "VALIDITE", "Valeur hors domaine (produit, formule, canal, zone, franchise)", "MAJEUR", "EXCLURE",
         "SELECT contrat_id::VARCHAR, _source_file, _row_num, produit||'/'||formule||'/'||canal||'/'||zone_risque "
         "FROM prep.contrats WHERE produit NOT IN ('AUTO','HABITATION') "
         "OR formule NOT IN ('ESSENTIELLE','CONFORT','PREMIUM') OR canal NOT IN ('AGENT','COURTIER','WEB') "
         "OR zone_risque NOT BETWEEN 1 AND 5 OR franchise NOT IN (150,300,500,1000) "
         "OR produit IS NULL OR formule IS NULL OR canal IS NULL OR zone_risque IS NULL OR franchise IS NULL"),
    Rule("Q13", "contrats", "COHERENCE", "Attributs incohérents avec le produit", "MINEUR", "SIGNALER",
         "SELECT contrat_id::VARCHAR, _source_file, _row_num, produit FROM prep.contrats "
         "WHERE (produit='AUTO' AND (puissance_cv IS NULL OR bonus_malus IS NULL OR surface_m2 IS NOT NULL)) "
         "OR (produit='HABITATION' AND (surface_m2 IS NULL OR puissance_cv IS NOT NULL))"),
    Rule("Q14", "contrats", "COMPLETUDE", "Date d'effet manquante ou illisible", "MAJEUR", "EXCLURE",
         "SELECT contrat_id::VARCHAR, _source_file, _row_num, COALESCE(date_effet_brute,'vide') "
         "FROM prep.contrats WHERE date_effet IS NULL "
         "OR (date_resiliation IS NULL AND date_resiliation_brute IS NOT NULL)"),
    Rule("Q15", "contrats", "COHERENCE_TEMPORELLE", "Dates postérieures à l'extraction", "MAJEUR", "EXCLURE",
         f"SELECT contrat_id::VARCHAR, _source_file, _row_num, date_effet||' / '||COALESCE(date_resiliation::VARCHAR,'') "
         f"FROM prep.contrats WHERE date_effet > DATE '{D}' OR date_resiliation > DATE '{D}'"),
    # ------------------------------ SINISTRES ----------------------------
    Rule("Q16", "sinistres", "UNICITE", "Identifiant sinistre dupliqué ou vide", "BLOQUANT", "EXCLURE",
         "SELECT sinistre_id::VARCHAR, _source_file, _row_num, 'doublon' FROM prep.sinistres "
         "WHERE sinistre_id IN (SELECT sinistre_id FROM prep.sinistres GROUP BY 1 HAVING COUNT(*)>1) OR sinistre_id IS NULL"),
    Rule("Q17", "sinistres", "COHERENCE_TABLES", "Sinistre sur contrat inexistant ou en quarantaine", "MAJEUR", "EXCLURE",
         "SELECT s.sinistre_id::VARCHAR, s._source_file, s._row_num, 'contrat '||s.contrat_id FROM prep.sinistres s "
         "WHERE NOT EXISTS (SELECT 1 FROM prep.contrats k WHERE k.contrat_id = s.contrat_id) "
         "OR s.contrat_id::VARCHAR IN (SELECT cle FROM quarantine.contrats)"),
    Rule("Q18", "sinistres", "COHERENCE_TEMPORELLE", "Déclaration antérieure à la survenance", "MINEUR", "SIGNALER",
         "SELECT sinistre_id::VARCHAR, _source_file, _row_num, date_survenance||' > '||date_declaration "
         "FROM prep.sinistres WHERE date_declaration < date_survenance"),
    Rule("Q19", "sinistres", "COHERENCE_TEMPORELLE", "Survenance hors période de couverture du contrat", "MAJEUR", "SIGNALER",
         "SELECT s.sinistre_id::VARCHAR, s._source_file, s._row_num, "
         "'survenance '||s.date_survenance||' / contrat '||k.date_effet||'→'||COALESCE(k.date_resiliation::VARCHAR,'') "
         "FROM prep.sinistres s JOIN prep.contrats k USING (contrat_id) "
         "WHERE s.date_survenance < k.date_effet OR s.date_survenance > k.date_resiliation"),
    Rule("Q20", "sinistres", "COHERENCE_TABLES", "Garantie incompatible avec le produit", "MAJEUR", "EXCLURE",
         "SELECT s.sinistre_id::VARCHAR, s._source_file, s._row_num, s.garantie||' sur '||k.produit "
         "FROM prep.sinistres s JOIN prep.contrats k USING (contrat_id) "
         "WHERE (k.produit='AUTO' AND s.garantie NOT IN ('COLLISION','RC','VOL','BRIS_GLACE')) "
         "OR (k.produit='HABITATION' AND s.garantie NOT IN ('DEGAT_EAUX','INCENDIE','TEMPETE','VOL'))"),
    Rule("Q21", "sinistres", "COHERENCE", "Statut incohérent avec la réserve", "MINEUR", "SIGNALER",
         "SELECT sinistre_id::VARCHAR, _source_file, _row_num, statut||' / réserve '||reserve_initiale "
         "FROM prep.sinistres WHERE (statut IN ('REJETE','SANS_SUITE') AND reserve_initiale > 0) "
         "OR (statut IN ('OUVERT','CLOTURE') AND COALESCE(reserve_initiale,0) <= 0) "
         "OR statut NOT IN ('OUVERT','CLOTURE','REJETE','SANS_SUITE')"),
    Rule("Q22", "sinistres", "VALIDITE", "Réserve atypique (> 500 k€) : sinistre grave à isoler", "MINEUR", "SIGNALER",
         "SELECT sinistre_id::VARCHAR, _source_file, _row_num, 'réserve '||reserve_initiale "
         "FROM prep.sinistres WHERE reserve_initiale > 500000"),
    # ------------------------------ RÈGLEMENTS ---------------------------
    Rule("Q23", "reglements", "UNICITE", "Paiement livré plusieurs fois (re-livraison)", "MAJEUR", "EXCLURE",
         "SELECT paiement_id::VARCHAR, _source_file, _row_num, 'déjà livré, livraison n°'||rang_livraison "
         "FROM prep.reglements WHERE rang_livraison > 1"),
    Rule("Q24", "reglements", "COHERENCE_TABLES", "Paiement sur sinistre inexistant ou en quarantaine", "MAJEUR", "EXCLURE",
         "SELECT r.paiement_id::VARCHAR, r._source_file, r._row_num, 'sinistre '||r.sinistre_id FROM prep.reglements r "
         "WHERE NOT EXISTS (SELECT 1 FROM prep.sinistres s WHERE s.sinistre_id = r.sinistre_id) "
         "OR r.sinistre_id::VARCHAR IN (SELECT cle FROM quarantine.sinistres)"),
    Rule("Q25", "reglements", "VALIDITE", "Montant nul, négatif ou illisible", "MAJEUR", "EXCLURE",
         "SELECT paiement_id::VARCHAR, _source_file, _row_num, 'montant '||COALESCE(montant::VARCHAR,'illisible') "
         "FROM prep.reglements WHERE montant IS NULL OR montant <= 0 OR paiement_id IS NULL"),
    Rule("Q26", "reglements", "COHERENCE_TEMPORELLE", "Paiement avant déclaration ou après extraction", "MAJEUR", "EXCLURE",
         f"SELECT r.paiement_id::VARCHAR, r._source_file, r._row_num, r.date_paiement::VARCHAR FROM prep.reglements r "
         f"LEFT JOIN prep.sinistres s USING (sinistre_id) "
         f"WHERE r.date_paiement IS NULL OR r.date_paiement > DATE '{D}' OR r.date_paiement < s.date_declaration"),
    Rule("Q27", "reglements", "COHERENCE", "Paiement sur sinistre rejeté ou sans suite", "MAJEUR", "SIGNALER",
         "SELECT r.paiement_id::VARCHAR, r._source_file, r._row_num, s.statut FROM prep.reglements r "
         "JOIN prep.sinistres s USING (sinistre_id) WHERE s.statut IN ('REJETE','SANS_SUITE')"),
    Rule("Q28", "reglements", "VALIDITE", "Fichier au schéma non standard (colonnes renommées/permutées)", "MINEUR", "SIGNALER",
         "SELECT paiement_id::VARCHAR, _source_file, _row_num, _header_original FROM prep.reglements "
         "WHERE _header_original <> 'paiement_id,sinistre_id,date_paiement,montant'"),
    Rule("Q29", "reglements", "COHERENCE_TEMPORELLE", "Paiement hors du mois de son fichier de livraison", "MINEUR", "SIGNALER",
         "SELECT paiement_id::VARCHAR, _source_file, _row_num, 'payé '||date_paiement||' livré '||mois_fichier "
         "FROM prep.reglements WHERE STRFTIME(date_paiement,'%Y-%m') <> mois_fichier"),
    Rule("Q30", "sinistres", "COHERENCE", "Cumul payé > 2 fois la réserve initiale du sinistre", "MINEUR", "SIGNALER",
         "SELECT s.sinistre_id::VARCHAR, s._source_file, s._row_num, 'payé '||ROUND(p.tot,2)||' / réserve '||s.reserve_initiale "
         "FROM prep.sinistres s JOIN (SELECT sinistre_id, SUM(montant) tot FROM prep.reglements WHERE rang_livraison=1 GROUP BY 1) p "
         "USING (sinistre_id) WHERE p.tot > 2*s.reserve_initiale"),
    # ------------------------------ AUDITS -------------------------------
    Rule("Q31", "audits", "COHERENCE_TABLES", "Audit sur sinistre inexistant ou en quarantaine", "MAJEUR", "EXCLURE",
         "SELECT a.sinistre_id::VARCHAR, a._source_file, a._row_num, 'sinistre absent' FROM prep.audits a "
         "WHERE NOT EXISTS (SELECT 1 FROM prep.sinistres s WHERE s.sinistre_id = a.sinistre_id) "
         "OR a.sinistre_id::VARCHAR IN (SELECT cle FROM quarantine.sinistres)"),
    Rule("Q32", "audits", "UNICITE", "Plusieurs audits pour un même sinistre", "MAJEUR", "EXCLURE",
         "SELECT sinistre_id::VARCHAR, _source_file, _row_num, 'audit en double' FROM ("
         "SELECT *, ROW_NUMBER() OVER (PARTITION BY sinistre_id ORDER BY date_audit DESC, _row_num) rn FROM prep.audits) WHERE rn > 1"),
    Rule("Q33", "audits", "COHERENCE_TEMPORELLE", "Audit antérieur à la déclaration ou postérieur à l'extraction", "MINEUR", "SIGNALER",
         f"SELECT a.sinistre_id::VARCHAR, a._source_file, a._row_num, a.date_audit::VARCHAR FROM prep.audits a "
         f"JOIN prep.sinistres s USING (sinistre_id) WHERE a.date_audit < s.date_declaration OR a.date_audit > DATE '{D}'"),
    Rule("Q34", "audits", "VALIDITE", "Indicateur de fraude hors {0,1}", "MAJEUR", "EXCLURE",
         "SELECT sinistre_id::VARCHAR, _source_file, _row_num, COALESCE(fraude_confirmee::VARCHAR,'vide') "
         "FROM prep.audits WHERE fraude_confirmee IS NULL OR fraude_confirmee NOT IN (0,1)"),
]


def run_quality(con, run_id: str) -> list[dict]:
    con.execute("""CREATE TABLE IF NOT EXISTS meta.dq_rules (rule_id VARCHAR, entite VARCHAR, dimension VARCHAR,
                   libelle VARCHAR, gravite VARCHAR, traitement VARCHAR, requete VARCHAR)""")
    con.execute("""CREATE TABLE IF NOT EXISTS meta.dq_results (run_id VARCHAR, rule_id VARCHAR, entite VARCHAR,
                   volume INTEGER, volume_total INTEGER, taux DOUBLE, gravite VARCHAR, traitement VARCHAR,
                   statut VARCHAR, controle_le TIMESTAMP)""")
    con.execute("DELETE FROM meta.dq_rules")
    for r in RULES:
        con.execute("INSERT INTO meta.dq_rules VALUES (?,?,?,?,?,?,?)",
                    [r.id, r.entite, r.dimension, r.libelle, r.gravite, r.traitement, r.sql])
    # Les tables de quarantaine et d'anomalies sont reconstruites à chaque exécution
    # (prep est entièrement recalculée depuis raw), ce qui garantit l'idempotence.
    con.execute("""CREATE OR REPLACE TABLE meta.dq_anomalies (run_id VARCHAR, rule_id VARCHAR, entite VARCHAR,
                   cle VARCHAR, _source_file VARCHAR, _row_num INTEGER, detail VARCHAR, traitement VARCHAR)""")
    for ent in ["clients", "contrats", "sinistres", "reglements", "audits"]:
        con.execute(f"""CREATE OR REPLACE TABLE quarantine.{ent} (cle VARCHAR, rule_id VARCHAR, motif VARCHAR,
                        gravite VARCHAR, detail VARCHAR, _source_file VARCHAR, _row_num INTEGER,
                        ligne_brute JSON, run_id VARCHAR, mis_en_quarantaine_le TIMESTAMP)""")
    totals = {e: con.execute(f"SELECT COUNT(*) FROM prep.{e}").fetchone()[0]
              for e in ["clients", "contrats", "sinistres", "reglements", "audits"]}
    results, blocking = [], []
    for r in RULES:
        con.execute(f"CREATE OR REPLACE TEMP TABLE _viol AS {r.sql}")
        con.execute("ALTER TABLE _viol RENAME COLUMN \"" + con.execute("SELECT * FROM _viol LIMIT 0").description[0][0] + "\" TO cle")
        cols = [d[0] for d in con.execute("SELECT * FROM _viol LIMIT 0").description]
        detail_col = cols[3]
        n = con.execute("SELECT COUNT(*) FROM _viol").fetchone()[0]
        con.execute(f"""INSERT INTO meta.dq_anomalies SELECT ?, ?, ?, cle, _source_file, _row_num,
                        "{detail_col}"::VARCHAR, ? FROM _viol""", [run_id, r.id, r.entite, r.traitement])
        if r.traitement in ("EXCLURE", "FUSIONNER") and n:
            con.execute(f"""INSERT INTO quarantine.{r.entite}
                SELECT v.cle, ?, ?, ?, v."{detail_col}"::VARCHAR, v._source_file, v._row_num,
                       to_json(b), ?, now()
                FROM _viol v LEFT JOIN raw.{r.entite} b
                  ON b._source_file = v._source_file AND b._row_num = v._row_num""",
                        [r.id, r.libelle, r.gravite, run_id])
        statut = "OK" if n == 0 else ("ECHEC_BLOQUANT" if r.gravite == "BLOQUANT" else "ANOMALIES")
        if statut == "ECHEC_BLOQUANT":
            blocking.append(r.id)
        tot = totals[r.entite]
        res = dict(run_id=run_id, rule_id=r.id, entite=r.entite, volume=n, volume_total=tot,
                   taux=(n / tot if tot else 0), gravite=r.gravite, traitement=r.traitement, statut=statut)
        con.execute("INSERT INTO meta.dq_results VALUES (?,?,?,?,?,?,?,?,?, now())", list(res.values()))
        results.append(res)
    if blocking:
        raise QualityBlockingError(f"Règles bloquantes en échec : {blocking}")
    return results
