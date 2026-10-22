# Catalogue des données · Entrepôt Boréal Assurances

Généré automatiquement depuis le schéma de l'entrepôt (`python -m docs.generer_catalogue`).

## Couche `raw`

### `raw.audits` · 372 lignes

Copie fidèle des sources, toutes valeurs en texte, une ligne par ligne source.

| Colonne | Type | Définition |
|---|---|---|
| `sinistre_id` | VARCHAR | Identifiant du sinistre. |
| `date_audit` | VARCHAR | Date de l'audit antifraude. |
| `fraude_confirmee` | VARCHAR | 1 si la fraude est confirmée par l'audit. |
| `_source_file` | VARCHAR | Chemin du fichier d'origine dans la zone d'atterrissage. |
| `_row_num` | INTEGER | Numéro de ligne dans le fichier source (en-tête = ligne 1). |
| `_file_hash` | VARCHAR | Empreinte SHA-256 du fichier source (détecte une re-livraison modifiée). |
| `_header_original` | VARCHAR | En-tête du fichier tel que livré (trace des dérives de schéma). |
| `_loaded_at` | TIMESTAMP | Horodatage du chargement en couche brute. |
| `_run_id` | VARCHAR | Identifiant de l'exécution qui a chargé la ligne. |

### `raw.clients` · 15 200 lignes

Copie fidèle des sources, toutes valeurs en texte, une ligne par ligne source.

| Colonne | Type | Définition |
|---|---|---|
| `client_id` | VARCHAR | Identifiant client (survivant après déduplication dans prep/core). |
| `date_naissance` | VARCHAR | Date de naissance retenue (NULL si manquante, sentinelle ou invraisemblable). |
| `region` | VARCHAR | Région administrative (code). |
| `csp` | VARCHAR | Catégorie socioprofessionnelle. |
| `consent_marketing` | VARCHAR | Consentement marketing tel que livré (0/1). |
| `email_hash` | VARCHAR | Empreinte pseudonymisée de l'e-mail. |
| `_source_file` | VARCHAR | Chemin du fichier d'origine dans la zone d'atterrissage. |
| `_row_num` | INTEGER | Numéro de ligne dans le fichier source (en-tête = ligne 1). |
| `_file_hash` | VARCHAR | Empreinte SHA-256 du fichier source (détecte une re-livraison modifiée). |
| `_header_original` | VARCHAR | En-tête du fichier tel que livré (trace des dérives de schéma). |
| `_loaded_at` | TIMESTAMP | Horodatage du chargement en couche brute. |
| `_run_id` | VARCHAR | Identifiant de l'exécution qui a chargé la ligne. |

### `raw.contrats` · 20 264 lignes

Copie fidèle des sources, toutes valeurs en texte, une ligne par ligne source.

| Colonne | Type | Définition |
|---|---|---|
| `contrat_id` | VARCHAR | Identifiant métier du contrat. |
| `client_id` | VARCHAR | Identifiant client (survivant après déduplication dans prep/core). |
| `produit` | VARCHAR | AUTO ou HABITATION (TOUS = ensemble). |
| `date_effet` | VARCHAR | Date de début de couverture. |
| `date_resiliation` | VARCHAR | Date de fin de couverture (NULL = en cours). |
| `formule` | VARCHAR | Formule (ESSENTIELLE, CONFORT, PREMIUM). |
| `canal_distribution` | VARCHAR | Canal de distribution tel que livré. |
| `zone_risque` | VARCHAR | Zone de risque (1 à 5). |
| `franchise` | VARCHAR | Franchise (€). |
| `bonus_malus` | VARCHAR | Coefficient de réduction-majoration (auto). |
| `puissance_cv` | VARCHAR | Puissance fiscale (auto). |
| `surface_m2` | VARCHAR | Surface du logement (habitation). |
| `prime_annuelle` | VARCHAR | Prime annuelle du contrat (€). |
| `_source_file` | VARCHAR | Chemin du fichier d'origine dans la zone d'atterrissage. |
| `_row_num` | INTEGER | Numéro de ligne dans le fichier source (en-tête = ligne 1). |
| `_file_hash` | VARCHAR | Empreinte SHA-256 du fichier source (détecte une re-livraison modifiée). |
| `_header_original` | VARCHAR | En-tête du fichier tel que livré (trace des dérives de schéma). |
| `_loaded_at` | TIMESTAMP | Horodatage du chargement en couche brute. |
| `_run_id` | VARCHAR | Identifiant de l'exécution qui a chargé la ligne. |

### `raw.reglements` · 3 207 lignes

Copie fidèle des sources, toutes valeurs en texte, une ligne par ligne source.

| Colonne | Type | Définition |
|---|---|---|
| `paiement_id` | VARCHAR | Identifiant du paiement. |
| `sinistre_id` | VARCHAR | Identifiant du sinistre. |
| `date_paiement` | VARCHAR | Date du paiement. |
| `montant` | VARCHAR | Montant du paiement (€). |
| `_source_file` | VARCHAR | Chemin du fichier d'origine dans la zone d'atterrissage. |
| `_row_num` | INTEGER | Numéro de ligne dans le fichier source (en-tête = ligne 1). |
| `_file_hash` | VARCHAR | Empreinte SHA-256 du fichier source (détecte une re-livraison modifiée). |
| `_header_original` | VARCHAR | En-tête du fichier tel que livré (trace des dérives de schéma). |
| `_loaded_at` | TIMESTAMP | Horodatage du chargement en couche brute. |
| `_run_id` | VARCHAR | Identifiant de l'exécution qui a chargé la ligne. |

### `raw.sinistres` · 2 805 lignes

Copie fidèle des sources, toutes valeurs en texte, une ligne par ligne source.

| Colonne | Type | Définition |
|---|---|---|
| `sinistre_id` | VARCHAR | Identifiant du sinistre. |
| `contrat_id` | VARCHAR | Identifiant métier du contrat. |
| `date_survenance` | VARCHAR | Date de survenance du sinistre. |
| `date_declaration` | VARCHAR | Date de déclaration du sinistre. |
| `garantie` | VARCHAR | Garantie touchée. |
| `statut` | VARCHAR | Statut (sinistre, test, exécution ou chargement). |
| `reserve_initiale` | VARCHAR | Réserve ouverte à la déclaration (€). |
| `_source_file` | VARCHAR | Chemin du fichier d'origine dans la zone d'atterrissage. |
| `_row_num` | INTEGER | Numéro de ligne dans le fichier source (en-tête = ligne 1). |
| `_file_hash` | VARCHAR | Empreinte SHA-256 du fichier source (détecte une re-livraison modifiée). |
| `_header_original` | VARCHAR | En-tête du fichier tel que livré (trace des dérives de schéma). |
| `_loaded_at` | TIMESTAMP | Horodatage du chargement en couche brute. |
| `_run_id` | VARCHAR | Identifiant de l'exécution qui a chargé la ligne. |

