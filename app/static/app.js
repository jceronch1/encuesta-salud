const state = {
  files: [],
  uploads: [],
  analytics: null,
  searchTimer: null,
  pollTimer: null,
};

const elements = {
  connectionPill: document.querySelector("#connectionPill"),
  connectionText: document.querySelector("#connectionText"),
  dropzone: document.querySelector("#dropzone"),
  fileInput: document.querySelector("#fileInput"),
  selection: document.querySelector("#selection"),
  selectionCount: document.querySelector("#selectionCount"),
  selectedFiles: document.querySelector("#selectedFiles"),
  clearSelection: document.querySelector("#clearSelection"),
  uploadButton: document.querySelector("#uploadButton"),
  uploadProgress: document.querySelector("#uploadProgress"),
  progressLabel: document.querySelector("#progressLabel"),
  progressPercent: document.querySelector("#progressPercent"),
  progressBar: document.querySelector("#progressBar"),
  statTotal: document.querySelector("#statTotal"),
  statCompleted: document.querySelector("#statCompleted"),
  statReview: document.querySelector("#statReview"),
  statPending: document.querySelector("#statPending"),
  analyticsSection: document.querySelector("#analyticsSection"),
  analyticsSummary: document.querySelector("#analyticsSummary"),
  analyticsLoading: document.querySelector("#analyticsLoading"),
  analyticsEmpty: document.querySelector("#analyticsEmpty"),
  analyticsEmptyTitle: document.querySelector("#analyticsEmptyTitle"),
  analyticsEmptyCopy: document.querySelector("#analyticsEmptyCopy"),
  analyticsContent: document.querySelector("#analyticsContent"),
  globalChartSubtitle: document.querySelector("#globalChartSubtitle"),
  categoryBars: document.querySelector("#categoryBars"),
  responseLegend: document.querySelector("#responseLegend"),
  domainChart: document.querySelector("#domainChart"),
  dimensionDomainFilter: document.querySelector("#dimensionDomainFilter"),
  dimensionChart: document.querySelector("#dimensionChart"),
  analyticsTableBody: document.querySelector("#analyticsTableBody"),
  analyticsMethodology: document.querySelector("#analyticsMethodology"),
  analyticsSource: document.querySelector("#analyticsSource"),
  recordsBody: document.querySelector("#recordsBody"),
  emptyState: document.querySelector("#emptyState"),
  emptyTitle: document.querySelector("#emptyTitle"),
  emptyCopy: document.querySelector("#emptyCopy"),
  tableLoading: document.querySelector("#tableLoading"),
  searchInput: document.querySelector("#searchInput"),
  refreshButton: document.querySelector("#refreshButton"),
  toastRegion: document.querySelector("#toastRegion"),
  drawerBackdrop: document.querySelector("#drawerBackdrop"),
  detailDrawer: document.querySelector("#detailDrawer"),
  drawerTitle: document.querySelector("#drawerTitle"),
  drawerBody: document.querySelector("#drawerBody"),
  closeDrawer: document.querySelector("#closeDrawer"),
  exportButton: document.querySelector("#exportButton"),
};

const recordsCard = document.querySelector(".records-card");
if (recordsCard && elements.analyticsSection) {
  recordsCard.after(elements.analyticsSection);
}

const statusLabels = {
  queued: "En cola",
  processing: "Procesando",
  completed: "Completado",
  needs_review: "Por revisar",
  error: "Error",
};

const categoryClasses = {
  A: "category-a",
  B: "category-b",
  C: "category-c",
  D: "category-d",
  E: "category-e",
};

const answerOptions = [
  ["A", "Siempre"],
  ["B", "Casi siempre"],
  ["C", "Algunas veces"],
  ["D", "Casi nunca"],
  ["E", "Nunca"],
];

const reviewStatusLabels = {
  blank: "Sin marca detectada",
  multiple: "Dos o más marcas",
  uncertain: "Marca dudosa",
};

const extractionMethodLabels = {
  pdf_vector_geometry: "Geometría PDF",
  hybrid_vector_raster: "OMR híbrido",
  omrchecker_raster_fallback: "Escaneo OMR",
};

const percentFormatter = new Intl.NumberFormat("es-CO", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 1,
});

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("es-CO", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function boolLabel(value) {
  if (value === true) return "Sí";
  if (value === false) return "No";
  return "No detectado";
}

function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = `toast${type === "error" ? " is-error" : ""}`;
  toast.textContent = message;
  elements.toastRegion.append(toast);
  window.setTimeout(() => toast.remove(), 5200);
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  let payload = null;
  try {
    payload = await response.json();
  } catch (_error) {
    payload = null;
  }
  if (!response.ok) {
    throw new Error(payload?.detail || "No fue posible completar la operación");
  }
  return payload;
}

