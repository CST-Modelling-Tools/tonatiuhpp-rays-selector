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
    "energy_Wh_m2",
)

DAILY_FILE_RE = re.compile(r"^daily_hemisphere_energy_R(?P<label>.+)m\.csv$")


def require_matplotlib():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.colors as mpl_colors
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("matplotlib is required to write concentration plots.") from exc

    return mpl_colors, plt


def degree_label(value):
    return f"{value:g}\N{DEGREE SIGN}"


def ordinal_degree_label(value):
    return f"{value:g}\N{MASCULINE ORDINAL INDICATOR}"


def radius_label(radius):
    return f"{radius:g}".replace("-", "neg").replace(".", "p")


def radius_from_label(label):
    return float(label.replace("neg", "-").replace("p", "."))


def azimuth_grid_labels():
    labels = []
    for azimuth in range(0, 360, 30):
        cardinal = {0: "N", 90: "E", 180: "S", 270: "W"}.get(azimuth)
        numeric = degree_label(azimuth)
        labels.append(f"{cardinal}\n{numeric}" if cardinal else numeric)
    return labels


def discover_daily_files(input_folder):
    by_radius = {}
    for path in sorted(input_folder.rglob("daily_hemisphere_energy_R*m.csv")):
        match = DAILY_FILE_RE.match(path.name)
        if match is None:
            continue
        radius = radius_from_label(match.group("label"))
        if radius in by_radius:
            raise ValueError(
                f"Multiple daily energy CSV files found for radius {radius:g} m:\n"
                f"  {by_radius[radius]}\n"
                f"  {path}"
            )
        by_radius[radius] = path
    return [(radius, by_radius[radius]) for radius in sorted(by_radius)]


def read_daily_csv(path):
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
    return data


def unit_vectors(azimuth_deg, elevation_deg):
    azimuth_rad = np.radians(azimuth_deg)
    elevation_rad = np.radians(elevation_deg)
    cos_elevation = np.cos(elevation_rad)
    return np.column_stack((
        cos_elevation * np.sin(azimuth_rad),
        cos_elevation * np.cos(azimuth_rad),
        np.sin(elevation_rad),
    ))


def vector_to_azimuth_elevation(vector):
    norm = np.linalg.norm(vector)
    if norm <= 0.0 or not np.isfinite(norm):
        return math.nan, math.nan
    unit = vector / norm
    azimuth = (math.degrees(math.atan2(unit[0], unit[1])) + 360.0) % 360.0
    elevation = math.degrees(math.asin(float(np.clip(unit[2], -1.0, 1.0))))
    return azimuth, elevation


def angular_distances_deg(vectors, center):
    dots = np.clip(vectors @ center, -1.0, 1.0)
    return np.degrees(np.arccos(dots))


def containment_radius_deg(distances_deg, energy, fraction=0.90):
    total = float(np.sum(energy))
    if total <= 0.0:
        return math.nan

    order = np.argsort(distances_deg, kind="stable")
    cumulative = np.cumsum(energy[order])
    index = int(np.searchsorted(cumulative, fraction * total, side="left"))
    index = min(index, order.size - 1)
    return float(distances_deg[order[index]])


