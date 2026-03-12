import './styles.css';

const AGENT_ORDER = [
  ['Analyst Team', 'Market Analyst'],
  ['Analyst Team', 'Social Analyst'],
  ['Analyst Team', 'News Analyst'],
  ['Analyst Team', 'Fundamentals Analyst'],
  ['Research Team', 'Bull Researcher'],
  ['Research Team', 'Bear Researcher'],
  ['Research Team', 'Research Manager'],
  ['Trading Team', 'Trader'],
  ['Risk Management', 'Aggressive Analyst'],
  ['Risk Management', 'Neutral Analyst'],
  ['Risk Management', 'Conservative Analyst'],
  ['Portfolio Management', 'Portfolio Manager'],
];

const agentState = new Map(AGENT_ORDER.map(([team, agent]) => [agent, { team, status: 'pending' }]));

const els = {
  messages: document.getElementById('messages'),
  events: document.getElementById('events'),
  form: document.getElementById('chatForm'),
  prompt: document.getElementById('prompt'),
  sendBtn: document.getElementById('sendBtn'),
  apiBase: document.getElementById('apiBase'),
  dryRun: document.getElementById('dryRun'),
  clearEvents: document.getElementById('clearEvents'),
  connDot: document.getElementById('connDot'),
  agentBoard: document.getElementById('agentBoard'),
  klineCanvas: document.getElementById('klineCanvas'),
  chartTitle: document.getElementById('chartTitle'),
};

function resetAgents() {
  for (const [team, agent] of AGENT_ORDER) {
    agentState.set(agent, { team, status: 'pending' });
  }
  renderAgentBoard();
}

function renderAgentBoard() {
  const html = AGENT_ORDER.map(([, agent]) => {
    const item = agentState.get(agent) || { team: '-', status: 'pending' };
    return `
      <article class="agent-card">
        <div class="agent-name">${escapeHtml(agent)}</div>
        <div class="agent-team">${escapeHtml(item.team)}</div>
        <div class="agent-status ${escapeHtml(item.status)}">${escapeHtml(item.status)}</div>
      </article>
    `;
  }).join('');
  els.agentBoard.innerHTML = html;
}

function resizeCanvas() {
  const canvas = els.klineCanvas;
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * dpr));
  canvas.height = Math.max(1, Math.floor(rect.height * dpr));
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function buildCandles(seedText, count = 72) {
  let seed = 0;
  for (const ch of seedText) seed = (seed * 31 + ch.charCodeAt(0)) >>> 0;
  const rnd = () => {
    seed = (1664525 * seed + 1013904223) >>> 0;
    return seed / 0xffffffff;
  };
  const out = [];
  let close = 100 + rnd() * 40;
  for (let i = 0; i < count; i++) {
    const drift = (rnd() - 0.48) * 3.6;
    const open = close;
    close = Math.max(8, open + drift);
    const high = Math.max(open, close) + rnd() * 2.2;
    const low = Math.min(open, close) - rnd() * 2.2;
    out.push({ open, high, low, close });
  }
  return out;
}

function drawKline(symbol = '600519.SH') {
  const canvas = els.klineCanvas;
  if (!canvas) return;
  resizeCanvas();
  const ctx = canvas.getContext('2d');
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  if (w < 2 || h < 2) return;

  ctx.clearRect(0, 0, w, h);

  const bg = ctx.createLinearGradient(0, 0, 0, h);
  bg.addColorStop(0, '#fbfdff');
  bg.addColorStop(1, '#f3f8fd');
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, w, h);

  ctx.strokeStyle = '#dde7f0';
  ctx.lineWidth = 1;
  for (let i = 1; i < 6; i++) {
    const y = (h / 6) * i;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }
  for (let i = 1; i < 12; i++) {
    const x = (w / 12) * i;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }

  const candles = buildCandles(symbol, Math.max(48, Math.floor(w / 13)));
  drawCandles(candles, ctx, w, h);
}

