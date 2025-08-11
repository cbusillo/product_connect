import importlib
from pathlib import Path

test_dirs = ["unit", "integration", "tour"]
for test_dir in test_dirs:
    test_path = Path(__file__).parent / test_dir
    if test_path.exists():
        for test_file in test_path.glob("test_*.py"):
            module_name = test_file.stem
            full_module_name = f"{__name__}.{test_dir}.{module_name}"
            globals()[module_name] = importlib.import_module(full_module_name)
