document.addEventListener('DOMContentLoaded', () => {
    fetchLanguages();
    setupEventListeners();
});

let currentConfig = {
    lang: 'Portuguese',
    min_len: 1,
    max_len: 46,
    strategy: 'random',
    auto_type: false,
    wpm: 60,
    error_rate: 0,
    hesitation_prob: 0.05,
    retry_rate: 0,
    priority_letters: '',
    exclude_letters: ''
};

function setupEventListeners() {
    // Config Inputs
    const wpmSlider = document.getElementById('wpm-slider');
    const wpmValue = document.getElementById('wpm-value');
    wpmSlider.addEventListener('input', (e) => {
        currentConfig.wpm = parseInt(e.target.value);
        wpmValue.textContent = e.target.value;
        syncConfigToBackend();
    });

    const errorSlider = document.getElementById('error-slider');
    const errorValue = document.getElementById('error-value');
    errorSlider.addEventListener('input', (e) => {
        currentConfig.error_rate = e.target.value / 100;
        errorValue.textContent = e.target.value;
        syncConfigToBackend();
    });

    const travadinhaSlider = document.getElementById('travadinha-slider');
    const travadinhaValue = document.getElementById('travadinha-value');
    travadinhaSlider.addEventListener('input', (e) => {
        currentConfig.hesitation_prob = e.target.value / 100;
        travadinhaValue.textContent = e.target.value;
        syncConfigToBackend();
    });

    const retrySlider = document.getElementById('retry-slider');
    const retryValue = document.getElementById('retry-value');
    retrySlider.addEventListener('input', (e) => {
        currentConfig.retry_rate = e.target.value / 100;
        retryValue.textContent = e.target.value;
        syncConfigToBackend();
    });

    document.getElementById('min-len').addEventListener('change', (e) => {
        currentConfig.min_len = parseInt(e.target.value);
        syncConfigToBackend();
    });

    document.getElementById('max-len').addEventListener('change', (e) => {
        currentConfig.max_len = parseInt(e.target.value);
        syncConfigToBackend();
    });

    document.getElementById('strategy-select').addEventListener('change', (e) => {
        currentConfig.strategy = e.target.value;
        syncConfigToBackend();
    });

    const priorityInput = document.getElementById('priority-input');
    if (priorityInput) {
        priorityInput.addEventListener('input', (e) => {
            currentConfig.priority_letters = e.target.value;
            syncConfigToBackend();
        });
    }

    const excludeInput = document.getElementById('exclude-input');
    if (excludeInput) {
        excludeInput.addEventListener('input', (e) => {
            currentConfig.exclude_letters = e.target.value;
            syncConfigToBackend();
        });
    }

    document.getElementById('auto-type-toggle').addEventListener('change', (e) => {
        currentConfig.auto_type = e.target.checked;
    });

    // Game Input
    const promptInput = document.getElementById('prompt-input');
    promptInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const prompt = e.target.value;
            if (prompt.length > 0) {
                getWord(prompt);
            } else {
                document.getElementById('current-word').textContent = 'Waiting...';
            }
        }
    });

    // Sync config on page load
    syncConfigToBackend();
}

// --- Sync config to auto-play backend ---
async function syncConfigToBackend() {
    try {
        await fetch('/api/autoplay/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                lang: currentConfig.lang,
                min_len: currentConfig.min_len,
                max_len: currentConfig.max_len,
                strategy: currentConfig.strategy,
                wpm: currentConfig.wpm,
                error_rate: currentConfig.error_rate,
                hesitation_prob: currentConfig.hesitation_prob,
                retry_rate: currentConfig.retry_rate,
                priority_letters: currentConfig.priority_letters,
                exclude_letters: currentConfig.exclude_letters
            })
        });
    } catch (e) {
        console.error('Failed to sync config to backend', e);
    }
}

async function fetchLanguages() {
    try {
        const response = await fetch('/api/languages');
        const languages = await response.json();

        const container = document.getElementById('lang-selector');
        container.innerHTML = '';

        languages.forEach(lang => {
            const btn = document.createElement('button');
            btn.className = `lang-btn ${lang === currentConfig.lang ? 'active' : ''}`;
            btn.textContent = lang;
            btn.onclick = () => setLanguage(lang, btn);
            container.appendChild(btn);
        });
    } catch (e) {
        console.error('Failed to fetch languages', e);
    }
}

function setLanguage(lang, btnElement) {
    currentConfig.lang = lang;

    // Update UI
    document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
    btnElement.classList.add('active');

    // Sync to auto-play backend
    syncConfigToBackend();
}

async function getWord(prompt) {
    try {
        const response = await fetch('/api/word', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                prompt: prompt,
                ...currentConfig
            })
        });

        const data = await response.json();
        const display = document.getElementById('current-word');

        if (data.word) {
            display.textContent = data.word;
            // Always clear input after a match to save user time
            document.getElementById('prompt-input').value = '';
        } else {
            display.textContent = 'No match found';
        }

    } catch (e) {
        console.error('Error fetching word', e);
    }
}

