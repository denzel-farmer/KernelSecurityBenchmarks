
from kernsecbench.microwave_wrapper import run_linux_benchmark, RAW_LOG_DIR
from kernsecbench.results_analysis import streams_to_scalar_run_map, parse_lmbench_scalars, parse_sqlite_scalars, parse_lm_streams, parse_inkscape_scalars, parse_glibc_scalars, print_key_figures, analyze_scalars_across_runs, analyze_streams_across_runs
from kernsecbench.test_configs import kconfig_map, BASE_DEFCONFIG
from microwave2.utils.kernel_config import Kconfig, generate_kconfig
from microwave2.utils.utils import Arch
from microwave2.results.kernel_log import RawKernelLogResult, KernelLog


import os


def do_run_all_benchmarks(num_iters):
    # Run all benchmarks num_iters times
    for i in range(num_iters):
        print(f"Running iteration {i + 1} of {num_iters}")
        do_run_sqlite()
        do_run_stressng()
        do_run_lmbench()
        do_run_glibc_bench()
        do_run_inkscape()
        # do_run_ksbench()


def do_run_glibc_bench():
    run_bench(launch_script="launch_glibc.sh", bench_name="lmbench")


def do_run_lmbench():
    run_bench(launch_script="launch_lmbench.sh", bench_name="lmbench")


def do_run_inkscape():
    run_bench(launch_script="launch_inkscape.sh", bench_name="lmbench")


def do_run_stressng():
    run_bench(launch_script="launch_stressng.sh", bench_name="lmbench")


def do_run_sqlite():
    run_bench(launch_script="launch_sqlite.sh", bench_name="lmbench")


ANALYSIS_DIR = os.path.join(os.path.dirname(__file__), "results-analysis")


def get_output_dir(config_name: str):
    # Get the output directory for the config
    output_dir = os.path.join(ANALYSIS_DIR, f"raw_results_{config_name}")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def extract_phoronix_stats(json_path: str, config_name: str, reuslt_no: int = 0):
    kernel_log = KernelLog.from_JSON(json_path)
    # Extract the glibc stats, which are in raw lines between "Aux log file:" and "[TAG: AUX GLIBC-BENCH RESULTS]"
    kernel_log_lines = kernel_log.get_raw_lines()

    # test to tag pairs and parse function map
    parse_fuc_map = {
        "glibc": ("Aux log file:", "[TAG: AUX GLIBC-BENCH RESULTS]", parse_glibc_scalars),
        "inkscape": ("Aux log file:", "[TAG: AUX INKSCAPE-BENCH RESULTS]", parse_inkscape_scalars),
        "sqlite": ("Aux log file:", "[TAG: AUX SQLITE-BENCH RESULTS]", parse_sqlite_scalars),
    }
    scalars = None
    # Figure out which test to run for each, if both tags are present the parse with specific function
    for test, (start_tag, end_tag, parse_func) in parse_fuc_map.items():
        lines = []
        try:
            start = kernel_log_lines.index(start_tag)
            end = kernel_log_lines.index(end_tag)
            lines = kernel_log_lines[start + 1:end]
        except ValueError as e:
            # print(f"Error: {e}")
            print(f"{test} results not found in kernel log for config: ", config_name)
            continue
            # return None
            # raise e

        # Print the lines
        # print(f"{test} Results:")
        # for line in lines:
        #     print(line)
        # Join into single string
        results_str = "\n".join(lines)

        # Dump to current file location + "results-analysis/<bench_name>_<config_name>"
        output_dir = get_output_dir(config_name)
        # Write copy of glibc results to file
        with open(os.path.join(output_dir, f"{test}_results_{reuslt_no}.txt"), "w") as f:
            f.write(results_str)
        # Parse the results
        scalars = parse_func(results_str)
        break

    return scalars

    # try:
    #     glibc_start = kernel_log_lines.index("Aux log file:")
    #     glibc_end = kernel_log_lines.index("[TAG: AUX GLIBC-BENCH RESULTS]")
    #     glibc_lines = kernel_log_lines[glibc_start + 1:glibc_end]
    # except ValueError as e:
    #     # print(f"Error: {e}")
    #     print("glibc results not found in kernel log for config: ", config_name)
    #     return None
    #     # raise e

    # glibc_results_str = "\n".join(glibc_lines)
    # # Dump to current file location + "results-analysis/<bench_name>_<config_name>"
    # output_dir = get_output_dir(config_name)
    # # Write copy of glibc results to file
    # with open(os.path.join(output_dir, f"glibc_results_{reuslt_no}.txt"), "w") as f:
    #     f.write(glibc_results_str)

    # scalars = parse_glibc_scalars(glibc_results_str)

    # return scalars


