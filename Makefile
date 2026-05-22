run-demetra:
	uv run main.py --project-name demetra --no-auto

run-odin:
	uv run main.py --project-name odin --no-auto

run-coruscant:
	uv run main.py --project-name coruscant --no-auto

deploy:
	git pull --ff-only
	uv sync
	cd hera && bun install && bun run build
	sudo systemctl daemon-reload
	sudo systemctl restart demetra-api.service
	sudo systemctl restart demetra-hera.service
	sudo systemctl restart demetra-watcher.service
	sudo systemctl restart demetra-worker.service
	sudo service nginx reload

check:
	git add .
	uv run ty check
	uv run pre-commit run

pip:
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

ci: pip check test hera-test


api:
	uv run uvicorn demetra.app:app --host 0.0.0.0 --port 8081 --workers 2

worker:
	uv run rq worker

watcher:
	uv run -m demetra.watcher

hera-install:
	cd hera && bun install

hera-build:
	cd hera && bun run build

hera-dev:
	cd hera && bun run dev --host

hera-test:
	cd hera && bun run test