async function loadHealth() {
  try {
    const health = await requestJson("/api/health");
    const connected = Boolean(health.database?.connected);
    elements.connectionPill.className = `connection-pill ${connected ? "" : "is-error"}`;
    elements.connectionText.textContent = connected ? "MySQL conectado" : "MySQL sin conexión";
    elements.connectionPill.title = connected ? "Base de datos disponible" : (health.database?.error || "Sin conexión");
    elements.uploadButton.disabled = !connected || state.files.length === 0;
    elements.exportButton.setAttribute("aria-disabled", connected ? "false" : "true");
    return connected;
  } catch (error) {
    elements.connectionPill.className = "connection-pill is-error";
    elements.connectionText.textContent = "Servicio no disponible";
    elements.connectionPill.title = error.message;
    elements.uploadButton.disabled = true;
    return false;
  }
}

function renderSelection() {
  elements.selection.hidden = state.files.length === 0;
  elements.selectionCount.textContent = `${state.files.length} ${state.files.length === 1 ? "archivo" : "archivos"} · ${formatBytes(state.files.reduce((sum, file) => sum + file.size, 0))}`;
  elements.selectedFiles.replaceChildren();
  state.files.slice(0, 6).forEach((file) => {
    const row = document.createElement("li");
    const name = document.createElement("span");
    const size = document.createElement("span");
    name.textContent = file.name;
    size.textContent = formatBytes(file.size);
    row.append(name, size);
    elements.selectedFiles.append(row);
  });
  if (state.files.length > 6) {
    const row = document.createElement("li");
    const more = document.createElement("span");
    more.textContent = `y ${state.files.length - 6} archivos más…`;
    row.append(more);
    elements.selectedFiles.append(row);
  }
  elements.uploadButton.disabled = state.files.length === 0 || elements.connectionPill.classList.contains("is-error");
}

function setFiles(fileList) {
  const files = Array.from(fileList);
  const invalid = files.filter((file) => !file.name.toLowerCase().endsWith(".pdf"));
  if (invalid.length) showToast(`${invalid.length} archivo(s) omitido(s): solo se admiten PDF.`, "error");
  state.files = files.filter((file) => file.name.toLowerCase().endsWith(".pdf")).slice(0, 250);
  if (files.length > 250) showToast("El máximo por lote es de 250 PDFs.", "error");
  renderSelection();
}

function clearFiles() {
  state.files = [];
  elements.fileInput.value = "";
  renderSelection();
}

function uploadFiles() {
  if (!state.files.length) return;
  const formData = new FormData();
  state.files.forEach((file) => formData.append("files", file));

  elements.uploadButton.disabled = true;
  elements.uploadProgress.hidden = false;
  elements.progressLabel.textContent = "Guardando lote…";
  elements.progressPercent.textContent = "0%";
  elements.progressBar.style.width = "0%";

  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/uploads");
  xhr.upload.addEventListener("progress", (event) => {
    if (!event.lengthComputable) return;
    const percent = Math.round((event.loaded / event.total) * 100);
    elements.progressPercent.textContent = `${percent}%`;
    elements.progressBar.style.width = `${percent}%`;
    if (percent === 100) elements.progressLabel.textContent = "Registrando y enviando a lectura…";
  });
  xhr.addEventListener("load", async () => {
    elements.uploadProgress.hidden = true;
    let payload = {};
    try { payload = JSON.parse(xhr.responseText || "{}"); } catch (_error) { /* noop */ }
    if (xhr.status < 200 || xhr.status >= 300) {
      showToast(payload.detail || "La carga no pudo completarse.", "error");
      elements.uploadButton.disabled = false;
      return;
    }
    const duplicates = (payload.items || []).filter((item) => item.duplicate).length;
    showToast(duplicates
      ? `Lote recibido. ${duplicates} PDF(s) ya estaban registrados y no se duplicaron.`
      : `Lote recibido: ${payload.count || state.files.length} PDF(s) en procesamiento.`);
    clearFiles();
    await loadDashboard();
  });
  xhr.addEventListener("error", () => {
    elements.uploadProgress.hidden = true;
    elements.uploadButton.disabled = false;
    showToast("No se pudo contactar la aplicación local.", "error");
  });
  xhr.send(formData);
}

function createCell(content, className = "") {
  const cell = document.createElement("td");
  if (className) cell.className = className;
  if (content instanceof Node) cell.append(content);
  else cell.textContent = content;
  return cell;
}

