/* Document and model content is rendered as text, never interpreted as HTML. */
const $ = (id) => document.getElementById(id);
const names = {
  rate_confirmation: "Rate confirmation",
  invoice: "Carrier invoice",
  proof_of_delivery: "Proof of delivery",
};
const statuses = {
  needs_review: ["Needs attention", "attention"],
  ready_for_review: ["Ready to review", "ready"],
  approved: ["Approved", "approved"],
};
const fieldNames = {
  shipment_reference: "Shipment reference",
  carrier: "Carrier",
  pickup_location: "Pickup location",
  delivery_location: "Delivery location",
  pickup_date: "Pickup date",
  delivery_date: "Delivery date",
  invoice_number: "Invoice number",
  amount: "Amount",
  currency: "Currency",
};
let current = null;
let reviews = [];
let filter = "all";
let query = "";
let busy = false;
let loaded = false;
let provider = null;
let pipelineRevision = null;
let returnToReview = null;
const noteDrafts = new Map();
let selectedDocumentId = null;
let selectedFieldKey = null;
const providerNames = {
  demo: "Demo mode",
  gemini: "Gemini API",
  kimi: "Kimi API",
};
let confirmationDocument = null;
let confirmationReturnFocus = null;
const confirmableFields = ["currency", "pickup_date", "delivery_date"];
function effectiveFields(doc) {
  return { ...doc.fields, ...(doc.confirmations || {}) };
}
function scopeBlocked(doc, review = current) {
  return review?.issues.some(
    (issue) =>
      issue.code === "unsupported_document_scope" &&
      issue.document_ids.includes(doc.id),
  );
}
function providerName(value) {
  return providerNames[value] || "AI provider";
}

