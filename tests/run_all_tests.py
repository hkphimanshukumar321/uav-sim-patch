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
from tests.test_experiments import run_experiment_tests
from tests.test_integration import run_integration_tests
from tests.test_comprehensive import run_comprehensive_tests
from tests.test_multiprocessing import run_multiprocessing_tests
from tests.test_ghost_functions import run_ghost_check


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
        print("\n[WARN]  FUNCTIONAL TESTS FAILED - Continuing to experiment tests")
    
    # 3. Experiment Tests
    print("\n" + "#"*60)
    print("# PHASE 3: EXPERIMENT TESTS")
    print("#"*60)
    exp_success, exp_result = run_experiment_tests()
    results['experiments'] = {'success': exp_success, 'result': exp_result}
    
    # 4. Integration Tests
    print("\n" + "#"*60)
    print("# PHASE 3: INTEGRATION TESTS")
    print("#"*60)
    integ_success, integ_result = run_integration_tests()
    results['integration'] = {'success': integ_success, 'result': integ_result}
    
    # 5. Comprehensive Tests
    print("\n" + "#"*60)
    print("# PHASE 5: COMPREHENSIVE TESTS")
    print("#"*60)
    comp_success, comp_result = run_comprehensive_tests()
    results['comprehensive'] = {'success': comp_success, 'result': comp_result}
    
    # 6. Multiprocessing Tests
    print("\n" + "#"*60)
    print("# PHASE 6: MULTIPROCESSING TESTS")
    print("#"*60)
    mp_success, mp_passed, mp_total = run_multiprocessing_tests()
    results['multiprocessing'] = {'success': mp_success, 'passed': mp_passed, 'total': mp_total}
    
    # 7. Ghost Functions
    print("\n" + "#"*60)
    print("# PHASE 7: GHOST FUNCTION CHECK")
    print("#"*60)
    ghost_success, ghost_count = run_ghost_check()
    results['ghost'] = {'success': ghost_success, 'count': ghost_count}
    
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
    
    print(f"\n[3] Experiment Tests:  {'[PASS]' if exp_success else '[FAIL]'}")
    print(f"    - Passed: {exp_result.passed}")
    print(f"    - Failed: {exp_result.failed}")
    
    print(f"\n[4] Integration Tests: {'[PASS]' if integ_success else '[FAIL]'}")
    print(f"    - Passed: {integ_result.passed}")
    print(f"    - Failed: {integ_result.failed}")
    if integ_result.warnings > 0:
        print(f"    - Warnings: {integ_result.warnings}")

    print(f"\n[5] Comprehensive Tests: {'[PASS]' if comp_success else '[FAIL]'}")
    
    print(f"\n[6] Multiprocessing:     {'[PASS]' if mp_success else '[FAIL]'}")
    print(f"    - Passed: {mp_passed}/{mp_total}")
    
    print(f"\n[7] Ghost Functions:     {'[WARN]' if ghost_count > 0 else '[PASS]'}")
    print(f"    - Found: {ghost_count}")
    
    overall_success = smoke_success and func_success and exp_success and integ_success and comp_success and mp_success
    
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