function renderRecords(items) {
  elements.recordsBody.replaceChildren();
  elements.emptyState.hidden = items.length !== 0;
  const hasSearch = elements.searchInput.value.trim().length > 0;
  elements.emptyTitle.textContent = hasSearch ? "Sin coincidencias" : "Aún no hay encuestas";
  elements.emptyCopy.textContent = hasSearch
    ? "Prueba con otro nombre de archivo o ID de respondiente."
    : "La primera carga aparecerá aquí con su estado y respuestas detectadas.";
  items.forEach((item) => {
    const row = document.createElement("tr");
    row.tabIndex = 0;
    row.addEventListener("click", () => openDetail(item.id));
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter") openDetail(item.id);
    });

    const fileBox = document.createElement("div");
    fileBox.className = "file-cell";
    const icon = document.createElement("span");
    icon.className = "file-mini-icon";
    icon.textContent = "PDF";
    const meta = document.createElement("span");
    meta.className = "file-meta";
    const name = document.createElement("span");
    name.className = "file-name";
    name.textContent = item.filename;
    name.title = item.filename;
    const size = document.createElement("span");
    size.className = "file-size";
    size.textContent = `${formatBytes(item.file_size)}${item.page_count ? ` · ${item.page_count} pág.` : ""}`;
    meta.append(name, size);
    fileBox.append(icon, meta);

    const id = document.createElement("span");
    id.className = "id-value";
    id.textContent = item.survey?.respondent_identifier || "—";

    const capture = document.createElement("div");
    capture.className = "capture";
    const count = document.createElement("strong");
    const expected = item.expected_answers || item.survey?.expected_count || 0;
    const detected = item.detected_answers || item.survey?.answered_count || 0;
    count.textContent = expected ? `${detected} de ${expected}` : "Pendiente";
    const method = document.createElement("span");
    method.textContent = extractionMethodLabels[item.extraction_method] || "Sin procesar";
    const meter = document.createElement("div");
    meter.className = "mini-progress";
    const fill = document.createElement("span");
    fill.style.width = `${expected ? Math.min(100, detected / expected * 100) : 0}%`;
    meter.append(fill);
    capture.append(count, method, meter);

    const badge = document.createElement("span");
    badge.className = `status-badge status-${item.status}`;
    badge.textContent = statusLabels[item.status] || item.status;

    const action = document.createElement("button");
    action.type = "button";
    action.className = "row-action";
    action.textContent = "Ver detalle";
    action.addEventListener("click", (event) => {
      event.stopPropagation();
      openDetail(item.id);
    });

    row.append(
      createCell(fileBox),
      createCell(id),
      createCell(capture),
      createCell(badge),
      createCell(formatDate(item.created_at)),
      createCell(action),
    );
    elements.recordsBody.append(row);
  });
}

async function loadUploads() {
  elements.tableLoading.hidden = false;
  try {
    const query = new URLSearchParams({ limit: "100" });
    const search = elements.searchInput.value.trim();
    if (search) query.set("search", search);
    const payload = await requestJson(`/api/uploads?${query}`);
    state.uploads = payload.items || [];
    renderRecords(state.uploads);
  } catch (error) {
    state.uploads = [];
    renderRecords([]);
    showToast(error.message, "error");
  } finally {
    elements.tableLoading.hidden = true;
  }
}

async function loadStats() {
  try {
    const stats = await requestJson("/api/stats");
    elements.statTotal.textContent = stats.total;
    elements.statCompleted.textContent = stats.completed;
    elements.statReview.textContent = stats.needs_review + stats.error;
    elements.statPending.textContent = stats.pending;
    schedulePoll(stats.pending > 0 ? 1800 : 9000);
  } catch (_error) {
    [elements.statTotal, elements.statCompleted, elements.statReview, elements.statPending]
      .forEach((element) => { element.textContent = "—"; });
    schedulePoll(9000);
  }
}

function formatPercent(value) {
  if (value === null || value === undefined) return "Sin aplicables";
  return `${percentFormatter.format(value)} %`;
}

function responseDescription(bucket) {
  if (bucket.applicable === 0) {
    return bucket.not_applicable
      ? `Sin casos aplicables · ${bucket.not_applicable} no aplica`
      : "Sin casos aplicables";
  }
  const parts = [
    `${bucket.answered} respuestas a ítems`,
    `${formatPercent(bucket.coverage_percent)} cobertura`,
  ];
  if (bucket.review) parts.push(`${bucket.review} por revisar`);
  if (bucket.not_applicable) parts.push(`${bucket.not_applicable} no aplica`);
  return parts.join(" · ");
}