def analyze_radius(radius, path):
    data = read_daily_csv(path)
    energy = data["energy_Wh_m2"]
    vectors = unit_vectors(data["azimuth_center_deg"], data["elevation_center_deg"])
    total_energy = float(np.sum(energy))

    max_index = int(np.argmax(energy))
    max_vector = vectors[max_index]
    az_max = float(data["azimuth_center_deg"][max_index])
    el_max = float(data["elevation_center_deg"][max_index])
    theta90_max = containment_radius_deg(angular_distances_deg(vectors, max_vector), energy)

    weighted_vector = np.sum(vectors * energy[:, np.newaxis], axis=0)
    centroid_norm = np.linalg.norm(weighted_vector)
    if total_energy > 0.0 and centroid_norm > 0.0 and np.isfinite(centroid_norm):
        centroid_vector = weighted_vector / centroid_norm
        az_centroid, el_centroid = vector_to_azimuth_elevation(centroid_vector)
        theta90_centroid = containment_radius_deg(angular_distances_deg(vectors, centroid_vector), energy)
    else:
        centroid_vector = np.array([math.nan, math.nan, math.nan], dtype=np.float64)
        az_centroid = math.nan
        el_centroid = math.nan
        theta90_centroid = math.nan

    return {
        "radius": radius,
        "path": path,
        "data": data,
        "vectors": vectors,
        "max_vector": max_vector,
        "centroid_vector": centroid_vector,
        "Az_max_deg": az_max,
        "El_max_deg": el_max,
        "Theta90_max_deg": theta90_max,
        "Az_centroid_deg": az_centroid,
        "El_centroid_deg": el_centroid,
        "Theta90_centroid_deg": theta90_centroid,
        "TotalEnergy_Wh_m2": total_energy,
    }


def write_summary_csv(path, results):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([
            "Radius_m",
            "Az_max_deg",
            "El_max_deg",
            "Theta90_max_deg",
            "Az_centroid_deg",
            "El_centroid_deg",
            "Theta90_centroid_deg",
            "TotalEnergy_Wh_m2",
        ])
        for result in results:
            writer.writerow([
                f"{result['radius']:.10g}",
                f"{result['Az_max_deg']:.10g}",
                f"{result['El_max_deg']:.10g}",
                f"{result['Theta90_max_deg']:.10g}",
                f"{result['Az_centroid_deg']:.10g}",
                f"{result['El_centroid_deg']:.10g}",
                f"{result['Theta90_centroid_deg']:.10g}",
                f"{result['TotalEnergy_Wh_m2']:.17g}",
            ])


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


def grid_from_flat(data):
    azimuth_centers = np.unique(data["azimuth_center_deg"])
    zenith_centers = np.unique(data["zenith_center_deg"])
    energy = np.full((azimuth_centers.size, zenith_centers.size), np.nan, dtype=np.float64)
    azimuth_index = {value: index for index, value in enumerate(azimuth_centers)}
    zenith_index = {value: index for index, value in enumerate(zenith_centers)}
    for azimuth, zenith, value in zip(
        data["azimuth_center_deg"],
        data["zenith_center_deg"],
        data["energy_Wh_m2"],
    ):
        energy[azimuth_index[azimuth], zenith_index[zenith]] = value
    if np.any(~np.isfinite(energy)):
        raise ValueError("Daily energy grid is incomplete.")
    return azimuth_centers, zenith_centers, energy


def choose_norm(values, mpl_colors):
    return mpl_colors.Normalize(vmin=0.0, vmax=None)


def contour_levels(values):
    max_value = float(np.max(values)) if values.size else 0.0
    min_value = float(np.min(values)) if values.size else 0.0
    if max_value <= 0.0 or max_value <= min_value:
        return []
    levels = [max_value * fraction for fraction in (0.10, 0.25, 0.50, 0.75, 0.90)]
    return [level for level in levels if min_value < level < max_value]


