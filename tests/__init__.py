import importlib
from pathlib import Path

addon_tests_dir = Path(__file__).parent
for test_file in addon_tests_dir.glob("test_*.py"):
    module_name = test_file.stem
    importlib.import_module(f".{module_name}", package=__name__)

services_test_dir = addon_tests_dir.parent / "services" / "tests"
if services_test_dir.exists():
    for test_file in services_test_dir.glob("test_*.py"):
        module_name = test_file.stem
        importlib.import_module(f"..services.tests.{module_name}", package=__name__)