## Couche `prep`

### `prep.audits` · 372 lignes

Audits antifraude typés.

| Colonne | Type | Définition |
|---|---|---|
| `sinistre_id` | INTEGER | Identifiant du sinistre. |
| `date_audit` | DATE | Date de l'audit antifraude. |
| `fraude_confirmee` | INTEGER | 1 si la fraude est confirmée par l'audit. |
| `_source_file` | VARCHAR | Chemin du fichier d'origine dans la zone d'atterrissage. |
| `_row_num` | INTEGER | Numéro de ligne dans le fichier source (en-tête = ligne 1). |

### `prep.client_mapping` · 15 200 lignes

Table de rapprochement des doublons clients : identifiant source → identifiant survivant.

| Colonne | Type | Définition |
|---|---|---|
| `client_id` | INTEGER | Identifiant client (survivant après déduplication dans prep/core). |
| `client_id_survivant` | INTEGER | Identifiant conservé pour le groupe de doublons. |
| `rang` | BIGINT | Rang (1 = premier). |
| `taille_groupe` | BIGINT | Taille du groupe de doublons. |
| `nb_contrats` | BIGINT | Nombre de contrats. |

### `prep.clients` · 15 200 lignes

Clients typés ; date de naissance contrôlée (sentinelle et âges invraisemblables neutralisés).

| Colonne | Type | Définition |
|---|---|---|
| `client_id` | INTEGER | Identifiant client (survivant après déduplication dans prep/core). |
| `date_naissance_brute` | VARCHAR | Date de naissance telle que livrée (JJ/MM/AAAA). |
| `dn_parse` | DATE | Date de naissance analysée avant contrôles. |
| `region` | VARCHAR | Région administrative (code). |
| `csp` | VARCHAR | Catégorie socioprofessionnelle. |
| `consentement_marketing` | BOOLEAN | Consentement marketing (booléen). |
| `email_hash` | VARCHAR | Empreinte pseudonymisée de l'e-mail. |
| `_source_file` | VARCHAR | Chemin du fichier d'origine dans la zone d'atterrissage. |
| `_row_num` | INTEGER | Numéro de ligne dans le fichier source (en-tête = ligne 1). |
| `date_premier_contrat` | DATE | Date d'effet du premier contrat du client. |
| `age_premier_contrat` | BIGINT | Âge révolu du client à la date d'effet de son premier contrat. |
| `fl_dn_manquante` | BOOLEAN | Date de naissance absente. |
| `fl_dn_format` | BOOLEAN | Date de naissance illisible. |
| `fl_dn_sentinelle` | BOOLEAN | Date de naissance = 01/01/1890. |
| `fl_age_invraisemblable` | BOOLEAN | Âge < 18 ou > 100 ans au premier contrat. |
| `date_naissance` | DATE | Date de naissance retenue (NULL si manquante, sentinelle ou invraisemblable). |

### `prep.contrats` · 20 264 lignes

Contrats typés ; client rattaché au survivant de la déduplication.

| Colonne | Type | Définition |
|---|---|---|
| `contrat_id` | INTEGER | Identifiant métier du contrat. |
| `client_id_source` | INTEGER | Identifiant client tel que livré dans le fichier contrats. |
| `produit` | VARCHAR | AUTO ou HABITATION (TOUS = ensemble). |
| `date_effet` | DATE | Date de début de couverture. |
| `date_resiliation` | DATE | Date de fin de couverture (NULL = en cours). |
| `formule` | VARCHAR | Formule (ESSENTIELLE, CONFORT, PREMIUM). |
| `canal` | VARCHAR | Canal de distribution (AGENT, COURTIER, WEB). |
| `zone_risque` | INTEGER | Zone de risque (1 à 5). |
| `franchise` | INTEGER | Franchise (€). |
| `bonus_malus` | DOUBLE | Coefficient de réduction-majoration (auto). |
| `puissance_cv` | INTEGER | Puissance fiscale (auto). |
| `surface_m2` | INTEGER | Surface du logement (habitation). |
| `prime_annuelle` | DOUBLE | Prime annuelle du contrat (€). |
| `date_effet_brute` | VARCHAR | Date d'effet telle que livrée. |
| `date_resiliation_brute` | VARCHAR | Date de résiliation telle que livrée. |
| `_source_file` | VARCHAR | Chemin du fichier d'origine dans la zone d'atterrissage. |
| `_row_num` | INTEGER | Numéro de ligne dans le fichier source (en-tête = ligne 1). |
| `client_id` | INTEGER | Identifiant client (survivant après déduplication dans prep/core). |

### `prep.reglements` · 3 207 lignes

Règlements typés, avec rang de livraison (détection des re-livraisons).

| Colonne | Type | Définition |
|---|---|---|
| `paiement_id` | INTEGER | Identifiant du paiement. |
| `sinistre_id` | INTEGER | Identifiant du sinistre. |
| `date_paiement` | DATE | Date du paiement. |
| `montant` | DOUBLE | Montant du paiement (€). |
| `mois_fichier` | VARCHAR | Mois porté par le nom du fichier de règlements. |
| `rang_livraison` | BIGINT | Rang de livraison du paiement (1 = première livraison). |
| `_source_file` | VARCHAR | Chemin du fichier d'origine dans la zone d'atterrissage. |
| `_row_num` | INTEGER | Numéro de ligne dans le fichier source (en-tête = ligne 1). |
| `_header_original` | VARCHAR | En-tête du fichier tel que livré (trace des dérives de schéma). |

### `prep.sinistres` · 2 805 lignes

Sinistres typés.

| Colonne | Type | Définition |
|---|---|---|
| `sinistre_id` | INTEGER | Identifiant du sinistre. |
| `contrat_id` | INTEGER | Identifiant métier du contrat. |
| `date_survenance` | DATE | Date de survenance du sinistre. |
| `date_declaration` | DATE | Date de déclaration du sinistre. |
| `garantie` | VARCHAR | Garantie touchée. |
| `statut` | VARCHAR | Statut (sinistre, test, exécution ou chargement). |
| `reserve_initiale` | DOUBLE | Réserve ouverte à la déclaration (€). |
| `_source_file` | VARCHAR | Chemin du fichier d'origine dans la zone d'atterrissage. |
| `_row_num` | INTEGER | Numéro de ligne dans le fichier source (en-tête = ligne 1). |

