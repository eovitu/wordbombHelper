// WordBomb Helper — modo Auto apenas. Calibra, dá play, mostra a palavra sugerida.
// Sem auto-type: o usuário digita. Config só com idioma, sublista, estratégia e filtros.

const cfg = {
  lang: 'Português',
  priority_sublist: '',
  strategy: 'random',
  priority_letters: '',
  starts_with_letters: '',
  finish_with_letters: '',
  exclude_letters: '',
  min_len: 1,
  max_len: 46,
  recover_mode: 'casual',
  recover_exclude: '',
  auto_type: false,   // fixo: nunca digita sozinho
};

const $ = (id) => document.getElementById(id);

document.addEventListener('DOMContentLoaded', async () => {
  restoreCompactMode();
  await fetchLanguages();
  bindInputs();
  syncRecoverVisibility();
  bindDictionary();
  loadDictionary();
  bindDiagnostics();
  bindPractice();
  syncConfig();
  initSSE();
  setInterval(poll, 1000);  // logs + calibração + fallback (1s em vez de 150ms)
  poll();
});

/* ---------- Config -> backend (debounced) ---------- */
let syncTimer = null;
function syncConfig() {
  clearTimeout(syncTimer);
  syncTimer = setTimeout(() => {
    fetch('/api/autoplay/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cfg),
    }).catch(() => {});
  }, 150);
}

function bindInputs() {
  const text = {
    'f-contains': 'priority_letters',
    'f-starts': 'starts_with_letters',
    'f-finish': 'finish_with_letters',
    'f-exclude': 'exclude_letters',
    'r-exclude': 'recover_exclude',
  };
  for (const [id, key] of Object.entries(text)) {
    $(id).addEventListener('input', (e) => { cfg[key] = e.target.value; syncConfig(); });
  }
  const num = { 'f-min': 'min_len', 'f-max': 'max_len' };
  for (const [id, key] of Object.entries(num)) {
    $(id).addEventListener('change', (e) => { cfg[key] = parseInt(e.target.value) || cfg[key]; syncConfig(); });
  }
  $('strategy').addEventListener('change', (e) => {
    cfg.strategy = e.target.value;
    syncRecoverVisibility();
    syncConfig();
  });
  $('recover-mode').addEventListener('change', (e) => { cfg.recover_mode = e.target.value; syncConfig(); });
  $('sublist').addEventListener('change', (e) => { cfg.priority_sublist = e.target.value; syncConfig(); });
  $('prompt-correction').addEventListener('submit', correctPrompt);
}

function syncRecoverVisibility() {
  $('recover-field').hidden = cfg.strategy !== 'recover';
}

/* ---------- Idiomas / sublistas ---------- */
async function fetchLanguages() {
  try {
    const langs = await (await fetch('/api/languages')).json();
    const box = $('langs');
    box.innerHTML = '';
    langs.forEach((lang) => {
      const b = document.createElement('button');
      b.className = 'lang' + (lang === cfg.lang ? ' on' : '');
      b.textContent = lang;
      b.onclick = () => setLanguage(lang);
      box.appendChild(b);
    });
    await fetchSublists(cfg.lang);
  } catch {}
}

function setLanguage(lang) {
  cfg.lang = lang;
  cfg.priority_sublist = '';
  dictionaryImportReady = false;
  const applyImport = $('dictionary-apply-import');
  if (applyImport) applyImport.disabled = true;
  document.querySelectorAll('.lang').forEach((b) => b.classList.toggle('on', b.textContent === lang));
  fetchSublists(lang);
  loadDictionary();
  syncConfig();
}

async function fetchSublists(lang) {
  try {
    const subs = await (await fetch('/api/sublists/' + encodeURIComponent(lang))).json();
    const field = $('sublist-field');
    const sel = $('sublist');
    if (!subs.length) { field.hidden = true; return; }
    field.hidden = false;
    sel.innerHTML = '<option value="">Lista principal</option>';
    subs.forEach((s) => {
      const o = document.createElement('option');
      o.value = s;
      o.textContent = s;
      sel.appendChild(o);
    });
  } catch {}
}

/* ---------- Auto-play ---------- */
async function toggleAuto() {
  try {
    const r = await (await fetch('/api/autoplay/toggle', { method: 'POST' })).json();
    setToggle(r.status === 'active');
  } catch {}
}

