#!/usr/bin/env python3

import pandas as pd
import numpy as np
import argparse
import json
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


def getBenchConfig(config, benchName, problemSize, localSize):
    aliasName = config.translate(benchName) if config else benchName
    return f"{aliasName} ({problemSize}x{localSize})"


class BenchConfig:
    prefix = None
    allowedConfigs = []

    def __init__(self, config, benchName, allowedConfigList):
        if allowedConfigList:
            self.allowedConfigs = [
                getBenchConfig(config, benchName, x[0], x[1]) for x in allowedConfigList
            ]
        else:
            self.prefix = config.translate(benchName) if config else benchName

    def matches(self, benchConfig):
        if self.allowedConfigs:
            return benchConfig in self.allowedConfigs
        else:
            return benchConfig.startswith(self.prefix)

    def __str__(self):
        if self.allowedConfigs:
            return ", ".join(self.allowedConfigs)
        else:
            return self.prefix


# end of class BenchConfig


class PlotConfig:
    aliases = None
    plotBenches = []

    def __init__(self, definedAliases):
        self.aliases = definedAliases

    def translate(self, benchName):
        return self.aliases.get(benchName, benchName) if self.aliases else benchName

    def add_bench(self, benchConfig):
        self.plotBenches.append(benchConfig)

    def should_plot(self, benchConfigStr):
        return any([x.matches(benchConfigStr) for x in self.plotBenches])

    def __str__(self):
        return f"aliases: {self.aliases}, benchmarks:\n {[str(b) for b in self.plotBenches]}"


# end of class PlotConfig


def parsePlotConfig(configFile):
    with open(configFile) as f:
        data = json.load(f)
        aliases = None
        if "alias" in data:
            aliases = data["alias"]

        config = PlotConfig(aliases)

        if "benchmarks" in data:
            for b in data["benchmarks"]:
                if "name" in b:
                    benchName = b["name"]
                    configs = []
                    if "configs" in b:
                        for c in b["configs"]:
                            if ("problem-size" in c) and ("local-size") in c:
                                configs.append((c["problem-size"], c["local-size"]))

                    config.add_bench(BenchConfig(config, benchName, configs))

        return config


def column_name(useKernelTime):
    return "Kernel" if useKernelTime else "Runtime"


def filter_data(df, useKernelTime):
    columnName = column_name(useKernelTime)
    return df[df[columnName].notnull()]


def calculate_speedup(df, bench, numerator, denominator, useKernelTime):
    return (
        df[((df["BenchConfig"] == bench) & (df["Name"] == numerator))][
            column_name(useKernelTime)
        ].mean()
        / df[((df["BenchConfig"] == bench) & (df["Name"] == denominator))][
            column_name(useKernelTime)
        ].mean()
    )


def preprare_data(df, config, useKernelTime, numerator, denominator):
    # Create a new column combining benchmark and configuration
    df["BenchConfig"] = df.apply(
        lambda x: getBenchConfig(
            config, x["Bench"], x["Problem Size"], x["Local Size"]
        ),
        axis=1,
    )

    # Filter to only include the benchmarks we actually want to plot.
    df = df[df["BenchConfig"].apply(lambda b: config.should_plot(b))]

    speedups = [
        [
            bench,
            calculate_speedup(df, bench, numerator, denominator, useKernelTime)
        ]
        for bench in df["BenchConfig"].unique()
    ]

    return pd.DataFrame(speedups, columns=["BenchConfig", "Speedup"])


def plot_external(
    inputFiles, outputFile, useKernelTime, configFile, numerator, denominator
):
    sns.set_style("whitegrid")
    df = None
    # Read all files and merge to one dataframe
    for f in inputFiles:
        if df is None:
            df = pd.read_csv(f, header=0)
        else:
            df = pd.concat([df, pd.read_csv(f, header=0)], ignore_index=True)

    # Parse the configuration file if given.
    config = parsePlotConfig(configFile) if configFile else None

    num = numerator
    denom = denominator
    if config:
        df["Name"] = df["Name"].apply(lambda x: config.translate(x))
        num = config.translate(num)
        denom = config.translate(denom)

    # Filter only the entries for the time we currently want to plot.
    # Either kernel time or runtime.
    df = filter_data(df, useKernelTime)

    # Add calculated columns and filter out benchmarks and configurations that
    # should not be plotted
    data = preprare_data(df, config, useKernelTime, num, denom)

    with PdfPages(outputFile) as pdf:
        fig = plt.figure()
        plt.xticks(rotation=80)
        # Set plot title
        plt.title(f"Performance comparison\n{num} vs. {denom}")
        # Barplot
        ax = sns.barplot(
            data,
            x="BenchConfig",
            y="Speedup",
            color=sns.color_palette()[0]
        )
        ax.bar_label(ax.containers[0], fmt='%.2fx')
        # Set axes labels
        ax.set(xlabel=None, ylabel=f"Speedup of {denom} over {num}")

        pdf.savefig(fig, bbox_inches="tight")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create one plot for all benchmarks")
    parser.add_argument("inputs", nargs="+", default=[])
    parser.add_argument("-o", "--output", default="external.pdf")
    parser.add_argument("--kernel-time", action="store_true")
    parser.add_argument("-c", "--config", default=None)
    parser.add_argument("-n", "--numerator", required=True)
    parser.add_argument("-d", "--denominator", required=True)
    args = parser.parse_args()
    plot_external(
        args.inputs,
        args.output,
        args.kernel_time,
        args.config,
        args.numerator,
        args.denominator,
    )
