import unittest

from application.app_factory import register_global_hotkeys


class FakeKeyboard:
    def __init__(self):
        self.bindings = {}

    def add_hotkey(self, keys, callback, suppress=False):
        self.bindings[keys] = (callback, suppress)


class FakeWordService:
    def reroll_short(self):
        return "short"

    def reroll_prev(self):
        return "previous"

    def reject_current(self):
        return "rejected"


class GlobalHotkeysTests(unittest.TestCase):
    def test_registers_rejection_on_delete_without_leaking_key_to_game(self):
        keyboard = FakeKeyboard()
        service = FakeWordService()

        register_global_hotkeys(keyboard, service)

        callback, suppress = keyboard.bindings["delete"]
        self.assertEqual(callback(), "rejected")
        self.assertTrue(suppress)


if __name__ == "__main__":
    unittest.main(verbosity=2)
