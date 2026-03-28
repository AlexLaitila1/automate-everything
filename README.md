# OpenClaw — Blueprint Cladding Estimator

Upload three Finnish architectural PDFs and get an exterior cladding estimate in seconds.

Claude Vision reads each drawing type in parallel, merges the measurements into a 3D house model, and calculates how much material to order.

## How It Works

```
3 PDFs uploaded
  pohjakuva (floor plan)   → wall lengths, footprint polygon
  julkisivu (elevation)    → wall height, openings, wall shapes
  leikkaus  (cross-section)→ storey height, eave level, roof pitch
        ↓
  3 parallel Claude Vision calls
        ↓
  HouseModel (merged + height-reconciled)
        ↓
  Perimeter, gross wall area, cladding units + cost
```

## Running

**With Docker (recommended):**

```bash
cp .env.example .env   # add your ANTHROPIC_API_KEY
docker-compose up --build
```

Open `http://localhost:8080`

**Without Docker:**

```bash
cp .env.example .env
pip install -r requirements.txt
uvicorn api:app --reload
# open frontend/index.html directly in browser
```

## API Endpoints

| Method | Path | Input | Description |
|--------|------|-------|-------------|
| GET | `/api/health` | — | Liveness check |
| GET | `/api/materials` | — | List available cladding materials |
| POST | `/api/analyze-3d` | `pohjakuva`, `julkisivu`, `leikkaus` PDFs + `material` | **Primary** — 3D model pipeline |
| POST | `/api/analyze-multi` | 1–3 PDFs + optional type hints + `material` | Auto-classifies drawing types |
| POST | `/api/analyze` | 1 PDF + `material` | Single-PDF legacy pipeline |

## Available Materials

`fiber_cement`, `brick`, `vinyl`, `wood_panel`, `metal_cladding`

Passed as the `material` form field. Defaults to `fiber_cement`.

## Project Structure

```
api.py                          FastAPI routes + input validation
pdf_converter.py                PDF → PNG → base64 (Poppler)

frontend/
  index.html / app.js / style.css   UI with 3 drop zones
  nginx.conf                         Proxies /api/* to backend

skills/blueprint/
  simulation_orchestrator.py    Primary pipeline (3D)
  extract_pohjakuva.py          Claude call — floor plan
  extract_julkisivu.py          Claude call — elevation
  extract_leikkaus.py           Claude call — cross-section
  house_model.py                Merge + reconcile 3 partial dicts → HouseModel
  calculate_from_house_model.py Perimeter, area, cladding (no Claude)
  orchestrator.py               Legacy single-PDF pipeline
  multi_orchestrator.py         Legacy multi-PDF pipeline
  prompts.py                    All Claude system prompts
  materials.py                  Material specs (coverage, waste %, cost)
  geometry.py                   Polygon math
  json_utils.py                 JSON extraction from Claude responses
  models.py                     Shared dataclasses

tests/                          158 pytest tests (no API key required)
```

## Environment Variables

```bash
ANTHROPIC_API_KEY=sk-ant-...   # required
```

## Tech Stack

- **Backend**: Python 3.13, FastAPI, Anthropic Claude Vision (`claude-sonnet-4-6`)
- **Frontend**: Plain HTML/CSS/JS, nginx
- **Infra**: Docker Compose (backend port 8000, frontend port 8080)
- **PDF processing**: Poppler via `pdf2image`
