# Pipeline Boréal Assurances · cibles principales
PY ?= python3
.PHONY: install data run rebuild reload test analyses catalogue report dashboard watch all clean

install:            ## dépendances
	$(PY) -m pip install -r requirements.txt

data:               ## dépose l'archive dans la zone d'atterrissage
	mkdir -p data/landing && $(PY) -c "import zipfile; zipfile.ZipFile('data/archive/sources_boreal.zip').extractall('data/landing')"

run:                ## exécution incrémentale (ingestion → tests bloquants → marts)
	$(PY) -m pipeline.run

rebuild:            ## entrepôt reconstruit de zéro
	$(PY) -m pipeline.run --rebuild

reload:             ## rejeu d'un mois : make reload MONTH=2023-04
	$(PY) -m pipeline.run --reload-month $(MONTH)

test:               ## tests de non-régression (idempotence, rejeu, double livraison, rollback)
	$(PY) -m pytest tests -q

analyses:           ## chiffres et figures du dossier (lus dans l'entrepôt)
	$(PY) -m analysis.analyses

catalogue:          ## catalogue des données
	$(PY) -m docs.generer_catalogue

report: analyses catalogue  ## dossier PDF + note exécutive
	$(PY) -m rapport.build_report

dashboard:          ## lance le dashboard
	$(PY) -m streamlit run dashboard/app.py

watch:              ## déclencheur sur arrivée de fichier (une vérification, à planifier par cron)
	$(PY) -m pipeline.watch --once

all: data rebuild test report

clean:
	rm -f data/warehouse/boreal.duckdb logs/*.log
