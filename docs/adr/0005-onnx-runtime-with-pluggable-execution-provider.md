# ADR 0005 — ONNX Runtime with a pluggable execution provider

**Status:** Accepted
**Date:** 2026-07-09

## Context

Production hardware is not yet procured. The platform must run today on a
developer laptop (CPU), tomorrow on whatever GPU is bought, and eventually on a
TensorRT-optimized deployment — without a rewrite, and without the capacity
question being answered by guesswork.

The specification says "unlimited cameras." No system is unlimited. The claim we
can defend, and that a buyer can plan against, is *horizontally scalable, with a
published and measured per-GPU capacity*.

## Decision

**Inference goes through ONNX Runtime behind a `Detector` interface**, with the
execution provider selected by configuration:

| Target | Execution provider | Status |
|---|---|---|
| Laptop / CI | `CPUExecutionProvider` | v1 |
| NVIDIA GPU | `CUDAExecutionProvider` | v1 |
| NVIDIA GPU, optimized | `TensorrtExecutionProvider` | post-benchmark |

RT-DETRv2 (ADR 0002) is NMS-free, so it exports to a single-output ONNX graph
with no custom operators — which is exactly the condition under which the
TensorRT provider works without hand-written plugins. The license decision and
the deployment decision reinforce each other here.

### Analytic FPS is decoupled from stream FPS

Crowd counting, density, and line crossing do **not** require 30 FPS. ByteTrack
bridges skipped frames, and a crossing is decided from a track's centroid history
rather than from every frame — the prototype already relies on this. We therefore
run inference at a configurable **analytic FPS** (default 10), independent of the
camera's native rate. This is the single largest lever on capacity, and it costs
essentially no accuracy on this workload.

### Capacity is measured, not asserted

`ops/benchmarks/` contains a harness that, for a given host, reports the sustained
camera count at a target analytic FPS, and — critically — **which stage is the
bottleneck**. The working hypothesis, to be confirmed rather than assumed:

> At 10 analytic FPS on 1080p H.264 streams, the ceiling is **NVDEC video decode,
> not inference.** A single RTX 4090 is expected to sustain roughly 25–40 cameras.

If that holds, buying a bigger GPU for *inference* is the wrong purchase, and the
architecture should decode on dedicated hardware or downscale before decode. We
will not know until we measure. **No capacity number appears in a proposal to a
customer until it comes out of this harness on their hardware.**

## Consequences

- A single `Detector` implementation serves CPU dev, GPU staging, and TensorRT
  production. Execution provider is one environment variable.
- The `vision-worker` is stateless and GPU-pinned; capacity scales by adding
  workers. Cameras are assigned to workers by a scheduler in `core-api`.
- Batched inference across cameras within a worker is possible because all
  streams are resized to a common inference resolution. This is a meaningful
  throughput win on GPU and is why cameras are grouped per worker rather than
  given one process each.
- We accept slightly worse ergonomics than a native PyTorch path, and the need to
  re-validate numerics after every export (an ONNX export test with a fixed input
  and a tolerance assertion is part of the model CI).
- The prototype's adaptive frame-skip heuristic (`MIN_FPS`, 5 s dwell,
  warm-up exclusion) is retained in concept: it is a good idea and it was already
  tuned to not oscillate. It becomes a property of the worker's scheduler.
