.PHONY: setup dev check
setup:
	python3 -m venv backend/.venv
	backend/.venv/bin/python -m pip install -r backend/requirements.txt
	cd frontend && npm ci

dev:
	python3 scripts/dev.py

check:
	cd backend && .venv/bin/python -m pytest -q
	cd frontend && npm test && npm run build