## Couche `quarantine`

### `quarantine.audits` · 0 lignes

Lignes écartées du cœur, avec la règle, le motif, la référence source et la ligne brute (JSON).

| Colonne | Type | Définition |
|---|---|---|
| `cle` | VARCHAR | Clé métier de la ligne concernée (identifiant client, contrat, sinistre ou paiement). |
| `rule_id` | VARCHAR | Identifiant de règle qualité. |
| `motif` | VARCHAR | Motif de mise en quarantaine (libellé de la règle). |
| `gravite` | VARCHAR | Gravité (BLOQUANT, MAJEUR, MINEUR). |
| `detail` | VARCHAR | Détail de l'anomalie (valeurs en cause). |
| `_source_file` | VARCHAR | Chemin du fichier d'origine dans la zone d'atterrissage. |
| `_row_num` | INTEGER | Numéro de ligne dans le fichier source (en-tête = ligne 1). |
| `ligne_brute` | JSON | Ligne source complète (JSON) pour réconciliation. |
| `run_id` | VARCHAR | Identifiant d'exécution. |
| `mis_en_quarantaine_le` | TIMESTAMP | Horodatage de mise en quarantaine. |

### `quarantine.clients` · 200 lignes

Lignes écartées du cœur, avec la règle, le motif, la référence source et la ligne brute (JSON).

| Colonne | Type | Définition |
|---|---|---|
| `cle` | VARCHAR | Clé métier de la ligne concernée (identifiant client, contrat, sinistre ou paiement). |
| `rule_id` | VARCHAR | Identifiant de règle qualité. |
| `motif` | VARCHAR | Motif de mise en quarantaine (libellé de la règle). |
| `gravite` | VARCHAR | Gravité (BLOQUANT, MAJEUR, MINEUR). |
| `detail` | VARCHAR | Détail de l'anomalie (valeurs en cause). |
| `_source_file` | VARCHAR | Chemin du fichier d'origine dans la zone d'atterrissage. |
| `_row_num` | INTEGER | Numéro de ligne dans le fichier source (en-tête = ligne 1). |
| `ligne_brute` | JSON | Ligne source complète (JSON) pour réconciliation. |
| `run_id` | VARCHAR | Identifiant d'exécution. |
| `mis_en_quarantaine_le` | TIMESTAMP | Horodatage de mise en quarantaine. |

### `quarantine.contrats` · 45 lignes

Lignes écartées du cœur, avec la règle, le motif, la référence source et la ligne brute (JSON).

| Colonne | Type | Définition |
|---|---|---|
| `cle` | VARCHAR | Clé métier de la ligne concernée (identifiant client, contrat, sinistre ou paiement). |
| `rule_id` | VARCHAR | Identifiant de règle qualité. |
| `motif` | VARCHAR | Motif de mise en quarantaine (libellé de la règle). |
| `gravite` | VARCHAR | Gravité (BLOQUANT, MAJEUR, MINEUR). |
| `detail` | VARCHAR | Détail de l'anomalie (valeurs en cause). |
| `_source_file` | VARCHAR | Chemin du fichier d'origine dans la zone d'atterrissage. |
| `_row_num` | INTEGER | Numéro de ligne dans le fichier source (en-tête = ligne 1). |
| `ligne_brute` | JSON | Ligne source complète (JSON) pour réconciliation. |
| `run_id` | VARCHAR | Identifiant d'exécution. |
| `mis_en_quarantaine_le` | TIMESTAMP | Horodatage de mise en quarantaine. |

### `quarantine.raw_rejets` · 0 lignes

Lignes illisibles à l'ingestion (nombre de champs, JSON invalide).

| Colonne | Type | Définition |
|---|---|---|
| `run_id` | VARCHAR | Identifiant d'exécution. |
| `source` | VARCHAR | Source de données. |
| `fichier` | VARCHAR | Fichier source. |
| `num_ligne` | INTEGER | Numéro de ligne dans le fichier. |
| `contenu` | VARCHAR | Contenu brut de la ligne rejetée. |
| `motif` | VARCHAR | Motif de mise en quarantaine (libellé de la règle). |
| `rejete_le` | TIMESTAMP | Horodatage du rejet. |

### `quarantine.reglements` · 33 lignes

Lignes écartées du cœur, avec la règle, le motif, la référence source et la ligne brute (JSON).

| Colonne | Type | Définition |
|---|---|---|
| `cle` | VARCHAR | Clé métier de la ligne concernée (identifiant client, contrat, sinistre ou paiement). |
| `rule_id` | VARCHAR | Identifiant de règle qualité. |
| `motif` | VARCHAR | Motif de mise en quarantaine (libellé de la règle). |
| `gravite` | VARCHAR | Gravité (BLOQUANT, MAJEUR, MINEUR). |
| `detail` | VARCHAR | Détail de l'anomalie (valeurs en cause). |
| `_source_file` | VARCHAR | Chemin du fichier d'origine dans la zone d'atterrissage. |
| `_row_num` | INTEGER | Numéro de ligne dans le fichier source (en-tête = ligne 1). |
| `ligne_brute` | JSON | Ligne source complète (JSON) pour réconciliation. |
| `run_id` | VARCHAR | Identifiant d'exécution. |
| `mis_en_quarantaine_le` | TIMESTAMP | Horodatage de mise en quarantaine. |

### `quarantine.sinistres` · 5 lignes

Lignes écartées du cœur, avec la règle, le motif, la référence source et la ligne brute (JSON).

| Colonne | Type | Définition |
|---|---|---|
| `cle` | VARCHAR | Clé métier de la ligne concernée (identifiant client, contrat, sinistre ou paiement). |
| `rule_id` | VARCHAR | Identifiant de règle qualité. |
| `motif` | VARCHAR | Motif de mise en quarantaine (libellé de la règle). |
| `gravite` | VARCHAR | Gravité (BLOQUANT, MAJEUR, MINEUR). |
| `detail` | VARCHAR | Détail de l'anomalie (valeurs en cause). |
| `_source_file` | VARCHAR | Chemin du fichier d'origine dans la zone d'atterrissage. |
| `_row_num` | INTEGER | Numéro de ligne dans le fichier source (en-tête = ligne 1). |
| `ligne_brute` | JSON | Ligne source complète (JSON) pour réconciliation. |
| `run_id` | VARCHAR | Identifiant d'exécution. |
| `mis_en_quarantaine_le` | TIMESTAMP | Horodatage de mise en quarantaine. |

