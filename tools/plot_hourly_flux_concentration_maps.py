import argparse
import csv
import math
from pathlib import Path

import numpy as np

from analyze_hourly_flux_concentration import (
    DEFAULT_RADII,
    bin_solid_angles,
    center_edges,
    discover_flux_files,
    find_point_number,
    periodic_azimuth_edges,
    radius_label,
    read_flux_csv,
    time_label,
)
from map_escaped_flux_hemisphere import azimuth_grid_labels, degree_label, require_matplotlib


TIME_BASIS = "Local Solar Time"

SUMMARY_COLUMNS = (
    "time_label",
    "hour",
    "TimeBasis",
    "point_name",
    "Radius_m",
    "TotalPower_W",
    "Top90SolidAngle_sr",
    "Top90HemispherePercent",
    "Top90BinCount",
    "TotalBinCount",
    "MaxFlux_W_m2",
    "Az_max_flux_deg",
    "El_max_flux_deg",
    "SunAzimuth_deg",
    "SunElevation_deg",
    "DNI_W_m2",
    "OutputPng",
)

SUN_REQUIRED_COLUMNS = (
    "point_name",
    "sun_azimuth_deg",
    "sun_elevation_deg",
)


def top_region_label(fraction):
    return f"Top{100.0 * fraction:g}"


def parse_optional_float(value, path, row_number, column):
    if value is None or value.strip() == "":
        return None
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid numeric value in {path}, row {row_number}, column {column}") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"CSV file contains non-finite value in column {column}: {path}")
    return parsed


def read_sun_positions_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError(f"CSV file has no header: {path}")

        missing = [column for column in SUN_REQUIRED_COLUMNS if column not in reader.fieldnames]
        if missing:
            raise ValueError(f"CSV file is missing required column(s) {missing}: {path}")

        sun_positions = {}
        for row_number, row in enumerate(reader, start=2):
            point_name = row["point_name"].strip()
            if not point_name:
                raise ValueError(f"Missing point_name in {path}, row {row_number}")
            if point_name in sun_positions:
                raise ValueError(f"Duplicate point_name in {path}: {point_name}")

            sun_azimuth = parse_optional_float(row["sun_azimuth_deg"], path, row_number, "sun_azimuth_deg")
            sun_elevation = parse_optional_float(row["sun_elevation_deg"], path, row_number, "sun_elevation_deg")
            dni = parse_optional_float(row.get("dni_W_m2"), path, row_number, "dni_W_m2")
            if sun_azimuth is None or sun_elevation is None:
                raise ValueError(f"Missing Sun azimuth/elevation in {path}, row {row_number}")
            if dni is not None and dni < 0.0:
                raise ValueError(f"CSV file contains negative DNI in {path}, row {row_number}")

            sun_positions[point_name] = {
                "SunAzimuth_deg": sun_azimuth,
                "SunElevation_deg": sun_elevation,
                "DNI_W_m2": dni,
            }

    return sun_positions


def top_power_region_mask(power, solid_angles, fraction):
    selected = np.zeros(power.size, dtype=bool)
    total_power = float(np.sum(power))
    if total_power <= 0.0 or power.size == 0:
        return selected, 0.0, 0.0, 0

    order = np.argsort(-power, kind="stable")
    cumulative = np.cumsum(power[order])
    index = int(np.searchsorted(cumulative, fraction * total_power, side="left"))
    index = min(index, order.size - 1)
    selected[order[: index + 1]] = True

    solid_angle = float(np.sum(solid_angles[selected]))
    hemisphere_percent = solid_angle / (2.0 * math.pi) * 100.0
    return selected, solid_angle, hemisphere_percent, int(np.count_nonzero(selected))


def grid_from_flat(data, values):
    azimuth_centers = np.unique(data["azimuth_center_deg"])
    zenith_centers = np.unique(data["zenith_center_deg"])
    grid = np.full((azimuth_centers.size, zenith_centers.size), np.nan, dtype=np.float64)
    azimuth_index = {value: index for index, value in enumerate(azimuth_centers)}
    zenith_index = {value: index for index, value in enumerate(zenith_centers)}

    for azimuth, zenith, value in zip(data["azimuth_center_deg"], data["zenith_center_deg"], values):
        grid[azimuth_index[azimuth], zenith_index[zenith]] = value

    if np.any(~np.isfinite(grid)):
        raise ValueError("Hemisphere flux grid is incomplete.")
    return azimuth_centers, zenith_centers, grid


