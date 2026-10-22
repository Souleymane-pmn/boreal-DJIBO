# Analyse RGPD de l'entrepôt

**Données personnelles présentes.** Aucune donnée directement identifiante (ni nom, ni adresse, ni e-mail en clair). Restent des
données personnelles *pseudonymisées* au sens du RGPD (art. 4.5) : identifiant client, empreinte d'e-mail, date de naissance
complète, région, CSP, consentement marketing, et des données de comportement (sinistres, fraude confirmée). La donnée
« fraude confirmée » est sensible au regard de l'art. 10 (infractions présumées) : accès restreint au service antifraude.

**Pseudonymisation.** L'empreinte d'e-mail reste réversible par rapprochement avec le CRM (qui détient la table de
correspondance) : c'est une pseudonymisation, pas une anonymisation. Mesures : minimisation dans les marts (le dashboard
n'expose ni identifiant ni date de naissance, seulement des tranches d'âge et des agrégats) ; la date de naissance pourrait
être réduite à l'année dans le cœur ; accès par rôle (raw/prep/quarantine réservés aux data engineers).

**Durées de conservation proposées.** Contrats et sinistres : durée du contrat + prescription (5 ans en général, 10 ans pour
les dommages corporels). Couches brute et quarantaine : 13 mois glissants (le temps de réconcilier et d'auditer), puis purge.
Journaux techniques : 12 mois. Données antifraude : 5 ans après clôture du dossier (recommandation CNIL).

**Droit à l'effacement, couche par couche.**
| Couche | Traitement d'une demande pour un client X |
|---|---|
| raw | suppression des lignes du client (dans clients, puis contrats/sinistres/règlements liés) ; le fichier source est l'archive du CRM, purgé à la source |
| prep / quarantine | reconstruites depuis raw à chaque exécution → effacées au run suivant ; purge immédiate possible par `cle` |
| core | dim_client et faits reconstruits depuis prep → effacés au run suivant ; dim_contrat (SCD2 persistante) : DELETE explicite des versions du client |
| marts | agrégats recalculés ; valeur_client (individuel) recalculé ; plus de trace |
| journaux | ne contiennent aucune donnée personnelle (noms de fichiers, volumes) |
Limite : les obligations légales de conservation (lutte anti-fraude, contentieux) priment sur l'effacement tant qu'elles courent ;
on gèle alors la donnée (accès restreint) au lieu de la supprimer.
