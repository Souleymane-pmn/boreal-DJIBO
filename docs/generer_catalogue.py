"""Génère docs/catalogue_donnees.md à partir du schéma réel de l'entrepôt + dictionnaire métier.
Échoue si une colonne n'a pas de définition (le catalogue reste exhaustif).
Usage : python -m docs.generer_catalogue
"""
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.config import DB_PATH  # noqa: E402

TABLES = {
    "raw.*": "Copie fidèle des sources, toutes valeurs en texte, une ligne par ligne source.",
    "prep.clients": "Clients typés ; date de naissance contrôlée (sentinelle et âges invraisemblables neutralisés).",
    "prep.client_mapping": "Table de rapprochement des doublons clients : identifiant source → identifiant survivant.",
    "prep.contrats": "Contrats typés ; client rattaché au survivant de la déduplication.",
    "prep.sinistres": "Sinistres typés.",
    "prep.reglements": "Règlements typés, avec rang de livraison (détection des re-livraisons).",
    "prep.audits": "Audits antifraude typés.",
    "quarantine.*": "Lignes écartées du cœur, avec la règle, le motif, la référence source et la ligne brute (JSON).",
    "quarantine.raw_rejets": "Lignes illisibles à l'ingestion (nombre de champs, JSON invalide).",
    "core.dim_date": "Dimension calendrier (grain : jour, 2019-2025).",
    "core.dim_client": "Dimension client (SCD 1) : un enregistrement par client survivant.",
    "core.dim_contrat": "Dimension contrat (SCD 2 sur les attributs tarifaires) : une ligne par version de contrat.",
    "core.dim_garantie": "Dimension garantie (référentiel).",
    "core.dim_segment": "Dimension segment de risque : produit × zone × formule × canal × tranche d'âge.",
    "core.fact_exposition_mensuelle": "Fait exposition, grain contrat × mois civil.",
    "core.fact_exposition_annuelle": "Fait exposition, grain contrat × année civile.",
    "core.fact_sinistre": "Fait sinistre, grain sinistre (charge, délais, audit).",
    "core.fact_reglement": "Fait règlement, grain paiement (chargé de façon incrémentale).",
    "mart.portefeuille_mensuel": "Agrégat mensuel par produit, région, canal, zone, formule, tranche d'âge (base du dashboard).",
    "mart.kpi_segment": "Indicateurs techniques par période (année ou 2020-2025) et par axe d'analyse.",
    "mart.decomposition_sp": "Décomposition annuelle de la variation du S/P (fréquence, coût moyen, prime moyenne).",
    "mart.contribution_segments": "Contribution additive de chaque segment à la variation annuelle du S/P.",
    "mart.retention_cohorte": "Matrice de rétention par cohorte annuelle et produit.",
    "mart.client_detention": "Statut de détention (mono / multi) de chaque client.",
    "mart.retention_detention": "Rétention comparée mono / multi-détenteurs.",
    "mart.valeur_client": "Valeur observée par client et rang de Pareto.",
    "mart.delais_sinistres": "Quantiles des délais de gestion par garantie.",
    "mart.audits_criteres": "Taux d'audit et de confirmation de fraude par critère.",
    "mart.distribution_couts": "Coûts individuels des sinistres avec suite (queue de distribution).",
    "mart.exploitation_chargements": "État du dernier chargement par source.",
    "mart.exploitation_qualite": "Résultats des règles qualité de la dernière exécution.",
    "mart.exploitation_tests": "Résultats des tests bloquants de la dernière exécution.",
    "mart.exploitation_fraicheur": "Dernière date métier disponible par source.",
    "mart.exploitation_runs": "Historique des 50 dernières exécutions.",
    "meta.ingestion_log": "Journal d'ingestion : un enregistrement par fichier et par exécution.",
    "meta.runs": "Journal des exécutions du pipeline.",
    "meta.dq_rules": "Catalogue des règles qualité (requête, gravité, traitement).",
    "meta.dq_results": "Volume d'anomalies par règle et par exécution (historisé).",
    "meta.dq_anomalies": "Détail de chaque anomalie détectée (y compris signalements et corrections).",
    "meta.test_results": "Résultat de chaque test bloquant par exécution (historisé).",
}