def configure_sky_axis(ax):
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


def analyze_flux_file(input_folder, hour, radius, path, top_fraction):
    data = read_flux_csv(path)
    if data["power_W"].size == 0:
        raise ValueError(f"Hemisphere flux CSV contains no sky bins: {path}")

    solid_angles = bin_solid_angles(data)
    top_mask, top_solid_angle, top_percent, top_bin_count = top_power_region_mask(
        data["power_W"],
        solid_angles,
        top_fraction,
    )

    max_flux_index = int(np.argmax(data["flux_W_m2"]))
    point_number = find_point_number(path, input_folder)
    result = {
        "time_label": time_label(hour),
        "hour": hour,
        "TimeBasis": TIME_BASIS,
        "point_name": f"Point_{point_number}",
        "Radius_m": radius,
        "TotalPower_W": float(np.sum(data["power_W"])),
        "Top90SolidAngle_sr": top_solid_angle,
        "Top90HemispherePercent": top_percent,
        "Top90BinCount": top_bin_count,
        "TotalBinCount": int(data["power_W"].size),
        "MaxFlux_W_m2": float(data["flux_W_m2"][max_flux_index]),
        "Az_max_flux_deg": float(data["azimuth_center_deg"][max_flux_index]),
        "El_max_flux_deg": float(data["elevation_center_deg"][max_flux_index]),
        "SunAzimuth_deg": None,
        "SunElevation_deg": None,
        "DNI_W_m2": None,
        "OutputPng": "",
    }
    return result, data, top_mask


def apply_sun_position(result, sun_positions, warned_missing_points):
    if sun_positions is None:
        return

    sun_position = sun_positions.get(result["point_name"])
    if sun_position is None:
        if result["point_name"] not in warned_missing_points:
            print(f"Warning: no Sun position row found for {result['point_name']}")
            warned_missing_points.add(result["point_name"])
        return

    result.update(sun_position)


def has_sun_position(result):
    return result["SunAzimuth_deg"] is not None and result["SunElevation_deg"] is not None


def output_png_name(result):
    return (
        f"hourly_flux_concentration_map_{result['point_name']}_"
        f"R{radius_label(result['Radius_m'])}m.png"
    )


def annotate_summary(ax, result, label):
    lines = [
        f"Time = {result['time_label']} ({result['TimeBasis']})",
        f"{label} solid angle = {result['Top90SolidAngle_sr']:.3f} sr",
        f"{label} hemisphere = {result['Top90HemispherePercent']:.2f}%",
        f"Max flux = {result['MaxFlux_W_m2']:.2f} W/m$^2$",
        f"Max at az = {result['Az_max_flux_deg']:.2f}\N{DEGREE SIGN}, el = {result['El_max_flux_deg']:.2f}\N{DEGREE SIGN}",
    ]
    if has_sun_position(result):
        lines.append(
            f"Sun az = {result['SunAzimuth_deg']:.2f}\N{DEGREE SIGN}, "
            f"el = {result['SunElevation_deg']:.2f}\N{DEGREE SIGN}"
        )
        if result["DNI_W_m2"] is not None:
            lines.append(f"DNI = {result['DNI_W_m2']:.2f} W/m$^2$")
        else:
            lines.append("DNI =")

    text = "\n".join(lines)
    ax.text(
        0.02,
        0.02,
        text,
        transform=ax.transAxes,
        fontsize=9,
        ha="left",
        va="bottom",
        bbox={"facecolor": "white", "edgecolor": "#555555", "alpha": 0.88, "pad": 4.0},
        zorder=10,
    )