function setToggle(active) {
  const b = $('btn-toggle');
  b.textContent = active ? '■ Parar' : '▶ Iniciar';
  b.classList.toggle('btn-go', !active);
  b.classList.toggle('btn-stop', active);
}

async function resetWords() {
  try {
    const response = await fetch('/api/reset', { method: 'POST' });
    if (!response.ok) throw new Error('reset failed');
    // Limpa as logs na tela (prompt + aprendidas + OCR ambíguo). Os high-water-marks de id
    // continuam altos, então entradas antigas do backend não voltam a aparecer.
    const lg = $('log'); if (lg) lg.innerHTML = '';
    const ll = $('learned-log'); if (ll) ll.innerHTML = '';
    const al = $('ambiguous-log'); if (al) al.innerHTML = '';  // ambíguo zera junto com o reset
    log('Palavras usadas resetadas');
    showNotice('reset-notice', 'Partida reiniciada. As palavras usadas foram esquecidas.');
  } catch {}
}

function exportMissing() {
  // Content-Disposition: attachment → o navegador baixa sem sair da página.
  window.location.href = '/api/missing_prompts/export';
}

async function clearMissing() {
  try {
    await fetch('/api/missing_prompts/clear', { method: 'POST' });
    const ml = $('missing-log'); if (ml) ml.innerHTML = '';
    log('Lista de prompts sem palavra limpa');
  } catch {}
}

function exportAmbiguous() {
  window.location.href = '/api/ambiguous_words/export';
}

/* ---------- Reroll (navegação manual de sugestões) ---------- */
async function rerollNext() {
  try { applyReroll(await (await fetch('/api/reroll/next', { method: 'POST' })).json()); } catch {}
}
async function rerollPrev() {
  try { applyReroll(await (await fetch('/api/reroll/prev', { method: 'POST' })).json()); } catch {}
}
function applyReroll(r) {
  if (!r) return;
  if (r.word) {
    renderWord(r.word, currentPrompt);
  }
  updateSuggestionCount(r.index, r.total);
}

async function rerollShort() {
  try {
    const response = await fetch('/api/reroll/short', { method: 'POST' });
    if (!response.ok) throw new Error('short reroll failed');
    applyReroll(await response.json());
  } catch {
    showNotice('ocr-notice', 'Não foi possível buscar uma alternativa curta.', true);
  }
}

async function rejectWord() {
  try {
    const response = await fetch('/api/word/reject', { method: 'POST' });
    if (!response.ok) throw new Error('reject failed');
    const result = await response.json();
    applyReroll(result);
    if (result.rejected) showNotice('ocr-notice', `${String(result.rejected).toUpperCase()} foi removida do dicionário.`);
    if (!result.word) renderWord('', currentPrompt);
  } catch {
    showNotice('ocr-notice', 'Não foi possível rejeitar esta sugestão.', true);
  }
}

async function correctPrompt(event) {
  event.preventDefault();
  const input = $('corrected-prompt');
  const prompt = input.value.trim();
  if (!prompt) return;
  try {
    const response = await fetch('/api/prompt/correct', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt }),
    });
    if (!response.ok) throw new Error('prompt correction failed');
    const result = await response.json();
    currentPrompt = result.prompt || prompt;
    if (result.word || result.suggested_word) renderWord(result.word || result.suggested_word, currentPrompt);
    updateSuggestionCount(result.index ?? result.suggestion_index, result.total ?? result.suggestion_total);
    showNotice('ocr-notice', 'Sílaba corrigida.', false);
  } catch {
    showNotice('ocr-notice', 'Não foi possível corrigir a sílaba.', true);
  }
}

function toggleCompact() {
  const compact = !document.body.classList.contains('compact');
  document.body.classList.toggle('compact', compact);
  localStorage.setItem('wordbomb-compact', compact ? '1' : '0');
  $('btn-compact').setAttribute('aria-pressed', String(compact));
}

function openFloatingWindow() {
  const popup = window.open('/?compact=1', 'wordbomb-helper-floating', 'popup=yes,width=460,height=560,resizable=yes');
  if (!popup) showNotice('reset-notice', 'O navegador bloqueou a janela flutuante.', true);
}

function restoreCompactMode() {
  const compact = new URLSearchParams(window.location.search).get('compact') === '1'
    || localStorage.getItem('wordbomb-compact') === '1';
  document.body.classList.toggle('compact', compact);
  $('btn-compact').setAttribute('aria-pressed', String(compact));
}
function updateSuggestionCount(idx, tot) {
  const el = $('suggestion-count');
  const bar = $('reroll-bar');
  if (!el || !bar) return;
  if (tot > 0) { el.textContent = `Sugestão ${idx} / ${tot}`; bar.hidden = false; }
  else { el.textContent = ''; bar.hidden = true; }
}

