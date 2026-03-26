// ─── Helpers ──────────────────────────────────────────────────────────────────

function removeAccents(str) {
    return str.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

function setsEqual(a, b) {
    if (a.size !== b.size) return false;
    for (const item of a) if (!b.has(item)) return false;
    return true;
}

function parseCharsInput(str) {
    return new Set(str.toLowerCase().replace(/[\s,]/g, '').split('').filter(c => c));
}

function randomChoice(arr) {
    return arr[Math.floor(Math.random() * arr.length)];
}

// ─── WordManager ──────────────────────────────────────────────────────────────

class WordManager {
    constructor() {
        this.wordlists = {};   // { lang: { full: string[], lower: string[] } }
        this.sublists  = {};   // { lang: { subname: { full: string[], lower: string[] } } }
        this.usedWords = new Set();
        this.recoverTarget  = 2;
        this.recoverExclude = new Set();
        this.letterTargets  = {};
        this.currentAlphaChar = 'a';
        this._buildInitialTargets();
    }

    _buildInitialTargets() {
        this.letterTargets = {};
        for (let i = 97; i <= 122; i++) {
            const c = String.fromCharCode(i);
            if (!this.recoverExclude.has(c)) {
                this.letterTargets[c] = this.recoverTarget;
            }
        }
    }

    setRecoverConfig(target, excludeStr) {
        const excludeChars = parseCharsInput(excludeStr);
        if (target !== this.recoverTarget || !setsEqual(excludeChars, this.recoverExclude)) {
            this.recoverTarget  = target;
            this.recoverExclude = excludeChars;
            this._buildInitialTargets();
        }
    }

    /** Load a wordlist file (plain text, one word per line). */
    async loadWordlist(name, url) {
        try {
            const res = await fetch(url);
            if (!res.ok) return;
            const text = await res.text();
            const words = text.split('\n').map(w => w.trim()).filter(w => w.length > 0);
            const lower = words.map(w => w.toLowerCase());

            if (name.includes('_')) {
                // Sub-list: e.g. "Portuguese_palindromos"
                const idx      = name.indexOf('_');
                const mainLang = name.slice(0, idx);
                const subName  = name.slice(idx + 1);
                if (!this.sublists[mainLang]) this.sublists[mainLang] = {};
                this.sublists[mainLang][subName] = { full: words, lower };
            } else {
                this.wordlists[name] = { full: words, lower };
            }
        } catch (e) {
            console.error(`Failed to load wordlist "${name}" from "${url}":`, e);
        }
    }

    getLanguages()    { return Object.keys(this.wordlists); }
    getSublists(lang) { return Object.keys(this.sublists[lang] || {}); }
    getSublistsMap()  {
        const map = {};
        for (const lang in this.sublists) map[lang] = Object.keys(this.sublists[lang]);
        return map;
    }

    /**
     * Find a word matching the prompt.
     * Mirrors the Python WordManager.get_word() logic exactly.
     */
    getWord(prompt, lang, minLen, maxLen, strategy, {
        priorityLetters   = '',
        excludeLetters    = '',
        startsWith        = '',
        priorityMinLen    = 1,
        priorityMaxLen    = 46,
        prioritySublist   = ''
    } = {}) {
        if (!this.wordlists[lang]) return null;

        const promptLower = prompt.toLowerCase();

        // ── Priority sub-list ──────────────────────────────────────────────────
        if (prioritySublist && this.sublists[lang]?.[prioritySublist]) {
            const sub = this.sublists[lang][prioritySublist];
            const subMatches = sub.full.filter((_, i) => {
                const wl = sub.lower[i];
                return wl.includes(promptLower)
                    && wl.length >= minLen && wl.length <= maxLen
                    && !this.usedWords.has(wl);
            });
            if (subMatches.length > 0) return randomChoice(subMatches);
        }

        // ── Main list ──────────────────────────────────────────────────────────
        const data = this.wordlists[lang];
        const excludeChars = parseCharsInput(excludeLetters);

        let candidates = data.full.filter((_, i) => {
            const wl = data.lower[i];
            return wl.includes(promptLower)
                && wl.length >= minLen && wl.length <= maxLen
                && !this.usedWords.has(wl);
        });

        if (candidates.length === 0) return null;

        // ── Exclude letters from word-start ────────────────────────────────────
        if (excludeChars.size > 0) {
            const filtered = candidates.filter(w => !excludeChars.has(w.toLowerCase()[0]));
            if (filtered.length > 0) candidates = filtered;
        }

        // ── Starts-with filter ─────────────────────────────────────────────────
        const startsChars = parseCharsInput(startsWith);
        if (startsChars.size > 0) {
            const filtered = candidates.filter(w => startsChars.has(w.toLowerCase()[0]));
            if (filtered.length > 0) candidates = filtered;
        }

        // ── Priority length ────────────────────────────────────────────────────
        if (priorityMinLen > 1 || priorityMaxLen < 46) {
            const filtered = candidates.filter(w => w.length >= priorityMinLen && w.length <= priorityMaxLen);
            if (filtered.length > 0) candidates = filtered;
        }

        // ── Priority letters (contains) ────────────────────────────────────────
        const priChars = parseCharsInput(priorityLetters);
        if (priChars.size > 0) {
            const scored = candidates.map(w => {
                const wl    = w.toLowerCase();
                const score = [...priChars].filter(c => wl.includes(c)).length;
                return { score, word: w };
            });
            const topScore = Math.max(...scored.map(s => s.score));
            if (topScore > 0) candidates = scored.filter(s => s.score === topScore).map(s => s.word);
        }

        // ── Strategy ───────────────────────────────────────────────────────────
        switch (strategy) {
            case 'shortest':
                candidates.sort((a, b) => a.length - b.length);
                return candidates[0];

            case 'longest':
                candidates.sort((a, b) => b.length - a.length);
                return candidates[0];

            case 'hyphen': {
                const hyphenated = candidates.filter(w => w.includes('-'));
                return hyphenated.length > 0 ? randomChoice(hyphenated) : randomChoice(candidates);
            }

            case 'alpha': {
                if (startsChars.size > 0) return randomChoice(candidates);

                if (excludeChars.size > 0 && excludeChars.size < 26) {
                    while (excludeChars.has(this.currentAlphaChar)) this._advanceAlphaChar();
                }
                const alphaCands = candidates.filter(w => w.toLowerCase().startsWith(this.currentAlphaChar));
                if (alphaCands.length > 0) {
                    const word = randomChoice(alphaCands);
                    this._advanceAlphaChar();
                    return word;
                }
                return randomChoice(candidates);
            }

            case 'recover': {
                const scored = candidates.map(w => {
                    const wClean = removeAccents(w.toLowerCase());
                    const score  = [...new Set(wClean)].reduce((s, c) => s + (this.letterTargets[c] ?? 0), 0);
                    return { score, word: w };
                });
                const bestScore = Math.max(...scored.map(s => s.score));
                if (bestScore > 0) {
                    const best = scored.filter(s => s.score === bestScore).map(s => s.word);
                    return randomChoice(best);
                }
                return randomChoice(candidates);
            }

            default: // 'random'
                return randomChoice(candidates);
        }
    }

    _advanceAlphaChar() {
        this.currentAlphaChar = this.currentAlphaChar === 'z'
            ? 'a'
            : String.fromCharCode(this.currentAlphaChar.charCodeAt(0) + 1);
    }

    markUsed(word) {
        if (!word) return;
        const wLower = word.toLowerCase();
        this.usedWords.add(wLower);

        const wClean = removeAccents(wLower);
        for (const c of new Set(wClean)) {
            if (c in this.letterTargets && this.letterTargets[c] > 0) this.letterTargets[c]--;
        }
        if (Object.values(this.letterTargets).every(v => v === 0)) this._buildInitialTargets();
    }

    resetUsed() {
        this.usedWords.clear();
        this._buildInitialTargets();
        this.currentAlphaChar = 'a';
    }
}

// ─── Application State ────────────────────────────────────────────────────────

const wm = new WordManager();

let currentConfig = {
    lang: 'Portuguese',
    min_len: 1,
    max_len: 46,
    priority_min_len: 1,
    priority_max_len: 46,
    strategy: 'random',
    priority_letters: '',
    exclude_letters: '',
    starts_with_letters: '',
    recover_target: 2,
    recover_exclude: '',
    priority_sublist: ''
};

// ─── Bootstrap ────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
    await loadAllWordlists();
    buildLanguageSelector();
    buildSublistSelector(currentConfig.lang);
    loadPresetsFromStorage();
    setupEventListeners();
});

