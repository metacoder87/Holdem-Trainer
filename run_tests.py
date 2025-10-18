#!/usr/bin/env python3
"""
Test runner for PyHoldem Pro.
Provides various test execution options and reporting.
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_all_tests(verbose=False, coverage=False):
    """Run all tests."""
    cmd = ["python", "-m", "pytest"]
    
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend(["--cov=src", "--cov-report=html", "--cov-report=term"])
    
    cmd.append("tests/")
    
    return subprocess.run(cmd)


def run_unit_tests(verbose=False):
    """Run only unit tests."""
    cmd = ["python", "-m", "pytest", "-m", "unit"]
    
    if verbose:
        cmd.append("-v")
    
    cmd.append("tests/")
    
    return subprocess.run(cmd)


def run_integration_tests(verbose=False):
    """Run only integration tests."""
    cmd = ["python", "-m", "pytest", "-m", "integration"]
    
    if verbose:
        cmd.append("-v")
    
    cmd.append("tests/")
    
    return subprocess.run(cmd)


def run_specific_test_file(test_file, verbose=False):
    """Run tests from a specific file."""
    cmd = ["python", "-m", "pytest"]
    
    if verbose:
        cmd.append("-v")
    
    cmd.append(f"tests/{test_file}")
    
    return subprocess.run(cmd)


def run_tests_by_category(category, verbose=False):
    """Run tests by category (marker)."""
    cmd = ["python", "-m", "pytest", "-m", category]
    
    if verbose:
        cmd.append("-v")
    
    cmd.append("tests/")
    
    return subprocess.run(cmd)


def check_test_environment():
    """Check if test environment is properly set up."""
    print("Checking test environment...")
    
    # Check if pytest is installed
    try:
        import pytest
        print(f"✓ pytest installed (version {pytest.__version__})")
    except ImportError:
        print("✗ pytest not installed")
        return False
    
    # Check if required directories exist
    test_dir = Path("tests")
    if test_dir.exists():
        print("✓ tests directory found")
    else:
        print("✗ tests directory not found")
        return False
    
    # Check if src directory exists
    src_dir = Path("src")
    if src_dir.exists():
        print("✓ src directory found")
    else:
        print("✗ src directory not found")
        return False
    
    # Count test files
    test_files = list(test_dir.glob("test_*.py"))
    print(f"✓ Found {len(test_files)} test files")
    
    return True


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description="PyHoldem Pro Test Runner")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-c", "--coverage", action="store_true", help="Run with coverage")
    parser.add_argument("-u", "--unit", action="store_true", help="Run only unit tests")
    parser.add_argument("-i", "--integration", action="store_true", help="Run only integration tests")
    parser.add_argument("-f", "--file", help="Run specific test file")
    parser.add_argument("-m", "--marker", help="Run tests with specific marker")
    parser.add_argument("--check", action="store_true", help="Check test environment")
    
    args = parser.parse_args()
    
    # Check environment first if requested
    if args.check:
        if check_test_environment():
            print("\n✓ Test environment is ready!")
        else:
            print("\n✗ Test environment has issues!")
            return 1
        return 0
    
    # Run specific test categories
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
