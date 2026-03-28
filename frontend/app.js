"use strict";

const SLOTS = ["pohjakuva", "julkisivu", "leikkaus"];
const selectedFiles = { pohjakuva: null, julkisivu: null, leikkaus: null };

const analyzeBtn   = document.getElementById("analyze-btn");
const materialSel  = document.getElementById("material-select");
const loadingEl    = document.getElementById("loading");
const errorBox     = document.getElementById("error-box");
const resultsEl    = document.getElementById("results");
const reportText   = document.getElementById("report-text");
const modelSection = document.getElementById("model-section");
const modelJson    = document.getElementById("model-json");
const toggleModel  = document.getElementById("toggle-model");

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
    showError(`${slot}: please upload a PDF file.`);
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
  const allPresent = SLOTS.every(s => selectedFiles[s] !== null);
  analyzeBtn.disabled = !allPresent;
}

// Wire up each slot
SLOTS.forEach(slot => {
  const dropZone  = document.getElementById(`drop-${slot}`);
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
  dropZone.addEventListener("click", e => {
    // Don't double-trigger when the click came from the browse label
    if (e.target.closest("label")) return;
    fileInput.click();
  });
  dropZone.addEventListener("keydown", e => {
    if (e.key === "Enter" || e.key === " ") fileInput.click();
  });
  fileInput.addEventListener("change", () => setFile(slot, fileInput.files[0]));
});

// ── Analysis ─────────────────────────────────────────────────────────────────

analyzeBtn.addEventListener("click", async () => {
  if (!SLOTS.every(s => selectedFiles[s])) return;

  setLoading(true);
  hideError();
  resultsEl.hidden = true;

  const form = new FormData();
  form.append("material", materialSel.value);
  form.append("pohjakuva", selectedFiles["pohjakuva"]);
  form.append("julkisivu", selectedFiles["julkisivu"]);
  form.append("leikkaus",  selectedFiles["leikkaus"]);

  try {
    const res  = await fetch("/api/analyze-3d", { method: "POST", body: form });
    const data = await res.json();

    if (!res.ok || !data.success) {
      const msg = data.detail || data.error || "Analysis failed. Please try again.";
      showError(msg);
      reportText.textContent = msg;
      document.querySelector("#results h2").textContent = "Analysis Error";
      modelSection.hidden = true;
      resultsEl.hidden = false;
    } else {
      document.querySelector("#results h2").textContent = "3D Simulation Report";
      reportText.textContent = data.report;
      if (data.house_model) {
        modelJson.textContent = JSON.stringify(data.house_model, null, 2);
        modelJson.hidden = true;
        toggleModel.textContent = "Show House Model (JSON)";
        modelSection.hidden = false;
      } else {
        modelSection.hidden = true;
      }
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
  loadingEl.hidden    = !on;
  analyzeBtn.disabled = on;
}

function showError(msg) {
  errorBox.textContent = msg;
  errorBox.hidden = false;
}

function hideError() {
  errorBox.hidden = true;
}

// ── House Model toggle ────────────────────────────────────────────────────────

toggleModel.addEventListener("click", () => {
  const visible = !modelJson.hidden;
  modelJson.hidden = visible;
  toggleModel.textContent = visible ? "Show House Model (JSON)" : "Hide House Model (JSON)";
});

// ── Init ─────────────────────────────────────────────────────────────────────

loadMaterials();
