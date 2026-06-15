import statistics
from html import escape
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
import tifffile

from startrail_pipeline.config import read_config
from startrail_pipeline.manifest import read_manifest, write_manifest
from startrail_pipeline.commands.preview_ import proxy_path


def _proxy_path(project_path, rel_path):
    return proxy_path(project_path, rel_path)


def _load_analysis_image(path, proxy_size):
    if path.suffix.lower() in {".tif", ".tiff"}:
        arr = tifffile.imread(str(path))
        if arr.ndim == 2:
            arr = np.stack([arr] * 3, axis=-1)
        if arr.shape[-1] > 3:
            arr = arr[:, :, :3]
        if arr.dtype == np.uint8:
            arr = arr.astype(np.uint16) * 257
        elif arr.dtype != np.uint16:
            raise ValueError(f"{path}: unsupported pixel type {arr.dtype}")
        scale = min(1.0, proxy_size / max(arr.shape[:2]))
        if scale < 1.0:
            preview = Image.fromarray((arr >> 8).astype(np.uint8), "RGB")
            preview.thumbnail((proxy_size, proxy_size), Image.LANCZOS)
            arr = np.asarray(preview, dtype=np.uint16) * 257
        return arr
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    img.thumbnail((proxy_size, proxy_size), Image.LANCZOS)
    return np.asarray(img, dtype=np.uint16) * 257


def _compute_metrics(img_array):
    metrics = {}
    gray = np.mean(img_array, axis=2) if img_array.ndim == 3 else img_array
    metrics["median_luminance"] = float(np.median(gray))
    metrics["mean_luminance"] = float(np.mean(gray))
    high_percentile = np.percentile(gray, 99)
    metrics["p99_luminance"] = float(high_percentile)
    clipped_high = np.sum(gray >= 65535 * 0.999)
    metrics["clipped_ratio"] = float(clipped_high / gray.size)
    lap = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
    laplacian = np.abs(
        np.sum(
            np.lib.stride_tricks.sliding_window_view(gray.astype(np.float32), (3, 3))
            * lap,
            axis=(2, 3),
        )
    )
    metrics["sharpness"] = float(np.mean(laplacian))
    return metrics


def _detect_anomalies(metrics_list, config):
    mad_mult_low = config["analysis"]["mad_multiplier_low"]
    mad_mult_high = config["analysis"]["mad_multiplier_high"]

    keys = ["median_luminance", "clipped_ratio", "sharpness"]
    results = []
    for i, m in enumerate(metrics_list):
        results.append({"index": i, "anomalies": [], **m})

    for key in keys:
        values = [m[key] for m in metrics_list]
        if len(values) < 3:
            continue
        median = statistics.median(values)
        abs_devs = [abs(v - median) for v in values]
        mad = statistics.median(abs_devs) if abs_devs else 0
        if mad == 0:
            mad = max((v for v in abs_devs if v > 0), default=0) or 1
        for rec, val in zip(results, values):
            signed_deviation = (val - median) / mad if mad else 0
            severity = (
                "severe"
                if abs(signed_deviation) > mad_mult_high
                else "moderate"
            )
            if abs(signed_deviation) <= mad_mult_low:
                continue
            if key == "sharpness" and signed_deviation < 0:
                rec["anomalies"].append(f"sharpness_low_{severity}")
            elif key == "median_luminance":
                direction = "high" if signed_deviation > 0 else "low"
                rec["anomalies"].append(
                    f"median_luminance_{direction}_{severity}"
                )
            elif key == "clipped_ratio" and signed_deviation > 0:
                rec["anomalies"].append(f"clipped_ratio_high_{severity}")

    return results


def _generate_contact_sheet(results, manifests_dir):
    html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Contact Sheet</title>
<style>
body { font-family: sans-serif; margin: 20px; }
table { border-collapse: collapse; }
td, th { border: 1px solid #ccc; padding: 8px; text-align: center; }
.keep { background: #d4edda; }
.review { background: #fff3cd; }
.reject { background: #f8d7da; }
</style></head><body>
<h1>Frame Analysis</h1>
<table><tr>
<th>#</th><th>Preview</th><th>File</th><th>Median</th><th>Clipped</th><th>Sharpness</th><th>Anomalies</th>
</tr>
"""
    for r in results:
        cls = "keep"
        if r.get("anomalies"):
            cls = "review"
        proxy = r.get("proxy_relative_path")
        preview = (
            f'<img src="../proxies/{escape(proxy)}" loading="lazy" width="240">'
            if proxy
            else "Unavailable"
        )
        html += (
            f'<tr class="{cls}">'
            f'<td>{r["index"]}</td>'
            f"<td>{preview}</td>"
            f'<td>{escape(Path(r.get("path", "")).name)}</td>'
            f'<td>{r["median_luminance"]:.1f}</td>'
            f'<td>{r["clipped_ratio"]:.4f}</td>'
            f'<td>{r["sharpness"]:.1f}</td>'
            f'<td>{escape(", ".join(r.get("anomalies", [])))}</td>'
            f"</tr>\n"
        )
    html += "</table></body></html>"
    contact_path = manifests_dir / "contact_sheet.html"
    with open(contact_path, "w") as f:
        f.write(html)
    return contact_path


def cmd_analyze(args, log):
    inventory = read_manifest(args.project, "inventory")
    if not inventory:
        log.warning("No inventory found. Run 'inventory' first.")
        return

    config = read_config(args.project)
    proxy_size = config["analysis"]["proxy_size"]

    manifests_dir = args.project / "manifests"

    metrics_list = []
    for rec in inventory:
        path = Path(rec["path"])
        if not path.exists():
            log.warning(f"File not found: {path}")
            continue
        ext = rec.get("extension", path.suffix.lower())
        analysis_proxy = _proxy_path(args.project, rec["relative_path"])
        if analysis_proxy.exists():
            arr = _load_analysis_image(analysis_proxy, proxy_size)
        elif ext in config["extensions"]["raw"]:
            if not analysis_proxy.exists():
                log.info(f"No proxy for RAW {path.name}, using fallback metrics")
                metrics_list.append({
                    "path": str(path),
                    "relative_path": rec["relative_path"],
                    "median_luminance": 0,
                    "mean_luminance": 0,
                    "p99_luminance": 0,
                    "clipped_ratio": 0,
                    "sharpness": 0,
                    "pre_anomalies": ["proxy_missing"],
                })
                continue
        else:
            try:
                arr = _load_analysis_image(path, proxy_size)
            except Exception as e:
                log.warning(f"Cannot open {path}: {e}")
                continue

        metrics = _compute_metrics(arr)
        metrics["path"] = str(path)
        metrics["relative_path"] = rec["relative_path"]
        metrics["proxy_relative_path"] = str(
            analysis_proxy.relative_to(args.project / "proxies")
        )
        metrics_list.append(metrics)

    results = _detect_anomalies(metrics_list, config)
    for source, result in zip(metrics_list, results):
        result["anomalies"] = source.get("pre_anomalies", []) + result["anomalies"]

    contact_path = _generate_contact_sheet(results, manifests_dir)
    write_manifest(args.project, "analysis", results)
    log.info(
        f"Analyzed {len(results)} frames, anomalies: "
        f"{sum(1 for r in results if r['anomalies'])}"
    )
    log.info(f"Contact sheet: {contact_path}")
