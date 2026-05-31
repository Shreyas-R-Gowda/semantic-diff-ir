.PHONY: install test eval web

install:
	pip install -e ".[dev]"

test:
	pytest -q

eval:
	semantic-diff-eval

web:
	@echo "open http://127.0.0.1:5173"
	uvicorn semantic_diff.web.api:app --host 127.0.0.1 --port 8000