function node(tag, text, cls) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (cls) element.className = cls;
  return element;
}
function badge(status) {
  const [label, cls] = statuses[status];
  return node("span", label, `badge ${cls}`);
}
function message(text, error = false) {
  if ($("confirmation-dialog").open) {
    $("confirmation-feedback").textContent = error ? "" : text;
    $("confirmation-error").textContent = error ? text : "";
    if (error) $("confirmation-error").focus();
    return;
  }
  const modal = $("upload-dialog").open;
  const status = $(modal ? "dialog-feedback" : "feedback");
  const alert = $(modal ? "dialog-error" : "error-feedback");
  status.textContent = error ? "" : text;
  alert.textContent = error ? text : "";
  if (error) alert.focus();
}
async function api(url, options = {}) {
  let response;
  try {
    response = await fetch(url, options);
  } catch {
    throw new Error(
      "Cannot reach FreightLens. Check that the local server is running, then retry.",
    );
  }
  let result;
  try {
    result = await response.json();
  } catch {
    throw new Error(
      "The server returned an unreadable response. Retry the request.",
    );
  }
  if (!response.ok)
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Check the required fields and try again.",
    );
  return result;
}
function syncCommands() {
  document.querySelectorAll("[data-command]").forEach((button) => {
    let blocked =
      button.id === "approve" &&
      (!current ||
        !usesCurrentPolicy(current) ||
        current.issues.length > 0 ||
        current.status === "approved");
    if (button.id === "confirm-field") {
      const doc = current?.documents.find(
        (doc) => doc.id === selectedDocumentId,
      );
      blocked =
        !current ||
        !usesCurrentPolicy(current) ||
        current.status === "approved" ||
        !doc ||
        scopeBlocked(doc);
      button.disabled = Boolean(blocked || busy);
    }
    button.setAttribute("aria-disabled", String(busy || blocked));
    // Workflow-blocked approval is disabled; pending actions retain keyboard focus.
    if (button.id === "approve") button.disabled = Boolean(blocked);
  });
  $("close-upload").disabled = busy;
  $("close-confirmation").disabled = busy;
  document.querySelectorAll('input[type="file"]').forEach((input) => {
    input.disabled = busy;
  });
  document
    .querySelectorAll("[data-open-upload], [data-open-guide]")
    .forEach((button) => {
      button.setAttribute("aria-disabled", String(busy));
    });
}
async function task(work, label = "", region = null) {
  if (busy) return;
  busy = true;
  syncCommands();
  $("request-progress").hidden = !label;
  $("progress-label").textContent = label;
  $("dialog-progress").hidden = !label || !$("upload-dialog").open;
  $("dialog-progress-label").textContent = label;
  if (region) region.setAttribute("aria-busy", "true");
  try {
    await work();
  } catch (error) {
    message(error.message, true);
  } finally {
    busy = false;
    $("request-progress").hidden = true;
    $("dialog-progress").hidden = true;
    if (region) region.setAttribute("aria-busy", "false");
    syncCommands();
  }
}
function reference(review) {
  return (
    review.documents.find(
      (doc) => !scopeBlocked(doc, review) && doc.fields.shipment_reference,
    )?.fields.shipment_reference.value || "Unconfirmed shipment"
  );
}
function carrier(review) {
  return (
    review.documents.find(
      (doc) => !scopeBlocked(doc, review) && doc.fields.carrier,
    )?.fields.carrier.value || "Carrier unavailable"
  );
}
function focusReview() {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  $("detail-title").focus({ preventScroll: true });
  window.scrollTo({
    behavior: reduced ? "instant" : "smooth",
    top: 0,
  });
}
function fieldValue(review, key, kind) {
  const doc = review.documents.find(
    (doc) =>
      !scopeBlocked(doc, review) &&
      (!kind || doc.kind === kind) &&
      effectiveFields(doc)[key],
  );
  return doc ? effectiveFields(doc)[key].value : undefined;
}
function route(review) {
  const origin = fieldValue(review, "pickup_location");
  const destination = fieldValue(review, "delivery_location");
  return origin && destination
    ? `${origin} → ${destination}`
    : "Route not confirmed";
}
function closeUpload() {
  $("upload-dialog").close();
}
function closeReview() {
  if (busy) return;
  if (current) noteDrafts.set(current.id, $("review-note").value);
  current = null;
  $("detail").hidden = true;
  $("workspace").classList.remove("has-selection");
  $("review-note").value = "";
  renderQueue();
  const button = Array.from(document.querySelectorAll("[data-review]")).find(
    (item) => item.dataset.review === returnToReview,
  );
  (button || $("queue-search")).focus();
}
function updateCounts() {
  $("nav-count").textContent = reviews.length;
  $("metric-total").textContent = reviews.length;
  $("metric-attention").textContent = reviews.filter(
    (r) => r.status === "needs_review",
  ).length;
  $("metric-ready").textContent = reviews.filter(
    (r) => r.status === "ready_for_review",
  ).length;
  $("metric-approved").textContent = reviews.filter(
    (r) => r.status === "approved",
  ).length;
}
function renderQueue() {
  updateCounts();
  document.querySelectorAll("[data-filter]").forEach((button) => {
    const selected = button.dataset.filter === filter;
    button.classList.toggle("selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  const visible = reviews.filter(
    (review) =>
      (filter === "all" || review.status === filter) &&
      `${reference(review)} ${carrier(review)}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  $("queue-table").hidden = !loaded || visible.length === 0;
  $("queue-empty").hidden = !loaded || visible.length > 0;
  $("clear-filters").hidden = filter === "all" && !query;
  const filtered = filter !== "all" || query.length > 0;
  $("empty-create").hidden = filtered;
  $("queue-subtitle").textContent =
    filter === "all" ? "All shipment packets" : statuses[filter][0];
  $("empty-title").textContent = filtered
    ? "No matching reviews"
    : "Your first review starts here";
  $("empty-description").textContent = filtered
    ? "Try another reference or clear the filters to see every shipment."
    : "Add shipment documents or choose an example to see the checks in action.";
  $("queue-count").textContent = loaded
    ? `${visible.length} of ${reviews.length} ${reviews.length === 1 ? "review" : "reviews"}`
    : "Connecting to local service";
  $("queue-body").replaceChildren();
  visible.forEach((review) => {
    const row = node("tr");
    row.classList.toggle("selected", current?.id === review.id);
    const shipment = node("td", undefined, "shipment-cell");
    shipment.append(
      node("strong", reference(review)),
      node(
        "small",
        `${carrier(review)} · ${review.documents.length}/3 documents`,
      ),
    );
    const routeCell = node("td", route(review), "route-cell");
    const status = node("td", undefined, "status-cell");
    status.append(badge(review.status));
    const findings = node(
      "td",
      !usesCurrentPolicy(review)
        ? "Recheck required"
        : review.issues.length
          ? `${review.issues.length} flagged`
          : "All checks passed",
      !usesCurrentPolicy(review) || review.issues.length
        ? "finding-count attention-text"
        : "finding-count",
    );
    const added = node(
      "td",
      new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(
        new Date(review.created_at),
      ),
      "date-cell",
    );
    const action = node("td", undefined, "action-cell");
    const button = node("button", "Review", "queue-open");
    button.type = "button";
    button.dataset.command = "";
    button.dataset.review = review.id;
    button.setAttribute("aria-label", `Review shipment ${reference(review)}`);
    button.setAttribute("aria-expanded", String(current?.id === review.id));
    button.setAttribute("aria-controls", "detail");
    button.addEventListener("click", () =>
      task(
        async () => {
          returnToReview = review.id;
          show(await api(`/api/v1/reviews/${review.id}`));
          renderQueue();
          focusReview();
        },
        "Opening shipment review…",
        $("detail"),
      ),
    );
    action.append(button);
    row.append(shipment, routeCell, status, findings, added, action);
    $("queue-body").append(row);
  });
  syncCommands();
}
function saveLocal(review) {
  const index = reviews.findIndex((item) => item.id === review.id);
  if (index === -1) reviews.unshift(review);
  else reviews[index] = review;
  loaded = true;
  $("queue-loading").hidden = true;
  $("queue-failure").hidden = true;
  renderQueue();
}
function showEvidence(doc, key, announce = true) {
  selectedFieldKey = key;
  const field = effectiveFields(doc)[key];
  $("evidence-title").textContent = `${doc.filename} / Page ${field.page}`;
  $("evidence-quote").textContent = field.quote;
  $("evidence-page").textContent =
    doc.pages.find((page) => page.number === field.page)?.text ||
    "Page unavailable";
  document.querySelectorAll("#fields-body tr").forEach((row) => {
    const selected = row.dataset.field === key;
    row.classList.toggle("selected", selected);
    row.querySelector("button")?.setAttribute("aria-pressed", String(selected));
  });
  if (announce)
    $("evidence-update").textContent =
      `${fieldNames[key]} evidence, ${doc.filename}, page ${field.page}.`;
}
function showDocument(doc) {
  if (selectedDocumentId !== doc.id) selectedFieldKey = null;
  selectedDocumentId = doc.id;
  const fields = scopeBlocked(doc) ? {} : effectiveFields(doc);
  $("field-count").textContent = scopeBlocked(doc)
    ? "Unsupported input"
    : `${Object.keys(fields).length} fields`;
  document.querySelectorAll("#document-tabs button").forEach((button) => {
    const selected = button.dataset.id === doc.id;
    button.classList.toggle("selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  $("fields-body").replaceChildren();
  $("evidence-update").textContent = "";
  Object.entries(fields).forEach(([key, field]) => {
    const row = node("tr");
    row.dataset.field = key;
    const cell = node("td");
    const button = node("button", field.value);
    button.type = "button";
    button.setAttribute(
      "aria-label",
      `Evidence for ${fieldNames[key]}: ${field.value}`,
    );
    button.setAttribute("aria-pressed", "false");
    button.addEventListener("click", () => showEvidence(doc, key));
    cell.append(button);
    if (doc.confirmations?.[key])
      cell.append(
        node(
          "small",
          `Employee confirmed · AI: ${doc.fields[key]?.value || "not extracted"}`,
          "confirmation-mark",
        ),
      );
    row.append(node("td", fieldNames[key]), cell, node("td", field.page));
    $("fields-body").append(row);
  });
  const key =
    selectedFieldKey && fields[selectedFieldKey]
      ? selectedFieldKey
      : fields.amount
        ? "amount"
        : Object.keys(fields)[0];
  if (key) showEvidence(doc, key, false);
  else {
    const row = node("tr");
    const cell = node(
      "td",
      scopeBlocked(doc)
        ? "Upload a standalone invoice. This guide or bundle cannot be confirmed as one transaction."
        : "No supported fields. Check the source document manually.",
      "missing-fields",
    );
    cell.colSpan = 3;
    row.append(cell);
    $("fields-body").append(row);
    $("evidence-title").textContent = doc.filename;
    $("evidence-quote").textContent = "No supported extraction available.";
    $("evidence-page").textContent = doc.pages
      .map((page) => page.text)
      .join("\n\n");
  }
  syncCommands();
}
function usesCurrentPolicy(review) {
  return Boolean(
    pipelineRevision &&
    review.processing?.pipeline_revision === pipelineRevision,
  );
}
function updateApproval() {
  $("approval-help").textContent = !usesCurrentPolicy(current)
    ? "This review used an earlier policy. Recheck its saved pages before making a confirmation or approval. Original extraction and history are preserved."
    : current.status === "approved"
      ? "Approved by an employee. The reviewed record is ready to download."
      : current.issues.length
        ? "Approval is blocked. Confirm currency or dates with evidence, or supply missing/corrected documents in a new review. A note alone does not clear findings."
        : "The configured checks passed. Verify the sources and record your decision before approving.";
  $("export").hidden =
    current.status !== "approved" || !usesCurrentPolicy(current);
  $("export").href = `/api/v1/reviews/${current.id}/export`;
  $("recheck").hidden = usesCurrentPolicy(current);
  syncCommands();
}
function show(review) {
  if (current?.id !== review.id) {
    if (current) noteDrafts.set(current.id, $("review-note").value);
    $("review-note").value = noteDrafts.get(review.id) || "";
    selectedDocumentId = null;
    selectedFieldKey = null;
    $("detail").scrollTop = 0;
  }
  current = review;
  returnToReview = review.id;
  $("detail").hidden = false;
  $("workspace").classList.add("has-selection");
  $("detail-title").textContent = reference(review);
  $("detail-meta").textContent =
    `${carrier(review)} · ${review.documents.length}/3 documents · ${review.provider === "demo" ? "Demo extraction" : `${providerName(review.provider)} extraction`} · ${usesCurrentPolicy(review) ? "Current checks" : "Earlier policy: recheck required"}`;
  const status = badge(review.status);
  $("detail-status").textContent = status.textContent;
  $("detail-status").className = status.className;
  if (!usesCurrentPolicy(review)) {
    $("detail-status").textContent = "Recheck required";
    $("detail-status").className = "badge attention";
  }
  $("shipment-overview").replaceChildren();
  const amount = fieldValue(review, "amount", "invoice");
  const currency = fieldValue(review, "currency", "invoice");
  [
    ["Route", route(review)],
    [
      "Invoice total",
      amount && currency ? `${currency} ${amount}` : "Not available",
    ],
    ["Documents", `${review.documents.length} of 3 supplied`],
  ].forEach(([label, value]) => {
    const item = node("dl", undefined, "overview-item");
    item.append(node("dt", label), node("dd", value));
    $("shipment-overview").append(item);
  });
  $("issue-count").textContent = review.issues.length
    ? `(${review.issues.length})`
    : "";
  $("issues").replaceChildren();
  if (!review.issues.length)
    $("issues").append(
      node(
        "div",
        usesCurrentPolicy(review)
          ? review.status === "approved"
            ? "Approved by an employee. The reviewed record is ready to download."
            : "All configured checks passed. Ready for your review."
          : "Earlier checks found no issues. Recheck this packet under the current policy before approval or export.",
        usesCurrentPolicy(review) ? "finding pass" : "finding",
      ),
    );
  review.issues.forEach((issue) => {
    const finding = node("div", undefined, "finding");
    finding.append(
      node(
        "strong",
        issue.code === "invalid_date"
          ? "Date clarification"
          : issue.code === "unsupported_document_scope"
            ? "Standalone invoice required"
            : issue.code.replaceAll("_", " "),
      ),
      node("p", issue.message),
    );
    if (
      confirmableFields.includes(issue.field) &&
      issue.document_ids.length === 1 &&
      usesCurrentPolicy(review) &&
      review.status !== "approved"
    ) {
      const doc = review.documents.find(
        (doc) => doc.id === issue.document_ids[0],
      );
      if (doc && !scopeBlocked(doc)) {
        const confirm = node(
          "button",
          "Clarify this field",
          "button secondary",
        );
        confirm.type = "button";
        confirm.dataset.command = "";
        confirm.addEventListener("click", () =>
          openConfirmation(doc, issue.field, confirm),
        );
        finding.append(confirm);
      }
    }
    $("issues").append(finding);
  });
  $("document-tabs").replaceChildren();
  review.documents.forEach((doc) => {
    const button = node("button", names[doc.kind]);
    button.type = "button";
    button.dataset.id = doc.id;
    button.addEventListener("click", () => showDocument(doc));
    $("document-tabs").append(button);
  });
  if (review.documents.length)
    showDocument(
      review.documents.find((doc) => doc.id === selectedDocumentId) ||
        review.documents.find((doc) => doc.kind === "invoice") ||
        review.documents[0],
    );
  $("draft").value = review.draft_email;
  $("audit").replaceChildren();
  $("audit-count").textContent = `(${review.audit.length})`;
  review.audit.forEach((event) => {
    const item = node(
      "li",
      `${event.actor} · ${event.action.replaceAll("_", " ")}`,
    );
    item.append(
      node("small", `${new Date(event.at).toLocaleString()} — ${event.note}`),
    );
    $("audit").append(item);
  });
  updateApproval();
}
async function initialize() {
  $("reviews").setAttribute("aria-busy", "true");
  $("queue-loading").hidden = false;
  $("queue-failure").hidden = true;
  $("queue-empty").hidden = true;
  try {
    const health = await api("/api/v1/health");
    provider = health.provider;
    pipelineRevision = health.pipeline_revision;
    $("mode").textContent = providerName(provider);
    $("mode-notice").textContent =
      provider === "demo"
        ? "Demo mode uses a sample parser. No AI calls are made."
        : provider === "gemini"
          ? "Document text is sent to Google’s Gemini API. Use public samples for this evaluation."
          : "Document text is sent to NVIDIA’s Kimi API. Use fictional documents for this demo.";
    $("sample-bar").hidden = provider !== "demo";
    reviews = await api("/api/v1/reviews");
    loaded = true;
    $("reviews").setAttribute("aria-busy", "false");
    $("queue-loading").hidden = true;
    renderQueue();
  } catch (error) {
    $("mode").textContent = provider
      ? providerName(provider)
      : "Service unavailable";
    if (!provider)
      $("mode-notice").textContent =
        "Start the local server, then retry the connection.";
    $("queue-loading").hidden = true;
    $("queue-failure").hidden = false;
    $("queue-count").textContent = "Connection interrupted";
    $("reviews").setAttribute("aria-busy", "false");
    message(error.message, true);
  }
}
document.querySelectorAll("[data-demo]").forEach((button) =>
  button.addEventListener("click", () =>
    task(
      async () => {
        message("Checking the example documents…");
        const review = await api(`/api/v1/demo/${button.dataset.demo}`, {
          method: "POST",
        });
        closeUpload();
        show(review);
        saveLocal(review);
        message(
          "Example reviewed. Inspect the findings and their source evidence.",
        );
        focusReview();
      },
      "Checking example documents…",
      $("upload-form"),
    ),
  ),
);
document.querySelectorAll('input[type="file"]').forEach((input) =>
  input.addEventListener("change", () => {
    input
      .closest(".file-card")
      .classList.toggle("selected-file", input.files.length > 0);
    input.closest(".file-card").querySelector(".file-name").textContent =
      input.files[0]?.name || "Choose PDF or text file";
  }),
);
$("upload-form").addEventListener("submit", (event) => {
  event.preventDefault();
  task(
    async () => {
      const form = new FormData();
      const kinds = [];
      for (const input of document.querySelectorAll('input[type="file"]')) {
        if (input.files.length) {
          const file = input.files[0];
          if (file.size > 5 * 1024 * 1024)
            throw new Error(
              `${names[input.name]} exceeds 5 MB. Choose a smaller file.`,
            );
          form.append("files", file);
          kinds.push(input.name);
        }
      }
      if (!kinds.length)
        throw new Error(
          "Choose at least one document, or try an example packet.",
        );
      form.append("kinds", kinds.join(","));
      message(
        provider !== "demo"
          ? `Extracting documents with ${providerName(provider)}. This may take a few minutes.`
          : "Reading documents and checking the shipment…",
      );
      const review = await api("/api/v1/reviews", {
        method: "POST",
        body: form,
      });
      closeUpload();
      $("upload-form").reset();
      document.querySelectorAll(".file-card").forEach((card) => {
        card.classList.remove("selected-file");
        card.querySelector(".file-name").textContent =
          "Choose PDF or text file";
      });
      show(review);
      saveLocal(review);
      message(
        "Document review complete. Inspect the findings before making a decision.",
      );
      focusReview();
    },
    "Reading and checking documents…",
    $("upload-form"),
  );
});
function reviewBody() {
  return JSON.stringify({
    reviewer: $("reviewer").value.trim(),
    note: $("review-note").value.trim(),
  });
}
$("review-form").addEventListener("submit", (event) => {
  event.preventDefault();
  task(
    async () => {
      const submittedNote = $("review-note").value;
      const review = await api(`/api/v1/reviews/${current.id}/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: reviewBody(),
      });
      show(review);
      saveLocal(review);
      if ($("review-note").value === submittedNote) {
        $("review-note").value = "";
        noteDrafts.delete(review.id);
      }
      message("Review note saved to this shipment’s history.");
    },
    "Saving review note…",
    $("detail"),
  );
});
function refreshConfirmationSource() {
  const page = confirmationDocument?.pages.find(
    (page) => page.number === Number($("confirmation-page").value),
  );
  $("confirmation-source-text").textContent = page?.text || "Page unavailable";
}
function prepareConfirmationField() {
  const key = $("confirmation-field").value;
  const fields = effectiveFields(confirmationDocument);
  const source = fields[key] || (key === "currency" ? fields.amount : null);
  $("confirmation-value").type = key === "currency" ? "text" : "date";
  $("confirmation-value").placeholder =
    key === "currency" ? "USD, CAD, EUR, MAD or GBP" : "YYYY-MM-DD";
  $("confirmation-value-label").textContent =
    key === "currency" ? "Confirmed currency code" : "Confirmed full date";
  const existing = fields[key]?.value || "";
  $("confirmation-value").value =
    key === "currency" || /^\d{4}-\d{2}-\d{2}$/.test(existing) ? existing : "";
  $("confirmation-original").textContent =
    `Original AI result: ${confirmationDocument.fields[key]?.value || "not extracted"}. It remains unchanged in the record.`;
  $("confirmation-page").value = String(
    source?.page || confirmationDocument.pages[0].number,
  );
  $("confirmation-quote").value = source?.quote || "";
  refreshConfirmationSource();
}
function openConfirmation(doc, key = "currency", trigger = null) {
  if (
    busy ||
    !current ||
    current.status === "approved" ||
    !usesCurrentPolicy(current) ||
    scopeBlocked(doc)
  )
    return;
  confirmationDocument = doc;
  confirmationReturnFocus = trigger || $("confirm-field");
  $("confirmation-form").reset();
  $("confirmation-feedback").textContent = "";
  $("confirmation-error").textContent = "";
  $("confirmation-document").textContent = doc.filename;
  $("confirmation-field").value = confirmableFields.includes(key)
    ? key
    : "currency";
  $("confirmation-page").replaceChildren();
  doc.pages.forEach((page) => {
    const option = node("option", `Page ${page.number}`);
    option.value = page.number;
    $("confirmation-page").append(option);
  });
  $("confirmation-reviewer").value = $("reviewer").value;
  prepareConfirmationField();
  $("confirmation-dialog").showModal();
  $("confirmation-value").focus();
}
$("confirm-field").addEventListener("click", () => {
  const doc = current?.documents.find((doc) => doc.id === selectedDocumentId);
  if (doc)
    openConfirmation(
      doc,
      confirmableFields.includes(selectedFieldKey)
        ? selectedFieldKey
        : "currency",
    );
});
$("confirmation-field").addEventListener("change", prepareConfirmationField);
$("confirmation-page").addEventListener("change", () => {
  $("confirmation-quote").value = "";
  refreshConfirmationSource();
});
$("close-confirmation").addEventListener("click", () => {
  if (!busy) $("confirmation-dialog").close();
});
$("confirmation-dialog").addEventListener("cancel", (event) => {
  if (busy) event.preventDefault();
});
$("confirmation-dialog").addEventListener("close", () => {
  if (confirmationReturnFocus?.isConnected) confirmationReturnFocus.focus();
  else $("confirm-field").focus();
});
$("confirmation-form").addEventListener("submit", (event) => {
  event.preventDefault();
  task(
    async () => {
      message("Saving your confirmation and rerunning checks…");
      const reviewer = $("confirmation-reviewer").value.trim();
      const review = await api(`/api/v1/reviews/${current.id}/confirmations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          document_id: confirmationDocument.id,
          field: $("confirmation-field").value,
          value: $("confirmation-value").value.trim(),
          page: Number($("confirmation-page").value),
          quote: $("confirmation-quote").value.trim(),
          reviewer,
          note: $("confirmation-note").value.trim(),
          expected_revision: current.revision || 0,
        }),
      });
      $("reviewer").value = reviewer;
      $("confirmation-dialog").close();
      show(review);
      saveLocal(review);
      message(
        "Confirmation saved. Original AI evidence retained; all checks rerun.",
      );
      focusReview();
    },
    "Saving field confirmation…",
    $("confirmation-form"),
  );
});
$("recheck").addEventListener("click", () =>
  task(
    async () => {
      const review = await api(`/api/v1/reviews/${current.id}/recheck`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: current.revision || 0 }),
      });
      show(review);
      saveLocal(review);
      message("Saved pages rechecked. No new AI request was made.");
      focusReview();
    },
    "Rechecking saved source pages…",
    $("detail"),
  ),
);
$("approve").addEventListener("click", () => {
  if (busy || !$("review-form").reportValidity()) return;
  task(
    async () => {
      const submittedNote = $("review-note").value;
      const review = await api(`/api/v1/reviews/${current.id}/approval`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: reviewBody(),
      });
      show(review);
      saveLocal(review);
      if ($("review-note").value === submittedNote) {
        $("review-note").value = "";
        noteDrafts.delete(review.id);
      }
      message("Record approved. The reviewed JSON is ready to download.");
      $("export").focus();
    },
    "Recording employee approval…",
    $("detail"),
  );
});
$("copy-draft").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("draft").value);
    message("Draft copied. Review it before sending.");
  } catch {
    message(
      "Copy is unavailable. The draft is selected; use your browser’s copy command.",
      true,
    );
    $("draft").focus();
    $("draft").select();
  }
});
document.querySelectorAll("[data-filter]").forEach((button) =>
  button.addEventListener("click", () => {
    filter = button.dataset.filter;
    renderQueue();
  }),
);
$("queue-search").addEventListener("input", (event) => {
  query = event.target.value.trim();
  renderQueue();
});
$("clear-filters").addEventListener("click", () => {
  filter = "all";
  query = "";
  $("queue-search").value = "";
  renderQueue();
  $("queue-search").focus();
});
$("close-detail").addEventListener("click", closeReview);
$("review-note").addEventListener("input", () => {
  if (current) noteDrafts.set(current.id, $("review-note").value);
});
document.querySelectorAll("[data-open-upload]").forEach((button) => {
  button.addEventListener("click", () => {
    if (busy) return;
    $("dialog-feedback").textContent = "";
    $("dialog-error").textContent = "";
    $("upload-dialog").showModal();
  });
});
$("close-upload").addEventListener("click", () => {
  if (!busy) closeUpload();
});
$("upload-dialog").addEventListener("cancel", (event) => {
  if (busy) {
    event.preventDefault();
    message("The review is still processing. Please wait for it to finish.");
  }
});
document.querySelectorAll("[data-open-guide]").forEach((button) => {
  button.addEventListener("click", () => {
    if (!busy) $("guide-dialog").showModal();
  });
});
$("close-guide").addEventListener("click", () => $("guide-dialog").close());
document.querySelectorAll("dialog").forEach((dialog) => {
  dialog.addEventListener("keydown", (event) => {
    if (event.key !== "Tab") return;
    const controls = Array.from(
      dialog.querySelectorAll(
        'button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled), a[href], summary, [tabindex="0"]',
      ),
    ).filter((element) => element.getClientRects().length > 0);
    const first = controls[0];
    const last = controls.at(-1);
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });
});
$("nav-reviews").addEventListener("click", () => {
  if (busy) return;
  closeReview();
  filter = "all";
  query = "";
  $("queue-search").value = "";
  renderQueue();
});
document.addEventListener("keydown", (event) => {
  const editing = event.target.closest(
    "input, textarea, select, [contenteditable]",
  );
  if (
    event.key === "/" &&
    !editing &&
    !document.querySelector("dialog[open]")
  ) {
    event.preventDefault();
    $("queue-search").focus();
  }
  if (
    event.key === "Escape" &&
    current &&
    !editing &&
    !document.querySelector("dialog[open]")
  )
    closeReview();
});
$("retry-load").addEventListener("click", () =>
  task(async () => {
    message("Reconnecting…");
    await initialize();
    if ($("queue-failure").hidden)
      message("Connection restored. Your queue is up to date.");
  }, "Connecting to local service…"),
);
task(initialize, "Loading workspace…");
