"""Livrable 5 · Dashboard Boréal Assurances (Streamlit).

Alimenté UNIQUEMENT par les tables mart.* de l'entrepôt DuckDB (lecture seule).
Lancement : streamlit run dashboard/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.config import DB_PATH, SEUIL_ALERTE_SP, SEUIL_GRAVE  # noqa: E402

st.set_page_config(page_title="Boréal Assurances · Pilotage", page_icon="🧭", layout="wide")
NAVY, AMBER, RED, GREEN, GREY = "#1F4E79", "#C55A11", "#C62828", "#2E7D32", "#8A8F98"
st.markdown(f"""<style>
 h1, h2, h3 {{ color: {NAVY}; }}
 div[data-testid="stMetricValue"] {{ font-size: 1.55rem; }}
 .alerte {{ background:#FDECEA; border-left:5px solid {RED}; padding:.6rem .9rem; margin:.4rem 0 .8rem 0; }}
 .ok {{ background:#EAF4EA; border-left:5px solid {GREEN}; padding:.6rem .9rem; margin:.4rem 0 .8rem 0; }}
</style>""", unsafe_allow_html=True)


def fmt_eur(x):
    return f"{x:,.0f} €".replace(",", " ")


def fmt_pct(x, d=1):
    return "—" if x is None or pd.isna(x) else f"{x * 100:.{d}f} %".replace(".", ",")


@st.cache_data(ttl=300)
def load(table: str) -> pd.DataFrame:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df = con.execute(f"SELECT * FROM mart.{table}").df()
    con.close()
    return df


pm = load("portefeuille_mensuel")
pm["mois"] = pd.to_datetime(pm["mois"])

# ------------------------------------------------------------------ filtres
st.sidebar.title("Boréal Assurances")
page = st.sidebar.radio("Page", ["Portefeuille", "Technique et clients", "Exploitation", "Définitions"])
st.sidebar.markdown("---")
mois_dispo = sorted(pm.mois.dt.to_period("M").unique())
p0, p1 = st.sidebar.select_slider("Période (mois de survenance / d'acquisition)", options=mois_dispo,
                                  value=(mois_dispo[0], mois_dispo[-1]), format_func=lambda p: p.strftime("%m/%Y"))
f_prod = st.sidebar.multiselect("Produit", sorted(pm.produit.unique()), default=sorted(pm.produit.unique()))
f_reg = st.sidebar.multiselect("Région", sorted(pm.region.unique()), default=[], help="Vide = toutes les régions")
f_can = st.sidebar.multiselect("Canal", sorted(pm.canal.unique()), default=[], help="Vide = tous les canaux")
f_zone = st.sidebar.multiselect("Zone de risque", sorted(pm.zone_risque.unique()), default=[], help="Vide = toutes les zones")
ecrete = st.sidebar.toggle(f"Écrêter les sinistres graves (> {SEUIL_GRAVE // 1000} k€)", value=False,
                           help="Remplace la charge de chaque sinistre par min(charge, seuil) pour neutraliser les sinistres exceptionnels.")
st.sidebar.caption(f"Données extraites le 30/06/2025 · seuil d'alerte S/P : {SEUIL_ALERTE_SP:.0%}")


def filt(df, with_period=True):
    m = df.produit.isin(f_prod)
    if f_reg:
        m &= df.region.isin(f_reg)
    if f_can:
        m &= df.canal.isin(f_can)
    if f_zone:
        m &= df.zone_risque.isin(f_zone)
    if with_period:
        m &= (df.mois >= p0.to_timestamp()) & (df.mois <= p1.to_timestamp())
    return df[m]


CH = "charge_ecretee" if ecrete else "charge"
d_all = filt(pm, with_period=False)
d = filt(pm)


def kpis(x):
    e, p, n = x.exposition.sum(), x.primes_acquises.sum(), x.nb_sinistres.sum()
    c = x[CH].sum()
    return dict(primes=p, expo=e, n=n, charge=c, freq=n / e if e else np.nan, cm=c / n if n else np.nan,
                sp=c / p if p else np.nan, resil=x.resiliations.sum() / e if e else np.nan,
                paye=x.montant_paye.sum(), reserves=x.reserves.sum())


def agg_axis(x, axe):
    g = x.groupby(axe).agg(exposition=("exposition", "sum"), primes=("primes_acquises", "sum"),
                           n=("nb_sinistres", "sum"), charge=(CH, "sum"), resil=("resiliations", "sum")).reset_index()
    g["frequence"] = g.n / g.exposition
    g["cout_moyen"] = g.charge / g.n
    g["sp"] = g.charge / g.primes
    g["taux_resiliation"] = g.resil / g.exposition
    return g


# ================================================================== PAGE 1
if page == "Portefeuille":
    st.title("Portefeuille")
    k = kpis(d)
    # même période un an plus tôt
    prev = filt(pm.assign(mois=pm.mois + pd.DateOffset(years=1)))
    kp = kpis(prev)
    actifs = d[d.mois == d.mois.max()].contrats_actifs_fin_mois.sum() if len(d) else 0
    actifs_prev = d_all[d_all.mois == (d.mois.max() - pd.DateOffset(years=1))].contrats_actifs_fin_mois.sum() if len(d) else 0

    def delta(a, b, pct=True):
        if b is None or pd.isna(b) or b == 0:
            return None
        return f"{(a - b) * 100:+.1f} pt vs N-1".replace(".", ",") if pct else f"{(a / b - 1) * 100:+.1f} % vs N-1".replace(".", ",")

    if k["sp"] > SEUIL_ALERTE_SP:
        st.markdown(f"<div class='alerte'><b>Alerte :</b> le ratio sinistres sur primes de la sélection ({fmt_pct(k['sp'])}) "
                    f"dépasse le seuil de {SEUIL_ALERTE_SP:.0%} au-delà duquel, après ~30 % de frais, l'activité perd de l'argent.</div>",
                    unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='ok'>Ratio sinistres sur primes de la sélection : <b>{fmt_pct(k['sp'])}</b>, sous le seuil d'alerte de {SEUIL_ALERTE_SP:.0%}.</div>",
                    unsafe_allow_html=True)
    c = st.columns(6)
    c[0].metric("Primes acquises", fmt_eur(k["primes"]), delta(k["primes"], kp["primes"], False),
                help="Prime annuelle × durée de couverture dans la période (en années).")
    c[1].metric("Contrats actifs", f"{actifs:,.0f}".replace(",", " "), delta(actifs, actifs_prev, False),
                help="Contrats couvrant le dernier jour du dernier mois sélectionné.")
    c[2].metric("Fréquence", fmt_pct(k["freq"], 2), delta(k["freq"], kp["freq"]),
                help="Sinistres avec suite (ouverts ou clôturés) par année-police d'exposition.", delta_color="inverse")
    c[3].metric("Coût moyen", fmt_eur(k["cm"]) if pd.notna(k["cm"]) else "—", delta(k["cm"], kp["cm"], False),
                help="Charge (payé + réserve restante des ouverts) / nombre de sinistres avec suite.", delta_color="inverse")
    c[4].metric("Ratio S/P", fmt_pct(k["sp"]), delta(k["sp"], kp["sp"]),
                help="Charge des sinistres survenus dans la période / primes acquises de la période.", delta_color="inverse")
    c[5].metric("Taux de résiliation", fmt_pct(k["resil"]), delta(k["resil"], kp["resil"]),
                help="Résiliations / années-police d'exposition (taux annualisé).", delta_color="inverse")

    m = d_all.groupby("mois").agg(primes=("primes_acquises", "sum"), charge=(CH, "sum"), n=("nb_sinistres", "sum"),
                                  expo=("exposition", "sum"), actifs=("contrats_actifs_fin_mois", "sum")).reset_index()
    m["sp12"] = m.charge.rolling(12).sum() / m.primes.rolling(12).sum()
    m["sp_mois"] = m.charge / m.primes
    m["annee"] = m.mois.dt.year
    m["mois_num"] = m.mois.dt.month
    sel = m[(m.mois >= p0.to_timestamp()) & (m.mois <= p1.to_timestamp())]
    last = sel.annee.max() if len(sel) else 2025

    col1, col2 = st.columns(2)
    with col1:
        cur, pr = m[m.annee == last], m[m.annee == last - 1]
        evol = (cur.primes.sum() / pr[pr.mois_num.isin(cur.mois_num)].primes.sum() - 1) if len(pr) else np.nan
        st.subheader(f"Les primes acquises {last} évoluent de {evol * 100:+.0f} % sur un an à mois comparables".replace(".", ","))
        fig = go.Figure()
        fig.add_bar(x=cur.mois_num, y=cur.primes, name=str(last), marker_color=NAVY,
                    hovertemplate="Mois %{x}<br>Primes acquises : %{y:,.0f} €<extra>" + str(last) + "</extra>")
        fig.add_scatter(x=pr.mois_num, y=pr.primes, name=str(last - 1), mode="lines+markers", line_color=GREY,
                        hovertemplate="Mois %{x}<br>Primes acquises : %{y:,.0f} €<extra>" + str(last - 1) + "</extra>")
        fig.update_layout(height=320, margin=dict(t=10, b=10), xaxis_title="Mois", yaxis_title="€", legend_orientation="h")
        st.plotly_chart(fig, width="stretch")
    with col2:
        dernier = sel.sp12.dropna().iloc[-1] if sel.sp12.notna().any() else np.nan
        verdict = "au-dessus" if dernier > SEUIL_ALERTE_SP else "sous"
        st.subheader(f"Le S/P glissant 12 mois ({fmt_pct(dernier)}) est {verdict} le seuil d'alerte")
        fig = go.Figure()
        fig.add_scatter(x=sel.mois, y=sel.sp12, name="S/P glissant 12 mois", line_color=NAVY,
                        hovertemplate="%{x|%m/%Y}<br>S/P 12 mois : %{y:.1%}<extra></extra>")
        fig.add_scatter(x=sel.mois, y=sel.sp12.shift(0).where(sel.sp12 > SEUIL_ALERTE_SP), mode="markers",
                        marker=dict(color=RED, size=7), name="Dépassement du seuil",
                        hovertemplate="%{x|%m/%Y}<br>Au-dessus du seuil : %{y:.1%}<extra></extra>")
        fig.add_hline(y=SEUIL_ALERTE_SP, line_dash="dash", line_color=RED, annotation_text=f"Seuil {SEUIL_ALERTE_SP:.0%}")
        fig.update_layout(height=320, margin=dict(t=10, b=10), yaxis_tickformat=".0%", legend_orientation="h")
        st.plotly_chart(fig, width="stretch")

    col3, col4 = st.columns(2)
    with col3:
        cur, pr = m[m.annee == last], m[m.annee == last - 1]
        st.subheader("Fréquence mensuelle annualisée comparée à l'année précédente")
        fig = go.Figure()
        fig.add_scatter(x=cur.mois_num, y=cur.n / cur.expo, name=str(last), line_color=NAVY,
                        hovertemplate="Mois %{x}<br>Fréquence : %{y:.2%}<extra>" + str(last) + "</extra>")
        fig.add_scatter(x=pr.mois_num, y=pr.n / pr.expo, name=str(last - 1), line_color=GREY, line_dash="dot",
                        hovertemplate="Mois %{x}<br>Fréquence : %{y:.2%}<extra>" + str(last - 1) + "</extra>")
        fig.update_layout(height=300, margin=dict(t=10, b=10), yaxis_tickformat=".1%", xaxis_title="Mois", legend_orientation="h")
        st.plotly_chart(fig, width="stretch")
    with col4:
        st.subheader("Le portefeuille actif se stabilise autour de " + f"{sel.actifs.iloc[-1]:,.0f}".replace(",", " ") + " contrats" if len(sel) else "Contrats actifs")
        fig = px.area(sel, x="mois", y="actifs", color_discrete_sequence=[NAVY])
        fig.update_traces(hovertemplate="%{x|%m/%Y}<br>Contrats actifs : %{y:,.0f}<extra></extra>")
        fig.update_layout(height=300, margin=dict(t=10, b=10), yaxis_title="contrats", xaxis_title=None)
        st.plotly_chart(fig, width="stretch")
    st.caption(f"Charge {('écrêtée' if ecrete else 'brute')} : payé {fmt_eur(k['paye'])} + réserves restantes {fmt_eur(k['reserves'])}. "
               "Les 12 derniers mois sont incomplets (sinistres récents encore peu développés).")

# ================================================================== PAGE 2
elif page == "Technique et clients":
    st.title("Technique et clients")
    st.subheader("Où le portefeuille gagne ou perd de l'argent")
    cols = st.columns(4)
    for col, (axe, lab) in zip(cols, [("zone_risque", "Zone"), ("formule", "Formule"), ("canal", "Canal"), ("tranche_age", "Âge")]):
        g = agg_axis(d, axe)
        g[axe] = g[axe].astype(str)
        worst = g.sort_values("sp").iloc[-1]
        col.markdown(f"**{lab} : S/P le plus élevé = {worst[axe]} ({fmt_pct(worst.sp)})**")
        fig = px.bar(g, x=axe, y="sp", color=g.sp > SEUIL_ALERTE_SP,
                     color_discrete_map={True: RED, False: NAVY}, custom_data=["frequence", "cout_moyen", "primes"])
        fig.update_traces(hovertemplate="%{x}<br>S/P : %{y:.1%}<br>Fréquence : %{customdata[0]:.2%}<br>"
                                        "Coût moyen : %{customdata[1]:,.0f} €<br>Primes : %{customdata[2]:,.0f} €<extra></extra>")
        fig.add_hline(y=SEUIL_ALERTE_SP, line_dash="dash", line_color=RED)
        fig.update_layout(height=280, showlegend=False, margin=dict(t=10, b=10), yaxis_tickformat=".0%", xaxis_title=None, yaxis_title=None)
        col.plotly_chart(fig, width="stretch")

    st.subheader("Décomposition de l'évolution annuelle du S/P")
    y = d.groupby("annee").agg(e=("exposition", "sum"), p=("primes_acquises", "sum"), n=("nb_sinistres", "sum"), c=(CH, "sum")).reset_index()
    y = y[(y.n > 0) & (y.e > 0)]
    y["f"], y["cm"], y["pm"], y["sp"] = y.n / y.e, y.c / y.n, y.p / y.e, y.c / y.p
    rows = []
    for i in range(1, len(y)):
        a, b = y.iloc[i - 1], y.iloc[i]
        dsp = b.sp - a.sp
        L = np.log(b.sp / a.sp) if b.sp != a.sp else np.nan
        w = dsp / L if L and not np.isnan(L) else 0
        rows += [dict(periode=f"{int(a.annee)}→{int(b.annee)}", effet="Fréquence", pts=w * np.log(b.f / a.f)),
                 dict(periode=f"{int(a.annee)}→{int(b.annee)}", effet="Coût moyen", pts=w * np.log(b.cm / a.cm)),
                 dict(periode=f"{int(a.annee)}→{int(b.annee)}", effet="Prime moyenne", pts=-w * np.log(b.pm / a.pm))]
    if rows:
        dd = pd.DataFrame(rows)
        main = dd.loc[dd.pts.abs().idxmax()]
        st.markdown(f"Le plus fort mouvement vient de l'effet **{main.effet.lower()}** en {main.periode} "
                    f"({main.pts * 100:+.1f} points de S/P). Le volume de contrats n'affecte pas le ratio : il fait varier "
                    "charge et primes dans la même proportion.".replace(".", ",", 1))
        fig = px.bar(dd, x="periode", y="pts", color="effet", barmode="group",
                     color_discrete_map={"Fréquence": NAVY, "Coût moyen": AMBER, "Prime moyenne": GREY})
        fig.update_traces(hovertemplate="%{x}<br>%{fullData.name} : %{y:+.1%} de S/P<extra></extra>")
        fig.update_layout(height=320, yaxis_tickformat="+.0%", yaxis_title="points de S/P", xaxis_title=None, margin=dict(t=10, b=10))
        st.plotly_chart(fig, width="stretch")
        st.caption("2024 est à consolider (réserves ouvertes) et 2025 ne couvre que 6 mois.")

    c1, c2 = st.columns(2)
    with c1:
        ret = load("retention_cohorte")
        prod = st.selectbox("Produit (rétention)", ["TOUS", "AUTO", "HABITATION"])
        r = ret[(ret.produit == prod) & ret.cellule_complete].pivot(index="cohorte", columns="annee_anciennete", values="taux_retention")
        r1 = ret[(ret.produit == prod) & ret.cellule_complete & (ret.annee_anciennete == 1)]
        st.subheader(f"Un client sur {1 / (1 - r1.clients_retenus.sum() / r1.clients_observables.sum()):.0f} part dès la 1re année".replace(".", ","))
        fig = px.imshow(r * 100, text_auto=".0f", color_continuous_scale="Blues", zmin=50, zmax=100, aspect="auto",
                        labels=dict(x="Années d'ancienneté", y="Cohorte de souscription", color="% retenus"))
        fig.update_traces(hovertemplate="Cohorte %{y}, an %{x}<br>Clients encore assurés : %{z:.1f} %<extra></extra>")
        fig.update_layout(height=320, margin=dict(t=10, b=10))
        st.plotly_chart(fig, width="stretch")
        st.caption("Seules les cellules entièrement observables au 30/06/2025 sont affichées.")
    with c2:
        v = load("valeur_client")
        if f_reg:
            v = v[v.region.isin(f_reg)]
        if f_can:
            v = v[v.canal_principal.isin(f_can)]
        v = v.sort_values("valeur_observee", ascending=False).reset_index(drop=True)
        v["pc"] = (v.index + 1) / len(v)
        v["pv"] = v.valeur_observee.cumsum() / v.valeur_observee.sum()
        neg = (v.valeur_observee < 0).mean()
        st.subheader(f"{fmt_pct(neg)} des clients détruisent de la valeur")
        fig = px.line(v.iloc[::max(1, len(v) // 800)], x="pc", y="pv", color_discrete_sequence=[NAVY])
        fig.update_traces(hovertemplate="%{x:.0%} des clients<br>%{y:.0%} de la valeur observée<extra></extra>")
        fig.add_hline(y=1, line_dash="dot", line_color=GREY)
        fig.update_layout(height=320, xaxis_tickformat=".0%", yaxis_tickformat=".0%", margin=dict(t=10, b=10),
                          xaxis_title="Clients classés du plus au moins rentable", yaxis_title="Valeur cumulée")
        st.plotly_chart(fig, width="stretch")
        st.caption("Valeur observée = primes acquises − sinistres payés (hors réserves). La courbe dépasse 100 % "
                   "puis redescend : les derniers clients consomment plus qu'ils n'apportent.")

# ================================================================== PAGE 3
elif page == "Exploitation":
    st.title("Exploitation de la chaîne")
    ch = load("exploitation_chargements")
    tests = load("exploitation_tests")
    dq = load("exploitation_qualite")
    fr = load("exploitation_fraicheur")
    runs = load("exploitation_runs")
    ok = (tests.statut == "OK").all()
    last_run = runs.iloc[0] if len(runs) else None
    if ok and last_run is not None and last_run.statut == "SUCCES":
        st.markdown(f"<div class='ok'>Dernière exécution réussie le {pd.to_datetime(last_run.debut):%d/%m/%Y à %H:%M} · "
                    f"{(tests.statut == 'OK').sum()}/{len(tests)} tests bloquants au vert.</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='alerte'><b>Attention :</b> la dernière exécution ou un test est en échec.</div>", unsafe_allow_html=True)
    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.subheader("Dernier chargement par source")
        st.dataframe(ch.rename(columns={"dernier_chargement_reussi": "dernier chargement", "nb_fichiers": "fichiers",
                                        "lignes_chargees_cumul": "lignes chargées", "lignes_rejetees_cumul": "lignes illisibles",
                                        "nb_echecs": "échecs", "dernier_fichier": "dernier fichier"})
                     .drop(columns=["derniere_tentative"]), hide_index=True, width="stretch")
        st.subheader("Fraîcheur des données")
        fr["retard_jours"] = (pd.Timestamp("2025-06-30") - pd.to_datetime(fr.derniere_date_metier)).dt.days
        st.dataframe(fr, hide_index=True, width="stretch")
    with c2:
        st.subheader("Résultats des tests bloquants")
        st.dataframe(tests[["test_id", "libelle", "ecarts", "statut"]], hide_index=True, width="stretch", height=330)
    dqa = dq[dq.volume > 0].sort_values("volume", ascending=True)
    st.subheader(f"{int(dq[dq.traitement.isin(['EXCLURE', 'FUSIONNER'])].volume.sum())} lignes écartées en quarantaine, "
                 f"{int(dq[~dq.traitement.isin(['EXCLURE', 'FUSIONNER'])].volume.sum())} signalées ou corrigées")
    fig = px.bar(dqa, y=dqa.rule_id + " · " + dqa.libelle, x="volume", color="traitement", orientation="h",
                 color_discrete_map={"EXCLURE": RED, "FUSIONNER": AMBER, "CORRIGER": NAVY, "SIGNALER": GREY},
                 custom_data=["entite", "gravite", "taux"])
    fig.update_traces(hovertemplate="%{y}<br>%{x} lignes (%{customdata[2]:.2%} de la table %{customdata[0]})<br>"
                                    "Gravité : %{customdata[1]}<extra></extra>")
    fig.update_layout(height=480, margin=dict(t=10, b=10), yaxis_title=None, xaxis_title="lignes concernées")
    st.plotly_chart(fig, width="stretch")
    dl = load("delais_sinistres")
    t = dl[dl.garantie == "TOUTES"].set_index("type_delai")
    st.subheader(f"Délais de gestion : 1er règlement en {t.loc['Premier règlement', 'mediane']:.0f} jours médians, "
                 f"clôture en {t.loc['Clôture (proxy dernier règlement)', 'mediane']:.0f} jours")
    g = dl[dl.garantie != "TOUTES"]
    fig = px.bar(g, x="garantie", y="mediane", color="type_delai", barmode="group",
                 error_y=g.p75 - g.mediane, error_y_minus=g.mediane - g.p25, custom_data=["p90", "n"],
                 color_discrete_sequence=[NAVY, AMBER, GREY])
    fig.update_traces(hovertemplate="%{x}<br>Médiane : %{y:.0f} j<br>P90 : %{customdata[0]:.0f} j<br>n = %{customdata[1]}<extra></extra>")
    fig.update_layout(height=340, margin=dict(t=10, b=10), yaxis_title="jours (médiane, barres P25–P75)", xaxis_title=None)
    st.plotly_chart(fig, width="stretch")
    st.caption("Clôture : la source ne fournit pas de date de clôture ; on utilise la date du dernier règlement des sinistres clôturés.")

# ================================================================== DÉFINITIONS
else:
    st.title("Définitions des indicateurs")
    defs = pd.DataFrame([
        ("Année-police (exposition)", "Durée de couverture exprimée en années : un contrat couvert 6 mois = 0,5 année-police. Base de toutes les fréquences et taux."),
        ("Primes acquises", "Prime annuelle × exposition de la période. Une prime de 600 € couverte 3 mois rapporte 150 € de primes acquises."),
        ("Contrats actifs", "Contrats en cours le dernier jour du mois (date d'effet passée, non résiliés)."),
        ("Sinistre avec suite", "Sinistre ouvert ou clôturé. Les sinistres « sans suite » et « rejetés » sont comptés à part et n'entrent pas dans la fréquence."),
        ("Fréquence", "Nombre de sinistres avec suite / années-police. 4 % = 4 sinistres pour 100 contrats assurés un an."),
        ("Charge", "Montants payés + réserve restante des sinistres encore ouverts (réserve initiale − déjà payé)."),
        ("Charge écrêtée", f"Charge de chaque sinistre plafonnée à {SEUIL_GRAVE:,} €".replace(",", " ") + " pour isoler les sinistres exceptionnels."),
        ("Coût moyen", "Charge / nombre de sinistres avec suite."),
        ("Prime moyenne", "Primes acquises / années-police."),
        ("Ratio S/P", "Charge des sinistres survenus dans la période / primes acquises de la période. Rattachement à l'année de survenance."),
        ("Seuil d'alerte S/P", f"{SEUIL_ALERTE_SP:.0%} : au-delà, la marge est insuffisante pour couvrir ~30 % de frais d'acquisition et de gestion."),
        ("Taux de résiliation", "Résiliations / années-police (taux annualisé)."),
        ("Rétention (cohorte)", "Part des clients d'une cohorte de 1re souscription encore assurés à l'anniversaire k. Calculée seulement si la période est entièrement observée."),
        ("Multi-détenteur", "Client détenant auto ET habitation dans les 90 jours suivant sa 1re souscription."),
        ("Valeur observée", "Primes acquises − sinistres payés par client, sur toute la période (hors réserves et frais)."),
        ("Délai de déclaration", "Jours entre survenance et déclaration (hors 15 sinistres aux dates incohérentes)."),
        ("Délai de 1er règlement", "Jours entre déclaration et premier paiement."),
        ("Délai de clôture", "Jours entre déclaration et dernier paiement des sinistres clôturés (proxy, la date de clôture n'existe pas)."),
        ("Taux de confirmation de fraude", "Fraudes confirmées / sinistres audités. Ne s'applique qu'aux dossiers audités (13 % des sinistres)."),
    ], columns=["Indicateur", "Définition"])
    st.dataframe(defs, hide_index=True, width="stretch", height=720)
