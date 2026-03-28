# OpenClaw — Architecture Overview

## What the app does

A construction CEO uploads three Finnish architectural PDF drawings into a web UI.
The system converts them to images, sends them to Claude (vision AI) in parallel,
extracts all measurements, and calculates how much exterior cladding is needed.

---

## System Map

```
USER BROWSER
│
│  drag & drop 3 PDFs
│  (Pohjakuva / Julkisivu / Leikkaus)
│
▼
┌──────────────────────────────────────────┐
│  frontend/index.html + app.js            │
│                                          │
│  3 drop zones (labeled per drawing type) │
│  material dropdown                       │
│  "Run 3D Simulation" button              │
│  results displayed as text <pre>         │
└──────────────────┬───────────────────────┘
                   │  POST /api/analyze-3d
                   │  multipart/form-data
                   │  pohjakuva= julkisivu= leikkaus= material=
                   ▼
┌──────────────────────────────────────────┐
│  api.py   (FastAPI, Docker container)    │
│                                          │
│  pdf_to_base64_png()  ← pdf_converter.py │
│  converts each PDF page → PNG → base64   │
│  (uses Poppler / pdf2image library)      │
└──────────────────┬───────────────────────┘
                   │  3 base64 images
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│  simulation_orchestrator.py   (PRIMARY PIPELINE)                     │
│                                                                      │
│  Step 1 — 3 parallel Claude vision calls (asyncio.gather):          │
│  ┌────────────────────┐  ┌─────────────────────┐  ┌──────────────┐ │
│  │ extract_pohjakuva  │  │ extract_julkisivu   │  │extract_leikkaus│ │
│  │ max_tokens: 4096   │  │ max_tokens: 2048    │  │max_tokens:1024│ │
│  │                    │  │                     │  │              │ │
│  │ Returns partial    │  │ Returns partial     │  │ Returns partial│ │
│  │ HouseModel dict:   │  │ HouseModel dict:    │  │ HouseModel:  │ │
│  │ - walls[]          │  │ - face_label        │  │ - storey_h_m │ │
│  │ - footprint_verts[]│  │ - facade_width_m    │  │ - eave_level_m│ │
│  │ - width_m, depth_m │  │ - wall_height_m     │  │ - total_h_m  │ │
│  │ - shape            │  │ - wall_shapes[]     │  │ - roof_pitch │ │
│  │ - openings[]       │  │ - openings[]        │  │ - num_storeys│ │
│  └────────────────────┘  └─────────────────────┘  └──────────────┘ │
│                                                                      │
│  Step 2 — house_model.py (HouseModelBuilder.build):                 │
│  Merges the three partial dicts into a single frozen HouseModel.    │
│  Height reconciliation:                                             │
│    • eave_level_m from Leikkaus = primary height source             │
│    • Julkisivu wall_height_m used when Leikkaus has no eave_level   │
│    • If Julkisivu and Leikkaus×storeys disagree >20%, Leikkaus wins │
│                                                                      │
│  Step 3 — calculate_from_house_model.py:                            │
│    perimeter_m     = polygon_perimeter(footprint_vertices)          │
│                      or sum of wall lengths                         │
│    gross_area_m2   = shape-based when wall_shapes available         │
│                      (rect × reconciled height + gable triangle)    │
│                      otherwise perimeter × wall_height_m            │
│    deductions_m2   = sum of opening areas (informational only)      │
│    net_area_m2     = gross − deductions                             │
│    cladding        = from gross area (Finnish practice: order full  │
│                      surface, cut openings on site)                 │
│                                                                      │
│  Step 4 — _format_report():                                         │
│  Plain-text report + house_model dict returned to API               │
└─────────────────────────────────────────────────────────────────────┘
                   │  {"success": true, "report": "...", "house_model": {...}}
                   ▼
         browser shows report in <pre> tag
```

---

## Data Model

```
Three partial dicts from extractors
       │
       ▼
HouseModelBuilder.build()
       │
       ▼
HouseModel (frozen dataclass)
─────────────────────────────
walls[]                       ← from Pohjakuva
  └─ label, length_m
footprint_vertices[]          ← from Pohjakuva (polygon corners in metres)
width_m, depth_m              ← from Pohjakuva
footprint_shape               ← from Pohjakuva

wall_height_m                 ← reconciled (Leikkaus eave_level_m preferred)
eave_level_m                  ← from Leikkaus (floor-to-eave, most reliable)
facade_width_m                ← from Julkisivu
openings[]                    ← from Julkisivu (fallback: Pohjakuva)
  └─ face, label, width_m, height_m
wall_face_shapes[]            ← from Julkisivu
  └─ face, components[]
       └─ shape_type (rectangle | triangle | trapezoid)
          width_m, height_m, height_right_m

storey_height_m               ← from Leikkaus
num_storeys                   ← from Leikkaus
roof_pitch_deg                ← from Leikkaus
total_height_m                ← from Leikkaus
material_key                  ← user-selected
scale_descriptions[]          ← one per source PDF
       │
       ▼
SimulationResult (frozen dataclass)
────────────────────────────────────
perimeter_m
wall_height_m
gross_wall_area_m2
opening_deductions_m2
net_wall_area_m2
cladding: CladdingEstimate
  └─ material_name, net_area_m2, waste_factor_pct
     total_area_needed_m2, units_needed, unit_cost, unit_label, total_cost
```