async function resetWords() {
    try {
        await fetch('/api/reset', { method: 'POST' });
        document.getElementById('current-word').textContent = 'Words/File Reloaded!';

        // Sync these changes back to the server
        syncConfigToBackend();

        setTimeout(() => {
            document.getElementById('current-word').textContent = 'Waiting...';
        }, 2000);
    } catch (e) {
        console.error('Reset failed', e);
    }
}

function switchTab(tabName) {
    // Update Buttons
    document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
    const buttons = document.querySelectorAll('.nav-btn');
    if (tabName === 'manual') buttons[0].classList.add('active');
    if (tabName === 'auto') buttons[1].classList.add('active');
    if (tabName === 'config') buttons[2].classList.add('active');

    // Update Content
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    document.getElementById(`${tabName}-tab`).classList.add('active');

    // Auto-Play polling
    if (tabName === 'auto') {
        if (!autoPlayInterval) autoPlayInterval = setInterval(pollAutoStatus, 1000);
        pollAutoStatus();
    } else {
        if (autoPlayInterval && !isCalibrating) {
            clearInterval(autoPlayInterval);
            autoPlayInterval = null;
        }
    }
}

// Auto-Play & Calibration Logic
let autoPlayInterval = null;
let isCalibrating = false;

async function startCalibration() {
    try {
        const response = await fetch('/api/calibration/start', { method: 'POST' });
        const data = await response.json();

        if (data.status === 'started') {
            showOverlay(data.message);
            isCalibrating = true;
            if (autoPlayInterval) clearInterval(autoPlayInterval);
            autoPlayInterval = setInterval(pollAutoStatus, 500);
        }
    } catch (e) {
        console.error('Failed to start calibration', e);
        logAuto("Error starting calibration");
    }
}

async function toggleAutoPlay() {
    try {
        const response = await fetch('/api/autoplay/toggle', { method: 'POST' });
        const data = await response.json();

        const btn = document.getElementById('autoplay-toggle-btn');
        if (data.status === 'active') {
            btn.textContent = 'Stop Auto-Play';
            btn.classList.replace('primary-btn', 'secondary-btn');
            logAuto("Auto-Play STARTED");
        } else {
            btn.textContent = 'Start Auto-Play';
            btn.classList.replace('secondary-btn', 'primary-btn');
            logAuto("Auto-Play STOPPED");
        }
        pollAutoStatus();
    } catch (e) {
        console.error('Failed to toggle auto-play', e);
        logAuto("Error toggling auto-play");
    }
}

let lastLogCount = 0;

async function pollAutoStatus() {
    if (!document.getElementById('auto-tab').classList.contains('active') && !isCalibrating) return;

    try {
        const response = await fetch('/api/autoplay/status');
        const state = await response.json();

        // Update Indicator
        const indicator = document.getElementById('auto-status-indicator');
        const statusText = document.getElementById('auto-status-text');

        statusText.textContent = state.status;
        indicator.className = 'status-indicator';

        if (state.status === 'Watching') {
            indicator.classList.add('watching');
        } else if (state.status === 'Parsing' || state.status === 'Typing') {
            indicator.classList.add('active');
        }

        // Update Calibration Overlay if active
        if (state.status === 'Calibrating') {
            isCalibrating = true;
            let instruction = "Click to calibrate...";
            if (state.calibration_step === 'turn_start') instruction = "Click Top-Left of the prompt + SUA VEZ area";
            if (state.calibration_step === 'turn_end') instruction = "Click Bottom-Right of the prompt + SUA VEZ area";
            updateOverlay(instruction);
        } else {
            if (isCalibrating) {
                isCalibrating = false;
                hideOverlay();
                logAuto("Calibration Finished");
            }
        }

        // Show backend logs
        if (state.logs && state.logs.length > 0) {
            // Only add new logs
            const newLogs = state.logs.slice(lastLogCount);
            newLogs.forEach(msg => logAuto(msg));
            lastLogCount = state.logs.length;
        }

        // Update Button State
        const btn = document.getElementById('autoplay-toggle-btn');
        if (state.is_watching && btn.textContent !== 'Stop Auto-Play') {
            btn.textContent = 'Stop Auto-Play';
            btn.classList.replace('primary-btn', 'secondary-btn');
        } else if (!state.is_watching && btn.textContent !== 'Start Auto-Play') {
            btn.textContent = 'Start Auto-Play';
            btn.classList.replace('secondary-btn', 'primary-btn');
        }

    } catch (e) {
        console.error('Poll error', e);
    }
}

function logAuto(msg) {
    const container = document.getElementById('auto-logs');
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
    container.prepend(entry);
}

// Overlay Helpers
function showOverlay(msg) {
    const overlay = document.getElementById('calibration-overlay');
    document.getElementById('calib-instruction').textContent = msg;
    overlay.classList.remove('hidden');
}

function updateOverlay(msg) {
    document.getElementById('calib-instruction').textContent = msg;
}

function hideOverlay() {
    document.getElementById('calibration-overlay').classList.add('hidden');
}

// Utility
function debounce(func, wait) {
    let timeout;
    return function (...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
