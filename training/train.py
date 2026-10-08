"""
Training Script for AI Heal Residual Model
Trains the U-Net with L1 loss, mask-weighted skin preservation loss, and AdamW optimizer.
License: MIT / Apache-2.0 Permissive.
"""
import os
import glob
import time
from typing import Optional

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import Dataset, DataLoader
    from PIL import Image
    import torchvision.transforms as T
except ImportError:
    torch = None

if torch is not None:
    from training.model import AIHealUNet

    class PatchDataset(Dataset):
        def __init__(self, data_dir: str):
            self.input_paths = sorted(glob.glob(os.path.join(data_dir, "input", "*.png")))
            self.target_dir = os.path.join(data_dir, "target")
            self.mask_dir = os.path.join(data_dir, "mask")
            self.transform = T.ToTensor()

        def __len__(self):
            return len(self.input_paths)

        def __getitem__(self, idx):
            inp_path = self.input_paths[idx]
            fname = os.path.basename(inp_path)
            tgt_path = os.path.join(self.target_dir, fname)
            msk_path = os.path.join(self.mask_dir, fname)

            inp_img = Image.open(inp_path).convert("RGB")
            tgt_img = Image.open(tgt_path).convert("RGB")
            msk_img = Image.open(msk_path).convert("L") if os.path.exists(msk_path) else Image.new("L", inp_img.size, 255)

            inp_tensor = self.transform(inp_img)
            tgt_tensor = self.transform(tgt_img)
            msk_tensor = self.transform(msk_img)

            # Ground-truth residual delta
            gt_delta = tgt_tensor - inp_tensor
            return inp_tensor, gt_delta, msk_tensor

    def train(
        data_dir: str,
        output_dir: str = "checkpoints",
        epochs: int = 50,
        batch_size: int = 8,
        lr: float = 2e-4
    ):
        os.makedirs(output_dir, exist_ok=True)
        device = torch.device("cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu"))
        print(f"Training AI Heal model on device: {device}")

        dataset = PatchDataset(data_dir)
        if len(dataset) == 0:
            print("Dataset is empty. Run prepare_dataset.py first!")
            return

        dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=2, pin_memory=True)
        model = AIHealUNet(base_ch=32).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)

        criterion_l1 = nn.L1Loss()

        for epoch in range(1, epochs + 1):
            model.train()
            total_loss = 0.0
            t0 = time.time()

            for inp, gt_delta, msk in dataloader:
                inp = inp.to(device)
                gt_delta = gt_delta.to(device)
                msk = msk.to(device)

                optimizer.zero_grad()
                pred_delta = model(inp)

                # Mask-weighted loss: 3x penalty inside blemish mask, 1x on clean skin
                weight = 1.0 + 2.0 * msk
                loss_res = torch.mean(weight * torch.abs(pred_delta - gt_delta))
                # Smoothness regularization
                loss_reg = torch.mean(torch.abs(pred_delta[:, :, :, 1:] - pred_delta[:, :, :, :-1])) * 0.05
                loss = loss_res + loss_reg

                loss.backward()
                optimizer.step()
                total_loss += loss.item()

            scheduler.step()
            avg_loss = total_loss / len(dataloader)
            elapsed = time.time() - t0
            print(f"Epoch [{epoch}/{epochs}] - Loss: {avg_loss:.5f} - Time: {elapsed:.1f}s")

            if epoch % 5 == 0 or epoch == epochs:
                save_path = os.path.join(output_dir, f"ai_heal_epoch_{epoch}.pt")
                torch.save(model.state_dict(), save_path)
                print(f"Saved checkpoint: {save_path}")

        print("Training complete!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/patches")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch", type=int, default=8)
    args = parser.parse_args()
    if torch is not None:
        train(args.data, epochs=args.epochs, batch_size=args.batch)
    else:
        print("PyTorch is required to run train.py. Install via: pip install torch torchvision")
