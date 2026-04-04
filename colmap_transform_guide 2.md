# COLMAP: Applying a Blender Transform to a Reconstruction

## Background

When you align a COLMAP model to a reference in Blender, you need to apply the same similarity transform (rotation + translation + scale) back to the COLMAP text files so the reconstruction matches the aligned coordinate system.

---

## Which Files Need Updating?

| File | Needs Updating? | Why |
|---|---|---|
| `cameras.txt` | ❌ No | Contains intrinsics only (focal length, cx, cy, distortion) — independent of world position |
| `images.txt` | ✅ Yes | Camera poses (R, t) are defined in world space |
| `points3D.txt` | ✅ Yes | 3D point positions are in world space |

The 2D point observations (pixel coordinates) on the second line of each image entry in `images.txt` are also **unchanged** — they are pixel coordinates, not world coordinates.

---

## What COLMAP's Text Files Store

### `images.txt`
Each image entry (first line):
```
IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME
```
- `QW, QX, QY, QZ` — quaternion rotation (**world-to-camera**, not camera-to-world)
- `TX, TY, TZ` — translation (**world-to-camera**)

### `points3D.txt`
```
POINT3D_ID, X, Y, Z, R, G, B, ERROR, TRACK[]
```
- `X, Y, Z` — 3D point position in world space

---

## The Transform

A similarity transform consists of:
- **R** — rotation matrix (3×3)
- **t** — translation vector (3×1)
- **s** — uniform scale (scalar)

To transform a point from old to new world space:
```
P_new = s * R @ P_old + t
```

---

## Step-by-Step Guide

### Step 1 — Export the Transform Matrix from Blender

In Blender, select your aligned object and open the **Python Console** (Scripting tab):

```python
import bpy
import numpy as np

obj = bpy.context.active_object
M = np.array(obj.matrix_world)
print(M)
```

Copy the printed 4×4 matrix output.

> **Note:** Make sure this is the transform applied to the COLMAP model object, representing how it was moved to match your reference.

---

### Step 2 — Decompose the Matrix into R, t, s

```python
import numpy as np

# Paste your matrix from Blender here
M = np.array([
    [1, 0, 0, 0],   # replace with your values
    [0, 1, 0, 0],
    [0, 0, 1, 0],
    [0, 0, 0, 1]
])

# Extract scale (length of each column vector of the upper 3x3)
sx = np.linalg.norm(M[:3, 0])
sy = np.linalg.norm(M[:3, 1])
sz = np.linalg.norm(M[:3, 2])

# Check for uniform scale (required for a valid similarity transform)
print(f"Scale per axis: x={sx:.6f}, y={sy:.6f}, z={sz:.6f}")
if not np.allclose([sx, sy, sz], sx, atol=1e-4):
    print("WARNING: Non-uniform scale detected! COLMAP requires uniform scale.")

s = sx  # use uniform scale

# Extract pure rotation matrix (normalize columns)
R = M[:3, :3] / s

# Verify R is a valid rotation matrix (determinant should be +1)
print(f"Rotation matrix determinant: {np.linalg.det(R):.6f}  (should be +1.0)")

# Extract translation
t = M[:3, 3]

print(f"\nScale: {s}")
print(f"Translation: {t}")
print(f"Rotation matrix:\n{R}")
```

---

### Step 3 — Convert Coordinate Systems (Blender → COLMAP)

> ⚠️ This is the most common source of error.

| System | Axes |
|---|---|
| **COLMAP** | X right, Y down, Z forward |
| **Blender** | X right, Y forward, Z up |

Apply the conversion:

```python
# Blender to COLMAP coordinate conversion matrix
T_bl2col = np.array([
    [1,  0,  0],
    [0,  0,  1],
    [0, -1,  0]
])

# Convert rotation and translation to COLMAP coordinate system
R_colmap = T_bl2col @ R @ T_bl2col.T
t_colmap = T_bl2col @ t
```

---

### Step 4 — Run the Transform Script

Save as `transform_colmap.py` and run with `python transform_colmap.py`:

