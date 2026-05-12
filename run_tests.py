#!/usr/bin/env python3
"""
Test runner for PyHoldem Pro.
Provides test execution options and simple environment checks.
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List


def _pytest_cmd(*args: str) -> List[str]:
    return [sys.executable, "-m", "pytest", *args]


def run_all_tests(verbose=False, coverage=False):
    cmd = _pytest_cmd()

    if verbose:
        cmd.append("-v")

    if coverage:
        cmd.extend(["--cov=src", "--cov-report=html", "--cov-report=term"])

    cmd.append("tests/")
    return subprocess.run(cmd)


def run_unit_tests(verbose=False):
    cmd = _pytest_cmd("-m", "unit")
    if verbose:
        cmd.append("-v")
    cmd.append("tests/")
    return subprocess.run(cmd)


def run_integration_tests(verbose=False):
    cmd = _pytest_cmd("-m", "integration")
    if verbose:
        cmd.append("-v")
    cmd.append("tests/")
    return subprocess.run(cmd)


def run_specific_test_file(test_file, verbose=False):
    cmd = _pytest_cmd()
    if verbose:
        cmd.append("-v")
    cmd.append(f"tests/{test_file}")
    return subprocess.run(cmd)


def run_tests_by_category(category, verbose=False):
    cmd = _pytest_cmd("-m", category)
    if verbose:
        cmd.append("-v")
    cmd.append("tests/")
    return subprocess.run(cmd)


def check_test_environment():
    print("Checking test environment...")

    try:
        import pytest

        print(f"[ok] pytest installed (version {pytest.__version__})")
    except ImportError:
        print("[error] pytest not installed")
        return False

    test_dir = Path("tests")
    if test_dir.exists():
        print("[ok] tests directory found")
    else:
        print("[error] tests directory not found")
        return False

    src_dir = Path("src")
    if src_dir.exists():
        print("[ok] src directory found")
    else:
        print("[error] src directory not found")
        return False

    test_files = list(test_dir.glob("test_*.py"))
    print(f"[ok] Found {len(test_files)} test files")
    return True


def main():
    parser = argparse.ArgumentParser(description="PyHoldem Pro Test Runner")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-c", "--coverage", action="store_true", help="Run with coverage")
    parser.add_argument("-u", "--unit", action="store_true", help="Run only unit tests")
    parser.add_argument("-i", "--integration", action="store_true", help="Run only integration tests")
    parser.add_argument("-f", "--file", help="Run specific test file")
    parser.add_argument("-m", "--marker", help="Run tests with specific marker")
    parser.add_argument("--check", action="store_true", help="Check test environment")

    args = parser.parse_args()

    if args.check:
        if check_test_environment():
            print("\n[ok] Test environment is ready!")
            return 0
        print("\n[error] Test environment has issues!")
        return 1

    if args.unit:
        print("Running unit tests...")
        result = run_unit_tests(args.verbose)
    elif args.integration:
        print("Running integration tests...")
        result = run_integration_tests(args.verbose)
    elif args.file:
        print(f"Running tests from {args.file}...")
        result = run_specific_test_file(args.file, args.verbose)
    elif args.marker:
        print(f"Running tests with marker '{args.marker}'...")
        result = run_tests_by_category(args.marker, args.verbose)
    else:
        print("Running all tests...")
        result = run_all_tests(args.verbose, args.coverage)

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
