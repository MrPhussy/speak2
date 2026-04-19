#!/usr/bin/env python3
"""
RunPod REST helpers: create a Serverless worker template + GPU endpoint for **speak2 / Unmute**
(all-in-one Traefik :80). See ../docs/runpod-testing.md — validate on a **Pod** first when possible.

Requires ``RUNPOD_API_KEY``. Uses ``https://rest.runpod.io/v1``.

This sets **flashboot: true** on the endpoint (same idea as Speak CleanS2S). Tune **CUDA** strings
to match your GPU lines in the RunPod UI if the API rejects them.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

API_BASE = os.environ.get("RUNPOD_REST_URL", "https://rest.runpod.io/v1").rstrip("/")

DEFAULT_GPU = os.environ.get(
    "RUNPOD_GPU_TYPE",
    "NVIDIA RTX PRO 6000 Blackwell Server Edition",
)
# Traefik serves Metis/Unmute UI on 80 inside the container.
DEFAULT_PORTS = ["80/http"]
_dcs = os.environ.get("RUNPOD_DATA_CENTERS", "").strip()
DEFAULT_DATA_CENTERS = (
    [x.strip() for x in _dcs.split(",") if x.strip()]
    if _dcs
    else ["US-WA-1", "US-TX-3"]
)
# Image uses CUDA 12.x PyTorch wheels (see Dockerfile backend-builder).
DEFAULT_CUDA_VERSIONS = os.environ.get("RUNPOD_UNMUTE_CUDA_VERSIONS", "12.8").split(",")
DEFAULT_CUDA_VERSIONS = [x.strip() for x in DEFAULT_CUDA_VERSIONS if x.strip()]


def _api_key() -> str:
    k = os.environ.get("RUNPOD_API_KEY", "").strip()
    if not k:
        print("ERROR: set RUNPOD_API_KEY", file=sys.stderr)
        raise SystemExit(2)
    return k


def _request(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    url = f"{API_BASE}{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code} {method} {path}: {err}", file=sys.stderr)
        raise SystemExit(1) from e
    if not raw:
        return None
    return json.loads(raw)


def _default_template_env() -> dict[str, str]:
    env: dict[str, str] = {
        "PORT": "80",
        "PORT_HEALTH": "80",
        "HUGGING_FACE_HUB_TOKEN": os.environ.get("HUGGING_FACE_HUB_TOKEN", ""),
        "KYUTAI_LLM_API_KEY": os.environ.get("KYUTAI_LLM_API_KEY", ""),
        "KYUTAI_LLM_URL": os.environ.get("KYUTAI_LLM_URL", "https://api.inceptionlabs.ai"),
        "KYUTAI_LLM_MODEL": os.environ.get("KYUTAI_LLM_MODEL", "mercury-2"),
        "KYUTAI_STT_URL": os.environ.get("KYUTAI_STT_URL", "ws://127.0.0.1:8091"),
        "KYUTAI_TTS_URL": os.environ.get("KYUTAI_TTS_URL", "ws://127.0.0.1:8092"),
    }
    # Strip empties — RunPod may reject keys with empty values.
    return {k: v for k, v in env.items() if v}


def cmd_create_template(ns: argparse.Namespace) -> str | None:
    image = ns.image or os.environ.get("RUNPOD_IMAGE_NAME", "").strip()
    if not image:
        print("ERROR: pass --image or set RUNPOD_IMAGE_NAME", file=sys.stderr)
        raise SystemExit(2)
    body: dict[str, Any] = {
        "name": ns.name,
        "imageName": image,
        "isServerless": True,
        "category": "NVIDIA",
        "containerDiskInGb": ns.container_disk_gb,
        "ports": DEFAULT_PORTS,
        "env": _default_template_env(),
    }
    if ns.registry_auth_id:
        body["containerRegistryAuthId"] = ns.registry_auth_id
    out = _request("POST", "/templates", body)
    print(json.dumps(out, indent=2))
    tid = out.get("id") if isinstance(out, dict) else None
    if tid:
        print(f"\nexport RUNPOD_TEMPLATE_ID={tid}", flush=True)
    return str(tid) if tid else None


def cmd_create_endpoint(ns: argparse.Namespace) -> None:
    tid = ns.template_id or os.environ.get("RUNPOD_TEMPLATE_ID", "").strip()
    if not tid:
        print("ERROR: pass --template-id or set RUNPOD_TEMPLATE_ID", file=sys.stderr)
        raise SystemExit(2)
    dcs = ns.data_centers or os.environ.get("RUNPOD_DATA_CENTERS", "")
    data_center_ids = [x.strip() for x in dcs.split(",") if x.strip()] or list(DEFAULT_DATA_CENTERS)
    min_cuda = DEFAULT_CUDA_VERSIONS[0] if DEFAULT_CUDA_VERSIONS else "12.8"
    body: dict[str, Any] = {
        "name": ns.name,
        "templateId": tid,
        "gpuTypeIds": [ns.gpu_type],
        "gpuCount": 1,
        "workersMin": ns.workers_min,
        "workersMax": ns.workers_max,
        "flashboot": True,
        "allowedCudaVersions": DEFAULT_CUDA_VERSIONS,
        "minCudaVersion": min_cuda,
        "dataCenterIds": data_center_ids,
        "idleTimeout": ns.idle_timeout,
        "scalerType": "QUEUE_DELAY",
        "scalerValue": ns.scaler_value,
    }
    out = _request("POST", "/endpoints", body)
    print(json.dumps(out, indent=2))


def cmd_create_all(ns: argparse.Namespace) -> None:
    t_ns = argparse.Namespace(
        name=ns.template_name,
        image=ns.image or os.environ.get("RUNPOD_IMAGE_NAME", "").strip(),
        container_disk_gb=ns.container_disk_gb,
        registry_auth_id=ns.registry_auth_id,
    )
    tid = cmd_create_template(t_ns)
    if not tid:
        print("ERROR: create-template response missing id", file=sys.stderr)
        raise SystemExit(1)
    e_ns = argparse.Namespace(
        name=ns.endpoint_name,
        template_id=tid,
        gpu_type=ns.gpu_type,
        workers_min=ns.workers_min,
        workers_max=ns.workers_max,
        idle_timeout=ns.idle_timeout,
        scaler_value=ns.scaler_value,
        data_centers=ns.data_centers,
    )
    cmd_create_endpoint(e_ns)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("create-template", help="POST /templates (serverless worker)")
    t.add_argument("--name", default=os.environ.get("RUNPOD_TEMPLATE_NAME", "speak2-unmute"))
    t.add_argument("--image", default="", help="Container image (or RUNPOD_IMAGE_NAME)")
    t.add_argument("--container-disk-gb", type=int, default=80)
    t.add_argument("--registry-auth-id", default=os.environ.get("RUNPOD_REGISTRY_AUTH_ID", ""))
    t.set_defaults(func=cmd_create_template)

    e = sub.add_parser("create-endpoint", help="POST /endpoints (GPU + scaling)")
    e.add_argument("--name", default=os.environ.get("RUNPOD_ENDPOINT_NAME", "speak2-unmute"))
    e.add_argument("--template-id", default="")
    e.add_argument("--gpu-type", default=DEFAULT_GPU)
    e.add_argument("--workers-min", type=int, default=int(os.environ.get("RUNPOD_WORKERS_MIN", "0")))
    e.add_argument("--workers-max", type=int, default=int(os.environ.get("RUNPOD_WORKERS_MAX", "3")))
    e.add_argument("--idle-timeout", type=int, default=int(os.environ.get("RUNPOD_IDLE_TIMEOUT", "300")))
    e.add_argument(
        "--scaler-value",
        type=int,
        default=int(os.environ.get("RUNPOD_SCALER_VALUE", "30")),
    )
    e.add_argument(
        "--data-centers",
        default="",
        help="Comma-separated RunPod data center ids (or RUNPOD_DATA_CENTERS)",
    )
    e.set_defaults(func=cmd_create_endpoint)

    a = sub.add_parser("create-all", help="create-template then create-endpoint")
    a.add_argument("--template-name", default=os.environ.get("RUNPOD_TEMPLATE_NAME", "speak2-unmute"))
    a.add_argument("--endpoint-name", default=os.environ.get("RUNPOD_ENDPOINT_NAME", "speak2-unmute"))
    a.add_argument("--image", default="", help="Container image (or RUNPOD_IMAGE_NAME)")
    a.add_argument("--container-disk-gb", type=int, default=80)
    a.add_argument("--registry-auth-id", default=os.environ.get("RUNPOD_REGISTRY_AUTH_ID", ""))
    a.add_argument("--gpu-type", default=DEFAULT_GPU)
    a.add_argument("--workers-min", type=int, default=int(os.environ.get("RUNPOD_WORKERS_MIN", "0")))
    a.add_argument("--workers-max", type=int, default=int(os.environ.get("RUNPOD_WORKERS_MAX", "3")))
    a.add_argument("--idle-timeout", type=int, default=int(os.environ.get("RUNPOD_IDLE_TIMEOUT", "300")))
    a.add_argument(
        "--scaler-value",
        type=int,
        default=int(os.environ.get("RUNPOD_SCALER_VALUE", "30")),
    )
    a.add_argument("--data-centers", default="")
    a.set_defaults(func=cmd_create_all)

    ns = ap.parse_args()
    if ns.cmd == "create-template":
        cmd_create_template(ns)
    elif ns.cmd == "create-endpoint":
        cmd_create_endpoint(ns)
    else:
        cmd_create_all(ns)


if __name__ == "__main__":
    main()