function categoryAriaLabel(label, bucket) {
  const values = bucket.categories
    .map((category) => `${category.label}: ${category.count} (${formatPercent(category.percent)})`)
    .join(", ");
  return `${label}. ${values}. ${responseDescription(bucket)}.`;
}

function createGlobalCategoryRow(category, totalAnswered) {
  const row = document.createElement("div");
  row.className = "category-bar-row";

  const label = document.createElement("div");
  label.className = "category-bar-label";
  const code = document.createElement("span");
  code.className = `category-code ${categoryClasses[category.code] || ""}`;
  code.textContent = category.code;
  const name = document.createElement("span");
  name.textContent = category.label;
  label.append(code, name);

  const track = document.createElement("div");
  track.className = "category-bar-track";
  track.setAttribute("role", "img");
  track.setAttribute(
    "aria-label",
    `${category.label}: ${category.count} de ${totalAnswered} respuestas (${formatPercent(category.percent)})`,
  );
  const fill = document.createElement("span");
  fill.className = `category-bar-fill ${categoryClasses[category.code] || ""}`;
  const width = totalAnswered ? category.count / totalAnswered * 100 : 0;
  fill.style.width = `${width}%`;
  track.append(fill);

  const value = document.createElement("div");
  value.className = "category-bar-value";
  const count = document.createElement("strong");
  count.textContent = category.count;
  const percent = document.createElement("span");
  percent.textContent = formatPercent(category.percent);
  value.append(count, percent);
  row.append(label, track, value);
  return row;
}

function renderLegend(categories) {
  elements.responseLegend.replaceChildren();
  categories.forEach((category) => {
    const item = document.createElement("span");
    item.className = "legend-item";
    const swatch = document.createElement("i");
    swatch.className = categoryClasses[category.code] || "";
    swatch.setAttribute("aria-hidden", "true");
    const text = document.createElement("span");
    text.textContent = `${category.code} · ${category.label}`;
    item.append(swatch, text);
    elements.responseLegend.append(item);
  });
}

function createStackedRow(bucket) {
  const row = document.createElement("div");
  row.className = "stacked-row";

  const copy = document.createElement("div");
  copy.className = "stacked-label";
  const title = document.createElement("strong");
  title.textContent = bucket.label;
  const meta = document.createElement("span");
  meta.textContent = responseDescription(bucket);
  copy.append(title, meta);

  const visual = document.createElement("div");
  visual.className = "stacked-visual";
  if (bucket.answered > 0) {
    const bar = document.createElement("div");
    bar.className = "stacked-bar";
    bar.setAttribute("role", "img");
    bar.setAttribute("aria-label", categoryAriaLabel(bucket.label, bucket));
    bucket.categories.forEach((category) => {
      if (!category.count) return;
      const segment = document.createElement("span");
      segment.className = `stacked-segment ${categoryClasses[category.code] || ""}`;
      const width = category.count / bucket.answered * 100;
      segment.style.width = `${width}%`;
      segment.title = `${category.code} · ${category.label}: ${category.count} (${formatPercent(category.percent)})`;
      if (width >= 8) segment.textContent = category.code;
      bar.append(segment);
    });
    visual.append(bar);
  } else {
    const empty = document.createElement("span");
    empty.className = "stacked-empty";
    empty.textContent = bucket.applicable ? "Sin respuestas contestadas" : "Sin casos aplicables";
    visual.append(empty);
  }

  row.append(copy, visual);
  return row;
}

function addAnalyticsTableRow(bucket, level) {
  const row = document.createElement("tr");
  const heading = document.createElement("th");
  heading.scope = "row";
  const levelNode = document.createElement("span");
  levelNode.className = "analytics-table-level";
  levelNode.textContent = level;
  const labelNode = document.createElement("span");
  labelNode.textContent = bucket.label;
  heading.append(levelNode, labelNode);
  row.append(heading);

  bucket.categories.forEach((category) => {
    const cell = document.createElement("td");
    cell.textContent = `${category.count} (${formatPercent(category.percent)})`;
    row.append(cell);
  });

  [bucket.answered, bucket.review, bucket.not_applicable].forEach((value) => {
    const cell = document.createElement("td");
    cell.textContent = value;
    row.append(cell);
  });
  const coverage = document.createElement("td");
  coverage.textContent = formatPercent(bucket.coverage_percent);
  row.append(coverage);
  elements.analyticsTableBody.append(row);
}

function renderAnalyticsTable(selectedDomain) {
  elements.analyticsTableBody.replaceChildren();
  state.analytics.domains.forEach((domain) => addAnalyticsTableRow(domain, "Dominio"));
  state.analytics.dimensions
    .filter((dimension) => dimension.domain_key === selectedDomain)
    .forEach((dimension) => addAnalyticsTableRow(dimension, "Dimensión"));
}

