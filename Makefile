run-demetra:
	uv run main.py --project-name demetra --no-auto

run-demetra-auto:
	uv run main.py --project-name demetra --auto --plan-loop

run-odin:
	uv run main.py --project-name odin --no-auto

run-coruscant:
	uv run main.py --project-name coruscant --no-auto

run-mgallery-auto:
	uv run main.py --project-name mgallery --auto --plan-loop
		
deploy:
	git pull --ff-only
	uv sync
	cd react && bun install && bun run build
	sudo systemctl daemon-reload
	sudo systemctl restart demetra-api.service
	sudo systemctl restart demetra-react.service
	sudo systemctl restart demetra-watcher.service
	sudo systemctl restart demetra-worker.service
	sudo service nginx reload

check:
	git add .
	uv run ty check
	uv run pre-commit run

install:
	uv sync --all-extras --dev

update:
	uv run uv-bump
	uv sync --all-extras --dev
	uv run pre-commit autoupdate

test:
	DB_NAME=test_demetra uv run pytest tests/

test-cov:
	DB_NAME=test_demetra uv run pytest tests/ --cov=demetra --cov-report=term-missing --cov-report=html --cov-fail-under=65

migrate:
	uv run alembic upgrade head

ci: install check test react-build react-test


uvicorn:
	uv run uvicorn demetra.app:app --host 0.0.0.0 --port 8081 --workers 2

fastapi:
	uv run fastapi dev demetra/app.py --host 0.0.0.0 --port 8081

mcp:
	uv run python -m demetra.mcp_server

worker:
	uv run rq worker

watcher:
	uv run -m demetra.watcher

react-install:
	cd react && bun install

react-build:
	cd react && bun run build

react-dev:
	cd react && bun run dev --host

react-test:
	cd react && bun run test