## Couche `core`

### `core.dim_client` · 15 000 lignes

Dimension client (SCD 1) : un enregistrement par client survivant.

| Colonne | Type | Définition |
|---|---|---|
| `client_id` | INTEGER | Identifiant client (survivant après déduplication dans prep/core). |
| `date_naissance` | DATE | Date de naissance retenue (NULL si manquante, sentinelle ou invraisemblable). |
| `annee_naissance` | BIGINT | Année de naissance retenue. |
| `region` | VARCHAR | Région administrative (code). |
| `csp` | VARCHAR | Catégorie socioprofessionnelle. |
| `consentement_marketing` | BOOLEAN | Consentement marketing (booléen). |
| `email_hash` | VARCHAR | Empreinte pseudonymisée de l'e-mail. |
| `date_premier_contrat` | DATE | Date d'effet du premier contrat du client. |
| `nb_identifiants_absorbes` | BIGINT | Doublons fusionnés dans ce client. |

### `core.dim_contrat` · 20 219 lignes

Dimension contrat (SCD 2 sur les attributs tarifaires) : une ligne par version de contrat.

| Colonne | Type | Définition |
|---|---|---|
| `contrat_sk` | BIGINT | Clé de substitution de la version de contrat (SCD 2). |
| `contrat_id` | INTEGER | Identifiant métier du contrat. |
| `version` | INTEGER | Numéro de version du contrat. |
| `client_id` | INTEGER | Identifiant client (survivant après déduplication dans prep/core). |
| `produit` | VARCHAR | AUTO ou HABITATION (TOUS = ensemble). |
| `formule` | VARCHAR | Formule (ESSENTIELLE, CONFORT, PREMIUM). |
| `canal` | VARCHAR | Canal de distribution (AGENT, COURTIER, WEB). |
| `zone_risque` | INTEGER | Zone de risque (1 à 5). |
| `franchise` | INTEGER | Franchise (€). |
| `bonus_malus` | DOUBLE | Coefficient de réduction-majoration (auto). |
| `puissance_cv` | INTEGER | Puissance fiscale (auto). |
| `surface_m2` | INTEGER | Surface du logement (habitation). |
| `prime_annuelle` | DOUBLE | Prime annuelle du contrat (€). |
| `date_effet` | DATE | Date de début de couverture. |
| `date_resiliation` | DATE | Date de fin de couverture (NULL = en cours). |
| `tranche_age_souscription` | VARCHAR | Tranche d'âge à la date d'effet. |
| `segment_key` | BIGINT | Clé du segment de risque. |
| `hash_attr` | VARCHAR | Empreinte MD5 des attributs suivis en SCD 2. |
| `valid_from` | DATE | Début de validité de la version. |
| `valid_to` | DATE | Fin de validité (9999-12-31 = courante). |
| `is_current` | BOOLEAN | Version courante du contrat. |

### `core.dim_date` · 2 557 lignes

Dimension calendrier (grain : jour, 2019-2025).

| Colonne | Type | Définition |
|---|---|---|
| `date_key` | INTEGER | Clé entière AAAAMMJJ. |
| `date` | DATE | Date calendaire. |
| `annee` | BIGINT | Année civile. |
| `trimestre` | BIGINT | Trimestre civil. |
| `mois` | BIGINT | Premier jour du mois civil. |
| `annee_mois` | VARCHAR | Mois au format AAAA-MM. |
| `debut_mois` | DATE | Premier jour du mois. |
| `jour_semaine` | BIGINT | Jour ISO (1 = lundi). |
| `hors_observation` | BOOLEAN | Date postérieure à l'extraction. |

### `core.dim_garantie` · 7 lignes

Dimension garantie (référentiel).

| Colonne | Type | Définition |
|---|---|---|
| `garantie` | VARCHAR | Garantie touchée. |
| `libelle` | VARCHAR | Libellé. |
| `produit` | VARCHAR | AUTO ou HABITATION (TOUS = ensemble). |
| `famille` | VARCHAR | Famille de garantie. |

### `core.dim_segment` · 630 lignes

Dimension segment de risque : produit × zone × formule × canal × tranche d'âge.

| Colonne | Type | Définition |
|---|---|---|
| `segment_key` | BIGINT | Clé du segment de risque. |
| `produit` | VARCHAR | AUTO ou HABITATION (TOUS = ensemble). |
| `zone_risque` | BIGINT | Zone de risque (1 à 5). |
| `formule` | VARCHAR | Formule (ESSENTIELLE, CONFORT, PREMIUM). |
| `canal` | VARCHAR | Canal de distribution (AGENT, COURTIER, WEB). |
| `tranche_age` | VARCHAR | Tranche d'âge à la souscription. |

### `core.fact_exposition_annuelle` · 65 081 lignes

Fait exposition, grain contrat × année civile.

| Colonne | Type | Définition |
|---|---|---|
| `annee` | BIGINT | Année civile. |
| `contrat_sk` | BIGINT | Clé de substitution de la version de contrat (SCD 2). |
| `contrat_id` | INTEGER | Identifiant métier du contrat. |
| `client_id` | INTEGER | Identifiant client (survivant après déduplication dans prep/core). |
| `segment_key` | BIGINT | Clé du segment de risque. |
| `jours_couverts` | HUGEINT | Jours couverts dans la période. |
| `exposition_annees` | DOUBLE | Durée couverte en années (jours / 365,25). |
| `prime_acquise` | DOUBLE | Prime acquise sur la période (€). |
| `nouvelle_souscription` | INTEGER | 1 si le contrat a pris effet dans la période. |
| `resiliation` | INTEGER | 1 si le contrat est résilié dans la période. |
| `actif_fin_periode` | INTEGER | 1 si le contrat est couvert à la fin de la dernière période observée de l'année. |

### `core.fact_exposition_mensuelle` · 555 226 lignes

Fait exposition, grain contrat × mois civil.