async function loadAllWordlists() {
    try {
        const res      = await fetch('wordlists/manifest.json');
        const manifest = await res.json();

        const promises = [];

        for (const name of manifest.wordlists) {
            promises.push(wm.loadWordlist(name, `wordlists/${name}.txt`));
        }

        // Sub-lists
        for (const [lang, subs] of Object.entries(manifest.sublists || {})) {
            for (const sub of subs) {
                promises.push(wm.loadWordlist(`${lang}_${sub}`, `wordlists/${lang}_${sub}.txt`));
            }
        }

        await Promise.all(promises);
    } catch (e) {
        console.error('Failed to load wordlists manifest:', e);
    }
}

// ─── Language & Sub-list UI ───────────────────────────────────────────────────

function buildLanguageSelector() {
    const container = document.getElementById('lang-selector');
    container.innerHTML = '';

    for (const lang of wm.getLanguages()) {
        const btn = document.createElement('button');
        btn.className = `lang-btn ${lang === currentConfig.lang ? 'active' : ''}`;
        btn.textContent = lang;
        btn.onclick = () => setLanguage(lang, btn);
        container.appendChild(btn);
    }
}

function buildSublistSelector(lang) {
    const group  = document.getElementById('sublist-group');
    const select = document.getElementById('sublist-select');
    const subs   = wm.getSublists(lang);

    if (subs.length === 0) {
        group.style.display = 'none';
        return;
    }

    group.style.display = 'block';
    select.innerHTML = '<option value="">Nenhuma (usar lista principal)</option>';
    for (const sub of subs) {
        const opt = document.createElement('option');
        opt.value = sub;
        opt.textContent = `🔹 ${sub.charAt(0).toUpperCase() + sub.slice(1)}`;
        if (sub === currentConfig.priority_sublist) opt.selected = true;
        select.appendChild(opt);
    }
}

