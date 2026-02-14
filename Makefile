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
