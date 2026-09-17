"""Contratos HTTP das rotas novas, usando apenas dependências locais falsas."""
from dataclasses import dataclass
import os
from pathlib import Path
import sys
import tempfile
import unittest

from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.routes import create_api_blueprint  # noqa: E402
from application.calibration_profiles import CalibrationProfiles  # noqa: E402
from application.personal_dictionary import PersonalDictionary  # noqa: E402
from application.practice_service import PracticeEvaluation, PracticeHint, PracticeRound  # noqa: E402


def no_auth(handler):
    return handler


class FakeWordManager:
    def __init__(self):
        self.refreshed = []

    def refresh_language(self, language):
        self.refreshed.append(language)


class FakeRegionStore:
    def __init__(self, region=None):
        self.region = region
        self.cleared = False

    def get_region(self):
        return self.region

    def set_region(self, region):
        self.region = region

    def clear_persistence(self):
        self.region = None
        self.cleared = True


class FakeScreenReader:
    def __init__(self):
        self.turn_region = None
        self.prompt_region = None
        self.preview = b"\x89PNG\r\n\x1a\npreview"
        self.replay = {"image_path": "debug/replay.png", "metadata_path": "debug/replay.json"}

    def get_preview_png(self):
        return self.preview

    def capture_ocr_replay(self):
        return self.replay


class FakeWordService:
    def __init__(self):
        self.reject_result = None
        self.corrected = []

    def reroll_short(self):
        return {"word": "curta", "index": 2, "total": 3}

    def correct_prompt(self, prompt):
        if prompt == "x":
            raise ValueError("Prompt inválido")
        self.corrected.append(prompt)
        return {"word": "casa", "index": 1, "total": 2}

    def reject_current(self):
        return self.reject_result


class FakePracticeService:
    def generate_round(self, language):
        return PracticeRound(language, "ca", "casa")

    def evaluate(self, round_, answer, *, elapsed_seconds):
        return PracticeEvaluation(answer == "casa", "correct" if answer == "casa" else "not_in_dictionary", answer, elapsed_seconds)

    def hint(self, round_, kind):
        return PracticeHint(kind, 4 if kind == "length" else "c")


class FakeAutoplayState:
    pass


class FakePresetService:
    pass


class ApiContractsTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.wm = FakeWordManager()
        self.word_service = FakeWordService()
        self.reader = FakeScreenReader()
        self.turn_store = FakeRegionStore({"x1": 10, "y1": 20, "width": 200, "height": 100})
        self.solve_store = FakeRegionStore({"x1": 300, "y1": 30, "width": 80, "height": 250})
        self.dictionary = PersonalDictionary(Path(self.temp.name) / "personal")
        self.profiles = CalibrationProfiles(Path(self.temp.name) / "profiles.json")
        app = Flask(__name__)
        app.config.update(TESTING=True)
        app.register_blueprint(create_api_blueprint({
            "word_manager": self.wm,
            "personal_dictionary": self.dictionary,
            "calibration_profiles": self.profiles,
            "solve_region_store": self.solve_store,
            "practice_service": FakePracticeService(),
            "screen_reader": self.reader,
            "word_service": self.word_service,
            "autoplay_state": FakeAutoplayState(),
            "preset_service": FakePresetService(),
            "region_store": self.turn_store,
            "used_word_scanner": None,
            "optional_auth_required": no_auth,
        }))
        self.client = app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def post(self, path, payload=None):
        return self.client.post(path, json=payload or {})

    def test_short_reroll_and_prompt_correction_contracts(self):
        reroll = self.post("/api/reroll/short")
        invalid = self.post("/api/prompt/correct", {"prompt": "x"})
        valid = self.post("/api/prompt/correct", {"prompt": "ca"})

        self.assertEqual((reroll.status_code, reroll.get_json()), (200, {"word": "curta", "index": 2, "total": 3}))
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.get_json()["status"], "error")
        self.assertEqual((valid.status_code, valid.get_json()["word"]), (200, "casa"))
        self.assertEqual(self.word_service.corrected, ["ca"])

    def test_reject_reports_no_session_then_returns_next_session_word(self):
        missing = self.post("/api/word/reject")
        self.word_service.reject_result = {"word": "bola", "index": 1, "total": 2}
        active = self.post("/api/word/reject")

        self.assertEqual(missing.status_code, 409)
        self.assertEqual(missing.get_json()["status"], "error")
        self.assertEqual((active.status_code, active.get_json()), (200, self.word_service.reject_result))

    def test_dictionary_mutations_import_and_undo_are_available_by_http(self):
        self.assertEqual(self.post("/api/dictionary/add", {"lang": "Português", "word": "casa"}).status_code, 200)
        edited = self.post("/api/dictionary/edit", {"lang": "Português", "old_word": "casa", "new_word": "casar"})
        self.assertEqual(edited.get_json()["word"], "casar")
        self.assertEqual(self.post("/api/dictionary/delete", {"lang": "Português", "word": "casar"}).status_code, 200)

        preview = self.post("/api/dictionary/preview-import", {"lang": "Português", "text": "bola\ncabana\n"})
        imported = self.post("/api/dictionary/apply-import", {"lang": "Português", "text": "bola\ncabana\n"})
        undo = self.post("/api/dictionary/undo")

        self.assertEqual(preview.get_json()["new_words"], ["bola", "cabana"])
        self.assertEqual(imported.get_json()["added"], ["bola", "cabana"])
        self.assertEqual(undo.status_code, 200)
        self.assertEqual(self.client.get("/api/dictionary?lang=Português").get_json()["words"], [])
        self.assertGreaterEqual(len(self.wm.refreshed), 5)

    def test_dictionary_add_accepts_multiple_space_separated_words(self):
        response = self.post("/api/dictionary/add", {
            "lang": "Português",
            "word": "ENRUDECA ENRUDECAIS ENRUDECAM ENRUDECAMOS ENRUDECAS",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["added"], [
            "enrudeca", "enrudecais", "enrudecam", "enrudecamos", "enrudecas",
        ])
        self.assertEqual(self.dictionary.get_words("Português"), [
            "enrudeca", "enrudecais", "enrudecam", "enrudecamos", "enrudecas",
        ])

    def test_calibration_profile_save_activate_and_delete_apply_both_regions(self):
        saved = self.post("/api/calibration/profiles/save", {"name": "Mesa"})
        profile = saved.get_json()
        activated = self.post("/api/calibration/profiles/activate", {"id": profile["id"]})
        deleted = self.client.delete("/api/calibration/profiles/" + profile["id"])

        self.assertEqual(saved.status_code, 200)
        self.assertTrue(profile["active"])
        self.assertEqual(activated.get_json()["id"], profile["id"])
        self.assertEqual(self.reader.turn_region, self.turn_store.region)
        self.assertEqual(self.solve_store.region["width"], 80)
        self.assertEqual((deleted.status_code, deleted.get_json()), (200, {"status": "success"}))

    def test_practice_new_hint_and_check_contracts(self):
        started = self.post("/api/practice/new", {"lang": "Português", "mode": "hints"})
        hint = self.post("/api/practice/hint", {"kind": "length"})
        checked = self.post("/api/practice/check", {"answer": "casa"})
        second_check = self.post("/api/practice/check", {"answer": "casa"})

        self.assertEqual(started.get_json(), {"prompt": "ca", "mode": "hints"})
        self.assertEqual(hint.get_json(), {"mode": "length", "value": 4})
        self.assertTrue(checked.get_json()["correct"])
        self.assertEqual(second_check.status_code, 409)

    def test_ocr_preview_and_replay_contracts(self):
        preview = self.client.get("/api/ocr/preview")
        replay = self.post("/api/ocr/replay")

        self.assertEqual((preview.status_code, preview.mimetype, preview.data), (200, "image/png", self.reader.preview))
        self.assertEqual((replay.status_code, replay.get_json()), (200, self.reader.replay))


if __name__ == "__main__":
    unittest.main(verbosity=2)
