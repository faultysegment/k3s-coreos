#!/usr/bin/env python3
"""Test runner for k3s-coreos ISO creator."""

import unittest
import sys
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Import all test modules
from tests.test_models import TestISOCreationConfig, TestButaneFileFinder, TestSSHKeyFinder
from tests.test_controller import TestConsoleController, TestInteractiveController
from tests.test_views import TestTUIView

def run_tests():
    """Run all test suites."""
    # Create test suite
    test_classes = [
        TestISOCreationConfig,
        TestButaneFileFinder,
        TestSSHKeyFinder,
        TestConsoleController,
        TestInteractiveController,
        TestTUIView
    ]

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")

    # Print details of failures and errors
    if result.failures:
        print(f"\n{'='*60}")
        print("FAILURES:")
        for test, traceback in result.failures:
            print(f"\n{test}:")
            print(traceback)

    if result.errors:
        print(f"\n{'='*60}")
        print("ERRORS:")
        for test, traceback in result.errors:
            print(f"\n{test}:")
            print(traceback)

    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)