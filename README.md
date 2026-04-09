# 3D Model Generator

An AI-powered web application that turns uploaded images into downloadable 3D models (GLB files) using the [Meshy.ai](https://www.meshy.ai/) image-to-3D API.

---

## Features

- **Drag-and-drop image upload** — PNG, JPG, JPEG, WEBP (up to 20 MB)
- **Art-style selection** — Realistic, Sculpture, or PBR
- **Negative prompt** — Guide the AI away from unwanted attributes
- **Real-time progress bar** — Polls the generation task and shows live progress
- **Install / Download GLB button** — One click to save the finished 3D model

---

## Quick start

### 1. Clone & install dependencies

```bash
git clone <repo-url>
cd hr
pip install -r requirements.txt
```

### 2. Configure your API key

```bash
cp .env.example .env
# Open .env and set your Meshy.ai key:
# MESHY_API_KEY=your_meshy_api_key_here
```

Get a free API key at <https://www.meshy.ai/>.

### 3. Run the app

```bash
python app.py
```

Then open <http://localhost:5000> in your browser.

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/` | Serves the UI |
| `POST` | `/generate` | Accepts an image and submits a Meshy image-to-3D task |
| `GET`  | `/status/<task_id>` | Returns task status and progress |
| `GET`  | `/download/<task_id>` | Streams the finished GLB file |

### `POST /generate`

Form fields:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `image` | file | — | Image to convert (required) |
| `art_style` | string | `realistic` | `realistic` · `sculpture` · `pbr` |
| `negative_prompt` | string | `"low quality…"` | Attributes to avoid |

Response:

```json
{ "task_id": "abc123" }
```

### `GET /status/<task_id>`

```json
{
  "status": "IN_PROGRESS",
  "progress": 42,
  "glb_url": null
}
```

`glb_url` is set to `/download/<task_id>` once the model is ready.

### `GET /download/<task_id>`

Returns the GLB file as `model.glb` (cached locally after the first fetch).

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MESHY_API_KEY` | — | **Required.** Your Meshy.ai API key |
| `UPLOAD_FOLDER` | `uploads/` | Where uploaded images are stored temporarily |
| `OUTPUT_FOLDER` | `outputs/` | Where generated GLB files are cached |
| `SECRET_KEY` | `change-me-in-production` | Flask session secret |

---

## Project structure

```
hr/
├── app.py              # Flask backend
├── templates/
│   └── index.html      # Frontend UI
├── requirements.txt
├── .env.example
└── README.md
```