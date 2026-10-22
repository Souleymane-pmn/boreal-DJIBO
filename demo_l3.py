"""Démonstration du livrable 3 : python demo_l3.py"""
import json
import duckdb

con = duckdb.connect("data/warehouse/boreal.duckdb", read_only=True)

print("\n=== 3.1 Indicateurs par zone de risque (2020-2025) ===")
print(con.sql("""SELECT modalite AS zone, ROUND(exposition) AS annees_police, nb_sinistres,
       ROUND(frequence*100, 2) AS freq_pct, ROUND(cout_moyen) AS cout_moyen,
       ROUND(prime_moyenne) AS prime_moy, ROUND(ratio_sp*100, 1) AS sp_pct,
       ROUND(ratio_sp_ecrete*100, 1) AS sp_plafonne_pct
FROM mart.kpi_segment WHERE axe='zone_risque' AND periode='2020-2025' ORDER BY modalite"""))

print("\n=== 3.1 Payé / réserves / sans suite par produit ===")
print(con.sql("""SELECT modalite AS produit, nb_sinistres_declares AS declares, nb_sinistres AS avec_suite,
       nb_sans_suite, nb_rejetes, ROUND(montant_paye) AS paye, ROUND(reserves) AS reserves,
       ROUND(ratio_sp*100, 1) AS sp_pct
FROM mart.kpi_segment WHERE axe='produit' AND periode='2020-2025'"""))

print("\n=== 3.2 Décomposition annuelle du S/P (en points) ===")
print(con.sql("""SELECT annee, ROUND(sp*100, 1) AS sp_pct, ROUND(delta_sp*100, 1) AS variation,
       ROUND(effet_frequence*100, 1) AS effet_freq, ROUND(effet_cout_moyen*100, 1) AS effet_cout,
       ROUND(effet_prime_moyenne*100, 1) AS effet_prime, statut_annee
FROM mart.decomposition_sp WHERE mesure='brut' ORDER BY annee"""))

print("\n=== 3.2 Le sinistre qui explique 2023 ===")
print(con.sql("""SELECT sinistre_id, garantie, annee_survenance, ROUND(charge) AS charge,
       ROUND(charge / (SELECT SUM(charge) FROM core.fact_sinistre) * 100, 1) AS part_charge_pct
FROM core.fact_sinistre ORDER BY charge DESC LIMIT 3"""))

R = json.load(open("analysis/output/results.json", encoding="utf-8"))
print("\n=== 3.3 Intervalles de confiance à 95 % ===")
for k in ["frequence", "cout_moyen", "ratio_sp", "ratio_sp_ecrete", "taux_resiliation"]:
    v = R["ic"][k]
    print(f"  {k:<18} {v['valeur']:>12.4f}   IC [{v['ic'][0]:.4f} ; {v['ic'][1]:.4f}]   ({v['methode']})")

t1, t2 = R["test_frequence_zone"], R["test_cout_canal"]
print("\n=== 3.3 Test 1 : fréquence zone 1 vs zone 5 ===")
print(f"  zone 1 : {t1['f1']*100:.2f} %   zone 5 : {t1['f5']*100:.2f} %   rapport {t1['rapport']:.2f}   p-value {t1['p_value']:.2e}")
print("\n=== 3.3 Test 2 : coût agence vs web (Mann-Whitney) ===")
print(f"  médiane agence {t2['med_agent']:.0f} €   médiane web {t2['med_web']:.0f} €   p-value {t2['p_value_mw']:.3f}")

q = R["queue"]
print("\n=== 3.3 Queue de distribution des coûts ===")
print(f"  médiane {q['mediane']:.0f} €   P90 {q['p90']:.0f} €   P99 {q['p99']:.0f} €   max {q['max']:.0f} €")
print(f"  top 1 % des sinistres = {q['part_top1']*100:.1f} % de la charge   top 10 % = {q['part_top10']*100:.1f} %")
con.close()