function setLanguage(lang, btnElement) {
    currentConfig.lang = lang;
    currentConfig.priority_sublist = '';

    document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
    btnElement.classList.add('active');

    buildSublistSelector(lang);
    saveConfigToStorage();
}

// ─── Event Listeners ─────────────────────────────────────────────────────────

function setupEventListeners() {
    document.getElementById('strategy-select').addEventListener('change', e => {
        currentConfig.strategy = e.target.value;
        saveConfigToStorage();
    });

    document.getElementById('min-len').addEventListener('change', e => {
        currentConfig.min_len = parseInt(e.target.value) || 1;
        saveConfigToStorage();
    });

    document.getElementById('max-len').addEventListener('change', e => {
        currentConfig.max_len = parseInt(e.target.value) || 46;
        saveConfigToStorage();
    });

    const priMinLen = document.getElementById('priority-min-len');
    if (priMinLen) priMinLen.addEventListener('change', e => {
        currentConfig.priority_min_len = parseInt(e.target.value) || 1;
        saveConfigToStorage();
    });

    const priMaxLen = document.getElementById('priority-max-len');
    if (priMaxLen) priMaxLen.addEventListener('change', e => {
        currentConfig.priority_max_len = parseInt(e.target.value) || 46;
        saveConfigToStorage();
    });

    const priorityInput = document.getElementById('priority-input');
    if (priorityInput) priorityInput.addEventListener('input', e => {
        currentConfig.priority_letters = e.target.value;
    });

    const startsWithInput = document.getElementById('starts-with-input');
    if (startsWithInput) startsWithInput.addEventListener('input', e => {
        currentConfig.starts_with_letters = e.target.value;
    });

    const excludeInput = document.getElementById('exclude-input');
    if (excludeInput) excludeInput.addEventListener('input', e => {
        currentConfig.exclude_letters = e.target.value;
    });

    const recoverTargetInput = document.getElementById('recover-target');
    if (recoverTargetInput) recoverTargetInput.addEventListener('change', e => {
        currentConfig.recover_target = parseInt(e.target.value) || 2;
        wm.setRecoverConfig(currentConfig.recover_target, currentConfig.recover_exclude);
        saveConfigToStorage();
    });

    const recoverExcludeInput = document.getElementById('recover-exclude');
    if (recoverExcludeInput) recoverExcludeInput.addEventListener('input', e => {
        currentConfig.recover_exclude = e.target.value;
        wm.setRecoverConfig(currentConfig.recover_target, currentConfig.recover_exclude);
    });

    const sublistSelect = document.getElementById('sublist-select');
    if (sublistSelect) sublistSelect.addEventListener('change', e => {
        currentConfig.priority_sublist = e.target.value;
        saveConfigToStorage();
    });

    // Prompt input: Enter key triggers word lookup
    const promptInput = document.getElementById('prompt-input');
    promptInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
            const prompt = e.target.value.trim();
            if (prompt.length > 0) {
                getWord(prompt);
            } else {
                document.getElementById('current-word').textContent = 'Waiting...';
            }
        }
    });

    // Preset selector
    document.getElementById('preset-selector').addEventListener('change', e => {
        if (e.target.value) loadPreset(e.target.value);
    });

    // Restore saved config from localStorage
    restoreConfigFromStorage();
}