function drawCandles(candles, ctx, w, h) {
  if (!candles || !candles.length) return;
  const max = Math.max(...candles.map(c => c.high)) * 1.02;
  const min = Math.min(...candles.map(c => c.low)) * 0.98;
  const toY = (v) => ((max - v) / (max - min)) * (h - 20) + 10;
  const step = w / candles.length;
  const bodyW = Math.max(3, step * 0.58);

  for (let i = 0; i < candles.length; i++) {
    const c = candles[i];
    const x = i * step + (step - bodyW) / 2;
    const yOpen = toY(c.open);
    const yClose = toY(c.close);
    const yHigh = toY(c.high);
    const yLow = toY(c.low);
    const up = c.close >= c.open;
    const color = up ? '#10a37f' : '#ef4444';

    ctx.strokeStyle = color;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(x + bodyW / 2, yHigh);
    ctx.lineTo(x + bodyW / 2, yLow);
    ctx.stroke();

    ctx.fillStyle = color;
    const by = Math.min(yOpen, yClose);
    const bh = Math.max(1.5, Math.abs(yClose - yOpen));
    ctx.fillRect(x, by, bodyW, bh);
  }

  ctx.strokeStyle = '#bdd0e3';
  ctx.strokeRect(0.5, 0.5, w - 1, h - 1);
}

async function fetchKline(apiBase, symbol) {
  const end = new Date();
  const start = new Date(end.getTime() - 120 * 24 * 3600 * 1000);
  const fmt = (d) => d.toISOString().slice(0, 10);
  const url = `${apiBase}/v1/market/kline?symbol=${encodeURIComponent(symbol)}&start_date=${fmt(start)}&end_date=${fmt(end)}`;
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`kline ${resp.status}`);
  const data = await resp.json();
  return Array.isArray(data?.candles) ? data.candles : [];
}

async function drawRealKlineOrFallback(apiBase, symbol) {
  const canvas = els.klineCanvas;
  if (!canvas) return;
  try {
    const candles = await fetchKline(apiBase, symbol);
    if (!candles.length) throw new Error('empty candles');

    resizeCanvas();
    const ctx = canvas.getContext('2d');
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    ctx.clearRect(0, 0, w, h);

    const bg = ctx.createLinearGradient(0, 0, 0, h);
    bg.addColorStop(0, '#fbfdff');
    bg.addColorStop(1, '#f3f8fd');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, w, h);

    ctx.strokeStyle = '#dde7f0';
    ctx.lineWidth = 1;
    for (let i = 1; i < 6; i++) {
      const y = (h / 6) * i;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }
    for (let i = 1; i < 12; i++) {
      const x = (w / 12) * i;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }

    const shown = candles.slice(-Math.max(48, Math.floor(w / 13)));
    drawCandles(shown, ctx, w, h);
    addEvent('kline.source', `real (${shown.length} bars)`);
  } catch {
    drawKline(symbol);
    addEvent('kline.source', 'fallback synthetic');
  }
}

function addMessage(role, content) {
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  div.textContent = content;
  els.messages.appendChild(div);
  els.messages.scrollTop = els.messages.scrollHeight;
}

function addEvent(name, body) {
  const li = document.createElement('li');
  li.innerHTML = `<div class="name">${escapeHtml(name)}</div><div class="body">${escapeHtml(body)}</div>`;
  els.events.prepend(li);
}

