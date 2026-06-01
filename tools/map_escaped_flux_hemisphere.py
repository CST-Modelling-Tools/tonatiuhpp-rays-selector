import argparse
import csv
import math
from pathlib import Path

import numpy as np


def metadata_path_for(input_file):
    path = Path(input_file)
    if path.suffix.lower() == ".dat":
        return path.with_name(f"{path.stem}_parameters.txt")
    return path.with_name(f"{path.name}_parameters.txt")


def read_power_per_ray(metadata_path):
    lines = metadata_path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.strip() != "PowerPerRay":
            continue
        for value_line in lines[index + 1:]:
            value_line = value_line.strip()
            if not value_line:
                continue
            return float(value_line)
    raise ValueError(f"PowerPerRay not found in metadata file: {metadata_path}")


def read_escaped_rays(input_file):
    data = np.fromfile(input_file, dtype=">f8")
    if data.size % 6 != 0:
        raise ValueError(f"Invalid escaped-ray file: expected a multiple of 6 doubles, got {data.size}")
    rays = data.reshape((-1, 6))
    return rays[np.all(np.isfinite(rays), axis=1)]


def positive_sphere_intersections(rays, center, radius):
    origins = rays[:, 0:3] - center
    directions = rays[:, 3:6]

    a = np.einsum("ij,ij->i", directions, directions)
    b = 2.0 * np.einsum("ij,ij->i", origins, directions)
    c = np.einsum("ij,ij->i", origins, origins) - radius * radius
    discriminant = b * b - 4.0 * a * c

    valid = (a > 0.0) & (discriminant >= 0.0)
    if not np.any(valid):
        return np.empty((0, 3))

    valid_indices = np.flatnonzero(valid)
    sqrt_disc = np.sqrt(discriminant[valid])
    denom = 2.0 * a[valid]
    t1 = (-b[valid] - sqrt_disc) / denom
    t2 = (-b[valid] + sqrt_disc) / denom

    eps = 1.0e-12
    t = np.where((t1 > eps) & ((t1 <= t2) | (t2 <= eps)), t1, t2)
    forward = t > eps
    if not np.any(forward):
        return np.empty((0, 3))

    ray_indices = valid_indices[forward]
    return origins[ray_indices] + t[forward, np.newaxis] * directions[ray_indices]


def spherical_angles(points, radius):
    east = points[:, 0]
    north = points[:, 1]
    up = points[:, 2]

    azimuth = (np.degrees(np.arctan2(east, north)) + 360.0) % 360.0
    elevation = np.degrees(np.arcsin(np.clip(up / radius, -1.0, 1.0)))
    zenith = 90.0 - elevation

    hemisphere = (elevation >= 0.0) & (zenith >= 0.0) & (zenith <= 90.0)
    return azimuth[hemisphere], elevation[hemisphere], zenith[hemisphere]


def bin_flux(azimuth, zenith, radius, az_bins, zenith_bins, power_per_ray):
    az_edges = np.linspace(0.0, 360.0, az_bins + 1)
    zenith_edges = np.linspace(0.0, 90.0, zenith_bins + 1)
    counts, _, _ = np.histogram2d(azimuth, zenith, bins=(az_edges, zenith_edges))

    delta_az = math.radians(360.0 / az_bins)
    zenith_inner = np.radians(zenith_edges[:-1])
    zenith_outer = np.radians(zenith_edges[1:])
    areas = radius * radius * delta_az * (np.cos(zenith_inner) - np.cos(zenith_outer))

    power = counts * power_per_ray
    flux = np.divide(power, areas[np.newaxis, :], out=np.zeros_like(power), where=areas[np.newaxis, :] > 0.0)
    return az_edges, zenith_edges, counts, power, flux


def write_csv(path, az_edges, zenith_edges, counts, power, flux):
    az_centers = 0.5 * (az_edges[:-1] + az_edges[1:])
    zenith_centers = 0.5 * (zenith_edges[:-1] + zenith_edges[1:])

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([
            "azimuth_center_deg",
            "elevation_center_deg",
            "zenith_center_deg",
            "ray_count",
            "power_W",
            "flux_W_m2",
        ])
        for az_index, az_center in enumerate(az_centers):
            for zenith_index, zenith_center in enumerate(zenith_centers):
                writer.writerow([
                    f"{az_center:.10g}",
                    f"{90.0 - zenith_center:.10g}",
                    f"{zenith_center:.10g}",
                    int(counts[az_index, zenith_index]),
                    f"{power[az_index, zenith_index]:.17g}",
                    f"{flux[az_index, zenith_index]:.17g}",
                ])


