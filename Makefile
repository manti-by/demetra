run-demetra:
	uv run main.py --project-name demetra

run-odin:
	uv run main.py --project-name odin

run-coruscant:
	uv run main.py --project-name coruscant

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

pip:
	uv sync --all-extras --dev

update:
	uv run uv-bump
	uv sync --all-extras --dev
	uv run pre-commit autoupdate

test:
	uv run pytest tests/

ci: pip check test


api:
	uv run uvicorn demetra.api:app --port 8081 --workers 2

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
