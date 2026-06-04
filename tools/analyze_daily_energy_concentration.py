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
    solid_angles = np.empty(data["energy_Wh_m2"].size, dtype=np.float64)
    for index, (azimuth, zenith) in enumerate(zip(data["azimuth_center_deg"], data["zenith_center_deg"])):
        solid_angles[index] = azimuth_widths[azimuth_index[azimuth]] * zenith_weights[zenith_index[zenith]]
    return solid_angles


def top90_energy_region(energy, solid_angles, fraction=0.90):
    selected = np.zeros(energy.size, dtype=bool)
    total = float(np.sum(energy))
    if total <= 0.0 or energy.size == 0:
        return selected, 0.0, 0.0, 0.0, 0

    order = np.argsort(-energy, kind="stable")
    cumulative = np.cumsum(energy[order])
    index = int(np.searchsorted(cumulative, fraction * total, side="left"))
    index = min(index, order.size - 1)
    selected[order[: index + 1]] = True

    solid_angle = float(np.sum(solid_angles[selected]))
    hemisphere_fraction = solid_angle / (2.0 * math.pi)
    return selected, solid_angle, hemisphere_fraction, 100.0 * hemisphere_fraction, int(np.count_nonzero(selected))


def analyze_radius(radius, path):
    data = read_daily_csv(path)
    energy = data["energy_Wh_m2"]
    if energy.size == 0:
        raise ValueError(f"Daily energy CSV contains no sky bins: {path}")

    vectors = unit_vectors(data["azimuth_center_deg"], data["elevation_center_deg"])
    total_energy = float(np.sum(energy))
    solid_angles = bin_solid_angles(data)
    top90_mask, top90_solid_angle, top90_fraction, top90_percent, top90_bin_count = top90_energy_region(
        energy,
        solid_angles,
    )

    max_index = int(np.argmax(energy))
    az_max = float(data["azimuth_center_deg"][max_index])
    el_max = float(data["elevation_center_deg"][max_index])
    max_energy = float(energy[max_index])

    weighted_vector = np.sum(vectors * energy[:, np.newaxis], axis=0)
    centroid_norm = np.linalg.norm(weighted_vector)
    if total_energy > 0.0 and centroid_norm > 0.0 and np.isfinite(centroid_norm):
        centroid_vector = weighted_vector / centroid_norm
        az_centroid, el_centroid = vector_to_azimuth_elevation(centroid_vector)
    else:
        az_centroid = math.nan
        el_centroid = math.nan

    return {
        "radius": radius,
        "path": path,
        "data": data,
        "vectors": vectors,
        "Top90EnergyRegion": top90_mask,
        "Az_max_deg": az_max,
        "El_max_deg": el_max,
        "MaxEnergy_Wh_m2": max_energy,
        "Az_centroid_deg": az_centroid,
        "El_centroid_deg": el_centroid,
        "TotalEnergy_Wh_m2": total_energy,
        "Top90SolidAngle_sr": top90_solid_angle,
        "Top90HemisphereFraction": top90_fraction,
        "Top90HemispherePercent": top90_percent,
        "Top90BinCount": top90_bin_count,
        "TotalBinCount": int(energy.size),
    }


def write_summary_csv(path, results):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([
            "Radius_m",
            "Az_max_deg",
            "El_max_deg",
            "MaxEnergy_Wh_m2",
            "Az_centroid_deg",
            "El_centroid_deg",
            "TotalEnergy_Wh_m2",
            "Top90SolidAngle_sr",
            "Top90HemisphereFraction",
            "Top90HemispherePercent",
            "Top90BinCount",
            "TotalBinCount",
        ])
        for result in results:
            writer.writerow([
                f"{result['radius']:.10g}",
                f"{result['Az_max_deg']:.10g}",
                f"{result['El_max_deg']:.10g}",
                f"{result['MaxEnergy_Wh_m2']:.17g}",
                f"{result['Az_centroid_deg']:.10g}",
                f"{result['El_centroid_deg']:.10g}",
                f"{result['TotalEnergy_Wh_m2']:.17g}",
                f"{result['Top90SolidAngle_sr']:.17g}",
                f"{result['Top90HemisphereFraction']:.17g}",
                f"{result['Top90HemispherePercent']:.10g}",
                result["Top90BinCount"],
                result["TotalBinCount"],
            ])


def grid_from_flat(data, values=None):
    azimuth_centers = np.unique(data["azimuth_center_deg"])
    zenith_centers = np.unique(data["zenith_center_deg"])
    if values is None:
        values = data["energy_Wh_m2"]
    grid = np.full((azimuth_centers.size, zenith_centers.size), np.nan, dtype=np.float64)
    azimuth_index = {value: index for index, value in enumerate(azimuth_centers)}
    zenith_index = {value: index for index, value in enumerate(zenith_centers)}
    for azimuth, zenith, value in zip(
        data["azimuth_center_deg"],
        data["zenith_center_deg"],
        values,
    ):
        grid[azimuth_index[azimuth], zenith_index[zenith]] = value
    if np.any(~np.isfinite(grid)):
        raise ValueError("Daily energy grid is incomplete.")
    return azimuth_centers, zenith_centers, grid