function renderDimensions() {
  if (!state.analytics) return;
  const selectedDomain = elements.dimensionDomainFilter.value;
  elements.dimensionChart.replaceChildren();
  state.analytics.dimensions
    .filter((dimension) => dimension.domain_key === selectedDomain)
    .forEach((dimension) => elements.dimensionChart.append(createStackedRow(dimension)));
  renderAnalyticsTable(selectedDomain);
}

function renderAnalytics(payload) {
  state.analytics = payload;
  elements.analyticsLoading.hidden = true;

  if (!payload.survey_count) {
    elements.analyticsContent.hidden = true;
    elements.analyticsEmpty.hidden = false;
    elements.analyticsEmptyTitle.textContent = "Aún no hay estadísticas";
    elements.analyticsEmptyCopy.textContent = "Las gráficas aparecerán cuando se procese la primera encuesta.";
    elements.analyticsSummary.textContent = "0 encuestas procesadas";
    return;
  }

  elements.analyticsEmpty.hidden = true;
  elements.analyticsContent.hidden = false;
  const surveyWord = payload.survey_count === 1 ? "encuesta" : "encuestas";
  elements.analyticsSummary.textContent = `${payload.survey_count} ${surveyWord} · ${payload.answered_count} respuestas a ítems · ${formatPercent(payload.coverage_percent)} cobertura`;
  elements.analyticsSummary.title = `${payload.review_count} por revisar · ${payload.not_applicable_count} no aplica`;
  elements.globalChartSubtitle.textContent = `${payload.answered_count} respuestas contestadas; “no aplica” y revisión quedan fuera del porcentaje.`;

  elements.categoryBars.replaceChildren();
  payload.response_categories.forEach((category) => {
    elements.categoryBars.append(createGlobalCategoryRow(category, payload.answered_count));
  });
  renderLegend(payload.response_categories);

  elements.domainChart.replaceChildren();
  payload.domains.forEach((domain) => elements.domainChart.append(createStackedRow(domain)));

  const previousDomain = elements.dimensionDomainFilter.value;
  elements.dimensionDomainFilter.replaceChildren();
  payload.domains.forEach((domain) => {
    const option = document.createElement("option");
    option.value = domain.key;
    option.textContent = domain.label;
    elements.dimensionDomainFilter.append(option);
  });
  if (payload.domains.some((domain) => domain.key === previousDomain)) {
    elements.dimensionDomainFilter.value = previousDomain;
  }
  renderDimensions();

  elements.analyticsMethodology.textContent = payload.methodology;
  elements.analyticsSource.href = payload.source.url;
  elements.analyticsSource.textContent = payload.source.label;
}

async function loadAnalytics() {
  if (!state.analytics) elements.analyticsLoading.hidden = false;
  try {
    const payload = await requestJson("/api/analytics");
    renderAnalytics(payload);
  } catch (error) {
    state.analytics = null;
    elements.analyticsLoading.hidden = true;
    elements.analyticsContent.hidden = true;
    elements.analyticsEmpty.hidden = false;
    elements.analyticsEmptyTitle.textContent = "No fue posible cargar las estadísticas";
    elements.analyticsEmptyCopy.textContent = error.message;
    elements.analyticsSummary.textContent = "Datos no disponibles";
  }
}

function schedulePoll(delay) {
  window.clearTimeout(state.pollTimer);
  state.pollTimer = window.setTimeout(loadDashboard, delay);
}

async function loadDashboard() {
  const connected = await loadHealth();
  if (!connected) {
    elements.tableLoading.hidden = true;
    renderRecords([]);
    elements.analyticsLoading.hidden = true;
    elements.analyticsContent.hidden = true;
    elements.analyticsEmpty.hidden = false;
    elements.analyticsEmptyTitle.textContent = "MySQL no está disponible";
    elements.analyticsEmptyCopy.textContent = "Las gráficas se recuperarán cuando vuelva la conexión.";
    elements.analyticsSummary.textContent = "Datos no disponibles";
    schedulePoll(9000);
    return;
  }
  await Promise.all([loadUploads(), loadStats(), loadAnalytics()]);
}

function summaryCard(label, value) {
  const article = document.createElement("article");
  const labelNode = document.createElement("span");
  const valueNode = document.createElement("strong");
  labelNode.textContent = label;
  valueNode.textContent = value;
  article.append(labelNode, valueNode);
  return article;
}

