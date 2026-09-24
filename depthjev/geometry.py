"""Geometry of an EB-Navigation frame: from a metric depth map to free distance, obstacles and target range.

Image rows run top to bottom and columns left to right. The camera frame has X to the right, Y down and Z forward along the optical axis, in metres. To measure against the floor, points are rotated back by the camera pitch into a gravity-aligned frame with the same origin, where Yw points straight down and Zw is the horizontal forward direction. Pitch is positive when the camera looks down, the same sign as AI2-THOR's cameraHorizon.

AI2-THOR's fieldOfView is Unity's vertical field of view; EB-Navigation frames are square, so the 100° also holds horizontally.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

FOV_DEG = 100.0  # EBNavigationEnv(fov=100)
DA3_PROCESS_RES = 504  # DepthAnything3.inference(process_res=504); 504 = 36 x 14 patches
DA3_CANONICAL_FOCAL = 300.0  # alignment.apply_metric_scaling(scale_factor=300.0)

CAMERA_HEIGHT_M = 1.576  # AI2-THOR default agent, standing (camera y above the floor)
AGENT_RADIUS_M = 0.2  # AI2-THOR agent capsule radius
MOVE_STEP_M = 0.25  # every translation action moves 0.25 m
OBSTACLE_MIN_HEIGHT_M = (
    0.15  # points lower than this above the floor count as floor (rugs, thresholds); to be calibrated
)
OBSTACLE_MAX_HEIGHT_M = 1.8  # points higher than this are ceiling / lamps the agent walks under; to be calibrated
FLOOR_PERCENTILE = 90  # floor = the deepest (largest Yw) points of the lower half; 90th pct is robust to clutter
FLOOR_RANGE_M = (
    0.9,
    2.0,
)  # covers the DA3 scale band measured on the GPU smoke (x0.67 near, x0.95 far); else the constant
MIN_OBSTACLE_PIXELS = 20  # fewer obstacle pixels than this are treated as noise; to be calibrated
DEPTH_VALID_RANGE_M = (0.05, 20.0)

SECTOR_NAMES = ("far_left", "left", "center", "right", "far_right")
DISTANCE_BINS = ((0.5, "under 0.5 m"), (1.0, "0.5 to 1 m"), (2.0, "1 to 2 m"), (math.inf, "over 2 m"))


def focal_px(size_px: float, fov_deg: float = FOV_DEG) -> float:
    """Focal length in pixels for a square frame of ``size_px`` pixels and the given field of view.

    500 px / 100 deg -> 209.8 px; 504 px / 100 deg -> 211.4 px (the value used in the README).
    """
    return size_px / 2.0 / math.tan(math.radians(fov_deg) / 2.0)


def canonical_to_metric(depth_canonical: np.ndarray, focal_processed_px: float) -> np.ndarray:
    """DA3 canonical depth -> metres: depth * focal / 300 (focal at the processed resolution)."""
    return depth_canonical * (focal_processed_px / DA3_CANONICAL_FOCAL)


def distance_bin(distance_m: float | None) -> str:
    """None/NaN = no measurement ("unknown"); +inf = nothing seen in that direction ("over 2 m")."""
    if distance_m is None or math.isnan(distance_m):
        return "unknown"
    if distance_m == math.inf:
        return DISTANCE_BINS[-1][1]
    for upper, label in DISTANCE_BINS:
        if distance_m < upper:
            return label
    return DISTANCE_BINS[-1][1]


def sector_of_column(col: float, width: int) -> str:
    idx = int(col * len(SECTOR_NAMES) / width)
    return SECTOR_NAMES[min(max(idx, 0), len(SECTOR_NAMES) - 1)]


def backproject(depth_m: np.ndarray, focal: float, cx: float, cy: float):
    """Camera-frame coordinates (X right, Y down, Z forward) for every pixel; depth is Z."""
    h, w = depth_m.shape
    us = np.arange(w, dtype=np.float32)[None, :]
    vs = np.arange(h, dtype=np.float32)[:, None]
    z = depth_m.astype(np.float32)
    x = (us - cx) / focal * z
    y = (vs - cy) / focal * z
    return x, y, z


def gravity_align(x, y, z, pitch_deg: float):
    """Undo the camera pitch. pitch_deg > 0 means the camera looks down."""
    t = math.radians(pitch_deg)
    c, s = math.cos(t), math.sin(t)
    yw = y * c + z * s
    zw = -y * s + z * c
    return x, yw, zw


def estimate_floor_depth(yw: np.ndarray, zw: np.ndarray, valid: np.ndarray, percentile: float = FLOOR_PERCENTILE):
    """Camera-to-floor distance from the lower half of the image. Returns (distance, from_data).

    Floor points are the lowest points in the scene, i.e. the largest gravity-aligned Yw, so a high
    percentile of Yw over the lower half tracks the floor even when furniture fills most of the view.
    Estimating it per frame absorbs the scale error of the depth model (a -10 % scale would otherwise
    turn every floor pixel into an "obstacle" 0.16 m above a fixed 1.576 m floor). The candidate must
    look like a horizontal plane: the pixels at that level have to spread over at least 0.5 m of forward
    distance (a wall or cabinet face at one Zw fails this). Otherwise, or outside FLOOR_RANGE_M, fall back
    to the AI2-THOR camera height.
    """
    h = yw.shape[0]
    lower = np.zeros_like(valid)
    lower[h // 2 :, :] = True
    sel = valid & lower
    if sel.sum() >= MIN_OBSTACLE_PIXELS:
        d = float(np.percentile(yw[sel], percentile))
        if FLOOR_RANGE_M[0] <= d <= FLOOR_RANGE_M[1]:
            band = sel & (np.abs(yw - d) <= 0.05)
            if band.sum() >= MIN_OBSTACLE_PIXELS:
                z = zw[band]
                if float(np.percentile(z, 95) - np.percentile(z, 5)) >= 0.5:
                    return d, True
    return CAMERA_HEIGHT_M, False


def ground_region(h: int, w: int, focal: float, cy: float, pitch_deg: float) -> np.ndarray:
    """Rows below the horizon: the "lower half of the image" at a level camera, and the same
    physical region (everything from the horizon down) when the camera is tilted. Row of the horizon =
    cy - focal * tan(pitch); at pitch 0 this is exactly the lower half."""
    horizon_row = cy - focal * math.tan(math.radians(pitch_deg))
    start = int(math.ceil(max(min(horizon_row, h - 1), 0)))
    if pitch_deg == 0:
        start = h // 2
    mask = np.zeros((h, w), dtype=bool)
    mask[start:, :] = True
    return mask


@dataclass
class FrameGeometry:
    """Everything the fact builder needs from one depth map."""

    floor_depth_m: float
    floor_from_data: bool
    sector_free_m: dict  # sector name -> free forward distance in metres (inf = nothing seen)
    forward_blocked: bool  # an obstacle stands inside the 0.25 m step corridor
    forward_blocking_pixels: int
    near_floor_visible: (
        bool  # floor points were seen inside the step corridor (only after a LookDown at 1.576 m camera height)
    )
    xw: np.ndarray
    zw: np.ndarray
    valid: np.ndarray

    def target_range_m(self, box: tuple[float, float, float, float]) -> float | None:
        """Median horizontal distance to the inner half of a detection box (x0, y0, x1, y1 in pixels)."""
        x0, y0, x1, y1 = box
        w, h = max(x1 - x0, 1.0), max(y1 - y0, 1.0)
        cx0, cx1 = x0 + 0.25 * w, x1 - 0.25 * w
        cy0, cy1 = y0 + 0.25 * h, y1 - 0.25 * h
        r0, r1 = int(math.floor(cy0)), int(math.ceil(cy1))
        c0, c1 = int(math.floor(cx0)), int(math.ceil(cx1))
        r0, c0 = max(r0, 0), max(c0, 0)
        r1, c1 = min(r1, self.valid.shape[0] - 1), min(c1, self.valid.shape[1] - 1)
        if r1 < r0 or c1 < c0:
            return None
        sel = self.valid[r0 : r1 + 1, c0 : c1 + 1]
        if sel.sum() == 0:
            return None
        xw = self.xw[r0 : r1 + 1, c0 : c1 + 1][sel]
        zw = self.zw[r0 : r1 + 1, c0 : c1 + 1][sel]
        return float(np.median(np.hypot(xw, zw)))


def analyze_depth(depth_m: np.ndarray, pitch_deg: float, fov_deg: float = FOV_DEG) -> FrameGeometry:
    """Turn a metric depth map (H x W, metres, camera Z) into free-space facts.

    * Points are back-projected with the known intrinsics (square frame, ``fov_deg``), gravity-aligned
      with the camera pitch, and measured against the floor level estimated from the lower half
      (90th percentile of Yw, see ``estimate_floor_depth``).
    * Obstacle = point between OBSTACLE_MIN_HEIGHT_M and OBSTACLE_MAX_HEIGHT_M above the floor.
    * Sector table (lower half of the image, five horizontal sectors): free forward distance =
      5th percentile of Zw over the obstacle points of that sector in the ground region (the lower half
      at a level camera; everything below the horizon line when the camera is tilted), inf when fewer
      than MIN_OBSTACLE_PIXELS obstacle points are seen.
    * Forward step check: any obstacle points (all rows) inside the corridor
      |Xw| <= MOVE_STEP_M and 0 < Zw <= MOVE_STEP_M + AGENT_RADIUS_M block a 0.25 m move.
    """
    h, w = depth_m.shape
    focal = focal_px(w, fov_deg)
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    x, y, z = backproject(depth_m, focal, cx, cy)
    valid = np.isfinite(depth_m) & (depth_m > DEPTH_VALID_RANGE_M[0]) & (depth_m < DEPTH_VALID_RANGE_M[1])
    xw, yw, zw = gravity_align(x, y, z, pitch_deg)
    floor_d, from_data = estimate_floor_depth(yw, zw, valid)
    height = floor_d - yw
    obstacle = valid & (height > OBSTACLE_MIN_HEIGHT_M) & (height < OBSTACLE_MAX_HEIGHT_M) & (zw > 0)
    floor_pts = valid & (np.abs(height) <= OBSTACLE_MIN_HEIGHT_M)

    lower = ground_region(h, w, focal, cy, pitch_deg)
    sector_free = {}
    edges = np.linspace(0, w, len(SECTOR_NAMES) + 1).astype(int)
    for i, name in enumerate(SECTOR_NAMES):
        cols = np.zeros_like(valid)
        cols[:, edges[i] : edges[i + 1]] = True
        sel = obstacle & lower & cols
        n = int(sel.sum())
        sector_free[name] = float(np.percentile(zw[sel], 5)) if n >= MIN_OBSTACLE_PIXELS else math.inf

    in_corridor = (np.abs(xw) <= MOVE_STEP_M) & (zw <= MOVE_STEP_M + AGENT_RADIUS_M) & (zw > 0)
    corridor = obstacle & in_corridor
    n_block = int(corridor.sum())
    near_floor = int((floor_pts & in_corridor).sum()) >= MIN_OBSTACLE_PIXELS
    return FrameGeometry(
        floor_depth_m=floor_d,
        floor_from_data=from_data,
        sector_free_m=sector_free,
        forward_blocked=n_block >= MIN_OBSTACLE_PIXELS,
        forward_blocking_pixels=n_block,
        near_floor_visible=near_floor,
        xw=xw,
        zw=zw,
        valid=valid,
    )
