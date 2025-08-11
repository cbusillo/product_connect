"""Test to ensure all tours have corresponding test runners.

This test will fail if any tour in static/tests/tours/ doesn't have a test runner,
preventing silent failures where tours exist but never run.
"""

import re
from pathlib import Path
from odoo.tests import tagged
from ..fixtures.base import UnitTestCase


@tagged("post_install", "-at_install", "unit_test")
class TestTourCoverage(UnitTestCase):
    """Ensure all tours have test runners to prevent silent failures"""

    def test_all_tours_have_runners(self) -> None:
        """Verify every tour file has a corresponding test runner"""
        # Find all tour files
        addon_path = Path(__file__).parent.parent
        tours_path = addon_path / "static" / "tests" / "tours"

        if not tours_path.exists():
            self.skipTest("No tours directory found")

        # Extract tour names from tour files
        tour_files = {}
        for tour_file in tours_path.glob("*.js"):
            if tour_file.name == "basic_tour.js":  # Skip template
                continue

            with open(tour_file) as f:
                content = f.read()
                # Extract tour name from registry.category("web_tour.tours").add("tour_name"
                match = re.search(r'registry\.category\("web_tour\.tours"\)\.add\("([^"]+)"', content)
                if match:
                    tour_name = match.group(1)
                    tour_files[tour_name] = tour_file.name

        # Find all test runners
        test_runners = set()

        # Check main tests directory
        tests_dir = Path(__file__).parent
        for test_file in tests_dir.glob("test_*.py"):
            if test_file.name == "test_tour_coverage.py":  # Skip self
                continue

            with open(test_file) as f:
                content = f.read()
                # Look for start_tour calls
                tour_matches = re.findall(r'self\.start_tour\([^,]+,\s*["\']([^"\']+)["\']', content)
                test_runners.update(tour_matches)

        # Check tours subdirectory
        tours_test_dir = tests_dir / "tours"
        if tours_test_dir.exists():
            for test_file in tours_test_dir.glob("test_*.py"):
                with open(test_file) as f:
                    content = f.read()
                    tour_matches = re.findall(r'self\.start_tour\([^,]+,\s*["\']([^"\']+)["\']', content)
                    test_runners.update(tour_matches)

        # Find tours without runners
        missing_runners = []
        for tour_name, tour_file in tour_files.items():
            if tour_name not in test_runners:
                missing_runners.append((tour_name, tour_file))

        # Report missing runners
        if missing_runners:
            message = "The following tours do not have test runners:\n"
            for tour_name, tour_file in missing_runners:
                message += f"  - {tour_file}: tour '{tour_name}' has no test runner\n"
            message += "\nCreate a test class with:\n"
            message += "  self.start_tour('/odoo', 'tour_name', login=self.test_user.login)\n"
            self.fail(message)

        # Also check for test runners without tours (optional warning)
        orphaned_runners = []
        for runner_tour in test_runners:
            if runner_tour not in tour_files:
                orphaned_runners.append(runner_tour)

        if orphaned_runners:
            print(f"WARNING: The following test runners have no corresponding tour files: {orphaned_runners}")

        # Success message
        print(f"✓ Tour coverage check passed: {len(tour_files)} tours, {len(test_runners)} runners")
