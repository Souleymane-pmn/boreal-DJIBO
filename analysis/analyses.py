"""Livrables 3 et 4 · Analyses (toutes les valeurs sont lues dans l'entrepôt DuckDB).

Produit, dans analysis/output/ :
  - results.json : chaque chiffre cité dans le dossier et la note (avec la requête source) ;
  - tables CSV ; figures PNG.
Usage : python -m analysis.analyses
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import matplotlib
import numpy as np
import pandas as pd
from scipy import stats

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from pipeline.config import DB_PATH, SEUIL_GRAVE  # noqa: E402

OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(exist_ok=True)
RNG = np.random.default_rng(2025)
B = 2000  # réplications bootstrap
COL = {"main": "#1F4E79", "acc": "#C55A11", "grey": "#7F7F7F", "ok": "#2E7D32", "bad": "#C62828"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.dpi": 150})

R: dict = {}  # résultats exportés
SQL: dict = {}  # requête de chaque résultat


def q(con, sql, key=None):
    df = con.execute(sql).df()
    if key:
        SQL[key] = " ".join(sql.split())
    return df


def poisson_ci(n, expo, a=0.05):
    lo = stats.chi2.ppf(a / 2, 2 * n) / 2 / expo if n > 0 else 0.0
    hi = stats.chi2.ppf(1 - a / 2, 2 * (n + 1)) / 2 / expo
    return lo, hi


def savefig(name):
    plt.tight_layout()
    plt.savefig(OUT / f"{name}.png", bbox_inches="tight")
    plt.close()


# =====================================================================
# L1/L2 : chiffres de la chaîne (pour le dossier)
# =====================================================================
def chaine(con):
    R["ingestion"] = q(con, """SELECT source, COUNT(DISTINCT fichier) fichiers, SUM(lignes_chargees) lignes,
        SUM(lignes_rejetees) rejets, STRING_AGG(DISTINCT encodage, '/') encodages, STRING_AGG(DISTINCT separateur, '/') separateurs
        FROM meta.ingestion_log WHERE mode IN ('INITIAL') GROUP BY 1 ORDER BY 1""", "ingestion").to_dict("records")
    R["qualite"] = q(con, "SELECT * EXCLUDE (controle_le) FROM mart.exploitation_qualite ORDER BY rule_id", "qualite").to_dict("records")
    R["tests"] = q(con, "SELECT test_id, libelle, ecarts, statut FROM mart.exploitation_tests ORDER BY test_id", "tests").to_dict("records")
    R["volumes"] = {
        t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ["raw.clients", "raw.contrats", "raw.sinistres", "raw.reglements", "raw.audits",
                  "core.dim_client", "core.dim_contrat", "core.fact_sinistre", "core.fact_reglement",
                  "core.fact_exposition_mensuelle", "core.fact_exposition_annuelle", "core.dim_segment",
                  "quarantine.clients", "quarantine.contrats", "quarantine.sinistres", "quarantine.reglements"]}
    rec = q(con, """SELECT (SELECT SUM(CAST(montant AS DECIMAL(18,2))) FROM raw.reglements) brut,
        (SELECT SUM(CAST(montant AS DECIMAL(18,2))) FROM core.fact_reglement) coeur,
        (SELECT SUM(CAST(b.montant AS DECIMAL(18,2))) FROM raw.reglements b WHERE (b._source_file,b._row_num) IN
           (SELECT _source_file,_row_num FROM quarantine.reglements WHERE rule_id='Q23')) doublons,
        (SELECT SUM(CAST(b.montant AS DECIMAL(18,2))) FROM raw.reglements b WHERE (b._source_file,b._row_num) IN
           (SELECT _source_file,_row_num FROM quarantine.reglements WHERE rule_id='Q24')) en_cascade""", "reconciliation")
    R["reconciliation"] = {k: float(v) for k, v in rec.iloc[0].items()}
    dd = q(con, """SELECT COUNT(*) n, SUM(taille_groupe>1 AND rang=1) survivants FROM prep.client_mapping""", "dedup").iloc[0]
    R["dedup"] = {"clients_source": int(dd.n), "doublons": int(con.execute("SELECT COUNT(*) FROM prep.client_mapping WHERE rang>1").fetchone()[0]),
                  "taux": float(con.execute("SELECT AVG((rang>1)::INT) FROM prep.client_mapping").fetchone()[0]),
                  "contrats_rattaches": int(con.execute("SELECT COUNT(*) FROM prep.contrats WHERE client_id<>client_id_source").fetchone()[0]),
                  "groupes_avec_contrats_des_deux_cotes": int(con.execute(
                      "SELECT COUNT(*) FROM (SELECT client_id_survivant FROM prep.client_mapping WHERE taille_groupe>1 "
                      "GROUP BY 1 HAVING SUM((nb_contrats>0)::INT)>1)").fetchone()[0])}


# =====================================================================
# L3.1 Indicateurs techniques par axe
# =====================================================================
def indicateurs(con):
    k = q(con, """SELECT axe, modalite, exposition, primes_acquises, nb_sinistres_declares, nb_sinistres, nb_sans_suite,
        nb_rejetes, montant_paye, reserves, charge, charge_ecretee, frequence, cout_moyen, cout_moyen_ecrete, prime_moyenne,
        ratio_sp, ratio_sp_ecrete, taux_resiliation, resiliations, nb_graves
        FROM mart.kpi_segment WHERE periode='2020-2025' ORDER BY axe, modalite""", "kpi_2020_2025")
    k.to_csv(OUT / "kpi_par_axe_2020_2025.csv", index=False)
    R["kpi"] = {f"{r.axe}|{r.modalite}": {c: (float(r[c]) if pd.notna(r[c]) else None) for c in k.columns[2:]}
                for _, r in k.iterrows()}
    an = q(con, "SELECT * FROM mart.kpi_segment WHERE axe='total' AND periode<>'2020-2025' ORDER BY periode", "kpi_annuel")
    an.to_csv(OUT / "kpi_annuel.csv", index=False)
    R["kpi_annuel"] = an[["periode", "exposition", "primes_acquises", "nb_sinistres", "charge", "charge_ecretee", "montant_paye",
                          "reserves", "frequence", "cout_moyen", "prime_moyenne", "ratio_sp", "ratio_sp_ecrete",
                          "taux_resiliation", "nb_graves", "nb_sans_suite", "nb_rejetes"]].to_dict("records")
    # Le sinistre le plus lourd
    g = q(con, f"""SELECT f.sinistre_id, f.garantie, f.annee_survenance, f.charge, f.reserve_initiale, f.nb_paiements, c.region,
                   s.zone_risque, s.canal, s.tranche_age FROM core.fact_sinistre f JOIN core.dim_segment s USING (segment_key)
                   JOIN core.dim_client c USING (client_id) WHERE f.charge > {SEUIL_GRAVE} ORDER BY f.charge DESC""", "graves")
    R["graves"] = g.to_dict("records")
    R["charge_totale"] = float(con.execute("SELECT SUM(charge) FROM core.fact_sinistre").fetchone()[0])

    # Figure : S/P par axe (brut vs écrêté)
    fig, axes = plt.subplots(2, 3, figsize=(10, 5.6))
    for ax, axe in zip(axes.flat, ["produit", "zone_risque", "formule", "canal", "tranche_age", "region"]):
        d = k[k.axe == axe].sort_values("modalite")
        x = np.arange(len(d))
        ax.bar(x - 0.2, d.ratio_sp * 100, 0.4, color=COL["main"], label="S/P brut")
        ax.bar(x + 0.2, d.ratio_sp_ecrete * 100, 0.4, color=COL["acc"], label=f"S/P écrêté à {SEUIL_GRAVE // 1000} k€")
        ax.axhline(70, color=COL["bad"], lw=0.8, ls="--")
        ax.set_xticks(x, d.modalite, rotation=45 if axe == "region" else 0, fontsize=7)
        ax.set_title(axe.replace("_", " ").capitalize(), fontsize=9)
        ax.set_ylabel("%")
    axes.flat[0].legend(fontsize=7)
    savefig("fig_sp_par_axe")


# =====================================================================
# L3.2 Décomposition
# =====================================================================
def decomposition(con):
    d = q(con, "SELECT * FROM mart.decomposition_sp ORDER BY mesure, annee", "decomposition")
    d.to_csv(OUT / "decomposition_sp.csv", index=False)
    R["decomposition"] = d.replace({np.nan: None}).to_dict("records")
    c = q(con, """SELECT annee, axe, modalite, ratio_sp, contribution_delta_sp, contribution_delta_sp_ecrete
                  FROM mart.contribution_segments WHERE annee >= 2021""", "contributions")
    c.to_csv(OUT / "contributions_segments.csv", index=False)
    top = {}
    for an in [2022, 2023, 2024]:
        for axe in ["zone_risque", "produit", "canal", "formule", "region", "tranche_age"]:
            s = c[(c.annee == an) & (c.axe == axe)].sort_values("contribution_delta_sp")
            top[f"{an}|{axe}"] = {"amelioration": s.head(2)[["modalite", "contribution_delta_sp"]].values.tolist(),
                                  "degradation": s.tail(2)[["modalite", "contribution_delta_sp"]].values.tolist()[::-1],
                                  "degradation_ecrete": s.sort_values("contribution_delta_sp_ecrete").tail(2)[
                                      ["modalite", "contribution_delta_sp_ecrete"]].values.tolist()[::-1]}
    R["contrib_top"] = top
    # Figure : cascade
    b = d[(d.mesure == "brut") & d.delta_sp.notna()]
    e = d[(d.mesure == "ecrete") & d.delta_sp.notna()]
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
    for ax, dd, t in [(axs[0], b, "S/P brut"), (axs[1], e, f"S/P écrêté ({SEUIL_GRAVE // 1000} k€)")]:
        x = np.arange(len(dd))
        ax.bar(x - 0.25, dd.effet_frequence * 100, 0.25, color=COL["main"], label="Effet fréquence")
        ax.bar(x, dd.effet_cout_moyen * 100, 0.25, color=COL["acc"], label="Effet coût moyen")
        ax.bar(x + 0.25, dd.effet_prime_moyenne * 100, 0.25, color=COL["grey"], label="Effet prime moyenne")
        ax.plot(x, dd.delta_sp * 100, "kD", ms=5, label="Variation totale du S/P")
        ax.axhline(0, color="k", lw=0.6)
        ax.set_xticks(x, [f"{a - 1}→{a}" for a in dd.annee])
        ax.set_title(t)
        ax.set_ylabel("points de S/P")
    axs[0].legend(fontsize=7)
    savefig("fig_decomposition")


# =====================================================================
# L3.3 Incertitude, tests, queue de distribution
# =====================================================================
def statistiques(con):
    ctr = q(con, """WITH e AS (SELECT contrat_id, SUM(exposition_annees) expo, SUM(prime_acquise) prime, SUM(resiliation) resil
                               FROM core.fact_exposition_mensuelle GROUP BY 1),
                    s AS (SELECT contrat_id, SUM(avec_suite::INT) n, SUM(charge) ch, SUM(charge_ecretee) che
                          FROM core.fact_sinistre GROUP BY 1)
                    SELECT e.*, COALESCE(s.n,0) n, COALESCE(s.ch,0) ch, COALESCE(s.che,0) che,
                           k.produit, k.zone_risque, k.canal
                    FROM e JOIN core.dim_contrat k ON k.contrat_id=e.contrat_id AND k.is_current
                    LEFT JOIN s ON s.contrat_id=e.contrat_id""", "base_bootstrap")
    claims = q(con, """SELECT f.charge, f.charge_ecretee, s.canal, s.zone_risque, s.produit, f.garantie
                       FROM core.fact_sinistre f JOIN core.dim_segment s USING (segment_key) WHERE f.avec_suite""", "base_couts")
    # Bootstrap de Poisson par contrat (préserve la corrélation sinistres/primes d'un même contrat)
    W = RNG.poisson(1.0, size=(B, len(ctr)))
    expo, prime, n, ch, che, resil = (ctr[c].to_numpy() for c in ["expo", "prime", "n", "ch", "che", "resil"])

    def bt(num, den):
        v = (W @ num) / (W @ den)
        return float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))

    ic = {}
    N, E = n.sum(), expo.sum()
    ic["frequence"] = {"valeur": N / E, "ic": poisson_ci(N, E), "methode": "Poisson exact (Garwood)"}
    ic["cout_moyen"] = {"valeur": ch.sum() / N, "ic": bt(ch, n), "methode": "bootstrap par contrat (B=2000)"}
    ic["cout_moyen_ecrete"] = {"valeur": che.sum() / N, "ic": bt(che, n), "methode": "bootstrap par contrat"}
    ic["prime_moyenne"] = {"valeur": prime.sum() / E, "ic": bt(prime, expo), "methode": "bootstrap par contrat"}
    ic["ratio_sp"] = {"valeur": ch.sum() / prime.sum(), "ic": bt(ch, prime), "methode": "bootstrap par contrat"}
    ic["ratio_sp_ecrete"] = {"valeur": che.sum() / prime.sum(), "ic": bt(che, prime), "methode": "bootstrap par contrat"}
    ic["taux_resiliation"] = {"valeur": resil.sum() / E, "ic": poisson_ci(resil.sum(), E), "methode": "Poisson exact"}
    # par produit
    for p in ["AUTO", "HABITATION"]:
        m = (ctr.produit == p).to_numpy()
        Wm = W[:, m]
        ic[f"ratio_sp_ecrete|{p}"] = {"valeur": che[m].sum() / prime[m].sum(),
                                     "ic": (float(np.percentile((Wm @ che[m]) / (Wm @ prime[m]), 2.5)),
                                            float(np.percentile((Wm @ che[m]) / (Wm @ prime[m]), 97.5))),
                                     "methode": "bootstrap par contrat"}
        ic[f"frequence|{p}"] = {"valeur": n[m].sum() / expo[m].sum(), "ic": poisson_ci(n[m].sum(), expo[m].sum()),
                                "methode": "Poisson exact"}
    R["ic"] = ic

    # Test 1 : fréquence zone 1 vs zone 5 (test exact conditionnel de deux taux de Poisson)
    z = ctr.groupby("zone_risque").agg(n=("n", "sum"), e=("expo", "sum"))
    n1, e1, n5, e5 = z.loc[1, "n"], z.loc[1, "e"], z.loc[5, "n"], z.loc[5, "e"]
    bt1 = stats.binomtest(int(n5), int(n1 + n5), e5 / (e1 + e5))
    rr = (n5 / e5) / (n1 / e1)
    se = np.sqrt(1 / n5 + 1 / n1)
    R["test_frequence_zone"] = {"n1": int(n1), "e1": float(e1), "n5": int(n5), "e5": float(e5),
                                "f1": n1 / e1, "f5": n5 / e5, "rapport": rr,
                                "rapport_ic": (rr * np.exp(-1.96 * se), rr * np.exp(1.96 * se)), "p_value": bt1.pvalue,
                                "test": "test exact conditionnel (binomial) de comparaison de deux taux de Poisson"}
    # Tendance de fréquence sur les 5 zones (régression de Poisson sur données agrégées, offset = exposition)
    zz = z.reset_index()
    import statsmodels.api as sm  # noqa: WPS433
    X = sm.add_constant(zz.zone_risque.astype(float))
    pm = sm.GLM(zz.n, X, family=sm.families.Poisson(), offset=np.log(zz.e)).fit()
    R["tendance_zone"] = {"hausse_par_zone": float(np.exp(pm.params.iloc[1]) - 1), "p_value": float(pm.pvalues.iloc[1])}

    # Test 2 : coût AGENT vs WEB (Mann-Whitney, distributions très asymétriques)
    a = claims[claims.canal == "AGENT"].charge.to_numpy()
    w = claims[claims.canal == "WEB"].charge.to_numpy()
    mw = stats.mannwhitneyu(a, w, alternative="two-sided")
    diff = [RNG.choice(a, len(a)).mean() - RNG.choice(w, len(w)).mean() for _ in range(B)]
    ae = claims[claims.canal == "AGENT"].charge_ecretee.to_numpy()
    we = claims[claims.canal == "WEB"].charge_ecretee.to_numpy()
    R["test_cout_canal"] = {"n_agent": len(a), "n_web": len(w), "moy_agent": a.mean(), "moy_web": w.mean(),
                            "med_agent": float(np.median(a)), "med_web": float(np.median(w)),
                            "moy_agent_ecrete": ae.mean(), "moy_web_ecrete": we.mean(),
                            "p_value_mw": mw.pvalue, "diff_moy_ic": (float(np.percentile(diff, 2.5)), float(np.percentile(diff, 97.5))),
                            "test": "Mann-Whitney bilatéral (pas d'hypothèse de normalité)"}
    # Test 3 (complément) : résiliation WEB vs AGENT
    c3 = ctr.groupby("canal").agg(r=("resil", "sum"), e=("expo", "sum"))
    bt3 = stats.binomtest(int(c3.loc["WEB", "r"]), int(c3.loc["WEB", "r"] + c3.loc["AGENT", "r"]),
                          c3.loc["WEB", "e"] / (c3.loc["WEB", "e"] + c3.loc["AGENT", "e"]))
    R["test_resiliation_canal"] = {"t_web": c3.loc["WEB", "r"] / c3.loc["WEB", "e"],
                                   "t_agent": c3.loc["AGENT", "r"] / c3.loc["AGENT", "e"], "p_value": bt3.pvalue,
                                   "ic_web": poisson_ci(c3.loc["WEB", "r"], c3.loc["WEB", "e"]),
                                   "ic_agent": poisson_ci(c3.loc["AGENT", "r"], c3.loc["AGENT", "e"])}

    # Queue de distribution
    x = np.sort(claims.charge.to_numpy())[::-1]
    tot = x.sum()
    R["queue"] = {"n": len(x), "moyenne": x.mean(), "mediane": float(np.median(x)),
                  "p75": float(np.percentile(x, 75)), "p90": float(np.percentile(x, 90)),
                  "p95": float(np.percentile(x, 95)), "p99": float(np.percentile(x, 99)), "max": float(x[0]),
                  "part_top1": x[: max(1, int(round(0.01 * len(x))))].sum() / tot,
                  "part_top5": x[: int(round(0.05 * len(x)))].sum() / tot,
                  "part_top10": x[: int(round(0.10 * len(x)))].sum() / tot,
                  "part_max": x[0] / tot, "nb_sup_seuil": int((x > SEUIL_GRAVE).sum())}
    R["queue_garantie"] = claims.groupby("garantie").charge.describe(percentiles=[.5, .9, .99]).round(0).reset_index().to_dict("records")
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.4))
    axs[0].hist(np.log10(x), bins=40, color=COL["main"])
    for p, lab in [(50, "médiane"), (90, "P90"), (99, "P99")]:
        v = np.percentile(x, p)
        axs[0].axvline(np.log10(v), color=COL["acc"], ls="--", lw=0.8)
        axs[0].text(np.log10(v), axs[0].get_ylim()[1] * 0.9, f" {lab}\n {v:,.0f} €".replace(",", " "), fontsize=7)
    axs[0].set_xlabel("Coût du sinistre (échelle log10, €)")
    axs[0].set_ylabel("Nombre de sinistres")
    axs[0].set_title("Distribution des coûts (sinistres avec suite)")
    cs = np.cumsum(x) / tot
    axs[1].plot(np.arange(1, len(x) + 1) / len(x) * 100, cs * 100, color=COL["main"])
    axs[1].plot([0, 100], [0, 100], color=COL["grey"], ls=":")
    axs[1].set_xlabel("% des sinistres (du plus cher au moins cher)")
    axs[1].set_ylabel("% de la charge cumulée")
    axs[1].set_title("Concentration de la charge")
    savefig("fig_queue_couts")


# =====================================================================
# L4 Clients et sinistres
# =====================================================================
def clients(con):
    ret = q(con, "SELECT * FROM mart.retention_cohorte ORDER BY produit, cohorte, annee_anciennete", "retention")
    ret.to_csv(OUT / "retention_cohortes.csv", index=False)
    R["retention"] = ret.to_dict("records")
    det = q(con, "SELECT * FROM mart.retention_detention ORDER BY 1, 2", "retention_detention")
    R["retention_detention"] = det.to_dict("records")
    R["detention"] = q(con, """SELECT COUNT(*) n, AVG((detention_origine='Multi-détenteur')::INT) part_origine,
        AVG((detention_tout_temps='Auto + habitation')::INT) part_tout_temps FROM mart.client_detention""", "detention").iloc[0].to_dict()
    # Rétention à 1 an mono vs multi : test de proportions
    d1 = det[det.annee_anciennete == 1].set_index("detention_origine")
    tab = np.array([[d1.loc["Multi-détenteur", "clients_retenus"], d1.loc["Multi-détenteur", "clients_observables"] - d1.loc["Multi-détenteur", "clients_retenus"]],
                    [d1.loc["Mono-détenteur", "clients_retenus"], d1.loc["Mono-détenteur", "clients_observables"] - d1.loc["Mono-détenteur", "clients_retenus"]]])
    R["test_retention_detention"] = {"p_value": float(stats.chi2_contingency(tab)[1])}

    fig, axs = plt.subplots(1, 3, figsize=(11, 3.3))
    for ax, p in zip(axs, ["TOUS", "AUTO", "HABITATION"]):
        m = ret[(ret.produit == p) & ret.cellule_complete].pivot(index="cohorte", columns="annee_anciennete", values="taux_retention")
        im = ax.imshow(m.values * 100, cmap="Blues", vmin=50, vmax=100, aspect="auto")
        for i in range(m.shape[0]):
            for j in range(m.shape[1]):
                if pd.notna(m.values[i, j]):
                    ax.text(j, i, f"{m.values[i, j] * 100:.0f}", ha="center", va="center", fontsize=7,
                            color="white" if m.values[i, j] > 0.85 else "black")
        ax.set_xticks(range(m.shape[1]), [f"an {c}" for c in m.columns])
        ax.set_yticks(range(m.shape[0]), m.index)
        ax.set_title(f"Rétention (%) — {p.lower()}")
    savefig("fig_retention")

    v = q(con, "SELECT * FROM mart.valeur_client ORDER BY rang", "valeur_client")
    tot = v.valeur_observee.sum()
    pos = v[v.valeur_observee > 0].valeur_observee.sum()
    n = len(v)
    R["valeur"] = {"n_clients": n, "valeur_totale": tot, "primes": v.primes_acquises.sum(), "payes": v.sinistres_payes.sum(),
                   "part_negatifs": float((v.valeur_observee < 0).mean()), "nb_negatifs": int((v.valeur_observee < 0).sum()),
                   "perte_negatifs": float(v[v.valeur_observee < 0].valeur_observee.sum()),
                   "part_top20_valeur_positive": float(v.head(int(0.2 * n)).valeur_observee.sum() / pos),
                   "part_valeur_top20": float(v.head(int(0.2 * n)).valeur_observee.sum() / tot),
                   "pire_client": float(v.valeur_observee.min()), "part_sans_sinistre": float((v.sinistres_payes == 0).mean()),
                   "part_clients_creant_100pct": float((v.part_cumulee_valeur.idxmax() + 1) / n)}
    prof = v.assign(groupe=np.where(v.decile == 1, "Top 10 %", np.where(v.decile == 10, "Bottom 10 %", "Autres"))).groupby("groupe").agg(
        n=("client_id", "count"), valeur_moy=("valeur_observee", "mean"), primes_moy=("primes_acquises", "mean"),
        payes_moy=("sinistres_payes", "mean"), expo_moy=("exposition", "mean"), nb_contrats=("nb_contrats", "mean"),
        part_multi=("produits", lambda s: (s == "AUTO+HABITATION").mean()), zone_moy=("zone_max", "mean"),
        part_premium=("formule_principale", lambda s: (s == "PREMIUM").mean()),
        part_web=("canal_principal", lambda s: (s == "WEB").mean()),
        part_sinistre=("nb_sinistres_payes", lambda s: (s > 0).mean()))
    prof.to_csv(OUT / "profils_valeur.csv")
    R["profils_valeur"] = prof.reset_index().to_dict("records")
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    ax.plot(v.part_cumulee_clients * 100, v.part_cumulee_valeur * 100, color=COL["main"])
    ax.axhline(100, color=COL["grey"], ls=":")
    ax.axvline(20, color=COL["acc"], ls="--", lw=0.8)
    ax.set_xlabel("% des clients (du plus au moins rentable)")
    ax.set_ylabel("% de la valeur observée totale")
    ax.set_title("Courbe de Pareto de la valeur observée (primes acquises − sinistres payés)")
    savefig("fig_pareto")


def sinistres(con):
    d = q(con, "SELECT * FROM mart.delais_sinistres ORDER BY ordre, garantie", "delais")
    d.to_csv(OUT / "delais.csv", index=False)
    R["delais"] = d.to_dict("records")
    a = q(con, "SELECT * FROM mart.audits_criteres ORDER BY critere, modalite", "audits")
    a.to_csv(OUT / "audits.csv", index=False)
    R["audits"] = a.replace({np.nan: None}).to_dict("records")
    # Moment de l'audit par rapport aux paiements
    t = q(con, """SELECT COUNT(*) n_audites_payes,
        AVG((date_audit > date_dernier_paiement)::INT) part_audit_apres_dernier_paiement,
        AVG((date_audit < date_premier_paiement)::INT) part_audit_avant_premier_paiement,
        MEDIAN(DATE_DIFF('day', date_declaration, date_audit)) delai_median_audit
        FROM core.fact_sinistre WHERE audite AND nb_paiements > 0""", "timing_audit").iloc[0].to_dict()
    R["audit_timing"] = t
    R["fraude_paiements"] = q(con, """SELECT COUNT(DISTINCT f.sinistre_id) nb_fraudes,
        SUM(r.montant) paye_total,
        SUM(CASE WHEN r.date_paiement > f.date_audit THEN r.montant ELSE 0 END) paye_apres_audit,
        SUM(CASE WHEN r.date_paiement <= f.date_audit THEN r.montant ELSE 0 END) paye_avant_audit
        FROM core.fact_sinistre f JOIN core.fact_reglement r USING (sinistre_id)
        WHERE f.fraude_confirmee = 1""", "fraude_paiements").iloc[0].to_dict()
    ci = {}
    for _, r in a[a.critere.isin(["delai_declaration", "ensemble"])].iterrows():
        if r.nb_audites:
            res = stats.binomtest(int(r.nb_fraudes_confirmees), int(r.nb_audites)).proportion_ci(method="wilson")
            ci[r.modalite] = (res.low, res.high)
    R["audit_ic"] = ci
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.3))
    s = d[d.garantie != "TOUTES"]
    for i, (t_, c) in enumerate([("Déclaration", COL["main"]), ("Premier règlement", COL["acc"]),
                                 ("Clôture (proxy dernier règlement)", COL["grey"])]):
        z = s[s.type_delai == t_].sort_values("garantie")
        x = np.arange(len(z))
        axs[0].errorbar(x + (i - 1) * 0.25, z.mediane, yerr=[z.mediane - z.p25, z.p75 - z.mediane], fmt="o", color=c,
                        capsize=2, label=t_.split(" (")[0])
    axs[0].set_xticks(np.arange(len(z)), z.garantie, rotation=30, fontsize=7)
    axs[0].set_ylabel("jours (médiane, P25–P75)")
    axs[0].set_title("Délais de gestion par garantie")
    axs[0].legend(fontsize=7)
    dl = a[a.critere == "delai_declaration"].sort_values("modalite")
    axs[1].bar(dl.modalite, dl.taux_confirmation_audites.fillna(0) * 100, color=COL["acc"])
    for j, r in enumerate(dl.itertuples()):
        axs[1].text(j, (r.taux_confirmation_audites or 0) * 100 + 1, f"{int(r.nb_fraudes_confirmees)}/{int(r.nb_audites)}",
                    ha="center", fontsize=7)
    axs[1].set_ylabel("% de fraudes confirmées (dossiers audités)")
    axs[1].set_title("Confirmation de fraude selon le délai de déclaration")
    savefig("fig_delais_audits")


def evolution_mensuelle(con):
    m = q(con, """SELECT mois, SUM(primes_acquises) primes, SUM(charge) charge, SUM(charge_ecretee) charge_e,
                  SUM(contrats_actifs_fin_mois) actifs, SUM(nb_sinistres) n, SUM(exposition) expo
                  FROM mart.portefeuille_mensuel GROUP BY 1 ORDER BY 1""", "mensuel")
    m["sp12"] = m.charge.rolling(12).sum() / m.primes.rolling(12).sum()
    m["sp12e"] = m.charge_e.rolling(12).sum() / m.primes.rolling(12).sum()
    fig, ax = plt.subplots(figsize=(10, 3.2))
    ax.plot(m.mois, m.sp12 * 100, color=COL["main"], label="S/P glissant 12 mois (brut)")
    ax.plot(m.mois, m.sp12e * 100, color=COL["acc"], label="S/P glissant 12 mois (écrêté)")
    ax.axhline(70, color=COL["bad"], ls="--", lw=0.8, label="Seuil d'alerte 70 %")
    ax2 = ax.twinx()
    ax2.fill_between(m.mois, m.actifs, color=COL["grey"], alpha=0.15)
    ax2.set_ylabel("Contrats actifs (fin de mois)")
    ax.set_ylabel("%")
    ax.legend(fontsize=7, loc="upper left")
    ax.set_title("Ratio S/P glissant sur 12 mois et taille du portefeuille")
    savefig("fig_evolution")
    R["actifs_fin"] = float(m.actifs.iloc[-1])
    R["actifs_max"] = float(m.actifs.max())


def main():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    chaine(con)
    indicateurs(con)
    decomposition(con)
    statistiques(con)
    clients(con)
    sinistres(con)
    evolution_mensuelle(con)
    con.close()

    def conv(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (pd.Timestamp,)):
            return str(o.date())
        if isinstance(o, (np.bool_,)):
            return bool(o)
        return str(o)
    (OUT / "results.json").write_text(json.dumps(R, default=conv, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "requetes_sources.json").write_text(json.dumps(SQL, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Analyses écrites dans {OUT} ({len(R)} blocs de résultats, {len(SQL)} requêtes tracées)")


if __name__ == "__main__":
    main()
