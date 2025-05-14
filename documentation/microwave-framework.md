# The Microwave Framework
The Microwave framework (*microwave* because it pops kernels) is a high flexible and generic
Linux kernel testing framework, built in Python. The framework automates each component of kernel testing,
allowing users to focus entirely on writing effective tests rather than the infrastructure
of configuring, building, and booting into the kernel. 

While this implementation was designed as a final project for COMS E6424 Hardware Security, future iterations will hopefully released open-source.

## Design Principles
Microwave is designed with a few key principles in mind:
- Extensibility - The framework must be easily extensible to support a variety of test scenarios, ideally without modification to the underlying framework. If necessary, extension to the framework must not require massive rewriting. 
- Ease of Use - The primary user of Microwave will be defining tests and retrieving their output. The interface for this must be as simple as possible, and must not require full understanding of the framework. 
- Modularity - Components of the framework should be modular and interoperable, to improve understandability and extensibility. 

## Microwave Design
The framework is designed in object-oriented Python centered around a set of abstract classes which callers instantiate and interact with to run tests.

These classes are generic enough to encompass any test scenario that follows the pattern of building target and test code into a binary image, and running that image to retrieve results. 

Currently, the only scenario fully implemented is for testing Linux kernel code and configurations, but we have conducted some exploration into other scenarios (including testing a 'raw' bootloader, as well as Linux kernel modules on a reference kernel).


### Tester
A top-level `Tester` class initializes each of the other relevant objects based on provided configurations: a `Target`, `Test`, `Image`, and `Runner`. 

Additionally, it exposes three generic implementations of the  functions to carry out a test, by calling methods from composed objects: `download` retrieves all required Test and Target artifacts, `build` compile both artifacts into a runnable Image, and `run` boots the Image, runs the Test, and retrieves results. 


**LinuxKernelTester**

The `LinuxKernelTester(Tester)` subclass is extremely simple, since it can rely on the generic implementations of each function. It only must override the `__init__` method of the `Tester`, to initialize specific sublcasses of each composed object required for testing:
- `Target` -> `KernelTarget`
- `Test` -> `LinuxTest`
- `Image` -> `UbuntuDiskImage`
- `Runner` -> `KernelLogRunner`
 

### Target
The `Target` class represents the code and configuration that is under test. 

The class includes a generic `download` implementation that pulls code from a Git repository into a source directory, but includes abstract functions `build` (which must compile code from the source folder into a build directory) and `install` (which must install built artifacts into the final Image). 

**KernelTarget**

The `KernelTarget(Target)` subclass wraps a Linux kernel and KConfig combination that will be tested. The only artifact downloaded is the kernel source tree itself from a Git remote, so the `KernelTarget` does not override the generic `download` function.