COLS = {
    "_file_hash": "Empreinte SHA-256 du fichier source (détecte une re-livraison modifiée).",
    "_header_original": "En-tête du fichier tel que livré (trace des dérives de schéma).",
    "_loaded_at": "Horodatage du chargement en couche brute.",
    "_row_num": "Numéro de ligne dans le fichier source (en-tête = ligne 1).",
    "_run_id": "Identifiant de l'exécution qui a chargé la ligne.",
    "_source_file": "Chemin du fichier d'origine dans la zone d'atterrissage.",
    "actif_fin_mois": "1 si le contrat est couvert au dernier jour du mois.",
    "actif_fin_periode": "1 si le contrat est couvert à la fin de la dernière période observée de l'année.",
    "age_premier_contrat": "Âge révolu du client à la date d'effet de son premier contrat.",
    "annee": "Année civile.", "annee_anciennete": "Nombre d'années depuis la première souscription (anniversaire k).",
    "annee_mois": "Mois au format AAAA-MM.", "annee_naissance": "Année de naissance retenue.",
    "annee_survenance": "Année de survenance du sinistre.", "audite": "Vrai si le sinistre a fait l'objet d'un audit antifraude.",
    "avec_suite": "Vrai si le sinistre est ouvert ou clôturé (entre dans la fréquence).",
    "axe": "Axe d'analyse (produit, zone, formule, canal, tranche d'âge, région, total).",
    "bonus_malus": "Coefficient de réduction-majoration (auto).", "canal": "Canal de distribution (AGENT, COURTIER, WEB).",
    "canal_distribution": "Canal de distribution tel que livré.", "canal_principal": "Canal le plus fréquent parmi les contrats du client.",
    "cellule_complete": "Vrai si l'anniversaire k de tous les clients de la cohorte est observable au 30/06/2025.",
    "charge": "Montant payé + réserve restante (sinistres ouverts), en euros.",
    "charge_ecretee": "Charge plafonnée à 150 000 € par sinistre.", "charge_le": "Horodatage d'insertion dans le cœur.",
    "cle": "Clé métier de la ligne concernée (identifiant client, contrat, sinistre ou paiement).",
    "client_id": "Identifiant client (survivant après déduplication dans prep/core).",
    "client_id_source": "Identifiant client tel que livré dans le fichier contrats.",
    "client_id_survivant": "Identifiant conservé pour le groupe de doublons.",
    "clients_observables": "Clients dont l'anniversaire k est antérieur à l'extraction.",
    "clients_retenus": "Clients ayant au moins un contrat actif à l'anniversaire k.", "cohorte": "Année de première souscription.",
    "consent_marketing": "Consentement marketing tel que livré (0/1).", "consentement_marketing": "Consentement marketing (booléen).",
    "contenu": "Contenu brut de la ligne rejetée.", "contrat_id": "Identifiant métier du contrat.",
    "contrat_sk": "Clé de substitution de la version de contrat (SCD 2).",
    "contrats_actifs_fin_mois": "Nombre de contrats actifs le dernier jour du mois.",
    "contribution_delta_sp": "Contribution du segment à la variation annuelle du S/P brut (en points de ratio).",
    "contribution_delta_sp_ecrete": "Idem sur la charge écrêtée.", "controle_le": "Horodatage du contrôle qualité.",
    "cout_moyen": "Charge / nombre de sinistres avec suite.", "cout_moyen_ecrete": "Charge écrêtée / nombre de sinistres avec suite.",
    "critere": "Critère de ventilation des audits.", "csp": "Catégorie socioprofessionnelle.", "date": "Date calendaire.",
    "date_audit": "Date de l'audit antifraude.", "date_declaration": "Date de déclaration du sinistre.",
    "date_dernier_paiement": "Date du dernier règlement du sinistre.", "date_effet": "Date de début de couverture.",
    "date_effet_brute": "Date d'effet telle que livrée.", "date_key": "Clé entière AAAAMMJJ.",
    "date_naissance": "Date de naissance retenue (NULL si manquante, sentinelle ou invraisemblable).",
    "date_naissance_brute": "Date de naissance telle que livrée (JJ/MM/AAAA).", "date_paiement": "Date du paiement.",
    "date_paiement_key": "Clé AAAAMMJJ de la date de paiement.", "date_premier_contrat": "Date d'effet du premier contrat du client.",
    "date_premier_paiement": "Date du premier règlement du sinistre.", "date_resiliation": "Date de fin de couverture (NULL = en cours).",
    "date_resiliation_brute": "Date de résiliation telle que livrée.", "date_survenance": "Date de survenance du sinistre.",
    "date_survenance_key": "Clé AAAAMMJJ de la survenance.", "debut": "Début de l'exécution.", "debut_mois": "Premier jour du mois.",
    "decile": "Décile de valeur (1 = 10 % des clients les plus rentables).",
    "delai_cloture_j": "Jours entre déclaration et dernier règlement (sinistres clôturés, proxy de clôture).",
    "delai_declaration_j": "Jours entre survenance et déclaration (NULL si dates incohérentes).",
    "delai_premier_reglement_j": "Jours entre déclaration et premier règlement.", "delta_charge": "Variation annuelle de la charge (€).",
    "delta_sp": "Variation annuelle du S/P (points de ratio).",
    "dernier_chargement_reussi": "Horodatage du dernier chargement réussi de la source.",
    "dernier_fichier": "Dernier fichier chargé (ordre alphabétique = chronologique pour les règlements).",
    "derniere_date_metier": "Date métier la plus récente disponible.", "derniere_tentative": "Horodatage de la dernière tentative.",
    "detail": "Détail de l'anomalie (valeurs en cause).", "detention_origine": "Mono ou multi-détenteur dans les 90 jours de la 1re souscription.",
    "detention_tout_temps": "A détenu les deux produits à un moment quelconque.", "dimension": "Dimension qualité (complétude, unicité...).",
    "dn_parse": "Date de naissance analysée avant contrôles.", "duree_s": "Durée de chargement du fichier (secondes).",
    "ecarts": "Nombre d'écarts trouvés par le test (0 = succès).", "effet_cout_moyen": "Part de ΔS/P due au coût moyen (LMDI).",
    "effet_cout_sur_charge": "Part de Δcharge due au coût moyen.", "effet_frequence": "Part de ΔS/P due à la fréquence.",
    "effet_frequence_sur_charge": "Part de Δcharge due à la fréquence.", "effet_prime_moyenne": "Part de ΔS/P due à la prime moyenne.",
    "effet_volume_sur_charge": "Part de Δcharge due au volume d'exposition.", "effet_volume_sur_sp": "Effet du volume sur le S/P (nul par construction).",
    "email_hash": "Empreinte pseudonymisée de l'e-mail.", "encodage": "Encodage détecté.", "entite": "Table concernée.",
    "etape": "Étape atteinte (ou en échec).", "execute_le": "Horodatage d'exécution du test.",
    "exposition": "Années-police d'exposition.", "exposition_annees": "Durée couverte en années (jours / 365,25).",
    "famille": "Famille de garantie.", "fichier": "Fichier source.", "file_hash": "Empreinte SHA-256 du fichier.",
    "fin": "Fin de l'exécution.", "fl_age_invraisemblable": "Âge < 18 ou > 100 ans au premier contrat.",
    "fl_decl_avant_surv": "Déclaration antérieure à la survenance (Q18).", "fl_dn_format": "Date de naissance illisible.",
    "fl_dn_manquante": "Date de naissance absente.", "fl_dn_sentinelle": "Date de naissance = 01/01/1890.",
    "fl_hors_couverture": "Survenance hors période de couverture (Q19).", "formule": "Formule (ESSENTIELLE, CONFORT, PREMIUM).",
    "formule_principale": "Formule la plus fréquente parmi les contrats du client.", "franchise": "Franchise (€).",
    "fraude_confirmee": "1 si la fraude est confirmée par l'audit.", "frequence": "Sinistres avec suite / années-police.",
    "garantie": "Garantie touchée.", "gravite": "Gravité (BLOQUANT, MAJEUR, MINEUR).",
    "hash_attr": "Empreinte MD5 des attributs suivis en SCD 2.", "hors_observation": "Date postérieure à l'extraction.",
    "is_current": "Version courante du contrat.", "jour_semaine": "Jour ISO (1 = lundi).", "jours_couverts": "Jours couverts dans la période.",
    "libelle": "Libellé.", "ligne_brute": "Ligne source complète (JSON) pour réconciliation.",
    "lignes_chargees": "Lignes insérées en couche brute.", "lignes_chargees_cumul": "Cumul des lignes chargées.",
    "lignes_lues": "Lignes lues dans le fichier.", "lignes_rejetees": "Lignes illisibles rejetées.",
    "lignes_rejetees_cumul": "Cumul des lignes rejetées.", "maximum": "Valeur maximale (jours).", "mediane": "Médiane (jours).",
    "message": "Message (en-tête lu, erreur, durée).", "mesure": "brut ou écrêté.", "mis_en_quarantaine_le": "Horodatage de mise en quarantaine.",
    "modalite": "Valeur de l'axe ou du critère.", "mode": "INITIAL, SKIP, REMPLACEMENT ou RECHARGEMENT_FORCE.",
    "mois": "Premier jour du mois civil.", "mois_fichier": "Mois porté par le nom du fichier de règlements.",
    "mois_key": "Clé AAAAMMJJ du premier jour du mois.", "mois_survenance": "Mois de survenance.", "montant": "Montant du paiement (€).",
    "montant_paye": "Somme des règlements (€).", "motif": "Motif de mise en quarantaine (libellé de la règle).",
    "moyenne": "Moyenne (jours).", "n": "Effectif.", "nb_audites": "Sinistres audités.", "nb_contrats": "Nombre de contrats.",
    "nb_echecs": "Nombre de chargements en échec.", "nb_fichiers": "Nombre de fichiers.", "nb_fraudes_confirmees": "Fraudes confirmées.",
    "nb_graves": "Sinistres dont la charge dépasse 150 000 €.", "nb_identifiants_absorbes": "Doublons fusionnés dans ce client.",
    "nb_ouverts": "Sinistres ouverts.", "nb_paiements": "Nombre de règlements.", "nb_produits_origine": "Produits détenus dans les 90 premiers jours.",
    "nb_produits_total": "Produits détenus sur toute la période.", "nb_rejetes": "Sinistres rejetés.", "nb_sans_suite": "Sinistres sans suite.",
    "nb_sinistres": "Sinistres avec suite.", "nb_sinistres_declares": "Tous sinistres déclarés.", "nb_sinistres_payes": "Sinistres ayant reçu un paiement.",
    "nouvelle_souscription": "1 si le contrat a pris effet dans la période.", "num_ligne": "Numéro de ligne dans le fichier.",
    "ordre": "Ordre d'affichage.", "origine": "Date de première souscription.", "p25": "1er quartile.", "p75": "3e quartile.", "p90": "9e décile.",
    "paiement_id": "Identifiant du paiement.", "part_cumulee_clients": "Part cumulée des clients (rang / total).",
    "part_cumulee_valeur": "Part cumulée de la valeur observée.", "part_sp": "Charge du segment / primes totales.",
    "part_sp_ecrete": "Charge écrêtée du segment / primes totales.", "paye_sur_fraude_confirmee": "Montants payés sur fraudes confirmées.",
    "periode": "Année ou « 2020-2025 ».", "prime_acquise": "Prime acquise sur la période (€).", "prime_annuelle": "Prime annuelle du contrat (€).",
    "prime_moyenne": "Primes acquises / années-police.", "primes_acquises": "Primes acquises (€).", "produit": "AUTO ou HABITATION (TOUS = ensemble).",
    "produits": "Produits détenus par le client.", "puissance_cv": "Puissance fiscale (auto).", "rang": "Rang (1 = premier).",
    "rang_livraison": "Rang de livraison du paiement (1 = première livraison).", "ratio_sp": "Charge / primes acquises.",
    "ratio_sp_ecrete": "Charge écrêtée / primes acquises.", "region": "Région administrative (code).", "rejete_le": "Horodatage du rejet.",
    "requete": "Requête SQL de la règle.", "reserve_auditee": "Réserves initiales des sinistres audités.",
    "reserve_fraude_confirmee": "Réserves initiales des fraudes confirmées.", "reserve_initiale": "Réserve ouverte à la déclaration (€).",
    "reserve_restante": "Réserve initiale − payé, pour les sinistres ouverts (€).", "reserves": "Somme des réserves restantes (€).",
    "resiliation": "1 si le contrat est résilié dans la période.", "resiliations": "Nombre de résiliations.", "rule_id": "Identifiant de règle qualité.",
    "run_id": "Identifiant d'exécution.", "segment_key": "Clé du segment de risque.", "separateur": "Séparateur détecté.",
    "sinistre_id": "Identifiant du sinistre.", "sinistres_payes": "Montants payés sur les sinistres du client (€).", "source": "Source de données.",
    "souscriptions": "Nouvelles souscriptions.", "sp": "Ratio S/P.", "statut": "Statut (sinistre, test, exécution ou chargement).",
    "statut_annee": "Complétude de l'année.", "surface_m2": "Surface du logement (habitation).", "taille_cohorte": "Clients de la cohorte.",
    "taille_groupe": "Taille du groupe de doublons.", "taux": "Volume / total de la table.", "taux_audit": "Audités / sinistres.",
    "taux_confirmation_audites": "Fraudes confirmées / audités.", "taux_resiliation": "Résiliations / années-police.",
    "taux_retention": "Retenus / observables.", "test_id": "Identifiant du test.", "traitement": "EXCLURE, FUSIONNER, CORRIGER ou SIGNALER.",
    "tranche_age": "Tranche d'âge à la souscription.", "tranche_age_actuelle": "Tranche d'âge au 30/06/2025.",
    "tranche_age_souscription": "Tranche d'âge à la date d'effet.", "trimestre": "Trimestre civil.", "type_delai": "Type de délai mesuré.",
    "valeur_observee": "Primes acquises − sinistres payés (€).", "valid_from": "Début de validité de la version.",
    "valid_to": "Fin de validité (9999-12-31 = courante).", "version": "Numéro de version du contrat.", "volume": "Lignes en anomalie.",
    "volume_total": "Lignes de la table contrôlée.", "zone_max": "Zone de risque la plus élevée du client.", "zone_risque": "Zone de risque (1 à 5).",
}


