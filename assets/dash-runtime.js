/*
 * dash-runtime.js
 * A tiny data runtime for the dashboard: loads the CSV/JSON sources, runs the
 * calculations on top of them, and redraws every chart when data arrives or the
 * window resizes. The page code only talks to `window.dash`.
 */
(function () {
  const sources = window.DASH_SOURCES || {};      // { id: 'data/file.csv' }
  const state = {};                               // id -> {status, data, message}
  const calcs = {};                               // id -> {inputs, fn}
  const calcCache = {};                           // id -> {version, result}
  const draws = {};                               // name -> fn
  const listeners = [];
  let version = 0;
  let scheduled = false;

  const colors = ['#2f6bd8', '#e07b28', '#2a9d8f', '#8e5ec9', '#d4a72c', '#c8432f', '#5c7cfa', '#8d6e63'];

  function load(id, url) {
    state[id] = { status: 'loading', data: [] };
    const bust = (url.includes('?') ? '&' : '?') + 'v=' + Date.now();
    const req = url.endsWith('.json') ? d3.json(url + bust) : d3.csv(url + bust);
    req.then((rows) => {
      state[id] = { status: 'ok', data: rows, columns: rows.columns || [] };
    }).catch((err) => {
      state[id] = { status: 'error', data: [], message: String(err) };
    }).finally(() => { version++; schedule(); });
  }

  function data(id) {
    if (calcs[id]) {
      const c = calcs[id];
      const inputs = c.inputs.map(data);
      if (inputs.some((d) => d.status === 'error')) return { status: 'error', data: [] };
      if (inputs.some((d) => d.status !== 'ok')) return { status: 'loading', data: [] };
      const cached = calcCache[id];
      if (cached && cached.version === version) return cached.result;
      let result;
      try {
        result = { status: 'ok', data: c.fn(...inputs.map((d) => d.data)) };
      } catch (err) {
        console.error('calc ' + id + ' failed', err);
        result = { status: 'error', data: [], message: String(err) };
      }
      calcCache[id] = { version, result };
      return result;
    }
    return state[id] || { status: 'missing', data: [] };
  }

  function runDraw(name, el) {
    try { draws[name](el); } catch (err) { console.error('draw ' + name + ' failed', err); }
  }

  function runAll() {
    scheduled = false;
    listeners.forEach((fn) => { try { fn(); } catch (err) { console.error(err); } });
    Object.keys(draws).forEach((name) => {
      document.querySelectorAll('[data-draw="' + name + '"]').forEach((el) => runDraw(name, el));
    });
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(runAll);
  }

  // Redraw a drawing when its own width changes (charts size from clientWidth).
  const widths = new WeakMap();
  const ro = new ResizeObserver((entries) => {
    entries.forEach((e) => {
      const el = e.target, w = Math.round(e.contentRect.width);
      if (widths.get(el) === w) return;
      const first = !widths.has(el);
      widths.set(el, w);
      if (!first && draws[el.dataset.draw]) runDraw(el.dataset.draw, el);
    });
  });

  window.dash = {
    colors,
    data,
    calc(id, def) { calcs[id] = def; },
    loader() {},
    draw(name, fn) {
      if (fn) {
        draws[name] = fn;
        document.querySelectorAll('[data-draw="' + name + '"]').forEach((el) => ro.observe(el));
        schedule();
      } else {
        document.querySelectorAll('[data-draw="' + name + '"]').forEach((el) => runDraw(name, el));
      }
    },
    onData(fn) { listeners.push(fn); schedule(); },
    params: () => ({}), setParams() {}, resetParams() {}, setLink() {},
    refresh(id) { if (sources[id]) load(id, sources[id]); },
  };

  Object.entries(sources).forEach(([id, url]) => load(id, url));
})();
