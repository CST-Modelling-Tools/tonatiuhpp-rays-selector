import argparse
import csv
import math
import re
from pathlib import Path

import numpy as np


REQUIRED_COLUMNS = (
    "azimuth_center_deg",
    "elevation_center_deg",
    "zenith_center_deg",
    "ray_count",
    "power_W",
    "flux_W_m2",
)

SUMMARY_COLUMNS = (
    "time_label",
    "hour",
    "Radius_m",
    "TotalPower_W",
    "Top90SolidAngle_sr",
    "Top90HemispherePercent",
    "Top90BinCount",
    "TotalBinCount",
    "MaxFlux_W_m2",
    "Az_max_flux_deg",
    "El_max_flux_deg",
)

DEFAULT_RADII = (25.0, 50.0, 100.0, 200.0, 300.0, 400.0, 500.0, 1000.0)
FLUX_FILE_RE = re.compile(r"^hemisphere_flux_R(?P<label>.+)m\.csv$")
POINT_FOLDER_RE = re.compile(r"^Point_(?P<number>\d+)$")


def require_matplotlib():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("matplotlib is required to write hourly flux concentration plots.") from exc

    return plt


def radius_label(radius):
    return f"{radius:g}".replace("-", "neg").replace(".", "p")


def radius_from_label(label):
    return float(label.replace("neg", "-").replace("p", "."))


def time_label(hour):
    return f"{hour:02d}:00"


def format_flux_label(value):
    if value >= 100.0:
        return f"{value:.0f}"
    if value >= 10.0:
        return f"{value:.1f}"
    return f"{value:.2f}"


def read_flux_csv(path):
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError(f"CSV file has no header: {path}")

        missing = [column for column in REQUIRED_COLUMNS if column not in reader.fieldnames]
        if missing:
            raise ValueError(f"CSV file is missing required column(s) {missing}: {path}")

        rows = list(reader)

    data = {column: np.empty(len(rows), dtype=np.float64) for column in REQUIRED_COLUMNS}
    for index, row in enumerate(rows):
        for column in REQUIRED_COLUMNS:
            try:
                data[column][index] = float(row[column])
            except ValueError as exc:
                raise ValueError(f"Invalid numeric value in {path}, row {index + 2}, column {column}") from exc

    for column in REQUIRED_COLUMNS:
        if not np.all(np.isfinite(data[column])):
            raise ValueError(f"CSV file contains non-finite values in column {column}: {path}")

    for column in ("ray_count", "power_W", "flux_W_m2"):
        if np.any(data[column] < 0.0):
            raise ValueError(f"CSV file contains negative values in column {column}: {path}")

    return data


def center_edges(centers, lower, upper):
    centers = np.asarray(centers, dtype=np.float64)
    if centers.size == 1:
        half_width = (upper - lower) / 2.0
        return np.array([max(lower, centers[0] - half_width), min(upper, centers[0] + half_width)])

    edges = np.empty(centers.size + 1, dtype=np.float64)
    edges[1:-1] = 0.5 * (centers[:-1] + centers[1:])
    edges[0] = centers[0] - 0.5 * (centers[1] - centers[0])
    edges[-1] = centers[-1] + 0.5 * (centers[-1] - centers[-2])
    edges[0] = max(lower, edges[0])
    edges[-1] = min(upper, edges[-1])
    return edges


def periodic_azimuth_edges(centers):
    centers = np.asarray(centers, dtype=np.float64)
    if centers.size == 1:
        return np.array([centers[0] - 180.0, centers[0] + 180.0], dtype=np.float64)

    previous_gap = centers[0] - (centers[-1] - 360.0)
    next_gaps = np.diff(np.concatenate((centers, [centers[0] + 360.0])))
    edges = np.empty(centers.size + 1, dtype=np.float64)
    edges[0] = centers[0] - 0.5 * previous_gap
    edges[1:] = centers + 0.5 * next_gaps
    return edges


def bin_solid_angles(data):
    azimuth_centers = np.unique(data["azimuth_center_deg"])
    zenith_centers = np.unique(data["zenith_center_deg"])
    azimuth_edges = periodic_azimuth_edges(azimuth_centers)
    zenith_edges = center_edges(zenith_centers, 0.0, 90.0)

    azimuth_widths = np.radians(np.diff(azimuth_edges))
    zenith_inner = np.radians(zenith_edges[:-1])
    zenith_outer = np.radians(zenith_edges[1:])
    zenith_weights = np.cos(zenith_inner) - np.cos(zenith_outer)

    azimuth_index = {value: index for index, value in enumerate(azimuth_centers)}
    zenith_index = {value: index for index, value in enumerate(zenith_centers)}
    solid_angles = np.empty(data["power_W"].size, dtype=np.float64)
    for index, (azimuth, zenith) in enumerate(zip(data["azimuth_center_deg"], data["zenith_center_deg"])):
        solid_angles[index] = azimuth_widths[azimuth_index[azimuth]] * zenith_weights[zenith_index[zenith]]
    return solid_angles