def choose_norm(values, mpl_colors):
    return mpl_colors.Normalize(vmin=0.0, vmax=None)


def contour_levels(values):
    max_value = float(np.max(values)) if values.size else 0.0
    min_value = float(np.min(values)) if values.size else 0.0
    if max_value <= 0.0 or max_value <= min_value:
        return []
    levels = [max_value * fraction for fraction in (0.10, 0.25, 0.50, 0.75, 0.90)]
    return [level for level in levels if min_value < level < max_value]


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
    _, _, top90_grid = grid_from_flat(result["data"], result["Top90EnergyRegion"].astype(np.float64))
    azimuth_edges = periodic_azimuth_edges(azimuth_centers)
    zenith_edges = center_edges(zenith_centers, 0.0, 90.0)
    zenith_edge_grid, theta_edge_grid = np.meshgrid(zenith_edges, np.radians(azimuth_edges), indexing="ij")
    zenith_center_grid, theta_center_grid = np.meshgrid(
        zenith_centers,
        np.radians(azimuth_centers),
        indexing="ij",
    )

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
        ax.contour(theta_center_grid, zenith_center_grid, energy.T, levels=levels, colors="white", linewidths=0.6, alpha=0.55)

    if np.any(top90_grid):
        top90_overlay = np.where(top90_grid.T > 0.5, 1.0, np.nan)
        top90_cmap = mpl_colors.ListedColormap(["#00d5ff"])
        ax.pcolormesh(
            theta_edge_grid,
            zenith_edge_grid,
            top90_overlay,
            cmap=top90_cmap,
            shading="auto",
            alpha=0.28,
            zorder=5,
        )
        if np.any(top90_grid < 0.5):
            ax.contour(
                theta_center_grid,
                zenith_center_grid,
                top90_grid.T,
                levels=[0.5],
                colors="#00d5ff",
                linewidths=1.2,
                alpha=0.9,
                zorder=6,
            )
        ax.plot([], [], color="#00d5ff", linewidth=5, alpha=0.45, label="Top90EnergyRegion")

    plot_marker(ax, result["Az_max_deg"], result["El_max_deg"], marker="o", color="white", label="Hotspot", zorder=7)
    plot_marker(ax, result["Az_centroid_deg"], result["El_centroid_deg"], marker="D", color="cyan", label="Centroid", zorder=8)

    ax.set_title(
        "\n".join((
            f"Daily energy concentration, R = {result['radius']:g} m",
            f"Top90 region = {result['Top90SolidAngle_sr']:.4g} sr ({result['Top90HemispherePercent']:.2f}% hemisphere)",
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
    solid_angles = np.array([result["Top90SolidAngle_sr"] for result in results], dtype=np.float64)

    fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)
    ax.plot(radii, solid_angles, marker="o", label="Energy-ranked 90% region")
    ax.set_xlabel("Radius [m]")
    ax.set_ylabel("Top90 solid angle [sr]")
    ax.set_title("Daily escaped-energy 90% sky-region size")
    ax.grid(True, alpha=0.35)
    ax.legend()
    secondary = ax.secondary_yaxis(
        "right",
        functions=(
            lambda steradians: steradians / (2.0 * math.pi) * 100.0,
            lambda percent: percent / 100.0 * (2.0 * math.pi),
        ),
    )
    secondary.set_ylabel("Hemisphere fraction [%]")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def print_summary(results):
    print("Radius  Top90SolidAngle_sr  Top90HemispherePercent  Top90BinCount  MaxEnergy_Wh_m2")
    for result in results:
        print(
            f"{result['radius']:g}  "
            f"{result['Top90SolidAngle_sr']:.6g}  "
            f"{result['Top90HemispherePercent']:.6g}  "
            f"{result['Top90BinCount']}  "
            f"{result['MaxEnergy_Wh_m2']:.6g}"
        )

    solid_angles = np.array([result["Top90SolidAngle_sr"] for result in results], dtype=np.float64)
    percentages = np.array([result["Top90HemispherePercent"] for result in results], dtype=np.float64)
    print(f"Minimum Top90SolidAngle_sr {np.nanmin(solid_angles):.6g}")
    print(f"Maximum Top90SolidAngle_sr {np.nanmax(solid_angles):.6g}")
    print(f"Minimum Top90HemispherePercent {np.nanmin(percentages):.6g}")
    print(f"Maximum Top90HemispherePercent {np.nanmax(percentages):.6g}")


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