---

## File Map

```
automate-everything/
│
├── api.py                          FastAPI app — all HTTP routes
├── pdf_converter.py                PDF → PNG → base64 (uses Poppler)
├── bot.py                          Telegram bot (uses /api/analyze endpoint)
│
├── frontend/
│   ├── index.html                  3 drop zones (Pohjakuva/Julkisivu/Leikkaus)
│   ├── app.js                      Calls /api/analyze-3d, shows text result
│   ├── style.css                   Styling
│   └── nginx.conf                  Reverse-proxy /api/* to backend:8000
│
├── skills/blueprint/
│   │
│   │   ── Primary 3D pipeline (/api/analyze-3d) ──
│   ├── simulation_orchestrator.py  Coordinates 3-step flow, formats report
│   ├── extract_pohjakuva.py        Claude call — floor plan → walls, vertices
│   ├── extract_julkisivu.py        Claude call — elevation → heights, shapes, openings
│   ├── extract_leikkaus.py         Claude call — cross-section → heights, pitch
│   ├── house_model.py              HouseModel dataclass + HouseModelBuilder (merge + reconcile)
│   ├── calculate_from_house_model.py  Perimeter, area (shape-based), cladding
│   │
│   │   ── Legacy single-PDF pipeline (/api/analyze, Telegram bot) ──
│   ├── orchestrator.py             Single-PDF flow
│   ├── extract_dimensions.py       Claude call — any blueprint → wall segments + height
│   ├── calculate_perimeter.py      Sum wall lengths → perimeter
│   ├── calculate_wall_area.py      Perimeter × height → gross/net area
│   │
│   │   ── Legacy multi-PDF pipeline (/api/analyze-multi) ──
│   ├── multi_orchestrator.py       Classify + analyze 1–3 PDFs, combine results
│   ├── classify_blueprint.py       Claude call — identifies floor_plan/elevation/section
│   ├── combine_results.py          Merges multi-PDF analysis into a single report
│   │
│   │   ── Shared ──
│   ├── estimate_cladding.py        Area → units → cost for any material
│   ├── materials.py                Material definitions (coverage, waste %, cost/unit)
│   ├── models.py                   Dataclasses: WallShapeComponent, WallFaceShape,
│   │                               CladdingEstimate, SimulationResult, etc.
│   ├── geometry.py                 Polygon perimeter/area, Point2D, distance helpers
│   ├── prompts.py                  All Claude system prompts
│   └── json_utils.py               Robust JSON extraction from Claude responses
│
└── tests/                          pytest suite (158 tests)
    ├── test_api.py                 /api/analyze endpoint
    ├── test_api_3d.py              /api/analyze-3d endpoint
    ├── test_api_multi.py           /api/analyze-multi endpoint
    ├── test_calculate_from_house_model.py
    ├── test_calculations.py
    ├── test_classify_blueprint.py
    ├── test_combine_results.py
    ├── test_geometry.py
    ├── test_house_model.py
    ├── test_models.py
    ├── test_multi_orchestrator.py
    ├── test_orchestrator.py
    ├── test_pdf_converter.py
    ├── test_simulation.py
    └── test_wall_shapes.py
```

---

## The Claude Prompts

| Prompt | Drawing | max_tokens | What Claude extracts |
|--------|---------|-----------|----------------------|
| `EXTRACT_POHJAKUVA_SYSTEM_PROMPT` | Pohjakuva (floor plan) | 4096 | Exterior walls + lengths, polygon vertices, footprint shape, openings from above |
| `EXTRACT_JULKISIVU_SYSTEM_PROMPT` | Julkisivu (elevation) | 2048 | Eave height, facade width, wall shape decomposition (rect + gable/trapezoid), openings with sizes |
| `EXTRACT_LEIKKAUS_SYSTEM_PROMPT` | Leikkaus (cross-section) | 1024 | eave_level_m, storey height, total height, roof pitch, number of storeys |

All heights are read from `+X.XXX` metre annotations above `±0.000` ground datum. No default values are used — missing required fields cause the extractor to retry or fail with a clear error.

---

## Height Reconciliation Logic

```
eave_level_m present in Leikkaus?
  ├─ YES → wall_height_m = eave_level_m         (most reliable)
  └─ NO
       ├─ Both Julkisivu height AND Leikkaus storey×storeys available?
       │    ├─ Differ by >20% → use Leikkaus (storey × storeys)
       │    └─ Agree within 20% → use Julkisivu height
       ├─ Only Julkisivu height → use Julkisivu height
       └─ Only Leikkaus → use storey × storeys
```

---

## Gross Area Calculation (Shape-Based)

When Julkisivu provides `wall_shapes` (rectangle + gable triangle, etc.):

1. Find walls whose length matches `facade_width_m` (±8% tolerance) — these are the gable-end walls
2. Gable-end walls get: `count × (facade_width × wall_height_m + 0.5 × facade_width × gable_height)`
3. Perpendicular walls get: `length × wall_height_m`
4. Rectangle component always uses reconciled `wall_height_m` (not raw Julkisivu value)

Falls back to `perimeter × wall_height_m` when no shapes are extracted.

---

## Docker Setup

```
docker-compose up --build

  backend   → FastAPI (uvicorn) on port 8000
  frontend  → nginx serving static files on port 80
              nginx proxies /api/* to backend:8000
```

Required in `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
```
