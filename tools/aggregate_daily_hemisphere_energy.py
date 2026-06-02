import argparse
import csv
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


def radius_label(radius):
    return f"{radius:g}".replace("-", "neg").replace(".", "p")


def degree_label(value):
    return f"{value:g}\N{DEGREE SIGN}"


def ordinal_degree_label(value):
    return f"{value:g}\N{MASCULINE ORDINAL INDICATOR}"


def azimuth_grid_labels():
    labels = []
    for azimuth in range(0, 360, 30):
        cardinal = {0: "N", 90: "E", 180: "S", 270: "W"}.get(azimuth)
        numeric = degree_label(azimuth)
        labels.append(f"{cardinal}\n{numeric}" if cardinal else numeric)
    return labels


def require_matplotlib():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.colors as mpl_colors
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "matplotlib is required to write PNG daily hemisphere energy maps."
        ) from exc

    return mpl_colors, plt


def read_hourly_csv(path):
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError(f"CSV file has no header: {path}")

        missing = [column for column in REQUIRED_COLUMNS if column not in reader.fieldnames]
        if missing:
            raise ValueError(f"CSV file is missing required column(s) {missing}: {path}")

        rows = list(reader)

    count = len(rows)
    data = {
        "azimuth_center_deg": np.empty(count, dtype=np.float64),
        "elevation_center_deg": np.empty(count, dtype=np.float64),
        "zenith_center_deg": np.empty(count, dtype=np.float64),
        "power_W": np.empty(count, dtype=np.float64),
        "flux_W_m2": np.empty(count, dtype=np.float64),
    }

    for index, row in enumerate(rows):
        for column in data:
            try:
                data[column][index] = float(row[column])
            except ValueError as exc:
                raise ValueError(f"Invalid numeric value in {path}, row {index + 2}, column {column}") from exc
    return data


def validate_matching_grid(reference, candidate, path):
    for column in ("azimuth_center_deg", "elevation_center_deg", "zenith_center_deg"):
        if reference[column].shape != candidate[column].shape or not np.array_equal(reference[column], candidate[column]):
            raise ValueError(f"Grid mismatch for {column} in hourly CSV: {path}")


def aggregate_radius(files, duration_hours):
    reference = read_hourly_csv(files[0])
    energy_Wh_m2 = reference["flux_W_m2"] * duration_hours
    integrated_power_Wh = reference["power_W"] * duration_hours

    for path in files[1:]:
        data = read_hourly_csv(path)
        validate_matching_grid(reference, data, path)
        energy_Wh_m2 += data["flux_W_m2"] * duration_hours
        integrated_power_Wh += data["power_W"] * duration_hours

    return {
        "azimuth_center_deg": reference["azimuth_center_deg"],
        "elevation_center_deg": reference["elevation_center_deg"],
        "zenith_center_deg": reference["zenith_center_deg"],
        "energy_Wh_m2": energy_Wh_m2,
        "energy_kWh_m2": energy_Wh_m2 / 1000.0,
        "integrated_power_Wh": integrated_power_Wh,
        "hourly_file_count": len(files),
    }


