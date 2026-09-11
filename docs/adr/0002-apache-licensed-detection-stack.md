# ADR 0002 — The detection stack must be Apache-2.0 or MIT end to end

**Status:** Accepted
**Date:** 2026-07-09
**Supersedes:** the prototype's use of `ultralytics` (YOLOv8n) in `mar-vision/`

## Context

The original prototype and the product specification both name YOLO11 / YOLOv8
via the `ultralytics` Python package. That package is licensed **AGPL-3.0**.

AGPL-3.0 §13 (the network clause) states that if you modify the program and let
users interact with it *remotely over a network*, you must offer those users the
Corresponding Source of your modified version. MANSOUR Vision is, by definition,
a networked command center. Under AGPL, shipping it to a customer would oblige us
to release the source of the entire platform — the API, the dashboard, the alert
engine — to every operator who logs in.

That is incompatible with selling proprietary software to government agencies.
The obligation is triggered by *use over a network*, not by distribution, so
"we host it, we never ship a binary" is not a defense. It is the exact case the
clause was written to cover.

### The subtle trap

The *model architecture* and the *package that implements it* have different
licenses, and only the package's license binds us.

| Thing | License | Safe? |
|---|---|---|
| RT-DETR / RT-DETRv2 architecture + official weights (`lyuwenyu/RT-DETR`) | Apache-2.0 | ✅ |
| `ultralytics.RTDETR` — the same architecture, inside the ultralytics package | **AGPL-3.0** | ❌ |
| ByteTrack algorithm + original repo (`ifzhang/ByteTrack`) | MIT | ✅ |
| `ultralytics`' bundled ByteTrack implementation | **AGPL-3.0** | ❌ |
| `supervision` (Roboflow) — includes a ByteTrack implementation | MIT | ✅ |
| `boxmot` | AGPL-3.0 | ❌ |
| OpenCV, ONNX Runtime, NumPy, PyTorch | Apache-2.0 / MIT / BSD | ✅ |

Importing `ultralytics` for *any* purpose — even just to export weights to ONNX —
brings the AGPL obligation with it. The license attaches to the package, not to
the tensor it produces.

## Decision

1. **The detector is RT-DETRv2** (Apache-2.0), taken from the official
   `lyuwenyu/RT-DETR` release, with our own inference code. **D-FINE**
   (Apache-2.0) is the designated upgrade path; both export to ONNX.
2. **Tracking is ByteTrack** via `supervision` (MIT), or a vendored port of the
   original MIT implementation.
3. **`ultralytics` must never appear in a production dependency manifest.** This
   is enforced in CI by a license-scanning gate (`pip-licenses`, deny-list on
   AGPL/GPL/SSPL), not by convention.
4. The detector sits behind a `Detector` interface in `vision-worker`, so the
   model can be replaced without touching the tracking, zone, or event layers.

## Consequences

**Positive.**
- No copyleft obligation, no commercial license fee, no procurement blocker.
- RT-DETRv2 is **NMS-free**. In dense crowds — our primary workload — NMS is a
  significant source of missed detections, because it suppresses genuinely
  overlapping people. Removing it is an accuracy win, not just a license win.
- No NMS also means a clean, single-output ONNX graph, which simplifies the
  TensorRT path in ADR 0005.

**Negative.**
- We lose ultralytics' extremely convenient `model.track(persist=True)` API. The
  detector→tracker glue that the prototype got for free must now be written and
  tested by us. Budgeted in Milestone 2.
- Ultralytics' training/export tooling is more mature. If we later pursue the
  custom-dataset track, we need our own training harness.
- The prototype's `detector.py` cannot be lifted verbatim. Its *geometry*
  (line crossing, side tests) and *state machine* (track lifecycle, staleness)
  are license-clean original work and are retained; only the model call changes.

## Compliance note for reviewers

No component of the production image is licensed under AGPL, GPL, or SSPL. The
CI license gate produces an SBOM (CycloneDX) per build; it is the artifact to
hand to a procurement legal review.
