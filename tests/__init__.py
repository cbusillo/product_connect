import importlib
from pathlib import Path

addon_tests_dir = Path(__file__).parent

for test_file in addon_tests_dir.glob("test_*.py"):
    module_name = test_file.stem
    importlib.import_module(f".{module_name}", package=__name__)