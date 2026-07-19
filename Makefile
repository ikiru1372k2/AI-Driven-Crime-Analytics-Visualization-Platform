.PHONY: lint test build backend-dev frontend-dev deploy-backend deploy-frontend

deploy-backend:
	bash scripts/catalyst/deploy_backend.sh

deploy-frontend:
	bash scripts/catalyst/deploy_frontend.sh

lint:
	cd backend && ruff check .

test:
	cd backend && python -m pytest -q

build:
	cd frontend && npm run build

backend-dev:
	cd backend && KAVACH_DEV_AUTH=1 uvicorn kavach.api.main:app --reload --port 8000

frontend-dev:
	cd frontend && npm run dev
