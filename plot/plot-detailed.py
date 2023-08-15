#!/usr/bin/env python3

import pandas as pd
import numpy as np
import argparse
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


def column_name(useKernelTime):
    return "Kernel" if useKernelTime else "Runtime"


def filter_data(df, useKernelTime):
    columnName = column_name(useKernelTime)
    return df[df[columnName].notnull()]


def prepare_data(df):
    df["BenchConfig"] = df.apply(
        lambda x: f"{x['Problem Size']}x{x['Local Size']}", axis=1
    )
    return df


def plot_internal(inputFiles, outputFile, useKernelTime):
    sns.set_style("whitegrid")
    df = None
    for f in inputFiles:
        if df is None:
            df = pd.read_csv(f, header=0)
        else:
            df = pd.concat([df, pd.read_csv(f, header=0)], ignore_index=True)

    with PdfPages(outputFile) as pdf:
        benchmarks = df["Bench"].unique()
        benchmarks.sort()
        figCount = 0
        for bench in benchmarks:
            if bench.startswith("Runtime_") or bench.startswith("Micro"):
                continue
            benchDF = df[df["Bench"] == bench]
            benchDF = filter_data(benchDF, useKernelTime)
            if benchDF.empty:
                continue
            benchDF = prepare_data(benchDF)
            fig = plt.figure(figCount)
            plt.xticks(rotation=45)
            plt.title(bench)
            sns.boxplot(
                benchDF, x="BenchConfig", y=column_name(useKernelTime), hue="Name"
            )
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(figCount)
            figCount += 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create one plot per benchmark")
    parser.add_argument("inputs", nargs="+", default=[])
    parser.add_argument("-o", "--output", default="internal.pdf")
    parser.add_argument("--kernel-time", action="store_true")
    args = parser.parse_args()
    plot_internal(args.inputs, args.output, args.kernel_time)
