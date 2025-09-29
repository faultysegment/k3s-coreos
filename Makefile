# Makefile for k3s-coreos project

.PHONY: test build help clean deps venv

# Default target
help:
	@echo "Available targets:"
	@echo "  venv    - Create virtual environment"
	@echo "  test    - Run all tests using pytest"
	@echo "  build   - Build the application package"
	@echo "  deps    - Install dependencies using Poetry"
	@echo "  clean   - Clean build artifacts"
	@echo "  help    - Show this help message"

# Create/ensure virtual environment
venv:
	@if [ ! -d "$$(poetry env info --path 2>/dev/null)" ]; then \
		echo "Creating virtual environment..."; \
		poetry install --no-root; \
	else \
		echo "Virtual environment already exists at $$(poetry env info --path)"; \
	fi
	@echo "To activate the virtual environment, run: poetry shell"

# Run tests
test: venv
	poetry run pytest

# Build application package
build: venv
	poetry build

# Install dependencies
deps: venv
	poetry install

# Clean build artifacts
clean:
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
