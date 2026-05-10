document.addEventListener('DOMContentLoaded', () => {
    fetchLanguages();
    fetchPresets();
    setupEventListeners();
    setupGlobalShortcuts();
    autoPlayInterval = setInterval(pollAutoStatus, 250);
    pollAutoStatus();
});

let currentConfig = {
    lang: 'Português',
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
    finish_with_letters: '',
    recover_target: 2,
    recover_exclude: '',
    priority_sublist: '',
    delayed_type: false,
    add_period_prob: 0.0
};

function debounce(fn, wait = 250) {
    let timer = null;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), wait);
    };
}

const scheduleSyncConfig = debounce(() => syncConfigToBackend(), 250);

function setupGlobalShortcuts() {
    document.addEventListener('keydown', (e) => {
        if (!e.altKey) return;
        switch (e.key) {
            case '1':
                e.preventDefault();
                switchTab('manual');
                break;
            case '2':
                e.preventDefault();
                switchTab('auto');
                break;
            case '3':
                e.preventDefault();
                switchTab('config');
                break;
        }
    });

    document.addEventListener('keyup', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
        if (e.altKey || e.ctrlKey || e.metaKey) return;
        if (e.key === '1') switchTab('manual');
        if (e.key === '2') switchTab('auto');
        if (e.key === '3') switchTab('config');
    });
}

function setupEventListeners() {
    const bindSlider = (id, field, divisor) => {
        const slider = document.getElementById(id + '-slider');
        const display = document.getElementById(id + '-value');
        if (!slider) return;
        slider.addEventListener('input', (e) => {
            currentConfig[field] = parseFloat(e.target.value) / divisor;
            if (display)
                display.textContent = display.textContent.includes('%')
                    ? e.target.value
                    : field === 'retry_rate'
                      ? e.target.value.toString()
                      : e.target.value;
            scheduleSyncConfig();
        });
    };

    bindSlider('wpm', 'wpm', 1);
    bindSlider('error', 'error_rate', 100);
    bindSlider('travadinha', 'hesitation_prob', 100);
    bindSlider('retry', 'retry_rate', 100);
    bindSlider('late-error', 'late_error_rate', 100);

    const maxTypos = document.getElementById('max-typos-slider');
    if (maxTypos) maxTypos.addEventListener('input', (e) => { currentConfig.max_typos = parseInt(e.target.value); scheduleSyncConfig(); });
    const maxLate = document.getElementById('max-late-slider');
    if (maxLate) maxLate.addEventListener('input', (e) => { currentConfig.max_late_errors = parseInt(e.target.value); scheduleSyncConfig(); });

    const bindNumber = (id, field, defaultVal) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.addEventListener('change', (e) => {
            currentConfig[field] = parseInt(e.target.value) || defaultVal;
            scheduleSyncConfig();
        });
    };
    bindNumber('min-len', 'min_len', 1);
    bindNumber('max-len', 'max_len', 46);
    bindNumber('priority-min-len', 'priority_min_len', 1);
    bindNumber('priority-max-len', 'priority_max_len', 46);
    bindNumber('recover-target', 'recover_target', 2);

    const filterFieldMap = {
        'priority-input': 'priority_letters',
        'starts-with-input': 'starts_with_letters',
        'finish-with-input': 'finish_with_letters',
        'exclude-input': 'exclude_letters',
        'recover-exclude': 'recover_exclude'
    };
    Object.entries(filterFieldMap).forEach(([id, field]) => {
        const input = document.getElementById(id);
        if (!input) return;
        input.addEventListener('input', (e) => {
            currentConfig[field] = e.target.value;
            scheduleSyncConfig();
        });
    });

    const strategy = document.getElementById('strategy-select');
    if (strategy) strategy.addEventListener('change', (e) => { currentConfig.strategy = e.target.value; scheduleSyncConfig(); });
    const sublist = document.getElementById('sublist-select');
    if (sublist) sublist.addEventListener('change', (e) => { currentConfig.priority_sublist = e.target.value; scheduleSyncConfig(); });

    const autoType = document.getElementById('auto-type-toggle');
    if (autoType) autoType.addEventListener('change', (e) => { currentConfig.auto_type = e.target.checked; scheduleSyncConfig(); });
    const delayedType = document.getElementById('delayed-type-toggle');
    if (delayedType) delayedType.addEventListener('change', (e) => { currentConfig.delayed_type = e.target.checked; scheduleSyncConfig(); });
    const periodToggle = document.getElementById('period-toggle');
    if (periodToggle) periodToggle.addEventListener('change', (e) => { currentConfig.add_period_prob = e.target.checked ? 0.99 : 0.0; scheduleSyncConfig(); });

    const promptInput = document.getElementById('prompt-input');
    if (promptInput) {
        promptInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                const prompt = e.target.value;
                if (prompt.length > 0) getWord(prompt);
                else document.getElementById('current-word').textContent = 'Waiting...';
            }
        });
    }

    const prefixInput = document.getElementById('prefix-input');
    if (prefixInput) {
        prefixInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                const prefix = e.target.value;
                if (prefix.length > 0) getWord('', prefix);
                else document.getElementById('current-word').textContent = 'Waiting...';
            }
        });
    }

    const presetSelector = document.getElementById('preset-selector');
    if (presetSelector) {
        presetSelector.addEventListener('change', (e) => {
            if (e.target.value) loadPreset(e.target.value);
        });
    }

    const overlay = document.getElementById('calibration-overlay');
    if (overlay) {
        overlay.addEventListener('click', () => {
            if (isCalibrating) {
                isCalibrating = false;
                hideOverlay();
                logAuto('Calibration aborted by user');
            }
        });
        document.addEventListener('keydown', () => {
            if (isCalibrating) {
                isCalibrating = false;
                hideOverlay();
                logAuto('Calibration aborted by user');
            }
        });
    }

    syncConfigToBackend();
}