| Colonne | Type | Définition |
|---|---|---|
| `mois_key` | INTEGER | Clé AAAAMMJJ du premier jour du mois. |
| `mois` | DATE | Premier jour du mois civil. |
| `annee` | BIGINT | Année civile. |
| `contrat_sk` | BIGINT | Clé de substitution de la version de contrat (SCD 2). |
| `contrat_id` | INTEGER | Identifiant métier du contrat. |
| `client_id` | INTEGER | Identifiant client (survivant après déduplication dans prep/core). |
| `segment_key` | BIGINT | Clé du segment de risque. |
| `jours_couverts` | BIGINT | Jours couverts dans la période. |
| `exposition_annees` | DOUBLE | Durée couverte en années (jours / 365,25). |
| `prime_acquise` | DOUBLE | Prime acquise sur la période (€). |
| `nouvelle_souscription` | INTEGER | 1 si le contrat a pris effet dans la période. |
| `resiliation` | INTEGER | 1 si le contrat est résilié dans la période. |
| `actif_fin_mois` | INTEGER | 1 si le contrat est couvert au dernier jour du mois. |

### `core.fact_reglement` · 3 174 lignes

Fait règlement, grain paiement (chargé de façon incrémentale).

| Colonne | Type | Définition |
|---|---|---|
| `paiement_id` | INTEGER | Identifiant du paiement. |
| `sinistre_id` | INTEGER | Identifiant du sinistre. |
| `contrat_id` | INTEGER | Identifiant métier du contrat. |
| `date_paiement` | DATE | Date du paiement. |
| `date_paiement_key` | INTEGER | Clé AAAAMMJJ de la date de paiement. |
| `montant` | DOUBLE | Montant du paiement (€). |
| `_source_file` | VARCHAR | Chemin du fichier d'origine dans la zone d'atterrissage. |
| `charge_le` | TIMESTAMP | Horodatage d'insertion dans le cœur. |

### `core.fact_sinistre` · 2 800 lignes

Fait sinistre, grain sinistre (charge, délais, audit).

| Colonne | Type | Définition |
|---|---|---|
| `sinistre_id` | INTEGER | Identifiant du sinistre. |
| `contrat_id` | INTEGER | Identifiant métier du contrat. |
| `contrat_sk` | BIGINT | Clé de substitution de la version de contrat (SCD 2). |
| `client_id` | INTEGER | Identifiant client (survivant après déduplication dans prep/core). |
| `segment_key` | BIGINT | Clé du segment de risque. |
| `garantie` | VARCHAR | Garantie touchée. |
| `date_survenance_key` | INTEGER | Clé AAAAMMJJ de la survenance. |
| `date_survenance` | DATE | Date de survenance du sinistre. |
| `date_declaration` | DATE | Date de déclaration du sinistre. |
| `annee_survenance` | BIGINT | Année de survenance du sinistre. |
| `mois_survenance` | DATE | Mois de survenance. |
| `statut` | VARCHAR | Statut (sinistre, test, exécution ou chargement). |
| `avec_suite` | BOOLEAN | Vrai si le sinistre est ouvert ou clôturé (entre dans la fréquence). |
| `reserve_initiale` | DOUBLE | Réserve ouverte à la déclaration (€). |
| `montant_paye` | DOUBLE | Somme des règlements (€). |
| `nb_paiements` | BIGINT | Nombre de règlements. |
| `reserve_restante` | DOUBLE | Réserve initiale − payé, pour les sinistres ouverts (€). |
| `charge` | DOUBLE | Montant payé + réserve restante (sinistres ouverts), en euros. |
| `charge_ecretee` | DOUBLE | Charge plafonnée à 150 000 € par sinistre. |
| `date_premier_paiement` | DATE | Date du premier règlement du sinistre. |
| `date_dernier_paiement` | DATE | Date du dernier règlement du sinistre. |
| `delai_declaration_j` | BIGINT | Jours entre survenance et déclaration (NULL si dates incohérentes). |
| `delai_premier_reglement_j` | BIGINT | Jours entre déclaration et premier règlement. |
| `delai_cloture_j` | BIGINT | Jours entre déclaration et dernier règlement (sinistres clôturés, proxy de clôture). |
| `audite` | BOOLEAN | Vrai si le sinistre a fait l'objet d'un audit antifraude. |
| `date_audit` | DATE | Date de l'audit antifraude. |
| `fraude_confirmee` | INTEGER | 1 si la fraude est confirmée par l'audit. |
| `fl_decl_avant_surv` | BOOLEAN | Déclaration antérieure à la survenance (Q18). |
| `fl_hors_couverture` | BOOLEAN | Survenance hors période de couverture (Q19). |

## Couche `mart`

### `mart.audits_criteres` · 34 lignes

Taux d'audit et de confirmation de fraude par critère.

| Colonne | Type | Définition |
|---|---|---|
| `critere` | VARCHAR | Critère de ventilation des audits. |
| `modalite` | VARCHAR | Valeur de l'axe ou du critère. |
| `nb_sinistres` | BIGINT | Sinistres avec suite. |
| `nb_audites` | HUGEINT | Sinistres audités. |
| `taux_audit` | DOUBLE | Audités / sinistres. |
| `nb_fraudes_confirmees` | HUGEINT | Fraudes confirmées. |
| `taux_confirmation_audites` | DOUBLE | Fraudes confirmées / audités. |
| `reserve_auditee` | DOUBLE | Réserves initiales des sinistres audités. |
| `reserve_fraude_confirmee` | DOUBLE | Réserves initiales des fraudes confirmées. |
| `paye_sur_fraude_confirmee` | DOUBLE | Montants payés sur fraudes confirmées. |

### `mart.client_detention` · 14 977 lignes

Statut de détention (mono / multi) de chaque client.

| Colonne | Type | Définition |
|---|---|---|
| `client_id` | INTEGER | Identifiant client (survivant après déduplication dans prep/core). |
| `origine` | DATE | Date de première souscription. |
| `cohorte` | BIGINT | Année de première souscription. |
| `nb_produits_total` | BIGINT | Produits détenus sur toute la période. |
| `nb_produits_origine` | BIGINT | Produits détenus dans les 90 premiers jours. |
| `detention_origine` | VARCHAR | Mono ou multi-détenteur dans les 90 jours de la 1re souscription. |
| `detention_tout_temps` | VARCHAR | A détenu les deux produits à un moment quelconque. |

### `mart.contribution_segments` · 192 lignes

Contribution additive de chaque segment à la variation annuelle du S/P.

