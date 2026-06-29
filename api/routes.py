import json
import logging
import time

from flask import Blueprint, Response, jsonify, stream_with_context

from shared.parsing import json_or_empty

logger = logging.getLogger(__name__)


def create_api_blueprint(deps):
    wm = deps["word_manager"]
    screen_reader = deps["screen_reader"]
    word_service = deps["word_service"]
    autoplay_state = deps["autoplay_state"]
    preset_service = deps["preset_service"]
    region_store = deps["region_store"]
    used_word_scanner = deps.get("used_word_scanner")
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
        if used_word_scanner:
            used_word_scanner.reset()  # esquece palavras aprendidas (novo match)
        return jsonify({"status": "success"})

    @bp.route("/api/calibration/start", methods=["POST"])
    @optional_auth_required
    def start_calibration():
        data = json_or_empty()
        target = "solve" if data.get("target") == "solve" else "turn"
        screen_reader.start_calibration(target=target)
        msg = ("Clique no canto superior-esquerdo do painel SOLVE" if target == "solve"
               else "Click top-left of 'My Turn' indicator")
        return jsonify({"status": "started", "step": "turn_start", "target": target, "message": msg})

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

        # Só persiste a região do PROMPT (Pipeline A). Para target=solve, o screen_reader
        # já persistiu via on_solve_region_calibrated — não tocar no turn_region aqui.
        if result.get("status") == "done" and result.get("target") != "solve":
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

    @bp.route("/api/stream")
    def event_stream():
        """SSE: empurra atualizações de palavra/preview/status ao cliente sem polling.
        Verifica mudanças a cada 20ms → latência avg ~10ms vs ~75ms do polling de 150ms.
        """
        def generate():
            last = {}
            try:
                while True:
                    cur = {
                        "word": screen_reader.suggested_word or "",
                        "preview": screen_reader.preview_prompt or "",
                        "status": screen_reader.status,
                        "watching": screen_reader.is_watching,
                    }
                    if cur != last:
                        last = dict(cur)
                        yield f"data: {json.dumps(cur)}\n\n"
                    time.sleep(0.020)
            except GeneratorExit:
                pass

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @bp.route("/api/autoplay/status", methods=["GET"])
    def get_autoplay_status():
        state = screen_reader.get_state()
        cfg = autoplay_state.snapshot_config()
        state["logs"] = autoplay_state.last_logs(10)
        state["autoplay_lang"] = cfg.get("lang")
        state["autoplay_strategy"] = cfg.get("strategy")
        if used_word_scanner:
            state["learned_words"] = used_word_scanner.learned_count
            state["solve_region_set"] = used_word_scanner.source.region_ready()
            state["learned_log"] = used_word_scanner.learned_log()
        if getattr(word_service, "missing_prompts", None):
            state["missing_prompts"] = word_service.missing_prompts.snapshot()
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
