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
  recover_target: 2,
  recover_exclude: '',
  auto_type: false,   // fixo: nunca digita sozinho
};

const $ = (id) => document.getElementById(id);

document.addEventListener('DOMContentLoaded', async () => {
  await fetchLanguages();
  bindInputs();
  syncRecoverVisibility();
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
  const num = { 'f-min': 'min_len', 'f-max': 'max_len', 'r-target': 'recover_target' };
  for (const [id, key] of Object.entries(num)) {
    $(id).addEventListener('change', (e) => { cfg[key] = parseInt(e.target.value) || cfg[key]; syncConfig(); });
  }
  $('strategy').addEventListener('change', (e) => {
    cfg.strategy = e.target.value;
    syncRecoverVisibility();
    syncConfig();
  });
  $('sublist').addEventListener('change', (e) => { cfg.priority_sublist = e.target.value; syncConfig(); });
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
  document.querySelectorAll('.lang').forEach((b) => b.classList.toggle('on', b.textContent === lang));
  fetchSublists(lang);
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
    await fetch('/api/reset', { method: 'POST' });
    // Limpa as DUAS logs na tela (prompt + aprendidas). Os high-water-marks de id
    // continuam altos, então entradas antigas do backend não voltam a aparecer.
    const lg = $('log'); if (lg) lg.innerHTML = '';
    const ll = $('learned-log'); if (ll) ll.innerHTML = '';
    log('Palavras usadas resetadas');
  } catch {}
}

function exportMissing() {
  // Content-Disposition: attachment → o navegador baixa sem sair da página.
  window.location.href = '/api/missing_prompts/export';
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
    const w = $('word');
    w.textContent = r.word.toUpperCase();
    w.classList.add('live');
  }
  updateSuggestionCount(r.index, r.total);
}
function updateSuggestionCount(idx, tot) {
  const el = $('suggestion-count');
  const bar = $('reroll-bar');
  if (!el || !bar) return;
  if (tot > 0) { el.textContent = `Sugestão ${idx} / ${tot}`; bar.hidden = false; }
  else { el.textContent = ''; bar.hidden = true; }
}

/* ---------- Calibração ---------- */
async function calibrate(target) {
  try {
    const r = await (await fetch('/api/calibration/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: target || 'turn' }),
    })).json();
    if (r.status === 'started') showOverlay(r.message || 'Clique no canto superior-esquerdo');
  } catch {}
}
function showOverlay(msg) { $('overlay-text').textContent = msg; $('overlay').hidden = false; }
function hideOverlay() { $('overlay').hidden = true; }
$('overlay') && $('overlay').addEventListener('click', hideOverlay);
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hideOverlay(); });

/* ---------- SSE — atualização em tempo real de palavra/preview/status ---------- */
let _sseActive = false;

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
  if (suggestedWord) {
    word.textContent = suggestedWord.toUpperCase();
    word.classList.add('live');
    promptLine.textContent = preview ? 'sílaba ' + preview.toUpperCase() : '';
  } else if (preview && watching) {
    word.textContent = '…';
    word.classList.remove('live');
    promptLine.textContent = 'sílaba ' + preview.toUpperCase();
  } else {
    word.textContent = '—';
    word.classList.remove('live');
    promptLine.textContent = watching ? 'aguardando sua vez' : '';
  }

  // Contador de sugestões (Reroll). SSE usa sidx/stot; o poll usa suggestion_index/total.
  updateSuggestionCount(s.sidx ?? s.suggestion_index ?? 0, s.stot ?? s.suggestion_total ?? 0);
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

  // Overlay de calibração (infrequente, 1s de lag é aceitável)
  if (s.status === 'Calibrating') {
    wasCalibrating = true;
    const step = s.calibration_step;
    const alvo = s.calib_target === 'solve' ? 'painel SOLVE' : 'prompt + SUA VEZ';
    showOverlay(step === 'turn_start' ? `Clique no canto SUPERIOR-ESQUERDO (${alvo})`
              : step === 'turn_end' ? 'Clique no canto INFERIOR-DIREITO'
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
