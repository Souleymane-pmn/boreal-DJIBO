# Lignage d'un indicateur : le ratio S/P (de la source au graphique)

```
contrats/contrats.csv ──► raw.contrats ──► prep.contrats ──[Q09,Q11 : 45 contrats en quarantaine]──► core.dim_contrat (version courante)
                                                                                                      │
                                                  exposition jour par jour, découpée par mois ◄───────┘
                                                                     ▼
                                               core.fact_exposition_mensuelle.prime_acquise  (= prime_annuelle × jours/365,25)
                                                                     │  DÉNOMINATEUR
sinistres/sinistres.jsonl ──► raw.sinistres ──► prep.sinistres ──[Q17 : 5 en quarantaine]──► core.fact_sinistre
reglements/*.csv (64) ──► raw.reglements ──► prep.reglements ──[Q23 doublons 32, Q24 1]──► core.fact_reglement ─┘
                                                     fact_sinistre.charge = Σ règlements + réserve restante (ouverts)
                                                                     │  NUMÉRATEUR
                                                                     ▼
                         mart.portefeuille_mensuel (charge, primes_acquises par mois × segment)
                                                                     ▼
                         mart.kpi_segment.ratio_sp = Σ charge / Σ primes_acquises    ← test T12 (égal au recalcul depuis core)
                                                                     ▼
                Dashboard page Portefeuille : métrique « Ratio S/P » + courbe S/P glissant 12 mois + alerte > 70 %
                Dossier : analysis/output/results.json → kpi["total|Ensemble"]["ratio_sp"] = 58,8 %
```
Tests de contrôle sur ce chemin : T05 (règlements brut = cœur + quarantaine), T09 (cœur = marts), T10, T12.
