/* Assistente Nexo — chat RAG (HTML/CSS/JS puro, sem build)
 *
 * Parâmetros de URL:
 *   ?mock=1                 → modo demo, respostas falsas no formato do contrato (sem backend)
 *   ?api=http://host:porta  → URL da API (padrão http://localhost:8000; fica salva no navegador)
 *   ?top_k=4                → nº de trechos recuperados
 */
(() => {
  "use strict";

  // ---------------- Configuração ----------------
  const params = new URLSearchParams(location.search);
  const MOCK = params.get("mock") === "1";
  const NOT_FOUND = "Não encontrei essa informação nos documentos internos.";
  const TOP_K = Math.max(1, Math.min(10, parseInt(params.get("top_k") || "4", 10) || 4));
  const REQUEST_TIMEOUT_MS = 90000;

  const API_BASE = (() => {
    const fromUrl = params.get("api");
    try {
      if (fromUrl) localStorage.setItem("nexo_api", fromUrl);
      return (fromUrl || localStorage.getItem("nexo_api") || "http://localhost:8000").replace(/\/+$/, "");
    } catch {
      return (fromUrl || "http://localhost:8000").replace(/\/+$/, "");
    }
  })();

  // ---------------- Elementos ----------------
  const $ = (sel) => document.querySelector(sel);
  const chatEl = $("#chat");
  const messagesEl = $("#messages");
  const welcomeEl = $("#welcome");
  const form = $("#composer");
  const input = $("#question");
  const sendBtn = $("#send");
  const statusBtn = $("#apiStatus");
  const popover = $("#popover");

  const LOGO_SVG = `<svg viewBox="0 0 40 40" aria-hidden="true"><rect width="40" height="40" rx="11" fill="url(#lg)"/><path d="M12 28V12l16 16V12" stroke="#fff" stroke-width="3.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/><circle cx="28" cy="12" r="3.4" fill="#FF6F59"/></svg>`;

  let busy = false;
  let msgSeq = 0;

  if (MOCK) $("#mockBadge").hidden = false;

  // ---------------- Utilidades ----------------
  const escapeHtml = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const fmtLatency = (ms) =>
    ms == null ? "" : ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} s`;

  const fmtScore = (s) => (typeof s === "number" ? s.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "–");
  const scorePct = (s) => (typeof s === "number" ? Math.max(4, Math.min(100, s * 100)) : 0);

  const isNotFound = (answer) => (answer || "").toLowerCase().includes("não encontrei essa informação");

  function scrollToBottom() {
    requestAnimationFrame(() => { chatEl.scrollTop = chatEl.scrollHeight; });
  }

  // Markdown mínimo: parágrafos, listas, **negrito**, *itálico*
  function renderMarkdown(text) {
    const lines = escapeHtml(text.trim()).split(/\r?\n/);
    let html = "";
    let list = null; // "ul" | "ol"
    let para = [];
    const inline = (s) => s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/(^|[^*])\*(?!\s)(.+?)\*/g, "$1<em>$2</em>");
    const flushPara = () => { if (para.length) { html += `<p>${inline(para.join("<br>"))}</p>`; para = []; } };
    const closeList = () => { if (list) { html += `</${list}>`; list = null; } };

    for (const raw of lines) {
      const line = raw.trim();
      const ul = line.match(/^[-*•]\s+(.*)$/);
      const ol = line.match(/^\d+[.)]\s+(.*)$/);
      if (ul || ol) {
        flushPara();
        const kind = ul ? "ul" : "ol";
        if (list !== kind) { closeList(); html += `<${kind}>`; list = kind; }
        html += `<li>${inline((ul || ol)[1])}</li>`;
      } else if (!line) {
        flushPara(); closeList();
      } else {
        closeList(); para.push(line);
      }
    }
    flushPara(); closeList();
    return html;
  }

  // Transforma [1], [1, 2], [1][2] em botões de citação ligados às fontes
  function linkCitations(html, sources, msgId) {
    const valid = new Set(sources.map((s) => Number(s.n)));
    return html.replace(/\[(\d+(?:\s*[,;]\s*\d+)*)\]/g, (match, group) => {
      const nums = group.split(/\s*[,;]\s*/).map(Number);
      if (!nums.every((n) => valid.has(n))) return match;
      return nums
        .map((n) => `<button type="button" class="cite" data-msg="${msgId}" data-n="${n}" aria-label="Fonte ${n}">${n}</button>`)
        .join("");
    });
  }

  // ---------------- Renderização ----------------
  function hideWelcome() { welcomeEl.hidden = true; }

  function addUserMessage(text) {
    const el = document.createElement("div");
    el.className = "msg msg-user";
    el.innerHTML = `<div class="bubble-user">${escapeHtml(text)}</div>`;
    messagesEl.appendChild(el);
    scrollToBottom();
  }

  function botShell() {
    const el = document.createElement("div");
    el.className = "msg msg-bot";
    el.innerHTML = `<div class="avatar">${LOGO_SVG}</div><div class="bot-body"></div>`;
    messagesEl.appendChild(el);
    return el;
  }

  function addThinking() {
    const el = botShell();
    el.querySelector(".bot-body").innerHTML =
      `<div class="thinking"><span class="dots"><i></i><i></i><i></i></span><span class="thinking-text">Pensando…</span></div>`;
    const textEl = el.querySelector(".thinking-text");
    const stages = ["Pensando…", "Buscando nos documentos internos…", "Lendo os trechos mais relevantes…", "Escrevendo a resposta com fontes…"];
    let i = 0;
    const timer = setInterval(() => {
      i = Math.min(i + 1, stages.length - 1);
      textEl.style.opacity = 0;
      setTimeout(() => { textEl.textContent = stages[i]; textEl.style.opacity = 1; }, 200);
    }, 1600);
    scrollToBottom();
    return { remove() { clearInterval(timer); el.remove(); } };
  }

  const sourcesStore = new Map(); // msgId -> sources[]

  function addBotAnswer(data) {
    const msgId = `m${++msgSeq}`;
    const sources = Array.isArray(data.sources) ? data.sources : [];
    sourcesStore.set(msgId, sources);
    const notFound = isNotFound(data.answer);

    const el = botShell();
    const body = el.querySelector(".bot-body");

    const answerHtml = notFound
      ? `<div class="notfound-head">
           <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="2" fill="none"/><path d="M20 20l-4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
           Sem resposta na base</div>${renderMarkdown(data.answer || NOT_FOUND)}`
      : linkCitations(renderMarkdown(data.answer || ""), sources, msgId);

    const cited = new Set(Array.from((data.answer || "").matchAll(/\[(\d+(?:\s*[,;]\s*\d+)*)\]/g))
      .flatMap((m) => m[1].split(/\s*[,;]\s*/).map(Number)));

    let sourcesHtml = "";
    if (!notFound && sources.length) {
      sourcesHtml = `<div class="sources">
        <div class="sources-title">Fontes consultadas</div>
        <div class="source-list">${sources.map((s) => `
          <button type="button" class="source" id="${msgId}-src-${s.n}" data-n="${s.n}" aria-expanded="false" title="${cited.has(Number(s.n)) ? "Citada na resposta" : "Recuperada, não citada"}">
            <span class="source-n">${escapeHtml(s.n)}</span>
            <span class="source-main">
              <span class="source-title" style="display:block">${escapeHtml(s.titulo || s.doc_id)}</span>
              <span class="source-doc">${escapeHtml(s.doc_id)}${cited.has(Number(s.n)) ? " · citada" : ""}</span>
              <span class="source-snippet">${escapeHtml(s.trecho)}</span>
            </span>
            <span class="score" title="Similaridade">${fmtScore(s.score)}<span class="score-bar"><span style="width:${scorePct(s.score)}%"></span></span></span>
          </button>`).join("")}
        </div></div>`;
    }

    body.innerHTML = `
      <div class="bubble-bot${notFound ? " notfound" : ""}">${answerHtml}</div>
      ${sourcesHtml}
      <div class="meta">
        ${data.latency_ms != null ? `<span title="Tempo de resposta">⏱ ${fmtLatency(data.latency_ms)}</span><span class="sep">•</span>` : ""}
        <span>${notFound ? "nenhum trecho relevante" : `${sources.length} ${sources.length === 1 ? "fonte" : "fontes"}`}</span>
        <span class="sep">•</span>
        <button type="button" class="copy-btn">Copiar</button>
      </div>`;

    body.querySelectorAll(".source").forEach((btn) =>
      btn.addEventListener("click", () => {
        const open = btn.classList.toggle("open");
        btn.setAttribute("aria-expanded", String(open));
      })
    );
    body.querySelector(".copy-btn").addEventListener("click", async (e) => {
      const plain = (data.answer || "") + (sources.length && !notFound
        ? "\n\nFontes:\n" + sources.map((s) => `[${s.n}] ${s.titulo} (${s.doc_id})`).join("\n") : "");
      try { await navigator.clipboard.writeText(plain); e.target.textContent = "Copiado ✓"; }
      catch { e.target.textContent = "Não foi possível copiar"; }
      setTimeout(() => (e.target.textContent = "Copiar"), 1800);
    });

    scrollToBottom();
  }

  function addError(err, question) {
    const el = botShell();
    let title, detail;
    if (err.kind === "offline") {
      title = "Não consegui falar com a API.";
      detail = `Verifique se o backend está rodando em <code>${escapeHtml(API_BASE)}</code> (ex.: <code>uvicorn api.main:app --port 8000</code>). Para uma demonstração sem backend, abra com <code>?mock=1</code>.`;
    } else if (err.kind === "timeout") {
      title = "A resposta demorou demais.";
      detail = "A API não respondeu a tempo. Tente novamente em instantes.";
    } else {
      title = "Algo deu errado ao gerar a resposta.";
      detail = escapeHtml(err.message || "Erro inesperado.");
    }
    el.querySelector(".bot-body").innerHTML =
      `<div class="bubble-error"><strong>${title}</strong>${detail}<br><button type="button" class="retry">Tentar novamente</button></div>`;
    el.querySelector(".retry").addEventListener("click", () => { el.remove(); ask(question, { skipUser: true }); });
    scrollToBottom();
  }

  // ---------------- Popover das citações ----------------
  let popTimer = null;
  let pinned = null;

  function showPopover(btn) {
    clearTimeout(popTimer);
    const sources = sourcesStore.get(btn.dataset.msg) || [];
    const s = sources.find((x) => Number(x.n) === Number(btn.dataset.n));
    if (!s) return;
    document.querySelectorAll(".cite.active").forEach((c) => c !== btn && c.classList.remove("active"));
    btn.classList.add("active");
    popover.innerHTML = `
      <div class="pop-head"><span class="pop-n">${escapeHtml(s.n)}</span><span class="pop-title">${escapeHtml(s.titulo || s.doc_id)}</span></div>
      <div class="pop-doc">${escapeHtml(s.doc_id)}</div>
      <div class="pop-snippet">${escapeHtml(s.trecho)}</div>
      <div class="pop-score">Similaridade <strong style="color:#fff">${fmtScore(s.score)}</strong><span class="score-bar"><span style="width:${scorePct(s.score)}%"></span></span></div>`;
    popover.hidden = false;
    const r = btn.getBoundingClientRect();
    const pw = popover.offsetWidth, ph = popover.offsetHeight;
    let left = Math.min(Math.max(16, r.left + r.width / 2 - pw / 2), window.innerWidth - pw - 16);
    let top = r.top - ph - 10;
    if (top < 12) top = r.bottom + 10;
    popover.style.left = `${left}px`;
    popover.style.top = `${top}px`;
  }

  function hidePopover(force) {
    if (pinned && !force) return;
    popTimer = setTimeout(() => {
      popover.hidden = true;
      document.querySelectorAll(".cite.active").forEach((c) => c.classList.remove("active"));
      pinned = null;
    }, force ? 0 : 120);
  }

  function flashSource(msgId, n) {
    const item = document.getElementById(`${msgId}-src-${n}`);
    if (!item) return;
    item.classList.add("open", "flash");
    item.setAttribute("aria-expanded", "true");
    setTimeout(() => item.classList.remove("flash"), 1600);
  }

  messagesEl.addEventListener("mouseover", (e) => {
    const btn = e.target.closest(".cite");
    if (btn && !pinned) showPopover(btn);
  });
  messagesEl.addEventListener("mouseout", (e) => {
    if (e.target.closest(".cite")) hidePopover(false);
  });
  messagesEl.addEventListener("focusin", (e) => {
    const btn = e.target.closest(".cite");
    if (btn) showPopover(btn);
  });
  messagesEl.addEventListener("focusout", (e) => {
    if (e.target.closest(".cite")) hidePopover(false);
  });
  messagesEl.addEventListener("click", (e) => {
    const btn = e.target.closest(".cite");
    if (!btn) return;
    e.stopPropagation();
    if (pinned === btn) { hidePopover(true); return; }
    pinned = null;
    showPopover(btn);
    pinned = btn;
    flashSource(btn.dataset.msg, btn.dataset.n);
  });
  popover.addEventListener("mouseenter", () => clearTimeout(popTimer));
  popover.addEventListener("mouseleave", () => hidePopover(false));
  document.addEventListener("click", (e) => { if (pinned && !popover.contains(e.target)) hidePopover(true); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") hidePopover(true); });
  chatEl.addEventListener("scroll", () => { if (!popover.hidden) hidePopover(true); }, { passive: true });

  // ---------------- API ----------------
  async function callAsk(question) {
    if (MOCK) return mockAsk(question);
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), REQUEST_TIMEOUT_MS);
    let res;
    try {
      res = await fetch(`${API_BASE}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, top_k: TOP_K }),
        signal: ctrl.signal,
      });
    } catch (e) {
      throw Object.assign(new Error(e.message), { kind: e.name === "AbortError" ? "timeout" : "offline" });
    } finally {
      clearTimeout(t);
    }
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const j = await res.json();
        if (j && j.detail) detail += ` — ${typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail)}`;
      } catch { /* sem corpo JSON */ }
      throw Object.assign(new Error(detail), { kind: "http" });
    }
    return res.json();
  }

  async function checkHealth() {
    const text = statusBtn.querySelector(".status-text");
    if (MOCK) {
      statusBtn.className = "status ok";
      text.textContent = `demo · ${MOCK_KB.length * 3} trechos`;
      statusBtn.title = "Modo demo (?mock=1) — respostas simuladas";
      return;
    }
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 5000);
      const res = await fetch(`${API_BASE}/health`, { signal: ctrl.signal });
      clearTimeout(t);
      const j = await res.json();
      if (!res.ok || j.status !== "ok") throw new Error();
      statusBtn.className = "status ok";
      text.textContent = `online · ${Number(j.chunks || 0).toLocaleString("pt-BR")} trechos`;
      statusBtn.title = `API em ${API_BASE} — clique para verificar novamente`;
    } catch {
      statusBtn.className = "status down";
      text.textContent = "API offline";
      statusBtn.title = `Sem resposta de ${API_BASE}/health — clique para verificar novamente`;
    }
  }

  // ---------------- Fluxo principal ----------------
  async function ask(question, { skipUser = false } = {}) {
    question = question.trim();
    if (!question || busy) return;
    busy = true;
    updateSend();
    hideWelcome();
    if (!skipUser) addUserMessage(question);
    const thinking = addThinking();
    const t0 = performance.now();
    try {
      const data = await callAsk(question);
      if (data.latency_ms == null) data.latency_ms = performance.now() - t0;
      thinking.remove();
      addBotAnswer(data);
    } catch (err) {
      thinking.remove();
      addError(err, question);
      if (err.kind === "offline") checkHealth();
    } finally {
      busy = false;
      updateSend();
      input.focus();
    }
  }

  function updateSend() { sendBtn.disabled = busy || !input.value.trim(); }

  function autoresize() {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = input.value;
    if (!q.trim() || busy) return;
    input.value = "";
    autoresize();
    ask(q);
  });
  input.addEventListener("input", () => { autoresize(); updateSend(); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); }
  });
  document.querySelectorAll("#suggestions .chip").forEach((chip) =>
    chip.addEventListener("click", () => {
      const ic = chip.querySelector(".chip-ic");
      ask(chip.textContent.slice(ic ? ic.textContent.length : 0).trim());
    })
  );
  $("#newChat").addEventListener("click", () => {
    if (busy) return;
    messagesEl.innerHTML = "";
    sourcesStore.clear();
    hidePopover(true);
    welcomeEl.hidden = false;
    input.value = "";
    autoresize(); updateSend(); input.focus();
  });
  statusBtn.addEventListener("click", checkHealth);

  // ---------------- Modo mock (?mock=1) ----------------
  const MOCK_KB = [
    {
      keys: ["sinistro", "auto", "carro", "prazo", "avisar", "aviso"],
      answer: "O aviso de sinistro do **Nexo Auto** deve ser feito em até **7 dias corridos** após o ocorrido [1]. Depois que a documentação estiver completa, o prazo de regulação (resposta ao cliente) é de até **30 dias** [1]. Em caso de roubo ou furto do veículo, é obrigatório apresentar o boletim de ocorrência; a indenização é integral pela tabela FIPE [2].",
      sources: [
        { n: 1, doc_id: "manual-sinistro-auto", titulo: "Manual de Sinistro — Nexo Auto", trecho: "O segurado deve comunicar o sinistro em até 7 (sete) dias corridos após o ocorrido, pela Central 24h (0800 000 6396) ou pelo app. Após a entrega da documentação completa, a Nexo tem até 30 dias para concluir a regulação e responder ao cliente.", score: 0.87 },
        { n: 2, doc_id: "manual-sinistro-auto", titulo: "Manual de Sinistro — Nexo Auto", trecho: "Roubo ou furto de veículo: é obrigatório o boletim de ocorrência. A indenização é integral, calculada pela tabela FIPE vigente na data do sinistro.", score: 0.79 },
        { n: 3, doc_id: "manual-sinistro-residencial", titulo: "Manual de Sinistro — Nexo Residencial", trecho: "O aviso de sinistro residencial deve ser feito em até 10 dias corridos após o ocorrido.", score: 0.71 },
      ],
    },
    {
      keys: ["reserva", "plus", "premium", "essencial"],
      answer: "No plano **Plus**, o carro reserva é de **15 dias** [1]. Para comparação: o plano Essencial oferece 7 dias e o Premium, 30 dias [1].",
      sources: [
        { n: 1, doc_id: "tabela-coberturas-auto", titulo: "Tabela de Coberturas — Nexo Auto", trecho: "Carro reserva: Essencial — 7 dias; Plus — 15 dias; Premium — 30 dias. Franquia básica: 5% do valor FIPE, com mínimo de R$ 2.500,00.", score: 0.91 },
        { n: 2, doc_id: "manual-sinistro-auto", titulo: "Manual de Sinistro — Nexo Auto", trecho: "O carro reserva é liberado após a abertura do sinistro, conforme o plano contratado.", score: 0.68 },
      ],
    },
    {
      keys: ["home", "office", "remoto", "híbrido", "hibrido", "presencial"],
      answer: "A Nexo adota o **modelo híbrido**:\n- **3 dias presenciais** — terça, quarta e quinta [1]\n- **2 dias remotos** [1]\n\nAlém disso, há um **auxílio home office de R$ 150,00 por mês** [2].",
      sources: [
        { n: 1, doc_id: "politica-home-office", titulo: "Política de Home Office", trecho: "O modelo de trabalho é híbrido: 3 dias presenciais (terça, quarta e quinta-feira) e 2 dias remotos, a combinar com o gestor.", score: 0.89 },
        { n: 2, doc_id: "beneficios", titulo: "Benefícios", trecho: "Auxílio home office: R$ 150,00 por mês, pago em folha. Vale-refeição: R$ 45,00 por dia útil.", score: 0.76 },
        { n: 3, doc_id: "faq-novos-colaboradores", titulo: "FAQ — Novos Colaboradores", trecho: "Os dias presenciais são definidos pela política de home office.", score: 0.64 },
      ],
    },
    {
      keys: ["chatgpt", "ia", "inteligência", "inteligencia", "gpt", "clientes"],
      answer: "**Não.** É proibido usar IA pública (como o ChatGPT) com dados de clientes [1]. Para esse tipo de tarefa, utilize apenas o **assistente interno aprovado** pela empresa [1]. Dados pessoais de clientes também são protegidos pela política de privacidade (LGPD) [2].",
      sources: [
        { n: 1, doc_id: "politica-uso-ia", titulo: "Política de Uso de Inteligência Artificial", trecho: "É proibido inserir dados de clientes em ferramentas de IA pública. Utilize somente o assistente interno aprovado pela área de TI e Segurança.", score: 0.88 },
        { n: 2, doc_id: "politica-privacidade-lgpd", titulo: "Política de Privacidade e LGPD", trecho: "O encarregado de dados (DPO) fica na área de Privacidade — contato: dpo@nexo.example. Pedidos de titulares são respondidos em até 15 dias.", score: 0.72 },
        { n: 3, doc_id: "politica-seguranca-informacao", titulo: "Política de Segurança da Informação", trecho: "Incidentes de segurança devem ser reportados em até 1 hora para seguranca@nexo.example.", score: 0.66 },
      ],
    },
    {
      keys: ["férias", "ferias"],
      answer: "São **30 dias de férias por ano**, que podem ser divididos em até **3 períodos** — um deles com no mínimo 14 dias [1]. O pedido deve ser feito com **45 dias de antecedência** pelo portal **Nexo Pessoas** [1].",
      sources: [
        { n: 1, doc_id: "politica-ferias", titulo: "Política de Férias", trecho: "Cada colaborador tem direito a 30 dias de férias por ano, que podem ser fracionados em até 3 períodos, sendo um deles de no mínimo 14 dias. Solicite com 45 dias de antecedência no portal Nexo Pessoas.", score: 0.92 },
      ],
    },
  ];

  function mockAsk(question) {
    const q = question.toLowerCase();
    const tokens = q.split(/[^\p{L}\p{N}]+/u);
    let best = null, bestScore = 0;
    for (const item of MOCK_KB) {
      const score = item.keys.reduce((acc, k) => acc + (tokens.includes(k) || q.includes(k) && k.length > 4 ? 1 : 0), 0);
      if (score > bestScore) { best = item; bestScore = score; }
    }
    const latency = 900 + Math.random() * 1400;
    const data = best
      ? { answer: best.answer, sources: best.sources.slice(0, TOP_K), latency_ms: Math.round(latency) }
      : { answer: NOT_FOUND, sources: [{ n: 1, doc_id: "faq-novos-colaboradores", titulo: "FAQ — Novos Colaboradores", trecho: "Dúvidas gerais sobre o primeiro dia na Nexo.", score: 0.41 }], latency_ms: Math.round(latency) };
    if (/\berro\b/.test(q)) return new Promise((_, rej) => setTimeout(() => rej(Object.assign(new Error("HTTP 500 — erro simulado no modo demo"), { kind: "http" })), 700));
    return new Promise((r) => setTimeout(() => r(data), latency));
  }

  // ---------------- Início ----------------
  checkHealth();
  setInterval(checkHealth, 20000);
  updateSend();
  input.focus();
})();
