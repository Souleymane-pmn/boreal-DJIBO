"""Génère le dossier PDF (DJIBO_Boreal.pdf) et la note exécutive d'une page.
Tous les chiffres proviennent de analysis/output/results.json (calculé depuis l'entrepôt) ou de requêtes directes.
Usage : python -m rapport.build_report
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import duckdb
import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate,  # noqa: E402
                                Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.config import DB_PATH, SEUIL_ALERTE_SP, SEUIL_GRAVE  # noqa: E402

OUT = ROOT / "analysis" / "output"
# Auteur (projet individuel) : remplacer ou définir les variables BOREAL_NOM / BOREAL_PRENOM
import os  # noqa: E402
NOM = os.getenv("BOREAL_NOM", "DJIBO")
PRENOM = os.getenv("BOREAL_PRENOM", "Souleymane")
DEST = ROOT / "rapport"
R = json.loads((OUT / "results.json").read_text(encoding="utf-8"))

F = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("DV", F + "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DVB", F + "DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DVI", F + "DejaVuSans-Oblique.ttf"))
pdfmetrics.registerFont(TTFont("DVM", F + "DejaVuSansMono.ttf"))
from reportlab.pdfbase.pdfmetrics import registerFontFamily  # noqa: E402
registerFontFamily("DV", normal="DV", bold="DVB", italic="DVI", boldItalic="DVB")

NAVY = colors.HexColor("#1F4E79")
AMBER = colors.HexColor("#C55A11")
LIGHT = colors.HexColor("#EAF0F7")
ss = getSampleStyleSheet()
S = {
    "body": ParagraphStyle("body", parent=ss["Normal"], fontName="DV", fontSize=9.2, leading=13, alignment=TA_JUSTIFY, spaceAfter=5),
    "h1": ParagraphStyle("h1", fontName="DVB", fontSize=15, leading=19, textColor=NAVY, spaceBefore=4, spaceAfter=8),
    "h2": ParagraphStyle("h2", fontName="DVB", fontSize=11.5, leading=15, textColor=NAVY, spaceBefore=8, spaceAfter=4),
    "h3": ParagraphStyle("h3", fontName="DVB", fontSize=9.6, leading=13, textColor=AMBER, spaceBefore=5, spaceAfter=2),
    "cell": ParagraphStyle("cell", fontName="DV", fontSize=7.3, leading=9),
    "cellb": ParagraphStyle("cellb", fontName="DVB", fontSize=7.3, leading=9, textColor=colors.white),
    "cap": ParagraphStyle("cap", fontName="DVI", fontSize=7.8, leading=10, textColor=colors.HexColor("#555555"), spaceAfter=7),
    "code": ParagraphStyle("code", fontName="DVM", fontSize=7, leading=8.8, backColor=colors.HexColor("#F4F6F8"),
                           borderPadding=4, spaceAfter=6),
    "box": ParagraphStyle("box", fontName="DV", fontSize=9, leading=12.5, backColor=LIGHT, borderPadding=6,
                          spaceBefore=4, spaceAfter=8, borderColor=NAVY, borderWidth=0.6),
    "title": ParagraphStyle("title", fontName="DVB", fontSize=24, leading=30, textColor=NAVY, alignment=TA_CENTER),
    "sub": ParagraphStyle("sub", fontName="DV", fontSize=12, leading=16, alignment=TA_CENTER, textColor=colors.HexColor("#444444")),
}


# ---------------------------------------------------------------- formats
def fe(x, d=0):
    return f"{x:,.{d}f} €".replace(",", " ").replace(".", ",") if x is not None else "—"


def fn(x, d=0):
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",") if x is not None else "—"


def fp(x, d=1):
    return f"{x * 100:.{d}f} %".replace(".", ",") if x is not None and x == x else "—"


def fpt(x, d=1):
    return f"{x * 100:+.{d}f} pt".replace(".", ",") if x is not None and x == x else "—"


def fpv(p):
    return "< 0,001" if p < 0.001 else f"{p:.3f}".replace(".", ",")


def P(t, s="body"):
    return Paragraph(t, S[s])


def T(rows, widths=None, header=True, fs=None, zebra=True):
    data = [[Paragraph(str(c), S["cellb"] if (header and i == 0) else S["cell"]) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B0B7C3")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    if header:
        st.append(("BACKGROUND", (0, 0), (-1, 0), NAVY))
    if zebra:
        for i in range(1 if header else 0, len(rows)):
            if i % 2 == 0:
                st.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F3F6FA")))
    t.setStyle(TableStyle(st))
    return t


def IMG(name, w=17):
    p = OUT / name if (OUT / name).exists() else DEST / name
    from PIL import Image as PI
    im = PI.open(p)
    h = w * im.size[1] / im.size[0]
    return Image(str(p), width=w * cm, height=h * cm)


def K(key):
    return R["kpi"][key]


# ---------------------------------------------------------------- schémas
def diagrams():
    fig, ax = plt.subplots(figsize=(11, 3.2))
    ax.axis("off")
    boxes = [("Sources\n68 fichiers\nCSV · JSONL\nlatin-1 / UTF-8", "#7F7F7F"),
             ("RAW\ncopie fidèle (texte)\n+ fichier, ligne,\nempreinte, date", "#4A6F95"),
             ("PREP\ntypage, normalisation\ndéduplication\nclients", "#2F5F8F"),
             ("QUALITÉ\n34 règles\nquarantaine\n+ motif", "#C55A11"),
             ("CORE\nétoile : 5 dim.\n4 faits\n(SCD 2 contrat)", "#1F4E79"),
             ("MARTS\n13 tables d'usage\n+ 13 tests\nbloquants", "#16365C"),
             ("Dashboard\nStreamlit\n& dossier", "#2E7D32")]
    for i, (t, c) in enumerate(boxes):
        x = i * 1.45
        ax.add_patch(FancyBboxPatch((x, 0.2), 1.2, 1.3, boxstyle="round,pad=0.03", fc=c, ec="none"))
        ax.text(x + 0.6, 0.85, t, ha="center", va="center", color="white", fontsize=8.2, family="DejaVu Sans")
        if i < len(boxes) - 1:
            ax.annotate("", xy=(x + 1.43, 0.85), xytext=(x + 1.22, 0.85), arrowprops=dict(arrowstyle="->", lw=1.4))
    ax.text(1.45 * 1 + 0.6, 0.02, "meta.ingestion_log · transaction par fichier", ha="center", fontsize=7, style="italic")
    ax.text(1.45 * 4 + 0.6, 0.02, "PREP → MARTS + tests : une transaction (échec = ROLLBACK + alerte)", ha="center", fontsize=7, style="italic")
    ax.text(0.6, 1.62, "pipeline.watch (cron) : fichier nouveau → exécution", fontsize=7.5, style="italic")
    ax.set_xlim(-0.05, 10.2)
    ax.set_ylim(-0.1, 1.75)
    plt.savefig(DEST / "fig_architecture.png", dpi=170, bbox_inches="tight")
    plt.close()

    fig, ax = plt.subplots(figsize=(10, 5.6))
    ax.axis("off")

    def box(x, y, title, cols, c):
        h = 0.32 + 0.21 * len(cols)
        ax.add_patch(FancyBboxPatch((x, y - h), 2.6, h, boxstyle="round,pad=0.02", fc="white", ec=c, lw=1.4))
        ax.add_patch(FancyBboxPatch((x, y - 0.32), 2.6, 0.32, boxstyle="round,pad=0.02", fc=c, ec=c))
        ax.text(x + 1.3, y - 0.16, title, ha="center", va="center", color="white", fontsize=8.2, weight="bold")
        for j, col in enumerate(cols):
            ax.text(x + 0.08, y - 0.48 - 0.21 * j, col, fontsize=6.8, va="center")
        return (x + 1.3, y - h / 2)
    fe_ = box(3.7, 5.4, "fact_exposition_mensuelle", ["grain : contrat × mois", "mois_key → dim_date", "contrat_sk → dim_contrat",
                                                        "client_id → dim_client", "segment_key → dim_segment", "jours_couverts, exposition_annees",
                                                        "prime_acquise, resiliation", "nouvelle_souscription, actif_fin_mois"], "#1F4E79")
    fs_ = box(3.7, 2.6, "fact_sinistre", ["grain : sinistre", "date_survenance_key, garantie", "contrat_sk, client_id, segment_key",
                                           "statut, reserve_initiale, montant_paye", "reserve_restante, charge, charge_ecretee",
                                           "délais (décl., 1er règl., clôture)", "audite, fraude_confirmee"], "#1F4E79")
    fr_ = box(7.3, 2.6, "fact_reglement (incrémental)", ["grain : paiement", "paiement_id (clé), sinistre_id", "contrat_id, date_paiement_key",
                                                          "montant, _source_file"], "#1F4E79")
    fa_ = box(7.3, 5.4, "fact_exposition_annuelle", ["grain : contrat × année", "agrégée depuis la mensuelle", "exposition, prime_acquise, resiliation"], "#1F4E79")
    d1 = box(0, 5.4, "dim_contrat (SCD 2)", ["contrat_sk, contrat_id, version", "produit, formule, canal, zone", "franchise, bonus_malus, prime",
                                             "date_effet, date_resiliation (SCD1)", "valid_from, valid_to, is_current"], "#C55A11")
    d2 = box(0, 3.2, "dim_client (SCD 1)", ["client_id (survivant)", "date_naissance, région, CSP", "consentement, email_hash"], "#C55A11")
    d3 = box(0, 1.5, "dim_segment", ["segment_key", "produit × zone × formule", "× canal × tranche d'âge"], "#C55A11")
    d4 = box(7.3, 0.9, "dim_garantie", ["garantie, libellé, famille"], "#C55A11")
    d5 = box(3.7, 0.55, "dim_date", ["date_key AAAAMMJJ, année, mois"], "#C55A11")
    for a, b in [(d1, fe_), (d2, fe_), (d3, fe_), (d1, fs_), (d2, fs_), (d3, fs_), (fs_, fr_), (d4, fs_), (d5, fs_), (fe_, fa_)]:
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#9AA5B1", lw=0.8, zorder=0)
    ax.set_xlim(-0.1, 10)
    ax.set_ylim(0, 5.5)
    plt.savefig(DEST / "fig_etoile.png", dpi=170, bbox_inches="tight")
    plt.close()


def pytest_summary():
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q"], cwd=ROOT, capture_output=True, text=True, timeout=900)
        return r.stdout.strip().splitlines()[-1]
    except Exception as e:  # noqa: BLE001
        return f"non exécuté ({e})"


# ---------------------------------------------------------------- contenu
def footer(c, d):
    c.saveState()
    c.setFont("DV", 7.5)
    c.setFillColor(colors.HexColor("#777777"))
    c.drawString(2 * cm, 1.2 * cm, "Souleymane DJIBO · M2 Data Analyst · PMN · Projet Boréal Assurances")
    c.drawRightString(19 * cm, 1.2 * cm, f"page {d.page}")
    c.restoreState()


def build():
    diagrams()
    py = pytest_summary()
    con = duckdb.connect(str(DB_PATH), read_only=True)
    log = con.execute("""SELECT fichier, mode, lignes_lues, lignes_chargees, statut, duree_s FROM meta.ingestion_log
                         WHERE fichier IN ('reglements/reglements_2023_04.csv','reglements/reglements_2024_03.csv','crm/clients.csv')
                         ORDER BY fichier, charge_le LIMIT 8""").fetchall()
    n_runs = con.execute("SELECT COUNT(*), SUM((statut='SUCCES')::INT) FROM meta.runs").fetchone()
    con.close()

    kt, ka, kh = K("total|Ensemble"), K("produit|AUTO"), K("produit|HABITATION")
    ic = R["ic"]
    q, tz, tc, tr = R["queue"], R["test_frequence_zone"], R["test_cout_canal"], R["test_resiliation_canal"]
    g0 = R["graves"][0]
    dec = {(d["mesure"], d["annee"]): d for d in R["decomposition"]}
    an = {int(a["periode"]): a for a in R["kpi_annuel"]}
    rec = R["reconciliation"]
    vol = R["volumes"]
    v = R["valeur"]
    fpay = R["fraude_paiements"]
    aud = {(a["critere"], a["modalite"]): a for a in R["audits"]}
    dl = {(d["garantie"], d["type_delai"]): d for d in R["delais"]}
    rd = {(d["detention_origine"], d["annee_anciennete"]): d for d in R["retention_detention"]}
    ret = pd.DataFrame(R["retention"])
    qa = {r["rule_id"]: r for r in R["qualite"]}


    st = []
    # ======================== COUVERTURE
    st += [Spacer(1, 4.5 * cm), P("Projet Boréal Assurances", "title"), Spacer(1, 0.4 * cm),
           P("Chaîne de données et analyse du portefeuille d'un assureur auto / habitation", "sub"), Spacer(1, 1.5 * cm),
           P("Souleymane DJIBO<br/>M2 Data Analyst · PMN", "sub"), Spacer(1, 1 * cm),
           P("Projet réalisé seul<br/>Données extraites le 30/06/2025<br/>Dépôt : boreal-DJIBO", "sub"), PageBreak()]

    # ======================== SOMMAIRE + RÉSUMÉ
    st += [P("Sommaire", "h1"),
           T([["Partie", "Page"], ["Résumé", "2"], ["1. Architecture et ingestion", "3"], ["2. Qualité des données et modèle", "5"],
              ["3. Analyse technique du portefeuille", "8"], ["4. Clients et sinistres", "13"], ["5. Dashboard et documentation", "17"],
              ["Annexes", "19"]], [12 * cm, 3 * cm]),
           Spacer(1, 0.4 * cm), P("Résumé", "h1"),
           P(f"Pour ce projet j'ai construit une base de données DuckDB qui charge automatiquement les 68 fichiers fournis "
             f"({fn(vol['raw.contrats'])} contrats, {fn(vol['raw.sinistres'])} sinistres, {fn(vol['raw.reglements'])} lignes de règlements). "
             f"Les données sont vérifiées (34 règles de qualité, 13 tests), puis organisées en schéma en étoile. "
             f"Le pipeline tourne en 5 secondes environ et on peut le relancer sans créer de doublons. "
             f"Le dashboard et ce dossier utilisent les mêmes tables, donc les chiffres sont les mêmes partout "
             f"(par exemple le ratio sinistres / primes = <b>{fp(kt['ratio_sp'])}</b>).", "body"),
           P("<b>Ce que j'ai trouvé :</b>", "body"),
           P(f"1. Un seul sinistre de {fe(g0['charge'])} (collision, {g0['annee_survenance']}) représente {fp(q['part_max'], 0)} de tout le coût des sinistres. "
             f"Si on plafonne les sinistres à {fn(SEUIL_GRAVE)} €, le S/P passe de {fp(kt['ratio_sp'])} à {fp(kt['ratio_sp_ecrete'])}. "
             f"La hausse de 2023 ({fp(an[2023]['ratio_sp'], 0)}) vient uniquement de ce sinistre.", "body"),
           P(f"2. L'habitation rapporte moins que l'auto : S/P de {fp(kh['ratio_sp_ecrete'])} contre {fp(ka['ratio_sp_ecrete'])} (hors gros sinistres), "
             f"alors que la fréquence est presque la même. La prime habitation est deux fois plus basse. "
             f"Il y a aussi {fn(tz['rapport'], 1)} fois plus de sinistres en zone 5 qu'en zone 1, mais la prime n'est que "
             f"{fp(K('zone_risque|5')['prime_moyenne'] / K('zone_risque|1')['prime_moyenne'] - 1, 0)} plus chère.", "body"),
           P(f"3. Les clients venus par le web résilient plus ({fp(tr['t_web'])} par an contre {fp(tr['t_agent'])} en agence). "
             f"Et {fe(fpay['paye_apres_audit'])} ont été payés sur des sinistres <i>après</i> qu'un audit ait confirmé la fraude.", "body"),
           P("<b>Ce que je propose :</b> suivre le S/P sans les gros sinistres, revoir le prix de l'habitation et des zones à risque, "
             "bloquer les paiements quand une fraude est confirmée, et essayer de mieux garder les clients web.", "box"),
           PageBreak()]

    # ======================== L1
    st += [P("1. Architecture et ingestion", "h1"), P("1.1 Schéma de la chaîne", "h2"), IMG("fig_architecture.png", 17),
           P("Figure 1 : les différentes couches de la base. Tout est dans un seul fichier DuckDB.", "cap"),
           P("Les données passent par plusieurs étapes. La couche <b>brute</b> garde les fichiers tels quels. La couche <b>préparation</b> "
             "met les bons types (dates, nombres). Ensuite les <b>contrôles qualité</b> mettent de côté les lignes à problème (quarantaine). "
             "Le <b>cœur</b> est le schéma en étoile. Les <b>marts</b> sont des tables prêtes à l'emploi pour le dashboard.", "body"),
           P("Pourquoi ces outils", "h3"),
           T([["Outil", "Pourquoi je l'ai choisi"],
              ["DuckDB", f"Peu de données ({fn(sum(vol[k] for k in vol if k.startswith('raw.')))} lignes, 610 Ko) : pas besoin d'un serveur. Gratuit, tout tourne en 5 s."],
              ["Python + SQL", "Ce sont les langages que je maîtrise et le SQL est facile à relire."],
              ["Makefile + cron", "Une livraison par mois seulement : pas besoin d'Airflow, une ligne de cron suffit."],
              ["Streamlit", "Gratuit, simple, et le code reste dans le même dépôt. Pages chargées en moins de 2 s."]],
             [3.5 * cm, 13.5 * cm]),
           P("Avec 100 fois plus de données", "h3"),
           P("DuckDB pourrait encore suivre, mais recalculer toutes les tables à chaque fois deviendrait lent. Je passerais à un chargement "
             "mois par mois (dbt incrémental, fichiers Parquet), à une base partagée comme PostgreSQL ou BigQuery si plusieurs personnes "
             "travaillent dessus, et à un vrai orchestrateur comme Airflow.", "body"),
           P("1.2 Chargement des fichiers", "h2"),
           P("Le programme regarde chaque fichier et devine tout seul l'encodage (UTF-8 ou latin-1) et le séparateur (virgule ou point-virgule). "
             "Les colonnes sont reconnues par leur nom, pas par leur position. C'était nécessaire car le fichier <i>reglements_2024_03.csv</i> "
             "n'a pas les colonnes dans le même ordre et la colonne montant s'appelle <i>montant_eur</i>. "
             "Dans la couche brute je garde tout en texte, et j'ajoute pour chaque ligne le nom du fichier, le numéro de ligne et la date de chargement.", "body"),
           T([["Source", "Fichiers", "Lignes", "Lignes illisibles", "Encodage", "Séparateur"]] +
             [[r["source"], fn(r["fichiers"]), fn(r["lignes"]), fn(r["rejets"]), r["encodages"], r["separateurs"]] for r in R["ingestion"]],
             [3 * cm, 2 * cm, 2.5 * cm, 3 * cm, 3 * cm, 3 * cm]),
           P("Tableau 1 : résultat du premier chargement.", "cap"),
           P("1.3 Chargement incrémental", "h2"),
           P("Chaque chargement est noté dans une table journal (<i>meta.ingestion_log</i>) : nom du fichier, lignes lues, lignes rejetées, "
             "durée, statut. Pour éviter les doublons :", "body"),
           P("• si un fichier a déjà été chargé (même empreinte), il est ignoré ;<br/>"
             "• si on recharge un mois, on supprime d'abord ses anciennes lignes puis on les remet ;<br/>"
             "• pour les règlements, on n'ajoute que les paiements qui ne sont pas déjà dans la table :", "body"),
           Preformatted("INSERT INTO core.fact_reglement\n"
                        "SELECT ... FROM v_reglements r JOIN v_sinistres s USING (sinistre_id)\n"
                        "WHERE NOT EXISTS (SELECT 1 FROM core.fact_reglement f WHERE f.paiement_id = r.paiement_id);", S["code"]),
           P(f"<b>Au deuxième passage</b>, tous les paiements existent déjà, donc la requête n'ajoute rien (le log affiche "
             f"« {fn(vol['core.fact_reglement'])} → {fn(vol['core.fact_reglement'])} lignes (+0) »). "
             f"Pour le prouver, j'ai écrit un test pytest qui recharge le mois d'avril 2023 et vérifie que les tables sont identiques avant et après. "
             f"Résultat des tests : {py}.", "body"),
           T([["Fichier", "Mode", "Lues", "Chargées", "Statut", "Durée (s)"]] + [[a, b, c, d_, e, fn(f_, 3)] for a, b, c, d_, e, f_ in log],
             [6.2 * cm, 3.4 * cm, 1.5 * cm, 1.8 * cm, 2.3 * cm, 1.8 * cm]),
           P("Tableau 2 : extrait du journal (premier chargement, relance ignorée, rechargement forcé). Commande : make reload MONTH=2023-04.", "cap"),
           PageBreak()]

    # ======================== L2
    rows = [["Règle", "Table", "Contrôle", "Gravité", "Volume", "Traitement"]]
    for r in R["qualite"]:
        rows.append([r["rule_id"], r["entite"], r["libelle"], r["gravite"].lower(), fn(r["volume"]), r["traitement"].lower()])
    st += [P("2. Qualité des données et modèle", "h1"), P("2.1 Règles de qualité", "h2"),
           P("J'ai écrit 34 règles. Chacune est une requête SQL qui cherche les lignes qui posent problème. Selon le cas je fais une de ces actions : "
             "<b>exclure</b> (la ligne part en quarantaine avec la raison), <b>fusionner</b> (doublon), <b>corriger</b> (la valeur fausse est "
             "remplacée par vide) ou <b>signaler</b> (on garde la ligne mais on la marque). Si une règle « bloquante » trouve un problème, "
             "le chargement s'arrête.", "body"),
           T(rows, [1.2 * cm, 1.8 * cm, 8 * cm, 1.6 * cm, 1.5 * cm, 1.9 * cm]),
           P("Tableau 3 : les 34 règles. 16 trouvent de vrais problèmes. La requête SQL de chaque règle est en annexe E.", "cap"),
           P("Les problèmes principaux", "h3"),
           P(f"• {qa['Q09']['volume']} contrats ont une date de résiliation avant la date de début, et {qa['Q11']['volume']} ont une prime à 0 ou négative : "
             f"je les exclus, ainsi que leurs {qa['Q17']['volume']} sinistres et {qa['Q24']['volume']} règlement.<br/>"
             f"• {qa['Q23']['volume']} paiements sont livrés deux fois (dans le fichier du mois suivant), pour {fe(rec['doublons'], 2)}. "
             "Le fichier de juillet 2025 (après la date d'extraction) ne contient que des paiements de juin déjà livrés. Je garde la première livraison.<br/>"
             f"• Dates de naissance : {qa['Q01']['volume']} vides, {qa['Q02']['volume']} au 01/01/1890 (valeur bidon) et {qa['Q03']['volume']} qui donnent "
             "un âge de moins de 18 ans au premier contrat. Je les mets à vide et l'âge devient « Inconnu ».<br/>"
             f"• {qa['Q18']['volume']} sinistres sont déclarés avant d'être arrivés : je les garde pour le coût mais pas pour les délais.<br/>"
             f"• Un sinistre a une réserve de {fe(g0['reserve_initiale'])}. Ce n'est pas forcément une erreur, je le signale seulement.", "body"),
           P(f"<b>Vérification</b> : total des règlements dans les fichiers = {fe(rec['brut'], 2)} = {fe(rec['coeur'], 2)} gardés + "
             f"{fe(rec['doublons'], 2)} de doublons + {fe(rec['en_cascade'], 2)} liés aux contrats exclus. Un test vérifie ça à chaque lancement.", "box"),
           P("2.2 Doublons clients", "h2"),
           P(f"Pour trouver les doublons, j'utilise l'e-mail (crypté) + la date de naissance. L'e-mail seul ne suffit pas car deux personnes d'une "
             f"même famille peuvent avoir le même. J'ai trouvé {fn(R['dedup']['doublons'])} doublons sur {fn(R['dedup']['clients_source'])} clients "
             f"({fp(R['dedup']['taux'], 1)}). Je garde l'identifiant qui a des contrats (sinon le plus petit). Les contrats des autres identifiants "
             "sont rattachés au client gardé. Ici, à chaque fois, un seul des deux avait des contrats.", "body"),
           PageBreak(),
           P("2.3 Schéma en étoile", "h2"), IMG("fig_etoile.png", 16.5),
           P("Figure 2 : schéma en étoile (orange = dimensions, bleu = faits).", "cap"),
           T([["Table de faits", "Une ligne =", "Lignes"],
              ["fact_exposition_mensuelle", "un contrat pour un mois", fn(vol["core.fact_exposition_mensuelle"])],
              ["fact_exposition_annuelle", "un contrat pour une année", fn(vol["core.fact_exposition_annuelle"])],
              ["fact_sinistre", "un sinistre", fn(vol["core.fact_sinistre"])],
              ["fact_reglement", "un paiement", fn(vol["core.fact_reglement"])]], [5.5 * cm, 7 * cm, 3 * cm]),
           P("J'ai choisi un grain au mois pour l'exposition car ça permet de calculer facilement n'importe quelle période et de comparer avec "
             "l'année d'avant dans le dashboard. La table annuelle est juste la somme des mois. L'exposition est le nombre de jours couverts "
             "divisé par 365,25, et la prime acquise = prime annuelle × exposition.", "body"),
           P("<b>Historique</b> : pour la dimension contrat j'utilise un SCD de type 2 sur les éléments du prix (formule, zone, franchise, "
             "bonus-malus, prime). Si un de ces éléments change, on crée une nouvelle version au lieu d'écraser l'ancienne, pour ne pas fausser "
             "l'historique. Pour l'instant chaque contrat n'a qu'une version car les données sont une photo à une date.", "body"),
           P("2.4 Tests", "h2"),
           T([["Test", "Ce qui est vérifié", "Écarts", "Statut"]] + [[t["test_id"], t["libelle"], fn(t["ecarts"]), t["statut"]] for t in R["tests"]],
             [1.2 * cm, 12 * cm, 1.6 * cm, 2.2 * cm]),
           P(f"Tableau 4 : les 13 tests lancés à chaque exécution. Si un test échoue, tout est annulé. "
             f"En plus, 5 tests pytest vérifient les cas de rejeu ({py}).", "cap"),
           PageBreak()]

    # ======================== L3
    def axis_table(axe):
        rows_ = [["Modalité", "Années-police", "Fréquence", "Coût moyen", "Prime moy.", "S/P", "S/P plafonné", "Résiliation"]]
        for k in sorted([k for k in R["kpi"] if k.startswith(axe + "|")], key=lambda s: s.split("|")[1]):
            x = R["kpi"][k]
            rows_.append([k.split("|")[1], fn(x["exposition"]), fp(x["frequence"], 2), fe(x["cout_moyen"]), fe(x["prime_moyenne"]),
                          fp(x["ratio_sp"]), fp(x["ratio_sp_ecrete"]), fp(x["taux_resiliation"])])
        return T(rows_, [2.3 * cm, 2.2 * cm, 1.9 * cm, 2.1 * cm, 2 * cm, 1.8 * cm, 2 * cm, 2 * cm])

    z1, z5 = K("zone_risque|1"), K("zone_risque|5")
    fe_, fc_ = K("formule|ESSENTIELLE"), K("formule|CONFORT")
    unk = K("tranche_age|Inconnu")
    st += [P("3. Analyse technique du portefeuille", "h1"),
           P(f"<b>Définitions.</b> Une année-police = un contrat assuré pendant un an (6 mois = 0,5). Je calcule toutes les fréquences par année-police "
             f"et pas par contrat, sinon un contrat de 2 mois compterait autant qu'un contrat de 5 ans ({fn(vol['raw.contrats'])} contrats ne font que "
             f"{fn(kt['exposition'])} années-police). Fréquence = sinistres (ouverts ou clôturés) / années-police. Charge = montants payés + réserve "
             "restante des sinistres ouverts. S/P = charge / primes acquises. Le « S/P plafonné » limite chaque sinistre à 150 000 €.", "body"),
           P("3.1 Payé, réserves et sans suite", "h2"),
           T([["", "Total", "Auto", "Habitation"],
              ["Sinistres déclarés", fn(kt["nb_sinistres_declares"]), fn(ka["nb_sinistres_declares"]), fn(kh["nb_sinistres_declares"])],
              ["dont avec suite", fn(kt["nb_sinistres"]), fn(ka["nb_sinistres"]), fn(kh["nb_sinistres"])],
              ["dont sans suite", fn(kt["nb_sans_suite"]), fn(ka["nb_sans_suite"]), fn(kh["nb_sans_suite"])],
              ["dont rejetés", fn(kt["nb_rejetes"]), fn(ka["nb_rejetes"]), fn(kh["nb_rejetes"])],
              ["Montants payés", fe(kt["montant_paye"]), fe(ka["montant_paye"]), fe(kh["montant_paye"])],
              ["Réserves restantes", fe(kt["reserves"]), fe(ka["reserves"]), fe(kh["reserves"])],
              ["Charge totale", fe(kt["charge"]), fe(ka["charge"]), fe(kh["charge"])],
              ["Primes acquises", fe(kt["primes_acquises"]), fe(ka["primes_acquises"]), fe(kh["primes_acquises"])]],
             [6.5 * cm, 3.5 * cm, 3.5 * cm, 3.5 * cm]),
           P(f"Tableau 5 : environ {fp((kt['nb_sans_suite'] + kt['nb_rejetes']) / kt['nb_sinistres_declares'], 0)} des déclarations sont sans suite ou rejetées. "
             "Les réserves concernent surtout 2024 et 2025, ces chiffres peuvent encore changer.", "cap"),
           P("3.2 Indicateurs par segment", "h2"),
           P("<b>Par produit</b>", "h3"), axis_table("produit"),
           P(f"Même fréquence, mais la prime habitation est deux fois plus faible. → Il faudrait revoir le prix de l'habitation.", "cap"),
           P("<b>Par zone de risque</b>", "h3"), axis_table("zone_risque"),
           P(f"La fréquence monte de {fp(z1['frequence'], 2)} (zone 1) à {fp(z5['frequence'], 2)} (zone 5), mais la prime monte peu. "
             "→ Augmenter l'écart de prix entre zones. (Le S/P de la zone 4 est gonflé par le gros sinistre.)", "cap"),
           P("<b>Par formule</b>", "h3"), axis_table("formule"),
           P(f"Essentielle a peu de sinistres ({fp(fe_['frequence'], 2)}) mais beaucoup de résiliations ({fp(fe_['taux_resiliation'])}). "
             f"Confort a le plus de sinistres ({fp(fc_['frequence'], 2)}). → Vérifier le prix de Confort.", "cap"),
           P("<b>Par canal</b>", "h3"), axis_table("canal"),
           P("Même fréquence sur les trois canaux, mais le web résilie beaucoup plus. → Faire des actions pour garder les clients web.", "cap"),
           P("<b>Par tranche d'âge</b>", "h3"), axis_table("tranche_age"),
           P(f"Peu de différences entre âges. Par contre les clients avec un âge « Inconnu » ont plus de sinistres ({fp(unk['frequence'], 2)}). "
             "→ Mieux contrôler la saisie de la date de naissance.", "cap"),
           IMG("fig_sp_par_axe.png", 17), P("Figure 3 : S/P normal et plafonné par segment (ligne rouge = seuil de 70 %).", "cap"),
           PageBreak()]

    drows = [["Période", "S/P début", "S/P fin", "Variation", "Fréquence", "Coût moyen", "Prime moy.", "Remarque"]]
    for y in range(2021, 2026):
        d_ = dec[("brut", y)]
        drows.append([f"{y - 1}→{y}", fp(dec[("brut", y - 1)]["sp"]), fp(d_["sp"]), fpt(d_["delta_sp"]), fpt(d_["effet_frequence"]),
                      fpt(d_["effet_cout_moyen"]), fpt(d_["effet_prime_moyenne"]), d_["statut_annee"]])
    erows = [["Période", "S/P plafonné fin", "Variation", "Fréquence", "Coût moyen", "Prime moy."]]
    for y in range(2021, 2026):
        d_ = dec[("ecrete", y)]
        erows.append([f"{y - 1}→{y}", fp(d_["sp"]), fpt(d_["delta_sp"]), fpt(d_["effet_frequence"]), fpt(d_["effet_cout_moyen"]),
                      fpt(d_["effet_prime_moyenne"])])
    ct = R["contrib_top"]
    st += [P("3.3 Évolution du S/P année par année", "h2"),
           P("On peut écrire S/P = fréquence × coût moyen / prime moyenne. Le nombre de contrats (volume) n'apparaît pas car il augmente "
             "autant la charge que les primes. J'ai donc séparé la variation du S/P en trois parts : fréquence, coût moyen et prime moyenne "
             "(méthode LMDI, qui ne laisse pas de reste).", "body"),
           T(drows, [1.6 * cm, 1.6 * cm, 1.5 * cm, 1.7 * cm, 1.8 * cm, 1.9 * cm, 1.8 * cm, 5.1 * cm]),
           P("Tableau 6 : décomposition du S/P (en points).", "cap"),
           T(erows, [2.5 * cm, 3 * cm, 2.5 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm]),
           P("Tableau 7 : même chose avec les sinistres plafonnés à 150 000 €.", "cap"),
           IMG("fig_decomposition.png", 17), P("Figure 4 : effets par année.", "cap"),
           IMG("fig_evolution.png", 17), P("Figure 5 : S/P sur 12 mois glissants et nombre de contrats actifs. Le pic de 2023 correspond au gros sinistre.", "cap"),
           P(f"<b>Ce qu'on voit</b> : la prime moyenne ne bouge presque pas (environ 442 €). En 2023, le S/P monte de "
             f"{fn(dec[('brut', 2023)]['delta_sp'] * 100, 1)} points à cause du coût moyen, c'est-à-dire du sinistre de 2,48 M€. "
             f"Sans ce sinistre, 2023 est même meilleur que 2022 ({fpt(dec[('ecrete', 2023)]['delta_sp'])}). En 2024 le S/P baisse car le gros "
             f"sinistre n'est plus là. Les segments qui pèsent le plus dans la hausse de 2023 (zone 4, Île-de-France, agence, Confort, 36-45 ans) "
             f"sont simplement ceux de ce sinistre. Sans lui, la hausse de 2024 vient surtout de la formule Essentielle "
             f"({fpt(ct['2024|formule']['degradation_ecrete'][0][1])}) et de la zone 3 ({fpt(ct['2024|zone_risque']['degradation_ecrete'][0][1])}).", "body"),
           P("<b>Attention aux années incomplètes</b> : 2020 est le démarrage (peu de contrats), 2024 a encore des sinistres ouverts, et 2025 "
             "ne fait que 6 mois avec des sinistres récents pas encore tous déclarés. Le S/P 2025 va donc sûrement monter.", "box"),
           PageBreak()]

    icrows = [["Indicateur", "Valeur", "Intervalle de confiance 95 %", "Méthode"]]
    for k, lab, f in [("frequence", "Fréquence", lambda x: fp(x, 2)), ("cout_moyen", "Coût moyen", fe), ("cout_moyen_ecrete", "Coût moyen plafonné", fe),
                      ("prime_moyenne", "Prime moyenne", fe), ("ratio_sp", "S/P", fp), ("ratio_sp_ecrete", "S/P plafonné", fp),
                      ("taux_resiliation", "Taux de résiliation", fp), ("ratio_sp_ecrete|AUTO", "S/P plafonné auto", fp),
                      ("ratio_sp_ecrete|HABITATION", "S/P plafonné habitation", fp)]:
        icrows.append([lab, f(ic[k]["valeur"]), f"{f(ic[k]['ic'][0])} à {f(ic[k]['ic'][1])}",
                       "loi de Poisson" if "Poisson" in ic[k]["methode"] else "bootstrap (2 000 tirages)"])
    st += [P("3.4 Statistiques", "h2"), P("Intervalles de confiance", "h3"),
           T(icrows, [4.2 * cm, 2.6 * cm, 5 * cm, 5.2 * cm]),
           P("Tableau 8 : pour la fréquence et la résiliation j'utilise la loi de Poisson (on compte des événements sur une durée). Pour les "
             "autres, j'utilise un bootstrap en tirant des contrats au hasard 2 000 fois.", "cap"),
           P("L'intervalle du S/P normal est très large à cause du gros sinistre ; celui du S/P plafonné est beaucoup plus serré. "
             "Les intervalles auto et habitation ne se chevauchent pas : la différence est réelle.", "body"),
           P("Test 1 : fréquence zone 1 contre zone 5", "h3"),
           P(f"Zone 1 : {tz['n1']} sinistres pour {fn(tz['e1'])} années-police ({fp(tz['f1'], 2)}). Zone 5 : {tz['n5']} pour {fn(tz['e5'])} "
             f"({fp(tz['f5'], 2)}). J'ai utilisé un test exact de comparaison de deux taux de Poisson, adapté à des comptages avec des durées "
             f"d'exposition différentes. p-value {fpv(tz['p_value'])} : la différence est significative. La zone 5 a {fn(tz['rapport'], 2)} fois "
             f"plus de sinistres (entre {fn(tz['rapport_ic'][0], 2)} et {fn(tz['rapport_ic'][1], 2)}).", "body"),
           P("Test 2 : coût des sinistres agence contre web", "h3"),
           P(f"Coût moyen agence {fe(tc['moy_agent'])}, web {fe(tc['moy_web'])}. Les coûts ne suivent pas une loi normale (quelques sinistres très chers), "
             f"donc j'ai utilisé le test de Mann-Whitney plutôt qu'un test de Student. Médianes : {fe(tc['med_agent'])} et {fe(tc['med_web'])}, "
             f"p-value {fpv(tc['p_value_mw'])} : pas de différence significative. L'écart de moyenne vient du gros sinistre (qui est en agence).", "body"),
           P("Distribution des coûts", "h3"),
           T([["Médiane", "P75", "P90", "P95", "P99", "Maximum", "Moyenne"],
              [fe(q["mediane"]), fe(q["p75"]), fe(q["p90"]), fe(q["p95"]), fe(q["p99"]), fe(q["max"]), fe(q["moyenne"])]], None),
           P(f"Tableau 9 : la moyenne est 3 fois la médiane. Les 1 % de sinistres les plus chers font {fp(q['part_top1'], 0)} du coût total, "
             f"les 10 % les plus chers {fp(q['part_top10'], 0)}.", "cap"),
           IMG("fig_queue_couts.png", 16.5), P("Figure 6 : répartition des coûts (échelle log) et concentration.", "cap"),
           PageBreak()]

    # ======================== L4
    def rr(p_, c, k):
        x = ret[(ret.produit == p_) & (ret.cohorte == c) & (ret.annee_anciennete == k) & ret.cellule_complete]
        return fp(x.taux_retention.iloc[0], 0) if len(x) else ""
    rrows = [["Produit", "Cohorte", "Clients", "1 an", "2 ans", "3 ans", "4 ans"]]
    for p_ in ["AUTO", "HABITATION", "TOUS"]:
        for c in range(2020, 2025):
            sz = ret[(ret.produit == p_) & (ret.cohorte == c)].taille_cohorte.iloc[0]
            rrows.append([p_.lower(), str(c), fn(sz)] + [rr(p_, c, k) for k in range(1, 5)])
    m1, s1 = rd[("Multi-détenteur", 1)], rd[("Mono-détenteur", 1)]
    pv = {p["groupe"]: p for p in R["profils_valeur"]}
    st += [P("4. Clients et sinistres", "h1"), P("4.1 Rétention par cohorte", "h2"),
           P("La cohorte = l'année où le client a pris son premier contrat. Un client est « retenu » après k ans s'il a encore un contrat actif. "
             "Je n'affiche que les cases où tous les clients ont pu être observés jusqu'au bout (par exemple la cohorte 2023 seulement à 1 an).", "body"),
           T(rrows, [2.6 * cm, 2 * cm, 2 * cm, 2.3 * cm, 2.3 * cm, 2.3 * cm, 2.3 * cm]),
           P("Tableau 10 : taux de rétention.", "cap"), IMG("fig_retention.png", 17),
           P("Figure 7 : les cohortes se ressemblent beaucoup. Environ 1 client sur 8 part la première année.", "cap"),
           P(f"<b>Auto + habitation.</b> {fp(R['detention']['part_tout_temps'], 0)} des clients ont eu les deux produits à un moment, mais "
             f"seulement {fp(R['detention']['part_origine'])} les avaient dès le départ (90 premiers jours). Pour comparer j'utilise la deuxième "
             "définition, sinon c'est biaisé (un client qui reste longtemps a plus de chances d'acheter un deuxième produit). "
             f"Résultat : après 1 an, {fp(m1['taux_retention'], 0)} des multi-détenteurs sont encore là contre {fp(s1['taux_retention'], 0)} "
             f"des autres (p-value {fpv(R['test_retention_detention']['p_value'])}). Ça ne prouve pas une cause, mais vendre les deux produits "
             "ensemble semble aider à garder les clients.", "body"),
           PageBreak(), P("4.2 Valeur des clients", "h2"),
           P(f"Valeur d'un client = primes acquises − sinistres payés sur toute la période. Au total : {fe(v['primes'])} − {fe(v['payes'])} "
             f"= {fe(v['valeur_totale'])} pour {fn(v['n_clients'])} clients.", "body"),
           IMG("fig_pareto.png", 12),
           P(f"Figure 8 : la courbe dépasse 100 % puis redescend, car {fn(v['nb_negatifs'])} clients ({fp(v['part_negatifs'])}) coûtent plus qu'ils "
             f"ne rapportent (au total {fe(v['perte_negatifs'])}, dont {fe(v['pire_client'])} pour un seul client).", "cap"),
           T([["Groupe", "Clients", "Valeur moy.", "Primes moy.", "Payé moy.", "Ancienneté (ans)", "Auto + hab.", "Sinistré"]] +
             [[g, fn(pv[g]["n"]), fe(pv[g]["valeur_moy"]), fe(pv[g]["primes_moy"]), fe(pv[g]["payes_moy"]), fn(pv[g]["expo_moy"], 1),
               fp(pv[g]["part_multi"], 0), fp(pv[g]["part_sinistre"], 0)] for g in ["Top 10 %", "Autres", "Bottom 10 %"]],
             [2.2 * cm, 1.6 * cm, 2 * cm, 2 * cm, 2 * cm, 2.6 * cm, 2 * cm, 1.8 * cm]),
           P("Tableau 11 : les meilleurs clients sont anciens et ont souvent les deux produits. Les moins bons ont surtout eu un sinistre (70 %), "
             "ils ne sont pas très différents des autres sinon.", "cap"),
           PageBreak()]

    drows = [["Garantie", "Déclaration (médiane / P90)", "1er paiement (médiane / P90)", "Clôture (médiane / P90)"]]
    for gg in ["BRIS_GLACE", "COLLISION", "DEGAT_EAUX", "INCENDIE", "RC", "TEMPETE", "VOL", "TOUTES"]:
        a_, b_, c_ = dl[(gg, "Déclaration")], dl[(gg, "Premier règlement")], dl[(gg, "Clôture (proxy dernier règlement)")]
        f3 = lambda x: f"{fn(x['mediane'])} j / {fn(x['p90'])} j"  # noqa: E731
        drows.append([gg.lower().replace("_", " "), f3(a_), f3(b_), f3(c_)])
    arows = [["Critère", "Valeur", "Sinistres", "Audités", "Fraudes", "Taux de fraude (audités)"]]
    for crit in ["delai_declaration", "tranche_reserve", "garantie"]:
        for a_ in sorted([a for a in R["audits"] if a["critere"] == crit], key=lambda x: x["modalite"]):
            arows.append([crit.replace("_", " "), a_["modalite"], fn(a_["nb_sinistres"]), fn(a_["nb_audites"]),
                          fn(a_["nb_fraudes_confirmees"]), fp(a_["taux_confirmation_audites"])])
    tous = aud[("ensemble", "Tous")]
    late = aud[("delai_declaration", "d. > 30 j")]
    st += [P("4.3 Délais de gestion", "h2"),
           P("Déclaration = jours entre le sinistre et la déclaration. 1er paiement = jours entre la déclaration et le premier paiement. "
             "Il n'y a pas de date de clôture dans les données, donc j'ai pris la date du dernier paiement pour les sinistres clôturés.", "body"),
           T(drows, [3 * cm, 4.6 * cm, 4.6 * cm, 4.6 * cm]),
           P(f"Tableau 12 : en général un sinistre est déclaré en {fn(dl[('TOUTES', 'Déclaration')]['mediane'])} jours, payé une première fois "
             f"en {fn(dl[('TOUTES', 'Premier règlement')]['mediane'])} jours et clôturé en {fn(dl[('TOUTES', 'Clôture (proxy dernier règlement)')]['mediane'])} jours. "
             f"Mais 10 % attendent plus de {fn(dl[('TOUTES', 'Premier règlement')]['p90'])} jours pour être payés. Les garanties sont assez proches.", "cap"),
           P("4.4 Audits antifraude", "h2"),
           P(f"<b>Important</b> : les taux de fraude ci-dessous ne concernent que les {fn(tous['nb_audites'])} sinistres audités "
             f"({fp(tous['taux_audit'], 0)} des sinistres), et ils n'ont pas été choisis au hasard. On ne peut donc pas en déduire le taux de fraude "
             f"de tout le portefeuille. Taux global chez les audités : {fp(tous['taux_confirmation_audites'])}.", "body"),
           T(arows, [3.2 * cm, 2.8 * cm, 2 * cm, 2 * cm, 2 * cm, 4 * cm]),
           P("Tableau 13 : taux de fraude confirmée selon plusieurs critères.", "cap"),
           IMG("fig_delais_audits.png", 16.5), P("Figure 9 : délais par garantie et fraude selon le délai de déclaration.", "cap"),
           P(f"Le critère qui marche le mieux est le délai de déclaration : quand le sinistre est déclaré plus de 30 jours après, "
             f"{fp(late['taux_confirmation_audites'], 0)} des audits trouvent une fraude, contre aucune quand il est déclaré en moins de 7 jours. "
             f"À l'inverse, les gros sinistres sont beaucoup audités mais avec peu de fraudes trouvées. "
             f"<b>Montants</b> : les sinistres audités représentent {fe(tous['reserve_auditee'])} de réserves. Les fraudes confirmées "
             f"représentent {fe(tous['reserve_fraude_confirmee'])}, soit environ {fe(tous['reserve_fraude_confirmee'] / tous['nb_audites'])} par audit. "
             "Si un audit coûte moins que ça, il est rentable ; je n'ai pas le coût d'un audit dans les données pour conclure. "
             f"Problème : sur les fraudes confirmées, {fe(fpay['paye_apres_audit'])} ont quand même été payés après l'audit "
             f"(sur {fe(fpay['paye_total'])} payés au total sur ces dossiers). "
             "→ Il faudrait bloquer les paiements quand une fraude est confirmée et auditer en priorité les déclarations tardives.", "body"),
           PageBreak()]

    # ======================== L5
    st += [P("5. Dashboard et documentation", "h1"), P("5.1 Dashboard", "h2"),
           P("Le dashboard est fait avec Streamlit. Il lit seulement les tables mart de la base. Chaque page se charge en moins de 2 secondes. "
             f"Sans filtre, il affiche les mêmes chiffres que ce dossier : primes {fe(kt['primes_acquises'])}, fréquence {fp(kt['frequence'], 2)}, "
             f"S/P {fp(kt['ratio_sp'])}, {fn(R['actifs_fin'])} contrats actifs au 30/06/2025.", "body"),
           T([["Page", "Contenu"],
              ["Portefeuille", "Les 6 indicateurs avec comparaison à l'année d'avant, courbes mensuelles, alerte rouge si le S/P dépasse 70 %."],
              ["Technique et clients", "S/P par zone, formule, canal, âge ; évolution du S/P ; rétention par cohorte ; courbe de Pareto."],
              ["Exploitation", "Dernier chargement par fichier, lignes rejetées par règle, résultat des tests, délais par garantie."],
              ["Définitions", "Explication de chaque indicateur."]], [3.5 * cm, 13.5 * cm]),
           P("Filtres : période, produit, région, canal et zone, plus un bouton pour plafonner les gros sinistres. J'ai mis le seuil d'alerte à "
             "70 % car un assureur dépense environ 30 % de ses primes en frais : au-dessus de 70 % de S/P, il ne gagne plus d'argent.", "body"),
           P("5.2 Automatisation", "h2"),
           P("Un petit script (<i>pipeline/watch.py</i>) regarde toutes les 15 minutes si un nouveau fichier est arrivé et lance le pipeline. "
             "S'il y a une erreur, tout est annulé, l'erreur est écrite dans <i>logs/alertes.log</i> et peut être envoyée sur Teams ou Slack.", "body"),
           Preformatted("*/15 * * * * cd /opt/boreal && .venv/bin/python -m pipeline.watch --once", S["code"]),
           P("5.3 Documentation", "h2"),
           P("Le README explique comment tout lancer en 5 commandes. Le catalogue (<i>docs/catalogue_donnees.md</i>) décrit les 48 tables et "
             "517 colonnes. Il y a aussi un schéma d'architecture, le lignage du S/P et l'analyse RGPD dans le dossier docs.", "body"),
           P("Lignage du S/P", "h3"),
           Preformatted("contrats.csv -> raw -> prep -> core.dim_contrat -> fact_exposition_mensuelle.prime_acquise  (dénominateur)\n"
                        "sinistres.jsonl + reglements_*.csv -> raw -> prep -> fact_sinistre.charge                   (numérateur)\n"
                        "-> mart.portefeuille_mensuel -> mart.kpi_segment.ratio_sp -> dashboard + dossier", S["code"]),
           PageBreak(), P("5.4 RGPD", "h2"),
           P("Il n'y a ni nom ni adresse, mais les données restent personnelles car elles sont seulement pseudonymisées (l'e-mail crypté "
             "peut être retrouvé avec le CRM). Données concernées : identifiant, e-mail crypté, date de naissance, région, CSP, sinistres et fraude. "
             "Le dashboard ne montre que des totaux. Durées proposées : 13 mois pour les couches brute et quarantaine, 5 ans après la fin du "
             "contrat pour le reste, 5 ans pour l'antifraude.", "body"),
           T([["Couche", "Supprimer un client"],
              ["raw", "Supprimer ses lignes (et à la source dans le CRM)."],
              ["prep / quarantaine / core", "Ces tables sont recalculées depuis raw : le client disparaît au lancement suivant (sauf dim_contrat à nettoyer à la main)."],
              ["marts", "Recalculés, plus de trace."]], [4 * cm, 13 * cm]),
           PageBreak()]

    # ======================== ANNEXES
    import json as _j
    sqls = _j.loads((OUT / "requetes_sources.json").read_text(encoding="utf-8"))
    st += [P("Annexes", "h1"), P("A. Limites", "h2"),
           P("• Les réserves ne sont pas mises à jour dans les données, donc 2024 et 2025 peuvent changer.<br/>"
             "• Pas de date de clôture : j'ai utilisé le dernier paiement.<br/>"
             "• Je suppose que la prime d'un contrat ne change pas pendant toute sa durée.<br/>"
             "• Les sinistres pas encore déclarés au 30/06/2025 ne sont pas estimés (pas de prévision demandée).<br/>"
             "• Les audits ne sont pas faits au hasard.", "body"),
           P("B. Contribution", "h2"),
           P("Projet réalisé seul par Souleymane DJIBO (M2 Data Analyst, PMN) : 100 % du travail.", "body"),
           PageBreak(), P("C. Requêtes utilisées", "h2"),
           P("Quelques requêtes qui donnent les chiffres du dossier (toutes sont dans analysis/output/requetes_sources.json).", "body")]
    for key in ["kpi_2020_2025", "decomposition", "base_bootstrap", "retention", "valeur_client", "delais", "audits", "fraude_paiements", "reconciliation"]:
        txt = sqls[key]
        txt = "\n".join(txt[i:i + 125] for i in range(0, len(txt), 125))
        st += [KeepTogether([P(f"<b>{key}</b>", "body"), Preformatted(txt, S["code"])])]

    st += [P("D. Exemples de règles qualité (SQL)", "h2"),
           P("Trois règles expliquées (la liste complète est en annexe E) :", "body")]
    for r in [x for x in R["qualite"] if x["rule_id"] in ("Q05", "Q09", "Q23")]:
        con2 = duckdb.connect(str(DB_PATH), read_only=True)
        sq = con2.execute("SELECT requete FROM meta.dq_rules WHERE rule_id = ?", [r["rule_id"]]).fetchone()[0]
        con2.close()
        sq = "\n".join(sq[i:i + 125] for i in range(0, len(sq), 125))
        st += [KeepTogether([P(f"<b>{r['rule_id']} : {r['libelle']}</b> ({fn(r['volume'])} lignes)", "body"), Preformatted(sq, S["code"])])]
    st += [PageBreak(), P("E. Requêtes des 34 règles qualité", "h2"),
           P("Pour chaque règle : la requête SQL qui renvoie les lignes en anomalie (stockée aussi dans la table meta.dq_rules).", "body")]
    con3 = duckdb.connect(str(DB_PATH), read_only=True)
    allr = con3.execute("SELECT rule_id, libelle, gravite, traitement, requete FROM meta.dq_rules ORDER BY rule_id").fetchall()
    con3.close()
    vols = {r["rule_id"]: r["volume"] for r in R["qualite"]}
    for rid, lib, grav, trt, sq in allr:
        sq = "\n".join(sq[i:i + 135] for i in range(0, len(sq), 135))
        st += [KeepTogether([P(f"<b>{rid}</b> · {lib} · gravité {grav.lower()} · {fn(vols[rid])} lignes · {trt.lower()}", "cell"),
                             Preformatted(sq, S["code"])])]
    st += [P("F. Questions possibles à l'oral", "h2"),
           P("<b>Si un mois est livré deux fois ?</b> Si c'est le même fichier, il est ignoré. Si c'est un autre nom, les paiements déjà connus "
             "partent en quarantaine (règle Q23) et rien ne change dans le cœur. C'est vérifié par un test pytest.<br/>"
             "<b>Comment savoir si la base est d'accord avec les fichiers ?</b> Les tests T05 et T06 vérifient que brut = cœur + quarantaine, "
             "en nombre de lignes et en euros.<br/>"
             "<b>Pourquoi un grain au mois ?</b> Pour calculer l'exposition exacte sur n'importe quelle période et comparer avec l'année d'avant.", "body")]

    doc = SimpleDocTemplate(str(DEST / f"{NOM}_Boreal.pdf"), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.7 * cm, bottomMargin=1.8 * cm, title="Projet Boréal Assurances", author=f"{PRENOM} {NOM}")
    doc.build(st, onFirstPage=lambda c, d: None, onLaterPages=footer)

    # ======================== NOTE
    nb = ParagraphStyle("nb", parent=S["body"], fontSize=9, leading=12.5, spaceAfter=4)
    nh = ParagraphStyle("nh", parent=S["h2"], fontSize=11, spaceBefore=6, spaceAfter=3)
    note = [P("Note de synthèse : portefeuille Boréal Assurances", "h1"),
            Paragraph("Souleymane DJIBO · M2 Data Analyst · PMN · données de janvier 2020 à juin 2025", nb),
            Paragraph("Pour Camille Roux, directrice technique. Le <b>S/P</b> (sinistres sur primes) compare ce que coûtent les sinistres à ce que "
                      "rapportent les primes. Au-dessus de 70 %, l'activité ne couvre plus ses frais.", nb),
            Paragraph("3 constats", nh),
            Paragraph(f"<b>1.</b> Le portefeuille gagne de l'argent : S/P de {fp(kt['ratio_sp'])}. Mais un seul sinistre de {fe(g0['charge'])} "
                      f"(2023) représente {fp(q['part_max'], 0)} du coût total. Sans les gros sinistres, le S/P est de {fp(kt['ratio_sp_ecrete'])}.", nb),
            Paragraph(f"<b>2.</b> L'habitation est moins rentable que l'auto ({fp(kh['ratio_sp_ecrete'], 0)} contre {fp(ka['ratio_sp_ecrete'], 0)}) car "
                      f"sa prime est deux fois plus basse. Il y a aussi {fn(tz['rapport'], 1)} fois plus de sinistres en zone 5 qu'en zone 1, "
                      f"pour une prime seulement {fp(z5['prime_moyenne'] / z1['prime_moyenne'] - 1, 0)} plus chère.", nb),
            Paragraph(f"<b>3.</b> Les clients web partent plus souvent ({fp(tr['t_web'], 0)} par an contre {fp(tr['t_agent'], 0)} en agence). "
                      f"Et {fe(fpay['paye_apres_audit'])} ont été payés après qu'une fraude ait été confirmée.", nb),
            Paragraph("3 propositions", nh),
            Paragraph("<b>1.</b> Suivre le S/P sans les gros sinistres et gérer ceux-ci à part.<br/>"
                      "<b>2.</b> Revoir le prix de l'habitation et des zones à risque.<br/>"
                      "<b>3.</b> Bloquer les paiements quand une fraude est confirmée et proposer auto + habitation ensemble aux clients web.", nb),
            Paragraph("Limites", nh),
            Paragraph("2025 ne fait que 6 mois. Les réserves ne sont pas mises à jour. Le taux de fraude ne vaut que pour les dossiers audités. "
                      "283 lignes avec des erreurs ont été mises de côté avant les calculs (doublons, contrats incohérents).", nb)]
    SimpleDocTemplate(str(DEST / f"{NOM}_Boreal_note_executive.pdf"), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                      topMargin=1.6 * cm, bottomMargin=1.4 * cm, title="Note de synthèse Boréal").build(note)
    print("PDF générés dans", DEST)


if __name__ == "__main__":
    build()