let allPresets = {};

async function fetchPresets() {
    try {
        const response = await fetch('/api/presets');
        allPresets = await response.json();
        const selector = document.getElementById('preset-selector');
        if (!selector) return;
        selector.innerHTML = '<option value="" disabled selected>Load Preset...</option>';
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
    Object.assign(currentConfig, preset);
    updateUIFromConfig();
    syncConfigToBackend();
}

function updateUIFromConfig() {
    const setValue = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
    const setText = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    const setCheck = (id, val) => { const el = document.getElementById(id); if (el) el.checked = val; };

    setValue('wpm-slider', currentConfig.wpm); setText('wpm-value', currentConfig.wpm);
    setValue('error-slider', currentConfig.error_rate * 100); setText('error-value', currentConfig.error_rate * 100);
    setValue('travadinha-slider', currentConfig.hesitation_prob * 100); setText('travadinha-value', currentConfig.hesitation_prob * 100);
    setValue('retry-slider', currentConfig.retry_rate * 100); setText('retry-value', (currentConfig.retry_rate * 100).toFixed(1));
    setValue('late-error-slider', currentConfig.late_error_rate * 100); setText('late-error-value', currentConfig.late_error_rate * 100);

    setValue('max-typos-slider', currentConfig.max_typos);
    setValue('max-late-slider', currentConfig.max_late_errors);

    setValue('min-len', currentConfig.min_len || 1);
    setValue('max-len', currentConfig.max_len || 46);
    setValue('priority-min-len', currentConfig.priority_min_len || 1);
    setValue('priority-max-len', currentConfig.priority_max_len || 46);

    setValue('strategy-select', currentConfig.strategy);
    setValue('recover-target', currentConfig.recover_target || 2);
    setValue('recover-exclude', currentConfig.recover_exclude || '');

    setCheck('delayed-type-toggle', currentConfig.delayed_type || false);
    setCheck('period-toggle', currentConfig.add_period_prob > 0);
    setCheck('auto-type-toggle', currentConfig.auto_type || false);

    fetchSublistsForLang(currentConfig.lang);
}

async function saveNewPreset() {
    const name = prompt('Enter a name for this preset:');
    if (!name) return;
    try {
        const response = await fetch('/api/presets/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, config: currentConfig })
        });
        if (response.ok) {
            alert('Preset saved successfully!');
            fetchPresets();
        } else {
            const err = await response.json();
            alert(`Failed to save preset: ${err.message || 'Unknown error'}`);
        }
    } catch (e) {
        alert('Network error while saving preset.');
    }
}

