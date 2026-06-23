"""Compare hourly maximum flux with Top90 concentration bubble sizes."""

import argparse
import csv
from pathlib import Path

from analyze_hourly_flux_concentration import radius_label
from compare_hourly_flux_concentration import (
    format_value,
    global_max,
    output_columns,
    parse_case_argument,
    read_case,
    rows_for_radius,
    select_radii,
)


SUMMARY_CSV_NAME = "hourly_flux_concentration.csv"


def require_matplotlib():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("matplotlib is required to write maximum-flux bubble plots.") from exc

    return plt


def resolve_summary_csv(path):
    if path.is_dir():
        return path / SUMMARY_CSV_NAME
    return path


def read_cases(case_arguments):
    parsed_cases = [parse_case_argument(value) for value in case_arguments]
    labels = [label for label, _ in parsed_cases]
    duplicates = sorted({label for label in labels if labels.count(label) > 1})
    if duplicates:
        raise ValueError(f"Duplicate technology label(s): {', '.join(duplicates)}")

    return [
        read_case(label, resolve_summary_csv(path))
        for label, path in parsed_cases
    ]


def time_ticks_for_radius(cases, radius):
    by_hour = {}
    for case in cases:
        for row in rows_for_radius(case, radius):
            by_hour.setdefault(row["hour"], row["time_label"])
    hours = sorted(by_hour)
    return hours, [by_hour[hour] for hour in hours]


def bubble_marker_areas(percentages, percent_max, radius_at_max):
    areas = []
    for value in percentages:
        clipped = min(max(value, 0.0), percent_max)
        radius = radius_at_max * clipped / percent_max
        areas.append(radius * radius)
    return areas


def bubble_legend_values(percent_max):
    candidates = [1.0, 2.0, 4.0]
    values = [value for value in candidates if value <= percent_max]
    if values and values[-1] == percent_max:
        return values
    return values + [percent_max]


def write_selected_csv(path, cases, radii):
    rows = [
        row
        for case in cases
        for row in case["rows"]
        if row["Radius_m"] in radii
    ]
    rows.sort(key=lambda row: (row["Technology"], row["Radius_m"], row["hour"]))

    columns = output_columns()
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([format_value(row, column) for column in columns])


def write_bubble_plot(
    path,
    cases,
    radius,
    flux_ymax,
    title_prefix,
    bubble_percent_max,
    bubble_radius_at_max,
    dpi,
):
    plt = require_matplotlib()
    fig, ax = plt.subplots(figsize=(12.5, 6))
    fig.subplots_adjust(bottom=0.16, right=0.72)
    colors = plt.get_cmap("tab10")

    for case_index, case in enumerate(cases):
        rows = rows_for_radius(case, radius)
        x_values = [row["hour"] for row in rows]
        flux_values = [row["MaxFlux_W_m2"] for row in rows]
        top90_percentages = [row["Top90HemispherePercent"] for row in rows]
        color = colors(case_index % 10)

        ax.plot(
            x_values,
            flux_values,
            color=color,
            linewidth=1.7,
            label=case["label"],
            zorder=2,
        )
        ax.scatter(
            x_values,
            flux_values,
            s=bubble_marker_areas(top90_percentages, bubble_percent_max, bubble_radius_at_max),
            color=color,
            edgecolors="black",
            linewidths=0.65,
            alpha=0.72,
            zorder=3,
        )

    ticks, tick_labels = time_ticks_for_radius(cases, radius)
    ax.set_xticks(ticks)
    ax.set_xticklabels(tick_labels)
    ax.set_xlabel("Solar time")
    ax.set_ylabel("Maximum flux [W/m$^2$]")
    ax.set_title(f"{title_prefix} hourly maximum escaped flux, R = {radius:g} m")
    ax.set_ylim(0.0, flux_ymax if flux_ymax > 0.0 else 1.0)
    ax.grid(True, alpha=0.35)

    technology_legend = ax.legend(
        title="Technology",
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        borderaxespad=0.0,
        fontsize=9,
        title_fontsize=10,
    )
    ax.add_artist(technology_legend)

    legend_values = bubble_legend_values(bubble_percent_max)
    legend_handles = [
        ax.scatter(
            [],
            [],
            s=bubble_marker_areas([value], bubble_percent_max, bubble_radius_at_max)[0],
            facecolors="white",
            edgecolors="#444444",
            linewidths=0.8,
        )
        for value in legend_values
    ]
    bubble_legend = ax.legend(
        legend_handles,
        [f"{value:g}%" for value in legend_values],
        title="Top90 hemisphere",
        loc="lower left",
        bbox_to_anchor=(1.01, 0.0),
        borderaxespad=0.0,
        scatterpoints=1,
        fontsize=9,
        title_fontsize=10,
    )

    fig.savefig(path, dpi=dpi, bbox_inches="tight", bbox_extra_artists=(technology_legend, bubble_legend))
    plt.close(fig)


