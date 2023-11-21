#!/usr/bin/env python3

import pandas as pd
import numpy as np
import argparse
import json
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from scipy.stats import gmean


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
        df[((df["Bench"] == bench) & (df["Name"] == numerator))][
            column_name(useKernelTime)
        ].mean()
        / df[((df["Bench"] == bench) & (df["Name"] == denominator))][
            column_name(useKernelTime)
        ].mean()
    )


def preprare_data(df, config, useKernelTime, numerator, denom1, denom2):
    # Create a new column combining benchmark and configuration
    df["BenchConfig"] = df.apply(
        lambda x: getBenchConfig(
            config, x["Bench"], x["Problem Size"], x["Local Size"]
        ),
        axis=1,
    )

    # Filter to only include the benchmarks we actually want to plot.
    df = df[df["BenchConfig"].apply(lambda b: config.should_plot(b))]

    if config:
        df.loc[:, "Bench"] = df["Bench"].apply(config.translate)

    speedups1 = [
        [bench, denom1, calculate_speedup(df, bench, numerator, denom1, useKernelTime)]
        for bench in df["Bench"].unique()
    ]
    speedups2 = [
        [bench, denom2, calculate_speedup(df, bench, numerator, denom2, useKernelTime)]
        for bench in df["Bench"].unique()
    ]
    
    speedups = speedups1 + speedups2


    return pd.DataFrame(speedups, columns=["Bench", "Implementation", "Speedup"])


def plot_external(
    inputFiles,
    outputFile,
    useKernelTime,
    configFile,
    numerator,
    denom1,
    denom2,
    title,
    ylim,
    ylabel
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
    d1 = denom1
    d2 = denom2
    if config:
        df["Name"] = df["Name"].apply(lambda x: config.translate(x))
        num = config.translate(num)
        d1 = config.translate(d1)
        d2 = config.translate(d2)

    # Filter only the entries for the time we currently want to plot.
    # Either kernel time or runtime.
    df = filter_data(df, useKernelTime)

    # Add calculated columns and filter out benchmarks and configurations that
    # should not be plotted
    data = preprare_data(df, config, useKernelTime, num, d1, d2)

    order = list(data["Bench"].unique())
    order.sort()
    order.append("geo.-mean")

    means = data.groupby(data.Implementation).Speedup.apply(lambda x: gmean(x.dropna()))

    geomeans = pd.DataFrame([["geo.-mean", d1, means[d1]],
                             ["geo.-mean", d2, means[d2]]], columns=["Bench", "Implementation", "Speedup"])

    print(geomeans)

    data = pd.concat([data, geomeans], ignore_index=True)

    with PdfPages(outputFile) as pdf:
        fig = plt.figure()
        plt.xticks(rotation=85)
        # Set plot title
        if title:
            print(str(title))
            plt.title(str(title))
        # Barplot
        ax = sns.barplot(
            data, x="Bench", y="Speedup", hue="Implementation", order=order
        )
        #ax.bar_label(ax.containers[0], fmt="%.2fx", rotation=80)
        # Set axes labels
        ax.set(xlabel=None, ylabel=ylabel)
        # Set y-axis limit
        if ylim:
            ax.set_ylim(top=float(ylim))

        pdf.savefig(fig, bbox_inches="tight")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create one plot for all benchmarks")
    parser.add_argument("inputs", nargs="+", default=[])
    parser.add_argument("-o", "--output", default="external.pdf")
    parser.add_argument("--kernel-time", action="store_true")
    parser.add_argument("-c", "--config", default=None)
    parser.add_argument("-n", "--numerator", required=True)
    parser.add_argument("-d1", "--denominator1", required=True)
    parser.add_argument("-d2", "--denominator2", required=True)
    parser.add_argument("-t", "--title", default=None, type=lambda x: bytes(x, "utf-8").decode("unicode_escape"))
    parser.add_argument("-y", "--ylim", default=None)
    parser.add_argument("-l", "--ylabel", default=None, type=lambda x: bytes(x, "utf-8").decode("unicode_escape"))
    args = parser.parse_args()
    plot_external(
        args.inputs,
        args.output,
        args.kernel_time,
        args.config,
        args.numerator,
        args.denominator1,
        args.denominator2,
        args.title,
        args.ylim,
        args.ylabel,
    )

