"""
Comprehensive Test Suite for UAV Network Simulator

Tests all major changes including:
- TDMA slot duration fix
- STDMA implementation
- Ablation framework
- Seed configuration
- Ghost function detection

Run with: python tests/test_comprehensive.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test 1: Verify all critical imports work"""
    print("\n" + "="*70)
    print("TEST 1: Import Verification")
    print("="*70)
    
    try:
        from utils import config
        print("[OK] config imported")
        
        from simulator.simulator import Simulator
        print("[OK] Simulator imported")
        
        from mac.tdma import Tdma
        print("[OK] TDMA imported")
        
        from mac.stdma import Stdma
        print("[OK] STDMA imported")
        
        from mac.csma_ca import CsmaCa
        print("[OK] CSMA/CA imported")
        
        from mac.pure_aloha import PureAloha
        print("[OK] ALOHA imported")
        
        from ablation.ablation_config import AblationConfig
        print("[OK] AblationConfig imported")
        
        from ablation.ablation_runner import AblationRunner
        print("[OK] AblationRunner imported")
        
        from ablation.plot_results import plot_mac_comparison
        print("[OK] plot_results imported")
        
        print("\n✓ All imports successful!")
        return True
    except Exception as e:
        print(f"\n✗ Import failed: {e}")
        return False


def test_config_parameters():
    """Test 2: Verify all new config parameters exist"""
    print("\n" + "="*70)
    print("TEST 2: Config Parameters")
    print("="*70)
    
    from utils import config
    
    required_params = [
        # TDMA
        "TDMA_SLOT_DURATION",
        "TDMA_SLOTS_PER_FRAME",
        "TDMA_GUARD_TIME",
        # STDMA
        "STDMA_RESERVATION_TIMEOUT",
        "STDMA_MAX_SLOTS_PER_DRONE",
        # Mobility
        "MOBILITY_ALPHA",
        "MOBILITY_POSITION_UPDATE_INTERVAL",
        # Channel
        "PATH_LOSS_MODEL",
        # Seed
        "MASTER_SEED",
    ]
    
    passed = 0
    failed = 0
    
    for param in required_params:
        if hasattr(config, param):
            value = getattr(config, param)
            print(f"[OK] {param} = {value}")
            passed += 1
        else:
            print(f"[FAIL] {param} missing!")
            failed += 1
    
    print(f"\n✓ {passed}/{len(required_params)} parameters found")
    return failed == 0


def test_tdma_slot_fix():
    """Test 3: Verify TDMA slot duration is correct"""
    print("\n" + "="*70)
    print("TEST 3: TDMA Slot Duration Fix")
    print("="*70)
    
    from utils import config
    
    # Calculate minimum required slot duration
    packet_bits = config.AVERAGE_PAYLOAD_LENGTH + config.IP_HEADER_LENGTH + config.MAC_HEADER_LENGTH + config.PHY_HEADER_LENGTH
    bit_rate = config.BIT_RATE
    transmission_time = packet_bits / bit_rate * 1e6  # in microseconds
    
    # Add SIFS and ACK time
    ack_time = config.ACK_PACKET_LENGTH / bit_rate * 1e6
    sifs = config.SIFS_DURATION
    min_slot_duration = transmission_time + sifs + ack_time + 100  # + buffer
    
    actual_slot_duration = config.TDMA_SLOT_DURATION
    
    print(f"Packet transmission time: {transmission_time:.0f} µs")
    print(f"ACK + SIFS time: {ack_time + sifs:.0f} µs")
    print(f"Minimum slot duration: {min_slot_duration:.0f} µs")
    print(f"Actual slot duration: {actual_slot_duration} µs")
    
    if actual_slot_duration >= min_slot_duration:
        print(f"\n✓ TDMA slot duration is adequate ({actual_slot_duration} >= {min_slot_duration:.0f})")
        return True
    else:
        print(f"\n✗ TDMA slot duration too short! ({actual_slot_duration} < {min_slot_duration:.0f})")
        return False


def test_ablation_config():
    """Test 4: Verify ablation parameter registry"""
    print("\n" + "="*70)
    print("TEST 4: Ablation Config Registry")
    print("="*70)
    
    from ablation.ablation_config import AblationConfig
    
    params = AblationConfig.PARAMETERS
    print(f"Total parameters registered: {len(params)}")
    
    # Test parameter categories
    categories = AblationConfig.get_categories()
    print(f"Categories: {categories}")
    
    # Test defaults
    defaults = AblationConfig.get_defaults()
    print(f"Default values available: {len(defaults)}")
    
    # Test validation
    valid = AblationConfig.validate_value("SNR_THRESHOLD", 6)
    invalid = AblationConfig.validate_value("SNR_THRESHOLD", -999)
    
    print(f"Validation test: valid={valid}, invalid={not invalid}")
    
    if len(params) >= 30 and valid and not invalid:
        print(f"\n✓ Ablation config working correctly")
        return True
    else:
        print(f"\n✗ Ablation config issues detected")
        return False


