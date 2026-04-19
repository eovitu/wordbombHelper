import logging
import threading

from flask import Blueprint, jsonify
from shared.parsing import json_or_empty

logger = logging.getLogger(__name__)


def create_api_blueprint(deps):
    wm = deps["word_manager"]
    screen_reader = deps["screen_reader"]
    word_service = deps["word_service"]
    autoplay_state = deps["autoplay_state"]
    solver_cache = deps["solver_cache"]
    letterlink_service = deps["letterlink_service"]
    preset_service = deps["preset_service"]
    region_store = deps["region_store"]
    compat_set_ll_region = deps.get("set_ll_grid_region")
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
        solver_cache.clear()
        threading.Thread(target=solver_cache.build_trie_bg).start()
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
        x = data.get("x")
        y = data.get("y")
        mode = data.get("mode", "classic")

        result = screen_reader.handle_calibration_click(x, y)

        if result.get("status") == "done" and mode == "letterlink":
            region = result["regions"]["turn_region"]
            region_store.set_region(region)
            if compat_set_ll_region:
                compat_set_ll_region(region)
            result["message"] = "Letter Link Grid Calibrated!"

        return jsonify(result)

    @bp.route("/api/letterlink/solve", methods=["POST"])
    @optional_auth_required
    def solve_letter_link():
        try:
            payload, status = letterlink_service.solve()
            return jsonify(payload), status
        except Exception as e:
            logger.error("Error in solve_letter_link: %s", str(e), exc_info=True)
            return jsonify({"status": "error", "message": f"Internal Error: {str(e)}"}), 500

    @bp.route("/api/autoplay/toggle", methods=["POST"])
    @optional_auth_required
    def toggle_autoplay():
        from overlay_manager import get_overlay

        try:
            active = screen_reader.toggle_watching()
            overlay = get_overlay()
            if overlay:
                if active:
                    overlay.root.after(0, overlay.show)
                else:
                    overlay.root.after(0, overlay.hide)

            return jsonify({"status": "active" if active else "inactive"})
        except Exception as e:
            logger.error("Error toggling auto-play: %s", e)
            return jsonify({"status": "error", "message": str(e)}), 500

    @bp.route("/api/autoplay/status", methods=["GET"])
    def get_autoplay_status():
        state = screen_reader.get_state()
        state["logs"] = autoplay_state.last_logs(10)
        return state

    @bp.route("/api/autoplay/config", methods=["POST"])
    @optional_auth_required
    def update_autoplay_config():
        data = json_or_empty()
        cfg = autoplay_state.update_from_payload(data)
        logger.info("Auto-Play config updated: %s", cfg)
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
