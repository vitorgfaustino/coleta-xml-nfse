(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const token = $('meta[name="nfse-token"]')?.content || "";
  const metaVersion = $('meta[name="nfse-version"]')?.content || "";

  const els = {
    form: $("#runForm"),
    certDrop: $("#certDrop"),
    pfx: $("#pfx"),
    certLabel: $("#certLabel"),
    password: $("#password"),
    cnpjs: $("#cnpjs"),
    cnpjCount: $("#cnpjCount"),
    cnpjHint: $("#cnpjHint"),
    cnpjFile: $("#cnpjFile"),
    importCnpjs: $("#importCnpjs"),
    pasteCnpjs: $("#pasteCnpjs"),
    copyCnpjs: $("#copyCnpjs"),
    environment: $("#environment"),
    filter: $("#filter"),
    periodMode: $("#periodMode"),
    periodStart: $("#periodStart"),
    periodEnd: $("#periodEnd"),
    emissionStart: $("#emissionStart"),
    emissionEnd: $("#emissionEnd"),
    periodNote: $("#periodNote"),
    startNsu: $("#startNsu"),
    noCache: $("#noCache"),
    formError: $("#formError"),
    start: $("#start"),
    cancel: $("#cancel"),
    wizardBack: $("#wizardBack"),
    wizardNext: $("#wizardNext"),
    statusCard: $("#statusCard"),
    statusTitle: $("#statusTitle"),
    statusPill: $("#statusPill"),
    progress: $("#progress"),
    resultMetrics: $("#resultMetrics"),
    mNew: $("#mNew"),
    mExported: $("#mExported"),
    mClients: $("#mClients"),
    mFailures: $("#mFailures"),
    resultNote: $("#resultNote"),
    reviewChips: $("#reviewChips"),
    resultActions: $("#resultActions"),
    downloadZip: $("#downloadZip"),
    openReader: $("#openReader"),
    revealData: $("#revealData"),
    wipeData: $("#wipeData"),
    log: $("#log"),
    dataDir: $("#dataDir"),
    cacheInfo: $("#cacheInfo"),
    version: $("#version"),
    quitApp: $("#quitApp"),
    clearPrefs: $("#clearPrefs"),
    revealDataInfo: $("#revealDataInfo"),
    wipeDataInfo: $("#wipeDataInfo"),
    lastRun: $("#lastRun"),
    cacheTag: $("#cacheTag"),
    cacheList: $("#cacheList"),
    backupCache: $("#backupCache"),
    restoreCache: $("#restoreCache"),
    restoreFile: $("#restoreFile"),
    historyCount: $("#historyCount"),
    historyList: $("#historyList"),
    runDiagnostics: $("#runDiagnostics"),
    diagnosticResult: $("#diagnosticResult"),
    toast: $("#toast"),
  };

  const PREFS_KEY = "coleta-xml-nfse:prefs:v1";
  let prefsTimer = null;

  function loadPreferences() {
    try {
      const raw = localStorage.getItem(PREFS_KEY);
      if (!raw) return;
      const prefs = JSON.parse(raw);
      if (!prefs || typeof prefs !== "object") return;
      if (typeof prefs.cnpjs === "string") els.cnpjs.value = prefs.cnpjs;
      if (["producao", "restrita"].includes(prefs.environment)) {
        els.environment.value = prefs.environment;
      }
      if (["Ambas", "Prestados", "Tomados"].includes(prefs.filter)) {
        els.filter.value = prefs.filter;
      }
      if (["all", "range"].includes(prefs.periodMode)) {
        els.periodMode.value = prefs.periodMode;
      }
      const isDay = (value) => typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value);
      if (isDay(prefs.periodStart)) els.periodStart.value = prefs.periodStart;
      if (isDay(prefs.periodEnd)) els.periodEnd.value = prefs.periodEnd;
      if (isDay(prefs.emissionStart)) els.emissionStart.value = prefs.emissionStart;
      if (isDay(prefs.emissionEnd)) els.emissionEnd.value = prefs.emissionEnd;
    } catch {
      // Preferências locais inválidas são ignoradas.
    }
  }

  function savePreferences() {
    clearTimeout(prefsTimer);
    prefsTimer = setTimeout(() => {
      try {
        localStorage.setItem(
          PREFS_KEY,
          JSON.stringify({
            cnpjs: els.cnpjs.value,
            environment: els.environment.value,
            filter: els.filter.value,
            periodMode: els.periodMode.value,
            periodStart: els.periodStart.value,
            periodEnd: els.periodEnd.value,
            emissionStart: els.emissionStart.value,
            emissionEnd: els.emissionEnd.value,
          }),
        );
      } catch {
        // Navegador sem localStorage ou armazenamento cheio.
      }
    }, 250);
  }

  function clearPreferences() {
    try {
      localStorage.removeItem(PREFS_KEY);
    } catch {
      // Ignora indisponibilidade do localStorage.
    }
    els.cnpjs.value = "";
    els.environment.value = "producao";
    els.filter.value = "Ambas";
    els.periodMode.value = "all";
    els.periodStart.value = "";
    els.periodEnd.value = "";
    els.emissionStart.value = "";
    els.emissionEnd.value = "";
    updateCnpjCount();
    syncPeriodFields();
    updateReview();
    showToast("Lista e preferências salvas foram removidas.");
  }

  const state = {
    pfxBase64: "",
    pfxName: "",
    running: false,
    pollTimer: null,
    pollFailures: 0,
    lastError: "",
  };

  let currentStep = 0;
  const STEP_COUNT = 4;
  const NEXT_LABELS = [
    "Continuar para empresas",
    "Continuar para consulta",
    "Continuar para revisão",
  ];

  function monthLabel(value) {
    const parts = String(value || "").split("-");
    return parts.length === 2 ? `${parts[1]}/${parts[0]}` : value;
  }

  function dateLabel(value) {
    const parts = String(value || "").split("-");
    if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`;
    return monthLabel(value);
  }

  function datePair(start, end) {
    if (!start && !end) return "";
    return `${start ? dateLabel(start) : "início"} a ${end ? dateLabel(end) : "fim"}`;
  }

  function formatBytes(bytes) {
    const value = Number(bytes) || 0;
    if (value < 1024) return `${value} B`;
    const units = ["KB", "MB", "GB", "TB"];
    let size = value;
    let unit = "B";
    for (const next of units) {
      size /= 1024;
      unit = next;
      if (size < 1024) break;
    }
    return `${size.toFixed(1)} ${unit}`;
  }

  function normalizeCnpj(value) {
    return String(value || "").toUpperCase().replace(/[^0-9A-Z]/g, "");
  }

  function validCnpj(value) {
    const cnpj = normalizeCnpj(value);
    if (cnpj.length !== 14 || cnpj === cnpj[0].repeat(14) || !/^\d{2}$/.test(cnpj.slice(12))) {
      return false;
    }
    const charValue = (char) => char.charCodeAt(0) - 48;
    const weights = [
      [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
      [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
    ];
    for (let pos = 12; pos <= 13; pos += 1) {
      const row = weights[pos - 12];
      let sum = 0;
      for (let index = 0; index < pos; index += 1) {
        sum += charValue(cnpj[index]) * row[index];
      }
      const remainder = sum % 11;
      const check = remainder < 2 ? 0 : 11 - remainder;
      if (Number(cnpj[pos]) !== check) return false;
    }
    return true;
  }

  const CNPJ_CANDIDATE =
    /[0-9A-Z]{2}[.\s]?[0-9A-Z]{3}[.\s]?[0-9A-Z]{3}[/\s]?[0-9A-Z]{4}-?[0-9]{2}/gi;

  function parseCnpjs(text) {
    const valid = new Set();
    const invalid = [];
    for (const chunk of String(text || "").split(/[,;\n]+/)) {
      const trimmed = chunk.trim();
      if (!trimmed) continue;
      const matches = trimmed.match(CNPJ_CANDIDATE) || [];
      const tokens = matches.length ? matches : [trimmed];
      for (const tokenValue of tokens) {
        let candidate = normalizeCnpj(tokenValue);
        if (candidate.length > 14) candidate = candidate.slice(-14);
        if (validCnpj(candidate)) {
          valid.add(candidate);
        } else {
          const label = tokenValue.trim().slice(0, 40);
          if (label && !invalid.includes(label)) invalid.push(label);
        }
      }
    }
    return { valid: [...valid], invalid };
  }

  function toBase64(bytes) {
    let binary = "";
    const chunk = 0x8000;
    for (let index = 0; index < bytes.length; index += chunk) {
      binary += String.fromCharCode(...bytes.subarray(index, index + chunk));
    }
    return btoa(binary);
  }

  let toastTimer = null;

  function showToast(message, kind = "") {
    els.toast.textContent = message;
    els.toast.className = `toast${kind ? ` ${kind}` : ""}`;
    els.toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      els.toast.hidden = true;
    }, 4500);
  }

  function showError(message) {
    els.formError.textContent = message;
    els.formError.hidden = false;
    els.formError.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function clearError() {
    els.formError.hidden = true;
    els.formError.textContent = "";
  }

  async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    headers.set("X-NFSE-Token", token);
    if (options.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    const response = await fetch(path, {
      ...options,
      headers,
      credentials: "same-origin",
      cache: "no-store",
    });
    const raw = await response.text();
    let data = {};
    try {
      data = raw ? JSON.parse(raw) : {};
    } catch {
      data = { error: raw.slice(0, 300) };
    }
    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    return data;
  }

  function setRunning(running) {
    state.running = running;
    els.start.disabled = running;
    els.start.textContent = running ? "Baixando…" : "Confirmar e baixar";
    els.cancel.hidden = !running;
    els.wizardBack.hidden = running || currentStep === 0;
    els.wizardNext.hidden = running || currentStep === STEP_COUNT - 1;
    els.wizardBack.disabled = running;
    els.wizardNext.disabled = running;
  }

  function setStep(index, options = {}) {
    currentStep = Math.max(0, Math.min(STEP_COUNT - 1, index));
    document.querySelectorAll(".step-panel").forEach((panel, position) => {
      panel.hidden = position !== currentStep;
    });
    document.querySelectorAll(".stepper li").forEach((item, position) => {
      item.classList.toggle("current", position === currentStep);
      item.classList.toggle("done", position < currentStep);
      if (position === currentStep) {
        item.setAttribute("aria-current", "step");
      } else {
        item.removeAttribute("aria-current");
      }
      const number = item.querySelector(".num");
      if (number) {
        number.textContent = position < currentStep ? "✓" : String(position + 1);
      }
    });
    els.wizardBack.hidden = state.running || currentStep === 0;
    els.wizardNext.hidden = state.running || currentStep === STEP_COUNT - 1;
    els.start.hidden = currentStep !== STEP_COUNT - 1;
    els.wizardNext.textContent = NEXT_LABELS[currentStep] || "Continuar";
    els.wizardBack.disabled = state.running;
    els.wizardNext.disabled = state.running;
    clearError();
    const panel = document.querySelector(`.step-panel[data-step="${currentStep}"]`);
    if (panel) {
      panel.classList.remove("is-entering");
      if (options.animate !== false) {
        void panel.offsetWidth;
        panel.classList.add("is-entering");
      }
    }
  }

  function validateStep(index) {
    if (index === 0) {
      if (!state.pfxBase64) {
        showError("Selecione o certificado A1 (.pfx/.p12).");
        return false;
      }
      if (!els.password.value) {
        showError("Informe a senha do certificado.");
        return false;
      }
    }
    if (index === 1) {
      const { valid, invalid } = parseCnpjs(els.cnpjs.value);
      if (invalid.length) {
        showError(`CNPJs inválidos: ${invalid.slice(0, 8).join(", ")}`);
        return false;
      }
      if (!valid.length) {
        showError("Informe ao menos um CNPJ válido.");
        return false;
      }
    }
    if (index === 2) {
      if (els.periodMode.value === "range") {
        const periodStart = els.periodStart.value;
        const periodEnd = els.periodEnd.value;
        const emissionStart = els.emissionStart.value;
        const emissionEnd = els.emissionEnd.value;
        if (Boolean(periodStart) !== Boolean(periodEnd)) {
          showError("Informe o início e o fim do período de competência.");
          return false;
        }
        if (periodStart && periodEnd && periodStart > periodEnd) {
          showError("A competência inicial não pode ser depois da final.");
          return false;
        }
        if (Boolean(emissionStart) !== Boolean(emissionEnd)) {
          showError("Informe o início e o fim da emissão.");
          return false;
        }
        if (emissionStart && emissionEnd && emissionStart > emissionEnd) {
          showError("A emissão inicial não pode ser depois da final.");
          return false;
        }
        if (!periodStart && !emissionStart) {
          showError("Informe ao menos um intervalo de competência ou emissão.");
          return false;
        }
      }
      const nsuText = els.startNsu.value.trim();
      if (nsuText) {
        const nsu = Number(nsuText);
        if (!Number.isInteger(nsu) || nsu < 0) {
          showError("NSU inicial inválido. Use um número inteiro maior ou igual a zero.");
          return false;
        }
      }
    }
    return true;
  }

  function nextStep() {
    if (state.running || currentStep >= STEP_COUNT - 1) return;
    if (!validateStep(currentStep)) return;
    setStep(currentStep + 1);
  }

  function previousStep() {
    if (state.running || currentStep === 0) return;
    setStep(currentStep - 1);
  }

  function syncPeriodFields() {
    const range = els.periodMode.value === "range";
    [els.periodStart, els.periodEnd, els.emissionStart, els.emissionEnd].forEach(
      (input) => {
        input.disabled = !range;
      },
    );
    els.periodNote.textContent = range
      ? "Informe um ou os dois intervalos. XMLs fora deles não serão guardados. A competência e a emissão são comparadas por dia."
      : "Todo o período guarda os XMLs retornados. Ao selecionar um período, os XMLs fora dele não são guardados.";
    updateReview();
  }

  function updateReview() {
    const chips = [];
    const add = (text) => {
      const span = document.createElement("span");
      span.className = "chip";
      span.textContent = text;
      chips.push(span);
    };
    if (state.pfxName) add(`Certificado: ${state.pfxName}`);
    add(els.environment.selectedOptions[0]?.textContent || "Produção");
    add(els.filter.selectedOptions[0]?.textContent || "Prestados e tomados");
    if (els.periodMode.value === "range") {
      const competence = datePair(els.periodStart.value, els.periodEnd.value);
      const emission = datePair(els.emissionStart.value, els.emissionEnd.value);
      if (competence) add(`Competência: ${competence}`);
      if (emission) add(`Emissão: ${emission}`);
      if (!competence && !emission) add("Todo o período");
    } else {
      add("Todo o período");
    }
    const count = parseCnpjs(els.cnpjs.value).valid.length;
    add(`${count} CNPJ${count === 1 ? "" : "s"}`);
    if (els.noCache.checked) add("Sem cópia local");
    const nsu = els.startNsu.value.trim();
    if (nsu) add(`NSU ${nsu}`);
    els.reviewChips.replaceChildren(...chips);
  }

  function updateCnpjCount() {
    const { valid, invalid } = parseCnpjs(els.cnpjs.value);
    els.cnpjCount.textContent = `${valid.length} CNPJ${valid.length === 1 ? "" : "s"}`;
    els.cnpjCount.classList.toggle("bad", invalid.length > 0);
    els.cnpjHint.textContent = invalid.length
      ? `${invalid.length} inválido(s): ${invalid.slice(0, 3).join(", ")}${invalid.length > 3 ? "…" : ""}`
      : "A procuração deve estar vigente para o serviço da NFS-e.";
    updateReview();
  }

  async function loadPfx(file) {
    if (!file) return;
    if (!/\.(pfx|p12)$/i.test(file.name)) {
      showError("Selecione um arquivo .pfx ou .p12.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      showError("O certificado é grande demais (limite de 5 MB).");
      return;
    }
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      state.pfxBase64 = toBase64(bytes);
      state.pfxName = file.name;
      els.certLabel.textContent = `${file.name} · ${formatBytes(file.size)}`;
      els.certDrop.classList.add("selected");
      updateReview();
      clearError();
    } catch {
      state.pfxBase64 = "";
      els.certLabel.textContent = "Selecione o certificado do procurador";
      els.certDrop.classList.remove("selected");
      showError("Não foi possível ler o certificado.");
    } finally {
      els.pfx.value = "";
    }
  }

  function resetCertificate() {
    state.pfxBase64 = "";
    state.pfxName = "";
    els.certLabel.textContent = "Selecione o certificado do procurador";
    els.certDrop.classList.remove("selected");
    els.pfx.value = "";
    updateReview();
  }

  function renderStatus(data) {
    const current = data.state || "idle";
    if (data.data_dir) els.dataDir.textContent = data.data_dir;
    const cacheFiles = data.cache_files ?? 0;
    els.cacheInfo.textContent = `${cacheFiles} XML${cacheFiles === 1 ? "" : "s"} · ${formatBytes(data.cache_bytes ?? 0)}`;
    if (data.version) els.version.textContent = data.version;

    if (current === "idle" && !(data.logs || []).length) return;

    els.statusCard.hidden = false;

    const titles = {
      idle: "Pronto",
      running: "Consultando o ADN…",
      done: "Download concluído",
      error: "A execução falhou",
      cancelled: "Execução cancelada",
    };
    const pills = {
      idle: "Pronto",
      running: "Em andamento",
      done: "Concluído",
      error: "Erro",
      cancelled: "Cancelado",
    };
    const pillClasses = {
      done: " done",
      error: " error",
      cancelled: " cancelled",
    };
    const progressClasses = {
      done: " done",
      error: " error",
      cancelled: " cancelled",
    };

    els.statusTitle.textContent = titles[current] || "Execução";
    els.statusPill.className = `status-pill${pillClasses[current] || ""}`;
    els.statusPill.textContent = pills[current] || "Aguardando";
    els.progress.className = `progress${progressClasses[current] || ""}`;

    const logs = data.logs || [];
    if (logs.length) {
      const nearBottom =
        els.log.scrollHeight - els.log.scrollTop - els.log.clientHeight < 90;
      els.log.textContent = logs.join("\n");
      if (nearBottom || current === "running") {
        els.log.scrollTop = els.log.scrollHeight;
      }
    }

    if (data.result) {
      els.resultMetrics.hidden = false;
      els.mNew.textContent = data.result.new_documents ?? 0;
      els.mExported.textContent = data.result.exported ?? 0;
      els.mClients.textContent = (data.result.clients || []).length;
      els.mFailures.textContent = (data.result.failures || []).length;
      const ignored = data.result.ignored ?? 0;
      const periodParts = [];
      if (data.result.period_start || data.result.period_end) {
        periodParts.push(
          `Competência ${datePair(data.result.period_start, data.result.period_end)}`,
        );
      }
      if (data.result.emission_start || data.result.emission_end) {
        periodParts.push(
          `Emissão ${datePair(data.result.emission_start, data.result.emission_end)}`,
        );
      }
      const period = periodParts.length
        ? `${periodParts.join("; ")}.`
        : "Todo o período.";
      els.resultNote.hidden = false;
      const certificate = data.result.certificate_not_after
        ? ` Certificado válido até ${new Date(
            `${data.result.certificate_not_after}T00:00:00`,
          ).toLocaleDateString("pt-BR")}.`
        : "";
      els.resultNote.textContent = `${period} ${
        ignored
          ? `${ignored} XML(s) fora do período não foram guardados.`
          : "Nenhum XML ficou fora do período."
      }${certificate}`;
      els.resultActions.hidden = false;
      if (data.result.has_zip) {
        els.downloadZip.hidden = false;
        els.downloadZip.href = `/api/download?token=${encodeURIComponent(token)}`;
        els.downloadZip.download = data.result.zip_name || "nfse.zip";
        els.openReader.hidden = false;
      } else {
        els.downloadZip.hidden = true;
        els.openReader.hidden = true;
      }
    } else {
      els.resultMetrics.hidden = true;
      els.resultNote.hidden = true;
      els.resultActions.hidden = true;
      els.openReader.hidden = true;
    }

    if (data.error && data.error !== state.lastError) {
      state.lastError = data.error;
      showToast(data.error, "error");
    }
    if (!data.error) state.lastError = "";
  }

  async function poll() {
    if (state.pollTimer) {
      clearTimeout(state.pollTimer);
      state.pollTimer = null;
    }
    try {
      const data = await api("/api/status");
      state.pollFailures = 0;
      renderStatus(data);
      if (data.state === "running") {
        state.pollTimer = setTimeout(poll, 700);
      } else {
        setRunning(false);
        refreshLocalData();
        if (data.state === "done") showToast("Download concluído.", "ok");
        if (data.state === "cancelled") showToast("Execução cancelada.");
      }
    } catch {
      state.pollFailures += 1;
      if (state.pollFailures > 5) {
        setRunning(false);
        showToast("O aplicativo não está respondendo. Reinicie pelo atalho.", "error");
        return;
      }
      state.pollTimer = setTimeout(poll, 1800);
    }
  }

  async function startRun(event) {
    event.preventDefault();
    if (state.running) return;
    if (currentStep < STEP_COUNT - 1) {
      nextStep();
      return;
    }
    clearError();

    const password = els.password.value;
    const { valid, invalid } = parseCnpjs(els.cnpjs.value);
    if (!state.pfxBase64) {
      showError("Selecione o certificado A1 (.pfx/.p12).");
      return;
    }
    if (!password) {
      showError("Informe a senha do certificado.");
      return;
    }
    if (invalid.length) {
      showError(`CNPJs inválidos: ${invalid.slice(0, 8).join(", ")}`);
      return;
    }
    if (!valid.length) {
      showError("Informe ao menos um CNPJ válido.");
      return;
    }

    let periodStart = "";
    let periodEnd = "";
    let emissionStart = "";
    let emissionEnd = "";
    if (els.periodMode.value === "range") {
      periodStart = els.periodStart.value;
      periodEnd = els.periodEnd.value;
      emissionStart = els.emissionStart.value;
      emissionEnd = els.emissionEnd.value;
      if (Boolean(periodStart) !== Boolean(periodEnd)) {
        showError("Informe o início e o fim do período de competência.");
        return;
      }
      if (periodStart && periodEnd && periodStart > periodEnd) {
        showError("A competência inicial não pode ser depois da final.");
        return;
      }
      if (Boolean(emissionStart) !== Boolean(emissionEnd)) {
        showError("Informe o início e o fim da emissão.");
        return;
      }
      if (emissionStart && emissionEnd && emissionStart > emissionEnd) {
        showError("A emissão inicial não pode ser depois da final.");
        return;
      }
      if (!periodStart && !emissionStart) {
        showError("Informe ao menos um intervalo de competência ou emissão.");
        return;
      }
    }
    const startNsuText = els.startNsu.value.trim();
    const startNsu = startNsuText ? Number(startNsuText) : 0;
    if (!Number.isInteger(startNsu) || startNsu < 0) {
      showError("NSU inicial inválido. Use um número inteiro maior ou igual a zero.");
      return;
    }

    const payload = {
      pfx_base64: state.pfxBase64,
      password,
      cnpjs: valid,
      environment: els.environment.value,
      document_filter: els.filter.value,
      no_cache: els.noCache.checked,
      period_start: periodStart || null,
      period_end: periodEnd || null,
      emission_start: emissionStart || null,
      emission_end: emissionEnd || null,
      start_nsu: startNsu,
    };

    setRunning(true);
    els.statusCard.hidden = false;
    els.statusTitle.textContent = "Preparando o certificado…";
    els.statusPill.className = "status-pill";
    els.statusPill.textContent = "Em andamento";
    els.progress.className = "progress";
    els.resultMetrics.hidden = true;
    els.resultNote.hidden = true;
    els.resultActions.hidden = true;
    els.log.textContent = "";
    els.statusCard.scrollIntoView({ block: "nearest", behavior: "smooth" });

    try {
      const data = await api("/api/run", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      els.password.value = "";
      resetCertificate();
      if (data.job_id) poll();
    } catch (error) {
      setRunning(false);
      showError(error.message);
      showToast(error.message, "error");
    }
  }

  async function cancelRun() {
    if (!state.running) return;
    els.cancel.disabled = true;
    els.cancel.textContent = "Cancelando…";
    try {
      await api("/api/cancel", { method: "POST" });
      showToast("Cancelamento solicitado.");
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      els.cancel.disabled = false;
      els.cancel.textContent = "Cancelar";
    }
  }

  async function revealData() {
    try {
      await api("/api/reveal", { method: "POST" });
      showToast("Pasta do aplicativo aberta.");
    } catch (error) {
      showToast(error.message, "error");
    }
  }

  let readerWindow = null;
  let readerReady = false;
  let pendingZip = null;

  function sendZipToReader() {
    if (!readerWindow || !readerReady || !pendingZip) return;
    try {
      readerWindow.postMessage(
        { type: "nfse-zip", buffer: pendingZip.buffer, name: pendingZip.name },
        location.origin,
      );
      pendingZip = null;
      showToast("ZIP enviado ao leitor.", "ok");
    } catch {
      showToast("Não foi possível enviar o ZIP. Baixe o arquivo e arraste no leitor.", "error");
    }
  }

  function openReaderWithZip() {
    if (!els.downloadZip.href || els.downloadZip.hidden) return;
    const zipUrl = els.downloadZip.href;
    const zipName = els.downloadZip.download || "nfse.zip";
    readerWindow = window.open(`/leitor?import=${Date.now()}`, "_blank");
    if (!readerWindow) {
      showToast("Permita pop-ups para abrir o leitor.", "error");
      return;
    }
    readerReady = false;
    pendingZip = null;
    fetch(zipUrl, { cache: "no-store", credentials: "same-origin" })
      .then((response) => {
        if (!response.ok) throw new Error("ZIP indisponível");
        return response.arrayBuffer();
      })
      .then((buffer) => {
        pendingZip = { buffer, name: zipName };
        sendZipToReader();
      })
      .catch(() => {
        showToast(
          "Não foi possível abrir o ZIP no leitor. Baixe o arquivo e arraste.",
          "error",
        );
      });
  }

  window.addEventListener("message", (event) => {
    if (event.origin !== location.origin || event.source !== readerWindow) return;
    if (event.data?.type === "nfse-reader-ready") {
      readerReady = true;
      sendZipToReader();
    }
  });

  async function wipeData() {
    const confirmed = confirm(
      "Apagar os dados do aplicativo? Isso remove a cópia local dos XMLs, o histórico da última consulta e os logs. Arquivos que você já baixou para Downloads não serão apagados.",
    );
    if (!confirmed) return;
    try {
      const data = await api("/api/wipe", { method: "POST" });
      showToast(`Dados do aplicativo apagados (${formatBytes(data.freed || 0)} liberados).`, "ok");
      els.statusCard.hidden = true;
      els.log.textContent = "";
      els.resultMetrics.hidden = true;
      els.resultActions.hidden = true;
      setRunning(false);
      poll();
      refreshLocalData();
    } catch (error) {
      showToast(error.message, "error");
    }
  }

  async function quitApp() {
    const confirmed = confirm(
      "Encerrar o aplicativo? Se houver um download em andamento, cancele antes.",
    );
    if (!confirmed) return;
    try {
      await api("/api/quit", { method: "POST" });
      document.body.innerHTML =
        '<main class="bye"><div><h1>Aplicativo encerrado</h1><p>Você pode fechar esta aba.</p></div></main>';
    } catch (error) {
      showToast(error.message, "error");
    }
  }

  function insertAtCursor(text) {
    const start = els.cnpjs.selectionStart ?? els.cnpjs.value.length;
    const end = els.cnpjs.selectionEnd ?? start;
    const value = els.cnpjs.value;
    els.cnpjs.value = value.slice(0, start) + text + value.slice(end);
    els.cnpjs.selectionStart = els.cnpjs.selectionEnd = start + text.length;
    els.cnpjs.focus();
    updateCnpjCount();
  }

  async function importCnpjs() {
    const file = els.cnpjFile.files?.[0];
    if (!file) return;
    try {
      const buffer = await file.arrayBuffer();
      let text = new TextDecoder("utf-8").decode(buffer);
      if (text.includes("\uFFFD")) {
        text = new TextDecoder("latin1").decode(buffer);
      }
      text = text.replace(/^\uFEFF/, "").trim();
      const current = els.cnpjs.value.trim();
      els.cnpjs.value = current ? `${current}\n${text}` : text;
      updateCnpjCount();
      showToast("Lista importada.", "ok");
    } catch {
      showToast("Não foi possível ler o arquivo.", "error");
    } finally {
      els.cnpjFile.value = "";
    }
  }

  async function pasteCnpjs() {
    try {
      const text = await navigator.clipboard.readText();
      insertAtCursor(text);
      showToast("Lista colada.", "ok");
    } catch {
      els.cnpjs.focus();
      showToast("Permissão de colagem negada; use Ctrl+V ou ⌘V.", "error");
    }
  }

  async function copyCnpjs() {
    const text = els.cnpjs.value.trim();
    if (!text) {
      showToast("A lista está vazia.");
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      showToast("Lista copiada.", "ok");
    } catch {
      els.cnpjs.select();
      showToast("Use Ctrl+C ou ⌘C para copiar.", "error");
    }
  }

  function formatDateTime(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function historyStateLabel(value) {
    return {
      done: "Concluído",
      error: "Erro",
      cancelled: "Cancelado",
    }[value] || value || "Execução";
  }

  async function loadHistory() {
    try {
      const data = await api("/api/history");
      const runs = Array.isArray(data.runs) ? data.runs : [];
      els.historyCount.textContent = String(runs.length);
      if (!runs.length) {
        els.historyList.innerHTML = '<p class="note">Nenhuma execução registrada.</p>';
        els.lastRun.textContent = "—";
        return;
      }
      const latest = runs[0];
      els.lastRun.textContent = `${formatDateTime(latest.finished_at)} · ${latest.new_documents} novo(s)`;
      const items = runs.map((run) => {
        const item = document.createElement("div");
        item.className = "history-item";
        const main = document.createElement("div");
        const title = document.createElement("b");
        title.textContent = historyStateLabel(run.state);
        const when = document.createElement("small");
        when.textContent = formatDateTime(run.finished_at);
        main.append(title, when);
        const summary = document.createElement("div");
        summary.className = "history-summary";
        const filters = [];
        if (run.period_start || run.period_end) {
          filters.push(`competência ${datePair(run.period_start, run.period_end)}`);
        }
        if (run.emission_start || run.emission_end) {
          filters.push(`emissão ${datePair(run.emission_start, run.emission_end)}`);
        }
        const period = filters.length ? filters.join("; ") : "todo o período";
        summary.textContent = `${run.cnpj_count} CNPJ(s) · ${run.new_documents} novos · ${run.exported} exportados · ${run.failures} erro(s) · ${period}`;
        item.append(main, summary);
        return item;
      });
      els.historyList.replaceChildren(...items);
    } catch {
      // Histórico é auxiliar; a tela principal continua funcionando.
    }
  }

  async function loadCache() {
    try {
      const data = await api("/api/cache");
      const clients = Array.isArray(data.clients) ? data.clients : [];
      els.cacheTag.textContent = `${clients.length} CNPJ${clients.length === 1 ? "" : "s"}`;
      if (!clients.length) {
        els.cacheList.innerHTML = '<p class="note">Nenhum XML salvo.</p>';
        return;
      }
      const items = clients.map((client) => {
        const item = document.createElement("div");
        item.className = "cache-item";
        const text = document.createElement("div");
        const name = document.createElement("b");
        name.textContent = client.cnpj;
        const detail = document.createElement("small");
        detail.textContent = `${client.files} XML(s) · ${formatBytes(client.bytes)}`;
        text.append(name, detail);
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "btn danger";
        remove.textContent = "Apagar";
        remove.addEventListener("click", () => clearCnpjCache(client.cnpj));
        item.append(text, remove);
        return item;
      });
      els.cacheList.replaceChildren(...items);
    } catch {
      // Cache é auxiliar; a tela principal continua funcionando.
    }
  }

  async function refreshLocalData() {
    await Promise.allSettled([loadHistory(), loadCache()]);
  }

  async function clearCnpjCache(cnpj) {
    if (!confirm(`Apagar os XMLs, o índice e o cursor do CNPJ ${cnpj}?`)) return;
    try {
      const data = await api("/api/cache/clear", {
        method: "POST",
        body: JSON.stringify({ cnpj }),
      });
      showToast(`${data.files || 0} XML(s) removido(s) da cópia local.`, "ok");
      await refreshLocalData();
      await loadStatus();
    } catch (error) {
      showToast(error.message, "error");
    }
  }

  function downloadCacheBackup() {
    window.location.href = `/api/cache/backup?token=${encodeURIComponent(token)}`;
  }

  async function restoreCacheBackup(file) {
    if (!file) return;
    if (!confirm("Restaurar este backup? Isso substitui a cópia local atual.")) return;
    els.restoreCache.disabled = true;
    try {
      const response = await fetch(
        `/api/cache/restore?token=${encodeURIComponent(token)}`,
        {
          method: "POST",
          headers: {
            "X-NFSE-Token": token,
            "Content-Type": "application/zip",
          },
          body: file,
        },
      );
      const raw = await response.text();
      let data = {};
      try {
        data = raw ? JSON.parse(raw) : {};
      } catch {
        data = { error: raw.slice(0, 300) };
      }
      if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
      showToast(`Backup restaurado: ${data.files || 0} XML(s).`, "ok");
      await refreshLocalData();
      await loadStatus();
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      els.restoreCache.disabled = false;
      els.restoreFile.value = "";
    }
  }

  async function runDiagnostics() {
    els.runDiagnostics.disabled = true;
    els.diagnosticResult.hidden = false;
    els.diagnosticResult.textContent = "Executando diagnóstico…";
    try {
      const data = await api("/api/diagnostics");
      const proxy = Object.entries(data.proxy || {})
        .filter(([, value]) => value)
        .map(([name, value]) => `${name}=${value}`)
        .join(" · ");
      const deps = Object.entries(data.dependencies || {})
        .map(([name, value]) => `${name} ${value}`)
        .join(" · ");
      const lines = [
        `Aplicativo: ${data.app} ${data.version}`,
        `Python: ${data.python}`,
        `Plataforma: ${data.platform}`,
        `Pasta: ${data.data_dir}`,
        `Cópia local: ${data.cache_files} XML(s), ${formatBytes(data.cache_bytes)}`,
        `Banco de estado: ${formatBytes(data.state_bytes)}`,
        `Dependências: ${deps}`,
        `Proxy: ${proxy || "não configurado"}`,
        `ADN: ${data.adn?.host || "—"}`,
        `DNS: ${data.adn?.dns?.ok ? data.adn.dns.addresses.join(", ") : `falhou (${data.adn?.dns?.error || "sem detalhes"})`}`,
        `TCP 443: ${data.adn?.tcp?.ok ? `${data.adn.tcp.ms} ms` : `falhou (${data.adn?.tcp?.error || "sem detalhes"})`}`,
        `Certificado: ${data.certificate}`,
      ];
      els.diagnosticResult.textContent = lines.join("\n");
    } catch (error) {
      els.diagnosticResult.textContent = `Falha no diagnóstico: ${error.message}`;
    } finally {
      els.runDiagnostics.disabled = false;
    }
  }

  async function loadStatus() {
    try {
      const data = await api("/api/status");
      renderStatus(data);
      if (data.state === "running") {
        setRunning(true);
        poll();
      } else {
        setRunning(false);
      }
    } catch {
      showToast("Inicie o aplicativo pelo atalho e abra a página novamente.", "error");
    }
  }

  els.pfx.addEventListener("change", () => loadPfx(els.pfx.files?.[0]));
  ["dragenter", "dragover"].forEach((eventName) => {
    els.certDrop.addEventListener(eventName, (event) => {
      event.preventDefault();
      els.certDrop.classList.add("over");
    });
  });
  ["dragleave", "dragend"].forEach((eventName) => {
    els.certDrop.addEventListener(eventName, () => els.certDrop.classList.remove("over"));
  });
  els.certDrop.addEventListener("drop", (event) => {
    event.preventDefault();
    els.certDrop.classList.remove("over");
    loadPfx(event.dataTransfer.files?.[0]);
  });
  els.certDrop.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      els.pfx.click();
    }
  });
  els.certDrop.addEventListener("click", (event) => {
    if (event.target.closest("input")) return;
    els.pfx.click();
  });

  const lastMonthPicker = new WeakMap();
  function openMonthPicker(input) {
    if (!input || input.disabled || typeof input.showPicker !== "function") return;
    const now = Date.now();
    if (now - (lastMonthPicker.get(input) || 0) < 300) return;
    lastMonthPicker.set(input, now);
    try {
      input.showPicker();
    } catch {
      // O navegador pode bloquear showPicker fora do gesto do usuário.
    }
  }
  [els.periodStart, els.periodEnd, els.emissionStart, els.emissionEnd].forEach(
    (input) => {
      input.addEventListener("click", () => openMonthPicker(input));
      input.closest("label")?.addEventListener("click", () => openMonthPicker(input));
    },
  );

  els.cnpjs.addEventListener("input", () => {
    updateCnpjCount();
    savePreferences();
  });
  els.periodMode.addEventListener("change", () => {
    syncPeriodFields();
    savePreferences();
  });
  els.periodStart.addEventListener("change", () => {
    updateReview();
    savePreferences();
  });
  els.periodEnd.addEventListener("change", () => {
    updateReview();
    savePreferences();
  });
  els.emissionStart.addEventListener("change", () => {
    updateReview();
    savePreferences();
  });
  els.emissionEnd.addEventListener("change", () => {
    updateReview();
    savePreferences();
  });
  els.environment.addEventListener("change", () => {
    updateReview();
    savePreferences();
  });
  els.filter.addEventListener("change", () => {
    updateReview();
    savePreferences();
  });
  els.noCache.addEventListener("change", updateReview);
  els.startNsu.addEventListener("input", updateReview);
  els.clearPrefs.addEventListener("click", clearPreferences);
  els.importCnpjs.addEventListener("click", () => els.cnpjFile.click());
  els.cnpjFile.addEventListener("change", importCnpjs);
  els.pasteCnpjs.addEventListener("click", pasteCnpjs);
  els.copyCnpjs.addEventListener("click", copyCnpjs);
  els.form.addEventListener("submit", startRun);
  els.wizardNext.addEventListener("click", nextStep);
  els.wizardBack.addEventListener("click", previousStep);
  els.cancel.addEventListener("click", cancelRun);
  els.revealData.addEventListener("click", revealData);
  els.openReader.addEventListener("click", openReaderWithZip);
  els.wipeData.addEventListener("click", wipeData);
  els.revealDataInfo.addEventListener("click", revealData);
  els.wipeDataInfo.addEventListener("click", wipeData);
  els.backupCache.addEventListener("click", downloadCacheBackup);
  els.restoreCache.addEventListener("click", () => els.restoreFile.click());
  els.restoreFile.addEventListener("change", () =>
    restoreCacheBackup(els.restoreFile.files?.[0]),
  );
  els.runDiagnostics.addEventListener("click", runDiagnostics);
  els.quitApp.addEventListener("click", quitApp);

  window.addEventListener("beforeunload", (event) => {
    if (state.running) {
      event.preventDefault();
      event.returnValue = "";
    }
  });

  loadPreferences();
  updateCnpjCount();
  syncPeriodFields();
  updateReview();
  setStep(0, { scroll: false, animate: false });
  if (metaVersion) els.version.textContent = metaVersion;
  loadStatus();
  refreshLocalData();
})();