def top_power_region(power, solid_angles, fraction):
    total_power = float(np.sum(power))
    if total_power <= 0.0 or power.size == 0:
        return 0.0, 0.0, 0

    order = np.argsort(-power, kind="stable")
    cumulative = np.cumsum(power[order])
    index = int(np.searchsorted(cumulative, fraction * total_power, side="left"))
    index = min(index, order.size - 1)
    selected = order[: index + 1]

    solid_angle = float(np.sum(solid_angles[selected]))
    hemisphere_percent = solid_angle / (2.0 * math.pi) * 100.0
    return solid_angle, hemisphere_percent, int(selected.size)


def find_point_number(path, input_folder):
    for parent in path.parents:
        match = POINT_FOLDER_RE.match(parent.name)
        if match is not None:
            return int(match.group("number"))
        if parent == input_folder:
            break
    raise ValueError(f"Cannot infer Point_<n> folder for flux CSV: {path}")


def discover_flux_files(input_folder, requested_radii, point_hour_offset):
    requested = {float(radius) for radius in requested_radii}
    discovered = {}

    for path in sorted(input_folder.rglob("hemisphere_flux_R*m.csv")):
        match = FLUX_FILE_RE.match(path.name)
        if match is None:
            continue

        radius = radius_from_label(match.group("label"))
        if radius not in requested:
            continue

        point_number = find_point_number(path, input_folder)
        hour = point_number + point_hour_offset
        key = (hour, radius)
        if key in discovered:
            raise ValueError(
                f"Multiple hemisphere flux CSV files found for hour {hour} and radius {radius:g} m:\n"
                f"  {discovered[key]}\n"
                f"  {path}"
            )
        discovered[key] = path

    return [(hour, radius, discovered[(hour, radius)]) for hour, radius in sorted(discovered)]


def analyze_flux_file(hour, radius, path, top_fraction):
    data = read_flux_csv(path)
    if data["power_W"].size == 0:
        raise ValueError(f"Hemisphere flux CSV contains no sky bins: {path}")

    solid_angles = bin_solid_angles(data)
    top90_solid_angle, top90_percent, top90_bin_count = top_power_region(
        data["power_W"],
        solid_angles,
        top_fraction,
    )

    max_flux_index = int(np.argmax(data["flux_W_m2"]))
    return {
        "time_label": time_label(hour),
        "hour": hour,
        "Radius_m": radius,
        "TotalPower_W": float(np.sum(data["power_W"])),
        "Top90SolidAngle_sr": top90_solid_angle,
        "Top90HemispherePercent": top90_percent,
        "Top90BinCount": top90_bin_count,
        "TotalBinCount": int(data["power_W"].size),
        "MaxFlux_W_m2": float(data["flux_W_m2"][max_flux_index]),
        "Az_max_flux_deg": float(data["azimuth_center_deg"][max_flux_index]),
        "El_max_flux_deg": float(data["elevation_center_deg"][max_flux_index]),
        "path": path,
    }


def write_summary_csv(path, results):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(SUMMARY_COLUMNS)
        for result in results:
            writer.writerow([
                result["time_label"],
                result["hour"],
                f"{result['Radius_m']:.10g}",
                f"{result['TotalPower_W']:.17g}",
                f"{result['Top90SolidAngle_sr']:.17g}",
                f"{result['Top90HemispherePercent']:.10g}",
                result["Top90BinCount"],
                result["TotalBinCount"],
                f"{result['MaxFlux_W_m2']:.17g}",
                f"{result['Az_max_flux_deg']:.10g}",
                f"{result['El_max_flux_deg']:.10g}",
            ])


def bubble_sizes(max_flux_values, bubble_scale):
    values = np.asarray(max_flux_values, dtype=np.float64)
    maximum = float(np.max(values)) if values.size else 0.0
    if maximum <= 0.0:
        return np.full(values.shape, 44.0)
    return 44.0 + 260.0 * bubble_scale * values / maximum


