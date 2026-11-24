"""Generate the 8 coursework charts from results/controlled.csv.

Usage (from the repo root):
    python -m experiments.plot_charts results/controlled.csv --output results/charts

Instance size (steps, users) and constraint composition are read from the instance
files, using the paths stored in the CSV (relative to the repo root).
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

import matplotlib
import matplotlib.ticker
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shared.parser import parse_wsp  # noqa: E402

SOLVERS = ["a1", "a2", "a3", "a4", "a5"]
LABEL = {"a1": "A1 CNF + Z3", "a2": "A2 Integer + Z3", "a3": "A3 Boolean + Z3",
         "a4": "A4 CNF + PySAT", "a5": "A5 CNF + CP-SAT"}
COLOUR = {"a1": "#1f77b4", "a2": "#ff7f0e", "a3": "#2ca02c", "a4": "#d62728", "a5": "#9467bd"}
GROUP_ORDER = ["1-constraint-small", "3-constraint-small", "4-constraint-small",
               "5-constraint-small", "3-constraint", "4-constraint", "5-constraint",
               "4-constraint-hard"]
KINDS = ["authorisations", "separation-of-duty", "binding-of-duty", "at-most-k", "one-team"]
KIND_COLOUR = dict(zip(KINDS, ["#8da0cb", "#fc8d62", "#66c2a5", "#e78ac3", "#a6d854"]))
COMPONENTS = ["loading_time_ms", "encoding_time_ms", "solve_time_ms", "decode_time_ms"]
COMP_LABEL = {"loading_time_ms": "Loading", "encoding_time_ms": "Encoding",
              "solve_time_ms": "Solving", "decode_time_ms": "Decoding"}
COMP_COLOUR = {"loading_time_ms": "#9ecae1", "encoding_time_ms": "#fdae6b",
               "solve_time_ms": "#74c476", "decode_time_ms": "#bcbddc"}


def short(g):
    return g.replace("-constraint", "c").replace("-small", " (small)").replace("-hard", " (hard)")


def load(path):
    d = pd.read_csv(path)
    feats = []
    for p in d.instance.unique():
        inst = parse_wsp(ROOT / p)
        cnt = Counter(c.kind for c in inst.constraints)
        feats.append({"instance": p, "steps": inst.num_steps, "users": inst.num_users,
                      "n_constraints": len(inst.constraints), **{k: cnt.get(k, 0) for k in KINDS}})
    d = d.merge(pd.DataFrame(feats), on="instance")
    d["group"] = d.instance.str.split("/").str[-2]
    d["solved"] = d.status.isin(["sat", "unsat"])
    return d


def grouped_bars(ax, table, solvers, groups):
    w = 0.8 / len(solvers)
    x = np.arange(len(groups))
    for i, s in enumerate(solvers):
        vals = [table.get((g, s), np.nan) for g in groups]
        ax.bar(x + (i - (len(solvers) - 1) / 2) * w, vals, w, label=LABEL[s], color=COLOUR[s])
    ax.set_xticks(x)
    ax.set_xticklabels([short(g) for g in groups], rotation=30, ha="right")


def save(fig, out, name):
    fig.tight_layout()
    fig.savefig(out / name, dpi=200)
    plt.close(fig)
    print("wrote", out / name)


def compare_chart(d, solvers, title, out, name):
    ok = d[d.solved & d.solver.isin(solvers)]
    groups = [g for g in GROUP_ORDER if g in set(ok.group)]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    for ax, col, lab in zip(axes, ["total_time_ms", "solve_time_ms"],
                            ["Median total time (ms)", "Median solve time (ms)"]):
        tab = ok.groupby(["group", "solver"])[col].median().to_dict()
        grouped_bars(ax, tab, solvers, groups)
        ax.set_yscale("log")
        ax.set_ylabel(lab + ", log scale")
        ax.set_title(lab)
        ax.grid(axis="y", alpha=0.3)
    axes[0].legend()
    fig.suptitle(title + "\n(4-constraint-hard omitted: every solver timed out)")
    save(fig, out, name)


def chart3(d, out):
    ok = d[d.solved]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    timeout_ms = d[d.status == "timeout"].wall_s.median() * 1000
    hard = d[d.status == "timeout"].drop_duplicates("instance")
    for ax, col, lab in zip(axes, ["steps", "users"], ["Number of steps", "Number of users"]):
        for s in SOLVERS:
            m = ok[ok.solver == s].groupby(col).total_time_ms.median()
            ax.plot(m.index, m.values, "o-", color=COLOUR[s], label=LABEL[s])
        if len(hard):
            ax.plot(hard[col].iloc[0], timeout_ms, "X", color="black", markersize=11,
                    label="All 5 solvers timed out")
            ax.axhline(timeout_ms, color="black", ls=":", lw=1, alpha=0.5)
        ax.set_xscale("log"); ax.set_yscale("log")
        ticks = sorted(d[col].unique())
        ax.set_xticks(ticks)
        ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
        ax.minorticks_off() if False else ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        ax.set_xlabel(lab + " (log scale)")
        ax.set_ylabel("Median total time (ms, log scale)")
        ax.set_title(f"Runtime vs {lab.lower()}")
        ax.grid(alpha=0.3, which="major")
    axes[0].legend(fontsize=8, loc="center right")
    fig.suptitle(f"Scalability (dotted line = ~{timeout_ms/1000:.0f} s timeout; "
                 "largest instances: 60 steps, 500 users)")
    save(fig, out, "3_scalability.png")


def chart4(d, out):
    groups = [g for g in GROUP_ORDER if g in set(d.group)]
    inst = d.drop_duplicates("instance")
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5))
    ax = axes[0]
    bottom = np.zeros(len(groups))
    mean = inst.groupby("group")[KINDS].mean()
    share = mean.div(mean.sum(axis=1), axis=0) * 100
    for k in KINDS:
        vals = np.array([share.loc[g, k] for g in groups])
        ax.bar(range(len(groups)), vals, bottom=bottom, label=k, color=KIND_COLOUR[k])
        bottom += vals
    for i, g in enumerate(groups):
        ax.text(i, 101, f"{mean.loc[g].sum():.0f}", ha="center", fontsize=8)
    ax.set_ylim(0, 110)
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels([short(g) for g in groups], rotation=30, ha="right")
    ax.set_ylabel("Share of constraints (%)")
    ax.set_title("Constraint mix per dataset (number above bar = mean constraints)")
    ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=3)
    ax = axes[1]
    ok = d[d.solved]
    for s in SOLVERS:
        m = ok[ok.solver == s].groupby("group").total_time_ms.median()
        ax.plot([short(g) for g in groups if g in m.index], [m[g] for g in groups if g in m.index],
                "o-", color=COLOUR[s], label=LABEL[s])
    ax.set_yscale("log")
    ax.set_ylabel("Median total time (ms, log scale)")
    ax.set_title("Runtime by dataset (hard set omitted: all timed out)")
    ax.tick_params(axis="x", rotation=30)
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=8)
    fig.suptitle("Performance across constraint types / compositions")
    save(fig, out, "4_constraint_composition.png")


def chart5(d, out):
    ok = d[d.solved]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    for ax, agg, lab in zip(axes, ["median", "mean"], ["Median", "Mean"]):
        tab = ok.groupby("solver")[COMPONENTS].agg(agg).loc[SOLVERS]
        bottom = np.zeros(len(SOLVERS))
        for c in COMPONENTS:
            ax.bar([LABEL[s] for s in SOLVERS], tab[c], bottom=bottom, label=COMP_LABEL[c],
                   color=COMP_COLOUR[c])
            bottom += tab[c].values
        ax.set_ylabel(f"{lab} time per instance (ms)")
        ax.set_title(f"{lab} runtime breakdown")
        ax.tick_params(axis="x", rotation=20)
        ax.grid(axis="y", alpha=0.3)
    axes[0].legend()
    fig.suptitle("Runtime breakdown: loading, encoding, solving, decoding (solved instances)")
    save(fig, out, "5_runtime_breakdown.png")


def chart6(d, out):
    ok = d[d.solved]
    sets = [("Small instances", [g for g in GROUP_ORDER if g.endswith("small")]),
            ("Standard instances (3c / 4c / 5c)", ["3-constraint", "4-constraint", "5-constraint"])]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), sharey=True)
    for ax, (title, groups) in zip(axes, sets):
        sub = ok[ok.group.isin(groups)]
        data = [sub[sub.solver == s].total_time_ms.values for s in SOLVERS]
        bp = ax.boxplot(data, tick_labels=[LABEL[s] for s in SOLVERS], patch_artist=True, showfliers=True)
        for patch, s in zip(bp["boxes"], SOLVERS):
            patch.set_facecolor(COLOUR[s]); patch.set_alpha(0.7)
        for med in bp["medians"]:
            med.set_color("black")
        ax.set_yscale("log")
        ax.set_title(f"{title} (n={len(sub)//5} instances)")
        ax.tick_params(axis="x", rotation=20)
        ax.grid(axis="y", alpha=0.3, which="both")
    axes[0].set_ylabel("Total time (ms, log scale)")
    fig.suptitle("Runtime distribution per solver (solved instances)")
    save(fig, out, "6_runtime_boxplot.png")


def chart7(d, out):
    ok = d[d.solved]
    groups = [g for g in GROUP_ORDER if g in set(ok.group)]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    for ax, col, lab in zip(axes, ["num_variables", "num_clauses"],
                            ["Median number of variables", "Median number of clauses/constraints"]):
        tab = ok.groupby(["group", "solver"])[col].median().to_dict()
        grouped_bars(ax, tab, SOLVERS, groups)
        ax.set_yscale("log")
        ax.set_ylabel(lab + " (log scale)")
        ax.set_title(lab)
        ax.grid(axis="y", alpha=0.3)
    axes[0].legend(fontsize=8)
    fig.suptitle("Encoding size per solver (A1, A4, A5 share the same CNF encoding)")
    save(fig, out, "7_variables_clauses.png")


def chart8(d, out):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    ax = axes[0]
    counts = d.groupby(["solver", "status"]).size().unstack(fill_value=0).reindex(SOLVERS)
    bottom = np.zeros(len(SOLVERS))
    for st, col in [("sat", "#74c476"), ("unsat", "#6baed6"), ("timeout", "#e6550d")]:
        if st in counts:
            ax.bar([LABEL[s] for s in SOLVERS], counts[st], bottom=bottom, label=st, color=col)
            bottom += counts[st].values
    ax.set_ylabel("Instances")
    ax.set_title("Outcome per solver")
    ax.tick_params(axis="x", rotation=20)
    ax.set_ylim(0, 185)
    ax.legend(loc="upper center", ncol=3)
    ax = axes[1]
    groups = [g for g in GROUP_ORDER if g in set(d.group)]
    rate = (d.groupby(["group", "solver"]).solved.mean() * 100).to_dict()
    grouped_bars(ax, rate, SOLVERS, groups)
    ax.set_ylim(0, 125)
    ax.set_yticks(range(0, 101, 20))
    for i, g in enumerate(groups):
        if d[(d.group == g)].solved.mean() == 0:
            ax.text(i, 3, "0%\nall timed out", ha="center", fontsize=9, color="#e6550d")
    ax.set_ylabel("Completion rate (%)")
    ax.set_title("Completion rate per dataset")
    ax.grid(axis="y", alpha=0.3)
    ax.legend(fontsize=8, loc="upper center", ncol=5)
    n = d[d.status == "timeout"].wall_s.median()
    fig.suptitle(f"Completion rates and timeouts (limit ~{n:.0f} s per instance)")
    save(fig, out, "8_completion_timeouts.png")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv", type=Path)
    p.add_argument("--output", type=Path, default=Path("results/charts"))
    a = p.parse_args()
    d = load(a.csv)
    print("solvers in data:", sorted(d.solver.unique()))
    a.output.mkdir(parents=True, exist_ok=True)
    compare_chart(d, ["a1", "a2", "a3"], "Formulation comparison: A1 (CNF) vs A2 (integer) vs A3 (boolean), all on Z3",
                  a.output, "1_formulation_comparison.png")
    compare_chart(d, ["a1", "a4", "a5"], "Solver comparison: same CNF encoding on Z3 (A1), PySAT (A4), CP-SAT (A5)",
                  a.output, "2_solver_comparison.png")
    chart3(d, a.output)
    chart4(d, a.output)
    chart5(d, a.output)
    chart6(d, a.output)
    chart7(d, a.output)
    chart8(d, a.output)


if __name__ == "__main__":
    main()