function updatePromptCoverage(prompt, total) {
  const el = $('prompt-coverage');
  if (!el) return;
  const count = Math.max(0, Number(total) || 0);
  const visible = Boolean(prompt);
  el.hidden = !visible;
  el.classList.toggle('is-empty', visible && count === 0);
  el.classList.toggle('is-rare', visible && count > 0 && count <= 5);
  el.textContent = visible ? `${count} ${count === 1 ? 'resposta' : 'respostas'}` : '';
}

/* ---------- Calibração ---------- */
async function calibrate(target) {
  try {
    const r = await (await fetch('/api/calibration/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: target || 'turn' }),
    })).json();
    if (r.status === 'started') showOverlay((r.message || 'Clique no canto superior-esquerdo') + ' — se o clique não for detectado, posicione o cursor e aperte F8.');
  } catch {}
}
function showOverlay(msg) { $('overlay-text').textContent = msg; $('overlay').hidden = false; }
function hideOverlay() { $('overlay').hidden = true; }
$('overlay') && $('overlay').addEventListener('click', hideOverlay);
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hideOverlay(); });

/* ---------- SSE — atualização em tempo real de palavra/preview/status ---------- */
let _sseActive = false;
let currentPrompt = '';

function initSSE() {
  const sse = new EventSource('/api/stream');
  sse.onopen = () => { _sseActive = true; };
  sse.onmessage = (e) => {
    _sseActive = true;
    try { applyRealtimeUpdate(JSON.parse(e.data)); } catch {}
  };
  sse.onerror = () => {
    _sseActive = false;
    // reconecta automaticamente — EventSource faz isso por padrão
  };
}

function applyRealtimeUpdate(s) {
  // Status dot
  const dot = $('dot');
  const st = s.status || (s.watching ? 'Watching' : 'Idle');
  dot.className = st === 'Watching' ? 'dot-watch' : st === 'Calibrating' ? 'dot-calib' : 'dot-idle';
  $('status-text').textContent = st === 'Watching' ? 'Observando' : st === 'Calibrating' ? 'Calibrando' : 'Parado';

  // Botão toggle
  setToggle(!!(s.is_watching ?? s.watching));

  // Palavra / sílaba
  const word = $('word');
  const promptLine = $('prompt-line');
  const suggestedWord = s.suggested_word || s.word || '';
  const preview = s.preview_prompt || s.preview || '';
  const watching = !!(s.is_watching ?? s.watching);
  currentPrompt = preview;
  if (suggestedWord) {
    renderWord(suggestedWord, preview);
    promptLine.textContent = preview ? 'sílaba ' + preview.toUpperCase() : '';
  } else if (preview && watching) {
    renderWord('…', '');
    promptLine.textContent = 'sílaba ' + preview.toUpperCase();
  } else {
    renderWord('—', '');
    promptLine.textContent = watching ? 'aguardando sua vez' : '';
  }

  // Contador de sugestões (Reroll). SSE usa sidx/stot; o poll usa suggestion_index/total.
  const suggestionTotal = s.stot ?? s.suggestion_total ?? 0;
  updateSuggestionCount(s.sidx ?? s.suggestion_index ?? 0, suggestionTotal);
  updatePromptCoverage(preview, suggestionTotal);
  updateSuggestionActions(suggestedWord, s);
  // SSE transporta só o estado do turno. Os metadados de diagnóstico chegam no poll.
  if ('ocr_uncertain' in s) updateOcrState(s, preview);
  if ('recover_progress' in s) updateRecoverProgress(s);
  if ('reset_notice' in s) updateResetNotice(s);
  if ('action_notice' in s) updateActionNotice(s);
}

function renderWord(value, prompt) {
  const word = $('word');
  const display = String(value || '').toUpperCase();
  const needle = String(prompt || '').toUpperCase();
  word.replaceChildren();
  const index = needle ? display.indexOf(needle) : -1;
  if (index < 0) {
    word.textContent = display || '—';
  } else {
    word.append(document.createTextNode(display.slice(0, index)));
    const highlight = document.createElement('mark');
    highlight.textContent = display.slice(index, index + needle.length);
    word.append(highlight, document.createTextNode(display.slice(index + needle.length)));
  }
  word.classList.toggle('live', Boolean(value) && value !== '…' && value !== '—');
}

