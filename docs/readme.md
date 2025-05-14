# KernelSecurityBenchmark

This repository contains our implementation and results of 'Final Project 2' for COMS E6424 Hardware Security. Rather than explore both NodeJS and Linux kernel configuration
hardening, we decided to focus entirely on kernel configurations. We also focused our 
effort on building a generic, flexible framework for evaluting future configurations 
rather than exploring a greater breadth of configurations and benchmarks. 

We build a kernel testing framework, which allows for automated configuration, compilation, virtualization, and evaluation of Linux kernels. For a more detailed description of the microwave framework, see [the microwave design document](microwave-framework.md). 

On top of this framework, we implement a runner that tests identical Linux 
kernels with key security configurations selectively enabled. The runner extracts
benchmarking results, and performs simple data analysis across them to demonstrate
how each configuration performs across benchmarks. For details on the kernel configurations evaluated and key results, see [the evaluation report](kernel-evaluation.md).

## Repo Structure

Microwave/ - Kernel testing framework Python package
KernelSecurityBenchmark/ - Kernel evaluation and analysis Python package
documentation/ - Documentation and evaluation results

## Installation

We ran all evaluation on an `n2-standard-8` Google Cloud virtual machine. To 
install this repository and replicate our results:
1. Create a new `n2-standard-8` virtual machine using the latest `Ubuntu` disk image,
enabling nested virtualization with the `enableNestedVirtualization` flag and/or the
special license key, as described in [gcp documentation](https://cloud.google.com/compute/docs/instances/nested-virtualization/enabling).
2. Log in as a `sudo` user, and add the user to the `kvm` group:
```bash
usermod -a -G kvm yourUserName
```
3. Install all of the Microwave dependencies (not all strictly required)
```bash
sudo apt-get update && sudo apt-get upgrade
sudo apt-get install git python3 python3-venv pip \
        qemu-user qemu-system qemu-utils \
        binfmt-support build-essential bc python3 \
        bison flex rsync libelf-dev libssl-dev libncurses-dev dwarves \
        gcc gdb-multiarch make zstd bsdmainutils cmake \
        procps kmod crossbuild-essential-amd64 \
        gcc-aarch64-linux-gnu gcc-x86-64-linux-gnu \
        cloud-image-utils ca-certificates
```
4. Clone the `KernelSecurityBenchmark` 
```bash
git clone git@github.com:denzel-farmer/KernelSecurityBenchmarks.git
```
5. Create a new virtual environment and install both Python applications
```bash
cd KernelSecurityBenchmarks
python3 -m venv .venv 
source .venv/bin/activate
pip install -e Microwave/
pip install -e KernelSecurityBenchmark/
```
6. If using private GitHub repositories to store tests and targets, add a GitHub personal access token to the environment.
```bash
export GIT_TOKEN=<token>
```
7. Run the benchmarks 
```bash
kernsecbench run-all-benchmarks <num-iters>
```
8. Analyze results, produce CSVs and figures
```bash
kernsecbench analyze-results
```