function renderDetail(item) {
  elements.drawerTitle.textContent = item.filename;
  elements.drawerBody.replaceChildren();
  const survey = item.survey;

  const summary = document.createElement("section");
  summary.className = "detail-summary";
  summary.append(
    summaryCard("ID respondiente", survey?.respondent_identifier || "No detectado"),
    summaryCard("Estado", statusLabels[item.status] || item.status),
    summaryCard("Atiende clientes", boolLabel(survey?.serves_customers)),
    summaryCard("Es jefe", boolLabel(survey?.is_manager)),
    summaryCard("Respuestas", `${item.detected_answers} / ${item.expected_answers || "—"}`),
    summaryCard("Páginas", String(item.page_count || "—")),
  );
  elements.drawerBody.append(summary);

  const currentIdentifier = survey?.respondent_identifier || "";
  let identifierEditor = null;
  let identifierInput = null;
  if (survey) {
    identifierEditor = document.createElement("section");
    identifierEditor.className = "identifier-editor";
    identifierEditor.hidden = Boolean(currentIdentifier);

    const identifierCopy = document.createElement("div");
    identifierCopy.className = "identifier-editor-copy";
    const identifierTitle = document.createElement("strong");
    identifierTitle.textContent = currentIdentifier
      ? "Editar ID del respondiente"
      : "Completar ID manualmente";
    const identifierHelp = document.createElement("p");
    identifierHelp.textContent = currentIdentifier
      ? "Corrija el dato y guárdelo. Las respuestas de la encuesta no cambiarán."
      : "El escaneo no permitió leerlo con seguridad. Escríbalo tal como aparece en el PDF.";
    identifierCopy.append(identifierTitle, identifierHelp);

    const identifierForm = document.createElement("form");
    identifierForm.className = "identifier-form";
    identifierInput = document.createElement("input");
    identifierInput.type = "text";
    identifierInput.name = "respondent_identifier";
    identifierInput.value = currentIdentifier;
    identifierInput.maxLength = 120;
    identifierInput.autocomplete = "off";
    identifierInput.placeholder = "ID del respondiente";
    identifierInput.setAttribute("aria-label", "ID del respondiente");
    identifierInput.setAttribute("aria-describedby", `identifier-help-${item.id}`);

    const identifierActions = document.createElement("div");
    identifierActions.className = "identifier-form-actions";
    const identifierSave = document.createElement("button");
    identifierSave.type = "submit";
    identifierSave.className = "button button-primary button-small";
    identifierSave.textContent = "Guardar ID";
    identifierSave.disabled = true;
    identifierActions.append(identifierSave);

    if (currentIdentifier) {
      const identifierCancel = document.createElement("button");
      identifierCancel.type = "button";
      identifierCancel.className = "button button-secondary button-small";
      identifierCancel.textContent = "Cancelar";
      identifierCancel.addEventListener("click", () => {
        identifierInput.value = currentIdentifier;
        identifierEditor.hidden = true;
      });
      identifierActions.append(identifierCancel);
    }

    const identifierFeedback = document.createElement("small");
    identifierFeedback.id = `identifier-help-${item.id}`;
    identifierFeedback.textContent = "Use letras, números, punto, guion o guion bajo (máximo 120).";

    const identifierPattern = /^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$/;
    const validateIdentifier = (showError = false) => {
      const value = identifierInput.value.trim();
      const valid = identifierPattern.test(value);
      identifierSave.disabled = !valid || value === currentIdentifier;
      identifierFeedback.classList.toggle("is-error", showError && !valid);
      identifierFeedback.textContent = showError && !valid
        ? "Ingrese un ID válido; no se permiten espacios ni caracteres especiales."
        : "Use letras, números, punto, guion o guion bajo (máximo 120).";
      return valid;
    };
    identifierInput.addEventListener("input", () => validateIdentifier(false));
    identifierForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!validateIdentifier(true)) return;
      const identifier = identifierInput.value.trim();
      if (identifier === currentIdentifier) return;
      identifierInput.disabled = true;
      identifierSave.disabled = true;
      identifierSave.textContent = "Guardando…";
      try {
        const updated = await requestJson(
          `/api/uploads/${item.id}/respondent-identifier`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ respondent_identifier: identifier }),
          },
        );
        showToast("ID del respondiente guardado.");
        renderDetail(updated);
        await Promise.all([loadUploads(), loadStats(), loadAnalytics()]);
      } catch (error) {
        identifierInput.disabled = false;
        identifierSave.textContent = "Guardar ID";
        validateIdentifier(false);
        showToast(error.message, "error");
      }
    });

    identifierForm.append(identifierInput, identifierActions, identifierFeedback);
    identifierEditor.append(identifierCopy, identifierForm);
    elements.drawerBody.append(identifierEditor);
  }

  if (item.error_message) {
    const box = document.createElement("div");
    box.className = "error-box";
    box.textContent = item.error_message;
    elements.drawerBody.append(box);
  }
  if (item.warnings?.length) {
    const box = document.createElement("div");
    box.className = "warning-box";
    box.textContent = item.warnings.join(" · ");
    elements.drawerBody.append(box);
  }

  const actions = document.createElement("div");
  actions.className = "detail-actions";
  const pdf = document.createElement("a");
  pdf.className = "button button-secondary button-small";
  pdf.href = `/api/uploads/${item.id}/file`;
  pdf.target = "_blank";
  pdf.rel = "noreferrer";
  pdf.textContent = "Abrir PDF";
  actions.append(pdf);
  if (currentIdentifier && identifierEditor && identifierInput) {
    const editIdentifier = document.createElement("button");
    editIdentifier.type = "button";
    editIdentifier.className = "button button-secondary button-small";
    editIdentifier.textContent = "Editar ID";
    editIdentifier.addEventListener("click", () => {
      identifierEditor.hidden = false;
      identifierInput.focus();
      identifierInput.select();
    });
    actions.append(editIdentifier);
  }
  if (["error", "needs_review", "completed"].includes(item.status)) {
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "button button-secondary button-small";
    retry.textContent = "Reprocesar";
    retry.addEventListener("click", async () => {
      retry.disabled = true;
      try {
        await requestJson(`/api/uploads/${item.id}/reprocess`, { method: "POST" });
        showToast("La encuesta volvió a la cola de procesamiento.");
        closeDrawer();
        await loadDashboard();
      } catch (error) {
        retry.disabled = false;
        showToast(error.message, "error");
      }
    });
    actions.append(retry);
  }
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "button button-danger button-small";
  remove.textContent = "Eliminar";
  remove.disabled = ["queued", "processing"].includes(item.status);
  if (remove.disabled) {
    remove.title = "Disponible cuando termine el procesamiento";
  }
  remove.addEventListener("click", async () => {
    const confirmed = window.confirm(
      `¿Eliminar "${item.filename}"?\n\nSe borrarán la encuesta, sus respuestas y la copia PDF guardada por la aplicación. Esta acción no se puede deshacer.`,
    );
    if (!confirmed) return;

    remove.disabled = true;
    remove.textContent = "Eliminando…";
    try {
      const deleted = await requestJson(`/api/uploads/${item.id}`, { method: "DELETE" });
      closeDrawer();
      showToast(
        deleted?.file_deleted
          ? "Encuesta, respuestas y PDF eliminados."
          : "La encuesta se eliminó de MySQL, pero no se pudo borrar la copia PDF.",
        deleted?.file_deleted ? "info" : "error",
      );
      await loadDashboard();
    } catch (error) {
      remove.disabled = false;
      remove.textContent = "Eliminar";
      showToast(error.message, "error");
    }
  });
  actions.append(remove);
  elements.drawerBody.append(actions);

  if (!survey?.responses) return;
  const heading = document.createElement("div");
  heading.className = "answers-heading";
  const title = document.createElement("h3");
  title.textContent = "Respuestas normalizadas";
  const filter = document.createElement("select");
  filter.className = "answers-filter";
  [["all", "Todas"], ["review", "Solo por revisar"], ["answered", "Solo respondidas"]]
    .forEach(([value, label]) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      filter.append(option);
    });
  heading.append(title, filter);
  elements.drawerBody.append(heading);

  const list = document.createElement("div");
  list.className = "answer-list";
  elements.drawerBody.append(list);

  const paintAnswers = () => {
    list.replaceChildren();
    const selected = filter.value;
    survey.responses
      .filter((response) => selected === "all"
        || (selected === "review" && ["blank", "multiple", "uncertain"].includes(response.status))
        || (selected === "answered" && response.status === "answered"))
      .forEach((response) => {
        const row = document.createElement("article");
        row.className = `answer-row${["blank", "multiple", "uncertain"].includes(response.status) ? " is-review" : ""}${response.status === "not_applicable" ? " is-na" : ""}`;
        const number = document.createElement("span");
        number.className = "answer-number";
        number.textContent = `P${response.question_number}`;
        const question = document.createElement("span");
        question.className = "answer-question";
        question.textContent = response.question_text;
        const isReview = ["blank", "multiple", "uncertain"].includes(response.status);
        const answer = document.createElement(isReview ? "div" : "span");
        answer.className = isReview ? "answer-review" : "answer-value";

        if (isReview) {
          const note = document.createElement("strong");
          note.className = "answer-review-note";
          note.textContent = reviewStatusLabels[response.status] || "Requiere revisión";
          answer.append(note);

          if (response.detected_answer_labels?.length) {
            const candidates = document.createElement("span");
            candidates.className = "answer-candidates";
            candidates.textContent = `Marcas: ${response.detected_answer_labels.join(" y ")}`;
            answer.append(candidates);
          }

          const editor = document.createElement("div");
          editor.className = "answer-review-editor";
          const select = document.createElement("select");
          select.setAttribute("aria-label", `Respuesta correcta para la pregunta ${response.question_number}`);
          const placeholder = document.createElement("option");
          placeholder.value = "";
          placeholder.textContent = "Elegir respuesta…";
          select.append(placeholder);
          answerOptions.forEach(([code, label]) => {
            const option = document.createElement("option");
            option.value = code;
            option.textContent = `${code} · ${label}`;
            select.append(option);
          });
          const save = document.createElement("button");
          save.type = "button";
          save.className = "answer-save";
          save.textContent = "Guardar";
          save.disabled = true;
          select.addEventListener("change", () => { save.disabled = !select.value; });
          save.addEventListener("click", async () => {
            if (!select.value) return;
            select.disabled = true;
            save.disabled = true;
            save.textContent = "Guardando…";
            try {
              const updated = await requestJson(
                `/api/uploads/${item.id}/responses/${response.question_number}`,
                {
                  method: "PATCH",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ answer_code: select.value }),
                },
              );
              showToast(`Pregunta ${response.question_number} corregida y registrada.`);
              renderDetail(updated);
              await Promise.all([loadUploads(), loadStats(), loadAnalytics()]);
            } catch (error) {
              select.disabled = false;
              save.disabled = !select.value;
              save.textContent = "Guardar";
              showToast(error.message, "error");
            }
          });
          editor.append(select, save);
          answer.append(editor);
        } else {
          answer.textContent = response.status === "answered"
            ? response.answer_label
            : "No aplica";
          if (response.manually_reviewed) {
            answer.textContent = `✓ ${answer.textContent}`;
            const originalMarks = response.detected_answer_labels?.length
              ? ` Marcas originales: ${response.detected_answer_labels.join(" y ")}.`
              : "";
            answer.title = `Respuesta confirmada manualmente.${originalMarks}`;
          } else if (response.confidence != null) {
            answer.title = `Confianza ${(response.confidence * 100).toFixed(1)}%`;
          }
        }
        row.append(number, question, answer);
        list.append(row);
      });
  };
  filter.addEventListener("change", paintAnswers);
  paintAnswers();
}