function updateSuggestionActions(suggestedWord, state) {
  const actions = $('suggestion-actions');
  if (!actions) return;
  actions.hidden = !suggestedWord;
  // O endpoint pode estar em rollout: só habilita a alternativa curta quando o status a confirmar.
  const shortAvailable = state.short_reroll_available ?? state.can_reroll_short ?? true;
  $('btn-short').hidden = shortAvailable === false;
}

function updateOcrState(state, prompt) {
  const ocr = state.ocr_uncertain;
  const uncertain = ocr && typeof ocr === 'object' && ocr.uncertain === true;
  if (uncertain) {
    const confidence = ocr.confidence;
    const suffix = Number.isFinite(Number(confidence)) ? ` (${Math.round(Number(confidence))}% de confiança)` : '';
    const candidate = ocr.candidate ? `: ${ocr.candidate}` : '';
    showNotice('ocr-notice', `Leitura OCR incerta${candidate}${suffix}. Confira ou corrija a sílaba.`, true);
  } else {
    hideNotice('ocr-notice');
  }
  const form = $('prompt-correction');
  form.hidden = !prompt && !uncertain;
  if (!form.hidden && document.activeElement !== $('corrected-prompt')) $('corrected-prompt').value = prompt || '';
}

function updateRecoverProgress(state) {
  const el = $('recover-progress');
  const tracker = $('recover-tracker');
  const letters = $('recover-letters');
  const meta = $('recover-tracker-meta');
  const progress = state.recover_progress;
  if (!progress || typeof progress !== 'object') {
    el.hidden = true;
    tracker.hidden = true;
    return;
  }
  const parts = [];
  if (progress.mode) parts.push(`Modo: ${progress.mode}`);
  if (progress.cycle != null) parts.push(`Ciclo: ${progress.cycle}`);
  if (progress.target != null) parts.push(`Alvo: ${progress.target}`);
  if (progress.remaining != null) {
    const remaining = typeof progress.remaining === 'object'
      ? Object.entries(progress.remaining).map(([letter, amount]) => `${letter.toUpperCase()}: ${amount}`).join(', ')
      : progress.remaining;
    parts.push(`Restam: ${remaining}`);
  }
  if (!parts.length) { el.hidden = true; return; }
  el.textContent = parts.join(' · ');
  el.hidden = false;

  const remaining = progress.remaining && typeof progress.remaining === 'object'
    ? Object.entries(progress.remaining).filter(([, amount]) => Number(amount) > 0)
    : [];
  letters.replaceChildren();
  for (const [letter, amountValue] of remaining) {
    const amount = Number(amountValue);
    const chip = document.createElement('span');
    chip.className = 'recover-letter';
    chip.setAttribute('role', 'listitem');
    chip.setAttribute('aria-label', `${letter.toUpperCase()}, falta ${amount} vez${amount === 1 ? '' : 'es'}`);
    chip.textContent = letter.toUpperCase();
    if (amount > 1) {
      const count = document.createElement('small');
      count.textContent = `×${amount}`;
      chip.appendChild(count);
    }
    letters.appendChild(chip);
  }
  const lengthHint = progress.fast_strategic
    ? ' · rápido estratégico'
    : progress.preferred_max_length == null
      ? ''
      : ` · prefere até ${progress.preferred_max_length} letras`;
  meta.textContent = `Ciclo ${progress.cycle ?? 1} · ${progress.target ?? 1}× cada${lengthHint}`;
  tracker.classList.toggle('is-complete', remaining.length === 0);
  if (!remaining.length) {
    const complete = document.createElement('span');
    complete.className = 'recover-complete';
    complete.textContent = 'Ciclo completo';
    letters.appendChild(complete);
  }
  tracker.hidden = false;
}

function updateResetNotice(state) {
  const message = state.reset_notification ?? state.reset_notice;
  if (message) showNotice('reset-notice', String(message));
}

function updateActionNotice(state) {
  if (state.action_notice) showNotice('ocr-notice', String(state.action_notice));
}

