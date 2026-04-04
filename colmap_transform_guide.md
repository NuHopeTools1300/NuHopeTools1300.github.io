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
