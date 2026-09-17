"""Testes dos snapshots e sinais de incerteza do diagnóstico OCR."""
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screen_reader import ScreenReader  # noqa: E402


def metadata(**overrides):
    value = {
        "captured_at": 123.0,
        "region": {"x1": 1, "y1": 2, "width": 30, "height": 20},
        "source_size": {"width": 30, "height": 20},
        "processed_size": {"width": 30, "height": 20},
        "white_pixels": 100,
        "ocr_ms": 4.5,
        "candidate": "ar",
        "confidence": 60.0,
        "keyword_detected": True,
        "is_my_turn": True,
        "accepted_prompt": "ar",
    }
    value.update(overrides)
    return value


class TestOcrDiagnostics(unittest.TestCase):
    def setUp(self):
        self.reader = ScreenReader()
        self.preview = np.full((20, 30, 3), 120, dtype=np.uint8)
        self.processed = np.full((20, 30), 255, dtype=np.uint8)

    def test_preview_is_available_as_png_without_exposing_live_array(self):
        self.reader._record_ocr_diagnostic(self.preview, self.processed, metadata())

        image = self.reader.get_preview_png()
        snapshot = self.reader.get_last_capture_snapshot("preview")

        self.assertTrue(image.startswith(b"\x89PNG"))
        self.assertEqual(snapshot["mime_type"], "image/jpeg")
        self.assertEqual(snapshot["metadata"]["candidate"], "ar")
        self.assertIsNot(snapshot["metadata"], self.reader._last_ocr_snapshot["metadata"])

    def test_uncertainty_reports_low_confidence_candidate(self):
        self.reader._record_ocr_diagnostic(
            self.preview,
            self.processed,
            metadata(confidence=30.0, accepted_prompt=None),
        )

        state = self.reader.get_state()["ocr_uncertain"]

        self.assertTrue(state["uncertain"])
        self.assertEqual(state["reason"], "low_confidence")
        self.assertEqual(state["candidate"], "ar")

    def test_replay_uses_saved_processed_image_without_changing_detection_state(self):
        self.reader._record_ocr_diagnostic(self.preview, self.processed, metadata())
        self.reader._read_prompt_and_turn = lambda image: ("re", 91.0, True)
        before = (self.reader._turn_confirm_streak, self.reader.last_suggested_prompt)

        replay = self.reader.replay_last_capture()

        self.assertEqual(replay["candidate"], "re")
        self.assertEqual(replay["confidence"], 91.0)
        self.assertTrue(replay["image"].startswith(b"\x89PNG"))
        self.assertEqual((self.reader._turn_confirm_streak, self.reader.last_suggested_prompt), before)

    def test_explicit_replay_artifact_includes_metadata_and_is_written_to_requested_directory(self):
        self.reader._record_ocr_diagnostic(self.preview, self.processed, metadata())
        self.reader._read_prompt_and_turn = lambda image: ("re", 91.0, True)

        with tempfile.TemporaryDirectory() as directory:
            artifact = self.reader.save_ocr_diagnostic_replay(directory)

            self.assertTrue(os.path.isfile(artifact["image_path"]))
            self.assertTrue(os.path.isfile(artifact["metadata_path"]))
            self.assertEqual(artifact["replay"]["replay_candidate"], "re")

    def test_manual_override_traps_the_corrected_prompt_until_lock_is_cleared(self):
        corrected = self.reader.override_prompt("D'Á")

        self.assertEqual(corrected, "d'á")
        self.assertEqual(self.reader.last_suggested_prompt, "d'á")
        self.assertEqual(self.reader.preview_prompt, "d'á")
        self.assertEqual(self.reader.get_state()["manual_prompt_override"], "d'á")

        self.reader._clear_prompt_lock()

        self.assertIsNone(self.reader.get_state()["manual_prompt_override"])
        self.assertEqual(self.reader.last_suggested_prompt, "")

    def test_manual_override_rejects_empty_or_out_of_range_prompt(self):
        with self.assertRaises(ValueError):
            self.reader.override_prompt("x")

    def test_manual_correction_ignores_old_ocr_then_releases_for_next_stable_prompt(self):
        found = []
        self.reader.set_callback(lambda prompt: found.append(prompt))
        self.reader.last_suggested_prompt = "iscc"
        self.reader.override_prompt("isc")

        for _ in range(5):
            self.assertTrue(self.reader._handle_manual_override_candidate("iscc"))
        self.assertEqual(found, [])
        self.assertEqual(self.reader.last_suggested_prompt, "isc")

        for _ in range(self.reader.switch_confirm_frames):
            self.assertTrue(self.reader._handle_manual_override_candidate("ad"))

        self.assertEqual(found, ["ad"])
        self.assertEqual(self.reader.last_suggested_prompt, "ad")
        self.assertIsNone(self.reader.get_state()["manual_prompt_override"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