def radius_label(radius):
    return f"{radius:g}".replace("-", "neg").replace(".", "p")


def require_matplotlib():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.colors as mpl_colors
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "matplotlib is required to write PNG hemisphere maps. Install matplotlib or run in an environment that provides it."
        ) from exc

    return mpl_colors, plt


def choose_norm(flux, vmax, log_scale, mpl_colors):
    if not log_scale:
        return mpl_colors.Normalize(vmin=0.0, vmax=vmax)

    positive = flux[flux > 0.0]
    if positive.size == 0:
        return mpl_colors.LogNorm(vmin=1.0, vmax=max(vmax or 1.0, 1.0))

    vmin = positive.min()
    norm_vmax = vmax if vmax is not None else positive.max()
    if norm_vmax <= vmin:
        norm_vmax = vmin * 10.0
    return mpl_colors.LogNorm(vmin=vmin, vmax=norm_vmax)


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


def title_line_one(radius, args):
    dni_text = f"{args.dni:g} W/m²" if args.dni is not None else "not provided"
    if args.sun_azimuth_deg is not None and args.sun_elevation_deg is not None:
        sun_text = f"az = {args.sun_azimuth_deg:g}, elev = {args.sun_elevation_deg:g}"
    else:
        sun_text = "not provided"
    return f"Hemisphere flux, R = {radius:g} m; DNI = {dni_text}; Sun position: {sun_text}"


def contour_levels(flux):
    max_flux = float(np.max(flux)) if flux.size else 0.0
    min_flux = float(np.min(flux)) if flux.size else 0.0
    if max_flux <= 0.0 or max_flux <= min_flux:
        return []

    levels = [max_flux * fraction for fraction in (0.10, 0.25, 0.50, 0.75, 0.90)]
    return [level for level in levels if min_flux < level < max_flux]