// ─── Word Lookup ──────────────────────────────────────────────────────────────

function getWord(prompt) {
    wm.setRecoverConfig(currentConfig.recover_target, currentConfig.recover_exclude);

    const word = wm.getWord(
        prompt,
        currentConfig.lang,
        currentConfig.min_len,
        currentConfig.max_len,
        currentConfig.strategy,
        {
            priorityLetters : currentConfig.priority_letters,
            excludeLetters  : currentConfig.exclude_letters,
            startsWith      : currentConfig.starts_with_letters,
            priorityMinLen  : currentConfig.priority_min_len,
            priorityMaxLen  : currentConfig.priority_max_len,
            prioritySublist : currentConfig.priority_sublist
        }
    );

    const display = document.getElementById('current-word');
    if (word) {
        wm.markUsed(word);
        display.textContent = word;
        document.getElementById('prompt-input').value = '';
    } else {
        display.textContent = 'No match found';
    }
}

function resetWords() {
    wm.resetUsed();
    document.getElementById('current-word').textContent = 'Words Reset!';
    setTimeout(() => {
        document.getElementById('current-word').textContent = 'Waiting...';
    }, 2000);
}

// ─── Tab Switching ────────────────────────────────────────────────────────────

function switchTab(tabName) {
    document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
    const buttons = document.querySelectorAll('.nav-btn');
    if (tabName === 'manual') buttons[0].classList.add('active');
    if (tabName === 'config') buttons[1].classList.add('active');

    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById(`${tabName}-tab`).classList.add('active');
}

// ─── Presets (localStorage) ───────────────────────────────────────────────────

const PRESETS_KEY = 'wordbombHelper_presets';

function loadPresetsFromStorage() {
    const raw = localStorage.getItem(PRESETS_KEY);
    if (!raw) return;
    try {
        allPresets = JSON.parse(raw);
        _rebuildPresetSelector();
    } catch (e) {
        console.error('Failed to parse presets from localStorage', e);
    }
}