def write_concentration_plot(path, day_name, result, data, top_mask, top_fraction, dpi):
    mpl_colors, plt = require_matplotlib()
    azimuth_centers, zenith_centers, top_grid = grid_from_flat(data, top_mask.astype(np.float64))
    azimuth_edges = periodic_azimuth_edges(azimuth_centers)
    zenith_edges = center_edges(zenith_centers, 0.0, 90.0)
    zenith_edge_grid, theta_edge_grid = np.meshgrid(zenith_edges, np.radians(azimuth_edges), indexing="ij")
    zenith_center_grid, theta_center_grid = np.meshgrid(
        zenith_centers,
        np.radians(azimuth_centers),
        indexing="ij",
    )

    fig, ax = plt.subplots(figsize=(10, 9), subplot_kw={"projection": "polar"}, constrained_layout=True)
    configure_sky_axis(ax)

    label = top_region_label(top_fraction)
    if np.any(top_grid):
        top_overlay = np.where(top_grid.T > 0.5, 1.0, np.nan)
        top_cmap = mpl_colors.ListedColormap(["#00a6d6"])
        ax.pcolormesh(
            theta_edge_grid,
            zenith_edge_grid,
            top_overlay,
            cmap=top_cmap,
            shading="auto",
            alpha=0.38,
            zorder=4,
        )
        if np.any(top_grid < 0.5):
            ax.contour(
                theta_center_grid,
                zenith_center_grid,
                top_grid.T,
                levels=[0.5],
                colors="#006f8f",
                linewidths=1.25,
                alpha=0.95,
                zorder=5,
            )
        ax.plot([], [], color="#00a6d6", linewidth=6, alpha=0.45, label=f"{label} power region")
    else:
        ax.text(
            0.5,
            0.5,
            "No positive power bins",
            transform=ax.transAxes,
            fontsize=12,
            ha="center",
            va="center",
            bbox={"facecolor": "white", "edgecolor": "#777777", "alpha": 0.9, "pad": 5.0},
            zorder=6,
        )

    max_theta = math.radians(result["Az_max_flux_deg"])
    max_zenith = 90.0 - result["El_max_flux_deg"]
    if result["TotalPower_W"] > 0.0 and np.isfinite(max_theta) and np.isfinite(max_zenith):
        ax.scatter(
            max_theta,
            max_zenith,
            marker="*",
            s=150,
            c="#ffd166",
            edgecolors="black",
            linewidths=0.9,
            label="Maximum flux",
            zorder=9,
        )
        ax.annotate(
            f"{result['MaxFlux_W_m2']:.2f} W/m$^2$",
            xy=(max_theta, max_zenith),
            xytext=(18, 18),
            textcoords="offset points",
            fontsize=9,
            color="black",
            bbox={"facecolor": "white", "edgecolor": "#555555", "alpha": 0.88, "pad": 3.0},
            arrowprops={"arrowstyle": "->", "color": "#333333", "linewidth": 0.9},
            zorder=11,
        )

    if has_sun_position(result):
        sun_zenith = 90.0 - result["SunElevation_deg"]
        if 0.0 <= sun_zenith <= 90.0:
            sun_theta = math.radians(result["SunAzimuth_deg"])
            ax.scatter(
                sun_theta,
                sun_zenith,
                marker="o",
                s=190,
                c="yellow",
                edgecolors="black",
                linewidths=1.0,
                label="Sun",
                zorder=8,
            )
            ax.annotate(
                "Sun",
                xy=(sun_theta, sun_zenith),
                xytext=(10, 10),
                textcoords="offset points",
                fontsize=10,
                weight="bold",
                color="black",
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.75, "pad": 1.5},
                zorder=10,
            )

    annotate_summary(ax, result, label)
    ax.set_title(
        "\n".join((
            f"{day_name} flux concentration, {result['TimeBasis']} {result['time_label']}, R = {result['Radius_m']:g} m",
            (
                f"{label} = {result['Top90SolidAngle_sr']:.3f} sr "
                f"({result['Top90HemispherePercent']:.2f}% hemisphere); "
                f"max flux = {result['MaxFlux_W_m2']:.2f} W/m$^2$"
            ),
        )),
        fontsize=12,
        pad=20,
    )
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(handles, labels, loc="lower left", bbox_to_anchor=(0.0, -0.08), fontsize=8)
    fig.savefig(path, dpi=dpi)
    plt.close(fig)