def write_plot(path, radius, az_edges, zenith_edges, flux, total_power, rays_used, args):
    _ = total_power, rays_used
    mpl_colors, plt = require_matplotlib()
    theta_edges = np.radians(az_edges)
    zenith_edge_grid, theta_edge_grid = np.meshgrid(zenith_edges, theta_edges, indexing="ij")
    plot_values = np.ma.masked_less_equal(flux.T, 0.0) if args.log_scale else flux.T

    fig, ax = plt.subplots(figsize=(10, 9), subplot_kw={"projection": "polar"}, constrained_layout=True)
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_ylim(0.0, 90.0)
    elevation_ticks = [90, 75, 60, 45, 30, 15, 0]
    zenith_ticks = [90.0 - elevation for elevation in elevation_ticks]
    ax.set_yticks(zenith_ticks)
    ax.set_yticklabels([degree_label(elevation) for elevation in elevation_ticks])
    ax.set_rlabel_position(225)
    azimuth_ticks = list(range(0, 360, 30))
    ax.set_thetagrids(azimuth_ticks, labels=azimuth_grid_labels())
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
        norm=choose_norm(flux, args.vmax, args.log_scale, mpl_colors),
        shading="auto",
    )
    colorbar = fig.colorbar(mesh, ax=ax, pad=0.08, shrink=0.86)
    colorbar.set_label("Flux [W/m$^2$]")

    max_index = np.unravel_index(np.argmax(flux), flux.shape)
    az_centers = 0.5 * (az_edges[:-1] + az_edges[1:])
    zenith_centers = 0.5 * (zenith_edges[:-1] + zenith_edges[1:])
    max_flux = flux[max_index]
    max_azimuth = az_centers[max_index[0]]
    max_zenith = zenith_centers[max_index[1]]
    max_elevation = 90.0 - max_zenith

    levels = contour_levels(flux)
    if levels:
        theta_centers = np.radians(az_centers)
        zenith_center_grid, theta_center_grid = np.meshgrid(zenith_centers, theta_centers, indexing="ij")
        ax.contour(
            theta_center_grid,
            zenith_center_grid,
            flux.T,
            levels=levels,
            colors="white",
            linewidths=0.75,
            alpha=0.75,
        )

    if max_flux > 0.0:
        max_theta = math.radians(max_azimuth)
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
        annotation_text = (
            f"Max flux = {max_flux:.2f} W/m$^2$\n"
            f"Az = {max_azimuth:.1f}\N{DEGREE SIGN}\n"
            f"El = {max_elevation:.1f}\N{DEGREE SIGN}"
        )
        ax.annotate(
            annotation_text,
            xy=(max_theta, max_zenith),
            xytext=(24, 24),
            textcoords="offset points",
            fontsize=9,
            color="black",
            bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": "#555555", "alpha": 0.88},
            arrowprops={"arrowstyle": "->", "color": "white", "linewidth": 1.0},
            zorder=7,
        )

    if args.sun_azimuth_deg is not None and args.sun_elevation_deg is not None:
        sun_zenith = 90.0 - args.sun_elevation_deg
        if 0.0 <= sun_zenith <= 90.0:
            sun_theta = math.radians(args.sun_azimuth_deg)
            ax.scatter(
                sun_theta,
                sun_zenith,
                marker="o",
                s=190,
                c="gold",
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
                zorder=9,
            )

    title = "\n".join((
        title_line_one(radius, args),
        (
            f"Max. Flux = {max_flux:.2f} W/m² at az = {ordinal_degree_label(max_azimuth)}, "
            f"elev = {ordinal_degree_label(max_elevation)}"
        ),
    ))
    ax.set_title(title, fontsize=12, pad=20)

    fig.savefig(path, dpi=180)
    plt.close(fig)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Map compact escaped-ray flux onto sky-dome hemispheres."
    )
    parser.add_argument("input_file", help="Escaped-ray .dat file with x y z dx dy dz big-endian double records.")
    parser.add_argument("--radius", nargs="+", type=float, required=True, help="One or more hemisphere radii in meters.")
    parser.add_argument("--center", nargs=3, type=float, default=(0.0, 0.0, 0.0), metavar=("X", "Y", "Z"))
    parser.add_argument("--az-bins", type=int, default=180)
    parser.add_argument("--zenith-bins", type=int, default=90)
    parser.add_argument("--power-per-ray", type=float, default=None, help="Override metadata PowerPerRay value.")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--sun-azimuth-deg", type=float, default=None)
    parser.add_argument("--sun-elevation-deg", type=float, default=None)
    parser.add_argument("--dni", type=float, default=None)
    parser.add_argument("--vmax", type=float, default=None)
    parser.add_argument("--log-scale", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.az_bins <= 0 or args.zenith_bins <= 0:
        raise ValueError("--az-bins and --zenith-bins must be positive")
    if any(radius <= 0.0 for radius in args.radius):
        raise ValueError("--radius values must be positive")
    if args.vmax is not None and args.vmax <= 0.0:
        raise ValueError("--vmax must be positive")
    if (args.sun_azimuth_deg is None) != (args.sun_elevation_deg is None):
        raise ValueError("--sun-azimuth-deg and --sun-elevation-deg must be provided together")

    input_file = Path(args.input_file)
    power_per_ray = args.power_per_ray
    if power_per_ray is None:
        metadata_path = metadata_path_for(input_file)
        power_per_ray = read_power_per_ray(metadata_path)
    if power_per_ray < 0.0:
        raise ValueError("PowerPerRay must be non-negative")

    rays = read_escaped_rays(input_file)
    center = np.array(args.center, dtype=np.float64)
    output_dir = input_file.parent if args.output_dir is None else Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loaded {len(rays)} finite escaped-ray records")
    print(f"PowerPerRay = {power_per_ray:.17g} W")

    for radius in args.radius:
        points = positive_sphere_intersections(rays, center, radius)
        azimuth, elevation, zenith = spherical_angles(points, radius)
        az_edges, zenith_edges, counts, power, flux = bin_flux(
            azimuth,
            zenith,
            radius,
            args.az_bins,
            args.zenith_bins,
            power_per_ray,
        )

        label = radius_label(radius)
        csv_path = output_dir / f"hemisphere_flux_R{label}m.csv"
        png_path = output_dir / f"hemisphere_flux_R{label}m.png"
        write_csv(csv_path, az_edges, zenith_edges, counts, power, flux)
        write_plot(png_path, radius, az_edges, zenith_edges, flux, power.sum(), int(counts.sum()), args)

        print(
            f"R={radius:g} m: used {int(counts.sum())} rays, "
            f"total power {power.sum():.17g} W, max flux {flux.max():.17g} W/m^2"
        )
        print(f"  wrote {csv_path}")
        print(f"  wrote {png_path}")


if __name__ == "__main__":
    main()
