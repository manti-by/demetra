run:
	uv run main.py

check:
	uv run pre-commit run --all-files
