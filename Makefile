.PHONY: dev-infra dev-infra-down migrate test unit integration lint typecheck audit check

dev-infra:
	docker compose -f compose.dev.yml up -d

dev-infra-down:
	docker compose -f compose.dev.yml down

migrate:
	alembic upgrade head

unit:
	pytest -m "not integration" -q

integration:
	RUN_INTEGRATION=1 pytest -m integration -q

test:
	pytest -q

lint:
	ruff check .

typecheck:
	mypy app tests

audit:
	pip-audit

check: lint typecheck unit audit
