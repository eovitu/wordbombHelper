from flask import Flask, render_template, request, jsonify
import os
import numpy as np
from word_manager import WordManager
from typer import Typer
from screen_reader import ScreenReader
from grid_reader import GridReader
from letter_link_solver import LetterLinkSolver
import threading
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
wm = WordManager()
typer = Typer()
grid_reader = GridReader()
ll_solver = LetterLinkSolver()

# Update Trie when wordlist finishes loading inside wm?
def build_trie_bg(lang=None):
    if lang is None:
        lang = wm.current_language
    
    if lang not in wm.wordlists:
        logger.error(f"Language '{lang}' not found in wordlists!")
        return
    
    wordlist = wm.wordlists[lang]['full']
    logger.info(f"Building Letter Link Trie from {lang} ({len(wordlist)} words)...")
    count = ll_solver.build_trie_from_list(wordlist)
    logger.info(f"Trie complete: {count} words indexed for Letter Link.")

# Store LetterLink calibration
ll_grid_region = None

# --- Auto-Play Config (synced from frontend) ---
autoplay_config = {
    'lang': 'Portuguese',
    'min_len': 1,
    'max_len': 46,
    'strategy': 'random',
    'wpm': 150,
    'error_rate': 0.0,
    'hesitation_prob': 0.05,
    'retry_rate': 0.0,
    'late_error_rate': 0.0,
    'max_typos': 2,
    'max_late_errors': 1,
    'priority_min_len': 1,
    'priority_max_len': 46,
    'priority_letters': '',
    'exclude_letters': '',
    'starts_with_letters': '',
    'finish_with_letters': '',
    'recover_target': 2,
    'recover_exclude': '',
    'priority_sublist': '',
    'delayed_type': False,
    'add_period_prob': 0.0
}

# Store auto-play log messages for frontend polling
autoplay_logs = []
autoplay_logs_lock = threading.Lock()
autoplay_config_lock = threading.Lock()  # Protects autoplay_config against concurrent read/write

def add_autoplay_log(msg):
    with autoplay_logs_lock:
        autoplay_logs.append(msg)
        # Keep only last 50 logs
        if len(autoplay_logs) > 50:
            autoplay_logs.pop(0)

# Callback for when ScreenReader finds a prompt
def on_prompt_found(prompt_text):
    """
    Called by ScreenReader when SUA VEZ is detected and a prompt is read.
    Returns True if a word was typed, False if no word found.
    """
    logger.info(f"Auto-Play: Found prompt '{prompt_text}'")
    add_autoplay_log(f"Prompt: '{prompt_text}'")
    
    # Thread-safe snapshot of config (Flask thread writes, ScreenReader thread reads)
    with autoplay_config_lock:
        config = dict(autoplay_config)
    
    lang = config['lang']
    min_len = config['min_len']
    max_len = config['max_len']
    strategy = config['strategy']
    priority_letters = config.get('priority_letters', '')
    exclude_letters = config.get('exclude_letters', '')
    starts_with_letters = config.get('starts_with_letters', '')
    finish_with_letters = config.get('finish_with_letters', '')
    priority_min_len = int(config.get('priority_min_len', 1))
    priority_max_len = int(config.get('priority_max_len', 46))
    wpm = config['wpm']
    error_rate = config['error_rate']
    
    # Configure recovery logic before getting word
    rec_target = int(config.get('recover_target', 2))
    rec_exclude = config.get('recover_exclude', '')
    wm.set_recover_config(rec_target, rec_exclude)
    
    word = wm.get_word(prompt_text, lang, min_len, max_len, strategy,
                       priority_letters=priority_letters,
                       exclude_letters=exclude_letters,
                       starts_with_letters=starts_with_letters,
                       finish_with_letters=finish_with_letters,
                       priority_min_len=priority_min_len,
                       priority_max_len=priority_max_len,
                       priority_sublist=config.get('priority_sublist', ''))
    if word:
        wm.mark_used(word)
        logger.info(f"Auto-Play: Typing word '{word}'")
        add_autoplay_log(f"Typing: '{word}'")
        
        # Disabled auto_tab for Auto-Play (assumed to be in focus)
        typer.type_word(
            word, wpm, error_rate, 
            auto_tab=False, 
            hesitation_prob=config['hesitation_prob'],
            retry_rate=config['retry_rate'],
            late_error_rate=config['late_error_rate'],
            max_typos=config['max_typos'],
            max_late_errors=config['max_late_errors'],
            delayed_type=config.get('delayed_type', False),
            add_period_prob=float(config.get('add_period_prob', 0.0))
        )
        # Track last word typed to avoid "ghost prompt" hallucinations
        screen_reader.last_word_typed = word
        
        # Wait for typing to complete using event (no busy-wait)
        typer.done_event.wait(timeout=5)
        
        return True
    else:
        logger.warning(f"Auto-Play: No word found for prompt '{prompt_text}'")
        add_autoplay_log(f"No word found for '{prompt_text}'")
        return False

