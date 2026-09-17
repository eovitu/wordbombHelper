"""Testes do armazenamento atômico de perfis de calibração."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from application.calibration_profiles import (  # noqa: E402
    CalibrationProfileNotFoundError,
    CalibrationProfileValidationError,
    CalibrationProfiles,
)


TURN = {"x1": 10, "y1": 20, "x2": 210, "y2": 140}
SOLVE = {"x1": 400, "y1": 30, "width": 250, "height": 320}


class CalibrationProfilesTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "profiles.json"
        self.service = CalibrationProfiles(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_create_normalizes_both_regions_and_activates_first_profile(self):
        profile = self.service.create("Mesa principal", TURN, SOLVE)

        self.assertTrue(profile["active"])
        self.assertEqual(profile["turn_region"], {"x1": 10, "y1": 20, "x2": 210, "y2": 140, "width": 200, "height": 120})
        self.assertEqual(profile["solve_region"], {"x1": 400, "y1": 30, "width": 250, "height": 320})
        self.assertEqual(self.service.get_active_profile()["id"], profile["id"])

    def test_crud_and_active_profile_survive_reopen(self):
        first = self.service.create("Casa", TURN)
        second = self.service.create("Trabalho", {"x1": 1, "y1": 2, "width": 30, "height": 40}, SOLVE)
        changed = self.service.update(second["id"], name="Escritório", solve_region=None)
        active = self.service.activate(changed["id"])

        reloaded = CalibrationProfiles(self.path)

        self.assertEqual([profile["name"] for profile in reloaded.list_profiles()], ["Casa", "Escritório"])
        self.assertEqual(reloaded.get_active_profile()["id"], active["id"])
        self.assertIsNone(reloaded.get_profile(active["id"])["solve_region"])
        reloaded.delete(first["id"])
        self.assertEqual(len(reloaded.list_profiles()), 1)

    def test_rejects_invalid_regions_and_duplicate_names_without_partial_write(self):
        self.service.create("Casa", TURN)
        before = self.path.read_text(encoding="utf-8")

        with self.assertRaises(CalibrationProfileValidationError):
            self.service.create("casa", {"x1": 2, "y1": 4, "width": 0, "height": 9})
        with self.assertRaises(CalibrationProfileValidationError):
            self.service.create("Outra", {"x1": 2, "y1": 4, "width": 0, "height": 9})

        self.assertEqual(self.path.read_text(encoding="utf-8"), before)
        self.assertEqual([profile["name"] for profile in self.service.list_profiles()], ["Casa"])

    def test_delete_active_leaves_no_active_profile(self):
        profile = self.service.create("Casa", TURN)

        self.service.delete(profile["id"])

        self.assertEqual(self.service.list_profiles(), [])
        self.assertIsNone(self.service.get_active_profile())
        persisted = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertIsNone(persisted["active_profile_id"])

    def test_missing_profile_is_explicit_error(self):
        with self.assertRaises(CalibrationProfileNotFoundError):
            self.service.activate("does-not-exist")

    def test_atomic_write_leaves_no_temporary_file(self):
        self.service.create("Casa", TURN)

        self.assertEqual(list(Path(self.temp.name).glob(".profiles.json.*.tmp")), [])
        self.assertTrue(self.path.is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