def write_summary_csv(path, results):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(SUMMARY_COLUMNS)
        for result in results:
            writer.writerow([
                result["time_label"],
                result["hour"],
                result["TimeBasis"],
                result["point_name"],
                f"{result['Radius_m']:.10g}",
                f"{result['TotalPower_W']:.17g}",
                f"{result['Top90SolidAngle_sr']:.17g}",
                f"{result['Top90HemispherePercent']:.10g}",
                result["Top90BinCount"],
                result["TotalBinCount"],
                f"{result['MaxFlux_W_m2']:.2f}",
                f"{result['Az_max_flux_deg']:.10g}",
                f"{result['El_max_flux_deg']:.10g}",
                "" if result["SunAzimuth_deg"] is None else f"{result['SunAzimuth_deg']:.10g}",
                "" if result["SunElevation_deg"] is None else f"{result['SunElevation_deg']:.10g}",
                "" if result["DNI_W_m2"] is None else f"{result['DNI_W_m2']:.10g}",
                result["OutputPng"],
            ])


def parse_args():
    parser = argparse.ArgumentParser(
        description="Plot hourly power-ranked sky concentration maps from hemisphere flux CSV files."
    )
    parser.add_argument("input_folder", help="Day folder containing Point_<n> hemisphere flux CSV files.")
    parser.add_argument("--radii", nargs="+", type=float, default=DEFAULT_RADII, help="Hemisphere radii in meters.")
    parser.add_argument(
        "--point-hour-offset",
        type=int,
        default=-3,
        help="Offset added to Point_<n> folder numbers to infer local solar hour.",
    )
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--top-fraction", type=float, default=0.90)
    parser.add_argument("--dpi", type=int, default=180)
    parser.add_argument("--show-empty", action="store_true", help="Write annotated plots for zero-power CSV files.")
    parser.add_argument("--sun-positions-csv", default=None, help="Day-level CSV mapping Point_<n> folders to Sun position.")
    return parser.parse_args()


def main():
    args = parse_args()
    if not (0.0 < args.top_fraction <= 1.0):
        raise ValueError("--top-fraction must be greater than 0 and no greater than 1")
    if args.dpi <= 0:
        raise ValueError("--dpi must be positive")
    if any(radius <= 0.0 for radius in args.radii):
        raise ValueError("--radii values must be positive")

    input_folder = Path(args.input_folder)
    if not input_folder.is_dir():
        raise ValueError(f"Input folder does not exist or is not a directory: {input_folder}")

    output_dir = input_folder / "hourly_flux_concentration_maps" if args.output_dir is None else Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sun_positions = None
    if args.sun_positions_csv is not None:
        sun_positions_path = Path(args.sun_positions_csv)
        if not sun_positions_path.is_file():
            raise ValueError(f"Sun positions CSV does not exist or is not a file: {sun_positions_path}")
        sun_positions = read_sun_positions_csv(sun_positions_path)

    discovered = discover_flux_files(input_folder, args.radii, args.point_hour_offset)
    if not discovered:
        raise ValueError(f"No requested hemisphere_flux_R<m>m.csv files found under: {input_folder}")

    discovered_radii = {radius for _, radius, _ in discovered}
    for radius in sorted(set(float(radius) for radius in args.radii) - discovered_radii):
        print(f"Warning: no hemisphere flux CSV files found for radius {radius:g} m under {input_folder}")

    results = []
    written_count = 0
    warned_missing_sun_points = set()
    for hour, radius, csv_path in discovered:
        result, data, top_mask = analyze_flux_file(input_folder, hour, radius, csv_path, args.top_fraction)
        apply_sun_position(result, sun_positions, warned_missing_sun_points)
        if result["TotalPower_W"] > 0.0 or args.show_empty:
            png_path = output_dir / output_png_name(result)
            write_concentration_plot(png_path, input_folder.name, result, data, top_mask, args.top_fraction, args.dpi)
            result["OutputPng"] = png_path.name
            written_count += 1
        else:
            print(f"Skipped zero-power plot for {result['point_name']} R={radius:g} m")
        results.append(result)

    results.sort(key=lambda result: (result["hour"], result["Radius_m"]))
    summary_csv = output_dir / "hourly_flux_concentration_maps.csv"
    write_summary_csv(summary_csv, results)

    skipped_count = len(results) - written_count
    print(f"Processed {len(results)} hour/radius combinations.")
    print(f"Wrote {written_count} PNG map(s); skipped {skipped_count} zero-power map(s).")
    print(f"Wrote {summary_csv}")
    print(f"Time basis: {TIME_BASIS}")


if __name__ == "__main__":
    main()