def write_daily_csv(path, data):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([
            "azimuth_center_deg",
            "elevation_center_deg",
            "zenith_center_deg",
            "energy_Wh_m2",
            "energy_kWh_m2",
            "integrated_power_Wh",
            "hourly_file_count",
        ])
        count = data["energy_Wh_m2"].size
        for index in range(count):
            writer.writerow([
                f"{data['azimuth_center_deg'][index]:.10g}",
                f"{data['elevation_center_deg'][index]:.10g}",
                f"{data['zenith_center_deg'][index]:.10g}",
                f"{data['energy_Wh_m2'][index]:.17g}",
                f"{data['energy_kWh_m2'][index]:.17g}",
                f"{data['integrated_power_Wh'][index]:.17g}",
                data["hourly_file_count"],
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


def grid_from_flat(data, value_column):
    azimuth_centers = np.unique(data["azimuth_center_deg"])
    zenith_centers = np.unique(data["zenith_center_deg"])
    values = np.full((azimuth_centers.size, zenith_centers.size), np.nan, dtype=np.float64)

    azimuth_index = {value: index for index, value in enumerate(azimuth_centers)}
    zenith_index = {value: index for index, value in enumerate(zenith_centers)}
    for azimuth, zenith, value in zip(
        data["azimuth_center_deg"],
        data["zenith_center_deg"],
        data[value_column],
    ):
        values[azimuth_index[azimuth], zenith_index[zenith]] = value

    if np.any(~np.isfinite(values)):
        raise ValueError("Daily energy grid is incomplete.")
    return azimuth_centers, zenith_centers, values


def choose_norm(values, vmax, log_scale, mpl_colors):
    if not log_scale:
        return mpl_colors.Normalize(vmin=0.0, vmax=vmax)

    positive = values[values > 0.0]
    if positive.size == 0:
        return mpl_colors.LogNorm(vmin=1.0, vmax=max(vmax or 1.0, 1.0))

    vmin = positive.min()
    norm_vmax = vmax if vmax is not None else positive.max()
    if norm_vmax <= vmin:
        norm_vmax = vmin * 10.0
    return mpl_colors.LogNorm(vmin=vmin, vmax=norm_vmax)


def contour_levels(values):
    max_value = float(np.max(values)) if values.size else 0.0
    min_value = float(np.min(values)) if values.size else 0.0
    if max_value <= 0.0 or max_value <= min_value:
        return []

    levels = [max_value * fraction for fraction in (0.10, 0.25, 0.50, 0.75, 0.90)]
    return [level for level in levels if min_value < level < max_value]


def write_daily_plot(path, radius, data, args):
    mpl_colors, plt = require_matplotlib()
    azimuth_centers, zenith_centers, energy = grid_from_flat(data, "energy_Wh_m2")
    azimuth_edges = center_edges(azimuth_centers, 0.0, 360.0)
    zenith_edges = center_edges(zenith_centers, 0.0, 90.0)
    zenith_edge_grid, theta_edge_grid = np.meshgrid(zenith_edges, np.radians(azimuth_edges), indexing="ij")
    plot_values = np.ma.masked_less_equal(energy.T, 0.0) if args.log_scale else energy.T

    fig, ax = plt.subplots(figsize=(10, 9), subplot_kw={"projection": "polar"}, constrained_layout=True)
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_ylim(0.0, 90.0)
    elevation_ticks = [90, 75, 60, 45, 30, 15, 0]
    zenith_ticks = [90.0 - elevation for elevation in elevation_ticks]
    ax.set_yticks(zenith_ticks)
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
        plot_values,
        cmap="inferno",
        norm=choose_norm(energy, args.vmax, args.log_scale, mpl_colors),
        shading="auto",
    )
    colorbar = fig.colorbar(mesh, ax=ax, pad=0.08, shrink=0.86)
    colorbar.set_label("Daily energy [Wh/m$^2$]")

    levels = contour_levels(energy)
    if levels:
        zenith_center_grid, theta_center_grid = np.meshgrid(zenith_centers, np.radians(azimuth_centers), indexing="ij")
        ax.contour(
            theta_center_grid,
            zenith_center_grid,
            energy.T,
            levels=levels,
            colors="white",
            linewidths=0.75,
            alpha=0.75,
        )

    max_index = np.unravel_index(np.argmax(energy), energy.shape)
    max_energy = energy[max_index]
    max_azimuth = azimuth_centers[max_index[0]]
    max_zenith = zenith_centers[max_index[1]]
    max_elevation = 90.0 - max_zenith

    if max_energy > 0.0:
        max_theta = np.radians(max_azimuth)
        ax.scatter(
            max_theta,
            max_zenith,
            marker="o",
            s=58,
            facecolors="none",
            edgecolors="white",
            linewidths=1.4,
            zorder=6,
        )
        ax.annotate(
            (
                f"Max energy = {max_energy:.2f} Wh/m$^2$\n"
                f"Az = {max_azimuth:.1f}\N{DEGREE SIGN}\n"
                f"El = {max_elevation:.1f}\N{DEGREE SIGN}"
            ),
            xy=(max_theta, max_zenith),
            xytext=(24, 24),
            textcoords="offset points",
            fontsize=9,
            color="black",
            bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": "#555555", "alpha": 0.88},
            arrowprops={"arrowstyle": "->", "color": "white", "linewidth": 1.0},
            zorder=7,
        )

    title = "\n".join((
        f"Daily hemisphere energy, R = {radius:g} m",
        (
            f"Max. Energy = {max_energy:.2f} Wh/m$^2$ at az = {ordinal_degree_label(max_azimuth)}, "
            f"elev = {ordinal_degree_label(max_elevation)}; hours = {data['hourly_file_count']}"
        ),
    ))
    ax.set_title(title, fontsize=12, pad=20)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def discover_files(input_folder, radius):
    pattern = f"hemisphere_flux_R{radius_label(radius)}m.csv"
    return sorted(input_folder.rglob(pattern))


def parse_args():
    parser = argparse.ArgumentParser(
        description="Aggregate hourly hemisphere flux CSVs into daily hemisphere energy maps."
    )
    parser.add_argument("input_folder", help="Day or season folder containing hourly Point_* subfolders.")
    parser.add_argument("--radius", nargs="+", type=float, required=True, help="One or more hemisphere radii in meters.")
    parser.add_argument("--duration-hours", type=float, required=True, help="Duration represented by each hourly flux CSV.")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--vmax", type=float, default=None)
    parser.add_argument("--log-scale", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.duration_hours <= 0.0:
        raise ValueError("--duration-hours must be positive")
    if any(radius <= 0.0 for radius in args.radius):
        raise ValueError("--radius values must be positive")
    if args.vmax is not None and args.vmax <= 0.0:
        raise ValueError("--vmax must be positive")

    input_folder = Path(args.input_folder)
    if not input_folder.is_dir():
        raise ValueError(f"Input folder does not exist or is not a directory: {input_folder}")

    output_dir = input_folder if args.output_dir is None else Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for radius in args.radius:
        files = discover_files(input_folder, radius)
        if not files:
            print(f"Warning: no hourly CSV files found for radius {radius:g} m under {input_folder}")
            continue

        data = aggregate_radius(files, args.duration_hours)
        label = radius_label(radius)
        csv_path = output_dir / f"daily_hemisphere_energy_R{label}m.csv"
        png_path = output_dir / f"daily_hemisphere_energy_R{label}m.png"
        write_daily_csv(csv_path, data)
        write_daily_plot(png_path, radius, data, args)

        print(
            f"R={radius:g} m: aggregated {len(files)} hourly CSV files, "
            f"max energy {data['energy_Wh_m2'].max():.17g} Wh/m^2"
        )
        print(f"  wrote {csv_path}")
        print(f"  wrote {png_path}")


if __name__ == "__main__":
    main()
