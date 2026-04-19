class PresetService:
    def __init__(self, preset_repository):
        self.preset_repository = preset_repository

    def get_all(self):
        return self.preset_repository.load()

    def save(self, name, config):
        if not name or not config:
            return {"status": "error", "message": "Name and config required"}, 400

        presets = self.preset_repository.load()
        presets[name] = config
        if self.preset_repository.save(presets):
            return {"status": "success"}, 200
        return {"status": "error", "message": "Failed to save file"}, 500

    def delete(self, name):
        presets = self.preset_repository.load()
        if name in presets:
            del presets[name]
            if self.preset_repository.save(presets):
                return {"status": "success"}, 200
        return {"status": "error", "message": "Preset not found or delete failed"}, 404
