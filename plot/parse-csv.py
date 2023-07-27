#!/usr/bin/python3

import json
import pandas as pd
import numpy as np
import argparse

columns = [
    "Bench",
    "Name",
    "Config",
    "Compiler",
    "Device",
    "Verify",
    "Problem Size",
    "Local Size",
    "Kernel",
    "Runtime",
]


def append_times_if_present(
    df, row, name, config, columnName, kernelTimeFunc, runTimeFunc
):
    if str(row[columnName]) != "nan":
        kernelTimes = [
            float(x) for x in row[columnName].strip('"').strip(" ").split(" ")
        ]
        kernelTimeEntries = [
            [
                row["# Benchmark name"],
                name,
                config,
                row["sycl-implementation"],
                row["device-name"],
                True,
                row["problem-size"],
                row["local-size"],
                kernelTimeFunc(r),
                runTimeFunc(r),
            ]
            for r in kernelTimes
        ]

        return pd.concat(
            [df, pd.DataFrame(kernelTimeEntries, columns=columns)], ignore_index=True
        )
    else:
        return df


def parse_bench(df, name, config, data):
    row = data.iloc[0]
    if "kernel-time-samples" in data:
        df = append_times_if_present(
            df,
            row,
            name,
            config,
            "kernel-time-samples",
            lambda x: x,
            lambda x: float("NaN"),
        )

    if "run-time-samples" in data:
        df = append_times_if_present(
            df,
            row,
            name,
            config,
            "run-time-samples",
            lambda x: float("NaN"),
            lambda x: x,
        )
    else:
        print(row["# Benchmark name"])

    return df


def parse_run(inputFile, outputFile):
    df = pd.DataFrame(columns=columns)

    # Detect number of lines
    with open(inputFile, "rb") as f:
        num_lines = sum(1 for _ in f)

    if num_lines < 4:
        # If there is not at least 4 lines, we do not have the header and at least one benchmark
        print("Error: Less than 4 lines indicates missing header or benchmark data")
        return

    # Read the first two lines to get configuration information
    header = pd.read_csv(inputFile, header=None, names=["Info"], nrows=2)
    name = header["Info"][0]
    config = header["Info"][1]

    print(name, config)

    # Go through the file in steps of two to parse header and one line of benchmark information
    for i in range(2, num_lines - 1, 2):
        data = pd.read_csv(inputFile, header=i, nrows=1)
        df = parse_bench(df, name, config, data)

    df.to_csv(outputFile, index=False, header=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract dataframe from CSV file")
    parser.add_argument("input")
    parser.add_argument("-o", "--output", default="sycl-bench.csv")
    args = parser.parse_args()
    parse_run(args.input, args.output)