| Colonne | Type | Définition |
|---|---|---|
| `annee` | INTEGER | Année civile. |
| `axe` | VARCHAR | Axe d'analyse (produit, zone, formule, canal, tranche d'âge, région, total). |
| `modalite` | VARCHAR | Valeur de l'axe ou du critère. |
| `charge` | DOUBLE | Montant payé + réserve restante (sinistres ouverts), en euros. |
| `charge_ecretee` | DOUBLE | Charge plafonnée à 150 000 € par sinistre. |
| `primes_acquises` | DOUBLE | Primes acquises (€). |
| `ratio_sp` | DOUBLE | Charge / primes acquises. |
| `part_sp` | DOUBLE | Charge du segment / primes totales. |
| `part_sp_ecrete` | DOUBLE | Charge écrêtée du segment / primes totales. |
| `contribution_delta_sp` | DOUBLE | Contribution du segment à la variation annuelle du S/P brut (en points de ratio). |
| `contribution_delta_sp_ecrete` | DOUBLE | Idem sur la charge écrêtée. |

### `mart.decomposition_sp` · 12 lignes

Décomposition annuelle de la variation du S/P (fréquence, coût moyen, prime moyenne).

| Colonne | Type | Définition |
|---|---|---|
| `annee` | INTEGER | Année civile. |
| `mesure` | VARCHAR | brut ou écrêté. |
| `exposition` | DOUBLE | Années-police d'exposition. |
| `primes_acquises` | DOUBLE | Primes acquises (€). |
| `nb_sinistres` | HUGEINT | Sinistres avec suite. |
| `charge` | DOUBLE | Montant payé + réserve restante (sinistres ouverts), en euros. |
| `frequence` | DOUBLE | Sinistres avec suite / années-police. |
| `cout_moyen` | DOUBLE | Charge / nombre de sinistres avec suite. |
| `prime_moyenne` | DOUBLE | Primes acquises / années-police. |
| `sp` | DOUBLE | Ratio S/P. |
| `delta_sp` | DOUBLE | Variation annuelle du S/P (points de ratio). |
| `effet_frequence` | DOUBLE | Part de ΔS/P due à la fréquence. |
| `effet_cout_moyen` | DOUBLE | Part de ΔS/P due au coût moyen (LMDI). |
| `effet_prime_moyenne` | DOUBLE | Part de ΔS/P due à la prime moyenne. |
| `effet_volume_sur_sp` | DECIMAL(2,1) | Effet du volume sur le S/P (nul par construction). |
| `delta_charge` | DOUBLE | Variation annuelle de la charge (€). |
| `effet_volume_sur_charge` | DOUBLE | Part de Δcharge due au volume d'exposition. |
| `effet_frequence_sur_charge` | DOUBLE | Part de Δcharge due à la fréquence. |
| `effet_cout_sur_charge` | DOUBLE | Part de Δcharge due au coût moyen. |
| `statut_annee` | VARCHAR | Complétude de l'année. |

### `mart.delais_sinistres` · 24 lignes

Quantiles des délais de gestion par garantie.

| Colonne | Type | Définition |
|---|---|---|
| `garantie` | VARCHAR | Garantie touchée. |
| `type_delai` | VARCHAR | Type de délai mesuré. |
| `ordre` | INTEGER | Ordre d'affichage. |
| `n` | BIGINT | Effectif. |
| `moyenne` | DOUBLE | Moyenne (jours). |
| `p25` | DOUBLE | 1er quartile. |
| `mediane` | DOUBLE | Médiane (jours). |
| `p75` | DOUBLE | 3e quartile. |
| `p90` | DOUBLE | 9e décile. |
| `maximum` | BIGINT | Valeur maximale (jours). |

### `mart.distribution_couts` · 1 957 lignes

Coûts individuels des sinistres avec suite (queue de distribution).

| Colonne | Type | Définition |
|---|---|---|
| `produit` | VARCHAR | AUTO ou HABITATION (TOUS = ensemble). |
| `garantie` | VARCHAR | Garantie touchée. |
| `annee_survenance` | BIGINT | Année de survenance du sinistre. |
| `charge` | DOUBLE | Montant payé + réserve restante (sinistres ouverts), en euros. |
| `charge_ecretee` | DOUBLE | Charge plafonnée à 150 000 € par sinistre. |
| `statut` | VARCHAR | Statut (sinistre, test, exécution ou chargement). |
| `sinistre_id` | INTEGER | Identifiant du sinistre. |

### `mart.exploitation_chargements` · 5 lignes

État du dernier chargement par source.

| Colonne | Type | Définition |
|---|---|---|
| `source` | VARCHAR | Source de données. |
| `dernier_chargement_reussi` | TIMESTAMP | Horodatage du dernier chargement réussi de la source. |
| `derniere_tentative` | TIMESTAMP | Horodatage de la dernière tentative. |
| `nb_fichiers` | BIGINT | Nombre de fichiers. |
| `lignes_chargees_cumul` | HUGEINT | Cumul des lignes chargées. |
| `lignes_rejetees_cumul` | HUGEINT | Cumul des lignes rejetées. |
| `nb_echecs` | HUGEINT | Nombre de chargements en échec. |
| `dernier_fichier` | VARCHAR | Dernier fichier chargé (ordre alphabétique = chronologique pour les règlements). |

### `mart.exploitation_fraicheur` · 5 lignes

Dernière date métier disponible par source.

| Colonne | Type | Définition |
|---|---|---|
| `source` | VARCHAR | Source de données. |
| `derniere_date_metier` | DATE | Date métier la plus récente disponible. |

### `mart.exploitation_qualite` · 34 lignes

Résultats des règles qualité de la dernière exécution.

| Colonne | Type | Définition |
|---|---|---|
| `rule_id` | VARCHAR | Identifiant de règle qualité. |
| `entite` | VARCHAR | Table concernée. |
| `dimension` | VARCHAR | Dimension qualité (complétude, unicité...). |
| `libelle` | VARCHAR | Libellé. |
| `gravite` | VARCHAR | Gravité (BLOQUANT, MAJEUR, MINEUR). |
| `traitement` | VARCHAR | EXCLURE, FUSIONNER, CORRIGER ou SIGNALER. |
| `volume` | INTEGER | Lignes en anomalie. |
| `volume_total` | INTEGER | Lignes de la table contrôlée. |
| `taux` | DOUBLE | Volume / total de la table. |
| `statut` | VARCHAR | Statut (sinistre, test, exécution ou chargement). |
| `controle_le` | TIMESTAMP | Horodatage du contrôle qualité. |

### `mart.exploitation_runs` · 2 lignes

Historique des 50 dernières exécutions.

| Colonne | Type | Définition |
|---|---|---|
| `run_id` | VARCHAR | Identifiant d'exécution. |
| `debut` | TIMESTAMP | Début de l'exécution. |
| `fin` | TIMESTAMP | Fin de l'exécution. |
| `statut` | VARCHAR | Statut (sinistre, test, exécution ou chargement). |
| `etape` | VARCHAR | Étape atteinte (ou en échec). |
| `message` | VARCHAR | Message (en-tête lu, erreur, durée). |

