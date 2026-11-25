SHELL := /bin/bash
.PHONY: deploy deploy-steps deploy-ui deploy-ui-steps worker-swap worker-swap-steps worker-bootstrap worker-bootstrap-steps react docker-test docker-up docker-down docker-logs docker-ps docker-migrate docker-clean docker-deploy docker-build docs check check-compose check-migrations

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
	uv run python -m demetra.deploy_lock -- $(MAKE) deploy-steps

deploy-steps:
	git pull --ff-only
	docker build --platform linux/amd64 --tag mantiby/demetra:latest .
	docker compose --env-file .env.docker pull postgres redis react-build || true
	docker compose --env-file .env.docker up --abort-on-container-failure migrate react-build
	docker compose --env-file .env.docker up --detach --force-recreate --no-deps api watcher listener rq-dashboard deployer
	$(MAKE) worker-swap-steps
	sudo service nginx reload


# Start the staging generation on the image just built and signal the live one
# exactly once. Callers must hold the deploy lock; deploy-steps does.
worker-swap-steps:
	docker compose --env-file .env.docker run --rm worker-swap

# Standalone swap: take the same deploy lock as make deploy, so an overlapping
# manual run cannot send a second TERM to a container still draining.
worker-swap:
	uv run python -m demetra.deploy_lock -- $(MAKE) worker-swap-steps


# Scale the generations to the slot in the deploy state (blue on a fresh stack).
# Callers must hold the deploy lock, so docker-up and a swap cannot race.
worker-bootstrap-steps:
	docker compose --env-file .env.docker run --rm worker-bootstrap

worker-bootstrap:
	uv run python -m demetra.deploy_lock -- $(MAKE) worker-bootstrap-steps


# Frontend-only deploy: rebuild the React bundle and reload nginx. The image,
# the migrations and the long-running services are left alone, so a UI change
# ships without restarting the API or interrupting the running workflows.
deploy-ui:
	uv run python -m demetra.deploy_lock -- $(MAKE) deploy-ui-steps

deploy-ui-steps:
	git pull --ff-only
	docker compose --env-file .env.docker pull react-build || true
	docker compose --env-file .env.docker up --abort-on-container-failure react-build
	sudo service nginx reload


check:
	git add .
	uv run ty check
	uv run pre-commit run

install:
	uv sync --all-extras --dev

update:
	uu
	uv sync --all-extras --dev
	uv run pre-commit autoupdate

test:
	uv run pytest tests/

test-slow:
	uv run pytest tests/ --durations=10

test-cov:
	uv run pytest tests/ --cov=demetra --cov-report=term-missing --cov-report=html --cov-fail-under=65

docs:
	uv run pdoc --output-directory docs demetra

migrate:
	uv run alembic upgrade head

check-migrations:
	uv run alembic -x url=sqlite:///:memory: upgrade head

check-compose:
	docker compose --env-file .env.docker config -q

ci: install check check-migrations test react-build react-test


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

deployer:
	uv run -m demetra.deployer

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

docker-test:
	docker compose --file docker-compose.test.yaml run --rm tests; \
	status=$$?; \
	docker compose --file docker-compose.test.yaml down --volumes --remove-orphans; \
	exit $$status

docker-up:
	docker compose --env-file .env.docker up -d api watcher listener rq-dashboard deployer
	$(MAKE) worker-bootstrap

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
