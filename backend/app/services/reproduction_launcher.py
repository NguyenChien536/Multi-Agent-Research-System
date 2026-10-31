"""Standalone launcher copied into a private experiment bundle (stdlib only)."""
import hashlib
import importlib.util
import json
import math
import platform
from pathlib import Path


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")


def scatter_svg(samples, residual=False):
    points = [(s["actual"], s["residual_ridge"] if residual else s["predicted_ridge"]) for s in samples]
    if not points or any(not isinstance(v, (int, float)) or not math.isfinite(v) for p in points for v in p):
        raise ValueError("Invalid measured chart data")
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    def scale(v, values, low, high):
        lo, hi = min(values), max(values)
        return (low + high) / 2 if hi == lo else low + (v - lo) / (hi - lo) * (high - low)
    ylabel = "Residual (actual - predicted)" if residual else "Predicted Ridge target"
    circles = "".join(f'<circle cx="{scale(x, xs, 75, 575):.3f}" cy="{scale(y, ys, 265, 40):.3f}" r="3" fill="#2563eb"/>' for x, y in points)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="650" height="330" role="img">'
            f'<title>{ylabel} versus actual; first {len(points)} held-out observations</title>'
            '<rect width="650" height="330" fill="white"/><path d="M65 30V275H590" fill="none" stroke="black"/>'
            f'{circles}<text x="270" y="322" font-size="14">Actual target</text>'
            f'<text x="70" y="18" font-size="14">{ylabel}</text>'
            f'<text x="65" y="298">{min(xs):.5g}</text><text x="540" y="298">{max(xs):.5g}</text>'
            f'<text x="2" y="48">{max(ys):.5g}</text><text x="2" y="268">{min(ys):.5g}</text></svg>')


def reproduce(root):
    manifest = json.loads((root / "bundle_manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["checksums"].items():
        if Path(name).name != name or name in {"", ".", ".."}:
            raise ValueError("Unsafe bundle entry")
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Integrity check failed: {name}")
    required = {"routine.py", "input.csv", "expected_result.json", "environment.json", "config.json"}
    if not required <= set(manifest["checksums"]):
        raise ValueError("Incomplete bundle integrity inventory")
    env = json.loads((root / "environment.json").read_text(encoding="utf-8"))
    if platform.python_version() != env["python_version"] or platform.python_implementation().lower() != env["implementation"]:
        raise ValueError(f"Use the recorded Python runtime: {env['implementation']} {env['python_version']}")
    spec = importlib.util.spec_from_file_location("frozen_routine", root / "routine.py")
    routine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(routine)
    dataset = (root / "input.csv").read_bytes().decode("utf-8")
    expected = json.loads((root / "expected_result.json").read_text(encoding="utf-8"))
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    if config != expected["manifest"]:
        raise ValueError("Config/result manifest mismatch")
    params = config["parameters"]
    result = routine.run_tabular_regression_v1(dataset, target_column=config["target_column"],
        feature_columns=config["feature_columns"], alpha=params["alpha"], test_size=params["test_size"], seed=params["seed"])
    differences = {}
    metric_checks = {}
    for group in ("baseline", "model"):
        for metric in ("mae", "rmse", "r2"):
            actual, previous = result["raw_metrics"][group][metric], expected["raw_metrics"][group][metric]
            name = f"{group}.{metric}"
            differences[name] = abs(actual - previous)
            metric_checks[name] = math.isfinite(actual) and math.isfinite(previous) and math.isclose(actual, previous, rel_tol=1e-6, abs_tol=1e-8)
    checks = {"raw_metrics_within_tolerance": all(metric_checks.values()), "manifest_matches": result["manifest"] == config,
              "chart_data_matches": result["chart_data"] == expected["chart_data"],
              "outcome_matches": result["verdict"] == expected["verdict"]}
    output = root / "reproduced"
    output.mkdir(exist_ok=True)
    write_json(output / "result.json", result)
    write_json(output / "comparison.json", {"passed": all(checks.values()), "checks": checks,
        "metric_differences": differences, "absolute_tolerance": 1e-8, "relative_tolerance": 1e-6})
    for name, residual in (("predicted-vs-actual.svg", False), ("residuals.svg", True)):
        (output / name).write_text(scatter_svg(result["chart_data"]["samples"], residual), encoding="utf-8")
    return all(checks.values())


if __name__ == "__main__":
    try:
        passed = reproduce(Path(__file__).resolve().parent)
        print("Replay PASSED" if passed else "Replay FAILED: see reproduced/comparison.json")
        raise SystemExit(0 if passed else 1)
    except Exception as exc:
        # A failed retry must not leave a previous comparison marked PASSED.
        try:
            output = Path(__file__).resolve().parent / "reproduced"
            output.mkdir(exist_ok=True)
            write_json(output / "comparison.json", {"passed": False, "execution_status": "FAILED",
                "error_type": type(exc).__name__, "error": str(exc)})
        except OSError:
            print("Could not save the failed attempt; any existing output belongs to an earlier attempt.")
        print(f"Replay could not complete: {type(exc).__name__}: {exc}")
        raise SystemExit(2)