To implement `build`, the `KernelTarget` passes the provided KConfig (wrapped with the [KernelConfig](#kernelconfig) utility) to an instance of the [LinuxKernel](#linuxkernel) utility, and calls methods to configure and compile the kernel into the build directory with its own Makefile. 

The `install` implementation is more involved, but mostly involves mounting and overwritting/installing key files in the `UbuntuDiskImage` (specifically, `/boot`, `/usr`, and `/lib`). 


### Test
The `Test` class represents the test that will run on the `Target`, which also must be installed on the final `Image`.

This class includes the same Git-based `download` implementation as `Target`, and a similarly abstract `install` method, but has concrete `build` method.
<!---
Maybe this isn't necessary, and we should just have callers themselves subclass the Test class if they need custom building.
 --->
The `build` method performs runtime loading of a dynamic, caller-provided Python module which should build the test code into a build directory. This allows callers to write extensible tests that require custom build functionality without needing to modify the Microwave framework itself. 

**LinuxTest**

The `LinuxTest(Test)` subclass represents a test to run on a Linux kernel under test. The implementation is minimal, leaving complexity to be implemented by callers only as necessary; most `LinuxTest` objects just wrap short, simple bash scripts and do not need custom build or installation.

The `install` method implementation interacts with the `UbuntuDiskImage` to copy the test build directory to the image `/test` directory and modify `.bashrc` scripts to launch on boot. 

### Image
The `DiskImage` class represents the final test artifact built with both `Target` and `Test` components. Since image details can vary widely, there are almost no generic method implementations, except for `construct` and `finish_edit` methods that allow tracking when the image is being modified (in most cases, this means when the imgae is mounted).

Subclasses are responsible for implementing `download` and extending `construct`, as well as providing all necessary utilities for the `Test` and `Target` objects to implement their `install` functions.
 
 **UbuntuDiskImage**

 The `UbuntuDiskImage(DiskImage)` subclass represents an Ubuntu image and includes all necessary code to construct an image with required dependencies from a stock, downloaded `cloudimg`. While the exposed interface behaves as if each test run constructs a new image entirely from scratch, this is prohibitively slow so in the background the disk image stores three versions of the image:
 1. A 'base' image, unmodified and downloaded from [cloud-images.ubuntu.com](cloud-images.ubuntu.com). 
 2. A 'template' image, which is a duplicate of the base image but with all generic (non test-specific) modifications applied: resizing, dependency installation, passwordless root autologin. This image is only generated if it does not already exist, by booting into it with an attached `seed.iso` to configure Ubuntu's `cloud-init` functionality. 
 3. An ephemerial, per-test-run 'output' image, which begins as a duplicate of the template image and is mounted and modified (without booting) by the `KernelTest` and `KernelTarget` install functions.

The `download` method implementation simply downloads the base image if it does not exist. The `construct` method generates the template image if it does not exist, copies the template image to the output image, and mounts the output image for future modification. When the `finish_edit` function is called, the output image is unmounted and prepared for boot. When the test completes, the output image is deleted.

### Runner
`Runner` classes manage runing a compiled `DiskImage` and retrieving results. 

**KernelLogRunner**

The `KernelLogRunner` class boots an `UbuntuDiskImage` on a `KernelTarget` kernel using the [QEMU](#qemu) wrapper utility. It boots the image with configurable parameters, by default virtualized
(assuming the host has KVM support, and is of a matching architecture) with 4 GB of RAM and 4 cores.

By default, runs are non-interactive and each line is passed into a [KernelLog](#kernellog) result. Alternatively, the image can be booted interactively for debugging purposes. 

The kernel is set to display all kernel logs to standard out, and so small-volume test results can be saved by passing them to `/dev/kmsg` from within bash testing scripts. For large-volume results, this is innefficient and dififcult to parse, so the runner also configures a serial `virtio` character device within the guest which outputs to a logfile on the host. 

### Utilities
While previously described classes cover the the overall sequence of running a test, much of the most complex logic in Microwave takes place in "utilities", which wrap tools or components in a simple, Python interface.

#### KernelConfig

The `KConfig` utility wraps a Linux kernel configuration, managing parsing existing configuration files, merging multiple configurations, and producing a single `KConfig` output file.

The object can be constructed with any combination of existing `.config` files, a few pre-made `defconfig`s, and strings containing individual configuration parameters. The `generate_kconfig` method will manage merging these, and generate errors if inputs directly conflict (although while indepedent of a specific kernel source tree, cannot detect config dependency issues). 

This functionality allows testing individual configs easily; the same `defconfig` can be used, and can be merged with specific config strings only relevant to the current test. 


#### LinuxKernel

The `LinuxKernel` class wraps a local Linux kernel source tree, and manages configuring, building, and installing the source tree via
`Makefiles` from in the source tree. It is initialized with a source directory, build directory, target architecture, and `KernelConfig` object.

While the build and source directories can be the same, if they are different then none of the configuration, compilation, or installation methods will taint the source directory. In addition, `make` ensures that if the source directory is unmodified and products exist in the build directory, some or all of the build products need not be recompiled. As a result, a single cloned Linux source tree can act as the source for many build results (which share a source directory, but not a build directory), each compiled with a different configuration without triggering frequent recompilations. 

Configuration involves exporting the `KernelConfig` object to `.config` in the build directory, and running `make olddefconfig` which produces a valid `.config` object for the current kernel based on the existing `.config`, using default values for configurations not mentioned. After this, the `LinuxKernel` validates that there are no configurations set in the `KernelConfig` object that are not met in the newly generated `.config`, which might happen if the `KernelConfig` does not appropriately manage KConfig dependencies. 

Build is the simplest step, which validates the `.config` and runs `make` to compile for the target architecture. If modules are configured, the build step will also compile modules. 

Install takes in an install directory, and runs `make install`, `make headers_install`, and `make modules_install` to place each component in the `boot`, `usr/include/..`, and `lib/modules/...` folders under the install directory. 

#### QEMU

The `QEMU` utlity interfaces with `QEMU` on disk to allow booting images with a variety of parameters. While intial implementations of Microwave included a more complete `qemu` wrapper in Python, for simplicity current versions of the utility call out to runner `bash` scripts.

The utility allows configuring launch with configurations like `-enable-kvm` to allow acceleration with the target and host architectures match, `-smp` and `-m` to configure the available resources, and various `virtio` devices to collect output and interact with the guest. 

The latest version also experiments with isolation options, like `taskset` that allow launching a test with minimal interference from the rest of the  system. 

#### KernelLog

The `KernelLog` is a simple `Result` utility that wraps the log output of a kernel run. It includes helpers for parsing common line formatting, and in the future could include parsing of common test
formats like `KTAP`. 

`KernelLog` objects also include the concept of markers, that allow tests to produce tags that delimit important sections output. These objects are fully serializable, so they can be written to a JSON file on disk and later fully restored for analysis.

## Working Directory
All of the files used by Microwave are stored in a configurable `.working` directory. Though messy, sometimes debugging requires examining or editing the contents of this directory. For the moment, it is roughly organized as follows:
```bash
build/ - All Test and Target build products (copied from here into test image)
    build/tests/ - Test build products (usually, just duplicates of their source)
    build/targets/ - Target build products (potentially multiple per single target source)
targets/ - All target source repositories (should not have bulid products, or be affected by build or install operations)
tests/ - All test source repositories
temp/ - Disk images, image mountpoint, and other image-related temporary files
```
The clear separation between build and source directories allows a single source (for example, a single cloned kernel
source tree) to produce multiple independent built targets (which we use to produce kernels with a variety of configurations). This functionality is currently unused for tests, which
are still just runner bash scripts.

## Usage

Callers interact with `Microwave` by constructing a top-level `Tester` object with various `Config` objects for each of the subcomponents. These configurations fully describe the test to run, including where to retrieve the `Test` and `Target` code. The specific `Tester` they call (for example, `KernelTester`) dictates which subcomponents will be initialized. Test and Target code should be stored in Git repositories that will be cloned (or pulled) at test-time.

Then, to run a test the caller can call the `download`, `build`, and `run` functions in sequence, checking their intermediate output for failure in between each call. The `run` method returns a `Result` object, which can be saved and/or parsed by the caller to understand the output of the test. 

### Dependencies

Microwave's Python dependencies are saved in `Microwave/pyproject.toml`, and as a result should be install automatically
with the command `pip install Microwave/`. However, it includes a number of other dependencies,which can be install (on Ubuntu) with:
```bash
 apt-get update && \
    apt-get install -y \
        qemu-user \
        qemu-system \
        qemu-utils \
        binfmt-support \
        build-essential bc python3 bison flex rsync \
        libelf-dev libssl-dev libncurses-dev dwarves \
        git \
        gcc \
        gdb-multiarch \
        sudo \
        make \
        zstd \
        bsdmainutils \
        cmake \
        procps \
        kmod \
        crossbuild-essential-amd64 \
        gcc-aarch64-linux-gnu \
		gcc-x86-64-linux-gnu \
        cloud-image-utils \
        ca-certificates
```

Note that this list of dependencies might not be comprehensive on non-stock Ubuntu systems. 


## Future Work
- Build the entire framework into a docker container and write a manager to allow launching many workers, passing them jobs to run in parallel and retrieving results 
- Simplify remote authentication 
- Clean up the Test dynamic loading--maybe we should just make callers extend the Test class and define their own download/build/install methods 
- Expand to more testers: module testers, and bootloader testers 
- Clean up disk footprint 
- Improve qemu utility, maybe integrate into existing 