def write_summary_plot(path, results, title, bubble_scale):
    plt = require_matplotlib()
    radii = sorted({result["Radius_m"] for result in results})
    hours = sorted({result["hour"] for result in results})
    all_flux_values = [result["MaxFlux_W_m2"] for result in results]

    fig, ax = plt.subplots(figsize=(11, 6), constrained_layout=True)
    colors = plt.get_cmap("tab10")

    for radius_index, radius in enumerate(radii):
        radius_results = sorted(
            (result for result in results if result["Radius_m"] == radius),
            key=lambda result: result["hour"],
        )
        x_values = np.array([result["hour"] for result in radius_results], dtype=np.float64)
        solid_angles = np.array([result["Top90SolidAngle_sr"] for result in radius_results], dtype=np.float64)
        flux_values = np.array([result["MaxFlux_W_m2"] for result in radius_results], dtype=np.float64)
        color = colors(radius_index % 10)

        ax.plot(x_values, solid_angles, color=color, linewidth=1.7, label=f"R = {radius:g} m", zorder=2)
        ax.scatter(
            x_values,
            solid_angles,
            s=bubble_sizes(flux_values, bubble_scale),
            color=color,
            edgecolors="black",
            linewidths=0.65,
            alpha=0.72,
            zorder=3,
        )
        for x_value, solid_angle, flux_value in zip(x_values, solid_angles, flux_values):
            ax.annotate(
                format_flux_label(flux_value),
                xy=(x_value, solid_angle),
                xytext=(0, 8),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=7,
                color="#222222",
                zorder=4,
            )

    ax.set_xticks(hours)
    ax.set_xticklabels([time_label(hour) for hour in hours])
    ax.set_xlabel("Time of day")
    ax.set_ylabel("Top90 solid angle [sr]")
    ax.set_title(title)
    ax.grid(True, alpha=0.35)
    ax.legend(title="Radius", loc="best")

    secondary = ax.secondary_yaxis(
        "right",
        functions=(
            lambda steradians: steradians / (2.0 * math.pi) * 100.0,
            lambda percent: percent / 100.0 * (2.0 * math.pi),
        ),
    )
    secondary.set_ylabel("Top90 hemisphere percentage [%]")

    if all_flux_values:
        ax.text(
            0.01,
            0.01,
            "Bubble area is proportional to the per-hour maximum flux; point labels are W/m$^2$.",
            transform=ax.transAxes,
            fontsize=8,
            ha="left",
            va="bottom",
            bbox={"facecolor": "white", "edgecolor": "#777777", "alpha": 0.86, "pad": 3.0},
        )

    fig.savefig(path, dpi=180)
    plt.close(fig)


def print_summary(results, summary_csv, summary_png):
    solid_angles = np.array([result["Top90SolidAngle_sr"] for result in results], dtype=np.float64)
    percentages = np.array([result["Top90HemispherePercent"] for result in results], dtype=np.float64)
    max_flux = np.array([result["MaxFlux_W_m2"] for result in results], dtype=np.float64)

    print(f"Analyzed {len(results)} hour/radius combinations.")
    print(f"Wrote {summary_csv}")
    print(f"Wrote {summary_png}")
    print(f"Top90SolidAngle_sr range: {np.min(solid_angles):.6g} to {np.max(solid_angles):.6g}")
    print(f"Top90HemispherePercent range: {np.min(percentages):.6g} to {np.max(percentages):.6g}")
    print(f"MaxFlux_W_m2 range: {np.min(max_flux):.6g} to {np.max(max_flux):.6g}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Analyze hourly sky-region concentration from hemisphere flux CSV files."
    )
    parser.add_argument("input_folder", help="Day folder containing Point_<n> subfolders with hemisphere flux CSV files.")
    parser.add_argument("--radii", nargs="+", type=float, default=DEFAULT_RADII, help="Hemisphere radii in meters.")
    parser.add_argument(
        "--point-hour-offset",
        type=int,
        default=-3,
        help="Offset added to Point_<n> folder numbers to infer hour of day.",
    )
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--top-fraction", type=float, default=0.90)
    parser.add_argument("--bubble-scale", type=float, default=1.0)
    return parser.parse_args()


def main():
    args = parse_args()
    if not (0.0 < args.top_fraction <= 1.0):
        raise ValueError("--top-fraction must be greater than 0 and no greater than 1")
    if args.bubble_scale <= 0.0:
        raise ValueError("--bubble-scale must be positive")
    if any(radius <= 0.0 for radius in args.radii):
        raise ValueError("--radii values must be positive")

    input_folder = Path(args.input_folder)
    if not input_folder.is_dir():
        raise ValueError(f"Input folder does not exist or is not a directory: {input_folder}")

    output_dir = input_folder if args.output_dir is None else Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    discovered = discover_flux_files(input_folder, args.radii, args.point_hour_offset)
    if not discovered:
        raise ValueError(f"No requested hemisphere_flux_R<m>m.csv files found under: {input_folder}")

    discovered_radii = {radius for _, radius, _ in discovered}
    for radius in sorted(set(float(radius) for radius in args.radii) - discovered_radii):
        print(f"Warning: no hemisphere flux CSV files found for radius {radius:g} m under {input_folder}")

    results = [
        analyze_flux_file(hour, radius, path, args.top_fraction)
        for hour, radius, path in discovered
    ]
    results.sort(key=lambda result: (result["hour"], result["Radius_m"]))

    summary_csv = output_dir / "hourly_flux_concentration.csv"
    summary_png = output_dir / "hourly_flux_concentration.png"
    write_summary_csv(summary_csv, results)
    write_summary_plot(
        summary_png,
        results,
        f"{input_folder.name} hourly escaped-flux concentration",
        args.bubble_scale,
    )
    print_summary(results, summary_csv, summary_png)


if __name__ == "__main__":
    main()
