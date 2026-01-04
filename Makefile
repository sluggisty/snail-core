# Snail Core - Test and Development Makefile
# This Makefile provides convenient commands for testing, development, and maintenance

.PHONY: help test test-all test-unit test-integration test-cli test-e2e test-performance test-multi-distro test-error-handling test-cov test-cov-html test-cov-xml test-slow test-fast lint format type-check clean install install-dev install-test docs build

# Default target
help:
	@echo "Snail Core - Development and Testing Commands"
	@echo ""
	@echo "Testing:"
	@echo "  test-all          - Run all tests"
	@echo "  test-unit         - Run unit tests only"
	@echo "  test-integration  - Run integration tests only"
	@echo "  test-cli          - Run CLI tests only"
	@echo "  test-e2e          - Run end-to-end tests only"
	@echo "  test-performance  - Run performance tests only"
	@echo "  test-multi-distro - Run multi-distribution tests only"
	@echo "  test-error-handling - Run error handling tests only"
	@echo "  test-cov          - Run all tests with coverage report"
	@echo "  test-cov-html     - Run tests with HTML coverage report"
	@echo "  test-cov-xml      - Run tests with XML coverage report"
	@echo "  test-slow         - Run slow tests only"
	@echo "  test-fast         - Run fast tests only (exclude slow)"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint              - Run linting (ruff)"
	@echo "  format            - Format code (black)"
	@echo "  type-check        - Run type checking (mypy)"
	@echo "  check-all         - Run all code quality checks"
	@echo ""
	@echo "Installation:"
	@echo "  install           - Install package"
	@echo "  install-dev       - Install in development mode"
	@echo "  install-test      - Install test dependencies"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean             - Clean build artifacts and cache"
	@echo "  build             - Build package"
	@echo "  docs              - Generate documentation"
	@echo ""

# Testing targets
test-all:
	pytest tests/

test-unit:
	pytest tests/unit/ -m unit

test-integration:
	pytest tests/integration/ -m integration

test-cli:
	pytest tests/cli/ -m cli

test-e2e:
	pytest tests/e2e/ -m e2e

test-performance:
	pytest tests/performance/ -m performance

test-multi-distro:
	pytest tests/multi_distro/

test-error-handling:
	pytest tests/error_handling/

test-cov:
	pytest --cov=src/snail_core --cov-report=term-missing tests/

test-cov-html:
	pytest --cov=src/snail_core --cov-report=html tests/
	@echo "HTML coverage report generated in htmlcov/index.html"

test-cov-xml:
	pytest --cov=src/snail_core --cov-report=xml tests/

test-slow:
	pytest -m slow tests/

test-fast:
	pytest -m "not slow" tests/

# Code quality targets
lint:
	ruff check src/ tests/

format:
	black src/ tests/

type-check:
	mypy src/

check-all: lint type-check test-all

# Installation targets
install:
	pip install .

install-dev:
	pip install -e .

install-test:
	pip install -r requirements-test.txt

# Maintenance targets
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf tests/__pycache__/
	rm -rf tests/*/__pycache__/
	rm -rf src/snail_core/__pycache__/
	rm -rf src/snail_core/*/__pycache__/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

build:
	python -m build

docs:
	@echo "Documentation generation not yet implemented"
	@echo "Consider using sphinx or similar for documentation"
