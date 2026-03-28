"use strict";

const SLOTS = [0, 1, 2];
const selectedFiles = [null, null, null];

const analyzeBtn   = document.getElementById("analyze-btn");
const materialSel  = document.getElementById("material-select");
const loadingEl    = document.getElementById("loading");
const errorBox     = document.getElementById("error-box");
const resultsEl    = document.getElementById("results");
const reportText   = document.getElementById("report-text");

// ── Material dropdown ────────────────────────────────────────────────────────

async function loadMaterials() {
  try {
    const res  = await fetch("/api/materials");
    const data = await res.json();
    materialSel.innerHTML = data.materials
      .map(m => `<option value="${m.key}">${m.name} (${m.unit}, +${m.waste_pct}% waste)</option>`)
      .join("");
  } catch {
    materialSel.innerHTML = '<option value="fiber_cement">Fiber Cement Board</option>';
  }
}

// ── Per-slot file handling ───────────────────────────────────────────────────

function setFile(slot, file) {
  if (!file) return;
  if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
    showError(`PDF ${slot + 1}: please upload a PDF file.`);
    return;
  }
  selectedFiles[slot] = file;
  const nameEl = document.getElementById(`name-${slot}`);
  nameEl.textContent = file.name;
  nameEl.hidden = false;
  document.getElementById(`card-${slot}`).classList.add("has-file");
  updateAnalyzeButton();
  hideError();
  resultsEl.hidden = true;
}

function updateAnalyzeButton() {
  analyzeBtn.disabled = selectedFiles[0] === null;
}

// Wire up each slot
SLOTS.forEach(slot => {
  const dropZone = document.getElementById(`drop-${slot}`);
  const fileInput = document.getElementById(`file-${slot}`);

  dropZone.addEventListener("dragover", e => {
    e.preventDefault();
    dropZone.classList.add("drag-over");
  });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
  dropZone.addEventListener("drop", e => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    setFile(slot, e.dataTransfer.files[0]);
  });
  dropZone.addEventListener("click", () => fileInput.click());
  dropZone.addEventListener("keydown", e => {
    if (e.key === "Enter" || e.key === " ") fileInput.click();
  });
  fileInput.addEventListener("change", () => setFile(slot, fileInput.files[0]));
});

// ── Analysis ─────────────────────────────────────────────────────────────────

analyzeBtn.addEventListener("click", async () => {
  if (!selectedFiles[0]) return;

  setLoading(true);
  hideError();
  resultsEl.hidden = true;

  const form = new FormData();
  form.append("material", materialSel.value);

  if (selectedFiles[0]) form.append("file1", selectedFiles[0]);
  if (selectedFiles[1]) form.append("file2", selectedFiles[1]);
  if (selectedFiles[2]) form.append("file3", selectedFiles[2]);

  SLOTS.forEach(slot => {
    const typeVal = document.getElementById(`type-${slot}`).value;
    form.append(`type${slot + 1}`, typeVal);
  });

  try {
    const res  = await fetch("/api/analyze-multi", { method: "POST", body: form });
    const data = await res.json();

    if (!res.ok || !data.success) {
      showError(data.detail || data.error || "Analysis failed. Please try again.");
    } else {
      reportText.textContent = data.report;
      resultsEl.hidden = false;
    }
  } catch {
    showError("Network error — is the backend running?");
  } finally {
    setLoading(false);
  }
});

// ── Helpers ──────────────────────────────────────────────────────────────────

function setLoading(on) {
  loadingEl.hidden     = !on;
  analyzeBtn.disabled  = on;
}

function showError(msg) {
  errorBox.textContent = msg;
  errorBox.hidden = false;
}

function hideError() {
  errorBox.hidden = true;
}

// ── Init ─────────────────────────────────────────────────────────────────────

loadMaterials();
