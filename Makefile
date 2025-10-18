# Makefile for PyHoldem Pro
.PHONY: help install dev-install test test-verbose test-coverage clean lint format run setup

# Default target
help:
	@echo "PyHoldem Pro Development Commands:"
	@echo "  help         Show this help message"
	@echo "  setup        Set up development environment"
	@echo "  install      Install package dependencies"
	@echo "  dev-install  Install package in development mode"
	@echo "  test         Run all tests"
	@echo "  test-verbose Run tests with verbose output"
	@echo "  test-coverage Run tests with coverage report"
	@echo "  test-unit    Run only unit tests"
	@echo "  test-integration Run only integration tests"
	@echo "  lint         Run linting checks"
	@echo "  format       Format code with black"
	@echo "  clean        Clean up generated files"
	@echo "  run          Run the game"

# Setup development environment
setup:
	@echo "Setting up PyHoldem Pro development environment..."
	python -m venv venv
	@echo "Virtual environment created. Activate with:"
	@echo "  source venv/bin/activate  # Linux/Mac"
	@echo "  venv\\Scripts\\activate     # Windows"

# Install dependencies
install:
	pip install -r requirements.txt

# Install in development mode
dev-install:
	pip install -e .[dev]

# Run all tests
test:
	python run_tests.py

# Run tests with verbose output
test-verbose:
	python run_tests.py -v

# Run tests with coverage
test-coverage:
	python run_tests.py -c

# Run only unit tests
test-unit:
	python run_tests.py -u

# Run only integration tests
test-integration:
	python run_tests.py -i

# Run specific test file
test-file:
	@echo "Usage: make test-file FILE=test_card.py"
	@if [ -z "$(FILE)" ]; then echo "Please specify FILE=<test_file>"; exit 1; fi
	python run_tests.py -f $(FILE)

# Run tests by marker
test-marker:
	@echo "Usage: make test-marker MARKER=unit"
	@if [ -z "$(MARKER)" ]; then echo "Please specify MARKER=<marker_name>"; exit 1; fi
	python run_tests.py -m $(MARKER)

# Linting
lint:
	@echo "Running flake8..."
	flake8 src/ tests/ --max-line-length=88 --extend-ignore=E203,W503
	@echo "Running mypy..."
	mypy src/ --ignore-missing-imports

# Format code
format:
	@echo "Formatting code with black..."
	black src/ tests/ --line-length=88

# Clean up
clean:
	@echo "Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ .coverage htmlcov/ .pytest_cache/

# Run the game
run:
	python main.py

# Check test environment
check-tests:
	python run_tests.py --check

# Install pre-commit hooks
install-hooks:
	@echo "Installing pre-commit hooks..."
	pip install pre-commit
	pre-commit install

# Run pre-commit on all files
pre-commit:
	pre-commit run --all-files

# Build distribution packages
build:
	@echo "Building distribution packages..."
	python setup.py sdist bdist_wheel

# Install package locally
install-local:
	pip install -e .

# Uninstall package
uninstall:
	pip uninstall pyholdem-pro -y

# Generate requirements.txt from current environment
freeze:
	pip freeze > requirements.txt

# Show project statistics
stats:
	@echo "Project Statistics:"
	@echo "==================="
	@find src -name "*.py" | xargs wc -l | tail -1
	@echo -n "Test files: "
	@find tests -name "test_*.py" | wc -l
	@find tests -name "test_*.py" | xargs wc -l | tail -1

# Run performance tests
test-perf:
	@echo "Running performance tests..."
	python -m pytest tests/ -m slow -v

# Create new test file template
new-test:
	@echo "Usage: make new-test NAME=new_feature"
	@if [ -z "$(NAME)" ]; then echo "Please specify NAME=<feature_name>"; exit 1; fi
	@echo "Creating test file for $(NAME)..."
	@cat > tests/test_$(NAME).py << 'EOF'
"""
Test suite for $(NAME).
"""
import pytest


class Test$(NAME):
    """Test cases for $(NAME)."""
    
    def test_placeholder(self):
        """Placeholder test."""
        assert True
EOF
	@echo "Created tests/test_$(NAME).py"

# Database operations (if needed)
init-db:
	@echo "Initializing database..."
	mkdir -p data
	touch data/players.json

# Backup data
backup-data:
	@echo "Backing up player data..."
	mkdir -p backups
	cp data/players.json backups/players_backup_$(shell date +%Y%m%d_%H%M%S).json

# Restore data
restore-data:
	@echo "Usage: make restore-data FILE=backups/players_backup_YYYYMMDD_HHMMSS.json"
	@if [ -z "$(FILE)" ]; then echo "Please specify FILE=<backup_file>"; exit 1; fi
	cp $(FILE) data/players.json

# Development server (if web interface is added)
dev-server:
	@echo "Development server not implemented yet"

# Documentation generation (if added)
docs:
	@echo "Documentation generation not implemented yet"

# Run security checks
security:
	@echo "Running security checks..."
	pip install bandit
	bandit -r src/

# Check for outdated packages
check-updates:
	pip list --outdated

# Update all packages
update-packages:
	pip install --upgrade -r requirements.txt

# Profile the application
profile:
	@echo "Profiling not implemented yet"

# Memory usage analysis
memory-profile:
	@echo "Memory profiling not implemented yet"

# Generate test coverage badge
coverage-badge:
	@echo "Coverage badge generation not implemented yet"

# Continuous integration simulation
ci:
	@echo "Running CI pipeline..."
	make clean
	make install
	make lint
	make test-coverage
	@echo "CI pipeline completed successfully!"
