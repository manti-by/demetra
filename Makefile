run-demetra:
	uv run main.py --project-name demetra

run-odin:
	uv run main.py --project-name odin

run-coruscant:
	uv run main.py --project-name coruscant

deploy:
	git pull --ff-only
	uv sync
	sudo systemctl daemon-reload
	sudo systemctl restart demetra-api.service
	sudo systemctl restart demetra-watcher.service
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