```python
import numpy as np
from scipy.spatial.transform import Rotation

# ── Paste your values from Steps 2 & 3 ──────────────────────────────────
R = R_colmap   # from Step 3
t = t_colmap   # from Step 3
s = s          # from Step 2

# ── Helper functions ─────────────────────────────────────────────────────

def quat_to_rotmat(qw, qx, qy, qz):
    # scipy uses (x, y, z, w) order
    return Rotation.from_quat([qx, qy, qz, qw]).as_matrix()

def rotmat_to_quat(mat):
    r = Rotation.from_matrix(mat)
    x, y, z, w = r.as_quat()
    return w, x, y, z  # back to COLMAP wxyz order

# ── Transform points3D.txt ───────────────────────────────────────────────

def transform_points3D(input_path, output_path, R, t, s):
    with open(input_path, 'r') as f:
        lines = f.readlines()

    out = []
    for line in lines:
        if line.startswith('#') or line.strip() == '':
            out.append(line)
            continue

        parts = line.strip().split()
        pid = parts[0]
        xyz = np.array([float(parts[1]), float(parts[2]), float(parts[3])])
        rest = parts[4:]  # R G B ERROR TRACK...

        xyz_new = s * R @ xyz + t

        out.append(
            f"{pid} {xyz_new[0]:.6f} {xyz_new[1]:.6f} {xyz_new[2]:.6f}"
            f" {' '.join(rest)}\n"
        )

    with open(output_path, 'w') as f:
        f.writelines(out)
    print(f"✓ points3D written to {output_path}")

# ── Transform images.txt ─────────────────────────────────────────────────

def transform_images(input_path, output_path, R, t, s):
    with open(input_path, 'r') as f:
        lines = f.readlines()

    out = []
    i = 0
    while i < len(lines):
        line = lines[i]

        if line.startswith('#') or line.strip() == '':
            out.append(line)
            i += 1
            continue

        parts = line.strip().split()
        img_id = parts[0]
        qw = float(parts[1]); qx = float(parts[2])
        qy = float(parts[3]); qz = float(parts[4])
        tx = float(parts[5]); ty = float(parts[6]); tz = float(parts[7])
        rest = parts[8:]  # CAMERA_ID NAME

        R_cam = quat_to_rotmat(qw, qx, qy, qz)
        t_cam = np.array([tx, ty, tz])

        # Apply similarity transform to world-to-camera pose:
        # Original:     P_cam = R_cam @ P_world + t_cam
        # New world:    P_world_new = s * R @ P_world_old + t
        # Substituting: P_cam = (R_cam @ R.T) @ P_world_new
        #                       + (1/s) * (t_cam - R_cam @ R.T @ t)

        R_cam_new = R_cam @ R.T
        t_cam_new = (1.0 / s) * (t_cam - R_cam @ R.T @ t)

        qw_n, qx_n, qy_n, qz_n = rotmat_to_quat(R_cam_new)

        out.append(
            f"{img_id} {qw_n:.9f} {qx_n:.9f} {qy_n:.9f} {qz_n:.9f} "
            f"{t_cam_new[0]:.6f} {t_cam_new[1]:.6f} {t_cam_new[2]:.6f} "
            f"{' '.join(rest)}\n"
        )

        # Second line: 2D point observations — copy unchanged
        i += 1
        if i < len(lines):
            out.append(lines[i])
        i += 1

    with open(output_path, 'w') as f:
        f.writelines(out)
    print(f"✓ images written to {output_path}")

# ── Run ──────────────────────────────────────────────────────────────────

transform_points3D('points3D.txt',  'points3D_new.txt', R, t, s)
transform_images(  'images.txt',    'images_new.txt',   R, t, s)

print("\nDone. Verify in COLMAP GUI before using the new files.")
```

---

### Step 5 — Verify in COLMAP GUI

1. **Back up** your original files first
2. Replace originals with the `_new` versions
3. Open **COLMAP GUI → File → Import Model**
4. Check that:
   - Camera frustums point in the correct direction
   - Point cloud aligns with your reference
   - Scale looks correct

---

## Summary

| Step | Action |
|---|---|
| 1 | Export 4×4 transform matrix from Blender |
| 2 | Decompose into R, t, s — verify uniform scale |
| 3 | Convert coordinate system (Blender → COLMAP) |
| 4 | Run script on `images.txt` and `points3D.txt` |
| 5 | Verify result in COLMAP GUI |
| `cameras.txt` | Leave completely untouched ✅ |

---

---

# Registering Missing Images into an Existing Sparse Model

## Background

After sparse reconstruction, some images may fail to register — usually due to insufficient feature matches, blur, or poor overlap. These can be identified by comparing the images on disk against those listed in `images.txt`, and potentially re-registered using COLMAP's `image_registrator`.

---

## Two Categories of Missing Images

| Category | Meaning | Action needed |
|---|---|---|
| In `database.db`, not in `images.txt` | Features extracted but localization failed | Run `image_registrator` directly |
| Not in `database.db` either | Never processed | Feature extraction + matching first, then register |

---

## Script: `colmap_register_missing.py`

Handles both categories automatically.

**Just check (no changes made):**
```bash
python colmap_register_missing.py \
  --image_dir  /path/to/images \
  --model_dir  /path/to/sparse/0 \
  --database   /path/to/database.db \
  --output_dir /path/to/sparse/1
```

**Check + attempt registration:**
```bash
python colmap_register_missing.py \
  --image_dir  /path/to/images \
  --model_dir  /path/to/sparse/0 \
  --database   /path/to/database.db \
  --output_dir /path/to/sparse/1 \
  --register
```

### What the script does in order

1. **Checks** — compares disk images vs `images.txt` vs `database.db`
2. **Extracts features** — only for images not yet in the database
3. **Matches features** — connects new images to existing ones
4. **Registers** — uses COLMAP's `image_registrator` (PnP localization against existing 3D points)
5. **Reports** — shows which images were newly registered and which still failed

