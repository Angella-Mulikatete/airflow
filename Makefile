PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip

.PHONY: setup ingest transform run serve chaos

setup:
	python3 -m venv .venv
	$(PIP) install --upgrade pip -q
	$(PIP) install -r requirements.txt -q

ingest:
	$(PYTHON) -m src.ingest

transform:
	$(PYTHON) -m src.transform

run: ingest transform

serve:
	$(PYTHON) -m uvicorn api.main:app --host 0.0.0.0 --port 8000

chaos:
	$(PYTHON) -m scripts.chaos_test
