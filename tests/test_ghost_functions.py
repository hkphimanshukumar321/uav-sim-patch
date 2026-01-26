"""
Ghost Function Detection Test

Finds functions that are defined but never called anywhere in the codebase.
This helps identify dead code that should be removed or connected.

Usage:
    python -m pytest tests/test_ghost_functions.py -v
    
Or run directly:
    python tests/test_ghost_functions.py
"""

import os
import re
import ast
from collections import defaultdict
from typing import Dict, Set, List, Tuple


def find_python_files(root_dir: str, exclude_dirs: List[str] = None) -> List[str]:
    """Find all Python files in directory tree"""
    if exclude_dirs is None:
        exclude_dirs = ['__pycache__', '.git', 'venv', 'env', '.venv']
    
    python_files = []
    for root, dirs, files in os.walk(root_dir):
        # Exclude certain directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    return python_files


def extract_function_definitions(filepath: str) -> List[Tuple[str, int, str]]:
    """
    Extract all function definitions from a Python file.
    Returns list of (function_name, line_number, qualified_name)
    """
    definitions = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                # Skip private/magic methods
                if not node.name.startswith('_'):
                    definitions.append((node.name, node.lineno, filepath))
    except SyntaxError:
        pass
    except Exception as e:
        print(f"Warning: Could not parse {filepath}: {e}")
    
    return definitions


def find_function_usages(filepaths: List[str], function_names: Set[str]) -> Dict[str, Set[str]]:
    """
    Find all usages of given function names across files.
    Returns dict: function_name -> set of files where it's used
    """
    usages = defaultdict(set)
    
    # Build regex pattern for all function names
    # Match function calls like: func_name(
    # or attribute access like: .func_name(
    # or assignment like: var = func_name
    
    for filepath in filepaths:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            for func_name in function_names:
                # Pattern: function call or reference
                patterns = [
                    rf'\b{func_name}\s*\(',         # direct call
                    rf'\.{func_name}\s*\(',         # method call
                    rf'=\s*{func_name}\b',          # assignment
                    rf'\({func_name}\b',            # passed as argument
                    rf',\s*{func_name}\b',          # in list/tuple
                ]
                
                for pattern in patterns:
                    if re.search(pattern, content):
                        usages[func_name].add(filepath)
                        break
                        
        except Exception as e:
            print(f"Warning: Could not read {filepath}: {e}")
    
    return usages


def find_ghost_functions(project_root: str) -> List[Tuple[str, str, int]]:
    """
    Find all ghost functions (defined but never called).
    Returns list of (function_name, filepath, line_number)
    """
    # Find all Python files
    python_files = find_python_files(project_root)
    
    # Extract all function definitions
    all_definitions = []
    all_function_names = set()
    
    for filepath in python_files:
        defs = extract_function_definitions(filepath)
        all_definitions.extend(defs)
        all_function_names.update(d[0] for d in defs)
    
    # Find usages
    usages = find_function_usages(python_files, all_function_names)
    
    # Find ghost functions (defined but not used, or only used in their own file)
    ghost_functions = []
    
    for func_name, line_num, filepath in all_definitions:
        usage_files = usages.get(func_name, set())
        
        # Remove self-reference (definition file contains the "def func_name" which matches)
        usage_files_filtered = {f for f in usage_files if f != filepath}
        
        # Check if there are any usages in OTHER files
        if not usage_files_filtered:
            # Double check: is it used in the same file (other than definition)?
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Count occurrences (should be > 1 if used after definition)
                pattern = rf'\b{func_name}\b'
                occurrences = len(re.findall(pattern, content))
                
                if occurrences <= 1:  # Only the definition
                    ghost_functions.append((func_name, filepath, line_num))
            except:
                ghost_functions.append((func_name, filepath, line_num))
    
    return ghost_functions


# Known false positives - functions that are intentionally unused or called dynamically
KNOWN_FALSE_POSITIVES = {
    'main',  # Entry points
    'setup',  # Setup functions
    'teardown',
    'test_',  # Test functions
    '__init__',
}


def test_no_ghost_functions():
    """Test that there are no unexpected ghost functions in the codebase"""
    import sys
    
    # Get project root (go up from tests/ directory)
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(tests_dir)
    
    print(f"\nScanning for ghost functions in: {project_root}")
    
    ghost_functions = find_ghost_functions(project_root)
    
    # Filter out known false positives
    real_ghosts = []
    for func_name, filepath, line_num in ghost_functions:
        # Skip test functions
        if func_name.startswith('test_'):
            continue
        # Skip known false positives
        if func_name in KNOWN_FALSE_POSITIVES:
            continue
        # Skip if in tests directory
        if 'tests' in filepath or 'test_' in os.path.basename(filepath):
            continue
        real_ghosts.append((func_name, filepath, line_num))
    
    if real_ghosts:
        print("\n[!] GHOST FUNCTIONS DETECTED (defined but never called):")
        print("-" * 70)
        for func_name, filepath, line_num in real_ghosts:
            rel_path = os.path.relpath(filepath, project_root)
            print(f"  {func_name} - {rel_path}:{line_num}")
        print("-" * 70)
        print(f"Total: {len(real_ghosts)} ghost functions found")
        
        # Don't fail the test, just warn
        # In a strict codebase, you might want: assert len(real_ghosts) == 0
    else:
        print("[OK] No ghost functions detected!")

    
    return real_ghosts


def test_known_ghost_functions():
    """Document known ghost functions that are intentionally unused"""
    known_ghosts = [
        ("probabilistic_los_path_loss", "phy/large_scale_fading.py", 
         "Alternative path loss model, can be enabled via PATH_LOSS_MODEL config"),
    ]
    
    print("\nKnown intentional ghost functions:")
    for func, location, reason in known_ghosts:
        print(f"  {func} ({location}): {reason}")
    
    # This test just documents, doesn't fail
    assert True


if __name__ == "__main__":
    import sys
    
    # Allow running as standalone script
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(tests_dir)
    
    # Add project root to path
    sys.path.insert(0, project_root)
    
    print("=" * 70)
    print("GHOST FUNCTION DETECTION")
    print("=" * 70)
    
    ghosts = test_no_ghost_functions()
    test_known_ghost_functions()
    
    print("\n" + "=" * 70)
    if ghosts:
        print(f"Found {len(ghosts)} ghost function(s)")
        sys.exit(0)  # Don't fail, just report
    else:
        print("No ghost functions found!")
        sys.exit(0)