async function deletePreset() {
    const name = document.getElementById('preset-selector').value;
    if (!name) return alert('Please select a preset to delete.');
    if (!confirm(`Are you sure you want to delete "${name}"?`)) return;
    try {
        const response = await fetch('/api/presets/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        if (response.ok) {
            alert('Preset deleted!');
            document.getElementById('preset-selector').value = '';
            fetchPresets();
        } else {
            const err = await response.json();
            alert(`Failed to delete: ${err.message || 'Not found'}`);
        }
    } catch (e) {
        alert('Network error while deleting preset.');
    }
}

async function syncConfigToBackend() {
    try {
        await fetch('/api/autoplay/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentConfig)
        });
    } catch (e) {
        console.error('Failed to sync config', e);
    }
}

async function fetchLanguages() {
    try {
        const response = await fetch('/api/languages');
        const languages = await response.json();
        const container = document.getElementById('lang-selector');
        if (!container) return;
        container.innerHTML = '';
        languages.forEach(lang => {
            const btn = document.createElement('button');
            btn.className = `lang-btn ${lang === currentConfig.lang ? 'active' : ''}`;
            btn.textContent = lang;
            btn.onclick = () => setLanguage(lang, btn);
            container.appendChild(btn);
        });
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
        if (!group || !select) return;
        if (sublists.length === 0) {
            group.style.display = 'none';
            return;
        }
        group.style.display = 'flex';
        select.innerHTML = '<option value="">None (Use main list)</option>';
        sublists.forEach(sub => {
            const opt = document.createElement('option');
            opt.value = sub;
            opt.textContent = `\u26ab ${sub.charAt(0).toUpperCase() + sub.slice(1)}`;
            if (sub === currentConfig.priority_sublist) opt.selected = true;
            select.appendChild(opt);
        });
    } catch (e) {
        console.error('Failed to fetch sublists', e);
    }
}

function setLanguage(lang, btnElement) {
    currentConfig.lang = lang;
    currentConfig.priority_sublist = '';
    document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
    if (btnElement) btnElement.classList.add('active');
    fetchSublistsForLang(lang);
    syncConfigToBackend();
}

async function getWord(prompt, prefix = '', suffix = '') {
    try {
        const response = await fetch('/api/word', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt, prefix, suffix, ...currentConfig })
        });
        const data = await response.json();
        const display = document.getElementById('current-word');
        if (data.word) {
            display.textContent = data.word;
            document.getElementById('prompt-input').value = '';
            if (document.getElementById('prefix-input')) document.getElementById('prefix-input').value = '';
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
        document.getElementById('current-word').textContent = 'Database Reloaded!';
        syncConfigToBackend();
        setTimeout(() => { document.getElementById('current-word').textContent = 'Waiting...'; }, 2000);
    } catch (e) {
        console.error('Reset failed', e);
    }
}

function switchTab(tabName) {
    document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
    const targetBtn = document.getElementById(`nav-btn-${tabName}`);
    if (targetBtn) targetBtn.classList.add('active');

    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    const targetContent = document.getElementById(`${tabName}-tab`);
    if (targetContent) targetContent.classList.add('active');

    pollAutoStatus();
}

let autoPlayInterval = null;
let isCalibrating = false;

async function startCalibration() {
    try {
        const response = await fetch('/api/calibration/start', { method: 'POST' });
        const data = await response.json();
        if (data.status === 'started') {
            showOverlay(data.message);
            isCalibrating = true;
        }
    } catch {
        logAuto('Error starting calibration');
    }
}