function updateMatchSummary(state) {
  const summary = state.match_summary;
  const target = $('match-summary');
  if (!target || !summary) return;
  const values = [
    ['Jogadas', summary.confirmed_words],
    ['Aprendidas', summary.learned_words],
    ['Rejeitadas', summary.rejections],
    ['Sílabas sem palavra', summary.missing_prompts],
  ];
  target.replaceChildren(...values.map(([label, value]) => {
    const item = document.createElement('div');
    const number = document.createElement('strong');
    const caption = document.createElement('span');
    number.textContent = String(value || 0);
    caption.textContent = label;
    item.append(number, caption);
    return item;
  }));
  const previous = state.last_match_summary;
  const last = $('last-match-summary');
  if (last && previous) {
    last.textContent = `Última partida: ${previous.confirmed_words || 0} jogadas, ${previous.learned_words || 0} aprendidas e ${previous.rejections || 0} rejeitadas.`;
    last.hidden = false;
  }
}

function showNotice(id, message, warning = false) {
  const el = $(id);
  if (!el) return;
  el.textContent = message;
  el.classList.toggle('notice-warning', warning);
  el.hidden = false;
}

function hideNotice(id) { const el = $(id); if (el) el.hidden = true; }

/* ---------- Dicionário pessoal ---------- */
let dictionaryImportReady = false;

function bindDictionary() {
  $('dictionary-add-form').addEventListener('submit', addDictionaryWord);
  $('dictionary-import-form').addEventListener('submit', previewDictionaryImport);
  $('dictionary-apply-import').addEventListener('click', applyDictionaryImport);
  $('dictionary-undo').addEventListener('click', undoDictionaryChange);
}

async function dictionaryRequest(path, body) {
  const response = await fetch(path, body === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.message || 'Não foi possível alterar o dicionário.');
  return data;
}

async function loadDictionary() {
  const language = $('dictionary-language');
  if (language) language.textContent = cfg.lang;
  const list = $('dictionary-list');
  if (!list) return;
  try {
    const response = await fetch('/api/dictionary?lang=' + encodeURIComponent(cfg.lang));
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || 'Não foi possível carregar o dicionário.');
    renderDictionaryWords(Array.isArray(data) ? data : data.words || []);
  } catch (error) {
    renderDictionaryWords([]);
    dictionaryMessage(error.message, true);
  }
}

function renderDictionaryWords(words) {
  const list = $('dictionary-list');
  list.replaceChildren();
  if (!words.length) {
    const empty = document.createElement('p');
    empty.className = 'field-help';
    empty.textContent = 'Nenhuma palavra pessoal neste idioma.';
    list.append(empty);
    return;
  }
  words.forEach((word) => {
    const row = document.createElement('div');
    row.className = 'dictionary-row';
    const input = document.createElement('input');
    input.value = String(word);
    input.setAttribute('aria-label', `Editar ${word}`);
    const save = document.createElement('button');
    save.type = 'button'; save.className = 'btn-mini'; save.textContent = 'Salvar';
    save.addEventListener('click', () => editDictionaryWord(String(word), input.value));
    const remove = document.createElement('button');
    remove.type = 'button'; remove.className = 'btn-mini btn-reject'; remove.textContent = 'Excluir';
    remove.addEventListener('click', () => deleteDictionaryWord(String(word)));
    row.append(input, save, remove);
    list.append(row);
  });
}

function dictionaryMessage(message, warning = false) {
  const el = $('dictionary-message');
  el.textContent = message || '';
  el.classList.toggle('notice-warning', warning);
}

async function addDictionaryWord(event) {
  event.preventDefault();
  const input = $('dictionary-word');
  const word = input.value.trim();
  if (!word) return;
  try {
    const result = await dictionaryRequest('/api/dictionary/add', { lang: cfg.lang, word });
    input.value = '';
    dictionaryMessage(result.message || dictionarySummary(result) || 'Palavra adicionada.');
    await loadDictionary();
  } catch (error) { dictionaryMessage(error.message, true); }
}

async function editDictionaryWord(oldWord, newWord) {
  const normalized = newWord.trim();
  if (!normalized || normalized === oldWord) return;
  try {
    const result = await dictionaryRequest('/api/dictionary/edit', { lang: cfg.lang, old_word: oldWord, new_word: normalized });
    dictionaryMessage(result.message || 'Palavra atualizada.');
    await loadDictionary();
  } catch (error) { dictionaryMessage(error.message, true); }
}

async function deleteDictionaryWord(word) {
  try {
    const result = await dictionaryRequest('/api/dictionary/delete', { lang: cfg.lang, word });
    dictionaryMessage(result.message || 'Palavra excluída.');
    await loadDictionary();
  } catch (error) { dictionaryMessage(error.message, true); }
}

