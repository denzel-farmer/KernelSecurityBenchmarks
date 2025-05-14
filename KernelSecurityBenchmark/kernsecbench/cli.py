import click

from kernsecbench.benchmark import do_run_sqlite, do_run_stressng, do_run_inkscape, do_analyze_results, do_run_all_benchmarks, do_run_lmbench, do_analyze_lmbench, do_run_glibc_bench
import platform


@click.group()
def cli():
    print("inCLI kernsecbench")
    pass


@cli.command()
def run_lmbench():
    print("Running lmbench benchmarks")
    do_run_lmbench()


@cli.command()
def run_glibc_bench():
    print("Running glibc benchmarks")
    do_run_glibc_bench()


@cli.command()
def run_inkscape():
    print("Running inkscape benchmarks")
    do_run_inkscape()


@cli.command()
def run_sqlite():
    print("Running sqlite benchmarks")
    do_run_sqlite()


@cli.command()
def run_stressng():
    print("Running stress-ng benchmarks")
    do_run_stressng()


@cli.command()
@click.option('--iters', type=click.INT, default=1, help='Number of iterations to run')
def run_all_benchmarks(iters):
    print("Running all benchmarks")
    do_run_all_benchmarks(num_iters=iters)


@cli.command()
def analyze_benchmarks():
    print("Analyzing benchmark results")
    do_analyze_lmbench()


if __name__ == "__main__":
    cli()