async function toggleAutoPlay() {
    try {
        const response = await fetch('/api/autoplay/toggle', { method: 'POST' });
        const data = await response.json();
        const btn = document.getElementById('autoplay-toggle-btn');
        if (!btn) return;
        if (data.status === 'active') {
            btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg> Stop Auto-Play';
            btn.classList.replace('btn-primary', 'btn-danger');
            logAuto('Auto-Play STARTED');
        } else {
            btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Start Auto-Play';
            btn.classList.replace('btn-danger', 'btn-primary');
            logAuto('Auto-Play STOPPED');
        }
        pollAutoStatus();
    } catch {
        logAuto('Error toggling auto-play');
    }
}

let lastLogId = 0;

async function pollAutoStatus() {
    try {
        const response = await fetch('/api/autoplay/status');
        const state = await response.json();

        const core = document.getElementById('auto-status-indicator');
        const statusText = document.getElementById('auto-status-text');

        if (statusText) statusText.textContent = state.status;
        if (core) {
            core.className = 'status-core';
            if (state.status === 'Watching') core.classList.add('watching');
            else if (state.status === 'Parsing' || state.status === 'Typing') core.classList.add('active');
        }

        const manualDisplay = document.getElementById('current-word');
        const manualOrb = document.getElementById('status-orb-manual');
        const liveDisplay = document.getElementById('live-word-display');

        let liveTxt = '';
        if (state.suggested_word) {
            liveTxt = state.suggested_word.toUpperCase();
            if (manualDisplay) manualDisplay.textContent = liveTxt;
            if (manualOrb) manualOrb.classList.add('active');
        } else if (state.preview_prompt && state.is_watching) {
            const p = state.preview_prompt.toUpperCase();
            liveTxt = `Prompt: ${p} — buscando...`;
            if (manualDisplay) manualDisplay.textContent = liveTxt;
            if (manualOrb) manualOrb.classList.add('active');
        } else {
            if (manualOrb && !state.preview_prompt && !state.suggested_word) manualOrb.classList.remove('active');
        }

        if (liveDisplay) {
            liveDisplay.textContent = liveTxt || 'WAITING TURN...';
        }

        if (state.status === 'Calibrating') {
            isCalibrating = true;
            let inst = 'Click to calibrate...';
            if (state.calibration_step === 'turn_start') inst = 'Click Top-Left of prompt area';
            if (state.calibration_step === 'turn_end') inst = 'Click Bottom-Right of prompt area';
            updateOverlay(inst);
        } else {
            if (isCalibrating) {
                isCalibrating = false;
                hideOverlay();
                logAuto('Calibration Finished');
            }
        }

        if (state.logs && state.logs.length > 0) {
            state.logs.forEach(entry => {
                const id = typeof entry === 'object' ? entry.id : 0;
                const msg = typeof entry === 'object' ? entry.msg : entry;
                if (id > lastLogId) {
                    logAuto(msg);
                    lastLogId = id;
                }
            });
        }

        const btn = document.getElementById('autoplay-toggle-btn');
        if (btn) {
            const isStopBtn = btn.textContent.includes('Stop');
            if (state.is_watching && !isStopBtn) {
                btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg> Stop Auto-Play';
                btn.classList.replace('btn-primary', 'btn-danger');
            } else if (!state.is_watching && isStopBtn) {
                btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Start Auto-Play';
                btn.classList.replace('btn-danger', 'btn-primary');
            }
        }
    } catch {
        /* ignore */
    }
}

function logAuto(msg) {
    const container = document.getElementById('auto-logs');
    if (!container) return;
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.textContent = `[${new Date().toLocaleTimeString('en-US', { hour12: false, hour: 'numeric', minute: 'numeric', second: 'numeric' })}] ${msg}`;
    container.prepend(entry);
}

function showOverlay(msg) {
    const overlay = document.getElementById('calibration-overlay');
    if (overlay) {
        document.getElementById('calib-instruction').textContent = msg;
        overlay.classList.remove('hidden');
    }
}

function updateOverlay(msg) {
    const inst = document.getElementById('calib-instruction');
    if (inst) inst.textContent = msg;
}

function hideOverlay() {
    const overlay = document.getElementById('calibration-overlay');
    if (overlay) overlay.classList.add('hidden');
}
