import argparse

import numpy as np
import plotly.graph_objects as go


def read_rays(path, max_rays=None):
    data = np.fromfile(path, dtype=">f8")

    if data.size % 6 != 0:
        raise ValueError(f"Invalid file: expected multiple of 6 doubles, got {data.size}")

    rays = data.reshape((-1, 6))

    finite_mask = np.all(np.isfinite(rays), axis=1)
    rays = rays[finite_mask]

    if max_rays is not None:
        rays = rays[:max_rays]

    return rays


def make_ray_lines(origins, endpoints):
    x = []
    y = []
    z = []

    for origin, endpoint in zip(origins, endpoints):
        x.extend([origin[0], endpoint[0], None])
        y.extend([origin[1], endpoint[1], None])
        z.extend([origin[2], endpoint[2], None])

    return x, y, z


def main():
    parser = argparse.ArgumentParser(description="Visualize compact escaped-ray records.")
    parser.add_argument("input_file", help="Binary .dat file with x y z dx dy dz records.")
    parser.add_argument("--length", type=float, default=10.0)
    parser.add_argument("--max-rays", type=int, default=1000)
    parser.add_argument("--html", default=None, help="Optional HTML output file.")

    args = parser.parse_args()

    rays = read_rays(args.input_file, args.max_rays)

    if len(rays) == 0:
        print("No rays found.")
        return

    origins = rays[:, 0:3]
    directions = rays[:, 3:6]
    endpoints = origins + args.length * directions

    norms = np.linalg.norm(directions, axis=1)
    print(f"Loaded {len(rays)} rays")
    print(f"Direction norm min:  {norms.min():.16g}")
    print(f"Direction norm max:  {norms.max():.16g}")
    print(f"Direction norm mean: {norms.mean():.16g}")

    line_x, line_y, line_z = make_ray_lines(origins, endpoints)

    fig = go.Figure()

    fig.add_trace(
        go.Scatter3d(
            x=line_x,
            y=line_y,
            z=line_z,
            mode="lines",
            line=dict(width=2, color="black"),
            name="ray",
        )
    )

    fig.add_trace(
        go.Scatter3d(
            x=origins[:, 0],
            y=origins[:, 1],
            z=origins[:, 2],
            mode="markers",
            marker=dict(size=3, color="blue"),
            name="origin",
        )
    )

    fig.add_trace(
        go.Scatter3d(
            x=endpoints[:, 0],
            y=endpoints[:, 1],
            z=endpoints[:, 2],
            mode="markers",
            marker=dict(size=3, color="red"),
            name="tip",
        )
    )

    fig.update_layout(
        title=f"Escaped rays: {len(rays)} shown, length = {args.length}",
        scene=dict(
            xaxis_title="X",
            yaxis_title="Y",
            zaxis_title="Z",
            aspectmode="data",
        ),
        legend=dict(x=0.01, y=0.99),
    )

    if args.html:
        fig.write_html(args.html)
        print(f"Wrote {args.html}")

    fig.show()


if __name__ == "__main__":
    main()