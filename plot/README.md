# Visualization

This folder contains scripts to process and visualize performance data from 
the SYCL Bench benchmark suite.

## Setup

Prior to using the scripts, you must setup a suitable Python environment.

If you do not want to install the Python packages system-wide, it is 
recommended to use a Python virtual environment instead. 

First, you need to install Python `venv` on your system. On Ubuntu, this 
is possible through `apt install python3-venv`. If you use a different system,
check instructions for your system online. 

After that, a new Python virtual environment can be created:
```bash
python3 -m venv venv
```

The second argument is the name of the folder that you would like to use for
the virtual environment, so you're free to choose a different name. If you do 
so, remember to use the correct name in the following commands.

Activate the virtual environment:
```bash
source venv/bin/activate
```

This command needs to be repeated every time you start a new shell environment.


To install the necessary packages, run: 
```bash
pip install pandas seaborn matplotlib
```

This step only needs to performed once during setup. 


## Preprocessing

SYCL Bench can provide raw runtime data in CSV format. However, this format is
not directly suitable for formatting and therefore needs to undergo
pre-processing. 

The input format is expected to start with two lines with a single column
giving a name for the current benchmark run (first line) and the configuration
(second line).

This is followed by alternating lines of header and data. The header is
expected to define the following fields, for which the data line gives values:

* `# Benchmark name`: Name of the benchmark
* `sycl-implementation`: Name for the SYCL implementation
* `device-name`: Name of the device the benchmark was executed on
* `problem-size`: Problem size given for the benchmark
* `local-size`: SYCL work-group size
* `kernel-time-samples` (Optional): List of kernel time samples
* `run-time-samples`: List of run time samples

The last two fields are expected to encode the list of samples as an
(optionally quoted) string, separating the different samples with a
whitespace character.

An example input file with two benchmarks might look like this:
```
some-name
some-config
# Benchmark name, problem-size, local-size, kernel-time-samples, run-time-samples, device-name, sycl-implementation
GEMM, 4096, 256, 5 6 5 7, "10 11 12 9", "Fast GPU", "popSYCL"
# Benchmark name, problem-size, local-size, kernel-time-samples, run-time-samples, device-name, sycl-implementation
SPMV, 8192, 128, 0.5 0.6 0.55, 0.8 0.9 1.1, "Fast GPU", "popSYCL"
```

The pre-processing script parses this format and creates a Pandas dataframe 
from it, suitable for plotting, which is also stored in CSV format.

The script can be executed as follows:

```bash
python src/parse-csv.py input.csv -o dataframe.csv
```

## Detailed visualization

The first visualization script will create one plot *per* benchmark,
allowing detailed investigation of different configurations (problem size, 
local size) of that benchmark. 

The script can be executed as follows and will yield a single PDF file with
one page per benchmark: 

```bash
python src/plot-detailed.py fast.csv slow.csv -o detailed.pdf
```

If you want to investigate kernel time from profiling rather than runtime, you
can do so by specifying the `--kernel-time` flag.


## Compact visualization

The second visualization script will create a single plot for more compact
visualization, e.g., for inclusion in a publication.

The visualization can be configured through a configuration file. The
configuration file supports the following fields:

* `alias`: An object, where each field defines an alias for a benchmark or
a name. 
* `benchmarks`: A list of objects. Each object must specify the `name` of a
benchmark and can optionally include a field `configs` with an array of 
configurations specified through an object with fields `problem-size` and
`local-size`. Only benchmarks/configurations included in this list will be 
plotted. For the `name` field, you can use the full name of the benchmark or
the corresponding alias you defined. 

An example configuration might look like this:

```json
{
    "alias": {
        "mlir" : "SYCL-MLIR",
        "spir" : "DPC++",
        "Polybench_2DConvolution": "2D Convolution",
        "Polybench_Syrk": "SYRK",
    },
    "benchmarks": [
        {
            "name" : "SYRK"
        },
        {
            "name": "Polybench_3mm",
            "configs": [
                {
                    "problem-size": 1024,
                    "local-size": 256
                }
            ]
        }
    ]
}
```

The script also takes two mandatory flags `--numerator` (`-n`) and
`--denominator` (`-d`), which take the name of the numerator and denominator
that should be used in the speedup calculation.

The visualization script can be executed as follows and will yield a PDF file:
```bash
python src/plot-compact.py fast.csv slow.csv -o compact.pdf -c config.json -n "slow-compiler" -d "fast-compiler"
```

Again, if you want to investigate kernel time from profiling rather than
runtime, you can do so by specifying the `--kernel-time` flag.
