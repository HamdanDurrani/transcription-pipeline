.PHONY: install install-dev run test lint docker-up docker-down

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

install-dev: install
	.venv/bin/pip install -r requirements-dev.txt

run:
	.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	.venv/bin/pytest -q

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down
