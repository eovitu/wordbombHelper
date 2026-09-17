from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class GameUiContractTests(unittest.TestCase):
    def test_easy_strategy_and_prompt_coverage_are_wired_to_the_page(self):
        template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")

        self.assertIn('option value="easy"', template)
        self.assertIn('id="prompt-coverage"', template)
        self.assertIn("function updatePromptCoverage(prompt, total)", script)
        self.assertIn("updatePromptCoverage(preview, suggestionTotal)", script)


if __name__ == "__main__":
    unittest.main()