function _rebuildPresetSelector() {
    const selector = document.getElementById('preset-selector');
    selector.innerHTML = '<option value="" disabled selected>Selecione um preset...</option>';
    for (const name of Object.keys(allPresets)) {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        selector.appendChild(opt);
    }
}

let allPresets = {};

function saveNewPreset() {
    const name = prompt('Digite um nome para este preset:');
    if (!name) return;

    allPresets[name] = {
        lang              : currentConfig.lang,
        min_len           : currentConfig.min_len,
        max_len           : currentConfig.max_len,
        priority_min_len  : currentConfig.priority_min_len,
        priority_max_len  : currentConfig.priority_max_len,
        strategy          : currentConfig.strategy,
        priority_letters  : currentConfig.priority_letters,
        exclude_letters   : currentConfig.exclude_letters,
        starts_with_letters: currentConfig.starts_with_letters,
        recover_target    : currentConfig.recover_target,
        recover_exclude   : currentConfig.recover_exclude,
        priority_sublist  : currentConfig.priority_sublist
    };

    localStorage.setItem(PRESETS_KEY, JSON.stringify(allPresets));
    _rebuildPresetSelector();
    alert('Preset salvo!');
}

function loadPreset(name) {
    const preset = allPresets[name];
    if (!preset) return;
    Object.assign(currentConfig, preset);
    _applyConfigToUI();
    saveConfigToStorage();
}

function deletePreset() {
    const selector = document.getElementById('preset-selector');
    const name     = selector.value;
    if (!name) { alert('Por favor, selecione um preset para remover.'); return; }
    if (!confirm(`Tem certeza de que deseja remover o preset "${name}"?`)) return;

    delete allPresets[name];
    localStorage.setItem(PRESETS_KEY, JSON.stringify(allPresets));
    selector.value = '';
    _rebuildPresetSelector();
    alert('Preset removido com sucesso!');
}

// ─── Config persistence (localStorage) ───────────────────────────────────────

const CONFIG_KEY = 'wordbombHelper_config';

function saveConfigToStorage() {
    localStorage.setItem(CONFIG_KEY, JSON.stringify(currentConfig));
}

function restoreConfigFromStorage() {
    try {
        const raw = localStorage.getItem(CONFIG_KEY);
        if (raw) Object.assign(currentConfig, JSON.parse(raw));
    } catch (e) {
        console.warn('Could not restore config from localStorage', e);
    }
    _applyConfigToUI();
}

function _applyConfigToUI() {
    const strategySelect = document.getElementById('strategy-select');
    if (strategySelect) strategySelect.value = currentConfig.strategy;

    const minL = document.getElementById('min-len');
    if (minL) minL.value = currentConfig.min_len || 1;

    const maxL = document.getElementById('max-len');
    if (maxL) maxL.value = currentConfig.max_len || 46;

    const priMinL = document.getElementById('priority-min-len');
    if (priMinL) priMinL.value = currentConfig.priority_min_len || 1;

    const priMaxL = document.getElementById('priority-max-len');
    if (priMaxL) priMaxL.value = currentConfig.priority_max_len || 46;

    const recTarget = document.getElementById('recover-target');
    if (recTarget) recTarget.value = currentConfig.recover_target || 2;

    const recExclude = document.getElementById('recover-exclude');
    if (recExclude) recExclude.value = currentConfig.recover_exclude || '';

    // Highlight the active language button (if buttons already exist)
    document.querySelectorAll('.lang-btn').forEach(btn => {
        btn.classList.toggle('active', btn.textContent === currentConfig.lang);
    });

    buildSublistSelector(currentConfig.lang);

    const sublistSelect = document.getElementById('sublist-select');
    if (sublistSelect && currentConfig.priority_sublist) {
        sublistSelect.value = currentConfig.priority_sublist;
    }
}
