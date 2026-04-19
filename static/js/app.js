document.addEventListener('DOMContentLoaded', () => {
    fetchLanguages();
    fetchPresets();
    setupEventListeners();
    setupGlobalShortcuts();
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
        // Only trigger if Alt is pressed
        if (!e.altKey) return;
        
        switch(e.key) {
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
            case 's':
            case 'S':
                e.preventDefault();
                if (document.getElementById('game-mode-select') && document.getElementById('game-mode-select').value === 'letterlink') {
                    solveLetterLink();
                }
                break;
        }
    });

    // Also support simple 1, 2, 3 if not active in input
    document.addEventListener('keyup', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
        if (e.altKey || e.ctrlKey || e.metaKey) return;
        
        if (e.key === '1') switchTab('manual');
        if (e.key === '2') switchTab('auto');
        if (e.key === '3') switchTab('config');
    });
}

function setupEventListeners() {
    // Sliders
    const bindSlider = (id, field, divisor) => {
        const slider = document.getElementById(id + '-slider');
        const display = document.getElementById(id + '-value');
        if(!slider) return;
        slider.addEventListener('input', (e) => {
            currentConfig[field] = parseFloat(e.target.value) / divisor;
            if(display) display.textContent = display.textContent.includes('%') ? e.target.value : (field === 'retry_rate' ? (e.target.value).toString() : e.target.value);
            scheduleSyncConfig();
        });
    };

    bindSlider('wpm', 'wpm', 1);
    bindSlider('error', 'error_rate', 100);
    bindSlider('travadinha', 'hesitation_prob', 100);
    bindSlider('retry', 'retry_rate', 100);
    bindSlider('late-error', 'late_error_rate', 100);

    const maxTypos = document.getElementById('max-typos-slider');
    if(maxTypos) maxTypos.addEventListener('input', (e) => { currentConfig.max_typos = parseInt(e.target.value); scheduleSyncConfig(); });
    const maxLate = document.getElementById('max-late-slider');
    if(maxLate) maxLate.addEventListener('input', (e) => { currentConfig.max_late_errors = parseInt(e.target.value); scheduleSyncConfig(); });

    // Number Inputs
    const bindNumber = (id, field, defaultVal) => {
        const el = document.getElementById(id);
        if(!el) return;
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

    // Text filter inputs — explicit map for clarity and maintainability
    const filterFieldMap = {
        'priority-input':    'priority_letters',
        'starts-with-input': 'starts_with_letters',
        'finish-with-input': 'finish_with_letters',
        'exclude-input':     'exclude_letters',
        'recover-exclude':   'recover_exclude'
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
    if(strategy) strategy.addEventListener('change', (e) => { currentConfig.strategy = e.target.value; scheduleSyncConfig(); });
    const sublist = document.getElementById('sublist-select');
    if(sublist) sublist.addEventListener('change', (e) => { currentConfig.priority_sublist = e.target.value; scheduleSyncConfig(); });

    // Toggles
    const autoType = document.getElementById('auto-type-toggle');
    if(autoType) autoType.addEventListener('change', (e) => { currentConfig.auto_type = e.target.checked; scheduleSyncConfig(); });
    const delayedType = document.getElementById('delayed-type-toggle');
    if(delayedType) delayedType.addEventListener('change', (e) => { currentConfig.delayed_type = e.target.checked; scheduleSyncConfig(); });
    const periodToggle = document.getElementById('period-toggle');
    if(periodToggle) periodToggle.addEventListener('change', (e) => { currentConfig.add_period_prob = e.target.checked ? 0.99 : 0.0; scheduleSyncConfig(); });

    // Game Inputs
    const promptInput = document.getElementById('prompt-input');
    if(promptInput) {
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

    // Game Mode Toggle
    const gameModeSelect = document.getElementById('game-mode-select');
    if (gameModeSelect) {
        gameModeSelect.addEventListener('change', (e) => {
            const mode = e.target.value;
            const orb = document.getElementById('classic-orb-container');
            const autoBtn = document.getElementById('autoplay-toggle-btn');
            const solveBtn = document.getElementById('solve-ll-btn');
            
            if (mode === 'letterlink') {
                if(orb) orb.style.display = 'none';
                if(autoBtn) autoBtn.style.display = 'none';
                if(solveBtn) solveBtn.style.display = 'block';
            } else {
                if(orb) orb.style.display = 'flex';
                if(autoBtn) autoBtn.style.display = 'block';
                if(solveBtn) solveBtn.style.display = 'none';
            }
        });
    }

    // Presets
    const presetSelector = document.getElementById('preset-selector');
    if(presetSelector) {
        presetSelector.addEventListener('change', (e) => {
            if (e.target.value) loadPreset(e.target.value);
        });
    }
    
    // Close overlay on click
    const overlay = document.getElementById('calibration-overlay');
    if(overlay) {
        overlay.addEventListener('click', (e) => {
            if (isCalibrating) {
                isCalibrating = false;
                hideOverlay();
                logAuto("Calibration aborted by user");
            }
        });
        document.addEventListener('keydown', (e) => {
            if (isCalibrating) {
                isCalibrating = false;
                hideOverlay();
                logAuto("Calibration aborted by user");
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
        if(!selector) return;
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
    console.log(`Loaded preset: ${name}`);
}

function updateUIFromConfig() {
    const setValue = (id, val) => { const el = document.getElementById(id); if(el) el.value = val; };
    const setText = (id, val) => { const el = document.getElementById(id); if(el) el.textContent = val; };
    const setCheck = (id, val) => { const el = document.getElementById(id); if(el) el.checked = val; };
    
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
    const name = prompt("Enter a name for this preset:");
    if (!name) return;
    try {
        const response = await fetch('/api/presets/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, config: currentConfig })
        });
        if (response.ok) {
            alert("Preset saved successfully!");
            fetchPresets();
        }
    } catch (e) { console.error('Failed to save', e); }
}

async function deletePreset() {
    const name = document.getElementById('preset-selector').value;
    if (!name) return alert("Please select a preset to delete.");
    if (!confirm(`Are you sure you want to delete "${name}"?`)) return;
    try {
        const response = await fetch('/api/presets/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        if (response.ok) {
            alert("Preset deleted!");
            document.getElementById('preset-selector').value = "";
            fetchPresets();
        }
    } catch (e) { console.error('Failed to delete', e); }
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
        if(!container) return;
        container.innerHTML = '';
        languages.forEach(lang => {
            const btn = document.createElement('button');
            btn.className = `lang-btn ${lang === currentConfig.lang ? 'active' : ''}`;
            btn.textContent = lang;
            btn.onclick = () => setLanguage(lang, btn);
            container.appendChild(btn);
        });
        await fetchSublistsForLang(currentConfig.lang);
    } catch (e) { console.error('Failed to fetch languages', e); }
}

async function fetchSublistsForLang(lang) {
    try {
        const response = await fetch(`/api/sublists/${encodeURIComponent(lang)}`);
        const sublists = await response.json();
        const group = document.getElementById('sublist-group');
        const select = document.getElementById('sublist-select');
        if(!group || !select) return;
        if (sublists.length === 0) {
            group.style.display = 'none';
            return;
        }
        group.style.display = 'flex';
        select.innerHTML = '<option value="">None (Use main list)</option>';
        sublists.forEach(sub => {
            const opt = document.createElement('option');
            opt.value = sub;
            opt.textContent = `🔹 ${sub.charAt(0).toUpperCase() + sub.slice(1)}`;
            if (sub === currentConfig.priority_sublist) opt.selected = true;
            select.appendChild(opt);
        });
    } catch (e) { console.error('Failed to fetch sublists', e); }
}

function setLanguage(lang, btnElement) {
    currentConfig.lang = lang;
    currentConfig.priority_sublist = '';
    document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
    if(btnElement) btnElement.classList.add('active');
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
            if(document.getElementById('prefix-input')) document.getElementById('prefix-input').value = '';
        } else {
            display.textContent = 'No match found';
        }
    } catch (e) { console.error('Error fetching word', e); }
}

async function resetWords() {
    try {
        await fetch('/api/reset', { method: 'POST' });
        document.getElementById('current-word').textContent = 'Database Reloaded!';
        syncConfigToBackend();
        setTimeout(() => { document.getElementById('current-word').textContent = 'Waiting...'; }, 2000);
    } catch (e) { console.error('Reset failed', e); }
}

function switchTab(tabName) {
    document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
    const targetBtn = document.getElementById(`nav-btn-${tabName}`);
    if (targetBtn) targetBtn.classList.add('active');

    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    const targetContent = document.getElementById(`${tabName}-tab`);
    if(targetContent) targetContent.classList.add('active');

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

// Auto-Play
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
    } catch (e) { logAuto("Error starting calibration"); }
}

async function toggleAutoPlay() {
    try {
        const response = await fetch('/api/autoplay/toggle', { method: 'POST' });
        const data = await response.json();
        const btn = document.getElementById('autoplay-toggle-btn');
        if(!btn) return;
        if (data.status === 'active') {
            btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg> Stop Auto-Play';
            btn.classList.replace('btn-primary', 'btn-danger');
            logAuto("Auto-Play STARTED");
        } else {
            btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Start Auto-Play';
            btn.classList.replace('btn-danger', 'btn-primary');
            logAuto("Auto-Play STOPPED");
        }
        pollAutoStatus();
    } catch (e) { logAuto("Error toggling auto-play"); }
}

let lastLogId = 0;
async function pollAutoStatus() {
    if (!document.getElementById('auto-tab').classList.contains('active') && !isCalibrating) return;
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

        if (state.status === 'Calibrating') {
            isCalibrating = true;
            let inst = "Click to calibrate...";
            if (state.calibration_step === 'turn_start') inst = "Click Top-Left of prompt area";
            if (state.calibration_step === 'turn_end') inst = "Click Bottom-Right of prompt area";
            updateOverlay(inst);
        } else {
            if (isCalibrating) {
                isCalibrating = false;
                hideOverlay();
                logAuto("Calibration Finished");
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
        if(btn) {
            const isStopBtn = btn.textContent.includes('Stop');
            if (state.is_watching && !isStopBtn) {
                btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg> Stop Auto-Play';
                btn.classList.replace('btn-primary', 'btn-danger');
            } else if (!state.is_watching && isStopBtn) {
                btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Start Auto-Play';
                btn.classList.replace('btn-danger', 'btn-primary');
            }
        }
    } catch (e) {
        // Suppress poll errors to terminal spam
    }
}

function logAuto(msg) {
    const container = document.getElementById('auto-logs');
    if(!container) return;
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.textContent = `[${new Date().toLocaleTimeString('en-US', { hour12: false, hour: "numeric", minute: "numeric", second: "numeric" })}] ${msg}`;
    container.prepend(entry);
}

function showOverlay(msg) {
    const overlay = document.getElementById('calibration-overlay');
    if(overlay) {
        document.getElementById('calib-instruction').textContent = msg;
        overlay.classList.remove('hidden');
    }
}

function updateOverlay(msg) {
    const inst = document.getElementById('calib-instruction');
    if(inst) inst.textContent = msg;
}

function hideOverlay() {
    const overlay = document.getElementById('calibration-overlay');
    if(overlay) overlay.classList.add('hidden');
}

let lastLLData = null;

function renderLLGrid(matrix, path) {
    let gridHtml = '<div class="ll-visual-grid">';
    for (let r = 0; r < 5; r++) {
        gridHtml += '<div class="ll-row">';
        for (let c = 0; c < 5; c++) {
            let stepIndex = path.findIndex(p => p[0] === r && p[1] === c);
            let content = matrix[r][c];
            let cellClass = stepIndex >= 0 ? 'll-cell in-path' : 'll-cell';
            if (content === '.' || content === '-') cellClass += ' empty';
            let badge = stepIndex >= 0 ? `<div class="step-badge">${stepIndex + 1}</div>` : '';
            gridHtml += `<div class="${cellClass}">${content}${badge}</div>`;
        }
        gridHtml += '</div>';
    }
    gridHtml += '</div>';
    return gridHtml;
}

function updateLLResultUI(index) {
    if (!lastLLData) return;
    const panel = document.getElementById('ll-result-panel');
    const wordObj = lastLLData.top_words[index];
    
    let gridHtml = renderLLGrid(lastLLData.matrix, wordObj.path);
    let wordListHtml = lastLLData.top_words.map((w, i) => `
        <div class="ll-word ${i === index ? 'best' : ''}" onclick="updateLLResultUI(${i})">
            ${i+1}. ${w.word.toUpperCase()} 
            <span class="ll-len">★ ${w.score} pts</span>
        </div>
    `).join('');
    
    panel.innerHTML = gridHtml + wordListHtml;
}

async function solveLetterLink() {
    logAuto('> Scanning Letter Link grid...');
    try {
        const response = await fetch('/api/letterlink/solve', { method: 'POST' });
        const data = await response.json();
        if (data.status === 'success') {
            lastLLData = data;
            const display = document.getElementById('current-word');
            if (display) display.textContent = data.word.toUpperCase();

            logAuto(`✅ BEST: ${data.word.toUpperCase()} (${data.score} pts)`);
            
            const panel = document.getElementById('ll-result-panel');
            if (panel) {
                panel.style.display = 'block';
                updateLLResultUI(0);
            }
        } else {
            logAuto(`>> Error: ${data.message}`);
        }
    } catch (e) {
        console.error(e);
        logAuto('>> Network error requesting solve.');
    }
}
