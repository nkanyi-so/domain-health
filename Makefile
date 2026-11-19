SHELL := /bin/bash
.DEFAULT_GOAL := help

# The emulator's project: a "demo-" ID never reaches a real Google Cloud project.
EMULATOR_PROJECT := demo-domain-health

# Node 24 or later. Where the default node is older and nvm has a 24, use that one for this make
# only: nothing on the machine is changed.
NODE_OK := $(shell node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 24 ? 0 : 1)' 2>/dev/null && echo yes)
ifneq ($(NODE_OK),yes)
NVM_NODE := $(lastword $(sort $(wildcard $(HOME)/.nvm/versions/node/v24.*/bin)))
ifneq ($(NVM_NODE),)
export PATH := $(NVM_NODE):$(PATH)
endif
endif

# A JDK of 21 or later, for the Firestore emulator. On a Mac, ask the system for one; elsewhere
# (CI) the JDK that is already on the PATH is used.
ifeq ($(shell uname),Darwin)
JDK21 := $(shell /usr/libexec/java_home -v 21+ 2>/dev/null)
ifneq ($(JDK21),)
export JAVA_HOME := $(JDK21)
export PATH := $(JDK21)/bin:$(PATH)
endif
endif

.PHONY: help setup dev check check-backend check-frontend format eval \
	eval-live record seed infra deploy-backend fallback screens check-domain

help:
	@echo "make setup | dev | check | format FILE=<path> | eval [STRICT=1]"
	@echo "not built yet: eval-live record seed infra deploy-backend fallback screens check-domain"

setup:
	cd backend && uv sync --frozen
	cd frontend && pnpm install --frozen-lockfile
	cd emulator && pnpm install --frozen-lockfile
	git config core.hooksPath .githooks
	@command -v gitleaks >/dev/null 2>&1 || echo "WARNING: gitleaks is not installed, so commits are not scanned for secrets before they are made."
	@bash scripts/toolchain-check.sh || true

dev:
	bash scripts/dev.sh $(EMULATOR_PROJECT)

check: check-backend check-frontend

check-backend:
	cd backend && uv run --frozen ruff format --check .
	cd backend && uv run --frozen ruff check .
	cd backend && uv run --frozen mypy
	cd backend && uv run --frozen pytest -m "not emulator"
	cd emulator && pnpm exec firebase emulators:exec --only firestore --project $(EMULATOR_PROJECT) \
		"cd ../backend && uv run --frozen pytest -m emulator"

check-frontend:
	cd frontend && pnpm run format:check
	cd frontend && pnpm run lint
	cd frontend && pnpm run typecheck
	cd frontend && pnpm run test
	cd frontend && pnpm run build

# Formats the one file passed as FILE=. The edit hook calls this. Files no formatter owns
# (docs, eval cases, shell) are left as written.
format:
	@test -n "$(FILE)" || { echo "usage: make format FILE=<path>" >&2; exit 1; }
	@bash scripts/format-one.sh "$(FILE)"

# Free. Scores the committed recordings; before any prompt exists there is nothing to measure.
eval:
	@cd backend && uv run --frozen python -m domain_health.evals --prompts ../prompts $(if $(STRICT),--strict,)

# Paid, or writes to Google Cloud. Each must be the only goal on the command line, so that it can
# never ride along behind an allowed command such as `make eval record`. Keep this guard when a
# phase builds the target.
GUARDED := eval-live record seed infra deploy-backend
ifneq ($(filter $(GUARDED),$(MAKECMDGOALS)),)
ifneq ($(words $(MAKECMDGOALS)),1)
$(error $(filter $(GUARDED),$(MAKECMDGOALS)) is paid or writes to Google Cloud: run it alone, as the only goal)
endif
endif

eval-live record seed infra deploy-backend fallback screens check-domain:
	@echo "make $@: not built yet" >&2; exit 1