def main():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.execute("""SELECT table_schema s, table_name t, column_name c, data_type d FROM information_schema.columns
        WHERE table_schema IN ('raw','prep','core','mart','quarantine','meta') ORDER BY 1,2,ordinal_position""").df()
    missing = sorted(set(df.c) - set(COLS))
    if missing:
        raise SystemExit(f"Colonnes sans définition : {missing}")
    lines = ["# Catalogue des données · Entrepôt Boréal Assurances", "",
             "Généré automatiquement depuis le schéma de l'entrepôt (`python -m docs.generer_catalogue`).", ""]
    order = ["raw", "prep", "quarantine", "core", "mart", "meta"]
    for s in order:
        lines += [f"## Couche `{s}`", ""]
        for t, g in df[df.s == s].groupby("t", sort=False):
            n = con.execute(f"SELECT COUNT(*) FROM {s}.{t}").fetchone()[0]
            desc = TABLES.get(f"{s}.{t}") or TABLES.get(f"{s}.*", "")
            lines += [f"### `{s}.{t}` · {n:,} lignes".replace(",", " "), "", desc, "", "| Colonne | Type | Définition |", "|---|---|---|"]
            lines += [f"| `{r.c}` | {r.d} | {COLS[r.c]} |" for r in g.itertuples()]
            lines.append("")
    out = Path(__file__).parent / "catalogue_donnees.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"{out} : {df.groupby(['s', 't']).ngroups} tables, {len(df)} colonnes documentées")


if __name__ == "__main__":
    main()
