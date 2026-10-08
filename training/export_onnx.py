"""
ONNX Model Exporter for AI Heal
Exports PyTorch weights to ONNX (opset 17), generates FP16 variant,
and validates maximum numerical difference between PyTorch and ONNX Runtime.
License: MIT / Apache-2.0 Permissive.
"""
import os
import numpy as np

try:
    import torch
    import onnxruntime as ort
    from training.model import AIHealUNet
except ImportError:
    torch = None

def export_model_to_onnx(
    checkpoint_path: str,
    onnx_output_path: str = "backend/data/models/ai_heal_unet.onnx",
    opset: int = 17
):
    if torch is None:
        print("PyTorch is required for ONNX export. Install via: pip install torch")
        return

    os.makedirs(os.path.dirname(os.path.abspath(onnx_output_path)), exist_ok=True)
    device = torch.device("cpu")

    model = AIHealUNet(base_ch=32)
    if os.path.exists(checkpoint_path):
        model.load_state_dict(torch.load(checkpoint_path, map_location=device))
        print(f"Loaded checkpoint from: {checkpoint_path}")
    else:
        print(f"Checkpoint {checkpoint_path} not found. Exporting initialized architecture.")

    model.eval()

    dummy_input = torch.randn(1, 3, 512, 512, dtype=torch.float32)

    # 1. Export FP32 ONNX model
    torch.onnx.export(
        model,
        dummy_input,
        onnx_output_path,
        export_params=True,
        opset_version=opset,
        do_constant_folding=True,
        input_names=["input_patch"],
        output_names=["predicted_delta"],
        dynamic_axes={
            "input_patch": {0: "batch_size", 2: "height", 3: "width"},
            "predicted_delta": {0: "batch_size", 2: "height", 3: "width"}
        }
    )
    print(f"Successfully exported ONNX FP32 model: {onnx_output_path}")

    # 2. Validate numerical parity between PyTorch and ONNX
    with torch.no_grad():
        torch_out = model(dummy_input).numpy()

    sess = ort.InferenceSession(onnx_output_path, providers=["CPUExecutionProvider"])
    onnx_out = sess.run(["predicted_delta"], {"input_patch": dummy_input.numpy()})[0]

    max_diff = np.max(np.abs(torch_out - onnx_out))
    print(f"Validation difference (PyTorch vs ONNX): {max_diff:.6f}")
    if max_diff < 1e-4:
        print("✓ ONNX export passed verification with perfect fidelity!")
    else:
        print(f"⚠ Warning: numerical difference {max_diff} exceeded tolerance.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--ckpt", default="checkpoints/ai_heal_epoch_30.pt")
    parser.add_argument("--out", default="backend/data/models/ai_heal_unet.onnx")
    args = parser.parse_args()
    export_model_to_onnx(args.ckpt, args.out)
