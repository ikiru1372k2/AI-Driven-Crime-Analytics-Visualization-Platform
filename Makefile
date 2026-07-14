.PHONY: lint test build backend-dev frontend-dev

lint:
	cd backend && ruff check .

test:
	cd backend && python -m pytest -q

build:
	cd frontend && npm run build

backend-dev:
	cd backend && uvicorn kavach.api.main:app --reload --port 8000

frontend-dev:
	cd frontend && npm run dev
