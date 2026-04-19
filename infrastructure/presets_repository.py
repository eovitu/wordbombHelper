import json
import logging
import os

logger = logging.getLogger(__name__)


class FilePresetRepository:
    def __init__(self, presets_file):
        self.presets_file = presets_file

    def load(self):
        if not os.path.exists(self.presets_file):
            return {}
        try:
            with open(self.presets_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Error loading presets: %s", e)
            return {}

    def save(self, presets):
        try:
            with open(self.presets_file, "w", encoding="utf-8") as f:
                json.dump(presets, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error("Error saving presets: %s", e)
            return False
