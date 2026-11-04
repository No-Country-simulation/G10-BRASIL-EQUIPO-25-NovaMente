# ─────────────────────────────────────────────────────────────────────────────
# NovaMente — comandos de desenvolvimento
#
# Funciona em Linux/macOS e Windows (PowerShell, CMD ou Git Bash), desde que o
# GNU Make esteja instalado. No Windows: `choco install make` ou
# `winget install ezwinports.make`.
#
# Uso:
#   make help
#   make venv
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
  VENV_PYTHON   := .venv/Scripts/python.exe
else
  DETECTED_OS   := $(shell uname -s)
  BOOTSTRAP_PYTHON ?= python3
  VENV_PYTHON   := .venv/bin/python
endif

NPM ?= npm

.PHONY: help venv install install-frontend dev-backend dev-frontend

help:
	@echo "NovaMente — comandos disponíveis (plataforma detectada: $(DETECTED_OS))"
	@echo ""
	@echo "  make venv            Cria backend/.venv e instala requirements.txt"
	@echo "  make install         Cria o venv e instala as dependências do frontend"
	@echo "  make install-frontend  Instala as dependências do frontend (npm install)"
	@echo "  make dev-backend     Sobe a API FastAPI em http://localhost:$(BACKEND_PORT)"
	@echo "  make dev-frontend    Sobe o Next.js em http://localhost:$(FRONTEND_PORT)"
	@echo ""
	@echo "Variáveis opcionais:"
	@echo "  BACKEND_HOST=$(BACKEND_HOST) BACKEND_PORT=$(BACKEND_PORT) FRONTEND_PORT=$(FRONTEND_PORT)"
	@echo "  BOOTSTRAP_PYTHON=$(BOOTSTRAP_PYTHON)   (interpretador usado para criar o venv)"

# ── Ambiente Python ──────────────────────────────────────────────────────────
venv:
	@echo ">> Criando ambiente virtual em $(VENV_DIR)..."
	@cd $(BACKEND_DIR) && $(BOOTSTRAP_PYTHON) -m venv .venv
	@echo ">> Atualizando pip..."
	@cd $(BACKEND_DIR) && $(VENV_PYTHON) -m pip install --upgrade pip
	@echo ">> Instalando backend/requirements.txt..."
	@cd $(BACKEND_DIR) && $(VENV_PYTHON) -m pip install -r requirements.txt
	@echo ">> Pronto! Ambiente criado em $(VENV_DIR)"

# ── Frontend ─────────────────────────────────────────────────────────────────
install-frontend:
	@echo ">> Instalando dependências do frontend..."
	@cd $(FRONTEND_DIR) && $(NPM) install

install: venv install-frontend

# ── Desenvolvimento ──────────────────────────────────────────────────────────
dev-backend:
	@echo ">> Backend em http://localhost:$(BACKEND_PORT) (docs: /docs)"
	@cd $(BACKEND_DIR) && $(VENV_PYTHON) -m uvicorn app.main:app --reload --host $(BACKEND_HOST) --port $(BACKEND_PORT)

dev-frontend:
	@echo ">> Frontend em http://localhost:$(FRONTEND_PORT)"
	@cd $(FRONTEND_DIR) && $(NPM) run dev -- --port $(FRONTEND_PORT)