def great_circle_boundary(center_vector, theta_deg, samples=361):
    if not np.isfinite(theta_deg):
        return np.array([]), np.array([])

    center = np.asarray(center_vector, dtype=np.float64)
    norm = np.linalg.norm(center)
    if norm <= 0.0 or not np.isfinite(norm):
        return np.array([]), np.array([])
    center = center / norm

    reference = np.array([0.0, 0.0, 1.0])
    if abs(float(center @ reference)) > 0.95:
        reference = np.array([1.0, 0.0, 0.0])
    axis_a = np.cross(center, reference)
    axis_a = axis_a / np.linalg.norm(axis_a)
    axis_b = np.cross(center, axis_a)

    theta = math.radians(theta_deg)
    phi = np.linspace(0.0, 2.0 * math.pi, samples)
    vectors = (
        math.cos(theta) * center
        + math.sin(theta) * (np.cos(phi)[:, np.newaxis] * axis_a + np.sin(phi)[:, np.newaxis] * axis_b)
    )

    azimuth = (np.degrees(np.arctan2(vectors[:, 0], vectors[:, 1])) + 360.0) % 360.0
    elevation = np.degrees(np.arcsin(np.clip(vectors[:, 2], -1.0, 1.0)))
    zenith = 90.0 - elevation
    visible = (elevation >= 0.0) & (zenith >= 0.0) & (zenith <= 90.0)
    azimuth[~visible] = np.nan
    zenith[~visible] = np.nan

    theta_plot = np.radians(azimuth)
    jumps = np.abs(np.diff(theta_plot)) > math.pi
    jump_indices = np.flatnonzero(jumps) + 1
    theta_plot[jump_indices] = np.nan
    zenith[jump_indices] = np.nan
    return theta_plot, zenith


def plot_marker(ax, azimuth_deg, elevation_deg, *, marker, color, label, zorder):
    if not (np.isfinite(azimuth_deg) and np.isfinite(elevation_deg)):
        return
    ax.scatter(
        math.radians(azimuth_deg),
        90.0 - elevation_deg,
        marker=marker,
        s=80,
        c=color,
        edgecolors="black",
        linewidths=0.9,
        label=label,
        zorder=zorder,
    )


