"""Metric depth from Depth Anything 3 (DA3METRIC-LARGE), at the resolution of the input frame.

The network works at 504 px and returns canonical depth. As in apply_metric_scaling (depth_anything_3/utils/alignment.py), metres = depth * focal / 300, with the focal length taken at 504 px: 252 / tan(50°) = 211.4 px for the 100° EB-Navigation camera. The result is resized back to the frame size so that it lines up with the detection boxes.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from depthjev.geometry import DA3_PROCESS_RES, FOV_DEG, canonical_to_metric, focal_px


class DepthEstimator:
    def __init__(
        self, model_dir: str, device: str = "cuda", fov_deg: float = FOV_DEG, process_res: int = DA3_PROCESS_RES
    ):
        import torch
        from depth_anything_3.api import DepthAnything3

        self.device = torch.device(device)
        self.fov_deg = fov_deg
        self.process_res = process_res
        self.model = DepthAnything3.from_pretrained(model_dir).to(self.device)
        self.model.eval()

    def predict(self, image: Image.Image) -> np.ndarray:
        """Metric depth (H x W float32, metres, camera Z) aligned with the input image."""
        import cv2

        rgb = np.asarray(image.convert("RGB"))
        pred = self.model.inference([rgb], process_res=self.process_res, process_res_method="upper_bound_resize")
        canonical = np.asarray(pred.depth[0], dtype=np.float32)  # (h, w) at the processed resolution
        focal_processed = focal_px(canonical.shape[1], self.fov_deg)  # 211.4 px for 504 px / 100 deg
        metric = canonical_to_metric(canonical, focal_processed)
        h, w = rgb.shape[:2]
        if metric.shape != (h, w):
            metric = cv2.resize(metric, (w, h), interpolation=cv2.INTER_LINEAR)
        return metric.astype(np.float32)
