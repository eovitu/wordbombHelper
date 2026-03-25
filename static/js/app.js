document.addEventListener('DOMContentLoaded', () => {
    fetchLanguages();
    fetchPresets();
    setupEventListeners();
});

let currentConfig = {
    lang: 'Portuguese',
    min_len: 1,
    max_len: 46,
    priority_min_len: 1,
    priority_max_len: 46,
    strategy: 'random',
    auto_type: false,
    wpm: 60,
    error_rate: 0,
    hesitation_prob: 0.05,
    retry_rate: 0,
    late_error_rate: 0,
    max_typos: 2,
    max_late_errors: 1,
    priority_letters: '',
    exclude_letters: '',
    starts_with_letters: '',
    recover_target: 2,
    recover_exclude: '',
    priority_sublist: ''
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

    const lateErrorSlider = document.getElementById('late-error-slider');
    const lateErrorValue = document.getElementById('late-error-value');
    lateErrorSlider.addEventListener('input', (e) => {
        currentConfig.late_error_rate = e.target.value / 100;
        lateErrorValue.textContent = e.target.value;
        syncConfigToBackend();
    });

    const maxTyposSlider = document.getElementById('max-typos-slider');
    const maxTyposValue = document.getElementById('max-typos-value');
    maxTyposSlider.addEventListener('input', (e) => {
        currentConfig.max_typos = parseInt(e.target.value);
        maxTyposValue.textContent = e.target.value;
        syncConfigToBackend();
    });

    const maxLateSlider = document.getElementById('max-late-slider');
    const maxLateValue = document.getElementById('max-late-value');
    maxLateSlider.addEventListener('input', (e) => {
        currentConfig.max_late_errors = parseInt(e.target.value);
        maxLateValue.textContent = e.target.value;
        syncConfigToBackend();
    });

    document.getElementById('min-len').addEventListener('change', (e) => {
        currentConfig.min_len = parseInt(e.target.value) || 1;
        syncConfigToBackend();
    });

    document.getElementById('max-len').addEventListener('change', (e) => {
        currentConfig.max_len = parseInt(e.target.value) || 46;
        syncConfigToBackend();
    });

    const priMinLen = document.getElementById('priority-min-len');
    if (priMinLen) {
        priMinLen.addEventListener('change', (e) => {
            currentConfig.priority_min_len = parseInt(e.target.value) || 1;
            syncConfigToBackend();
        });
    }

    const priMaxLen = document.getElementById('priority-max-len');
    if (priMaxLen) {
        priMaxLen.addEventListener('change', (e) => {
            currentConfig.priority_max_len = parseInt(e.target.value) || 46;
            syncConfigToBackend();
        });
    }

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

    const startsWithInput = document.getElementById('starts-with-input');
    if (startsWithInput) {
        startsWithInput.addEventListener('input', (e) => {
            currentConfig.starts_with_letters = e.target.value;
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

    const recoverTargetInput = document.getElementById('recover-target');
    if (recoverTargetInput) {
        recoverTargetInput.addEventListener('change', (e) => {
            currentConfig.recover_target = parseInt(e.target.value) || 2;
            syncConfigToBackend();
        });
    }

    const recoverExcludeInput = document.getElementById('recover-exclude');
    if (recoverExcludeInput) {
        recoverExcludeInput.addEventListener('input', (e) => {
            currentConfig.recover_exclude = e.target.value;
            syncConfigToBackend();
        });
    }

    document.getElementById('auto-type-toggle').addEventListener('change', (e) => {
        currentConfig.auto_type = e.target.checked;
    });

    const sublistSelect = document.getElementById('sublist-select');
    if (sublistSelect) {
        sublistSelect.addEventListener('change', (e) => {
            currentConfig.priority_sublist = e.target.value;
            syncConfigToBackend();
        });
    }

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

    // Preset Selector
    const presetSelector = document.getElementById('preset-selector');
    presetSelector.addEventListener('change', (e) => {
        const name = e.target.value;
        if (name) loadPreset(name);
    });
}

let allPresets = {};

async function fetchPresets() {
    try {
        const response = await fetch('/api/presets');
        allPresets = await response.json();

        const selector = document.getElementById('preset-selector');
        // Clear except first
        selector.innerHTML = '<option value="" disabled selected>Selecione um preset...</option>';

        Object.keys(allPresets).forEach(name => {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            selector.appendChild(opt);
        });
    } catch (e) {
        console.error('Failed to fetch presets', e);
    }
}

function loadPreset(name) {
    const preset = allPresets[name];
    if (!preset) return;

    // Update currentConfig
    Object.assign(currentConfig, preset);

    // Update UI Elements
    updateUIFromConfig();

    // Sync
    syncConfigToBackend();
    console.log(`Loaded preset: ${name}`);
}

function updateUIFromConfig() {
    // Sliders & Values
    document.getElementById('wpm-slider').value = currentConfig.wpm;
    document.getElementById('wpm-value').textContent = currentConfig.wpm;

    document.getElementById('error-slider').value = currentConfig.error_rate * 100;
    document.getElementById('error-value').textContent = currentConfig.error_rate * 100;

    document.getElementById('travadinha-slider').value = currentConfig.hesitation_prob * 100;
    document.getElementById('travadinha-value').textContent = currentConfig.hesitation_prob * 100;

    document.getElementById('retry-slider').value = currentConfig.retry_rate * 100;
    document.getElementById('retry-value').textContent = (currentConfig.retry_rate * 100).toFixed(1);

    document.getElementById('late-error-slider').value = currentConfig.late_error_rate * 100;
    document.getElementById('late-error-value').textContent = currentConfig.late_error_rate * 100;

    document.getElementById('max-typos-slider').value = currentConfig.max_typos;
    document.getElementById('max-typos-value').textContent = currentConfig.max_typos;

    document.getElementById('max-late-slider').value = currentConfig.max_late_errors;
    document.getElementById('max-late-value').textContent = currentConfig.max_late_errors;

    const minL = document.getElementById('min-len');
    if (minL) minL.value = currentConfig.min_len || 1;

    const maxL = document.getElementById('max-len');
    if (maxL) maxL.value = currentConfig.max_len || 46;

    const priMinL = document.getElementById('priority-min-len');
    if (priMinL) priMinL.value = currentConfig.priority_min_len || 1;

    const priMaxL = document.getElementById('priority-max-len');
    if (priMaxL) priMaxL.value = currentConfig.priority_max_len || 46;

    // Inputs & Selects
    document.getElementById('strategy-select').value = currentConfig.strategy;

    const recTarget = document.getElementById('recover-target');
    if (recTarget) recTarget.value = currentConfig.recover_target || 2;

    const recExclude = document.getElementById('recover-exclude');
    if (recExclude) recExclude.value = currentConfig.recover_exclude || '';

    // Reload sub-lists for the language in this preset
    fetchSublistsForLang(currentConfig.lang);
}

async function saveNewPreset() {
    const name = prompt("Digite um nome para este preset:");
    if (!name) return;

    const configToSave = {
        min_len: currentConfig.min_len,
        max_len: currentConfig.max_len,
        priority_min_len: currentConfig.priority_min_len || 1,
        priority_max_len: currentConfig.priority_max_len || 46,
        wpm: currentConfig.wpm,
        error_rate: currentConfig.error_rate,
        hesitation_prob: currentConfig.hesitation_prob,
        retry_rate: currentConfig.retry_rate,
        late_error_rate: currentConfig.late_error_rate,
        max_typos: currentConfig.max_typos,
        max_late_errors: currentConfig.max_late_errors,
        strategy: currentConfig.strategy,
        priority_letters: currentConfig.priority_letters,
        exclude_letters: currentConfig.exclude_letters,
        starts_with_letters: currentConfig.starts_with_letters,
        recover_target: currentConfig.recover_target,
        recover_exclude: currentConfig.recover_exclude,
        priority_sublist: currentConfig.priority_sublist
    };

    try {
        const response = await fetch('/api/presets/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, config: configToSave })
        });

        if (response.ok) {
            alert("Preset salvo!");
            fetchPresets();
        }
    } catch (e) {
        console.error('Failed to save preset', e);
    }
}

async function deletePreset() {
    const selector = document.getElementById('preset-selector');
    const name = selector.value;
    if (!name) {
        alert("Por favor, selecione um preset para remover.");
        return;
    }

    if (!confirm(`Tem certeza de que deseja remover o preset "${name}"?`)) {
        return;
    }

    try {
        const response = await fetch('/api/presets/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });

        if (response.ok) {
            alert("Preset removido com sucesso!");
            // Reset selector and fetch
            selector.value = "";
            fetchPresets();
        } else {
            const data = await response.json();
            alert(data.message || "Falha ao remover o preset.");
        }
    } catch (e) {
        console.error('Falha ao remover o preset', e);
    }
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
                priority_min_len: currentConfig.priority_min_len,
                priority_max_len: currentConfig.priority_max_len,
                strategy: currentConfig.strategy,
                wpm: currentConfig.wpm,
                error_rate: currentConfig.error_rate,
                hesitation_prob: currentConfig.hesitation_prob,
                retry_rate: currentConfig.retry_rate,
                late_error_rate: currentConfig.late_error_rate,
                max_typos: currentConfig.max_typos,
                max_late_errors: currentConfig.max_late_errors,
                priority_letters: currentConfig.priority_letters,
                exclude_letters: currentConfig.exclude_letters,
                starts_with_letters: currentConfig.starts_with_letters,
                recover_target: currentConfig.recover_target,
                recover_exclude: currentConfig.recover_exclude,
                priority_sublist: currentConfig.priority_sublist
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

        // Load sub-lists for the current language on startup
        await fetchSublistsForLang(currentConfig.lang);
    } catch (e) {
        console.error('Failed to fetch languages', e);
    }
}

async function fetchSublistsForLang(lang) {
    try {
        const response = await fetch(`/api/sublists/${encodeURIComponent(lang)}`);
        const sublists = await response.json();

        const group = document.getElementById('sublist-group');
        const select = document.getElementById('sublist-select');

        if (sublists.length === 0) {
            group.style.display = 'none';
            return;
        }

        // Show the group and populate the select
        group.style.display = 'block';
        select.innerHTML = '<option value="">Nenhuma (usar lista principal)</option>';
        sublists.forEach(sub => {
            const opt = document.createElement('option');
            opt.value = sub;
            // Capitalize nicely
            opt.textContent = `🔹 ${sub.charAt(0).toUpperCase() + sub.slice(1)}`;
            if (sub === currentConfig.priority_sublist) opt.selected = true;
            select.appendChild(opt);
        });
    } catch (e) {
        console.error('Failed to fetch sublists', e);
    }
}

function setLanguage(lang, btnElement) {
    currentConfig.lang = lang;
    // Reset sub-list when switching language
    currentConfig.priority_sublist = '';

    // Update UI
    document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
    btnElement.classList.add('active');

    // Load sub-lists for new language
    fetchSublistsForLang(lang);

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
