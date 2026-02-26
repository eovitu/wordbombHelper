from flask import Flask, render_template, request, jsonify
import os
from word_manager import WordManager
from typer import Typer
from screen_reader import ScreenReader
import threading
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
wm = WordManager()
typer = Typer()

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
    'priority_letters': '',
    'exclude_letters': ''
}

# Store auto-play log messages for frontend polling
autoplay_logs = []
autoplay_logs_lock = threading.Lock()

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
    
    # Use the synced config from frontend
    lang = autoplay_config['lang']
    min_len = autoplay_config['min_len']
    max_len = autoplay_config['max_len']
    strategy = autoplay_config['strategy']
    priority_letters = autoplay_config.get('priority_letters', '')
    exclude_letters = autoplay_config.get('exclude_letters', '')
    wpm = autoplay_config['wpm']
    error_rate = autoplay_config['error_rate']
    
    word = wm.get_word(prompt_text, lang, min_len, max_len, strategy, priority_letters=priority_letters, exclude_letters=exclude_letters)
    if word:
        wm.mark_used(word)
        logger.info(f"Auto-Play: Typing word '{word}'")
        add_autoplay_log(f"Typing: '{word}'")
        
        # Disabled auto_tab for Auto-Play (assumed to be in focus)
        typer.type_word(
            word, wpm, error_rate, 
            auto_tab=False, 
            hesitation_prob=autoplay_config['hesitation_prob'],
            retry_rate=autoplay_config['retry_rate']
        )
        # Track last word typed to avoid "ghost prompt" hallucinations
        screen_reader.last_word_typed = word
        
        # Wait for typing to finish before returning
        import time
        timeout = 5
        waited = 0
        while typer.is_typing and waited < timeout:
            time.sleep(0.05)
            waited += 0.05
        
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
    auto_type = data.get('auto_type', False)
    wpm = int(data.get('wpm', 60))
    error_rate = float(data.get('error_rate', 0))

    word = wm.get_word(prompt, lang, min_len, max_len, strategy, priority_letters=priority_letters, exclude_letters=exclude_letters)
    
    if word:
        wm.mark_used(word)
        if auto_type:
            # Track last word typed even in manual mode
            screen_reader.last_word_typed = word
            # Manual mode keeps Alt-Tab to switch focus to the game
            # Added hesitation_prob and retry_rate
            typer.type_word(
                word, wpm, error_rate, 
                auto_tab=True,
                hesitation_prob=autoplay_config['hesitation_prob'],
                retry_rate=autoplay_config['retry_rate'],
                return_tab=True # Switch back to browser after manual typing
            )
            
    return jsonify({'word': word})

@app.route('/api/reset', methods=['POST'])
def reset_words():
    wm.reset_used()
    wm.load_wordlists()
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
    result = screen_reader.handle_calibration_click(x, y)
    return jsonify(result)

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
    if 'priority_letters' in data:
        autoplay_config['priority_letters'] = data['priority_letters']
    if 'exclude_letters' in data:
        autoplay_config['exclude_letters'] = data['exclude_letters']
    
    logger.info(f"Auto-Play config updated: {autoplay_config}")
    return jsonify({"status": "ok", "config": autoplay_config})

def run_flask():
    app.run(debug=False, port=5000, use_reloader=False)

if __name__ == '__main__':
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

    run_overlay(on_overlay_move)