async function previewDictionaryImport(event) {
  event.preventDefault();
  const text = $('dictionary-import-text').value;
  try {
    const result = await dictionaryRequest('/api/dictionary/preview-import', { lang: cfg.lang, text });
    dictionaryImportReady = true;
    $('dictionary-apply-import').disabled = false;
    dictionaryMessage(result.message || dictionarySummary(result));
  } catch (error) {
    dictionaryImportReady = false;
    $('dictionary-apply-import').disabled = true;
    dictionaryMessage(error.message, true);
  }
}

async function applyDictionaryImport() {
  if (!dictionaryImportReady) return;
  try {
    const result = await dictionaryRequest('/api/dictionary/apply-import', {
      lang: cfg.lang, text: $('dictionary-import-text').value,
    });
    dictionaryImportReady = false;
    $('dictionary-apply-import').disabled = true;
    dictionaryMessage(result.message || dictionarySummary(result) || 'Importação aplicada.');
    await loadDictionary();
  } catch (error) { dictionaryMessage(error.message, true); }
}

async function undoDictionaryChange() {
  try {
    const result = await dictionaryRequest('/api/dictionary/undo', { lang: cfg.lang });
    dictionaryMessage(result.message || 'Última alteração desfeita.');
    await loadDictionary();
  } catch (error) { dictionaryMessage(error.message, true); }
}

function dictionarySummary(result) {
  const parts = [];
  for (const key of ['new_words', 'duplicates', 'invalid_lines', 'added']) {
    const value = result[key];
    if (Array.isArray(value)) parts.push(`${key.replace('_', ' ')}: ${value.length}`);
    else if (typeof value === 'number') parts.push(`${key.replace('_', ' ')}: ${value}`);
  }
  return parts.join(' · ');
}

/* ---------- Diagnóstico OCR e perfis de calibração ---------- */
function bindDiagnostics() {
  $('ocr-preview-refresh').addEventListener('click', loadOcrPreview);
  $('ocr-replay').addEventListener('click', replayOcr);
  $('profile-save-form').addEventListener('submit', saveCalibrationProfile);
  $('diagnostics-panel').addEventListener('toggle', () => {
    if ($('diagnostics-panel').open) { loadOcrPreview(); loadCalibrationProfiles(); }
  });
}

async function loadOcrPreview() {
  const image = $('ocr-preview');
  const result = $('ocr-diagnostic-result');
  image.hidden = true;
  try {
    const response = await fetch('/api/ocr/preview?ts=' + Date.now(), { cache: 'no-store' });
    if (!response.ok) throw new Error('Ainda não há uma imagem OCR disponível.');
    const blob = await response.blob();
    if (!blob.type.startsWith('image/')) throw new Error('A pré-visualização OCR não é uma imagem válida.');
    if (image.dataset.objectUrl) URL.revokeObjectURL(image.dataset.objectUrl);
    image.dataset.objectUrl = URL.createObjectURL(blob);
    image.src = image.dataset.objectUrl;
    image.alt = 'Pré-visualização da última imagem processada pelo OCR.';
    image.hidden = false;
  } catch (error) {
    image.removeAttribute('src');
    result.textContent = error.message;
  }
}

async function replayOcr() {
  const result = $('ocr-diagnostic-result');
  try {
    const data = await dictionaryRequest('/api/ocr/replay', {});
    result.textContent = data.message || ocrReplaySummary(data) || 'Leitura reprocessada.';
    await loadOcrPreview();
  } catch (error) { result.textContent = error.message; }
}

function ocrReplaySummary(data) {
  const parts = [];
  if (data.prompt) parts.push(`Sílaba: ${data.prompt}`);
  if (data.candidate) parts.push(`Leitura: ${data.candidate}`);
  if (data.confidence != null) parts.push(`Confiança: ${Math.round(Number(data.confidence))}%`);
  return parts.join(' · ');
}

async function loadCalibrationProfiles() {
  const list = $('profile-list');
  try {
    const response = await fetch('/api/calibration/profiles');
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || 'Não foi possível carregar os perfis.');
    renderCalibrationProfiles(Array.isArray(data) ? data : data.profiles || []);
  } catch (error) { profileMessage(error.message, true); }
}

