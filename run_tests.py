#!/usr/bin/env python3
"""
Test runner script for Iron Chef Recipe Database
Provides a simple interface to run different test suites
"""

import sys
import subprocess
import argparse
import os
from pathlib import Path


def run_command(command, description=""):
    """Run a command and display results"""
    print(f"\n{'='*60}")
    if description:
        print(f"Running: {description}")
    print(f"Command: {' '.join(command)}")
    print('='*60)
    
    try:
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.stdout:
            print("STDOUT:")
            print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        if result.returncode == 0:
            print(f"✓ SUCCESS: {description}")
        else:
            print(f"✗ FAILED: {description} (exit code: {result.returncode})")
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"✗ ERROR running command: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Iron Chef Recipe Database Test Runner")
    parser.add_argument('--suite', choices=['unit', 'integration', 'security', 'all', 'fast'], 
                       default='fast', help='Test suite to run')
    parser.add_argument('--coverage', action='store_true', help='Run with coverage reporting')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--install', action='store_true', help='Install dependencies first')
    
    args = parser.parse_args()
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    print("Iron Chef Recipe Database - Test Runner")
    print(f"Working directory: {os.getcwd()}")
    
    success = True
    
    # Install dependencies if requested
    if args.install:
        print("\nInstalling dependencies...")
        install_cmd = [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt']
        if not run_command(install_cmd, "Installing dependencies"):
            print("Failed to install dependencies")
            return 1
    
    # Check if pytest is available
    try:
        import pytest
        print(f"✓ pytest version: {pytest.__version__}")
    except ImportError:
        print("✗ pytest not found. Installing...")
        install_cmd = [sys.executable, '-m', 'pip', 'install', 'pytest>=7.0.0', 'pytest-cov>=4.0.0']
        if not run_command(install_cmd, "Installing pytest"):
            print("Failed to install pytest")
            return 1
    
    # Build pytest command
    pytest_cmd = [sys.executable, '-m', 'pytest', 'tests/']
    
    if args.verbose:
        pytest_cmd.extend(['-v', '--tb=short'])
    else:
        pytest_cmd.append('-q')
    
    # Add coverage if requested
    if args.coverage:
        pytest_cmd.extend(['--cov', '--cov-report=term-missing', '--cov-report=html'])
    
    # Add test suite specific markers
    if args.suite == 'unit':
        pytest_cmd.extend(['-m', 'unit'])
        description = "Unit Tests"
    elif args.suite == 'integration':
        pytest_cmd.extend(['-m', 'integration'])
        description = "Integration Tests"
    elif args.suite == 'security':
        pytest_cmd.extend(['-m', 'security'])
        description = "Security Tests"
    elif args.suite == 'fast':
        pytest_cmd.extend(['-m', 'not slow'])
        description = "Fast Tests (excluding slow tests)"
    else:  # all
        description = "All Tests"
    
    # Run tests
    if not run_command(pytest_cmd, description):
        success = False
    
    # Show summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print('='*60)
    
    if success:
        print("✓ All tests completed successfully!")
        if args.coverage:
            print("✓ Coverage report generated in htmlcov/index.html")
    else:
        print("✗ Some tests failed. Please review the output above.")
    
    print("\nNext steps:")
    print("- Run 'python run_tests.py --suite all --coverage' for complete test suite")
    print("- Run 'python run_tests.py --suite security' for security-focused tests")
    print("- Check htmlcov/index.html for detailed coverage report")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())