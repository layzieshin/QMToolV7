(() => {
  "use strict";

  const STORAGE_KEY = "qmtool.container.module-builder.v1";
  const FIELD_TYPES = [
    ["string", "Kurzer Text"], ["multiline_text", "Langer Text"],
    ["integer", "Ganzzahl"], ["decimal", "Dezimalzahl"],
    ["boolean", "Ja / Nein"], ["date", "Datum"],
    ["datetime", "Datum & Uhrzeit"], ["single_select", "Einfachauswahl"],
    ["multi_select", "Mehrfachauswahl"], ["user_reference", "Benutzerverweis"],
    ["object_reference", "Objektverweis"], ["artifact_reference", "Nachweisverweis"],
  ];
  const ROLES = ["ADMIN", "QMB", "USER"];
  const ISSUE_TEXT = {
    "container.blueprint.invalid_key": "Der Modulschlüssel muss mit einem Kleinbuchstaben beginnen und darf nur a–z, 0–9, _ und - enthalten.",
    "container.blueprint.invalid_name": "Das Modul benötigt einen Namen mit höchstens 120 Zeichen.",
    "container.blueprint.description_too_long": "Die Beschreibung darf höchstens 1.000 Zeichen enthalten.",
    "container.blueprint.invalid_template_count": "Das Modul benötigt 1 bis 50 Bausteine.",
    "container.blueprint.duplicate_template_key": "Jeder Baustein benötigt einen eindeutigen Schlüssel.",
    "container.blueprint.invalid_template_key": "Ein Bausteinschlüssel ist ungültig.",
    "container.blueprint.root_not_found": "Bitte ein vorhandenes Objekt als Haupteintrag wählen.",
    "container.blueprint.root_must_be_object": "Der Haupteintrag muss ein Objekt sein, kein Nachweis.",
    "container.blueprint.child_template_not_found": "Eine Unterstruktur verweist auf einen fehlenden Baustein.",
    "container.blueprint.child_must_be_object": "Unterstrukturen können nur auf Objekt-Bausteine zeigen.",
    "container.blueprint.auto_child_required_fields": "Ein automatisch erzeugter Pflicht-Unterbaustein besitzt eigene Pflichtfelder. Diese können bei der automatischen Anlage nicht ausgefüllt werden.",
    "container.blueprint.cycle": "Die Unterstrukturen bilden einen Kreis. Mindestens eine Verbindung muss entfernt werden.",
    "container.blueprint.key_exists": "Dieser Modulschlüssel wurde bereits veröffentlicht. Für einen neuen Test bitte einen neuen Schlüssel verwenden.",
    "container.template.invalid_definition": "Name und mindestens eine Erstellerrolle sind erforderlich.",
    "container.template.invalid_roles": "Rollen dürfen nicht leer oder doppelt sein.",
    "container.template.duplicate_field": "Feldschlüssel müssen ausgefüllt und eindeutig sein.",
    "container.template.invalid_field_options": "Auswahlwerte dürfen nicht leer oder doppelt sein.",
    "container.template.options_for_non_select": "Auswahlwerte sind nur bei Einfach- oder Mehrfachauswahl erlaubt.",
    "container.template.artifact_children_forbidden": "Nachweise können keine strukturellen Unterobjekte besitzen.",
    "container.template.invalid_child": "Eine Unterstruktur enthält ungültige Mengen oder einen doppelten Schlüssel.",
    "container.template.invalid_lifecycle": "Status oder Übergänge sind unvollständig bzw. widersprüchlich.",
  };

  const starterBlueprint = () => ({
    key: `device-management-${Date.now().toString(36)}`,
    name: "Gerätemanagement",
    description: "Verwaltet Geräte, ihre Wartungen und zugehörige Nachweise.",
    root_template_key: "device",
    templates: [
      {
        key: "device", kind: "OBJECT", name: "Gerät", create_roles: ["ADMIN", "QMB"],
        fields: [
          field("name", "string", {required: true, searchable: true, printable: true}),
          field("serial_number", "string", {required: true, searchable: true, printable: true}),
          field("manufacturer", "string", {searchable: true, printable: true}),
        ],
        children: [{key: "maintenance", template_key: "maintenance", min_count: 1, max_count: null, auto_create: true, mode: "FIXED"}],
        initial_state: "ACTIVE",
        lifecycle_states: [{code: "ACTIVE", initial: true}, {code: "OUT_OF_SERVICE", initial: false}],
        lifecycle_transitions: [{from_state: "ACTIVE", to_state: "OUT_OF_SERVICE", allowed_roles: ["QMB"], reason_required: true, signature_required: false}],
      },
      {
        key: "maintenance", kind: "OBJECT", name: "Wartungen", create_roles: ["ADMIN", "QMB"],
        fields: [field("note", "multiline_text", {printable: true, historized: true})], children: [],
        initial_state: "ACTIVE", lifecycle_states: [], lifecycle_transitions: [],
      },
      {
        key: "evidence", kind: "ARTIFACT", name: "Wartungsnachweis", create_roles: ["ADMIN", "QMB"],
        fields: [field("title", "string", {required: true, printable: true}), field("performed_on", "date", {printable: true, relevant_for_review: true})],
        children: [], initial_state: "ACTIVE", lifecycle_states: [], lifecycle_transitions: [],
      },
    ],
  });

  function field(key, fieldType, flags = {}) {
    return {key, field_type: fieldType, required: false, searchable: false, linkable: false, printable: false, relevant_for_review: false, historized: false, editable: true, visible: true, options: [], ...flags};
  }
  const clone = value => JSON.parse(JSON.stringify(value));
  const $ = selector => document.querySelector(selector);
  const escapeHtml = value => String(value ?? "").replace(/[&<>'"]/g, char => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"}[char]));
  const slugify = value => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 64) || "baustein";
  const selectedTemplate = () => state.blueprint.templates.find(item => item.key === state.selectedKey) || state.blueprint.templates[0];
  const objectTemplates = () => state.blueprint.templates.filter(item => item.kind === "OBJECT");
  const typeLabel = value => FIELD_TYPES.find(([key]) => key === value)?.[1] || value;
  const fieldTypeOptions = selected => FIELD_TYPES.map(([value, label]) => `<option value="${value}" ${value === selected ? "selected" : ""}>${label}</option>`).join("");

  let state = {
    blueprint: loadBlueprint(),
    selectedKey: null,
    view: "structure",
    validation: null,
    published: null,
    publishedModules: [],
    testResult: null,
  };
  state.selectedKey = state.blueprint.root_template_key || state.blueprint.templates[0]?.key;

  function loadBlueprint() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? normalizeBlueprint(JSON.parse(saved)) : starterBlueprint();
    } catch (_error) {
      return starterBlueprint();
    }
  }

  function normalizeBlueprint(value) {
    if (!value || typeof value !== "object" || !Array.isArray(value.templates)) throw new Error("invalid blueprint");
    const result = clone(value);
    result.description ??= "";
    result.templates = result.templates.map(template => ({
      key: template.key || slugify(template.name), kind: template.kind || "OBJECT", name: template.name || "Unbenannter Baustein",
      create_roles: Array.isArray(template.create_roles) && template.create_roles.length ? template.create_roles : ["ADMIN"],
      fields: (template.fields || []).map(item => field(item.key || "feld", item.field_type || "string", item)),
      children: template.kind === "ARTIFACT" ? [] : (template.children || []),
      initial_state: template.initial_state || "ACTIVE", lifecycle_states: template.lifecycle_states || [], lifecycle_transitions: template.lifecycle_transitions || [],
    }));
    return result;
  }

  function save() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.blueprint));
    state.validation = null;
    const publishedSnapshot = localStorage.getItem(`${STORAGE_KEY}.published.${state.blueprint.key}`);
    if (!publishedSnapshot || publishedSnapshot !== JSON.stringify(state.blueprint)) state.published = null;
    const marker = $("#save-state");
    if (marker) {
      marker.textContent = "Gespeichert";
      marker.animate([{opacity: .3}, {opacity: 1}], {duration: 240});
    }
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {headers: {"Content-Type": "application/json"}, ...options});
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = payload.detail || {};
      const error = new Error(detail.code || `HTTP ${response.status}`);
      error.code = detail.code;
      error.params = detail.params || {};
      throw error;
    }
    return payload;
  }

  function toast(message, error = false) {
    const item = document.createElement("div");
    item.className = `toast${error ? " error" : ""}`;
    item.textContent = message;
    $("#toast-region").append(item);
    setTimeout(() => item.remove(), 4200);
  }

  function render() {
    const template = selectedTemplate();
    if (template && !state.selectedKey) state.selectedKey = template.key;
    const publishButton = document.querySelector('.top-actions [data-action="publish"]');
    publishButton.disabled = Boolean(state.published);
    publishButton.textContent = state.published ? "✓ Veröffentlicht" : "Veröffentlichen";
    $("#crumb-name").textContent = state.blueprint.name || "Neues Modul";
    renderNavigation();
    $("#workspace").innerHTML = state.view === "preview" ? renderPreview() : renderStructure(template);
    $("#inspector").innerHTML = renderInspector(template);
    bindInputs();
  }

  function renderNavigation() {
    document.querySelectorAll("[data-view]").forEach(button => button.classList.toggle("is-active", button.dataset.view === state.view));
    $("#template-tree").innerHTML = state.blueprint.templates.map(template => `
      <button class="tree-item ${template.key === state.selectedKey ? "is-selected" : ""}" data-action="select-template" data-key="${escapeHtml(template.key)}">
        <span class="type-dot ${template.kind === "ARTIFACT" ? "artifact" : "object"}"></span>
        <span class="label">${escapeHtml(template.name)}</span>
        ${template.key === state.blueprint.root_template_key ? "<small>Start</small>" : ""}
      </button>`).join("") || `<div class="muted">Noch keine Bausteine</div>`;
    $("#published-list").innerHTML = state.publishedModules.length ? state.publishedModules.map(item => `
      <div class="published-card"><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.blueprint_key)} · ${item.templates.length} Bausteine</small></div>`).join("") : `<span class="muted">Noch nichts veröffentlicht</span>`;
  }

  function renderModuleHeader() {
    return `
      <div class="page-icon">◫</div>
      <input class="page-title" aria-label="Modulname" data-blueprint="name" value="${escapeHtml(state.blueprint.name)}" placeholder="Modulname">
      <textarea class="page-description" aria-label="Modulbeschreibung" data-blueprint="description" placeholder="Wofür wird dieses Modul verwendet?">${escapeHtml(state.blueprint.description)}</textarea>
      <div class="module-meta">
        <label class="meta-pill">Schlüssel <input data-blueprint="key" value="${escapeHtml(state.blueprint.key)}"></label>
        <span class="meta-pill">${state.blueprint.templates.length} Bausteine</span>
        <span class="meta-pill">${state.published ? "✓ veröffentlicht" : "Entwurf"}</span>
      </div>`;
  }

  function renderStructure(template) {
    if (!template) return `${renderModuleHeader()}<div class="empty-block"><b>Noch kein Baustein.</b><br><button class="button small" data-action="add-object">Erstes Objekt anlegen</button></div>`;
    return `${renderModuleHeader()}
      <div class="template-header">
        <div class="template-identity">
          <div class="template-icon ${template.kind === "ARTIFACT" ? "artifact" : ""}">${template.kind === "ARTIFACT" ? "◆" : "□"}</div>
          <div><h2>${escapeHtml(template.name)}</h2><p>${template.kind === "ARTIFACT" ? "Nachweis / Datei-Container" : "Objekt / Struktur-Container"} · ${escapeHtml(template.key)}</p></div>
        </div>
        <button class="button ghost danger small" data-action="delete-template">Baustein löschen</button>
      </div>
      ${renderFields(template)}
      ${template.kind === "OBJECT" ? renderChildren(template) : ""}
      ${renderLifecycle(template)}`;
  }

  function renderFields(template) {
    return `<section>
      <div class="section-head"><div><h2>Datenfelder</h2><p>Jedes Feld ist ein eigenständiger, typisierter Block.</p></div><button class="button small" data-action="add-field">＋ Feld</button></div>
      <div class="block-list">${template.fields.length ? template.fields.map((item, index) => `
        <div class="block">
          <div class="block-row">
            <span class="drag-handle">••</span>
            <input aria-label="Feldschlüssel" data-field-index="${index}" data-field-prop="key" value="${escapeHtml(item.key)}" placeholder="feldschluessel">
            <select aria-label="Feldtyp" data-field-index="${index}" data-field-prop="field_type">${fieldTypeOptions(item.field_type)}</select>
            <div class="block-tools">
              <button class="icon-button" data-action="move-field-up" data-index="${index}" title="Nach oben">↑</button>
              <button class="icon-button" data-action="move-field-down" data-index="${index}" title="Nach unten">↓</button>
              <button class="icon-button danger" data-action="delete-field" data-index="${index}" title="Entfernen">×</button>
            </div>
          </div>
          <div class="block-details">
            ${["required", "searchable", "printable", "relevant_for_review", "historized", "linkable", "editable", "visible"].map(flag => `<label class="check"><input type="checkbox" data-field-index="${index}" data-field-prop="${flag}" ${item[flag] ? "checked" : ""}>${flagLabel(flag)}</label>`).join("")}
            ${["single_select", "multi_select"].includes(item.field_type) ? `<input class="options-input" data-field-index="${index}" data-field-prop="options" value="${escapeHtml((item.options || []).join(", "))}" placeholder="Auswahlwerte, mit Komma getrennt">` : ""}
          </div>
        </div>`).join("") : `<div class="empty-block">Noch keine Felder. Ein Baustein darf auch feldlos sein.</div>`}
      </div>
      <button class="add-block" data-action="add-field">＋ Weiteres Feld hinzufügen</button>
    </section>`;
  }

  function renderChildren(template) {
    const targets = objectTemplates().filter(item => item.key !== template.key);
    return `<section>
      <div class="section-head"><div><h2>Unterstruktur</h2><p>Verbindet diesen Baustein mit weiteren Objekt-Bausteinen.</p></div><button class="button small" data-action="add-child" ${targets.length ? "" : "disabled"}>＋ Verbindung</button></div>
      <div class="block-list">${template.children.length ? template.children.map((child, index) => `
        <div class="block">
          <div class="block-row">
            <span class="drag-handle">↳</span>
            <input aria-label="Verbindungsschlüssel" data-child-index="${index}" data-child-prop="key" value="${escapeHtml(child.key)}">
            <select aria-label="Zielbaustein" data-child-index="${index}" data-child-prop="template_key">${targets.map(target => `<option value="${escapeHtml(target.key)}" ${target.key === child.template_key ? "selected" : ""}>${escapeHtml(target.name)}</option>`).join("")}</select>
            <button class="icon-button danger" data-action="delete-child" data-index="${index}" title="Entfernen">×</button>
          </div>
          <div class="block-details">
            <label class="check">Minimum <input type="number" min="0" data-child-index="${index}" data-child-prop="min_count" value="${child.min_count}"></label>
            <label class="check">Maximum <input type="number" min="0" data-child-index="${index}" data-child-prop="max_count" value="${child.max_count ?? ""}" placeholder="∞"></label>
            <label class="check"><input type="checkbox" data-child-index="${index}" data-child-prop="auto_create" ${child.auto_create ? "checked" : ""}>Automatisch anlegen</label>
            <label class="check">Struktur <select data-child-index="${index}" data-child-prop="mode"><option value="FLEXIBLE" ${child.mode === "FLEXIBLE" ? "selected" : ""}>Flexibel</option><option value="FIXED" ${child.mode === "FIXED" ? "selected" : ""}>Fest</option><option value="MAINTENANCE" ${child.mode === "MAINTENANCE" ? "selected" : ""}>Wartung</option></select></label>
          </div>
        </div>`).join("") : `<div class="empty-block">Keine feste Unterstruktur. Objekte dieses Typs können trotzdem flexibel angelegt werden.</div>`}
      </div>
    </section>`;
  }

  function renderLifecycle(template) {
    const states = template.lifecycle_states || [];
    return `<section>
      <div class="section-head"><div><h2>Status & Übergänge</h2><p>Optionaler Lifecycle; ohne Einträge bleibt der Status „ACTIVE“.</p></div><button class="button small" data-action="add-state">＋ Status</button></div>
      <div class="block-list">${states.map((item, index) => `
        <div class="block"><div class="block-row"><span class="drag-handle">○</span><input data-state-index="${index}" data-state-prop="code" value="${escapeHtml(item.code)}"><label class="check"><input type="radio" name="initial-state" data-action="set-initial" data-index="${index}" ${item.initial ? "checked" : ""}>Startstatus</label><button class="icon-button danger" data-action="delete-state" data-index="${index}">×</button></div></div>`).join("") || `<div class="empty-block">Standardstatus ACTIVE wird automatisch verwendet.</div>`}</div>
      ${states.length > 1 ? `<div class="section-head"><div><h2>Erlaubte Übergänge</h2></div><button class="button small" data-action="add-transition">＋ Übergang</button></div>
      <div class="block-list">${(template.lifecycle_transitions || []).map((item, index) => `
        <div class="block"><div class="block-row"><span class="drag-handle">→</span><select data-transition-index="${index}" data-transition-prop="from_state">${stateOptions(states, item.from_state)}</select><select data-transition-index="${index}" data-transition-prop="to_state">${stateOptions(states, item.to_state)}</select><button class="icon-button danger" data-action="delete-transition" data-index="${index}">×</button></div>
        <div class="block-details"><label class="check"><input type="checkbox" data-transition-index="${index}" data-transition-prop="reason_required" ${item.reason_required ? "checked" : ""}>Begründung</label><label class="check"><input type="checkbox" data-transition-index="${index}" data-transition-prop="signature_required" ${item.signature_required ? "checked" : ""}>Signatur</label>${ROLES.map(role => `<label class="check"><input type="checkbox" data-transition-role="${role}" data-index="${index}" ${(item.allowed_roles || []).includes(role) ? "checked" : ""}>${role}</label>`).join("")}</div></div>`).join("") || `<div class="empty-block">Noch keine Übergänge.</div>`}</div>` : ""}
    </section>`;
  }

  function renderInspector(template) {
    return `<section class="inspector-section"><h3>Baustein</h3>${template ? `
      <div class="property"><label>Name</label><input data-template-prop="name" value="${escapeHtml(template.name)}"></div>
      <div class="property"><label>Schlüssel</label><input data-template-prop="key" value="${escapeHtml(template.key)}"></div>
      <div class="property"><label>Art</label><select data-template-prop="kind"><option value="OBJECT" ${template.kind === "OBJECT" ? "selected" : ""}>Objekt</option><option value="ARTIFACT" ${template.kind === "ARTIFACT" ? "selected" : ""}>Nachweis</option></select></div>
      <div class="property"><label>Haupteintrag</label><input type="radio" name="root" data-action="make-root" ${template.key === state.blueprint.root_template_key ? "checked" : ""} ${template.kind !== "OBJECT" ? "disabled" : ""}></div>
      <div class="property"><label>Ersteller</label><div class="role-grid">${ROLES.map(role => `<label class="role-chip"><input type="checkbox" data-template-role="${role}" ${template.create_roles.includes(role) ? "checked" : ""}><span>${role}</span></label>`).join("")}</div></div>` : `<span class="muted">Kein Baustein gewählt.</span>`}</section>
      <section class="inspector-section"><h3>Serverprüfung</h3>${renderValidation()}</section>
      <section class="inspector-section"><h3>Entwurf</h3><button class="button ghost small" data-action="reset">Beispiel wiederherstellen</button></section>`;
  }

  function renderValidation() {
    if (!state.validation) return `<div class="validation-card"><div class="validation-title">○ Noch nicht geprüft</div><p class="muted">Die verbindliche Prüfung läuft im Container-Backend.</p><button class="button secondary small" data-action="validate">Jetzt prüfen</button></div>`;
    if (state.validation.valid) return `<div class="validation-card good"><div class="validation-title">✓ Bereit zur Veröffentlichung</div><p>Reihenfolge: ${state.validation.deployment_order.map(escapeHtml).join(" → ")}</p></div>${state.published ? renderPublishedResult() : ""}`;
    return `<div class="validation-card bad"><div class="validation-title">! ${state.validation.issues.length} Punkt${state.validation.issues.length === 1 ? "" : "e"} offen</div><ul class="issue-list">${state.validation.issues.map(issue => `<li>${escapeHtml(ISSUE_TEXT[issue.code] || issue.code)}${issue.template_key ? ` <b>(${escapeHtml(issue.template_key)})</b>` : ""}</li>`).join("")}</ul></div>`;
  }

  function renderPublishedResult() {
    return `<div class="published-result"><b>Modul veröffentlicht</b><span class="muted"> · ${state.published.templates.length} Bausteine</span><code>${escapeHtml(state.published.uid)}</code><button class="button small" data-view="preview">Testinstanz anlegen</button></div>`;
  }

  function renderPreview() {
    const published = state.published;
    if (!published) return `${renderModuleHeader()}<div class="empty-block"><b>Erst veröffentlichen, dann testen.</b><br>Die Testinstanz verwendet ausschließlich die vom Backend zurückgegebene Root-Template-UID.<br><br><button class="button secondary" data-action="validate">Entwurf prüfen</button></div>`;
    state.published = published;
    const root = state.blueprint.templates.find(item => item.key === state.blueprint.root_template_key);
    return `${renderModuleHeader()}<section>
      <div class="section-head"><div><h2>Erste Testinstanz</h2><p>Erzeugt ein echtes Objekt im lokalen Demo-Backend.</p></div></div>
      <form id="test-instance-form" class="test-form">${(root?.fields || []).map((item, index) => renderTestField(item, index)).join("") || `<div class="empty-block">Der Haupteintrag besitzt keine Felder.</div>`}
        <button class="button primary" type="submit">${escapeHtml(root?.name || "Objekt")} anlegen</button>
      </form>
      ${state.testResult ? `<div class="success-panel"><b>✓ Testinstanz wurde angelegt</b><p>UID: <code>${escapeHtml(state.testResult.uid)}</code></p><p>Status: ${escapeHtml(state.testResult.state)} · Revision ${state.testResult.revision}</p></div>` : ""}
    </section>`;
  }

  function renderTestField(item, index) {
    const required = item.required ? "required" : "";
    let control;
    if (item.field_type === "boolean") control = `<input type="checkbox" data-test-index="${index}">`;
    else if (item.field_type === "multiline_text") control = `<textarea data-test-index="${index}" ${required}></textarea>`;
    else if (item.field_type === "single_select") control = `<select data-test-index="${index}" ${required}><option value="">Bitte wählen</option>${(item.options || []).map(value => `<option>${escapeHtml(value)}</option>`).join("")}</select>`;
    else if (item.field_type === "multi_select") control = `<input data-test-index="${index}" placeholder="Werte mit Komma trennen" ${required}>`;
    else control = `<input type="${item.field_type === "date" ? "date" : item.field_type === "datetime" ? "datetime-local" : ["integer", "decimal"].includes(item.field_type) ? "number" : "text"}" ${item.field_type === "decimal" ? 'step="any"' : ""} data-test-index="${index}" ${required}>`;
    return `<div class="test-field"><label>${escapeHtml(item.key)}${item.required ? " *" : ""}</label>${control}<small>${escapeHtml(typeLabel(item.field_type))}</small></div>`;
  }

  const flagLabel = flag => ({required: "Pflichtfeld", searchable: "Suchbar", printable: "Druckbar", relevant_for_review: "Prüfrelevant", historized: "Historisiert", linkable: "Verlinkbar", editable: "Bearbeitbar", visible: "Sichtbar"}[flag] || flag);
  const stateOptions = (states, selected) => states.map(item => `<option value="${escapeHtml(item.code)}" ${item.code === selected ? "selected" : ""}>${escapeHtml(item.code)}</option>`).join("");

  function bindInputs() {
    document.querySelectorAll("[data-blueprint]").forEach(input => input.addEventListener("input", () => { state.blueprint[input.dataset.blueprint] = input.value; save(); if (input.dataset.blueprint === "name") $("#crumb-name").textContent = input.value; }));
    document.querySelectorAll("[data-template-prop]").forEach(input => input.addEventListener("change", () => updateTemplateProperty(input.dataset.templateProp, input.value)));
    document.querySelectorAll("[data-template-role]").forEach(input => input.addEventListener("change", () => toggleRole(selectedTemplate().create_roles, input.dataset.templateRole, input.checked)));
    document.querySelectorAll("[data-field-index]").forEach(input => input.addEventListener("change", () => updateIndexed(selectedTemplate().fields, Number(input.dataset.fieldIndex), input.dataset.fieldProp, input)));
    document.querySelectorAll("[data-child-index]").forEach(input => input.addEventListener("change", () => updateIndexed(selectedTemplate().children, Number(input.dataset.childIndex), input.dataset.childProp, input)));
    document.querySelectorAll("[data-state-index]").forEach(input => input.addEventListener("change", () => updateIndexed(selectedTemplate().lifecycle_states, Number(input.dataset.stateIndex), input.dataset.stateProp, input)));
    document.querySelectorAll("[data-transition-index]").forEach(input => input.addEventListener("change", () => updateIndexed(selectedTemplate().lifecycle_transitions, Number(input.dataset.transitionIndex), input.dataset.transitionProp, input)));
    document.querySelectorAll("[data-transition-role]").forEach(input => input.addEventListener("change", () => { const transition = selectedTemplate().lifecycle_transitions[Number(input.dataset.index)]; toggleRole(transition.allowed_roles, input.dataset.transitionRole, input.checked); }));
    $("#test-instance-form")?.addEventListener("submit", createTestInstance);
  }

  function updateTemplateProperty(property, value) {
    const template = selectedTemplate();
    if (!template) return;
    if (property === "key") {
      const oldKey = template.key;
      template.key = value;
      state.selectedKey = value;
      if (state.blueprint.root_template_key === oldKey) state.blueprint.root_template_key = value;
      state.blueprint.templates.forEach(item => item.children.forEach(child => { if (child.template_key === oldKey) child.template_key = value; }));
    } else if (property === "kind") {
      template.kind = value;
      if (value === "ARTIFACT") {
        template.children = [];
        if (state.blueprint.root_template_key === template.key) state.blueprint.root_template_key = objectTemplates().find(item => item.key !== template.key)?.key || "";
      }
    } else template[property] = value;
    save(); render();
  }

  function toggleRole(list, role, enabled) {
    const index = list.indexOf(role);
    if (enabled && index < 0) list.push(role);
    if (!enabled && index >= 0) list.splice(index, 1);
    save(); render();
  }

  function updateIndexed(list, index, property, input) {
    const target = list[index];
    if (!target) return;
    const oldValue = target[property];
    if (property === "options") target[property] = input.value.split(",").map(value => value.trim()).filter(Boolean);
    else if (input.type === "checkbox") target[property] = input.checked;
    else if (["min_count", "max_count"].includes(property)) target[property] = input.value === "" ? null : Number(input.value);
    else target[property] = input.value;
    const template = selectedTemplate();
    if (list === template.fields && property === "field_type" && !["single_select", "multi_select"].includes(target.field_type)) target.options = [];
    if (list === template.lifecycle_states && property === "code") {
      if (target.initial) template.initial_state = target.code;
      template.lifecycle_transitions.forEach(transition => {
        if (transition.from_state === oldValue) transition.from_state = target.code;
        if (transition.to_state === oldValue) transition.to_state = target.code;
      });
    }
    save(); render();
  }

  async function validateBlueprint(showToast = true) {
    try {
      state.validation = await api("/container/blueprints/validate", {method: "POST", body: JSON.stringify(state.blueprint)});
      if (showToast) toast(state.validation.valid ? "Entwurf ist bereit zur Veröffentlichung." : `${state.validation.issues.length} Punkte müssen noch geklärt werden.`, !state.validation.valid);
      render();
      return state.validation.valid;
    } catch (error) {
      toast(`Prüfung fehlgeschlagen: ${ISSUE_TEXT[error.code] || error.code || error.message}`, true);
      return false;
    }
  }

  async function publishBlueprint() {
    if (!(await validateBlueprint(false))) { toast("Bitte zuerst die angezeigten Punkte korrigieren.", true); return; }
    if (!window.confirm(`„${state.blueprint.name}“ jetzt unveränderlich veröffentlichen?`)) return;
    try {
      state.published = await api("/container/blueprints/publish", {method: "POST", body: JSON.stringify(state.blueprint)});
      localStorage.setItem(`${STORAGE_KEY}.published.${state.blueprint.key}`, JSON.stringify(state.blueprint));
      toast("Modul wurde vollständig veröffentlicht.");
      await loadPublished();
      render();
    } catch (error) {
      toast(`Veröffentlichung fehlgeschlagen: ${ISSUE_TEXT[error.code] || error.code || error.message}`, true);
    }
  }

  async function loadPublished() {
    try {
      state.publishedModules = await api("/container/blueprints");
      const matching = state.publishedModules.find(item => item.blueprint_key === state.blueprint.key);
      const publishedSnapshot = localStorage.getItem(`${STORAGE_KEY}.published.${state.blueprint.key}`);
      state.published = matching && publishedSnapshot === JSON.stringify(state.blueprint) ? matching : state.published;
      renderNavigation();
    } catch (error) {
      toast(`Veröffentlichte Module konnten nicht geladen werden: ${error.code || error.message}`, true);
    }
  }

  async function createTestInstance(event) {
    event.preventDefault();
    const root = state.blueprint.templates.find(item => item.key === state.blueprint.root_template_key);
    const values = {};
    (root?.fields || []).forEach((item, index) => {
      const input = document.querySelector(`[data-test-index="${index}"]`);
      if (!input) return;
      let value = input.type === "checkbox" ? input.checked : input.value;
      if (value === "" && !item.required) return;
      if (item.field_type === "integer") value = Number.parseInt(value, 10);
      if (item.field_type === "decimal") value = value;
      if (item.field_type === "multi_select") value = value.split(",").map(entry => entry.trim()).filter(Boolean);
      values[item.key] = value;
    });
    try {
      const rootInfo = await api("/container/workspace-root");
      state.testResult = await api("/container/objects", {method: "POST", body: JSON.stringify({template_version_uid: state.published.root_template_version_uid, parent_kind: "WORKSPACE_ROOT", parent_uid: rootInfo.uid, values})});
      toast("Testinstanz wurde im Demo-Backend angelegt.");
      render();
    } catch (error) {
      toast(`Testinstanz fehlgeschlagen: ${ISSUE_TEXT[error.code] || error.code || error.message}`, true);
    }
  }

  function addTemplate(kind) {
    const base = kind === "OBJECT" ? "Neues Objekt" : "Neuer Nachweis";
    let key = slugify(base);
    let suffix = 2;
    while (state.blueprint.templates.some(item => item.key === key)) key = `${slugify(base)}-${suffix++}`;
    const template = {key, kind, name: base, create_roles: ["ADMIN"], fields: [], children: [], initial_state: "ACTIVE", lifecycle_states: [], lifecycle_transitions: []};
    state.blueprint.templates.push(template);
    if (!state.blueprint.root_template_key && kind === "OBJECT") state.blueprint.root_template_key = key;
    state.selectedKey = key;
    state.view = "structure";
    save(); render();
  }

  function deleteTemplate() {
    const template = selectedTemplate();
    if (!template || !window.confirm(`Baustein „${template.name}“ aus diesem lokalen Entwurf entfernen?`)) return;
    state.blueprint.templates = state.blueprint.templates.filter(item => item !== template);
    state.blueprint.templates.forEach(item => { item.children = item.children.filter(child => child.template_key !== template.key); });
    if (state.blueprint.root_template_key === template.key) state.blueprint.root_template_key = objectTemplates()[0]?.key || "";
    state.selectedKey = state.blueprint.root_template_key || state.blueprint.templates[0]?.key || null;
    save(); render();
  }

  function moveItem(list, index, delta) {
    const target = index + delta;
    if (target < 0 || target >= list.length) return;
    [list[index], list[target]] = [list[target], list[index]];
    save(); render();
  }

  function exportBlueprint() {
    const blob = new Blob([JSON.stringify(state.blueprint, null, 2)], {type: "application/json"});
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${state.blueprint.key || "container-module"}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
    toast("Entwurf wurde als JSON exportiert.");
  }

  async function importBlueprint(file) {
    try {
      state.blueprint = normalizeBlueprint(JSON.parse(await file.text()));
      state.selectedKey = state.blueprint.root_template_key || state.blueprint.templates[0]?.key;
      state.published = null; state.validation = null; state.testResult = null;
      save(); render();
      await validateBlueprint(false);
      toast("Entwurf wurde importiert und serverseitig geprüft.");
    } catch (error) {
      toast(`Import nicht möglich: ${error.message}`, true);
    }
  }

  document.addEventListener("click", async event => {
    const button = event.target.closest("button, [data-view]");
    if (!button) return;
    if (button.dataset.view) { state.view = button.dataset.view; render(); return; }
    const action = button.dataset.action;
    const template = selectedTemplate();
    if (action === "select-template") { state.selectedKey = button.dataset.key; state.view = "structure"; render(); }
    else if (action === "add-object") addTemplate("OBJECT");
    else if (action === "add-artifact") addTemplate("ARTIFACT");
    else if (action === "delete-template") deleteTemplate();
    else if (action === "add-field") { template.fields.push(field(`field_${template.fields.length + 1}`, "string")); save(); render(); }
    else if (action === "delete-field") { template.fields.splice(Number(button.dataset.index), 1); save(); render(); }
    else if (action === "move-field-up") moveItem(template.fields, Number(button.dataset.index), -1);
    else if (action === "move-field-down") moveItem(template.fields, Number(button.dataset.index), 1);
    else if (action === "add-child") { const target = objectTemplates().find(item => item.key !== template.key); if (target) { template.children.push({key: target.key, template_key: target.key, min_count: 0, max_count: null, auto_create: false, mode: "FLEXIBLE"}); save(); render(); } }
    else if (action === "delete-child") { template.children.splice(Number(button.dataset.index), 1); save(); render(); }
    else if (action === "add-state") { const code = `STATE_${template.lifecycle_states.length + 1}`; if (!template.lifecycle_states.length) template.lifecycle_states.push({code: template.initial_state || "ACTIVE", initial: true}); template.lifecycle_states.push({code, initial: false}); save(); render(); }
    else if (action === "delete-state") { const removed = template.lifecycle_states.splice(Number(button.dataset.index), 1)[0]; template.lifecycle_transitions = template.lifecycle_transitions.filter(item => item.from_state !== removed.code && item.to_state !== removed.code); if (template.lifecycle_states.length && !template.lifecycle_states.some(item => item.initial)) template.lifecycle_states[0].initial = true; template.initial_state = template.lifecycle_states.find(item => item.initial)?.code || "ACTIVE"; save(); render(); }
    else if (action === "set-initial") { template.lifecycle_states.forEach((item, index) => item.initial = index === Number(button.dataset.index)); template.initial_state = template.lifecycle_states[Number(button.dataset.index)].code; save(); render(); }
    else if (action === "add-transition") { const [first, second] = template.lifecycle_states; template.lifecycle_transitions.push({from_state: first.code, to_state: second.code, allowed_roles: ["ADMIN"], reason_required: false, signature_required: false}); save(); render(); }
    else if (action === "delete-transition") { template.lifecycle_transitions.splice(Number(button.dataset.index), 1); save(); render(); }
    else if (action === "make-root") { if (template.kind === "OBJECT") { state.blueprint.root_template_key = template.key; save(); render(); } }
    else if (action === "validate") await validateBlueprint();
    else if (action === "publish") await publishBlueprint();
    else if (action === "refresh-published") await loadPublished();
    else if (action === "export") exportBlueprint();
    else if (action === "import") $("#import-file").click();
    else if (action === "reset" && window.confirm("Lokalen Entwurf durch das Gerätemanagement-Beispiel ersetzen?")) { state.blueprint = starterBlueprint(); state.selectedKey = state.blueprint.root_template_key; state.validation = null; state.published = null; state.testResult = null; save(); render(); }
  });

  $("#import-file").addEventListener("change", event => { const [file] = event.target.files; if (file) importBlueprint(file); event.target.value = ""; });
  render();
  loadPublished();
})();
