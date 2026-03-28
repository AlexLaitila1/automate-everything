"use strict";

const dropZone     = document.getElementById("drop-zone");
const fileInput    = document.getElementById("file-input");
const fileNameEl   = document.getElementById("file-name");
const materialSel  = document.getElementById("material-select");
const analyzeBtn   = document.getElementById("analyze-btn");
const loadingEl    = document.getElementById("loading");
const errorBox     = document.getElementById("error-box");
const resultsEl    = document.getElementById("results");
const reportText   = document.getElementById("report-text");

let selectedFile = null;

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

// ── File handling ────────────────────────────────────────────────────────────

function setFile(file) {
  if (!file) return;
  if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
    showError("Please upload a PDF file.");
    return;
  }
  selectedFile = file;
  fileNameEl.textContent = `Selected: ${file.name}`;
  fileNameEl.hidden = false;
  analyzeBtn.disabled = false;
  hideError();
  resultsEl.hidden = true;
}

// Drop zone events
dropZone.addEventListener("dragover", e => {
  e.preventDefault();
  dropZone.classList.add("drag-over");
});

dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));

dropZone.addEventListener("drop", e => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");
  setFile(e.dataTransfer.files[0]);
});

dropZone.addEventListener("click", () => fileInput.click());

dropZone.addEventListener("keydown", e => {
  if (e.key === "Enter" || e.key === " ") fileInput.click();
});

fileInput.addEventListener("change", () => setFile(fileInput.files[0]));

// ── Analysis ─────────────────────────────────────────────────────────────────

analyzeBtn.addEventListener("click", async () => {
  if (!selectedFile) return;

  setLoading(true);
  hideError();
  resultsEl.hidden = true;

  const form = new FormData();
  form.append("file", selectedFile);
  form.append("material", materialSel.value);

  try {
    const res  = await fetch("/api/analyze", { method: "POST", body: form });
    const data = await res.json();

    if (!res.ok || !data.success) {
      showError(data.detail || data.error || "Analysis failed. Please try again.");
    } else {
      reportText.textContent = data.report;
      resultsEl.hidden = false;
    }
  } catch (err) {
    showError("Network error — is the backend running?");
  } finally {
    setLoading(false);
  }
});

// ── Helpers ──────────────────────────────────────────────────────────────────

function setLoading(on) {
  loadingEl.hidden  = !on;
  analyzeBtn.disabled = on;
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
