run-chimera:
	uv run main.py --project-name chimera

run-demetra:
	uv run main.py --project-name demetra

run-odin:
	uv run main.py --project-name odin

run-coruscant:
	uv run main.py --project-name coruscant

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
	uv run python run_api.py

api-dev:
	uv run python run_api.py --reload

test-api:
	uv run python test_api.py

example:
	uv run python example_usage.py

# Systemd service management
service-install:
	sudo ./setup_systemd.sh install

service-start:
	./manage_service.sh start

service-stop:
	./manage_service.sh stop

service-restart:
	./manage_service.sh restart

service-status:
	./manage_service.sh status

service-logs:
	./manage_service.sh logs

service-test:
	./manage_service.sh test