screen_reader = ScreenReader(callback_found_word=on_prompt_found)
screen_reader.set_log_callback(add_autoplay_log)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/languages')
def get_languages():
    return jsonify(wm.get_languages())

@app.route('/api/sublists')
def get_sublists_map():
    return jsonify(wm.get_sublists_map())

@app.route('/api/sublists/<lang>')
def get_sublists_for_lang(lang):
    return jsonify(wm.get_sublists(lang))

@app.route('/api/word', methods=['POST'])
def get_word():
    data = request.json
    prompt = data.get('prompt', '')
    lang = data.get('lang', 'en')
    min_len = int(data.get('min_len', 1))
    max_len = int(data.get('max_len', 46))
    strategy = data.get('strategy', 'random')
    priority_letters = data.get('priority_letters', '')
    exclude_letters = data.get('exclude_letters', '')
    starts_with_letters = data.get('starts_with_letters', '')
    finish_with_letters = data.get('finish_with_letters', '')
    priority_min_len = int(data.get('priority_min_len', 1))
    priority_max_len = int(data.get('priority_max_len', 46))
    auto_type = data.get('auto_type', False)
    wpm = int(data.get('wpm', 60))
    error_rate = float(data.get('error_rate', 0))
    
    priority_sublist = data.get('priority_sublist', '')

    # Configure recovery logic before getting word
    rec_target = int(data.get('recover_target', 2))
    rec_exclude = data.get('recover_exclude', '')
    prefix = data.get('prefix', '')
    suffix = data.get('suffix', '')
    wm.set_recover_config(rec_target, rec_exclude)

    word = wm.get_word(prompt, lang, min_len, max_len, strategy,
                       priority_letters=priority_letters,
                       exclude_letters=exclude_letters,
                       starts_with_letters=starts_with_letters,
                       finish_with_letters=finish_with_letters,
                       priority_min_len=priority_min_len,
                       priority_max_len=priority_max_len,
                       priority_sublist=priority_sublist,
                       prefix=prefix,
                       suffix=suffix)
    
    if word:
        wm.mark_used(word)
        if auto_type:
            # Track last word typed even in manual mode
            screen_reader.last_word_typed = word
            
            # Use request data or fallback to synced global config
            h_prob = float(data.get('hesitation_prob', autoplay_config['hesitation_prob']))
            r_rate = float(data.get('retry_rate', autoplay_config['retry_rate']))
            l_rate = float(data.get('late_error_rate', autoplay_config['late_error_rate']))
            
            typer.type_word(
                word, wpm, error_rate, 
                auto_tab=True,
                hesitation_prob=h_prob,
                retry_rate=r_rate,
                late_error_rate=l_rate,
                max_typos=int(data.get('max_typos', autoplay_config['max_typos'])),
                max_late_errors=int(data.get('max_late_errors', autoplay_config['max_late_errors'])),
                return_tab=True,
                delayed_type=data.get('delayed_type', autoplay_config.get('delayed_type', False)),
                add_period_prob=float(data.get('add_period_prob', autoplay_config.get('add_period_prob', 0.0)))
            )
            
    return jsonify({'word': word})