def extract_lmbench_stats(json_path: str, config_name: str, result_no: int = 0):
    # Deserialize into kernel log object
    kernel_log = KernelLog.from_JSON(json_path)

    # Extract the lmbench stats, which are in raw lines between [TAG: AUX LMBENCH RESULTS] and [TAG: AUX LMBENCH RESULTS END]
    kernel_log_lines = kernel_log.get_raw_lines()
    try:
        lmbench_start = kernel_log_lines.index("[TAG: AUX LMBENCH RESULTS]")
        lmbench_end = kernel_log_lines.index("[TAG: AUX LMBENCH RESULTS END]")
        lmbench_lines = kernel_log_lines[lmbench_start + 1:lmbench_end]
    except ValueError as e:
        # print(f"Error: {e}")
        print("LMBench results not found in kernel log for config: ", config_name)
        return None, None
        # raise e
    # Print the lines
    # print("LMBench Results:")
    # for line in lmbench_lines:
    #     print(line)
    # Join into single string
    lmbench_results_str = "\n".join(lmbench_lines)

    # Dump to current file location + "results-analysis/<bench_name>_<config_name>"
    output_dir = get_output_dir(config_name)
    # Write copy of lmbench results to file
    with open(os.path.join(output_dir, f"lmbench_results_{result_no}.txt"), "w") as f:
        f.write(lmbench_results_str)

    scalars = parse_lmbench_scalars(lmbench_results_str)
    streams = parse_lm_streams(lmbench_results_str)

    # print("Streams:", streams)
    # dump_stream_csv(streams, outdir=output_dir)
    # print_key_figures(streams)

    return scalars, streams

    print("End of LMBench Results")


def do_analyze_lmbench():
    """
    Analyze the results of the skeleton benchmark.
    """
    bench_prefix = "lmbench"
    config_scalar_results = {}
    config_stream_results = {}
    for config_name, kconfig_str in kconfig_map.items():
        print(f"Analyzing {bench_prefix} with {config_name}")
        curr_log_dir = os.path.join(
            RAW_LOG_DIR, f"{bench_prefix}_{config_name}_{BASE_DEFCONFIG}")
        test_log_dir = os.path.join(
            curr_log_dir, f"test_lmbench_{config_name}")

        # for each json in the format kernel_[date].json excluding kernel_current.json
        scalars = None
        streams = None
        glibc_scalars = None
        result_no = 0

        # If does not exist, move on
        if not os.path.exists(test_log_dir):
            print(f"Error: {test_log_dir} does not exist")
            continue

        for file in os.listdir(test_log_dir):
            if file.startswith("kernel_") and file.endswith(".json") and file != "kernel_current.json":
                # get the date from the filename
                date = file.split("_")[1].split(".")[0]
                # get the path to the json file
                json_path = os.path.join(test_log_dir, file)
                print(f"Analyzing {os.path.basename(json_path)}")
                glibc_scalars = extract_phoronix_stats(
                    json_path, config_name, result_no)
                if glibc_scalars is not None:
                    # print("Found glibc results, press enter to continue")
                    # print(glibc_scalars)
                    # input("Press enter to continue")
                    if (config_scalar_results.get(config_name) is None):
                        config_scalar_results[config_name] = [glibc_scalars]
                    else:
                        config_scalar_results[config_name].append(
                            glibc_scalars)
                else:
                    print(
                        f"Error: {os.path.basename(json_path)} does not contain glibc results")
                scalars, streams = extract_lmbench_stats(
                    json_path, config_name, result_no)
                if scalars is not None:
                    if (config_scalar_results.get(config_name) is None):
                        config_scalar_results[config_name] = [scalars]
                    else:
                        config_scalar_results[config_name].append(scalars)
                else:
                    print(
                        f"Error: {os.path.basename(json_path)} does not contain scalar results")
                if streams is not None:
                    if (config_stream_results.get(config_name) is None):
                        config_stream_results[config_name] = [streams]
                    else:
                        config_stream_results[config_name].append(streams)
                else:
                    print(
                        f"Error: {os.path.basename(json_path)} does not contain stream results")

                result_no += 1

        # scalar_path = os.path.join(get_output_dir(config_name), "lmbench_scalar.csv")
        # dump_scalar_csv(config_results[config_name], fn=scalar_path)

    # print("Config results:")
    # print(config_results)
    # analyze_streams_across_runs(config_stream_results)

    stream_scalar_map = streams_to_scalar_run_map(config_stream_results)

    # merge the two maps: for each run, just concatenate the iteration lists
    for run, iters in stream_scalar_map.items():
        if run in config_scalar_results:
            for i, s_list in enumerate(iters):
                # same iteration exists
                if i < len(config_scalar_results[run]):
                    config_scalar_results[run][i].extend(
                        s_list)  # append new scalars
                else:                                      # iteration only in streams
                    config_scalar_results[run].append(s_list)
        else:
            config_scalar_results[run] = iters

    analyze_scalars_across_runs(config_scalar_results)


def do_analyze_results():
    pass


def run_bench(launch_script: str, bench_name: str, interactive: bool = False) -> None:

    # For this benchmark, will run each kconfig once
    for config_name, (kconfig_str, extra_args) in kconfig_map.items():
        print(f"Running {bench_name} with {config_name}")
        full_run_name = f"{bench_name}_{config_name}"
        kconfig = generate_kconfig(arch=Arch.X86, defconfig_names=[
            "manmin_nosec_defconfig"], kconfig_strings=[kconfig_str], label_base=full_run_name, allow_def_override=True)
        run_linux_benchmark(test_name=f"test_{full_run_name}", kconfig=kconfig,
                            build_function=None, launch_script=launch_script, interactive=interactive, extra_args=extra_args)
        print(f"Finished {bench_name} with {config_name}")

    pass


def run_ksbench_single(interactive: bool, extra_kconfig_str: str, label_base: str, launch_script: str) -> None:
    """
    Run the kernel security benchmark.
    """

    kconfig = generate_kconfig(arch=Arch.X86, defconfig_names=[
                               BASE_DEFCONFIG], kconfig_strings=[extra_kconfig_str], label_base=label_base)
    run_linux_benchmark(test_name=f"test_{label_base}", kconfig=kconfig,
                        build_function=None, launch_script=launch_script, interactive=interactive)

    print("Running kernel security benchmark")
