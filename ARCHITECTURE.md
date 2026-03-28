# OpenClaw — Architecture Overview

## What the app does

A construction CEO drops Finnish architectural PDF drawings into a web UI.
The system converts them to images, sends them to Claude (vision AI),
extracts measurements, and calculates how much exterior cladding is needed.

---

## System Map

```
USER BROWSER
│
│  drag & drop 3 PDFs
│  (Pohjakuva / Julkisivu / Leikkaus)
│
▼
┌─────────────────────────────────────────┐
│  frontend/index.html + app.js           │
│                                         │
│  3 drop zones (labeled per drawing type)│
│  material dropdown                      │
│  "Run 3D Simulation" button             │
│  results displayed as raw text <pre>    │
└─────────────────┬───────────────────────┘
                  │  POST /api/analyze-3d
                  │  multipart/form-data
                  │  pohjakuva= julkisivu= leikkaus= material=
                  ▼
┌─────────────────────────────────────────┐
│  api.py   (FastAPI, Docker container)   │
│                                         │
│  pdf_to_base64_png()  ← pdf_converter.py│
│  converts each PDF page → PNG → base64  │
│  (uses Poppler / pdf2image library)     │
└─────────────────┬───────────────────────┘
                  │  3 base64 images
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  simulation_orchestrator.py   (THE ACTIVE PIPELINE)             │
│                                                                  │
│  Step 1 — 3 parallel Claude vision calls:                       │
│  ┌──────────────────┐  ┌───────────────────┐  ┌──────────────┐ │
│  │ extract_pohjakuva│  │ extract_julkisivu │  │extract_leikkaus│ │
│  │                  │  │                   │  │              │ │
│  │ EXTRACT_POHJAKUVA│  │ EXTRACT_JULKISIVU │  │EXTRACT_LEIKKAUS│
│  │ _SYSTEM_PROMPT   │  │ _SYSTEM_PROMPT    │  │_SYSTEM_PROMPT│ │
│  │                  │  │                   │  │              │ │
│  │ Returns:         │  │ Returns:          │  │ Returns:     │ │
│  │ PohjakuvaData    │  │ JulkisivuData     │  │ LeikkausData │ │
│  │ - walls[]        │  │ - face_label      │  │ - storey_h_m │ │
│  │ - width_m        │  │ - facade_width_m  │  │ - total_h_m  │ │
│  │ - depth_m        │  │ - wall_height_m   │  │ - roof_pitch │ │
│  │ - shape          │  │ - openings[]      │  │ - num_storeys│ │
│  │ - openings[]     │  │                   │  │              │ │
│  └──────────────────┘  └───────────────────┘  └──────────────┘ │
│                                                                  │
│  Step 2 — assemble_3d.py:                                       │
│  Combines the three data objects into Building3D.               │
│  Reconciles wall height: if Julkisivu and Leikkaus disagree     │
│  by >20%, trusts Leikkaus (section = definitive height source). │
│                                                                  │
│  Step 3 — calculate_from_3d.py:                                 │
│  perimeter_m     = sum of all wall segment lengths              │
│  gross_area_m2   = perimeter × wall_height                      │
│  deductions_m2   = sum of all opening areas (windows + doors)   │
│  net_area_m2     = gross − deductions                           │
│  cladding units  = ceil(net_area / coverage_per_unit × waste)   │
│  total_cost      = units × unit_cost                            │
│                                                                  │
│  Step 4 — _format_report():                                     │
│  Formats everything as a plain-text report string               │
└─────────────────────────────────────────────────────────────────┘
                  │  {"success": true, "report": "text..."}
                  ▼
        browser shows report in <pre> tag
```

---

## Data Models (models.py)

