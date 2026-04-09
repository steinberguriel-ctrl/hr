# Image-to-3D with TripoSR + Gradio

Upload an image and instantly get a 3D model you can spin and inspect in the browser.

## Setup

```bash
# Install TripoSR (required, not on PyPI)
pip install git+https://github.com/VAST-AI-Research/TripoSR.git

# Install the remaining dependencies
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Then open `http://localhost:7860` in your browser.

## How it works

1. Upload any image of an object.
2. The background is removed automatically with `rembg`.
3. [TripoSR](https://github.com/VAST-AI-Research/TripoSR) (`stabilityai/TripoSR`) generates a 3D mesh.
4. The mesh is exported as a `.glb` file and displayed with Gradio's built-in `Model3D` component.