def write_overlay_plot(path, result):
    mpl_colors, plt = require_matplotlib()
    azimuth_centers, zenith_centers, energy = grid_from_flat(result["data"])
    azimuth_edges = center_edges(azimuth_centers, 0.0, 360.0)
    zenith_edges = center_edges(zenith_centers, 0.0, 90.0)
    zenith_edge_grid, theta_edge_grid = np.meshgrid(zenith_edges, np.radians(azimuth_edges), indexing="ij")

    fig, ax = plt.subplots(figsize=(10, 9), subplot_kw={"projection": "polar"}, constrained_layout=True)
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_ylim(0.0, 90.0)
    elevation_ticks = [90, 75, 60, 45, 30, 15, 0]
    ax.set_yticks([90.0 - elevation for elevation in elevation_ticks])
    ax.set_yticklabels([degree_label(elevation) for elevation in elevation_ticks])
    ax.set_rlabel_position(225)
    ax.set_thetagrids(list(range(0, 360, 30)), labels=azimuth_grid_labels())
    ax.tick_params(axis="x", labelsize=12, pad=8)
    ax.tick_params(axis="y", labelsize=9, pad=3)
    for label in ax.get_yticklabels():
        label.set_bbox({"facecolor": "white", "edgecolor": "none", "alpha": 0.65, "pad": 1.5})
    for label in ax.get_xticklabels():
        label.set_fontweight("bold")
    ax.grid(True, color="#9a9a9a", linewidth=0.55, alpha=0.5)

    mesh = ax.pcolormesh(
        theta_edge_grid,
        zenith_edge_grid,
        energy.T,
        cmap="inferno",
        norm=choose_norm(energy, mpl_colors),
        shading="auto",
    )
    colorbar = fig.colorbar(mesh, ax=ax, pad=0.08, shrink=0.86)
    colorbar.set_label("Daily energy [Wh/m$^2$]")

    levels = contour_levels(energy)
    if levels:
        zenith_center_grid, theta_center_grid = np.meshgrid(zenith_centers, np.radians(azimuth_centers), indexing="ij")
        ax.contour(theta_center_grid, zenith_center_grid, energy.T, levels=levels, colors="white", linewidths=0.6, alpha=0.55)

    plot_marker(ax, result["Az_max_deg"], result["El_max_deg"], marker="o", color="white", label="Hotspot", zorder=7)
    plot_marker(ax, result["Az_centroid_deg"], result["El_centroid_deg"], marker="D", color="cyan", label="Centroid", zorder=8)

    theta, zenith = great_circle_boundary(result["max_vector"], result["Theta90_max_deg"])
    if theta.size:
        ax.plot(theta, zenith, color="white", linewidth=1.4, linestyle="-", label="Theta90 hotspot", zorder=6)

    theta, zenith = great_circle_boundary(result["centroid_vector"], result["Theta90_centroid_deg"])
    if theta.size:
        ax.plot(theta, zenith, color="cyan", linewidth=1.4, linestyle="--", label="Theta90 centroid", zorder=6)

    ax.set_title(
        "\n".join((
            f"Daily energy concentration, R = {result['radius']:g} m",
            (
                f"Theta90 hotspot = {result['Theta90_max_deg']:.2f}\N{DEGREE SIGN}; "
                f"Theta90 centroid = {result['Theta90_centroid_deg']:.2f}\N{DEGREE SIGN}"
            ),
        )),
        fontsize=12,
        pad=20,
    )
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, -0.08), fontsize=8)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def write_summary_plot(path, results):
    _, plt = require_matplotlib()
    radii = np.array([result["radius"] for result in results], dtype=np.float64)
    theta_max = np.array([result["Theta90_max_deg"] for result in results], dtype=np.float64)
    theta_centroid = np.array([result["Theta90_centroid_deg"] for result in results], dtype=np.float64)

    fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)
    ax.plot(radii, theta_max, marker="o", label="Theta90 hotspot")
    ax.plot(radii, theta_centroid, marker="s", label="Theta90 centroid")
    ax.set_xlabel("Radius [m]")
    ax.set_ylabel("Angular radius [deg]")
    ax.set_title("Daily escaped-energy angular concentration")
    ax.grid(True, alpha=0.35)
    ax.legend()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def print_summary(results):
    print("Radius  Theta90_max  Theta90_centroid")
    for result in results:
        print(
            f"{result['radius']:g}  "
            f"{result['Theta90_max_deg']:.6g}  "
            f"{result['Theta90_centroid_deg']:.6g}"
        )

    theta_max = np.array([result["Theta90_max_deg"] for result in results], dtype=np.float64)
    theta_centroid = np.array([result["Theta90_centroid_deg"] for result in results], dtype=np.float64)
    print(f"Minimum Theta90_max {np.nanmin(theta_max):.6g}")
    print(f"Maximum Theta90_max {np.nanmax(theta_max):.6g}")
    print(f"Minimum Theta90_centroid {np.nanmin(theta_centroid):.6g}")
    print(f"Maximum Theta90_centroid {np.nanmax(theta_centroid):.6g}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Analyze angular concentration of daily hemisphere energy maps."
    )
    parser.add_argument("input_folder", help="Folder containing daily_hemisphere_energy_R<radius>m.csv files.")
    return parser.parse_args()


def main():
    args = parse_args()
    input_folder = Path(args.input_folder)
    if not input_folder.is_dir():
        raise ValueError(f"Input folder does not exist or is not a directory: {input_folder}")

    discovered = discover_daily_files(input_folder)
    if not discovered:
        raise ValueError(f"No daily_hemisphere_energy_R<m>m.csv files found under: {input_folder}")

    results = [analyze_radius(radius, path) for radius, path in discovered]
    summary_csv = input_folder / "daily_energy_concentration.csv"
    summary_png = input_folder / "daily_energy_concentration.png"
    write_summary_csv(summary_csv, results)
    write_summary_plot(summary_png, results)

    for result in results:
        overlay_png = input_folder / f"daily_hemisphere_energy_R{radius_label(result['radius'])}m_concentration.png"
        write_overlay_plot(overlay_png, result)

    print(f"Wrote {summary_csv}")
    print(f"Wrote {summary_png}")
    print_summary(results)


if __name__ == "__main__":
    main()