```
PohjakuvaData          JulkisivuData           LeikkausData
─────────────          ─────────────           ────────────
walls[]                face_label              storey_height_m
  └─ label             facade_width_m          total_height_m
  └─ length_m          wall_height_m           roof_pitch_deg
width_m                openings[]              num_storeys
depth_m                  └─ face               scale_description
shape                    └─ label
scale_description        └─ width_m
openings[]               └─ height_m

         All three combine into:

         Building3D
         ──────────
         pohjakuva: PohjakuvaData
         julkisivu: JulkisivuData
         leikkaus:  LeikkausData
         material_key: str

         Which produces:

         SimulationResult
         ────────────────
         perimeter_m
         wall_height_m
         gross_wall_area_m2
         opening_deductions_m2
         net_wall_area_m2
         cladding: CladdingEstimate
           └─ material_name
           └─ units_needed
           └─ unit_label
           └─ total_cost
```

---

## File Map

```
automate-everything/
│
├── api.py                          Entry point — FastAPI app, all HTTP routes
├── pdf_converter.py                PDF → PNG conversion (uses Poppler)
│
├── frontend/
│   ├── index.html                  UI — 3 drop zones (Pohjakuva/Julkisivu/Leikkaus)
│   ├── app.js                      Calls /api/analyze-3d, shows text result
│   └── style.css                   Styling
│
├── skills/blueprint/
│   ├── models.py                   All dataclasses (PohjakuvaData, Building3D, etc.)
│   ├── prompts.py                  All Claude system prompts
│   │
│   ├── simulation_orchestrator.py  ACTIVE PIPELINE — coordinates the 3-step flow
│   ├── extract_pohjakuva.py        Claude call #1 — reads floor plan
│   ├── extract_julkisivu.py        Claude call #2 — reads elevation
│   ├── extract_leikkaus.py         Claude call #3 — reads cross-section
│   ├── assemble_3d.py              Combines 3 data objects into Building3D
│   ├── calculate_from_3d.py        Math — perimeter, area, cladding quantity
│   ├── estimate_cladding.py        Converts area → units → cost
│   ├── materials.py                Material definitions (cost, coverage, waste%)
│   │
│   └── json_utils.py               Shared JSON parsing helper
│
└── docker-compose.yml              Runs backend + frontend containers
```

---

## The 3 Prompts Claude Uses

| File | Drawing type | What Claude extracts |
|------|-------------|----------------------|
| `EXTRACT_POHJAKUVA_SYSTEM_PROMPT` | Pohjakuva (floor plan) | Wall segments + lengths, footprint shape, windows/doors from above |
| `EXTRACT_JULKISIVU_SYSTEM_PROMPT` | Julkisivu (elevation) | Wall height, facade width, windows/doors with confirmed heights |
| `EXTRACT_LEIKKAUS_SYSTEM_PROMPT` | Leikkaus (cross-section) | Storey height, total height, roof pitch, number of storeys |

---

## Inactive / Orphaned Code

These exist in the codebase but are NOT called by the current frontend:

| Endpoint | File | What it does | Why not used |
|----------|------|-------------|--------------|
| `POST /api/analyze` | `orchestrator.py` | Single PDF, old pipeline | Replaced by 3D pipeline |
| `POST /api/analyze-multi` | `multi_orchestrator.py` | 1-3 PDFs, auto-classify each | Replaced by 3D pipeline |
| `POST /api/analyze-cladding` | `analyze_cladding.py` | Single Claude call with few-shot example, returns running metres in JSON | Added but frontend reverted to 3D endpoint |

---

## Known Issues / What Does Not Work Yet

1. **Running metres not calculated** — the active pipeline calculates m² and converts to
   sheets/bricks/m², but does NOT calculate running metres (rm) for plank cladding.
   The `analyze_cladding.py` orphan does this correctly, but is not wired to the UI.

2. **Material not read from drawings** — the active pipeline uses a user-selected dropdown,
   not text extracted from the elevation drawing.

3. **Results shown as raw text** — the frontend dumps the report into `<pre>` instead of
   rendering it as structured fields.

4. **`simulation_orchestrator.py` is missing** from `analyze_cladding` import in `api.py` —
   `analyze_cladding` is imported but no route calls it (dead import).

---

## Docker Setup

```
docker-compose up --build

  backend   → FastAPI (uvicorn) on port 8000
  frontend  → nginx serving static files on port 80
              nginx proxies /api/* to backend:8000
```

Environment variables required in `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
```
