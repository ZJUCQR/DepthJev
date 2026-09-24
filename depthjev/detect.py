"""Find the target object with OWLv2 (google/owlv2-base-patch16-ensemble) through transformers.

The image processor pads each frame to a square before resizing it to 960 x 960, so boxes are scaled back with the padded size, max(H, W). EB-Navigation frames are already square, so that is simply the frame size.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image


@dataclass
class Detection:
    box: tuple[float, float, float, float]  # x0, y0, x1, y1 in input pixels
    score: float
    query: str


class TargetDetector:
    def __init__(self, model_dir: str, device: str = "cuda", threshold: float = 0.1):
        import torch
        from transformers import Owlv2ForObjectDetection, Owlv2Processor

        self.device = torch.device(device)
        self.threshold = threshold
        self.processor = Owlv2Processor.from_pretrained(model_dir)
        self.model = Owlv2ForObjectDetection.from_pretrained(model_dir).to(self.device)
        self.model.eval()

    def detect(self, image: Image.Image, names: list[str]) -> list[Detection]:
        """All detections above threshold for the given object names, best score first."""
        import torch

        image = image.convert("RGB")
        queries = [f"a photo of a {n}" for n in names]
        inputs = self.processor(text=[queries], images=image, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.model(**inputs)
        side = max(image.size)
        target_sizes = torch.tensor([[side, side]], device=self.device)
        results = self.processor.post_process_object_detection(
            outputs=outputs, threshold=self.threshold, target_sizes=target_sizes
        )[0]
        dets = []
        for box, score, label in zip(results["boxes"], results["scores"], results["labels"], strict=True):
            x0, y0, x1, y1 = [float(v) for v in box.tolist()]
            dets.append(Detection(box=(x0, y0, x1, y1), score=float(score), query=queries[int(label)]))
        dets.sort(key=lambda d: d.score, reverse=True)
        return dets
