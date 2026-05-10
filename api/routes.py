import logging

from flask import Blueprint, jsonify

from shared.parsing import json_or_empty

logger = logging.getLogger(__name__)


def create_api_blueprint(deps):
    wm = deps["word_manager"]
    screen_reader = deps["screen_reader"]
    word_service = deps["word_service"]
    autoplay_state = deps["autoplay_state"]
    preset_service = deps["preset_service"]
    region_store = deps["region_store"]
    optional_auth_required = deps["optional_auth_required"]

    bp = Blueprint("api", __name__)

    @bp.route("/api/languages")
    def get_languages():
        return jsonify(wm.get_languages())

    @bp.route("/api/sublists")
    def get_sublists_map():
        return jsonify(wm.get_sublists_map())

    @bp.route("/api/sublists/<lang>")
    def get_sublists_for_lang(lang):
        return jsonify(wm.get_sublists(lang))

    @bp.route("/api/word", methods=["POST"])
    @optional_auth_required
    def get_word():
        data = json_or_empty()
        word = word_service.get_word_from_payload(data)
        return jsonify({"word": word})

    @bp.route("/api/reset", methods=["POST"])
    @optional_auth_required
    def reset_words():
        word_service.reset_words()
        return jsonify({"status": "success"})

    @bp.route("/api/calibration/start", methods=["POST"])
    @optional_auth_required
    def start_calibration():
        screen_reader.start_calibration()
        return jsonify({"status": "started", "step": "turn_start", "message": "Click top-left of 'My Turn' indicator"})

    @bp.route("/api/calibration/click", methods=["POST"])
    @optional_auth_required
    def calibration_click():
        data = json_or_empty()
        raw_x = data.get("x")
        raw_y = data.get("y")

        if raw_x is None or raw_y is None:
            return jsonify({"status": "error", "message": "Coordinates 'x' and 'y' are required"}), 400

        try:
            x = int(round(float(raw_x)))
            y = int(round(float(raw_y)))
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "Invalid numeric coordinates"}), 400

        result = screen_reader.handle_calibration_click(x, y)

        if result.get("status") == "done":
            region = result["regions"]["turn_region"]
            try:
                region_store.set_region(region)
                screen_reader.turn_region = region_store.get_region() or region
                screen_reader.prompt_region = screen_reader.turn_region
            except Exception:
                pass

        return jsonify(result)

    @bp.route("/api/autoplay/toggle", methods=["POST"])
    @optional_auth_required
    def toggle_autoplay():
        try:
            active = screen_reader.toggle_watching()
            return jsonify({"status": "active" if active else "inactive"})
        except Exception as e:
            logger.error("Error toggling auto-play: %s", e)
            return jsonify({"status": "error", "message": str(e)}), 500

    @bp.route("/api/autoplay/status", methods=["GET"])
    def get_autoplay_status():
        state = screen_reader.get_state()
        cfg = autoplay_state.snapshot_config()
        state["logs"] = autoplay_state.last_logs(10)
        state["autoplay_lang"] = cfg.get("lang")
        state["autoplay_strategy"] = cfg.get("strategy")
        return state

    @bp.route("/api/autoplay/config", methods=["POST"])
    @optional_auth_required
    def update_autoplay_config():
        data = json_or_empty()
        cfg = autoplay_state.update_from_payload(data)
        if cfg.get("lang"):
            wm.current_language = cfg["lang"]
        return jsonify({"status": "ok", "config": cfg})

    @bp.route("/api/presets", methods=["GET"])
    def get_presets():
        return jsonify(preset_service.get_all())

    @bp.route("/api/presets/save", methods=["POST"])
    @optional_auth_required
    def save_preset():
        data = json_or_empty()
        payload, status = preset_service.save(data.get("name"), data.get("config"))
        return jsonify(payload), status

    @bp.route("/api/presets/delete", methods=["POST"])
    @optional_auth_required
    def delete_preset():
        data = json_or_empty()
        payload, status = preset_service.delete(data.get("name"))
        return jsonify(payload), status

    return bp