async function openDetail(uploadId) {
  elements.drawerBackdrop.hidden = false;
  elements.detailDrawer.classList.add("is-open");
  elements.detailDrawer.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
  elements.drawerBody.replaceChildren();
  const loading = document.createElement("div");
  loading.className = "drawer-loading";
  loading.innerHTML = '<span class="spinner"></span> Cargando detalle…';
  elements.drawerBody.append(loading);
  try {
    const item = await requestJson(`/api/uploads/${uploadId}`);
    renderDetail(item);
  } catch (error) {
    elements.drawerBody.replaceChildren();
    const box = document.createElement("div");
    box.className = "error-box";
    box.textContent = error.message;
    elements.drawerBody.append(box);
  }
}

function closeDrawer() {
  elements.detailDrawer.classList.remove("is-open");
  elements.detailDrawer.setAttribute("aria-hidden", "true");
  elements.drawerBackdrop.hidden = true;
  document.body.style.overflow = "";
}

elements.fileInput.addEventListener("change", (event) => setFiles(event.target.files));
elements.clearSelection.addEventListener("click", clearFiles);
elements.uploadButton.addEventListener("click", uploadFiles);
elements.refreshButton.addEventListener("click", loadDashboard);
elements.dimensionDomainFilter.addEventListener("change", renderDimensions);
elements.closeDrawer.addEventListener("click", closeDrawer);
elements.drawerBackdrop.addEventListener("click", closeDrawer);
document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeDrawer(); });

["dragenter", "dragover"].forEach((name) => elements.dropzone.addEventListener(name, (event) => {
  event.preventDefault();
  elements.dropzone.classList.add("is-dragging");
}));
["dragleave", "drop"].forEach((name) => elements.dropzone.addEventListener(name, (event) => {
  event.preventDefault();
  elements.dropzone.classList.remove("is-dragging");
}));
elements.dropzone.addEventListener("drop", (event) => setFiles(event.dataTransfer.files));
elements.searchInput.addEventListener("input", () => {
  window.clearTimeout(state.searchTimer);
  state.searchTimer = window.setTimeout(loadUploads, 280);
});

loadDashboard();
