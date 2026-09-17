import json
import logging
import threading
import time
from dataclasses import asdict

from flask import Blueprint, Response, jsonify, request, stream_with_context

from application.calibration_profiles import (CalibrationProfileNotFoundError,
                                              CalibrationProfilesError,
                                              CalibrationProfileValidationError)
from application.personal_dictionary import (NotFoundError, PersonalDictionaryError,
                                             UndoUnavailableError, ValidationError)
from application.practice_service import PracticeError
from shared.parsing import json_or_empty

logger = logging.getLogger(__name__)


def create_api_blueprint(deps):
    wm = deps["word_manager"]
    personal_dictionary = deps["personal_dictionary"]
    calibration_profiles = deps["calibration_profiles"]
    solve_region_store = deps["solve_region_store"]
    practice_service = deps["practice_service"]
    screen_reader = deps["screen_reader"]
    word_service = deps["word_service"]
    autoplay_state = deps["autoplay_state"]
    preset_service = deps["preset_service"]
    region_store = deps["region_store"]
    used_word_scanner = deps.get("used_word_scanner")
    match_summary = deps.get("match_summary")
    optional_auth_required = deps["optional_auth_required"]

    bp = Blueprint("api", __name__)
    practice_lock = threading.Lock()
    practice_session = {"round": None, "mode": "normal", "started_at": None}

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

    @bp.route("/api/missing_prompts/export")
    def export_missing_prompts():
        """Exporta os prompts sem palavra como TXT (um por linha, mais frequentes primeiro)."""
        store = getattr(word_service, "missing_prompts", None)
        lines = store.ordered_prompts() if store else []
        body = "\n".join(lines) + ("\n" if lines else "")
        return Response(body, mimetype="text/plain",
                        headers={"Content-Disposition": "attachment; filename=missing_prompts.txt"})

    @bp.route("/api/ambiguous_words/export")
    def export_ambiguous_words():
        """Exporta as leituras OCR ambíguas (não marcadas) como TXT, para revisão manual."""
        store = getattr(used_word_scanner, "ambiguous_store", None) if used_word_scanner else None
        lines = store.ordered_prompts() if store else []
        body = "\n".join(lines) + ("\n" if lines else "")
        return Response(body, mimetype="text/plain",
                        headers={"Content-Disposition": "attachment; filename=ambiguous_ocr.txt"})

    @bp.route("/api/reroll/next", methods=["POST"])
    @optional_auth_required
    def reroll_next():
        return jsonify(word_service.reroll_next() or {"word": "", "index": 0, "total": 0})

    @bp.route("/api/reroll/short", methods=["POST"])
    @optional_auth_required
    def reroll_short():
        return jsonify(word_service.reroll_short() or {"word": "", "index": 0, "total": 0})

    @bp.route("/api/prompt/correct", methods=["POST"])
    @optional_auth_required
    def correct_prompt():
        try:
            return jsonify(word_service.correct_prompt(json_or_empty().get("prompt")))
        except ValueError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400

    @bp.route("/api/word/reject", methods=["POST"])
    @optional_auth_required
    def reject_word():
        result = word_service.reject_current()
        if result is None:
            return jsonify({"status": "error", "message": "Nenhuma sugestão ativa"}), 409
        return jsonify(result)

    @bp.route("/api/reroll/prev", methods=["POST"])
    @optional_auth_required
    def reroll_prev():
        return jsonify(word_service.reroll_prev() or {"word": "", "index": 0, "total": 0})

    @bp.route("/api/reset", methods=["POST"])
    @optional_auth_required
    def reset_words():
        word_service.reset_words()
        if used_word_scanner:
            used_word_scanner.reset()  # esquece palavras aprendidas (novo match)
            # OCR ambíguo é dado de manutenção do match atual → zera junto com as palavras.
            amb = getattr(used_word_scanner, "ambiguous_store", None)
            if amb:
                amb.clear()
        return jsonify({"status": "success"})

    @bp.route("/api/missing_prompts/clear", methods=["POST"])
    @optional_auth_required
    def clear_missing_prompts():
        """Limpa o registro de prompts sem palavra (após adicionar as palavras ao dicionário)."""
        store = getattr(word_service, "missing_prompts", None)
        if store:
            store.clear()
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
            idle_ticks = 0
            try:
                while True:
                    cur = {
                        "word": screen_reader.suggested_word or "",
                        "preview": screen_reader.preview_prompt or "",
                        "status": screen_reader.status,
                        "watching": screen_reader.is_watching,
                        "sidx": screen_reader.suggestion_index,
                        "stot": screen_reader.suggestion_total,
                    }
                    if cur != last:
                        last = dict(cur)
                        idle_ticks = 0
                        yield f"data: {json.dumps(cur)}\n\n"
                    else:
                        # Sem mudança: a cada ~15s manda um comentário-keepalive. Isso força
                        # uma escrita no socket; se o cliente desconectou ocioso, o broken-pipe
                        # dispara GeneratorExit e a thread encerra (senão giraria para sempre).
                        idle_ticks += 1
                        if idle_ticks >= 750:
                            idle_ticks = 0
                            yield ": keepalive\n\n"
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
        state["recover_progress"] = wm.recover_progress()
        state["reset_notice"] = getattr(word_service, "reset_notice", "")
        state["action_notice"] = getattr(word_service, "action_notice", "")
        if match_summary:
            state["match_summary"] = match_summary.snapshot()
        last_summary = getattr(word_service, "last_summary", None)
        if last_summary is not None:
            state["last_match_summary"] = last_summary
        if used_word_scanner:
            state["learned_words"] = used_word_scanner.learned_count
            state["solve_region_set"] = used_word_scanner.source.region_ready()
            state["learned_log"] = used_word_scanner.learned_log()
        if getattr(word_service, "missing_prompts", None):
            state["missing_prompts"] = word_service.missing_prompts.snapshot()
        if used_word_scanner and getattr(used_word_scanner, "ambiguous_store", None):
            state["ambiguous_words"] = used_word_scanner.ambiguous_store.snapshot()
        return state

    @bp.route("/api/ocr/preview")
    def ocr_preview():
        data = screen_reader.get_preview_png()
        if data is None:
            return jsonify({"status": "error", "message": "Ainda não há captura"}), 404
        return Response(data, mimetype="image/png", headers={"Cache-Control": "no-store"})

    @bp.route("/api/ocr/replay", methods=["POST"])
    @optional_auth_required
    def save_ocr_replay():
        result = screen_reader.capture_ocr_replay()
        if result is None:
            return jsonify({"status": "error", "message": "Ainda não há captura"}), 404
        return jsonify(result)

    def dictionary_response(action):
        try:
            return jsonify(action())
        except ValidationError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400
        except NotFoundError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 404
        except UndoUnavailableError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 409
        except PersonalDictionaryError as exc:
            logger.error("Dictionary operation failed: %s", exc)
            return jsonify({"status": "error", "message": str(exc)}), 500

    @bp.route("/api/dictionary")
    def dictionary_list():
        lang = request.args.get("lang", "")
        return dictionary_response(lambda: {"words": personal_dictionary.get_words(lang)})

    @bp.route("/api/dictionary/add", methods=["POST"])
    @optional_auth_required
    def dictionary_add():
        data = json_or_empty()
        def action():
            language = data.get("lang")
            raw = data.get("word")
            tokens = raw.split() if isinstance(raw, str) else []
            if len(tokens) <= 1:
                word = personal_dictionary.add(language, raw)
                wm.refresh_language(language)
                return {"word": word}
            preview = personal_dictionary.preview_import(language, raw)
            added = personal_dictionary.apply_import(preview)
            if added:
                wm.refresh_language(language)
            return {"added": added, "duplicates": preview.duplicates}
        return dictionary_response(action)

    @bp.route("/api/dictionary/edit", methods=["POST"])
    @optional_auth_required
    def dictionary_edit():
        data = json_or_empty()
        def action():
            word = personal_dictionary.edit(data.get("lang"), data.get("old_word"), data.get("new_word"))
            wm.refresh_language(data["lang"])
            return {"word": word}
        return dictionary_response(action)

    @bp.route("/api/dictionary/delete", methods=["POST"])
    @optional_auth_required
    def dictionary_delete():
        data = json_or_empty()
        def action():
            personal_dictionary.delete(data.get("lang"), data.get("word"))
            wm.refresh_language(data["lang"])
            return {"status": "success"}
        return dictionary_response(action)

    @bp.route("/api/dictionary/preview-import", methods=["POST"])
    @optional_auth_required
    def dictionary_preview_import():
        data = json_or_empty()
        def action():
            preview = personal_dictionary.preview_import(data.get("lang"), data.get("text"))
            return {"new_words": preview.new_words, "duplicates": preview.duplicates,
                    "invalid_lines": preview.invalid_lines}
        return dictionary_response(action)

    @bp.route("/api/dictionary/apply-import", methods=["POST"])
    @optional_auth_required
    def dictionary_apply_import():
        data = json_or_empty()
        def action():
            preview = personal_dictionary.preview_import(data.get("lang"), data.get("text"))
            added = personal_dictionary.apply_import(preview)
            if added:
                wm.refresh_language(data["lang"])
            return {"added": added}
        return dictionary_response(action)

    @bp.route("/api/dictionary/undo", methods=["POST"])
    @optional_auth_required
    def dictionary_undo():
        def action():
            result = dict(personal_dictionary.undo())
            wm.refresh_language(result["language"])
            return result
        return dictionary_response(action)

    def profile_response(action):
        try:
            return jsonify(action())
        except CalibrationProfileValidationError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400
        except CalibrationProfileNotFoundError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 404
        except CalibrationProfilesError as exc:
            logger.error("Calibration profile operation failed: %s", exc)
            return jsonify({"status": "error", "message": str(exc)}), 500

    @bp.route("/api/calibration/profiles")
    def list_calibration_profiles():
        return jsonify({"profiles": calibration_profiles.list_profiles()})

    @bp.route("/api/calibration/profiles/save", methods=["POST"])
    @optional_auth_required
    def save_calibration_profile():
        data = json_or_empty()
        return profile_response(lambda: calibration_profiles.create(
            data.get("name"), region_store.get_region(), solve_region_store.get_region()))

    @bp.route("/api/calibration/profiles/activate", methods=["POST"])
    @optional_auth_required
    def activate_calibration_profile():
        data = json_or_empty()
        def action():
            profile = calibration_profiles.activate(data.get("id"))
            region_store.set_region(profile["turn_region"])
            screen_reader.turn_region = profile["turn_region"]
            screen_reader.prompt_region = profile["turn_region"]
            if profile["solve_region"]:
                solve_region_store.set_region(profile["solve_region"])
            else:
                solve_region_store.clear_persistence()
            return profile
        return profile_response(action)

    @bp.route("/api/calibration/profiles/<profile_id>", methods=["DELETE"])
    @optional_auth_required
    def delete_calibration_profile(profile_id):
        def action():
            calibration_profiles.delete(profile_id)
            return {"status": "success"}
        return profile_response(action)

    @bp.route("/api/practice/new", methods=["POST"])
    @optional_auth_required
    def new_practice_round():
        data = json_or_empty()
        mode = data.get("mode", "normal")
        if mode not in ("normal", "hints"):
            return jsonify({"status": "error", "message": "Modo de treino inválido"}), 400
        try:
            round_ = practice_service.generate_round(data.get("lang", "Português"))
        except PracticeError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400
        with practice_lock:
            practice_session.update({"round": round_, "mode": mode, "started_at": time.monotonic()})
        return jsonify({"prompt": round_.prompt, "mode": mode})

    @bp.route("/api/practice/check", methods=["POST"])
    @optional_auth_required
    def check_practice_answer():
        data = json_or_empty()
        with practice_lock:
            round_ = practice_session["round"]
            started_at = practice_session["started_at"]
            if round_ is None:
                return jsonify({"status": "error", "message": "Inicie um treino primeiro"}), 409
            practice_session["round"] = None
        elapsed = max(0.0, time.monotonic() - started_at)
        try:
            result = practice_service.evaluate(round_, data.get("answer", ""), elapsed_seconds=elapsed)
        except PracticeError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400
        return jsonify(asdict(result))

    @bp.route("/api/practice/hint", methods=["POST"])
    @optional_auth_required
    def practice_hint():
        data = json_or_empty()
        with practice_lock:
            round_ = practice_session["round"]
            mode = practice_session["mode"]
        if round_ is None or mode != "hints":
            return jsonify({"status": "error", "message": "Dicas indisponíveis"}), 409
        try:
            return jsonify(asdict(practice_service.hint(round_, data.get("kind"))))
        except PracticeError as exc:
            return jsonify({"status": "error", "message": str(exc)}), 400

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
