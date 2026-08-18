.PHONY: bootstrap lint workflow-lint test smoke dependencies check

bootstrap:
	./scripts/bootstrap

lint:
	./scripts/lint

workflow-lint:
	./scripts/workflow-lint

test:
	./scripts/test

smoke:
	./scripts/smoke

dependencies:
	./scripts/dependencies

check:
	./scripts/check