def write_plots(output_dir, cases, radii, flux_ymax, title_prefix, bubble_percent_max, bubble_radius_at_max, dpi):
    written = []
    for radius in radii:
        path = output_dir / f"comparison_max_flux_bubbles_R{radius_label(radius)}m.png"
        write_bubble_plot(
            path,
            cases,
            radius,
            flux_ymax,
            title_prefix,
            bubble_percent_max,
            bubble_radius_at_max,
            dpi,
        )
        written.append(path)
    return written


def max_top90_percentage(cases, radii):
    values = [
        row["Top90HemispherePercent"]
        for case in cases
        for row in case["rows"]
        if row["Radius_m"] in radii
    ]
    return max(values) if values else 0.0


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Plot hourly maximum escaped flux across technology cases, with bubble radius "
            "proportional to Top90 hemisphere percentage."
        )
    )
    parser.add_argument(
        "--case",
        action="append",
        required=True,
        help=(
            "Technology label=SpringEquinox folder or path/to/hourly_flux_concentration.csv. "
            "May be repeated."
        ),
    )
    parser.add_argument("--radii", nargs="+", type=float, default=None, help="Radii in meters to plot.")
    parser.add_argument("--output-dir", default=".", help="Folder for comparison CSV and PNG outputs.")
    parser.add_argument("--flux-ymax", type=float, default=None, help="Override maximum-flux plot y-axis maximum.")
    parser.add_argument("--title-prefix", default="Spring Equinox")
    parser.add_argument(
        "--bubble-percent-max",
        type=float,
        default=4.0,
        help="Top90 hemisphere percentage represented by the largest bubble radius.",
    )
    parser.add_argument(
        "--bubble-radius-at-max",
        type=float,
        default=24.0,
        help="Matplotlib marker radius proxy, in points, for --bubble-percent-max.",
    )
    parser.add_argument("--dpi", type=int, default=180)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.dpi <= 0:
        raise ValueError("--dpi must be positive")
    if args.flux_ymax is not None and args.flux_ymax <= 0.0:
        raise ValueError("--flux-ymax must be positive")
    if args.bubble_percent_max <= 0.0:
        raise ValueError("--bubble-percent-max must be positive")
    if args.bubble_radius_at_max <= 0.0:
        raise ValueError("--bubble-radius-at-max must be positive")

    cases = read_cases(args.case)
    radii = select_radii(cases, args.radii)
    flux_ymax = args.flux_ymax if args.flux_ymax is not None else global_max(cases, radii, "MaxFlux_W_m2") * 1.05

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    comparison_csv = output_dir / "hourly_max_flux_bubble_comparison.csv"
    write_selected_csv(comparison_csv, cases, radii)
    written_plots = write_plots(
        output_dir,
        cases,
        radii,
        flux_ymax,
        args.title_prefix,
        args.bubble_percent_max,
        args.bubble_radius_at_max,
        args.dpi,
    )

    top90_max = max_top90_percentage(cases, radii)
    print(f"Compared {len(cases)} technology case(s) at radii: {', '.join(f'{radius:g}' for radius in radii)} m")
    print(f"Bubble radius scale: 0 to {args.bubble_percent_max:.10g} % Top90 hemisphere")
    if top90_max > args.bubble_percent_max:
        print(
            f"Warning: maximum Top90 percentage is {top90_max:.10g} %, "
            "so larger bubbles were clipped to the configured scale."
        )
    print(f"Maximum-flux y-axis maximum: {flux_ymax:.10g} W/m^2")
    print(f"Wrote {comparison_csv}")
    for path in written_plots:
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