@app.route('/api/reset', methods=['POST'])
def reset_words():
    wm.reset_used()
    wm.load_wordlists()
    threading.Thread(target=build_trie_bg).start()
    return jsonify({'status': 'success'})

# --- Screen Reader / Auto-Play Routes ---

@app.route('/api/calibration/start', methods=['POST'])
def start_calibration():
    screen_reader.start_calibration()
    return jsonify({"status": "started", "step": "turn_start", "message": "Click top-left of 'My Turn' indicator"})

@app.route('/api/calibration/click', methods=['POST'])
def calibration_click():
    data = request.json
    x = data.get('x')
    y = data.get('y')
    mode = data.get('mode', 'classic') # 'classic' or 'letterlink'
    
    # Let screen_reader handle the click logic for both since it's just rectangle coordinates
    result = screen_reader.handle_calibration_click(x, y)
    
    if result.get('status') == 'done':
        # If letterlink, steal the region for grid
        if mode == 'letterlink':
            global ll_grid_region
            ll_grid_region = result['regions']['turn_region']
            result['message'] = "Letter Link Grid Calibrated!"
            
    return jsonify(result)

@app.route('/api/letterlink/solve', methods=['POST'])
def solve_letter_link():
    try:
        global ll_grid_region
        region = ll_grid_region or screen_reader.turn_region
        if not region:
            return jsonify({'status': 'error', 'message': 'Calibrate grid first'})
            
        # Read grid
        matrix, coords = grid_reader.read_grid(region)
        if not matrix:
            return jsonify({'status': 'error', 'message': 'Failed to read grid. Check Tesseract.'})
        
        logger.info(f"Grid read: {np.array(matrix)}")
            
        # ALWAYS rebuild Trie for Portuguese to ensure fresh wordlist
        logger.info("Building fresh Trie for Portuguese...")
        build_trie_bg(lang='Portuguese')
            
        # Solve — return top 5 highest scoring words for the user to read
        logger.info(f"Solving grid with Trie (root has {len(ll_solver.trie.root.children)} children)...")
        results = ll_solver.solve_grid(matrix)
        logger.info(f"Found {len(results)} words total")
        
        if not results:
            return jsonify({'status': 'error', 'message': 'No words found in Portuguese wordlist. Check grid OCR!'})
        
        top_words = [{'word': word, 'score': score, 'path': path} for word, path, score in results[:5]]
        best_word = top_words[0]
        
        logger.info(f"Letter Link -> Best: '{best_word['word']}' ({best_word['score']} pts)")
        top_5_words = ', '.join(f"{w['word']}({w['score']}pts)" for w in top_words)
        logger.info(f"Top 5: {top_5_words}")
        
        return jsonify({'status': 'success', 'word': best_word['word'], 'score': best_word['score'], 'top_words': top_words, 'matrix': matrix})
    except Exception as e:
        logger.error(f"Error in solve_letter_link: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': f"Internal Error: {str(e)}"}), 500

@app.route('/api/autoplay/toggle', methods=['POST'])
def toggle_autoplay():
    from overlay_manager import get_overlay
    try:
        active = screen_reader.toggle_watching()
        
        # Show/hide overlay based on auto-play state
        overlay = get_overlay()
        if overlay:
            if active:
                # Use root.after to call from Tkinter main thread
                overlay.root.after(0, overlay.show)
            else:
                overlay.root.after(0, overlay.hide)
        
        return jsonify({"status": "active" if active else "inactive"})
    except Exception as e:
        logger.error(f"Error toggling auto-play: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/autoplay/status', methods=['GET'])
def get_autoplay_status():
    state = screen_reader.get_state()
    # Include recent logs
    with autoplay_logs_lock:
        state['logs'] = list(autoplay_logs[-10:])  # Last 10 logs
    return state

@app.route('/api/autoplay/config', methods=['POST'])
def update_autoplay_config():
    """Sync config from frontend to auto-play backend."""
    data = request.json
    with autoplay_config_lock:
        if 'lang' in data:
            autoplay_config['lang'] = data['lang']
        if 'min_len' in data:
            autoplay_config['min_len'] = int(data['min_len'])
        if 'max_len' in data:
            autoplay_config['max_len'] = int(data['max_len'])
        if 'strategy' in data:
            autoplay_config['strategy'] = data['strategy']
        if 'wpm' in data:
            autoplay_config['wpm'] = int(data['wpm'])
        if 'error_rate' in data:
            autoplay_config['error_rate'] = float(data['error_rate'])
        if 'hesitation_prob' in data:
            autoplay_config['hesitation_prob'] = float(data['hesitation_prob'])
        if 'retry_rate' in data:
            autoplay_config['retry_rate'] = float(data['retry_rate'])
        if 'late_error_rate' in data:
            autoplay_config['late_error_rate'] = float(data['late_error_rate'])
        if 'max_typos' in data:
            autoplay_config['max_typos'] = int(data['max_typos'])
        if 'max_late_errors' in data:
            autoplay_config['max_late_errors'] = int(data['max_late_errors'])
        if 'priority_min_len' in data:
            autoplay_config['priority_min_len'] = int(data['priority_min_len'])
        if 'priority_max_len' in data:
            autoplay_config['priority_max_len'] = int(data['priority_max_len'])
        if 'priority_letters' in data:
            autoplay_config['priority_letters'] = data['priority_letters']
        if 'exclude_letters' in data:
            autoplay_config['exclude_letters'] = data['exclude_letters']
        if 'starts_with_letters' in data:
            autoplay_config['starts_with_letters'] = data['starts_with_letters']
        if 'finish_with_letters' in data:
            autoplay_config['finish_with_letters'] = data['finish_with_letters']
        if 'recover_target' in data:
            autoplay_config['recover_target'] = int(data['recover_target'])
        if 'recover_exclude' in data:
            autoplay_config['recover_exclude'] = data['recover_exclude']
        if 'priority_sublist' in data:
            autoplay_config['priority_sublist'] = data['priority_sublist']
        if 'delayed_type' in data:
            autoplay_config['delayed_type'] = bool(data['delayed_type'])
        if 'add_period_prob' in data:
            autoplay_config['add_period_prob'] = float(data['add_period_prob'])
        
        logger.info(f"Auto-Play config updated: {autoplay_config}")
        return jsonify({"status": "ok", "config": autoplay_config})

# --- Preset Management ---

PRESETS_FILE = os.path.join(os.path.dirname(__file__), 'presets.json')

def load_presets():
    if not os.path.exists(PRESETS_FILE):
        return {}
    try:
        with open(PRESETS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading presets: {e}")
        return {}

def save_presets(presets):
    try:
        with open(PRESETS_FILE, 'w', encoding='utf-8') as f:
            json.dump(presets, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving presets: {e}")
        return False

@app.route('/api/presets', methods=['GET'])
def get_presets():
    return jsonify(load_presets())

@app.route('/api/presets/save', methods=['POST'])
def save_preset():
    data = request.json
    name = data.get('name')
    config = data.get('config')
    
    if not name or not config:
        return jsonify({"status": "error", "message": "Name and config required"}), 400
        
    presets = load_presets()
    presets[name] = config
    if save_presets(presets):
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Failed to save file"}), 500

@app.route('/api/presets/delete', methods=['POST'])
def delete_preset():
    data = request.json
    name = data.get('name')
    
    presets = load_presets()
    if name in presets:
        del presets[name]
        if save_presets(presets):
            return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Preset not found or delete failed"}), 404

def run_flask():
    app.run(debug=False, port=5000, use_reloader=False)

if __name__ == '__main__':
    # Initial Trie build on boot
    threading.Thread(target=build_trie_bg).start()

    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    logger.info("Starting Overlay Manager...")
    
    # Run Tkinter Overlay in Main Thread
    from overlay_manager import run_overlay
    
    def on_overlay_move(region):
        # Just update the screen reader region — don't auto-start watching.
        # Watching is controlled by the Auto-Play toggle button.
        if screen_reader:
            screen_reader.prompt_region = region
            screen_reader.turn_region = region
            # Also update letter link region just in case they drag it manually
            global ll_grid_region
            ll_grid_region = region

    run_overlay(on_overlay_move)
