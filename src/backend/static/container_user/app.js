(() => {
  "use strict";

  const ERROR_TEXT = {
    "container.authorization.denied": "Für diese Aktion fehlt die Berechtigung.",
    "container.authorization.create_denied": "Dieser Eintrag darf in der aktuellen Sitzung nicht angelegt werden.",
    "container.authorization.confirmed_actor_required": "Die Sitzung konnte nicht als bestätigte Identität aufgelöst werden.",
    "container.revision.conflict": "Der Eintrag wurde zwischenzeitlich geändert. Bitte neu laden und erneut versuchen.",
    "container.archive.read_only": "Archivierte Inhalte sind schreibgeschützt.",
    "container.artifact.immutable": "Der finalisierte Nachweis ist unveränderlich.",
    "container.field.required": "Bitte alle Pflichtfelder ausfüllen.",
    "container.field.invalid_type": "Ein Feldwert hat nicht den erwarteten Typ.",
    "container.field.invalid_option": "Eine Auswahl enthält einen nicht erlaubten Wert.",
    "container.tree.cardinality": "Die maximal erlaubte Anzahl dieser Untereinträge ist erreicht.",
    "container.storage.file_too_large": "Die Datei ist für den Prototyp zu groß.",
    "container.storage.invalid_original_name": "Der Dateiname ist nicht zulässig.",
  };
  const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

  const state = {
    modules: [],
    workspaceUid: null,
    activeModuleUid: null,
    activeObjectUid: null,
    activeDetail: null,
    tree: [],
    details: new Map(),
    collapsed: new Set(),
    editorSubmit: null,
    artifactDetail: null,
    loading: 0,
  };

  const $ = selector => document.querySelector(selector);
  const escapeHtml = value => String(value ?? "").replace(/[&<>'"]/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);
  const humanize = value => String(value || "").replace(/[._-]+/g, " ").replace(/\b\w/g, char => char.toUpperCase());
  const activeModule = () => state.modules.find(item => item.uid === state.activeModuleUid) || null;
  const templateByUid = (uid, module = activeModule()) => module?.templates.find(item => item.template_version_uid === uid) || null;
  const isAllowed = (detail, action) => Boolean(detail?.allowed_actions?.[action]?.allowed);

  function setLoading(active) {
    state.loading = Math.max(0, state.loading + (active ? 1 : -1));
    $("#loading").classList.toggle("is-active", state.loading > 0);
  }

  async function api(path, options = {}) {
    setLoading(true);
    try {
      const headers = {...(options.headers || {})};
      if (options.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
      const response = await fetch(path, {...options, headers});
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = payload?.detail;
        const error = new Error(typeof detail?.code === "string" ? detail.code : `HTTP ${response.status}`);
        error.code = detail?.code;
        error.params = detail?.params || {};
        error.status = response.status;
        throw error;
      }
      return payload;
    } finally {
      setLoading(false);
    }
  }

  function messageFor(error) {
    return ERROR_TEXT[error?.code] || (error?.code ? `Aktion nicht möglich (${error.code}).` : "Die Aktion konnte nicht abgeschlossen werden.");
  }

  function toast(message, error = false) {
    const item = document.createElement("div");
    item.className = `toast${error ? " error" : ""}`;
    item.textContent = message;
    $("#toast-region").append(item);
    setTimeout(() => item.remove(), 4500);
  }

  async function guarded(work, successMessage) {
    try {
      const result = await work();
      if (successMessage) toast(successMessage);
      return result;
    } catch (error) {
      toast(messageFor(error), true);
      return null;
    }
  }

  function valueParts(value) {
    if (Array.isArray(value)) return value;
    if (typeof value === "string" && value.includes("\u001f")) return value.split("\u001f");
    return value == null ? [] : [value];
  }

  function valueText(value) {
    if (value == null || value === "") return "";
    if (typeof value === "boolean") return value ? "Ja" : "Nein";
    if (Array.isArray(value)) return value.join(", ");
    if (typeof value === "string" && value.includes("\u001f")) return value.split("\u001f").join(", ");
    return String(value);
  }

  function objectLabel(detail) {
    if (!detail) return "Wird geladen …";
    const template = templateByUid(detail.entity.template_version_uid);
    const priorities = ["title", "name", "bezeichnung", "number", "nummer", "code", "serial_number"];
    for (const key of priorities) {
      if (valueText(detail.field_values[key])) return valueText(detail.field_values[key]);
    }
    for (const field of template?.fields || []) {
      if (valueText(detail.field_values[field.key])) return valueText(detail.field_values[field.key]);
    }
    return `${template?.name || "Eintrag"} · ${detail.entity.uid.slice(0, 8)}`;
  }

  function fieldRows(template, values) {
    const fields = template?.fields || [];
    if (!fields.length) return `<div class="notice">Dieser Baustein besitzt keine sichtbaren Datenfelder.</div>`;
    return `<dl class="field-table">${fields.map(field => {
      const text = valueText(values[field.key]);
      return `<div class="field-row"><dt>${escapeHtml(humanize(field.key))}</dt><dd>${text ? escapeHtml(text) : '<span class="empty-value">Nicht ausgefüllt</span>'}</dd></div>`;
    }).join("")}</dl>`;
  }

  function setBreadcrumbs(...items) {
    $("#breadcrumbs").innerHTML = items.map((item, index) => `${index ? '<i>/</i>' : ""}<${index === items.length - 1 ? "b" : "span"}>${escapeHtml(item)}</${index === items.length - 1 ? "b" : "span"}>`).join("");
  }

  function renderModules() {
    const list = $("#module-list");
    list.innerHTML = state.modules.length ? state.modules.map(module => `
      <button class="module-button ${module.uid === state.activeModuleUid ? "is-active" : ""}" data-module-uid="${escapeHtml(module.uid)}">
        <span class="module-icon">${escapeHtml(module.name.slice(0, 1).toUpperCase())}</span>
        <span>${escapeHtml(module.name)}</span>
      </button>`).join("") : `<p class="side-hint">Noch kein veröffentlichtes Modul verfügbar.</p>`;
    const module = activeModule();
    const root = module?.templates.find(item => item.is_root);
    $("#new-root-shortcut").hidden = !root?.create_allowed;
  }

  function renderTreeNode(node) {
    const uid = node.detail.entity.uid;
    const hasChildren = node.children.length > 0;
    const collapsed = state.collapsed.has(uid);
    return `<li>
      <div class="tree-node">
        <button class="tree-caret" data-toggle-uid="${escapeHtml(uid)}" ${hasChildren ? "" : "disabled"} aria-label="Unterstruktur ${collapsed ? "öffnen" : "schließen"}">${hasChildren ? (collapsed ? "›" : "⌄") : "·"}</button>
        <button class="tree-entry ${uid === state.activeObjectUid ? "is-active" : ""}" data-object-uid="${escapeHtml(uid)}">
          <span class="tree-dot ${node.detail.entity.archived ? "archived" : ""}"></span><span>${escapeHtml(objectLabel(node.detail))}</span>
        </button>
      </div>
      ${hasChildren && !collapsed ? `<ul class="tree-list">${node.children.map(renderTreeNode).join("")}</ul>` : ""}
    </li>`;
  }

  function renderTree() {
    $("#object-tree").innerHTML = state.tree.length
      ? `<ul class="tree-list">${state.tree.map(renderTreeNode).join("")}</ul>`
      : `<p class="side-hint">Noch keine Einträge. Lege den ersten Haupteintrag an.</p>`;
  }

  async function loadTreeNode(entity, seen = new Set()) {
    if (seen.has(entity.uid)) return null;
    const branchSeen = new Set(seen);
    branchSeen.add(entity.uid);
    const [detail, children] = await Promise.all([
      api(`/container/objects/${encodeURIComponent(entity.uid)}`),
      api(`/container/objects/${encodeURIComponent(entity.uid)}/children`),
    ]);
    state.details.set(entity.uid, detail);
    const nested = (await Promise.all(children.map(child => loadTreeNode(child, branchSeen)))).filter(Boolean);
    return {detail, children: nested};
  }

  async function rebuildTree() {
    const module = activeModule();
    state.details.clear();
    state.tree = module
      ? (await Promise.all(module.root_objects.map(root => loadTreeNode(root)))).filter(Boolean)
      : [];
    renderTree();
  }

  function renderEmpty() {
    setBreadcrumbs("Arbeitsbereich");
    const hasPublished = state.modules.length > 0;
    $("#workspace").innerHTML = `<div class="empty-state"><div>
      <div class="empty-art">${hasPublished ? "◫" : "◇"}</div>
      <h1>${hasPublished ? "Wähle ein Modul" : "Noch kein Modul veröffentlicht"}</h1>
      <p>${hasPublished
        ? "Links findest du alle Module, die für diese Sitzung vom Backend freigegeben wurden."
        : "Erstelle in der Modulwerkstatt zunächst einen Bauplan und veröffentliche ihn. Danach erscheint er hier als Endnutzeransicht."}</p>
      <div class="empty-actions">${hasPublished ? "" : '<a class="button primary" href="/container/admin">Modulwerkstatt öffnen</a>'}<button class="button" data-action="refresh">Neu laden</button></div>
    </div></div>`;
  }

  function moduleStats(module) {
    const objects = module.templates.filter(item => item.kind === "OBJECT").length;
    const artifacts = module.templates.filter(item => item.kind === "ARTIFACT").length;
    return `${objects} Objekttyp${objects === 1 ? "" : "en"} · ${artifacts} Nachweistyp${artifacts === 1 ? "" : "en"}`;
  }

  function renderModuleOverview() {
    const module = activeModule();
    if (!module) return renderEmpty();
    setBreadcrumbs("Arbeitsbereich", module.name);
    const rootTemplate = module.templates.find(item => item.is_root);
    const rootCards = state.tree.map(node => `
      <button class="content-card" data-object-uid="${escapeHtml(node.detail.entity.uid)}">
        <span class="card-icon">□</span><strong>${escapeHtml(objectLabel(node.detail))}</strong>
        <small>${escapeHtml(rootTemplate?.name || "Haupteintrag")} · Status ${escapeHtml(node.detail.entity.state)}</small>
      </button>`).join("");
    $("#workspace").innerHTML = `
      <header class="hero">
        <div class="hero-icon">◫</div><span class="eyebrow">Veröffentlichtes Modul</span>
        <h1>${escapeHtml(module.name)}</h1><p>${escapeHtml(module.description || "Dieses Modul besitzt noch keine Beschreibung.")}</p>
        <div class="hero-meta"><span class="pill">${escapeHtml(moduleStats(module))}</span><span class="pill">${module.root_objects.length} Haupteinträge</span></div>
      </header>
      ${rootTemplate?.create_allowed ? '<div class="page-actions"><button class="button primary" data-action="create-root">＋ Neuer Haupteintrag</button></div>' : ""}
      <section class="section"><div class="section-head"><div><span class="eyebrow">Übersicht</span><h2>Haupteinträge</h2></div></div>
        ${rootCards ? `<div class="card-grid">${rootCards}</div>` : `<div class="notice">Noch keine Einträge sichtbar.${rootTemplate?.create_allowed ? " Mit „Neuer Haupteintrag“ kannst du beginnen." : ""}</div>`}
      </section>`;
  }

  function eligibleChildTemplates(detail) {
    const parentTemplate = templateByUid(detail.entity.template_version_uid);
    return (parentTemplate?.children || []).map(child => ({
      definition: child,
      template: templateByUid(child.template_version_uid),
    })).filter(item => item.template?.create_allowed);
  }

  function eligibleArtifactTemplates() {
    return (activeModule()?.templates || []).filter(item => item.kind === "ARTIFACT" && item.create_allowed);
  }

  function transitionButtons(detail, template) {
    if (!isAllowed(detail, "TRANSITION")) return "";
    return (template.lifecycle_transitions || []).filter(item => item.from_state === detail.entity.state).map(item => `
      <button class="button secondary" data-action="transition" data-to-state="${escapeHtml(item.to_state)}" data-reason-required="${item.reason_required}" data-signature-required="${item.signature_required}">→ ${escapeHtml(humanize(item.to_state))}</button>`).join("");
  }

  function renderObject(detail) {
    const module = activeModule();
    const template = templateByUid(detail.entity.template_version_uid);
    const label = objectLabel(detail);
    setBreadcrumbs(module?.name || "Modul", label);
    const childTemplates = eligibleChildTemplates(detail);
    const artifacts = detail.artifacts || [];
    const artifactCards = artifacts.map(artifact => {
      const artifactTemplate = templateByUid(artifact.template_version_uid);
      return `<button class="content-card" data-artifact-uid="${escapeHtml(artifact.uid)}">
        <span class="card-icon artifact">◆</span><strong>${escapeHtml(artifactTemplate?.name || "Nachweis")}</strong>
        <small>${artifact.immutable ? "Finalisiert" : "In Bearbeitung"} · Status ${escapeHtml(artifact.state)}</small>
        <span class="artifact-meta"><span>Revision ${artifact.revision}</span><span>${escapeHtml(artifact.uid.slice(0, 8))}</span></span>
      </button>`;
    }).join("");
    const children = [...state.details.values()].filter(item => item.entity.parent.kind === "OBJECT" && item.entity.parent.uid === detail.entity.uid);
    const childCards = children.map(child => `
      <button class="content-card" data-object-uid="${escapeHtml(child.entity.uid)}">
        <span class="card-icon">□</span><strong>${escapeHtml(objectLabel(child))}</strong><small>${escapeHtml(templateByUid(child.entity.template_version_uid)?.name || "Untereintrag")} · ${escapeHtml(child.entity.state)}</small>
      </button>`).join("");
    $("#workspace").innerHTML = `
      <header class="hero">
        <div class="hero-icon">□</div><span class="eyebrow">${escapeHtml(template?.name || "Eintrag")}</span>
        <h1>${escapeHtml(label)}</h1><p>${escapeHtml(module?.description || "Strukturierter Eintrag im QMTool-Arbeitsbereich.")}</p>
        <div class="hero-meta"><span class="pill state">${escapeHtml(humanize(detail.entity.state))}</span><span class="pill">Revision ${detail.entity.revision}</span>${detail.entity.archived ? '<span class="pill archived">Archiviert</span>' : ""}</div>
      </header>
      <div class="page-actions">
        ${isAllowed(detail, "UPDATE") ? '<button class="button primary" data-action="edit-object">Bearbeiten</button>' : ""}
        ${isAllowed(detail, "CREATE_CHILD") && childTemplates.length ? '<button class="button" data-action="create-child">＋ Untereintrag</button>' : ""}
        ${isAllowed(detail, "CREATE_ARTIFACT") && eligibleArtifactTemplates().length ? '<button class="button" data-action="create-artifact">◆ Nachweis</button>' : ""}
        ${transitionButtons(detail, template)}
        <a class="button ghost" href="/container/objects/${encodeURIComponent(detail.entity.uid)}/export">Export</a>
        ${isAllowed(detail, "ARCHIVE") ? '<button class="button danger" data-action="archive">Archivieren</button>' : ""}
        ${isAllowed(detail, "REACTIVATE") ? '<button class="button secondary" data-action="reactivate">Reaktivieren</button>' : ""}
      </div>
      <section class="section"><div class="section-head"><div><span class="eyebrow">Daten</span><h2>Eigenschaften</h2></div></div>${fieldRows(template, detail.field_values)}</section>
      <section class="section"><div class="section-head"><div><span class="eyebrow">Struktur</span><h2>Untereinträge</h2></div>${isAllowed(detail, "CREATE_CHILD") && childTemplates.length ? '<button class="button" data-action="create-child">＋ Hinzufügen</button>' : ""}</div>
        ${childCards ? `<div class="card-grid">${childCards}</div>` : '<div class="notice">Keine sichtbaren Untereinträge.</div>'}
      </section>
      <section class="section"><div class="section-head"><div><span class="eyebrow">Dokumentation</span><h2>Nachweise & Dateien</h2></div>${isAllowed(detail, "CREATE_ARTIFACT") && eligibleArtifactTemplates().length ? '<button class="button" data-action="create-artifact">＋ Nachweis</button>' : ""}</div>
        ${artifactCards ? `<div class="card-grid">${artifactCards}</div>` : '<div class="notice">Noch keine sichtbaren Nachweise.</div>'}
      </section>
      <section class="section"><div class="section-head"><div><span class="eyebrow">Nachvollziehbarkeit</span><h2>Aktivitätsverlauf</h2></div><button class="button ghost" data-action="show-audit">Verlauf laden</button></div><div id="audit-region"></div></section>`;
  }

  async function selectObject(uid) {
    const detail = await guarded(() => api(`/container/objects/${encodeURIComponent(uid)}`));
    if (!detail) return;
    state.activeObjectUid = uid;
    state.activeDetail = detail;
    state.details.set(uid, detail);
    renderModules();
    renderTree();
    renderObject(detail);
    document.body.classList.remove("sidebar-open");
  }

  async function selectModule(uid) {
    state.activeModuleUid = uid;
    state.activeObjectUid = null;
    state.activeDetail = null;
    renderModules();
    await guarded(rebuildTree);
    renderModuleOverview();
    document.body.classList.remove("sidebar-open");
  }

  async function refreshAll({preserveObject = true} = {}) {
    const priorModule = state.activeModuleUid;
    const priorObject = preserveObject ? state.activeObjectUid : null;
    const data = await guarded(() => Promise.all([
      api("/container/runtime-modules"),
      api("/container/workspace-root"),
    ]));
    if (!data) return;
    [state.modules, {uid: state.workspaceUid}] = data;
    state.activeModuleUid = state.modules.some(item => item.uid === priorModule) ? priorModule : state.modules[0]?.uid || null;
    renderModules();
    if (!state.activeModuleUid) {
      state.tree = [];
      renderTree();
      renderEmpty();
      return;
    }
    await guarded(rebuildTree);
    if (priorObject && state.details.has(priorObject)) await selectObject(priorObject);
    else {
      state.activeObjectUid = null;
      state.activeDetail = null;
      renderModuleOverview();
    }
  }

  function inputForField(field, value) {
    const key = escapeHtml(field.key);
    const required = field.required ? "required" : "";
    const label = `${escapeHtml(humanize(field.key))}${field.required ? ' <span class="required">*</span>' : ""}`;
    const current = valueText(value);
    let control;
    if (field.field_type === "multiline_text") {
      control = `<textarea data-field-key="${key}" ${required}>${escapeHtml(current)}</textarea>`;
    } else if (field.field_type === "boolean") {
      control = `<label class="check-field"><input type="checkbox" data-field-key="${key}" ${value === true ? "checked" : ""}><span>Ja, trifft zu</span></label>`;
    } else if (field.field_type === "single_select") {
      control = `<select data-field-key="${key}" ${required}><option value="">Bitte wählen</option>${field.options.map(option => `<option value="${escapeHtml(option)}" ${current === option ? "selected" : ""}>${escapeHtml(option)}</option>`).join("")}</select>`;
    } else if (field.field_type === "multi_select") {
      const selected = new Set(valueParts(value));
      control = `<div class="multi-options">${field.options.map(option => `<label><input type="checkbox" data-field-key="${key}" value="${escapeHtml(option)}" ${selected.has(option) ? "checked" : ""}><span>${escapeHtml(option)}</span></label>`).join("")}</div>`;
    } else {
      const types = {integer: "number", decimal: "number", date: "date", datetime: "datetime-local"};
      const type = types[field.field_type] || "text";
      const step = field.field_type === "decimal" ? 'step="any"' : "";
      control = `<input type="${type}" ${step} data-field-key="${key}" value="${escapeHtml(current)}" ${required}>`;
    }
    const help = {
      user_reference: "UID eines Benutzers",
      object_reference: "UID eines vorhandenen Objekts",
      artifact_reference: "UID eines vorhandenen Nachweises",
      multi_select: "Mehrere Werte sind möglich",
    }[field.field_type];
    return `<label class="form-field"><span>${label}</span>${control}${help ? `<small>${escapeHtml(help)}</small>` : ""}</label>`;
  }

  function fieldsForm(template, values = {}, {editableOnly = false} = {}) {
    const fields = template.fields.filter(field => !editableOnly || field.editable);
    return fields.length ? `<div class="form-grid">${fields.map(field => inputForField(field, values[field.key])).join("")}</div>` : `<div class="notice">Für diesen Baustein sind keine bearbeitbaren Felder definiert.</div>`;
  }

  function collectFields(template, form, {editableOnly = false} = {}) {
    const result = {};
    const fields = template.fields.filter(field => !editableOnly || field.editable);
    for (const field of fields) {
      const controls = [...form.querySelectorAll("[data-field-key]")].filter(item => item.dataset.fieldKey === field.key);
      let value = null;
      if (field.field_type === "multi_select") value = controls.filter(item => item.checked).map(item => item.value);
      else if (field.field_type === "boolean") value = Boolean(controls[0]?.checked);
      else {
        const raw = controls[0]?.value ?? "";
        if (raw !== "") value = field.field_type === "integer" ? Number.parseInt(raw, 10) : raw;
      }
      if (field.field_type === "multi_select" && value.length === 0) value = null;
      if (field.required && (value == null || value === "")) throw Object.assign(new Error("required"), {code: "container.field.required"});
      result[field.key] = value;
    }
    return result;
  }

  function openEditor({kicker, title, body, submitLabel = "Speichern", onSubmit, afterOpen}) {
    $("#dialog-kicker").textContent = kicker;
    $("#dialog-title").textContent = title;
    $("#dialog-body").innerHTML = body;
    $("#dialog-submit").textContent = submitLabel;
    state.editorSubmit = onSubmit;
    $("#editor-dialog").showModal();
    afterOpen?.();
  }

  function closeEditor() {
    $("#editor-dialog").close();
    state.editorSubmit = null;
  }

  function createWithTemplate({kicker, title, templates, onCreate}) {
    const first = templates[0];
    const renderDynamic = template => {
      $("#dynamic-fields").innerHTML = fieldsForm(template);
    };
    openEditor({
      kicker,
      title,
      submitLabel: "Anlegen",
      body: `<div class="form-grid">
        ${templates.length > 1 ? `<label class="form-field"><span>Baustein</span><select id="template-choice">${templates.map(item => `<option value="${escapeHtml(item.template_version_uid)}">${escapeHtml(item.name)}</option>`).join("")}</select></label>` : `<input id="template-choice" type="hidden" value="${escapeHtml(first.template_version_uid)}">`}
        <div id="dynamic-fields">${fieldsForm(first)}</div>
      </div>`,
      onSubmit: async (_data, form) => {
        const template = templates.find(item => item.template_version_uid === $("#template-choice").value);
        await onCreate(template, collectFields(template, form));
      },
      afterOpen: () => $("#template-choice").addEventListener("change", event => renderDynamic(templates.find(item => item.template_version_uid === event.target.value))),
    });
  }

  function openRootCreator() {
    const module = activeModule();
    const root = module?.templates.find(item => item.is_root && item.create_allowed);
    if (!root) return toast("Für dieses Modul kann kein Haupteintrag angelegt werden.", true);
    createWithTemplate({
      kicker: module.name,
      title: `Neuer ${root.name}`,
      templates: [root],
      onCreate: async (template, values) => {
        const created = await api("/container/objects", {method: "POST", body: JSON.stringify({
          template_version_uid: template.template_version_uid,
          parent_kind: "WORKSPACE_ROOT",
          parent_uid: state.workspaceUid,
          values,
        })});
        closeEditor();
        toast("Haupteintrag wurde angelegt.");
        await refreshAll({preserveObject: false});
        await selectObject(created.uid);
      },
    });
  }

  function openChildCreator() {
    if (!state.activeDetail) return;
    const candidates = eligibleChildTemplates(state.activeDetail).map(item => item.template);
    if (!candidates.length) return toast("Kein zulässiger Unterbaustein verfügbar.", true);
    createWithTemplate({
      kicker: objectLabel(state.activeDetail),
      title: "Untereintrag anlegen",
      templates: candidates,
      onCreate: async (template, values) => {
        const created = await api("/container/objects", {method: "POST", body: JSON.stringify({
          template_version_uid: template.template_version_uid,
          parent_kind: "OBJECT",
          parent_uid: state.activeDetail.entity.uid,
          values,
        })});
        closeEditor();
        toast("Untereintrag wurde angelegt.");
        await refreshAll();
        await selectObject(created.uid);
      },
    });
  }

  function openArtifactCreator() {
    if (!state.activeDetail) return;
    const templates = eligibleArtifactTemplates();
    if (!templates.length) return toast("Kein zulässiger Nachweistyp verfügbar.", true);
    const ownerUid = state.activeDetail.entity.uid;
    createWithTemplate({
      kicker: objectLabel(state.activeDetail),
      title: "Nachweis anlegen",
      templates,
      onCreate: async (template, values) => {
        const created = await api("/container/artifacts", {method: "POST", body: JSON.stringify({
          template_version_uid: template.template_version_uid,
          owner_object_uid: ownerUid,
          values,
        })});
        closeEditor();
        toast("Nachweis wurde angelegt.");
        await refreshAll();
        await selectObject(ownerUid);
        await openArtifact(created.uid);
      },
    });
  }

  function openObjectEditor() {
    const detail = state.activeDetail;
    const template = templateByUid(detail.entity.template_version_uid);
    openEditor({
      kicker: template.name,
      title: "Eigenschaften bearbeiten",
      body: fieldsForm(template, detail.field_values, {editableOnly: true}),
      onSubmit: async (_data, form) => {
        await api(`/container/objects/${encodeURIComponent(detail.entity.uid)}/fields`, {method: "PUT", body: JSON.stringify({
          values: collectFields(template, form, {editableOnly: true}),
          expected_revision: detail.entity.revision,
        })});
        closeEditor();
        toast("Änderungen wurden gespeichert.");
        await refreshAll();
      },
    });
  }

  function openTransition(button) {
    const detail = state.activeDetail;
    const toState = button.dataset.toState;
    const reasonRequired = button.dataset.reasonRequired === "true";
    const signatureRequired = button.dataset.signatureRequired === "true";
    openEditor({
      kicker: `${humanize(detail.entity.state)} → ${humanize(toState)}`,
      title: "Status ändern",
      submitLabel: "Übergang ausführen",
      body: `<div class="form-grid">
        <label class="form-field"><span>Begründung${reasonRequired ? ' <span class="required">*</span>' : ""}</span><textarea name="reason" ${reasonRequired ? "required" : ""} placeholder="Warum wird der Status geändert?"></textarea></label>
        ${signatureRequired ? '<label class="form-field"><span>Signaturbedeutung <span class="required">*</span></span><input name="signature" required placeholder="z. B. fachlich geprüft"></label>' : ""}
      </div>`,
      onSubmit: async data => {
        await api(`/container/objects/${encodeURIComponent(detail.entity.uid)}/transition`, {method: "POST", body: JSON.stringify({
          to_state: toState,
          reason: data.get("reason") || null,
          signature_meaning: data.get("signature") || null,
          expected_revision: detail.entity.revision,
        })});
        closeEditor();
        toast(`Status wurde auf „${humanize(toState)}“ gesetzt.`);
        await refreshAll();
      },
    });
  }

  async function mutateObject(action) {
    const detail = state.activeDetail;
    if (!detail) return;
    const wording = action === "archive" ? "archivieren" : "reaktivieren";
    if (!window.confirm(`Eintrag wirklich ${wording}?`)) return;
    const result = await guarded(() => api(`/container/objects/${encodeURIComponent(detail.entity.uid)}/${action}`, {method: "POST", body: JSON.stringify({expected_revision: detail.entity.revision})}), `Eintrag wurde ${action === "archive" ? "archiviert" : "reaktiviert"}.`);
    if (result) await refreshAll();
  }

  async function showAudit() {
    const region = $("#audit-region");
    region.innerHTML = `<p class="side-hint">Verlauf wird geladen …</p>`;
    const records = await guarded(() => api(`/container/objects/${encodeURIComponent(state.activeDetail.entity.uid)}/audit`));
    if (!records) return;
    region.innerHTML = records.length ? `<ol class="audit-list">${records.map(record => `
      <li><strong>${escapeHtml(humanize(record.event_type))}</strong><small>${escapeHtml(record.occurred_at || "Zeitpunkt nicht verfügbar")} · ${escapeHtml(record.actor_user_id)}</small></li>`).join("")}</ol>` : `<div class="notice">Noch keine sichtbaren Audit-Einträge.</div>`;
  }

  async function search(query) {
    const module = activeModule();
    if (!module || !query.trim()) return renderModuleOverview();
    const templateUids = new Set(module.templates.filter(item => item.kind === "OBJECT").map(item => item.template_version_uid));
    const entities = await guarded(() => api(`/container/objects/search?query=${encodeURIComponent(query.trim())}&limit=100`));
    if (!entities) return;
    const matches = entities.filter(entity => templateUids.has(entity.template_version_uid));
    const details = await guarded(() => Promise.all(matches.map(entity => api(`/container/objects/${encodeURIComponent(entity.uid)}`))));
    if (!details) return;
    setBreadcrumbs(module.name, `Suche: ${query.trim()}`);
    $("#workspace").innerHTML = `<header class="hero"><span class="eyebrow">Suche</span><h1>${details.length} Treffer</h1><p>Ergebnisse für „${escapeHtml(query.trim())}“ im Modul ${escapeHtml(module.name)}.</p></header>
      <div class="search-results">${details.map(detail => `<button class="search-result" data-object-uid="${escapeHtml(detail.entity.uid)}"><span class="card-icon">□</span><span><strong>${escapeHtml(objectLabel(detail))}</strong><small>${escapeHtml(templateByUid(detail.entity.template_version_uid)?.name || "Eintrag")} · ${escapeHtml(detail.entity.state)}</small></span><span>→</span></button>`).join("") || '<div class="notice">Keine sichtbaren Treffer gefunden.</div>'}</div>`;
  }

  function artifactTitle(detail, template) {
    for (const key of ["title", "name", "bezeichnung", "number", "nummer"]) {
      if (valueText(detail.field_values[key])) return valueText(detail.field_values[key]);
    }
    return template?.name || "Nachweis";
  }

  async function openArtifact(uid) {
    const detail = await guarded(() => api(`/container/artifacts/${encodeURIComponent(uid)}`));
    if (!detail) return;
    state.artifactDetail = detail;
    const template = templateByUid(detail.entity.template_version_uid);
    const editable = isAllowed(detail, "UPDATE") && !detail.entity.immutable;
    $("#artifact-panel").innerHTML = `
      <header class="dialog-head"><div><span class="eyebrow">${escapeHtml(template?.name || "Nachweis")}</span><h2>${escapeHtml(artifactTitle(detail, template))}</h2></div><button class="icon-button close" data-action="close-artifact" aria-label="Schließen">×</button></header>
      <div class="artifact-body">
        <div class="hero-meta"><span class="pill state">${escapeHtml(humanize(detail.entity.state))}</span><span class="pill">Revision ${detail.entity.revision}</span><span class="pill">${detail.entity.immutable ? "Finalisiert" : "In Bearbeitung"}</span></div>
        <section class="section"><div class="section-head"><div><span class="eyebrow">Metadaten</span><h2>Eigenschaften</h2></div></div>
          ${editable ? `<form id="artifact-fields-form">${fieldsForm(template, detail.field_values, {editableOnly: true})}<div class="page-actions"><button class="button primary" type="submit">Änderungen speichern</button></div></form>` : fieldRows(template, detail.field_values)}
        </section>
        <section class="section"><div class="section-head"><div><span class="eyebrow">Anhänge</span><h2>Dateien</h2></div></div>
          <div class="file-list">${detail.files.map(file => `<div class="file-row"><span class="card-icon artifact">↧</span><span><strong>${escapeHtml(file.original_name)}</strong><small>${escapeHtml(file.media_type)} · ${Math.max(1, Math.round(file.size_bytes / 1024))} KB</small></span><a class="button ghost" href="/container/artifacts/${encodeURIComponent(detail.entity.uid)}/files/${encodeURIComponent(file.uid)}/download">Laden</a></div>`).join("") || '<div class="notice">Noch keine Datei angehängt.</div>'}</div>
          ${editable ? '<form id="artifact-upload-form" class="upload-box"><strong>Datei hinzufügen</strong><input id="artifact-file" type="file" required><button class="button" type="submit">Datei hochladen</button></form>' : ""}
        </section>
        <div class="page-actions">
          ${isAllowed(detail, "FINALIZE") && !detail.entity.immutable ? '<button class="button primary" data-action="finalize-artifact">Finalisieren</button>' : ""}
          ${isAllowed(detail, "SIGN") && detail.entity.immutable ? '<button class="button" data-action="sign-artifact">Signieren</button>' : ""}
          ${isAllowed(detail, "CORRECT") && detail.entity.immutable ? '<button class="button secondary" data-action="correct-artifact">Korrektur anlegen</button>' : ""}
        </div>
      </div>`;
    if (!$("#artifact-dialog").open) $("#artifact-dialog").showModal();
    $("#artifact-fields-form")?.addEventListener("submit", saveArtifactFields);
    $("#artifact-upload-form")?.addEventListener("submit", uploadArtifactFile);
  }

  async function saveArtifactFields(event) {
    event.preventDefault();
    const detail = state.artifactDetail;
    const template = templateByUid(detail.entity.template_version_uid);
    const result = await guarded(() => api(`/container/artifacts/${encodeURIComponent(detail.entity.uid)}/fields`, {method: "PUT", body: JSON.stringify({
      values: collectFields(template, event.currentTarget, {editableOnly: true}),
      expected_revision: detail.entity.revision,
    })}), "Nachweis wurde gespeichert.");
    if (result) {
      await openArtifact(detail.entity.uid);
      await refreshAll();
    }
  }

  function fileAsBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(file);
    });
  }

  async function uploadArtifactFile(event) {
    event.preventDefault();
    const detail = state.artifactDetail;
    const file = $("#artifact-file").files[0];
    if (!file) return;
    if (file.size > MAX_UPLOAD_BYTES) return toast("Die Datei darf höchstens 10 MB groß sein.", true);
    const result = await guarded(async () => api(`/container/artifacts/${encodeURIComponent(detail.entity.uid)}/files`, {method: "POST", body: JSON.stringify({
      original_name: file.name,
      media_type: file.type || "application/octet-stream",
      content_base64: await fileAsBase64(file),
      expected_revision: detail.entity.revision,
    })}), "Datei wurde hochgeladen.");
    if (result) {
      await openArtifact(detail.entity.uid);
      await refreshAll();
    }
  }

  async function finalizeArtifact() {
    const detail = state.artifactDetail;
    if (!window.confirm("Nachweis finalisieren? Danach sind Felder und Dateien unveränderlich.")) return;
    const result = await guarded(() => api(`/container/artifacts/${encodeURIComponent(detail.entity.uid)}/finalize`, {method: "POST", body: JSON.stringify({expected_revision: detail.entity.revision})}), "Nachweis wurde finalisiert.");
    if (result) {
      await openArtifact(detail.entity.uid);
      await refreshAll();
    }
  }

  async function signArtifact() {
    const detail = state.artifactDetail;
    const meaning = window.prompt("Bedeutung der Signatur", "fachlich geprüft");
    if (!meaning?.trim()) return;
    const result = await guarded(() => api(`/container/artifacts/${encodeURIComponent(detail.entity.uid)}/sign`, {method: "POST", body: JSON.stringify({meaning: meaning.trim()})}), "Nachweis wurde signiert.");
    if (result) await openArtifact(detail.entity.uid);
  }

  async function correctArtifact() {
    const detail = state.artifactDetail;
    const corrected = await guarded(() => api(`/container/artifacts/${encodeURIComponent(detail.entity.uid)}/correct`, {method: "POST"}), "Korrektur wurde als neuer Nachweis angelegt.");
    if (corrected) {
      await refreshAll();
      await openArtifact(corrected.uid);
    }
  }

  $("#editor-form").addEventListener("submit", async event => {
    event.preventDefault();
    if (!state.editorSubmit) return;
    const button = $("#dialog-submit");
    button.disabled = true;
    try {
      await state.editorSubmit(new FormData(event.currentTarget), event.currentTarget);
    } catch (error) {
      toast(messageFor(error), true);
    } finally {
      button.disabled = false;
    }
  });

  $("#search-form").addEventListener("submit", event => {
    event.preventDefault();
    search($("#search-input").value);
  });

  document.addEventListener("click", async event => {
    const moduleButton = event.target.closest("[data-module-uid]");
    if (moduleButton) return selectModule(moduleButton.dataset.moduleUid);
    const objectButton = event.target.closest("[data-object-uid]");
    if (objectButton) return selectObject(objectButton.dataset.objectUid);
    const artifactButton = event.target.closest("[data-artifact-uid]");
    if (artifactButton) return openArtifact(artifactButton.dataset.artifactUid);
    const toggle = event.target.closest("[data-toggle-uid]");
    if (toggle) {
      const uid = toggle.dataset.toggleUid;
      state.collapsed.has(uid) ? state.collapsed.delete(uid) : state.collapsed.add(uid);
      return renderTree();
    }
    const action = event.target.closest("[data-action]")?.dataset.action;
    if (!action) return;
    if (action === "refresh") return refreshAll();
    if (action === "toggle-sidebar") return document.body.classList.toggle("sidebar-open");
    if (action === "create-root") return openRootCreator();
    if (action === "create-child") return openChildCreator();
    if (action === "create-artifact") return openArtifactCreator();
    if (action === "edit-object") return openObjectEditor();
    if (action === "transition") return openTransition(event.target.closest("[data-action]"));
    if (action === "archive" || action === "reactivate") return mutateObject(action);
    if (action === "show-audit") return showAudit();
    if (action === "close-dialog") return closeEditor();
    if (action === "close-artifact") return $("#artifact-dialog").close();
    if (action === "finalize-artifact") return finalizeArtifact();
    if (action === "sign-artifact") return signArtifact();
    if (action === "correct-artifact") return correctArtifact();
  });

  $("#editor-dialog").addEventListener("click", event => {
    if (event.target === $("#editor-dialog")) closeEditor();
  });
  $("#artifact-dialog").addEventListener("click", event => {
    if (event.target === $("#artifact-dialog")) $("#artifact-dialog").close();
  });

  refreshAll({preserveObject: false});
})();