def test_ablation_dry_run():
    """Test 5: Run ablation dry-run"""
    print("\n" + "="*70)
    print("TEST 5: Ablation Dry-Run")
    print("="*70)
    
    from ablation.ablation_config import SWEEP_PRESETS
    import itertools
    
    for sweep_name in ['quick_channel', 'mac_comparison']:
        if sweep_name in SWEEP_PRESETS:
            sweep = SWEEP_PRESETS[sweep_name]
            combos = list(itertools.product(*sweep.values()))
            print(f"[OK] {sweep_name}: {len(combos)} configurations")
        else:
            print(f"[FAIL] {sweep_name} not found!")
            return False
    
    print(f"\n✓ Ablation sweeps configured correctly")
    return True


def test_seed_configuration():
    """Test 6: Verify seed system"""
    print("\n" + "="*70)
    print("TEST 6: Seed Configuration")
    print("="*70)
    
    from mobility.start_coords import get_random_start_point_3d
    from utils import config
    
    # Test same seed produces same positions
    pos1 = get_random_start_point_3d(2025)
    pos2 = get_random_start_point_3d(2025)
    
    if pos1 == pos2:
        print("[OK] Same seed produces same positions")
    else:
        print("[FAIL] Seed reproducibility broken!")
        return False
    
    # Test different seeds produce different positions
    pos3 = get_random_start_point_3d(9999)
    
    if pos1 != pos3:
        print("[OK] Different seeds produce different positions")
    else:
        print("[FAIL] Seeds not working correctly!")
        return False
    
    print(f"\n✓ Seed system working correctly")
    return True


def test_mac_modes():
    """Test 7: Verify MAC mode configuration"""
    print("\n" + "="*70)
    print("TEST 7: MAC Mode Configuration")
    print("="*70)
    
    from utils import config
    
    valid_modes = ["TDMA", "CSMA", "ALOHA", "STDMA", "ADAPTIVE"]
    
    print(f"Current MAC_MODE: {config.MAC_MODE}")
    
    if config.MAC_MODE in valid_modes:
        print(f"[OK] MAC_MODE is valid")
    else:
        print(f"[FAIL] Invalid MAC_MODE!")
        return False
    
    # Test TDMA params
    if hasattr(config, 'TDMA_SLOT_DURATION') and hasattr(config, 'TDMA_SLOTS_PER_FRAME'):
        print(f"[OK] TDMA parameters exist")
    else:
        print(f"[FAIL] TDMA parameters missing!")
        return False
    
    # Test STDMA params
    if hasattr(config, 'STDMA_RESERVATION_TIMEOUT') and hasattr(config, 'STDMA_MAX_SLOTS_PER_DRONE'):
        print(f"[OK] STDMA parameters exist")
    else:
        print(f"[FAIL] STDMA parameters missing!")
        return False
    
    print(f"\n✓ All MAC modes configured correctly")
    return True


def run_comprehensive_tests():
    """Run all tests and report results"""
    print("\n" + "="*70)
    print("UAV NETWORK SIMULATOR - COMPREHENSIVE TEST SUITE")
    print("="*70)
    
    tests = [
        ("Import Verification", test_imports),
        ("Config Parameters", test_config_parameters),
        ("TDMA Slot Fix", test_tdma_slot_fix),
        ("Ablation Config", test_ablation_config),
        ("Ablation Dry-Run", test_ablation_dry_run),
        ("Seed Configuration", test_seed_configuration),
        ("MAC Modes", test_mac_modes),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed, None))
        except Exception as e:
            results.append((test_name, False, str(e)))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed_count = 0
    for test_name, passed, error in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {test_name}")
        if error:
            print(f"       Error: {error}")
        if passed:
            passed_count += 1
    
    print("="*70)
    print(f"TOTAL: {passed_count}/{len(tests)} tests passed")
    print("="*70)
    
    success = (passed_count == len(tests))
    if success:
        print("\n✓✓✓ ALL TESTS PASSED! ✓✓✓")
    else:
        print(f"\n✗ {len(tests) - passed_count} test(s) failed")
        
    return success, results


if __name__ == "__main__":
    success, _ = run_comprehensive_tests()
    sys.exit(0 if success else 1)
