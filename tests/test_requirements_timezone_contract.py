import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def pinned_version(filename: str, package: str) -> str:
    pattern = re.compile(rf"^{re.escape(package)}==([^\s#]+)$", re.IGNORECASE | re.MULTILINE)
    text = (ROOT / filename).read_text(encoding="utf-8")
    match = pattern.search(text)
    if not match:
        raise AssertionError(f"{package} must have an exact pin in {filename}")
    return match.group(1)


class RequirementsTimezoneContractTest(unittest.TestCase):
    def test_pytz_pin_matches_and_satisfies_croniter_6_floor(self):
        full = pinned_version("requirements.txt", "pytz")
        core = pinned_version("requirements-core.txt", "pytz")
        self.assertEqual(full, core)
        year_match = re.match(r"^(\d{4})\.(\d+)", core)
        self.assertIsNotNone(year_match, core)
        year, release = (int(value) for value in year_match.groups())
        self.assertGreater((year, release), (2021, 1))


if __name__ == "__main__":
    unittest.main()