### `mart.exploitation_tests` · 13 lignes

Résultats des tests bloquants de la dernière exécution.

| Colonne | Type | Définition |
|---|---|---|
| `run_id` | VARCHAR | Identifiant d'exécution. |
| `test_id` | VARCHAR | Identifiant du test. |
| `libelle` | VARCHAR | Libellé. |
| `ecarts` | BIGINT | Nombre d'écarts trouvés par le test (0 = succès). |
| `statut` | VARCHAR | Statut (sinistre, test, exécution ou chargement). |
| `execute_le` | TIMESTAMP | Horodatage d'exécution du test. |

### `mart.kpi_segment` · 231 lignes

Indicateurs techniques par période (année ou 2020-2025) et par axe d'analyse.

| Colonne | Type | Définition |
|---|---|---|
| `periode` | VARCHAR | Année ou « 2020-2025 ». |
| `axe` | VARCHAR | Axe d'analyse (produit, zone, formule, canal, tranche d'âge, région, total). |
| `modalite` | VARCHAR | Valeur de l'axe ou du critère. |
| `exposition` | DOUBLE | Années-police d'exposition. |
| `primes_acquises` | DOUBLE | Primes acquises (€). |
| `nb_sinistres` | HUGEINT | Sinistres avec suite. |
| `nb_sinistres_declares` | HUGEINT | Tous sinistres déclarés. |
| `nb_sans_suite` | HUGEINT | Sinistres sans suite. |
| `nb_rejetes` | HUGEINT | Sinistres rejetés. |
| `charge` | DOUBLE | Montant payé + réserve restante (sinistres ouverts), en euros. |
| `charge_ecretee` | DOUBLE | Charge plafonnée à 150 000 € par sinistre. |
| `montant_paye` | DOUBLE | Somme des règlements (€). |
| `reserves` | DOUBLE | Somme des réserves restantes (€). |
| `resiliations` | HUGEINT | Nombre de résiliations. |
| `nb_graves` | HUGEINT | Sinistres dont la charge dépasse 150 000 €. |
| `frequence` | DOUBLE | Sinistres avec suite / années-police. |
| `cout_moyen` | DOUBLE | Charge / nombre de sinistres avec suite. |
| `cout_moyen_ecrete` | DOUBLE | Charge écrêtée / nombre de sinistres avec suite. |
| `prime_moyenne` | DOUBLE | Primes acquises / années-police. |
| `ratio_sp` | DOUBLE | Charge / primes acquises. |
| `ratio_sp_ecrete` | DOUBLE | Charge écrêtée / primes acquises. |
| `taux_resiliation` | DOUBLE | Résiliations / années-police. |

### `mart.portefeuille_mensuel` · 256 153 lignes

Agrégat mensuel par produit, région, canal, zone, formule, tranche d'âge (base du dashboard).

| Colonne | Type | Définition |
|---|---|---|
| `mois` | DATE | Premier jour du mois civil. |
| `annee` | BIGINT | Année civile. |
| `produit` | VARCHAR | AUTO ou HABITATION (TOUS = ensemble). |
| `region` | VARCHAR | Région administrative (code). |
| `canal` | VARCHAR | Canal de distribution (AGENT, COURTIER, WEB). |
| `zone_risque` | BIGINT | Zone de risque (1 à 5). |
| `formule` | VARCHAR | Formule (ESSENTIELLE, CONFORT, PREMIUM). |
| `tranche_age` | VARCHAR | Tranche d'âge à la souscription. |
| `exposition` | DOUBLE | Années-police d'exposition. |
| `primes_acquises` | DOUBLE | Primes acquises (€). |
| `contrats_actifs_fin_mois` | HUGEINT | Nombre de contrats actifs le dernier jour du mois. |
| `resiliations` | HUGEINT | Nombre de résiliations. |
| `souscriptions` | HUGEINT | Nouvelles souscriptions. |
| `nb_sinistres_declares` | BIGINT | Tous sinistres déclarés. |
| `nb_sinistres` | HUGEINT | Sinistres avec suite. |
| `nb_sans_suite` | HUGEINT | Sinistres sans suite. |
| `nb_rejetes` | HUGEINT | Sinistres rejetés. |
| `nb_ouverts` | HUGEINT | Sinistres ouverts. |
| `charge` | DOUBLE | Montant payé + réserve restante (sinistres ouverts), en euros. |
| `charge_ecretee` | DOUBLE | Charge plafonnée à 150 000 € par sinistre. |
| `montant_paye` | DOUBLE | Somme des règlements (€). |
| `reserves` | DOUBLE | Somme des réserves restantes (€). |
| `nb_graves` | HUGEINT | Sinistres dont la charge dépasse 150 000 €. |

### `mart.retention_cohorte` · 63 lignes

Matrice de rétention par cohorte annuelle et produit.

| Colonne | Type | Définition |
|---|---|---|
| `produit` | VARCHAR | AUTO ou HABITATION (TOUS = ensemble). |
| `cohorte` | BIGINT | Année de première souscription. |
| `annee_anciennete` | BIGINT | Nombre d'années depuis la première souscription (anniversaire k). |
| `taille_cohorte` | BIGINT | Clients de la cohorte. |
| `clients_observables` | BIGINT | Clients dont l'anniversaire k est antérieur à l'extraction. |
| `clients_retenus` | HUGEINT | Clients ayant au moins un contrat actif à l'anniversaire k. |
| `taux_retention` | DOUBLE | Retenus / observables. |
| `cellule_complete` | BOOLEAN | Vrai si l'anniversaire k de tous les clients de la cohorte est observable au 30/06/2025. |

### `mart.retention_detention` · 8 lignes

Rétention comparée mono / multi-détenteurs.

| Colonne | Type | Définition |
|---|---|---|
| `detention_origine` | VARCHAR | Mono ou multi-détenteur dans les 90 jours de la 1re souscription. |
| `annee_anciennete` | BIGINT | Nombre d'années depuis la première souscription (anniversaire k). |
| `clients_observables` | BIGINT | Clients dont l'anniversaire k est antérieur à l'extraction. |
| `clients_retenus` | HUGEINT | Clients ayant au moins un contrat actif à l'anniversaire k. |
| `taux_retention` | DOUBLE | Retenus / observables. |

### `mart.valeur_client` · 14 977 lignes

Valeur observée par client et rang de Pareto.

