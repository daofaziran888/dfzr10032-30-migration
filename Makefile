.PHONY: install backend frontend test

install:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd frontend && npm install

backend:
	cd backend && ./run.sh

frontend:
	cd frontend && npm run dev

test:
	cd backend && python3 -I scripts/run_tests.py
	cd backend && python3 -I scripts/run_api_check.py
	cd backend && python3 -I scripts/run_router_smoke.py
