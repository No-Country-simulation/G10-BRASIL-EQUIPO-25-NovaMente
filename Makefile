# ─────────────────────────────────────────────────────────────────────────────
# NovaMente — comandos de desenvolvimento
#
# Funciona em Linux/macOS e Windows (PowerShell, CMD ou Git Bash), desde que o
# GNU Make esteja instalado. No Windows: `choco install make` ou
# `winget install ezwinports.make`.
#
# Uso:
#   make help
#   make install
#   make dev-backend
#   make dev-frontend
# ─────────────────────────────────────────────────────────────────────────────

.DEFAULT_GOAL := help

BACKEND_DIR  := backend
FRONTEND_DIR := frontend
VENV_DIR     := $(BACKEND_DIR)/.venv

BACKEND_HOST ?= 0.0.0.0
BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 3000

# ── Detecção de plataforma ───────────────────────────────────────────────────
# As receitas usam caminhos relativos com "/" e `cd ... && ...`, que funcionam
# tanto no cmd.exe/Git Bash (Windows) quanto no sh (Linux/macOS).
ifeq ($(OS),Windows_NT)
  DETECTED_OS   := Windows
  BOOTSTRAP_PYTHON ?= python
  # Aspas necessárias: o cmd.exe não executa ".venv/Scripts/python.exe" sem elas.
  VENV_PYTHON   := ".venv/Scripts/python.exe"
  # `echo` sozinho imprime "ECHO está desativado." no cmd.exe.
  BLANK         := echo.
else
  DETECTED_OS   := $(shell uname -s)
  BOOTSTRAP_PYTHON ?= python3
  VENV_PYTHON   := ".venv/bin/python"
  BLANK         := echo
endif

NPM ?= npm

.PHONY: help venv install-backend install-backend-dev install-frontend install \
        dev-backend dev-frontend test-backend test-frontend test \
        typecheck lint build e2e verificar

help:
	@echo NovaMente — comandos disponíveis (plataforma detectada: $(DETECTED_OS))
	@$(BLANK)
	@echo   make install              Cria o venv com deps de dev e instala o frontend
	@echo   make install-backend      Cria o venv e instala só as deps de produção
	@echo   make install-backend-dev  Instala as deps de dev/testes no venv
	@echo   make install-frontend     Instala as deps do frontend (npm install)
	@echo   make dev-backend          Sobe a API FastAPI em http://localhost:$(BACKEND_PORT)
	@echo   make dev-frontend         Sobe o Next.js em http://localhost:$(FRONTEND_PORT)
	@echo   make test                 Roda pytest e Vitest
	@echo   make test-backend         Roda pytest
	@echo   make test-frontend        Roda Vitest
	@echo   make typecheck            TypeScript sem emitir
	@echo   make lint                 ESLint
	@echo   make build                Build de produção do Next
	@echo   make e2e                  Playwright
	@echo   make verificar            DoD completo (backend + frontend)
	@$(BLANK)
	@echo Variáveis opcionais:
	@echo   BACKEND_HOST=$(BACKEND_HOST) BACKEND_PORT=$(BACKEND_PORT) FRONTEND_PORT=$(FRONTEND_PORT)
	@echo   BOOTSTRAP_PYTHON=$(BOOTSTRAP_PYTHON)   (interpretador usado para criar o venv)

# ── Ambiente Python ──────────────────────────────────────────────────────────
venv:
	@echo Criando ambiente virtual em $(VENV_DIR)...
	@cd $(BACKEND_DIR) && $(BOOTSTRAP_PYTHON) -m venv .venv
	@echo Atualizando pip...
	@cd $(BACKEND_DIR) && $(VENV_PYTHON) -m pip install --upgrade pip
	@echo Instalando backend/requirements.txt...
	@cd $(BACKEND_DIR) && $(VENV_PYTHON) -m pip install -r requirements.txt
	@echo Pronto! Ambiente criado em $(VENV_DIR)

install-backend: venv

install-backend-dev: venv
	@echo Instalando backend/requirements-dev.txt...
	@cd $(BACKEND_DIR) && $(VENV_PYTHON) -m pip install -r requirements-dev.txt

# ── Frontend ─────────────────────────────────────────────────────────────────
install-frontend:
	@echo Instalando dependências do frontend...
	@cd $(FRONTEND_DIR) && $(NPM) install

install: install-backend-dev install-frontend

# ── Desenvolvimento ──────────────────────────────────────────────────────────
dev-backend:
	@echo Backend em http://localhost:$(BACKEND_PORT) (docs: /docs)
	@cd $(BACKEND_DIR) && $(VENV_PYTHON) -m uvicorn app.main:app --reload --host $(BACKEND_HOST) --port $(BACKEND_PORT)

dev-frontend:
	@echo Frontend em http://localhost:$(FRONTEND_PORT)
	@cd $(FRONTEND_DIR) && $(NPM) run dev -- --port $(FRONTEND_PORT)

# ── Testes e qualidade ───────────────────────────────────────────────────────
test-backend:
	@echo Rodando testes do backend...
	@cd $(BACKEND_DIR) && $(VENV_PYTHON) -m pytest tests -q

test-frontend:
	@echo Rodando testes do frontend...
	@cd $(FRONTEND_DIR) && $(NPM) test

test: test-backend test-frontend

typecheck:
	@cd $(FRONTEND_DIR) && $(NPM) run typecheck

lint:
	@cd $(FRONTEND_DIR) && $(NPM) run lint

build:
	@cd $(FRONTEND_DIR) && $(NPM) run build

e2e:
	@cd $(FRONTEND_DIR) && $(NPM) run e2e

verificar: test-backend
	@cd $(FRONTEND_DIR) && $(NPM) run verificar
