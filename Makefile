SHELL := /bin/bash
.PHONY: react docker-up docker-down docker-logs docker-ps docker-migrate docker-clean docker-deploy docker-build

run-demetra:
	uv run main.py --project-name demetra --no-auto

run-demetra-auto:
	uv run main.py --project-name demetra --auto --plan-loop

run-odin:
	uv run main.py --project-name odin --no-auto

run-odin-auto:
	uv run main.py --project-name odin --auto --plan-loop

run-coruscant:
	uv run main.py --project-name coruscant --no-auto

run-coruscant-auto:
	uv run main.py --project-name coruscant --auto --plan-loop

run-mgallery-auto:
	uv run main.py --project-name mgallery --auto --plan-loop

deploy:
	git pull --ff-only
	uv sync
	uv run alembic upgrade head
	cd react && bun install && bun run build
	sudo systemctl daemon-reload
	sudo systemctl restart demetra-api.service
	sudo systemctl restart demetra-react.service
	sudo systemctl restart demetra-watcher.service
	sudo systemctl restart demetra-listener.service
	sudo systemctl restart demetra-worker@{1..4}.service
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
	uv run pytest tests/

test-slow:
	uv run pytest tests/ --durations=10

test-cov:
	uv run pytest tests/ --cov=demetra --cov-report=term-missing --cov-report=html --cov-fail-under=65

migrate:
	uv run alembic upgrade head

ci: install check test react-build react-test


uvicorn:
	uv run uvicorn demetra.app:app --host 0.0.0.0 --port 8081 --workers 4

fastapi:
	uv run fastapi dev demetra/app.py --host 0.0.0.0 --port 8081

mcp:
	uv run python -m demetra.mcp_server

worker:
	uv run rq worker

watcher:
	uv run -m demetra.watcher

react:
	cd react && bun run dev --host

react-install:
	cd react && bun install

react-build:
	cd react && bun run build

react-test:
	cd react && bun run test

docker-build:
	docker build --platform linux/amd64 -t mantiby/demetra:latest .

docker-build-arm:
	docker build --platform linux/arm64 -t mantiby/demetra:arm .

docker-run:
	docker run -e PARENT_HOME=/home/manti/ -v "$(HOME):/home/manti/:ro" demetra

docker-up:
	docker compose --env-file .env.docker up -d --scale worker=4 api worker watcher listener rq-dashboard

docker-down:
	docker compose --env-file .env.docker down

docker-logs:
	docker compose --env-file .env.docker logs -f

docker-ps:
	docker compose --env-file .env.docker ps

docker-migrate:
	docker compose --env-file .env.docker run --rm migrate

docker-clean:
	docker compose --env-file .env.docker down -v --remove-orphans

docker-deploy: docker-build
	docker compose --env-file .env.docker pull db redis react-build || true
	docker compose --env-file .env.docker up --abort-on-container-failure migrate react-build
	docker compose --env-file .env.docker up -d --scale worker=4 api worker watcher listener rq-dashboard
	docker compose --env-file .env.docker ps

container-build:
	container build --tag demetra:latest --file Dockerfile .

gh-use-manti:
	git config user.name "$(MANTI_GIT_NAME)"
	git config user.email "$(MANTI_GIT_EMAIL)"
	git config user.signingkey "$(MANTI_SIGNIN_KEY_ID)"
	gh auth login

gh-use-demetra:
	git config user.name "$(DEMETRA_GIT_NAME)"
	git config user.email "$(DEMETRA_GIT_EMAIL)"
	git config user.signingkey "$(DEMETRA_SIGNIN_KEY_ID)"
	gh auth login
