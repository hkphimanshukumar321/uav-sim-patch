"""
Test Runner for UAV Sim Patched
================================
Runs all tests in sequence and generates summary report.

Run: python -m tests.run_all_tests
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_smoke import run_smoke_tests
from tests.test_functional import run_functional_tests
from tests.test_integration import run_integration_tests


def run_all_tests():
    """Run all test suites"""
    print("\n" + "="*60)
    print("UAV SIM PATCHED - COMPREHENSIVE TEST SUITE")
    print("="*60)
    print("\nRunning all tests...\n")
    
    results = {}
    
    # 1. Smoke Tests
    print("\n" + "#"*60)
    print("# PHASE 1: SMOKE TESTS")
    print("#"*60)
    smoke_success, smoke_result = run_smoke_tests()
    results['smoke'] = {'success': smoke_success, 'result': smoke_result}
    
    if not smoke_success:
        print("\n[FAIL] SMOKE TESTS FAILED - Stopping test execution")
        print("   Fix syntax/import errors before proceeding.")
        return False, results
    
    # 2. Functional Tests
    print("\n" + "#"*60)
    print("# PHASE 2: FUNCTIONAL TESTS")
    print("#"*60)
    func_success, func_result = run_functional_tests()
    results['functional'] = {'success': func_success, 'result': func_result}
    
    if not func_success:
        print("\n[WARN]  FUNCTIONAL TESTS FAILED - Continuing to integration tests")
    
    # 3. Integration Tests
    print("\n" + "#"*60)
    print("# PHASE 3: INTEGRATION TESTS")
    print("#"*60)
    integ_success, integ_result = run_integration_tests()
    results['integration'] = {'success': integ_success, 'result': integ_result}
    
    # Final Summary
    print("\n" + "="*60)
    print("FINAL TEST SUMMARY")
    print("="*60)
    
    print(f"\n[1] Smoke Tests:       {'[PASS]' if smoke_success else '[FAIL]'}")
    print(f"    - Passed: {smoke_result.passed}")
    print(f"    - Failed: {smoke_result.failed}")
    
    print(f"\n[2] Functional Tests:  {'[PASS]' if func_success else '[FAIL]'}")
    print(f"    - Passed: {func_result.passed}")
    print(f"    - Failed: {func_result.failed}")
    
    print(f"\n[3] Integration Tests: {'[PASS]' if integ_success else '[FAIL]'}")
    print(f"    - Passed: {integ_result.passed}")
    print(f"    - Failed: {integ_result.failed}")
    if integ_result.warnings > 0:
        print(f"    - Warnings: {integ_result.warnings}")
    
    overall_success = smoke_success and func_success and integ_success
    
    print("\n" + "="*60)
    if overall_success:
        print("[ALL TESTS PASSED]")
    else:
        print("[SOME TESTS FAILED]")
    print("="*60 + "\n")
    
    return overall_success, results


if __name__ == "__main__":
    success, results = run_all_tests()
    sys.exit(0 if success else 1)