### If images still fail to register

Run `point_triangulator` then `bundle_adjuster` to consolidate the model:

```bash
colmap point_triangulator \
  --database_path database.db \
  --image_path    images/ \
  --input_path    sparse/1 \
  --output_path   sparse/1

colmap bundle_adjuster \
  --input_path  sparse/1 \
  --output_path sparse/1
```

---

---

# Constrained Bundle Adjustment with Fixed Reference Cameras

## Background

COLMAP's built-in CLI `bundle_adjuster` is all-or-nothing — it either refines all camera poses or none. To preserve the scale and rotation established by your Blender alignment (or surveyed reference images), you need to fix a **subset** of cameras while allowing the rest to be optimized. This requires `pycolmap`.

```bash
pip install pycolmap
```

---

## How Many Cameras to Fix?

In SfM, a reconstruction has **7 gauge freedoms** (3 rotation + 3 translation + 1 scale). Fixing 3 non-collinear cameras fully constrains all 7. Fewer than 3 and scale or rotation can still drift.

| Fixed cameras | Effect |
|---|---|
| 1 | Constrains translation only |
| 2 | Partial constraint |
| 3+ | Fully constrains scale + rotation + translation ✅ |

---

## Script: `colmap_constrained_ba.py`

**Fix specific reference cameras, refine everything else:**
```bash
python colmap_constrained_ba.py \
  --input_model  sparse/0 \
  --output_model sparse/1 \
  --reference    ref_001.jpg ref_002.jpg ref_003.jpg \
  --fix_intrinsics \
  --text_format
```

**Gauge-only mode** (fix just 3 cameras to lock scale+rotation, allow subtle refinement of all others):
```bash
python colmap_constrained_ba.py \
  --input_model  sparse/0 \
  --output_model sparse/1 \
  --reference    ref_A.jpg ref_B.jpg ref_C.jpg \
  --gauge_only
```

### Key options

| Flag | Effect |
|---|---|
| `--fix_intrinsics` | Also holds focal length, cx, cy fixed — recommended if well-calibrated |
| `--gauge_only` | Fixes only the first 3 reference cameras (minimum to constrain gauge) |
| `--max_iterations N` | Ceres solver iteration limit (default: 100) |
| `--text_format` | Saves output as text files instead of binary |

### Notes

- Uses a **Cauchy loss function** for robustness against outlier 3D points
- `--fix_intrinsics` is recommended after a good COLMAP calibration — otherwise BA can absorb errors into focal length
- Reference image names are matched on basename, so subdirectory prefixes are handled automatically

---

---

# Image Undistortion — Where It Fits in the Pipeline

## Full Pipeline Order

```
1. Feature extraction          → database.db
2. Feature matching            → database.db
3. Sparse reconstruction (SfM) → sparse/0/   ← transform + BA happen here
4. Image undistortion          → dense/0/images/  (undistorted images)
                                 dense/0/sparse/   (PINHOLE camera models)
5. Dense matching (MVS)        → dense/0/stereo/
6. Fusion                      → dense/0/fused.ply
7. Meshing (optional)          → dense/0/meshed.ply
```

## Why Undistortion Happens After Sparse

The sparse reconstruction works **with** distortion — COLMAP's feature matching and triangulation explicitly model lens distortion using the camera model (SIMPLE_RADIAL, OPENCV, etc.). Undistortion is only needed before **dense matching** (Step 5), because PatchMatch MVS assumes a pinhole camera with no distortion.

After undistortion, `dense/0/sparse/cameras.txt` contains a pure **PINHOLE** model with no distortion coefficients.

## Image Stages

| Stage | Images | Camera model |
|---|---|---|
| Sparse (SfM) | Original distorted | SIMPLE_RADIAL / OPENCV / etc. |
| After `image_undistorter` | Undistorted copies | PINHOLE (no distortion) |
| Dense (MVS) | Undistorted | PINHOLE |

## Important Implications

- Images displayed alongside your point cloud annotations should be the **undistorted** ones — they match the dense point cloud geometry exactly
- Apply your Blender transform + constrained BA to the **sparse model first**, then re-run undistortion afterward
- Never modify `cameras.txt` — distortion parameters must remain intact for the undistortion step to work correctly

## Running Undistortion

```bash
colmap image_undistorter \
  --image_path    images/ \
  --input_path    sparse/0 \
  --output_path   dense/0 \
  --output_type   COLMAP
```

Run this **after** your transform and constrained BA are complete.

---

## Recommended End-to-End Order for Your Project

| Step | Tool / Script |
|---|---|
| 1. Sparse reconstruction | COLMAP GUI or CLI |
| 2. Find missing images | `colmap_register_missing.py` |
| 3. Register missing images | `colmap_register_missing.py --register` |
| 4. Apply Blender transform | `transform_colmap.py` |
| 5. Constrained bundle adjustment | `colmap_constrained_ba.py` |
| 6. Undistortion | `colmap image_undistorter` |
| 7. Dense MVS + fusion | COLMAP GUI or CLI |