function renderCalibrationProfiles(profiles) {
  const list = $('profile-list');
  list.replaceChildren();
  if (!profiles.length) {
    const empty = document.createElement('p');
    empty.className = 'field-help'; empty.textContent = 'Nenhum perfil salvo.';
    list.append(empty); return;
  }
  profiles.forEach((profile) => {
    const row = document.createElement('div'); row.className = 'profile-row';
    const name = document.createElement('span');
    name.textContent = `${profile.name || 'Sem nome'}${profile.active ? ' (ativo)' : ''}`;
    const activate = document.createElement('button');
    activate.type = 'button'; activate.className = 'btn-mini'; activate.textContent = profile.active ? 'Ativo' : 'Ativar';
    activate.disabled = Boolean(profile.active);
    activate.addEventListener('click', () => activateCalibrationProfile(profile.id));
    const remove = document.createElement('button');
    remove.type = 'button'; remove.className = 'btn-mini btn-reject'; remove.textContent = 'Excluir';
    remove.addEventListener('click', () => deleteCalibrationProfile(profile.id));
    row.append(name, activate, remove); list.append(row);
  });
}

function profileMessage(message, warning = false) {
  const el = $('profile-message'); el.textContent = message || ''; el.classList.toggle('notice-warning', warning);
}

async function saveCalibrationProfile(event) {
  event.preventDefault();
  const input = $('profile-name'); const name = input.value.trim();
  if (!name) return;
  try {
    const data = await dictionaryRequest('/api/calibration/profiles/save', { name });
    input.value = ''; profileMessage(data.message || 'Perfil salvo.'); await loadCalibrationProfiles();
  } catch (error) { profileMessage(error.message, true); }
}

async function activateCalibrationProfile(id) {
  try {
    const data = await dictionaryRequest('/api/calibration/profiles/activate', { id });
    profileMessage(data.message || 'Perfil ativado.'); await loadCalibrationProfiles();
  } catch (error) { profileMessage(error.message, true); }
}

async function deleteCalibrationProfile(id) {
  try {
    const response = await fetch('/api/calibration/profiles/' + encodeURIComponent(id), { method: 'DELETE' });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.message || 'Não foi possível excluir o perfil.');
    profileMessage(data.message || 'Perfil excluído.'); await loadCalibrationProfiles();
  } catch (error) { profileMessage(error.message, true); }
}

/* ---------- Treino offline ---------- */
let practiceStartedAt = 0;

function bindPractice() {
  $('practice-new').addEventListener('click', newPracticeRound);
  $('practice-check-form').addEventListener('submit', checkPracticeAnswer);
  $('practice-hints').addEventListener('click', (event) => {
    const button = event.target.closest('button[data-hint]');
    if (button) requestPracticeHint(button.dataset.hint);
  });
}

function currentPracticeMode() {
  return document.querySelector('input[name="practice-mode"]:checked').value;
}

async function newPracticeRound() {
  try {
    const data = await dictionaryRequest('/api/practice/new', { lang: cfg.lang, mode: currentPracticeMode() });
    const prompt = data.prompt || data.syllable || data.challenge || '';
    $('practice-round').hidden = !prompt;
    $('practice-prompt').textContent = prompt ? `Sílaba: ${String(prompt).toUpperCase()}` : '';
    $('practice-answer').value = '';
    $('practice-hints').hidden = currentPracticeMode() !== 'hints';
    $('practice-result').textContent = data.message || (prompt ? 'Rodada iniciada.' : 'Não há rodada disponível.');
    practiceStartedAt = Date.now();
    if (prompt) $('practice-answer').focus();
  } catch (error) { $('practice-result').textContent = error.message; }
}

async function checkPracticeAnswer(event) {
  event.preventDefault();
  const answer = $('practice-answer').value.trim();
  if (!answer || !practiceStartedAt) return;
  try {
    const data = await dictionaryRequest('/api/practice/check', {
      answer, elapsed_seconds: Math.max(0, Math.round((Date.now() - practiceStartedAt) / 1000)),
    });
    const reasons = {
      empty_answer: 'Digite uma palavra.',
      missing_prompt: 'A palavra precisa conter a sílaba mostrada.',
      not_in_dictionary: 'Essa palavra não está no dicionário ativo.',
      correct: 'Correto.',
    };
    const outcome = data.message || reasons[data.reason] || (data.correct === true ? 'Correto.' : 'Resposta conferida.');
    $('practice-result').textContent = outcome;
    practiceStartedAt = 0;
  } catch (error) { $('practice-result').textContent = error.message; }
}