function escapeHtml(s) {
  return String(s)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

function parseSSE(chunkBuffer, onEvent) {
  const blocks = chunkBuffer.split('\n\n');
  const rest = blocks.pop() ?? '';
  for (const b of blocks) {
    const lines = b.split('\n');
    let event = 'message';
    const dataLines = [];
    for (const line of lines) {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
    }
    const raw = dataLines.join('\n');
    onEvent(event, raw);
  }
  return rest;
}

function normalizePayload(raw) {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

function updateAgentStatus(payload) {
  const agent = payload?.agent;
  const status = payload?.status;
  if (!agent || !status) return;
  const curr = agentState.get(agent) || { team: '-', status: 'pending' };
  agentState.set(agent, { ...curr, status });
  renderAgentBoard();
}

function updateAgentSnapshot(payload) {
  const list = payload?.agents;
  if (!Array.isArray(list)) return;
  for (const row of list) {
    if (!row?.agent) continue;
    agentState.set(row.agent, { team: row.team || '-', status: row.status || 'pending' });
  }
  renderAgentBoard();
}

async function streamChat({ apiBase, prompt, dryRun }) {
  const resp = await fetch(`${apiBase}/v1/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: 'tradingagents-ashare',
      stream: true,
      dry_run: dryRun,
      messages: [{ role: 'user', content: prompt }],
    }),
  });

  if (!resp.ok || !resp.body) {
    const text = await resp.text();
    throw new Error(`HTTP ${resp.status}: ${text || 'stream failed'}`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    buffer = parseSSE(buffer, (event, raw) => {
      if (!raw || raw === '[DONE]') return;

      const payload = normalizePayload(raw);

      if (event === 'agent.snapshot') {
        updateAgentSnapshot(payload);
      }
      if (event === 'agent.status') {
        updateAgentStatus(payload);
      }
      if (event === 'agent.message') {
        const content = payload?.content || '';
        if (content) addMessage('assistant', content);
      }
      if (event === 'agent.report') {
        const section = payload?.section || 'report';
        const content = payload?.content || '';
        if (content) addMessage('assistant', `[${section}]\n${content}`);
      }
      if (event === 'job.completed') {
        addMessage('assistant', `分析完成。最终决策：${payload?.decision || 'N/A'}`);
      }
      if (event === 'job.failed') {
        addMessage('assistant', `分析失败：${payload?.error || raw}`);
      }

      const brief = typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2).slice(0, 520);
      addEvent(event, brief);
    });
  }
}

els.form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const prompt = els.prompt.value.trim();
  if (!prompt) return;

  const apiBase = els.apiBase.value.trim().replace(/\/$/, '');
  const dryRun = els.dryRun.checked;
  const symbolMatch =
    prompt.match(/\b\d{6}(?:\.(?:SH|SZ|SS))?\b/i)?.[0] ||
    prompt.match(/\b[A-Z]{1,6}(?:\.[A-Z]{1,3})?\b/)?.[0] ||
    'UNKNOWN';
  const symbol = symbolMatch.toUpperCase();
  if (els.chartTitle) els.chartTitle.textContent = `K线图 · ${symbol}`;
  await drawRealKlineOrFallback(apiBase, symbol);

  resetAgents();
  addMessage('user', prompt);
  addMessage('system', '任务已提交，正在接收 12-Agent 实时状态...');
  els.prompt.value = '';
  els.sendBtn.disabled = true;
  els.connDot.classList.add('live');

  try {
    await streamChat({ apiBase, prompt, dryRun });
  } catch (err) {
    addMessage('assistant', `请求异常：${err?.message || err}`);
    addEvent('error', String(err?.message || err));
  } finally {
    els.sendBtn.disabled = false;
    els.connDot.classList.remove('live');
  }
});

els.clearEvents.addEventListener('click', () => {
  els.events.innerHTML = '';
});

renderAgentBoard();
drawRealKlineOrFallback((els.apiBase?.value || 'http://127.0.0.1:8000').trim(), '600519.SH');
addMessage('assistant', '已切换到 12-Agent 工作台模式。\n直接输入：请分析 600519.SH 在 2026-03-02 的情况。');
window.addEventListener('resize', () => {
  const current = (els.chartTitle?.textContent || '').replace('K线图 · ', '').trim() || '600519.SH';
  drawRealKlineOrFallback((els.apiBase?.value || 'http://127.0.0.1:8000').trim(), current);
});