| Colonne | Type | Définition |
|---|---|---|
| `client_id` | INTEGER | Identifiant client (survivant après déduplication dans prep/core). |
| `region` | VARCHAR | Région administrative (code). |
| `csp` | VARCHAR | Catégorie socioprofessionnelle. |
| `tranche_age_actuelle` | VARCHAR | Tranche d'âge au 30/06/2025. |
| `nb_contrats` | BIGINT | Nombre de contrats. |
| `produits` | VARCHAR | Produits détenus par le client. |
| `canal_principal` | VARCHAR | Canal le plus fréquent parmi les contrats du client. |
| `zone_max` | INTEGER | Zone de risque la plus élevée du client. |
| `formule_principale` | VARCHAR | Formule la plus fréquente parmi les contrats du client. |
| `exposition` | DOUBLE | Années-police d'exposition. |
| `primes_acquises` | DOUBLE | Primes acquises (€). |
| `sinistres_payes` | DOUBLE | Montants payés sur les sinistres du client (€). |
| `nb_sinistres_payes` | BIGINT | Sinistres ayant reçu un paiement. |
| `valeur_observee` | DOUBLE | Primes acquises − sinistres payés (€). |
| `rang` | BIGINT | Rang (1 = premier). |
| `part_cumulee_clients` | DOUBLE | Part cumulée des clients (rang / total). |
| `part_cumulee_valeur` | DOUBLE | Part cumulée de la valeur observée. |
| `decile` | BIGINT | Décile de valeur (1 = 10 % des clients les plus rentables). |

## Couche `meta`

### `meta.dq_anomalies` · 1 424 lignes

Détail de chaque anomalie détectée (y compris signalements et corrections).

| Colonne | Type | Définition |
|---|---|---|
| `run_id` | VARCHAR | Identifiant d'exécution. |
| `rule_id` | VARCHAR | Identifiant de règle qualité. |
| `entite` | VARCHAR | Table concernée. |
| `cle` | VARCHAR | Clé métier de la ligne concernée (identifiant client, contrat, sinistre ou paiement). |
| `_source_file` | VARCHAR | Chemin du fichier d'origine dans la zone d'atterrissage. |
| `_row_num` | INTEGER | Numéro de ligne dans le fichier source (en-tête = ligne 1). |
| `detail` | VARCHAR | Détail de l'anomalie (valeurs en cause). |
| `traitement` | VARCHAR | EXCLURE, FUSIONNER, CORRIGER ou SIGNALER. |

### `meta.dq_results` · 68 lignes

Volume d'anomalies par règle et par exécution (historisé).

| Colonne | Type | Définition |
|---|---|---|
| `run_id` | VARCHAR | Identifiant d'exécution. |
| `rule_id` | VARCHAR | Identifiant de règle qualité. |
| `entite` | VARCHAR | Table concernée. |
| `volume` | INTEGER | Lignes en anomalie. |
| `volume_total` | INTEGER | Lignes de la table contrôlée. |
| `taux` | DOUBLE | Volume / total de la table. |
| `gravite` | VARCHAR | Gravité (BLOQUANT, MAJEUR, MINEUR). |
| `traitement` | VARCHAR | EXCLURE, FUSIONNER, CORRIGER ou SIGNALER. |
| `statut` | VARCHAR | Statut (sinistre, test, exécution ou chargement). |
| `controle_le` | TIMESTAMP | Horodatage du contrôle qualité. |

### `meta.dq_rules` · 34 lignes

Catalogue des règles qualité (requête, gravité, traitement).

| Colonne | Type | Définition |
|---|---|---|
| `rule_id` | VARCHAR | Identifiant de règle qualité. |
| `entite` | VARCHAR | Table concernée. |
| `dimension` | VARCHAR | Dimension qualité (complétude, unicité...). |
| `libelle` | VARCHAR | Libellé. |
| `gravite` | VARCHAR | Gravité (BLOQUANT, MAJEUR, MINEUR). |
| `traitement` | VARCHAR | EXCLURE, FUSIONNER, CORRIGER ou SIGNALER. |
| `requete` | VARCHAR | Requête SQL de la règle. |

### `meta.ingestion_log` · 136 lignes

Journal d'ingestion : un enregistrement par fichier et par exécution.

| Colonne | Type | Définition |
|---|---|---|
| `run_id` | VARCHAR | Identifiant d'exécution. |
| `source` | VARCHAR | Source de données. |
| `fichier` | VARCHAR | Fichier source. |
| `file_hash` | VARCHAR | Empreinte SHA-256 du fichier. |
| `encodage` | VARCHAR | Encodage détecté. |
| `separateur` | VARCHAR | Séparateur détecté. |
| `lignes_lues` | INTEGER | Lignes lues dans le fichier. |
| `lignes_rejetees` | INTEGER | Lignes illisibles rejetées. |
| `lignes_chargees` | INTEGER | Lignes insérées en couche brute. |
| `duree_s` | DOUBLE | Durée de chargement du fichier (secondes). |
| `statut` | VARCHAR | Statut (sinistre, test, exécution ou chargement). |
| `mode` | VARCHAR | INITIAL, SKIP, REMPLACEMENT ou RECHARGEMENT_FORCE. |
| `message` | VARCHAR | Message (en-tête lu, erreur, durée). |
| `charge_le` | TIMESTAMP | Horodatage d'insertion dans le cœur. |

### `meta.runs` · 2 lignes

Journal des exécutions du pipeline.

| Colonne | Type | Définition |
|---|---|---|
| `run_id` | VARCHAR | Identifiant d'exécution. |
| `debut` | TIMESTAMP | Début de l'exécution. |
| `fin` | TIMESTAMP | Fin de l'exécution. |
| `statut` | VARCHAR | Statut (sinistre, test, exécution ou chargement). |
| `etape` | VARCHAR | Étape atteinte (ou en échec). |
| `message` | VARCHAR | Message (en-tête lu, erreur, durée). |

### `meta.test_results` · 26 lignes

Résultat de chaque test bloquant par exécution (historisé).

| Colonne | Type | Définition |
|---|---|---|
| `run_id` | VARCHAR | Identifiant d'exécution. |
| `test_id` | VARCHAR | Identifiant du test. |
| `libelle` | VARCHAR | Libellé. |
| `ecarts` | BIGINT | Nombre d'écarts trouvés par le test (0 = succès). |
| `statut` | VARCHAR | Statut (sinistre, test, exécution ou chargement). |
| `execute_le` | TIMESTAMP | Horodatage d'exécution du test. |
