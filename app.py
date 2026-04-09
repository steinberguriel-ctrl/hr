"""
Image-to-3D Generator using TripoSR and Gradio.

Upload an image and get a 3D model (.glb) previewed directly in the browser.
"""

import os
import tempfile

import gradio as gr
import numpy as np
import rembg
import torch
from PIL import Image

from tsr.system import TSR
from tsr.utils import remove_background, resize_foreground


DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

model = TSR.from_pretrained(
    "stabilityai/TripoSR",
    config_name="config.yaml",
    weight_name="model.ckpt",
)
model.renderer.set_chunk_size(131072)
model.to(DEVICE)

rembg_session = rembg.new_session()


def preprocess(image: Image.Image, foreground_ratio: float = 0.85) -> Image.Image:
    image = remove_background(image, rembg_session)
    image = resize_foreground(image, foreground_ratio)
    image = np.array(image).astype(np.float32) / 255.0
    image = image[:, :, :3] * image[:, :, 3:4] + (1 - image[:, :, 3:4]) * 0.5
    image = Image.fromarray((image * 255).astype(np.uint8))
    return image


def generate_3d(
    image: Image.Image,
    foreground_ratio: float,
    mc_resolution: int,
) -> str:
    if image is None:
        raise gr.Error("Please upload an image first.")

    processed = preprocess(image, foreground_ratio)

    with torch.no_grad():
        scene_codes = model([processed], device=DEVICE)

    meshes = model.extract_mesh(scene_codes, resolution=mc_resolution)
    mesh = meshes[0]

    tmp = tempfile.NamedTemporaryFile(suffix=".glb", delete=False)
    mesh.export(tmp.name)
    return tmp.name


with gr.Blocks(title="Image to 3D — TripoSR") as demo:
    gr.Markdown("# 🖼️ → 🧊 Image to 3D with TripoSR")
    gr.Markdown(
        "Upload any image and the app will generate a 3D model (.glb) you can "
        "rotate and inspect directly in the browser."
    )

    with gr.Row():
        with gr.Column():
            input_image = gr.Image(type="pil", label="Input Image")
            foreground_ratio = gr.Slider(
                minimum=0.5,
                maximum=1.0,
                value=0.85,
                step=0.05,
                label="Foreground Ratio",
            )
            mc_resolution = gr.Slider(
                minimum=32,
                maximum=320,
                value=256,
                step=32,
                label="Marching-Cubes Resolution",
            )
            run_btn = gr.Button("Generate 3D Model", variant="primary")

        with gr.Column():
            output_model = gr.Model3D(label="3D Preview (.glb)")

    run_btn.click(
        fn=generate_3d,
        inputs=[input_image, foreground_ratio, mc_resolution],
        outputs=output_model,
    )

if __name__ == "__main__":
    demo.launch()