async function requestPracticeHint(kind) {
  try {
    const data = await dictionaryRequest('/api/practice/hint', { kind });
    const labels = { length: 'Tamanho', first_letter: 'Primeira letra', answer: 'Resposta' };
    const hint = data.value != null ? `${labels[data.mode] || 'Dica'}: ${data.value}` : '';
    $('practice-result').textContent = data.message || hint || 'Dica indisponível.';
  } catch (error) { $('practice-result').textContent = error.message; }
}

/* ---------- Polling periódico — logs + calibração + fallback se SSE falhar ---------- */
let lastLogId = 0;
let lastLearnedId = 0;
let wasCalibrating = false;

async function poll() {
  let s;
  try { s = await (await fetch('/api/autoplay/status')).json(); } catch { return; }

  // Fallback: atualiza palavra/status se SSE não estiver ativo
  if (!_sseActive) applyRealtimeUpdate(s);
  // SSE é propositalmente enxuto; estes estados só chegam na resposta completa.
  updateOcrState(s, s.preview_prompt || s.preview || '');
  updateRecoverProgress(s);
  updateResetNotice(s);
  updateActionNotice(s);
  updateMatchSummary(s);

  // Overlay de calibração (infrequente, 1s de lag é aceitável)
  if (s.status === 'Calibrating') {
    wasCalibrating = true;
    const step = s.calibration_step;
    const alvo = s.calib_target === 'solve' ? 'painel SOLVE' : 'prompt + SUA VEZ';
    showOverlay(step === 'turn_start' ? `Clique no canto SUPERIOR-ESQUERDO (${alvo}) ou posicione o cursor e aperte F8`
              : step === 'turn_end' ? 'Clique no canto INFERIOR-DIREITO ou posicione o cursor e aperte F8'
              : 'Clique para calibrar');
  } else if (wasCalibrating) {
    wasCalibrating = false;
    hideOverlay();
    log('Calibração concluída');
  }

  // Badge do Pipeline B (palavras aprendidas dos outros jogadores)
  const badge = $('learned-badge');
  if (badge) {
    if (s.solve_region_set) badge.textContent = `🧠 ${s.learned_words || 0} aprendidas`;
    else badge.textContent = '';
  }

  // Logs (menos urgentes — 1s de lag OK)
  if (s.logs) {
    s.logs.forEach((e) => {
      const id = typeof e === 'object' ? e.id : 0;
      const msg = typeof e === 'object' ? e.msg : e;
      if (id > lastLogId) { log(msg); lastLogId = id; }
    });
  }

  // Log de palavras aprendidas (Pipeline B) — incremental por id
  if (s.learned_log) {
    s.learned_log.forEach((e) => {
      if (e.id > lastLearnedId) { learnedLog((e.word || '').toUpperCase()); lastLearnedId = e.id; }
    });
  }

  // Prompts sem palavra (manutenção do dicionário) — snapshot ordenado, persiste entre runs.
  // NÃO é limpo pelo Reset (é dado de manutenção).
  const ml = $('missing-log');
  if (ml && s.missing_prompts) {
    ml.innerHTML = '';
    s.missing_prompts.forEach((m) => {
      const line = document.createElement('div');
      line.textContent = `${(m.prompt || '').toUpperCase()}  ×${m.count}`;
      ml.appendChild(line);
    });
  }

  // OCR ambíguo não marcado (manutenção) — snapshot ordenado, persiste. Não limpo pelo Reset.
  const al = $('ambiguous-log');
  if (al && s.ambiguous_words) {
    al.innerHTML = '';
    s.ambiguous_words.forEach((m) => {
      const line = document.createElement('div');
      line.textContent = `${(m.prompt || '').toUpperCase()}  ×${m.count}`;
      al.appendChild(line);
    });
  }
}

function learnedLog(word) {
  const box = $('learned-log');
  if (!box) return;
  const line = document.createElement('div');
  const t = new Date().toLocaleTimeString('pt-BR', { hour12: false });
  line.textContent = `${t}  ${word}`;
  box.prepend(line);
  while (box.childElementCount > 40) box.removeChild(box.lastChild);
}

function log(msg) {
  const box = $('log');
  const line = document.createElement('div');
  const t = new Date().toLocaleTimeString('pt-BR', { hour12: false });
  line.textContent = `${t}  ${msg}`;
  box.prepend(line);
  while (box.childElementCount > 40) box.removeChild(box.lastChild);
}
