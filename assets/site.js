/* DepthJev project page.
   data/featured.json: six recorded runs, every step with the facts Jev read, its answer, the OWLv2 box, the exact pose and
   top-down cells from the depth map. data/runs.json: all 300 runs. data/stats.json: latency and tokens from the server logs. */
(function () {
  "use strict";

  // ---------- helpers ----------
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const SVGNS = "http://www.w3.org/2000/svg";
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const rootEl = document.documentElement;

  function build(el, attrs, kids) {
    if (attrs) for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === "class") el.setAttribute("class", v);
      else if (k === "text") el.textContent = v;
      else if (k === "style") el.style.cssText = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat(Infinity)) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    return el;
  }
  const h = (tag, attrs, ...kids) => build(document.createElement(tag), attrs, kids);
  const s = (tag, attrs, ...kids) => build(document.createElementNS(SVGNS, tag), attrs, kids);
  const icon = (id, cls) => s("svg", { class: cls || null, "aria-hidden": "true" }, s("use", { href: "#" + id }));
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const ease = (t) => (t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
  const pad = (k) => String(k).padStart(2, "0");
  const media = (id, k, depth) => `media/${id}/${pad(k)}${depth ? "-d" : ""}.webp`;
  const typeName = (t) => t.replace(/([a-z])([A-Z])/g, "$1 $2").toLowerCase();
  const cap = (t) => t.charAt(0).toUpperCase() + t.slice(1);
  const getJSON = (url) => fetch(url).then((r) => { if (!r.ok) throw new Error(url + " " + r.status); return r.json(); });
  const cssVar = (name, el) => getComputedStyle(el || rootEl).getPropertyValue(name).trim();

  function whenVisible(el, cb, threshold) {
    const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { io.disconnect(); cb(); } }), { threshold: threshold || 0.25 });
    io.observe(el);
  }
  function watchVisible(el, cb) {
    const io = new IntersectionObserver((es) => es.forEach((e) => cb(e.isIntersecting)), { threshold: 0.12 });
    io.observe(el);
  }
  function sizeCanvas(cv, w, hgt) {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const W = w || cv.clientWidth, H = hgt || cv.clientHeight;
    if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
    const g = cv.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, W, H);
    return { g, W, H };
  }

  // ---------- theme ----------
  const themeBtn = $("#theme");
  const themeHooks = [];
  const isDark = () => (rootEl.dataset.theme ? rootEl.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches);
  function themeChanged() { themeBtn.classList.toggle("is-dark", isDark()); themeHooks.forEach((f) => f()); }
  themeBtn.addEventListener("click", () => {
    const next = isDark() ? "light" : "dark";
    rootEl.dataset.theme = next;
    try { localStorage.setItem("depthjev-theme", next); } catch (e) { /* storage may be unavailable */ }
    themeChanged();
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", themeChanged);
  themeBtn.classList.toggle("is-dark", isDark());

  // ---------- top bar ----------
  const topbar = $("#topbar"), heroEl = $("#top");
  const updateBar = () => topbar.classList.toggle("solid", heroEl.getBoundingClientRect().bottom < 72);
  addEventListener("scroll", updateBar, { passive: true });
  updateBar();

  // ---------- reveal on scroll ----------
  $$(".sec .card, .sec .stage, .notes li, .cases").forEach((el) => el.classList.add("reveal"));
  const rio = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); rio.unobserve(e.target); } }), { threshold: 0.08 });
  $$(".reveal").forEach((el) => rio.observe(el));

  // ---------- tooltip ----------
  const tip = $("#tip");
  function showTip(nodes, x, y) {
    tip.replaceChildren(...nodes.filter(Boolean));
    tip.hidden = false;
    const r = tip.getBoundingClientRect();
    let left = x + 16, top = y + 16;
    if (left + r.width > innerWidth - 8) left = x - r.width - 16;
    if (top + r.height > innerHeight - 8) top = y - r.height - 16;
    tip.style.left = Math.max(8, left) + "px";
    tip.style.top = Math.max(8, top) + "px";
  }
  const hideTip = () => { tip.hidden = true; };
  addEventListener("scroll", hideTip, { passive: true });

  // ---------- vocabulary ----------
  const ACTIONS = ["move_ahead", "move_back", "move_left", "move_right", "rotate_left", "rotate_right", "look_up", "look_down"];
  const SECTORS = ["far_left", "left", "center", "right", "far_right"];
  const BIN = { "under 0.5 m": 0, "0.5 to 1 m": 1, "1 to 2 m": 2, "over 2 m": 3 };
  const BIN_HEX = ["#f6d543", "#f3761b", "#b43359", "#8a226a"];
  const binOfM = (m) => (m == null ? 3 : m < 0.5 ? 0 : m < 1 ? 1 : m < 2 ? 2 : 3);
  const FOCAL = 250 / Math.tan((50 * Math.PI) / 180); // 209.8 px: the 500 px frame and its 100 degree field of view
  const CX = 249.5;
  const EDGES = [0, 100, 200, 300, 400, 500].map((c) => Math.atan((c - CX) / FOCAL)); // sector edges, radians from straight ahead
  const SUBSETS = [["base", "Base"], ["common_sense", "Common sense"], ["complex_instruction", "Complex"], ["visual_appearance", "Visual"], ["long_horizon", "Long horizon"]];
  const CODE = { F: "move_ahead", B: "move_back", L: "move_left", R: "move_right", Q: "rotate_left", E: "rotate_right", U: "look_up", D: "look_down" };

  const binChip = (txt) => h("span", { class: "vchip " + (txt in BIN ? "b" + BIN[txt] : "unk"), text: txt });
  const moveChip = (txt) => h("span", { class: "vchip " + (txt === "clear" ? "ok" : txt === "blocked" ? "no" : "unk"), text: txt });

  // ---------- geometry: cells, poses, maps ----------
  function bytes(b64) {
    const bin = atob(b64), out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }
  function cells(b64, res) {
    const b = bytes(b64), n = b.length >> 1, xs = new Float32Array(n), zs = new Float32Array(n);
    for (let i = 0; i < n; i++) { xs[i] = (b[2 * i] + 0.5) * res - 3; zs[i] = (b[2 * i + 1] + 0.5) * res; }
    return { xs, zs, n };
  }
  function prepRun(run) {
    const p0 = run.frames[0].pose, t0 = (p0[2] * Math.PI) / 180, c0 = Math.cos(t0), s0 = Math.sin(t0);
    // map frame: x to the right of the start heading, y along it (the start heading points up on screen)
    const toMap = (wx, wz) => { const dx = wx - p0[0], dz = wz - p0[1]; return [dx * c0 - dz * s0, dx * s0 + dz * c0]; };
    const toWorld = (pose, x, z) => { const t = (pose[2] * Math.PI) / 180, c = Math.cos(t), sn = Math.sin(t); return [pose[0] + x * c + z * sn, pose[1] - x * sn + z * c]; };
    run.name = typeName(run.target);
    run.N = run.frames.length;
    run.mapTarget = toMap(run.targetXZ[0], run.targetXZ[1]);
    let x0 = run.mapTarget[0] - 1.25, x1 = run.mapTarget[0] + 1.25, y0 = run.mapTarget[1] - 1.25, y1 = run.mapTarget[1] + 1.25;
    run.frames.forEach((f) => {
      f.local = { obs: cells(f.obs, 0.05), floor: cells(f.floor, 0.1) };
      f.mapPos = toMap(f.pose[0], f.pose[1]);
      f.mapYaw = ((f.pose[2] - p0[2]) * Math.PI) / 180;
      x0 = Math.min(x0, f.mapPos[0] - 0.9); x1 = Math.max(x1, f.mapPos[0] + 0.9); y0 = Math.min(y0, f.mapPos[1] - 0.9); y1 = Math.max(y1, f.mapPos[1] + 0.9);
      const conv = (c) => { const out = new Float32Array(c.n * 2); for (let i = 0; i < c.n; i++) { const w = toWorld(f.pose, c.xs[i], c.zs[i]), m = toMap(w[0], w[1]); out[2 * i] = m[0]; out[2 * i + 1] = m[1]; } return out; };
      f.mapObs = conv(f.local.obs);
      f.mapFloor = conv(f.local.floor);
    });
    run.bounds = { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, hw: (x1 - x0) / 2 + 0.25, hh: (y1 - y0) / 2 + 0.25 };
  }

  function drawMap(cv, run, k, opts) {
    const { g, W, H } = sizeCanvas(cv);
    if (!W) return;
    const b = run.bounds, sc = Math.min(W / (2 * b.hw), H / (2 * b.hh)) * 0.96;
    const X = (x) => W / 2 + (x - b.cx) * sc, Y = (y) => H / 2 - (y - b.cy) * sc;
    // visible floor, accumulated up to step k
    g.fillStyle = "rgba(120, 148, 196, 0.10)";
    const fs = Math.max(1.5, 0.1 * sc);
    for (let j = 0; j <= k; j++) { const a = run.frames[j].mapFloor; for (let i = 0; i < a.length; i += 2) g.fillRect(X(a[i]) - fs / 2, Y(a[i + 1]) - fs / 2, fs, fs); }
    // obstacles, older steps fainter
    const os = Math.max(1.2, Math.min(3, 0.05 * sc * 0.8));
    for (let j = 0; j <= k; j++) {
      const a = run.frames[j].mapObs;
      g.fillStyle = j === k ? "rgba(246, 150, 60, 0.8)" : "rgba(243, 118, 27, 0.18)";
      for (let i = 0; i < a.length; i += 2) g.fillRect(X(a[i]) - os / 2, Y(a[i + 1]) - os / 2, os, os);
    }
    // target and its 1 m success circle
    const tx = X(run.mapTarget[0]), ty = Y(run.mapTarget[1]);
    g.beginPath(); g.arc(tx, ty, 1 * sc, 0, Math.PI * 2);
    g.fillStyle = "rgba(34, 197, 94, 0.08)"; g.fill();
    g.lineWidth = 1.5; g.strokeStyle = "rgba(34, 197, 94, 0.75)"; g.stroke();
    // field of view at the current pose
    const f = run.frames[k], ax = X(f.mapPos[0]), ay = Y(f.mapPos[1]), yaw = f.mapYaw, R = 2.2 * sc;
    g.beginPath(); g.moveTo(ax, ay);
    for (let a = -50; a <= 50; a += 5) { const t = yaw + (a * Math.PI) / 180; g.lineTo(ax + Math.sin(t) * R, ay - Math.cos(t) * R); }
    g.closePath();
    const grad = g.createRadialGradient(ax, ay, 0, ax, ay, R);
    grad.addColorStop(0, "rgba(255, 255, 255, 0.20)"); grad.addColorStop(1, "rgba(255, 255, 255, 0)");
    g.fillStyle = grad; g.fill();
    // path so far
    g.lineWidth = 2; g.lineJoin = g.lineCap = "round"; g.strokeStyle = "rgba(255, 255, 255, 0.85)";
    g.beginPath();
    for (let j = 0; j <= k; j++) { const p = run.frames[j].mapPos; if (j === 0) g.moveTo(X(p[0]), Y(p[1])); else g.lineTo(X(p[0]), Y(p[1])); }
    g.stroke();
    for (let j = 0; j < k; j++) { const p = run.frames[j].mapPos; g.beginPath(); g.arc(X(p[0]), Y(p[1]), 2.4, 0, Math.PI * 2); g.fillStyle = "#dfe5f1"; g.fill(); }
    // the target
    g.beginPath(); g.arc(tx, ty, 5.5, 0, Math.PI * 2); g.fillStyle = "#22c55e"; g.fill();
    g.lineWidth = 2; g.strokeStyle = "#0a0e18"; g.stroke();
    if (!opts || !opts.noLabels) {
      g.font = "500 11px Inter, system-ui, sans-serif"; g.fillStyle = "#cfe9d6"; g.textAlign = "center";
      g.fillText(run.name, tx, ty - 1 * sc - 6 < 12 ? ty + 1 * sc + 14 : ty - 1 * sc - 6);
    }
    // the robot
    g.save(); g.translate(ax, ay); g.rotate(yaw);
    g.beginPath(); g.moveTo(0, -9); g.lineTo(6.5, 6); g.lineTo(0, 3); g.lineTo(-6.5, 6); g.closePath();
    g.fillStyle = "#f6d543"; g.fill(); g.lineWidth = 1.5; g.strokeStyle = "#0a0e18"; g.stroke();
    g.restore();
  }

  // ---------- probability bars ----------
  function probRows(box) {
    box.replaceChildren();
    const rows = {};
    ACTIONS.forEach((a) => {
      const bar = h("span", { class: "pb" }), val = h("span", { class: "pv" });
      rows[a] = { el: h("div", { class: "prob" }, icon("a-" + a), h("span", { class: "pn", text: a }), h("span", { class: "pt" }, bar), val), bar, val };
      box.append(rows[a].el);
    });
    return {
      set(p, chosen) {
        ACTIONS.forEach((a) => {
          const v = p ? p[a] || 0 : 0, r = rows[a];
          r.el.classList.toggle("on", !!p && a === chosen);
          r.bar.style.width = (v * 100).toFixed(1) + "%";
          r.val.textContent = p ? v.toFixed(2) : "";
        });
      },
    };
  }

  // ---------- box and label over a frame ----------
  function frameOverlay(view, svgEl) {
    const halo = s("rect", { class: "ov-box-halo", rx: 5 }), box = s("rect", { class: "ov-box", rx: 5 });
    svgEl.append(halo, box);
    const label = h("span", { class: "ov-label" });
    label.hidden = true;
    view.append(label);
    return {
      set(f, name) {
        const on = f && f.visible && f.box;
        halo.style.display = box.style.display = on ? "" : "none";
        label.hidden = !on;
        if (!on) return;
        const [x0, y0, x1, y1] = f.box;
        [halo, box].forEach((r) => { r.setAttribute("x", x0 - 3); r.setAttribute("y", y0 - 3); r.setAttribute("width", x1 - x0 + 6); r.setAttribute("height", y1 - y0 + 6); });
        label.replaceChildren(name + " · ", h("b", { text: f.est != null ? f.est.toFixed(2) + " m" : "no depth" }));
        const below = y0 < 46;
        label.classList.toggle("below", below);
        label.style.left = clamp(((x0 + x1) / 2) / 5, 14, 86) + "%";
        label.style.top = ((below ? y1 + 3 : y0 - 3) / 5) + "%";
      },
    };
  }

  // =====================================================================================================
  // FIG. 1: one episode, as Jev sees it
  // =====================================================================================================
  function initHero(run) {
    const view = $("#hero-view"), rgb = $("#hero-rgb"), dep = $("#hero-depth"), ov = $("#hero-overlay");
    const facts = $("#hero-facts"), tokens = $("#hero-tokens"), meta = $("#hero-meta"), dist = $("#hero-dist");
    const playBtn = $("#hero-play"), mapCv = $("#hero-map");
    $("#hero-instr").textContent = "“" + run.instruction + "”";
    run.frames.forEach((f, k) => { new Image().src = media(run.id, k); new Image().src = media(run.id, k, true); });

    // sector separators and the bins written under each sector
    const seps = [100, 200, 300, 400].map((x) => s("line", { class: "ov-sep", x1: x, x2: x, y1: 0, y2: 500 }));
    ov.append(...seps);
    const box = frameOverlay(view, ov);
    const binsRow = h("div", { class: "ov-bins" });
    const binSpans = SECTORS.map(() => h("span"));
    binsRow.append(...binSpans);
    view.append(binsRow);

    const probs = probRows($("#hero-probs"));
    const dots = $("#hero-dots");
    const dotBtns = run.frames.map((f, k) => {
      const last = k === run.N - 1;
      const b = h("button", { type: "button", class: last ? "goal" : null, "aria-label": last ? "Final position" : `Step ${k}: ${f.action}` }, icon(last ? "i-check" : "a-" + f.action));
      b.addEventListener("click", () => { setPlaying(false); show(k, true); });
      dots.append(b);
      return b;
    });

    let k = 0, t0 = 0, playing = !reduced, onScreen = true, raf = 0, lines = [];
    const T = { scan0: 300, scan1: 1700, bars: 1850, next: 3900 };

    function buildFacts(f) {
      const fa = f.facts, tg = fa.target, name = fa.task.target_object;
      const rows = [["target", tg.visible ? [name + " · " + tg.sector.replace("_", " ") + " · ", binChip(tg.distance)] : [name + " · ", h("span", { class: "vchip unk", text: "not in view" })]]];
      SECTORS.forEach((sec) => rows.push([sec, [binChip(fa.free_distance_ahead_by_sector[sec])]]));
      rows.push(["move_ahead", [moveChip(fa.move_check.move_ahead)]]);
      rows.push(["camera", [fa.camera_pitch]]);
      const rec = fa.recent_actions.filter((r) => r.action).map((r) => r.action + (r.result === "success" ? "" : " (failed)"));
      rows.push(["recent", [rec.length ? rec.join(", ") : "none yet"]]);
      facts.replaceChildren(...rows.map(([key, val]) => h("li", null, h("span", { class: "k", text: key }), h("span", { class: "v" }, val))));
      lines = $$("li", facts);
    }

    function show(step, still) {
      k = step;
      t0 = performance.now() - (still || reduced ? T.next - 1 : 0);
      const f = run.frames[k], last = k === run.N - 1;
      rgb.src = media(run.id, k);
      dep.src = media(run.id, k, true);
      dotBtns.forEach((b, j) => { b.toggleAttribute("aria-current", j === k); if (j === k) b.setAttribute("aria-current", "step"); b.classList.toggle("done", j < k); });
      box.set(last ? null : f, run.name);
      if (!last) {
        buildFacts(f);
        SECTORS.forEach((sec, i) => { const v = f.facts.free_distance_ahead_by_sector[sec]; binSpans[i].textContent = v.replace(" to ", "–"); binSpans[i].style.background = BIN_HEX[BIN[v]]; binSpans[i].style.color = BIN[v] >= 2 ? "#fff" : "#0b1020"; });
        tokens.textContent = `Jev read ${f.tokens.toLocaleString("en-US")} tokens of text and answered in ${(f.jevMs / 1000).toFixed(2)} s.`;
        meta.textContent = `Step ${k + 1} of ${run.N - 1} · true distance ${f.dist.toFixed(2)} m`;
      } else {
        facts.replaceChildren(h("li", { class: "on now" }, h("span", { class: "k", text: "result" }), h("span", { class: "v" }, h("span", { class: "vchip ok", text: "success" }))),
          h("li", { class: "on" }, h("span", { class: "k", text: "distance" }), h("span", { class: "v", text: f.dist.toFixed(2) + " m from the " + run.name })),
          h("li", { class: "on" }, h("span", { class: "k", text: "steps" }), h("span", { class: "v", text: String(run.N - 1) })));
        lines = [];
        binSpans.forEach((b) => b.classList.remove("on"));
        tokens.textContent = "The episode ends as soon as the robot is within 1 m of the target.";
        meta.textContent = `Reached in ${run.N - 1} steps`;
        probs.set(null);
      }
      dist.textContent = `${f.dist.toFixed(2)} m to the ${run.name}`;
      drawMap(mapCv, run, k);
      tick(performance.now());
    }

    function tick(now) {
      cancelAnimationFrame(raf);
      const t = now - t0, last = k === run.N - 1, f = run.frames[k];
      const p = last ? 1 : clamp((t - T.scan0) / (T.scan1 - T.scan0), 0, 1), e = ease(p);
      view.style.setProperty("--reveal", (last ? 0 : e * 100).toFixed(2) + "%");
      view.style.setProperty("--scan-o", p > 0 && p < 1 ? 1 : 0);
      view.style.setProperty("--sep-o", last ? 0 : Math.min(1, p * 1.5).toFixed(2));
      if (!last) {
        const reached = SECTORS.map((_, i) => e >= (i + 0.55) / 5);
        binSpans.forEach((b, i) => b.classList.toggle("on", reached[i]));
        lines.forEach((li, i) => {
          const on = i === 0 ? t > T.scan0 * 0.5 : i <= 5 ? reached[i - 1] : p >= 1;
          li.classList.toggle("on", on);
          li.classList.toggle("now", on && (i === 0 ? p < 0.12 : i <= 5 ? !reached[i] && p < 1 : t < T.bars + 300));
        });
        probs.set(t > T.bars ? f.p : null, f.action);
      }
      if (playing && onScreen && t > T.next + (last ? 1400 : 0)) { show((k + 1) % run.N); return; }
      if (playing && onScreen) raf = requestAnimationFrame(tick);
    }

    function setPlaying(on) {
      playing = on;
      playBtn.setAttribute("aria-pressed", String(on));
      playBtn.querySelector("span").textContent = on ? "Pause" : "Play";
      if (on) { t0 = performance.now() - Math.min(performance.now() - t0, T.next); tick(performance.now()); }
    }
    playBtn.addEventListener("click", () => setPlaying(!playing));
    watchVisible($("#hero"), (v) => { onScreen = v; if (v && playing) tick(performance.now()); });
    document.addEventListener("visibilitychange", () => { onScreen = !document.hidden; if (onScreen && playing) { t0 = performance.now() - 200; tick(performance.now()); } });
    addEventListener("resize", () => drawMap(mapCv, run, k));
    setPlaying(playing);
    show(0, reduced);
  }

  // =====================================================================================================
  // FIG. 2: anatomy of a step
  // =====================================================================================================
  const RULES = {
    2: "when the target is visible in the center sector and move_ahead is clear, pick move_ahead",
    3: "when the target is in the far_left or far_right sector it would leave the view if the robot moved ahead, so pick move_left or move_right toward it, or rotate toward it if that sidestep is blocked",
    4: "when the target is not visible and the camera is level, turn toward where it most likely is with rotate_left or rotate_right and keep turning in the same direction until a full turn of 4 rotations is done",
    6: "pick look_down only when the camera is level and the target is likely below the view",
    11: "when the target note says the true distance is still over 1 m, keep approaching: move_ahead if the target is in the center sector, otherwise sidestep toward it",
  };
  const SCENARIOS = [
    { id: "pasta", k: 0, tab: "Clear path", rule: 2, text: "The pot sits on the stove at the far end of the kitchen: center sector, over 2 m. The center has more than 2 m of free floor and the next 0.25 m step is clear, so Jev moves ahead." },
    { id: "laptop", k: 0, tab: "Blocked", rule: 3, text: "A wall edge fills four sectors at under 0.5 m and blocks the next step. The laptop is on the table in the far-left sector, where moving ahead would lose it from view, so Jev sidesteps left." },
    { id: "phone", k: 0, tab: "Searching", rule: 4, text: "This long-horizon episode starts facing a wall: every sector is under 0.5 m and the cell phone is not in view. With the target out of view, Jev also says where it probably is, and turns to search." },
    { id: "pot", k: 1, tab: "Looking down", rule: 6, text: "After one turn the stove is in view, but OWLv2 finds no pot at eye level. Jev places the target below the view, so with a level camera it looks down; one step later the pot is detected 30 degrees down." },
    { id: "pasta", k: 7, tab: "Last metres", rule: 11, text: "The pot is 0.5 to 1 m away in the left sector. The episode has not ended, so the facts add a note that the true distance is still over 1 m. Jev sidesteps toward it, and the next step ends the episode." },
  ];

  function jsonView(pre, obj) {
    pre.replaceChildren();
    const text = JSON.stringify(obj, null, 2).split("\n"), stack = [];
    const linkFor = (path) => {
      if (path[0] === "free_distance_ahead_by_sector" && path[1]) return "sector:" + path[1];
      if (path[0] === "target") return "target";
      if ((path[0] === "move_check" && path[1] === "move_ahead") || path[0] === "move_ahead_check_saw_the_floor") return "move_ahead";
      return null;
    };
    const tok = /("(?:[^"\\]|\\.)*")(\s*:)?|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:e[+-]?\d+)?)/g;
    text.forEach((line, i) => {
      const m = line.match(/^\s*"([^"]+)":/), key = m ? m[1] : null;
      if (/^\s*[}\]]/.test(line)) stack.pop();
      const link = linkFor((key ? [...stack, key] : [...stack]).filter((p) => p !== "#"));
      const span = h("span", { class: "jl", "data-link": link });
      let last = 0, t;
      tok.lastIndex = 0;
      while ((t = tok.exec(line))) {
        if (t.index > last) span.append(h("span", { class: "jp", text: line.slice(last, t.index) }));
        if (t[1]) { span.append(h("span", { class: t[2] ? "jk" : "js", text: t[1] })); if (t[2]) span.append(h("span", { class: "jp", text: t[2] })); }
        else if (t[3]) span.append(h("span", { class: "jb", text: t[3] }));
        else span.append(h("span", { class: "jn", text: t[4] }));
        last = tok.lastIndex;
      }
      if (last < line.length) span.append(h("span", { class: "jp", text: line.slice(last) }));
      pre.append(span);
      if (i < text.length - 1) pre.append("\n");
      if (/[{[]\s*$/.test(line)) stack.push(key || "#");
    });
  }

  function initAnatomy(byId) {
    const fig = $("#anatomy"), tabs = $("#anat-tabs"), view = $("#anat-view");
    const rgb = $("#anat-rgb"), dep = $("#anat-depth"), ov = $("#anat-overlay"), readout = $("#anat-readout");
    const bev = $("#bev"), bevCv = $("#bev-canvas"), pre = $("#anat-json"), rule = $("#anat-rule"), capEl = $("#anat-cap");
    const probs = probRows($("#anat-probs"));
    const dirBox = h("div", { class: "dir" });
    $("#anat-probs").after(dirBox);
    const box = frameOverlay(view, ov);
    const bands = SECTORS.map((sec, i) => s("rect", { class: "ov-band", x: i * 100, y: 0, width: 100, height: 500, "data-link": "sector:" + sec }));
    ov.prepend(...bands);
    let cur = null, grid = null;

    const tabBtns = SCENARIOS.map((sc, i) => {
      const f = byId[sc.id].frames[sc.k];
      const b = h("button", { class: "tab", type: "button", role: "tab", "aria-selected": "false", id: "tab-" + i }, icon("a-" + f.action), sc.tab);
      b.addEventListener("click", () => select(i));
      b.addEventListener("keydown", (e) => { if (e.key === "ArrowRight" || e.key === "ArrowLeft") { const j = (i + (e.key === "ArrowRight" ? 1 : SCENARIOS.length - 1)) % SCENARIOS.length; tabBtns[j].focus(); select(j); } });
      tabs.append(b);
      return b;
    });

    $$(".seg button", fig).forEach((b) => b.addEventListener("click", () => {
      $$(".seg button", fig).forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      view.classList.toggle("show-depth", b.dataset.view === "depth");
    }));

    function readAt(e) {
      if (!grid) return;
      const r = view.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
      if (x < 0 || y < 0 || x >= r.width || y >= r.height) { readout.hidden = true; return; }
      const mm = grid[Math.floor((y / r.height) * 100) * 100 + Math.floor((x / r.width) * 100)];
      readout.hidden = false;
      readout.textContent = (mm / 1000).toFixed(2) + " m";
      readout.style.left = (x < r.width - 90 ? x : x - 110) + "px";
      readout.style.top = y + "px";
    }
    view.addEventListener("pointermove", readAt);
    view.addEventListener("pointerleave", () => { readout.hidden = true; });

    // linked highlighting between the JSON, the frame and the top-down view
    function highlight(link) { $$("[data-link]", fig).forEach((el) => el.classList.toggle("hl", !!link && el.getAttribute("data-link") === link)); }
    fig.addEventListener("pointerover", (e) => { const t = e.target.closest("[data-link]"); highlight(t ? t.getAttribute("data-link") : null); });
    fig.addEventListener("pointerleave", () => highlight(null));

    function drawBev(f) {
      const S = 400, sc = S / 4.8, X = (x) => S / 2 + x * sc, Y = (z) => S - 0.38 * sc - z * sc;
      bev.setAttribute("viewBox", `0 0 ${S} ${S}`);
      bev.replaceChildren();
      // cells on the canvas underneath
      const { g, W } = sizeCanvas(bevCv);
      const k = W / S;
      g.fillStyle = "rgba(120, 148, 196, 0.18)";
      const fl = f.local.floor, ob = f.local.obs;
      for (let i = 0; i < fl.n; i++) g.fillRect(X(fl.xs[i] - 0.05) * k, Y(fl.zs[i] + 0.05) * k, 0.1 * sc * k, 0.1 * sc * k);
      const ps = Math.max(1.2, 0.05 * sc * k * 0.78);
      g.globalAlpha = 0.9;
      for (let i = 0; i < ob.n; i++) { g.fillStyle = BIN_HEX[binOfM(ob.zs[i])]; g.fillRect(X(ob.xs[i]) * k - ps / 2, Y(ob.zs[i]) * k - ps / 2, ps, ps); }
      g.globalAlpha = 1;
      // distance guides at the bin edges
      [0.5, 1, 2, 3, 4].forEach((z) => {
        bev.append(s("line", { class: "guide", x1: 0, x2: S, y1: Y(z), y2: Y(z) }));
        bev.append(s("text", { class: "t-mono", x: S - 6, y: Y(z) - 4, "text-anchor": "end", text: z + " m" }));
      });
      // the five sectors: free floor up to the nearest obstacle
      const zmax = 4.42;
      SECTORS.forEach((sec, i) => {
        const v = f.free[sec], F = v == null ? zmax : Math.min(v, zmax), a0 = EDGES[i], a1 = EDGES[i + 1];
        const pts = [[0, 0], [F * Math.tan(a0), F], [F * Math.tan(a1), F]].map(([x, z]) => X(x).toFixed(1) + "," + Y(z).toFixed(1)).join(" ");
        const bin = BIN[f.facts.free_distance_ahead_by_sector[sec]];
        bev.append(s("polygon", { class: "wedge", points: pts, fill: BIN_HEX[bin], "data-link": "sector:" + sec }));
        if (v != null && v < zmax) {
          bev.append(s("line", { class: "wedge-edge", x1: X(F * Math.tan(a0)), x2: X(F * Math.tan(a1)), y1: Y(F), y2: Y(F), stroke: BIN_HEX[bin], "data-link": "sector:" + sec }));
          const mid = (Math.tan(a0) + Math.tan(a1)) / 2;
          if (F >= 0.6 && (Math.tan(a1) - Math.tan(a0)) * F * sc >= 44 && Math.abs(X(F * mid) - S / 2) < S / 2 - 24) bev.append(s("text", { x: X(F * mid), y: Y(F) - 6, "text-anchor": "middle", text: v.toFixed(2) + " m", "data-link": "sector:" + sec }));
        }
      });
      // field of view edges
      [-50, 50].forEach((d) => { const t = (d * Math.PI) / 180; bev.append(s("line", { class: "fov", x1: X(0), y1: Y(0), x2: X(Math.sin(t) * 6), y2: Y(Math.cos(t) * 6) })); });
      // the next 0.25 m step: |x| <= 0.25 m, 0 < z <= 0.45 m
      bev.append(s("rect", { class: "corr" + (f.blockPx >= 20 ? " blocked" : ""), x: X(-0.25), y: Y(0.45), width: 0.5 * sc, height: 0.45 * sc, rx: 3, "data-link": "move_ahead" }));
      bev.append(s("circle", { class: "agent", cx: X(0), cy: Y(0), r: 0.2 * sc }));
      bev.append(s("path", { d: `M${X(0)} ${Y(0) - 0.2 * sc - 7} l-5 8 h10 z`, fill: "#f6d543" }));
      // the target, at its bearing and DA3 distance
      if (f.visible && f.box && f.est != null) {
        const bear = Math.atan(((f.box[0] + f.box[2]) / 2 - CX) / FOCAL), tx = X(Math.sin(bear) * f.est), ty = Y(Math.cos(bear) * f.est);
        const tgt = s("g", { "data-link": "target" }, s("circle", { class: "tgt-ring", cx: tx, cy: ty, r: 9 }), s("circle", { class: "tgt-dot", cx: tx, cy: ty, r: 4 }),
          s("text", { x: clamp(tx, 70, S - 70), y: ty - 15, "text-anchor": "middle", text: `${typeName(cur.run.target)} · ${f.est.toFixed(2)} m` }));
        bev.append(tgt);
      }
    }

    function select(i) {
      const sc = SCENARIOS[i], run = byId[sc.id], f = run.frames[sc.k];
      cur = { run, f, sc };
      tabBtns.forEach((b, j) => b.setAttribute("aria-selected", String(j === i)));
      rgb.src = media(run.id, sc.k);
      dep.src = media(run.id, sc.k, true);
      rgb.alt = `Camera frame: ${run.title}, step ${sc.k}`;
      box.set(f, run.name);
      grid = f.grid ? (() => { const b = bytes(f.grid); return new Uint16Array(b.buffer, b.byteOffset, b.length >> 1); })() : null;
      jsonView(pre, f.facts);
      drawBev(f);
      probs.set(f.p, f.action);
      dirBox.replaceChildren();
      if (f.dirP) {
        const ent = Object.entries(f.dirP).sort((a, b) => b[1] - a[1]);
        dirBox.append(h("p", { class: "col-lab", text: "Where is the target?" }),
          h("div", { class: "probs probs-card" }, ent.map(([d, v]) => h("div", { class: "prob" + (d === f.dir ? " on" : "") }, h("span"), h("span", { class: "pn", text: d }), h("span", { class: "pt" }, h("span", { class: "pb", style: `width:${(v * 100).toFixed(1)}%` })), h("span", { class: "pv", text: v.toFixed(2) })))));
      }
      rule.replaceChildren(h("span", { class: "rule-k", text: `Rule ${sc.rule} of Jev's instructions` }), h("q", { text: RULES[sc.rule] }));
      capEl.replaceChildren(h("b", { text: `${run.behaviour}, step ${sc.k + 1}. ` }), sc.text, ` Jev: ${f.action}, probability ${f.p[f.action].toFixed(2)}.`);
    }
    themeHooks.push(() => cur && drawBev(cur.f));
    addEventListener("resize", () => cur && drawBev(cur.f));
    select(0);
  }

  // =====================================================================================================
  // 02: leaderboard
  // =====================================================================================================
  const BOARD = [
    ["GPT-4o", "image", [57.7, 55.0, 60.0, 58.3, 60.0, 55.0]],
    ["GPT-4o-mini", "image", [32.8, 31.7, 33.3, 35.0, 28.3, 33.3]],
    ["Claude-3.5-Sonnet", "image", [44.7, 66.7, 51.7, 41.7, 36.7, 26.7]],
    ["Gemini-1.5-Pro", "image", [24.3, 23.3, 25.0, 25.0, 28.3, 20.0]],
    ["Gemini-2.0-flash", "image", [48.7, 63.3, 65.0, 50.0, 51.7, 13.3]],
    ["Gemini-1.5-flash", "image", [41.7, 56.7, 50.0, 46.7, 50.0, 5.0]],
    ["GPT-4o", "text", [17.4, 21.7, 21.7, 26.7, 16.7, 0.0]],
    ["GPT-4o-mini", "text", [8.3, 3.3, 13.3, 10.0, 15.0, 0.0]],
    ["Llama-3.2-90B-Vision-Ins", "image", [30.0, 48.3, 23.3, 38.3, 33.3, 6.7]],
    ["Llama-3.2-11B-Vision-Ins", "image", [21.4, 23.3, 21.7, 26.7, 18.3, 17.0]],
    ["InternVL2.5-78B", "image", [30.7, 36.7, 38.3, 33.3, 21.7, 23.3]],
    ["InternVL2.5-38B", "image", [30.3, 35.0, 28.3, 38.3, 26.7, 23.3]],
    ["InternVL2.5-8B", "image", [21.3, 35.0, 23.3, 21.7, 26.7, 0.0]],
    ["Qwen2-VL-72B-Ins", "image", [21.2, 26.7, 30.0, 28.3, 16.0, 5.0]],
    ["Qwen2-VL-7B-Ins", "image", [14.0, 26.7, 10.0, 15.0, 15.0, 3.3]],
    ["DepthJev", "ours", [46.7, 53.3, 51.7, 50.0, 36.7, 41.7]],
  ];
  const BOARD_COLS = ["Average", "Base", "Common sense", "Complex instruction", "Visual appearance", "Long horizon"];

  function initBoard() {
    const board = $("#board"), pills = $("#board-pills"), title = $("#board-title");
    let col = 0, shown = false;
    const rows = BOARD.map(([name, kind, vals]) => {
      const bar = h("div", { class: "bar" }), val = h("span", { class: "val" }), rk = h("span", { class: "rk" }), badge = kind === "ours" ? h("span", { class: "badge" }) : null;
      const el = h("div", { class: "row" + (kind === "ours" ? " ours" : ""), role: "listitem" },
        h("div", { class: "nm" }, rk, h("span", { text: name }), kind === "text" ? h("i", { class: "tag-mini", text: "text only" }) : null, badge),
        h("div", { class: "trk" }, bar, val));
      const row = { el, bar, val, rk, badge, name, kind, vals };
      el.addEventListener("pointermove", (e) => showTip([h("div", { class: "tv", text: vals[col].toFixed(1) + "%" }), h("div", { text: name + (kind === "text" ? " · text only" : kind === "ours" ? " · text facts only" : " · image + text") }), h("div", { class: "tl", text: BOARD_COLS[col] + " · rank " + rank(row, col) + " of 16" })], e.clientX, e.clientY));
      el.addEventListener("pointerleave", hideTip);
      board.append(el);
      return row;
    });
    const rank = (row, c) => 1 + rows.filter((r) => r.vals[c] > row.vals[c]).length;
    BOARD_COLS.forEach((c, i) => {
      const b = h("button", { class: "pill", type: "button", "aria-pressed": String(i === 0), text: c });
      b.addEventListener("click", () => { $$(".pill", pills).forEach((x) => x.setAttribute("aria-pressed", String(x === b))); select(i); });
      pills.append(b);
    });
    function select(c) {
      col = c;
      title.textContent = BOARD_COLS[c] + (c === 0 ? " over 300 episodes" : " · 60 episodes");
      const first = new Map(rows.map((r) => [r, r.el.getBoundingClientRect().top]));
      const order = rows.slice().sort((a, b) => b.vals[c] - a.vals[c] || (a.kind === "ours" ? -1 : b.kind === "ours" ? 1 : 0));
      order.forEach((r) => board.append(r.el));
      order.forEach((r) => {
        const rk = rank(r, c), tied = rows.some((o) => o !== r && o.vals[c] === r.vals[c]);
        r.rk.textContent = rk;
        if (r.badge) r.badge.textContent = "#" + rk + (tied ? " tied" : "");
        r.val.textContent = r.vals[c].toFixed(1);
        const w = shown ? (r.vals[c] / 70) * 100 + "%" : "0%";
        r.bar.style.width = w;
        r.bar.parentNode.style.setProperty("--w", w);
        if (!reduced && first.size) {
          const dy = first.get(r) - r.el.getBoundingClientRect().top;
          if (dy) { r.el.style.transition = "none"; r.el.style.transform = `translateY(${dy}px)`; requestAnimationFrame(() => requestAnimationFrame(() => { r.el.style.transition = "transform .7s cubic-bezier(.22,1,.36,1)"; r.el.style.transform = ""; })); }
        }
      });
    }
    select(0);
    whenVisible(board, () => { shown = true; select(col); }, 0.2);
    // table view
    $("#board-table").append(h("table", { class: "data-table" },
      h("thead", null, h("tr", null, h("th", { text: "Agent" }), h("th", { text: "Reads" }), BOARD_COLS.map((c) => h("th", { text: c })))),
      h("tbody", null, BOARD.slice().sort((a, b) => b[2][0] - a[2][0]).map(([n, kind, v]) => h("tr", { class: kind === "ours" ? "ours" : null }, h("td", { text: n }), h("td", { text: kind === "image" ? "image + text" : kind === "text" ? "text" : "text facts" }), v.map((x) => h("td", { text: x.toFixed(1) })))))));
  }

  // =====================================================================================================
  // 03: six runs, replayed
  // =====================================================================================================
  function initTheater(runs) {
    const cases = $("#cases"), view = $("#th-view"), rgb = $("#th-rgb"), dep = $("#th-depth"), ov = $("#th-overlay");
    const hud = $("#th-hud"), capEl = $("#th-caption"), metaEl = $("#th-meta"), q = $("#th-q"), res = $("#th-res");
    const mapCv = $("#th-map"), mapNote = $("#th-mapnote"), distSvg = $("#th-dist"), chain = $("#th-chain"), playBtn = $("#th-play"), split = $("#th-split");
    const probs = probRows($("#th-probs"));
    const box = frameOverlay(view, ov);
    let ri = 0, k = 0, playing = !reduced, onScreen = false, timer = 0, chainBtns = [];
    const STEP = 1900, HOLD = 3000;

    const cards = runs.map((run, i) => {
      const prog = h("i");
      const b = h("button", { class: "case", type: "button", "aria-pressed": "false" },
        h("img", { src: media(run.id, Math.min(2, run.N - 1)), alt: "", loading: "lazy" }),
        h("span", { class: "cb" }, h("span", { class: "ck", text: run.behaviour }), h("span", { class: "ct", text: run.title }),
          h("span", { class: "cv" }, icon("i-check"), `reached in ${run.N - 1} steps`)),
        h("span", { class: "cp" }, prog));
      b.addEventListener("click", () => { select(i, 0); setPlaying(true); });
      cases.append(b);
      return { b, prog };
    });

    function select(i, step) {
      ri = i;
      const run = runs[ri];
      cards.forEach((c, j) => c.b.setAttribute("aria-pressed", String(j === i)));
      metaEl.textContent = `${run.subset.replace("_", " ")} · ${run.scene} · episode ${run.episode}`;
      q.textContent = "“" + run.instruction + "”";
      const r = run.resolved;
      res.replaceChildren("Jev reads the target as ", h("b", { text: typeName(r.type) }), ` (p ${r.p.toFixed(2)}), then reaches it in `, h("b", { text: `${run.N - 1} steps` }), ".");
      chain.replaceChildren();
      chainBtns = run.frames.map((f, j) => {
        const last = j === run.N - 1;
        const b = h("button", { type: "button", class: last ? "goal" : f.ok ? null : "fail", "aria-label": last ? "Final position" : `Step ${j + 1}: ${f.action}${f.ok ? "" : ", blocked"}` },
          icon(last ? "i-check" : "a-" + f.action), h("span", { class: "n", text: last ? "" : String(j + 1) }), last ? "reached" : f.action);
        b.addEventListener("click", () => { setPlaying(false); show(j); });
        chain.append(h("li", null, b));
        return b;
      });
      run.frames.forEach((f, j) => { new Image().src = media(run.id, j); new Image().src = media(run.id, j, true); });
      show(step || 0);
    }

    function show(j) {
      k = j;
      const run = runs[ri], f = run.frames[k], last = k === run.N - 1;
      rgb.src = media(run.id, k);
      dep.src = media(run.id, k, true);
      rgb.alt = `Step ${k} of ${run.title}: camera frame`;
      box.set(last ? null : f, run.name);
      hud.className = "hud" + (last ? " goal" : f.ok ? "" : " bad");
      hud.replaceChildren(icon(last ? "i-check" : "a-" + f.action), h("span", { class: "hud-n", text: last ? "end" : `${k + 1}/${run.N - 1}` }), last ? "within 1 m" : f.action + (f.ok ? "" : " · blocked"));
      chainBtns.forEach((b, i) => { b.toggleAttribute("aria-current", i === k); if (i === k) b.setAttribute("aria-current", "step"); b.classList.toggle("future", i > k); });
      cards[ri].prog.style.transform = `scaleX(${k / (run.N - 1)})`;
      cards[ri].prog.style.transition = reduced ? "none" : `transform ${STEP}ms linear`;
      if (last) {
        capEl.replaceChildren(h("b", { text: "Reached. " }), `The robot stops ${f.dist.toFixed(2)} m from the ${run.name}, inside the 1 m success radius.`);
        probs.set(null);
      } else {
        const fa = f.facts, tg = fa.target;
        const where = { left: "to the left", right: "to the right", behind: "behind the robot", ahead: "ahead, out of detection range", above: "above the view", below: "below the view" };
        const what = tg.visible ? [cap(run.name) + " in the ", h("b", { text: tg.sector.replace("_", " ") }), " sector, " + tg.distance] : [cap(run.name) + " ", h("b", { text: "not in view" }), f.dir ? `; Jev guesses it is ${where[f.dir] || f.dir}` : ""];
        capEl.replaceChildren(...what, `. Center free ${fa.free_distance_ahead_by_sector.center}, next step ${fa.move_check.move_ahead}. Jev: `, h("b", { text: f.action }), ` (${f.p[f.action].toFixed(2)})` + (f.ok ? "." : ", which the simulator rejects: the way is blocked."));
        probs.set(f.p, f.action);
      }
      mapNote.textContent = `${f.dist.toFixed(2)} m to the ${run.name}`;
      drawMap(mapCv, run, k);
      drawDist(run, k);
      schedule();
    }

    function drawDist(run, kk) {
      const W = distSvg.clientWidth || 300, H = 118, m = { l: 30, r: 10, t: 10, b: 20 };
      const n = run.N - 1, dmax = Math.max(1.5, Math.ceil(Math.max(...run.frames.map((f) => f.dist)) * 2) / 2);
      const X = (i) => m.l + (i / n) * (W - m.l - m.r), Y = (d) => m.t + (1 - d / dmax) * (H - m.t - m.b);
      distSvg.setAttribute("viewBox", `0 0 ${W} ${H}`);
      distSvg.replaceChildren();
      const grid = cssVar("--grid"), axis = cssVar("--axis"), accent = cssVar("--accent"), ink2 = cssVar("--ink-2"), cardC = cssVar("--card");
      for (let d = 0; d <= dmax + 1e-6; d += 1) {
        distSvg.append(s("line", { x1: m.l, x2: W - m.r, y1: Y(d), y2: Y(d), stroke: d === 0 ? axis : grid, "stroke-width": 1 }));
        distSvg.append(s("text", { x: m.l - 6, y: Y(d) + 4, "text-anchor": "end", text: d + " m" }));
      }
      distSvg.append(s("line", { x1: m.l, x2: W - m.r, y1: Y(1), y2: Y(1), stroke: ink2, "stroke-width": 1 }));
      distSvg.append(s("text", { class: "thr-t", x: m.l + 4, y: Y(1) + 13, text: "within 1 m: success" }));
      const pts = run.frames.map((f, i) => [X(i), Y(f.dist)]);
      distSvg.append(s("polyline", { points: pts.map((p) => p.join(",")).join(" "), fill: "none", stroke: axis, "stroke-width": 1.5 }));
      const done = pts.slice(0, kk + 1);
      distSvg.append(s("path", { d: `M${done[0][0]},${Y(0)} L` + done.map((p) => p.join(",")).join(" L") + ` L${done[done.length - 1][0]},${Y(0)} Z`, fill: accent, opacity: 0.1 }));
      distSvg.append(s("polyline", { points: done.map((p) => p.join(",")).join(" "), fill: "none", stroke: accent, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
      distSvg.append(s("circle", { cx: pts[kk][0], cy: pts[kk][1], r: 5, fill: accent, stroke: cardC, "stroke-width": 2 }));
      distSvg.append(s("text", { x: X(0), y: H - 4, text: "step 0" }), s("text", { x: X(n), y: H - 4, "text-anchor": "end", text: "step " + n }));
      // hover: crosshair snaps to the nearest step
      const hair = s("line", { y1: m.t, y2: H - m.b, stroke: ink2, "stroke-width": 1, opacity: 0 });
      const hit = s("rect", { x: m.l, y: 0, width: W - m.l - m.r, height: H, fill: "transparent" });
      distSvg.append(hair, hit);
      hit.addEventListener("pointermove", (e) => {
        const r = distSvg.getBoundingClientRect(), i = clamp(Math.round(((e.clientX - r.left) * (W / r.width) - m.l) / ((W - m.l - m.r) / n)), 0, n);
        hair.setAttribute("x1", X(i)); hair.setAttribute("x2", X(i)); hair.setAttribute("opacity", 0.5);
        showTip([h("div", { class: "tv", text: run.frames[i].dist.toFixed(2) + " m" }), h("div", { class: "tl", text: i === n ? "final position" : `step ${i}, before ${run.frames[i].action}` })], e.clientX, e.clientY);
      });
      hit.addEventListener("pointerleave", () => { hair.setAttribute("opacity", 0); hideTip(); });
    }

    function schedule() {
      clearTimeout(timer);
      if (!playing || !onScreen) return;
      const run = runs[ri], last = k === run.N - 1;
      timer = setTimeout(() => { if (last) select((ri + 1) % runs.length, 0); else show(k + 1); }, last ? HOLD : STEP);
    }
    function setPlaying(on) {
      playing = on;
      playBtn.setAttribute("aria-pressed", String(on));
      playBtn.querySelector("span").textContent = on ? "Pause" : "Play";
      if (!on) cards[ri].prog.style.transition = "none";
      schedule();
    }
    playBtn.addEventListener("click", () => setPlaying(!playing));
    addEventListener("keydown", (e) => {
      if (!onScreen || e.target.closest("input, textarea, [role=slider], .tabs")) return;
      const run = runs[ri];
      if (e.key === "ArrowRight") { setPlaying(false); show(Math.min(k + 1, run.N - 1)); }
      if (e.key === "ArrowLeft") { setPlaying(false); show(Math.max(k - 1, 0)); }
    });
    watchVisible($("#theater"), (v) => { onScreen = v; schedule(); });
    document.addEventListener("visibilitychange", () => { onScreen = !document.hidden && onScreen; schedule(); });

    // the RGB / depth split
    let dragging = false;
    const setSplit = (pct) => { pct = clamp(pct, 0, 100); view.style.setProperty("--split", pct + "%"); split.setAttribute("aria-valuenow", Math.round(pct)); };
    const fromEvent = (e) => { const r = view.getBoundingClientRect(); setSplit(((e.clientX - r.left) / r.width) * 100); };
    split.addEventListener("pointerdown", (e) => { dragging = true; split.setPointerCapture(e.pointerId); fromEvent(e); });
    split.addEventListener("pointermove", (e) => dragging && fromEvent(e));
    split.addEventListener("pointerup", () => { dragging = false; });
    view.addEventListener("click", (e) => { if (e.target === split || split.contains(e.target)) return; fromEvent(e); });
    split.addEventListener("keydown", (e) => {
      const now = parseFloat(split.getAttribute("aria-valuenow"));
      if (e.key === "ArrowLeft") { setSplit(now - 5); e.preventDefault(); }
      if (e.key === "ArrowRight") { setSplit(now + 5); e.preventDefault(); }
    });
    setSplit(50);

    themeHooks.push(() => { const run = runs[ri]; drawDist(run, k); });
    addEventListener("resize", () => { const run = runs[ri]; drawMap(mapCv, run, k); drawDist(run, k); });
    setPlaying(playing);
    select(0, 0);
    return { play: (id) => { const i = runs.findIndex((r) => r.id === id); if (i >= 0) { select(i, 0); setPlaying(true); } } };
  }

  // =====================================================================================================
  // 04: all 300 episodes
  // =====================================================================================================
  function initAll(runs, featuredIds, theater) {
    const atlas = $("#atlas"), side = $("#atlas-side"), pills = $("#all-pills"), cv = $("#curves"), sub = $("#curves-sub");
    let filter = -1, hover = null, pinned = null, drawn = [];
    runs.forEach((r) => { r.dist = r.d; r.n = r.a.length; r.sub = SUBSETS[r.s][1]; });
    const byKey = new Map(runs.map((r) => [r.s + ":" + r.e, r]));

    // filters
    ["All", ...SUBSETS.map((x) => x[1])].forEach((label, i) => {
      const b = h("button", { class: "pill", type: "button", "aria-pressed": String(i === 0), text: label });
      b.addEventListener("click", () => { filter = i - 1; $$(".pill", pills).forEach((x) => x.setAttribute("aria-pressed", String(x === b))); applyFilter(); });
      pills.append(b);
    });

    // the grid: rows are instruction styles, columns are scenes
    const cellEls = new Map();
    SUBSETS.forEach(([, label], si) => {
      const ok = runs.filter((r) => r.s === si && r.ok).length;
      atlas.append(h("div", { class: "rl", text: `${label} · ${ok}`, title: `${label}: ${ok} of 60 reached`, style: `grid-row:${si + 1};grid-column:1` }));
      for (let e = 1; e <= 60; e++) {
        const r = byKey.get(si + ":" + e);
        const c = h("button", { class: "cell" + (r.ok ? " ok" : ""), type: "button", style: `--dr:${si + 1};--dc:${e + 1};--mr:${e};--mc:${si + 1};--r:${si};--c:${e}`,
          "aria-label": `${label}, scene ${e}: ${r.ok ? "reached" : "not reached"}, target ${typeName(r.t)}` });
        c.addEventListener("pointerenter", (ev) => { enter(r); tipFor(r, ev.clientX, ev.clientY); });
        c.addEventListener("pointermove", (ev) => tipFor(r, ev.clientX, ev.clientY));
        c.addEventListener("pointerleave", leave);
        c.addEventListener("focus", () => { const b = c.getBoundingClientRect(); enter(r); tipFor(r, b.right, b.bottom); });
        c.addEventListener("blur", leave);
        c.addEventListener("click", () => {
          pinned = pinned === r ? null : r;
          $$(".cell.sel", atlas).forEach((x) => x.classList.remove("sel"));
          if (pinned) c.classList.add("sel");
          const feat = featuredIds[r.s + ":" + r.e];
          if (feat && pinned) { theater.play(feat); $("#runs").scrollIntoView({ behavior: reduced ? "auto" : "smooth" }); }
          drawCurves();
        });
        cellEls.set(r, c);
        atlas.append(c);
      }
    });
    atlas.append(h("div", { class: "ax", style: "grid-row:6" }, h("span", { text: "scene 1" }), h("span", { text: "scene 30" }), h("span", { text: "scene 60" })));
    whenVisible(atlas, () => { if (!reduced) atlas.classList.add("pop"); }, 0.2);

    function tipFor(r, x, y) {
      const right = r.rt === r.t;
      showTip([
        h("img", { src: `media/thumbs/${r.th}.webp`, alt: "" }),
        h("div", { class: "tl", text: `${SUBSETS[r.s][1]} · FloorPlan${r.sc} · episode ${r.e}` }),
        h("p", { class: "tq", text: "“" + r.i + "”" }),
        h("div", { class: "tl", text: `Target ${typeName(r.t)}; Jev read ${typeName(r.rt || "?")}${right ? "" : " (wrong type)"}` }),
        h("div", { class: "tr " + (r.ok ? "ok" : "no") }, icon(r.ok ? "i-check" : "i-x"), r.ok ? `Reached in ${r.n} steps, ${r.dist[r.dist.length - 1].toFixed(2)} m away` : `Not reached: ${r.dist[r.dist.length - 1].toFixed(2)} m away after ${r.n} steps`),
        featuredIds[r.s + ":" + r.e] ? h("div", { class: "tl", text: "Click to replay it above." }) : null,
      ], x, y);
    }
    function enter(r) {
      hover = r;
      $$(".cell.col", atlas).forEach((x) => x.classList.remove("col"));
      SUBSETS.forEach((_, si) => { const o = byKey.get(si + ":" + r.e); if (o !== r) cellEls.get(o).classList.add("col"); });
      drawCurves();
    }
    function leave() { hover = null; hideTip(); $$(".cell.col", atlas).forEach((x) => x.classList.remove("col")); drawCurves(); }
    function applyFilter() {
      runs.forEach((r) => cellEls.get(r).classList.toggle("dim", filter >= 0 && r.s !== filter));
      drawCurves();
      const sel = runs.filter((r) => filter < 0 || r.s === filter), ok = sel.filter((r) => r.ok).length;
      sub.textContent = `${filter < 0 ? "All styles" : SUBSETS[filter][1]}: ${ok} of ${sel.length} reached`;
    }

    // per-style success
    const bars = SUBSETS.map(([, label], si) => {
      const ok = runs.filter((r) => r.s === si && r.ok).length, fill = h("div", { class: "sf" });
      side.append(h("div", { class: "sbar" }, h("div", { class: "sh" }, h("span", { text: label }), h("b", { text: `${((ok / 60) * 100).toFixed(1)}%` })), h("div", { class: "st" }, fill)));
      return [fill, ok / 60];
    });
    const all = runs.filter((r) => r.ok).length, allFill = h("div", { class: "sf" });
    side.append(h("div", { class: "sbar all" }, h("div", { class: "sh" }, h("span", { text: "All 300" }), h("b", { text: `${((all / 300) * 100).toFixed(1)}%` })), h("div", { class: "st" }, allFill)));
    bars.push([allFill, all / 300]);
    whenVisible(side, () => bars.forEach(([f, v]) => { f.style.width = v * 100 + "%"; }));

    // distance curves
    function drawCurves() {
      const { g, W, H } = sizeCanvas(cv);
      if (!W) return;
      const m = { l: 40, r: 16, t: 14, b: 30 }, ymax = Math.ceil(Math.max(...runs.map((r) => Math.max(...r.dist))) * 2) / 2;
      const X = (i) => m.l + (i / 20) * (W - m.l - m.r), Y = (d) => m.t + (1 - Math.min(d, ymax) / ymax) * (H - m.t - m.b);
      const grid = cssVar("--grid"), axis = cssVar("--axis"), muted = cssVar("--muted"), ink2 = cssVar("--ink-2"), good = cssVar("--good"), base = cssVar("--base-bar"), ink = cssVar("--ink"), card = cssVar("--card");
      g.font = "400 11px Inter, system-ui, sans-serif";
      for (let d = 0; d <= ymax; d++) {
        g.strokeStyle = d === 0 ? axis : grid; g.lineWidth = 1;
        g.beginPath(); g.moveTo(m.l, Math.round(Y(d)) + 0.5); g.lineTo(W - m.r, Math.round(Y(d)) + 0.5); g.stroke();
        g.fillStyle = muted; g.textAlign = "right"; g.fillText(d + " m", m.l - 8, Y(d) + 4);
      }
      g.textAlign = "center";
      for (let i = 0; i <= 20; i += 5) { g.textAlign = i === 0 ? "left" : i === 20 ? "right" : "center"; g.fillText(i === 0 ? "start" : "step " + i, X(i), H - 10); }
      drawn = [];
      const visible = runs.filter((r) => filter < 0 || r.s === filter);
      const pass = (okPass) => visible.forEach((r) => {
        if (!!r.ok !== okPass) return;
        g.strokeStyle = r.ok ? good : base;
        g.globalAlpha = r.ok ? 0.34 : 0.3;
        g.lineWidth = 1.2;
        g.beginPath();
        const pts = r.dist.map((d, i) => [X(i), Y(d)]);
        pts.forEach((p, i) => (i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1])));
        g.stroke();
        drawn.push([r, pts]);
      });
      pass(false); pass(true);
      g.globalAlpha = 1;
      // 1 m: success
      g.strokeStyle = ink2; g.lineWidth = 1;
      g.beginPath(); g.moveTo(m.l, Math.round(Y(1)) + 0.5); g.lineTo(W - m.r, Math.round(Y(1)) + 0.5); g.stroke();
      g.fillStyle = ink2; g.textAlign = "left"; g.font = "500 11.5px Inter, system-ui, sans-serif";
      g.fillText("within 1 m: success", m.l + 6, Y(1) + 16);
      const focus = hover || pinned;
      if (focus) {
        const pts = focus.dist.map((d, i) => [X(i), Y(d)]);
        g.strokeStyle = card; g.lineWidth = 5; g.beginPath(); pts.forEach((p, i) => (i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1]))); g.stroke();
        g.strokeStyle = focus.ok ? good : ink; g.lineWidth = 2.4; g.beginPath(); pts.forEach((p, i) => (i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1]))); g.stroke();
        const e = pts[pts.length - 1];
        g.beginPath(); g.arc(e[0], e[1], 4.5, 0, Math.PI * 2); g.fillStyle = focus.ok ? good : ink; g.fill(); g.lineWidth = 2; g.strokeStyle = card; g.stroke();
      }
    }
    // hover on the curves: the nearest line within 14 px
    function nearest(px, py) {
      let best = null, bd = 14;
      for (const [r, pts] of drawn) {
        for (let i = 1; i < pts.length; i++) {
          const [x1, y1] = pts[i - 1], [x2, y2] = pts[i], dx = x2 - x1, dy = y2 - y1, L = dx * dx + dy * dy;
          const t = L ? clamp(((px - x1) * dx + (py - y1) * dy) / L, 0, 1) : 0, d = Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
          if (d < bd) { bd = d; best = r; }
        }
      }
      return best;
    }
    cv.addEventListener("pointermove", (e) => {
      const r = cv.getBoundingClientRect(), hit = nearest(e.clientX - r.left, e.clientY - r.top);
      if (hit !== hover) { hover = hit; drawCurves(); }
      if (hit) tipFor(hit, e.clientX, e.clientY); else hideTip();
    });
    cv.addEventListener("pointerleave", () => { hover = null; hideTip(); drawCurves(); });
    themeHooks.push(drawCurves);
    addEventListener("resize", drawCurves);
    applyFilter();

    // table view: success per style
    $("#subset-table").append(h("table", { class: "data-table" },
      h("thead", null, h("tr", null, ["Instruction style", "Reached", "Rate", "Mean steps", "Mean final distance"].map((t) => h("th", { text: t })))),
      h("tbody", null, [...SUBSETS.map(([, label], si) => runs.filter((r) => r.s === si)), runs].map((rs, i) => {
        const ok = rs.filter((r) => r.ok).length, steps = rs.reduce((a, r) => a + r.n, 0) / rs.length, fd = rs.reduce((a, r) => a + r.dist[r.dist.length - 1], 0) / rs.length;
        return h("tr", null, h("td", { text: i < 5 ? SUBSETS[i][1] : "All" }), h("td", { text: `${ok}/${rs.length}` }), h("td", { text: ((ok / rs.length) * 100).toFixed(1) + "%" }), h("td", { text: steps.toFixed(1) }), h("td", { text: fd.toFixed(2) + " m" }));
      }))));
  }

  // =====================================================================================================
  // 05: latency
  // =====================================================================================================
  function initLatency(st) {
    const parts = [["depth", "DA3 depth", "s-depth"], ["detect", "OWLv2 detection", "s-det"], ["jev", "Jev decision", "s-jev"], ["rest", "Rest of the step", "s-rest"]];
    const groups = [["One run per GPU", st.single], ["Three runs per GPU", st.shared]];
    groups.forEach(([, g]) => { g.rest = Math.max(0, g.step - g.depth - g.detect - g.jev); });
    const lat = $("#latency"), axis = $("#lat-axis"), legend = $("#latency-legend"), max = 1.2;
    parts.forEach(([, label, cls]) => legend.append(h("span", null, h("i", { class: "sw " + cls.replace("s-", "sl-") }), label)));
    $$("#latency-legend .sw").forEach((sw, i) => { sw.style.background = ["var(--depth)", "var(--det)", "var(--jev)", "var(--base-bar)"][i]; });
    const segs = [];
    groups.forEach(([name, g]) => {
      const bar = h("div", { class: "lat-bar" });
      parts.forEach(([key, label, cls]) => {
        const seg = h("div", { class: "seg-l " + cls, style: `width:0%` }, h("span", { class: "lt", text: g[key].toFixed(2) + " s" }));
        seg.addEventListener("pointermove", (e) => showTip([h("div", { class: "tv", text: g[key].toFixed(3) + " s" }), h("div", { text: label }), h("div", { class: "tl", text: `${name}, mean over ${g.steps.toLocaleString("en-US")} steps` })], e.clientX, e.clientY));
        seg.addEventListener("pointerleave", hideTip);
        bar.append(seg);
        segs.push([seg, (g[key] / max) * 100]);
      });
      lat.append(h("div", { class: "lat-row" }, h("div", { class: "ln-name" }, h("b", { text: g.step.toFixed(2) + " s" }), name), bar));
    });
    for (let t = 0; t <= max + 1e-9; t += 0.2) axis.append(h("span", { style: `left:${(t / max) * 100}%`, text: t.toFixed(1) + " s" }));
    const fit = () => segs.forEach(([seg]) => seg.classList.toggle("tight", seg.getBoundingClientRect().width < 52));
    whenVisible(lat, () => { segs.forEach(([seg, w]) => { seg.style.width = w + "%"; }); setTimeout(fit, reduced ? 0 : 900); });
    $$(".seg-l", lat).forEach((x) => { x.style.transition = "width .9s cubic-bezier(.22,1,.36,1)"; });
    addEventListener("resize", fit);
    $("#latency-table").append(h("table", { class: "data-table" },
      h("thead", null, h("tr", null, h("th", { text: "Setup" }), parts.map((p) => h("th", { text: p[1] })), h("th", { text: "Whole step" }), h("th", { text: "Steps" }))),
      h("tbody", null, groups.map(([name, g]) => h("tr", null, h("td", { text: name }), parts.map((p) => h("td", { text: g[p[0]].toFixed(3) + " s" })), h("td", { text: g.step.toFixed(3) + " s" }), h("td", { text: g.steps.toLocaleString("en-US") }))))));
    const kpi = $$(".kpi span")[2];
    if (kpi && st.all) kpi.textContent = `images reach the decision model, only ~${(st.all.tokens / 1000).toFixed(1)}k tokens of text per step`;
  }

  // =====================================================================================================
  // 06: failures, 07: code tree, copy buttons, KPIs, the hero field
  // =====================================================================================================
  function initFails() {
    const F = [["Target rarely detected or wrongly identified", 51], ["Sidestepping left and right without progress", 40], ["Stuck against an obstacle", 32], ["Distance underestimated or a false detection", 27], ["Other", 10]];
    const box = $("#fails"), fills = [];
    F.forEach(([label, n]) => { const f = h("div", { class: "ff" }); fills.push([f, n]); box.append(h("div", { class: "frow" }, h("div", { class: "fh" }, h("span", { text: label }), h("b", { text: n })), h("div", { class: "ft" }, f))); });
    whenVisible(box, () => fills.forEach(([f, n]) => { f.style.width = (n / 51) * 100 + "%"; }));
  }

  function initTree() {
    const G = "https://github.com/ZJUCQR/DepthJev/";
    const T = [
      ["", "depthjev/", "the agent: one sub-package per stage", "tree/main/depthjev", null, true],
      ["├── ", "perception/", "the frame becomes metres", "tree/main/depthjev/perception", "var(--depth)", true],
      ["│   ├── ", "depth.py", "Depth Anything 3 metric depth", "blob/main/depthjev/perception/depth.py"],
      ["│   ├── ", "detection.py", "OWLv2 open-vocabulary detection", "blob/main/depthjev/perception/detection.py"],
      ["│   └── ", "geometry.py", "floor, free space per sector, step collision, target range", "blob/main/depthjev/perception/geometry.py"],
      ["├── ", "language/", "metres and history become text", "tree/main/depthjev/language", "var(--textc)", true],
      ["│   ├── ", "prompt.py", "instruction and action history from the EmbodiedBench prompt", "blob/main/depthjev/language/prompt.py"],
      ["│   ├── ", "facts.py", "distance bins, move checks, search status, the JSON state", "blob/main/depthjev/language/facts.py"],
      ["│   ├── ", "actions.py", "the eight actions and how Jev sees them", "blob/main/depthjev/language/actions.py"],
      ["│   └── ", "objects.py", "the 125 iTHOR object types and detector aliases", "blob/main/depthjev/language/objects.py"],
      ["├── ", "decision/", "the text becomes an action", "tree/main/depthjev/decision", "var(--jev)", true],
      ["│   ├── ", "jev.py", "Jev client and its three questions", "blob/main/depthjev/decision/jev.py"],
      ["│   └── ", "policy.py", "one step: parse, depth, detect, facts, Jev, reply", "blob/main/depthjev/decision/policy.py"],
      ["├── ", "server.py", "HTTP endpoint for EmbodiedBench", "blob/main/depthjev/server.py"],
      ["└── ", "evaluation/", "Python 3.9: launch EmbodiedBench, report results", "tree/main/depthjev/evaluation", null, true],
      ["", "scripts/", "run.sh, server.sh, eval.sh", "tree/main/scripts", null, true],
      ["", "third_party/", "EmbodiedBench and Depth Anything 3, pinned", "tree/main/third_party", null, true],
      ["", "requirements.txt", "both environments, chosen by Python version", "blob/main/requirements.txt"],
    ];
    const box = $("#tree");
    T.forEach(([glyph, name, desc, path, color, layer]) => box.append(h("a", { class: "trow" + (layer ? " layer" : ""), href: G + path },
      h("span", { class: "tn" }, h("span", { class: "g", text: glyph }), color ? h("i", { class: "ld", style: "background:" + color }) : null, layer ? h("b", { text: name }) : name),
      h("span", { class: "td", text: desc }))));
  }

  function initCopy() {
    $$("[data-copy]").forEach((b) => b.addEventListener("click", async () => {
      const text = document.getElementById(b.dataset.copy).textContent;
      try { await navigator.clipboard.writeText(text); } catch (e) {
        const ta = h("textarea", { style: "position:fixed;opacity:0" }); ta.value = text; document.body.append(ta); ta.select(); document.execCommand("copy"); ta.remove();
      }
      b.textContent = "Copied";
      setTimeout(() => { b.textContent = "Copy"; }, 1600);
    }));
  }

  function initKPIs() {
    const els = $$(".kpi b[data-count]").filter((b) => parseFloat(b.dataset.count) > 0);
    if (reduced) return;
    els.forEach((b) => { b.dataset.final = b.textContent; });
    whenVisible($(".kpis"), () => {
      const t0 = performance.now(), dur = 1300;
      const step = (now) => {
        const p = clamp((now - t0) / dur, 0, 1), e = 1 - Math.pow(1 - p, 3);
        els.forEach((b) => { const v = parseFloat(b.dataset.count) * e; b.textContent = v.toFixed(+b.dataset.dec) + (b.dataset.suffix || ""); });
        if (p < 1) requestAnimationFrame(step); else els.forEach((b) => { b.textContent = b.dataset.final; });
      };
      requestAnimationFrame(step);
    }, 0.4);
  }

  // a depth field streaming towards the viewer: points on the floor and on a few obstacles, coloured by distance
  function initField() {
    const cv = $("#field"), heat = [[246, 213, 67], [243, 118, 27], [180, 51, 89], [85, 15, 109]];
    const col = (t) => { const x = clamp(t, 0, 0.999) * 3, i = Math.floor(x), f = x - i, a = heat[i], b = heat[i + 1]; return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f]; };
    const pts = Array.from({ length: 640 }, () => spawn({}, true));
    function spawn(p, anywhere) {
      p.x = (Math.random() * 2 - 1) * 9;
      p.z = anywhere ? 1 + Math.random() * 34 : 30 + Math.random() * 6;
      const wall = Math.random() < 0.18;
      p.y = wall ? 1.55 - Math.random() * 2.6 : 1.55;
      p.x = wall ? (Math.random() < 0.5 ? -1 : 1) * (2.4 + Math.random() * 5) : p.x;
      return p;
    }
    let raf = 0, run = !reduced, last = performance.now();
    function frame(now) {
      const dt = Math.min(50, now - last); last = now;
      const { g, W, H } = sizeCanvas(cv);
      const f = W * 0.58, hy = H * 0.3, cx = W * 0.5;
      for (const p of pts) {
        if (run) { p.z -= dt * 0.0012; if (p.z < 0.7) spawn(p, false); }
        const sx = cx + (p.x / p.z) * f, sy = hy + (p.y / p.z) * f;
        if (sx < -10 || sx > W + 10 || sy < -10 || sy > H + 10) continue;
        const t = (Math.log(p.z) - Math.log(0.7)) / (Math.log(36) - Math.log(0.7)), c = col(t);
        const a = Math.min(1, (36 - p.z) / 8) * Math.min(1, (p.z - 0.7) / 1.5) * 0.7, r = Math.max(0.6, 3 / Math.sqrt(p.z));
        g.fillStyle = `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a.toFixed(3)})`;
        g.beginPath(); g.arc(sx, sy, r, 0, Math.PI * 2); g.fill();
      }
      if (run) raf = requestAnimationFrame(frame);
    }
    watchVisible(heroEl, (v) => { cancelAnimationFrame(raf); run = v && !reduced; last = performance.now(); raf = requestAnimationFrame(frame); });
    addEventListener("resize", () => { if (!run) requestAnimationFrame(frame); });
    requestAnimationFrame(frame);
  }

  // the hero fan: the five sectors seen from above, with the free floor DA3 measured in each (pasta, step 1)
  function initFan(f) {
    const svg = $("#fan");
    if (!svg) return;
    const O = [300, 410], k = 88; // px per metre, forward distance on a linear scale
    const P = (x, z) => [O[0] + x * k, O[1] - z * k];
    const pt = (x, z) => P(x, z).map((v) => v.toFixed(1)).join(",");
    const defs = s("defs", null,
      s("radialGradient", { id: "fan-glow", cx: O[0], cy: O[1], r: 420, gradientUnits: "userSpaceOnUse" },
        s("stop", { offset: "0", "stop-color": "#f6d543", "stop-opacity": ".22" }), s("stop", { offset: ".45", "stop-color": "#f3761b", "stop-opacity": ".08" }), s("stop", { offset: "1", "stop-color": "#8a226a", "stop-opacity": "0" })),
      s("linearGradient", { id: "fan-beam", x1: "0", y1: "1", x2: "0", y2: "0" },
        s("stop", { offset: "0", "stop-color": "#fff8d6", "stop-opacity": ".55" }), s("stop", { offset: "1", "stop-color": "#fff8d6", "stop-opacity": "0" })));
    svg.append(defs);
    const half = (50 * Math.PI) / 180, zmax = 4.4;
    svg.append(s("path", { d: `M${pt(0, 0)} L${pt(-Math.tan(half) * zmax, zmax)} L${pt(Math.tan(half) * zmax, zmax)} Z`, fill: "url(#fan-glow)" }));
    // free floor per sector, up to the nearest obstacle
    SECTORS.forEach((sec, i) => {
      const v = f.free[sec], F = Math.min(v == null ? zmax : v, zmax), t0 = Math.tan(EDGES[i]), t1 = Math.tan(EDGES[i + 1]);
      const col = BIN_HEX[BIN[f.facts.free_distance_ahead_by_sector[sec]]];
      svg.append(s("path", { class: "fan-free", d: `M${pt(0, 0)} L${pt(t0 * F, F)} L${pt(t1 * F, F)} Z`, fill: col }));
      if (v != null) svg.append(s("line", { class: "fan-wall", x1: P(t0 * F, F)[0], y1: P(t0 * F, F)[1], x2: P(t1 * F, F)[0], y2: P(t1 * F, F)[1], stroke: col, color: col }));
      const mid = (t0 + t1) / 2, lz = Math.min(zmax, F) + 0.28;
      svg.append(s("text", { x: P(mid * lz, lz)[0], y: P(mid * lz, lz)[1], "text-anchor": "middle", text: v == null ? "> 4 m" : v.toFixed(2) + " m" }));
    });
    // range rings and sector edges
    [1, 2, 3, 4].forEach((z) => {
      const r = z * k, a = P(-Math.sin(half) * z, Math.cos(half) * z), b = P(Math.sin(half) * z, Math.cos(half) * z);
      svg.append(s("path", { class: "fan-ring", d: `M${a[0]},${a[1]} A${r},${r} 0 0 1 ${b[0]},${b[1]}` }));
    });
    EDGES.forEach((e) => svg.append(s("line", { class: "fan-edge", x1: O[0], y1: O[1], x2: P(Math.sin(e) * 4.6, Math.cos(e) * 4.6)[0], y2: P(Math.sin(e) * 4.6, Math.cos(e) * 4.6)[1] })));
    // the sweeping beam and the robot
    if (!reduced) svg.append(s("path", { class: "fan-beam", d: `M${O[0]},${O[1]} L${O[0] - 14},${O[1] - 400} L${O[0] + 14},${O[1] - 400} Z`, fill: "url(#fan-beam)" }));
    svg.append(s("path", { d: `M${O[0]} ${O[1] - 12} l-8 16 h16 z`, fill: "#f6d543" }));
    svg.append(s("text", { x: O[0], y: O[1] + 24, "text-anchor": "middle", text: "free floor per sector, from DA3 depth" }));
  }

  // ---------- start ----------
  initBoard();
  initFails();
  initTree();
  initCopy();
  initKPIs();
  initField();
  Promise.all([getJSON("data/featured.json"), getJSON("data/runs.json"), getJSON("data/stats.json")]).then(([featured, runs, stats]) => {
    featured.forEach(prepRun);
    const byId = Object.fromEntries(featured.map((r) => [r.id, r]));
    const featuredIds = {};
    featured.forEach((r) => { featuredIds[SUBSETS.findIndex((x) => x[0] === r.subset) + ":" + r.episode] = r.id; });
    initFan(byId.pasta.frames[0]);
    initHero(byId.pasta);
    initAnatomy(byId);
    const theater = initTheater(featured);
    initAll(runs, featuredIds, theater);
    initLatency(stats);
  }).catch((err) => {
    console.error(err);
    $$("#hero, #anatomy, #theater").forEach((el) => el.prepend(h("p", { class: "cell-note", text: "The recorded runs could not be loaded: " + err.message })));
  });
})();
