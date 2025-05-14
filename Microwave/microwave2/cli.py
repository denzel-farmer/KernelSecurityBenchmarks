import click

from microwave2.images.ubuntu_image import UbuntuDiskImage
from microwave2.utils.utils import Arch
from microwave2.controller import run_config_file
import platform
# from microwave2.controller import run_kmod_test

@click.group()
def cli():
	print("inCLI worker")
	pass

@cli.command()
@click.option('--configpath', type=click.STRING, required=True)
def run_config(configpath):
    print("Running config")
    print("Config Path:", configpath)

    run_config_file(configpath)

@cli.command()
@click.option('--arch', type=click.Choice(['x86', 'arm']), required=True, help='Architecture of the image')
@click.option('--image_name', type=click.STRING, required=True, help='Name of the image')
@click.option('--rebuild', is_flag=True, default=False, help='Rebuild the base image and start from scratch??')
@click.option('--skip_boot', is_flag=True, default=False, help='Skip booting the image interactively')
def create_ubuntu_image(arch, image_name, rebuild, skip_boot):
    print("Creating Ubuntu image")
    print("Architecture:", arch)
    print("Image Name:", image_name)
    print("Rebuild:", rebuild)
    print("Skip Boot:", skip_boot)
    
    image = UbuntuDiskImage(arch=Arch.from_string(arch), image_name=image_name)
    image.construct(rebuild=rebuild, editable=False)

    # Check if arch matches the current system
    enable_kvm = False
    # if image.arch != Arch.from_platform():
    #       enable_kvm = False

    if not skip_boot:
        image.boot_interactive(enable_kvm=enable_kvm)


@cli.command()
@click.option('--arch', type=click.Choice(['x86', 'arm']), required=True, help='Architecture of the image')
@click.option('--redownload', is_flag=True, default=False, help='Redownload the base image and start from scratch')
@click.option('--rebuild_template', is_flag=True, default=False, help='Reconfigure starting from the current base image')
def modify_template_image(arch, redownload, rebuild_template):
    print("Architecture:", arch)    

    image = UbuntuDiskImage(arch=Arch.from_string(arch), image_name=None)
    image.build_template_image(rebuild=rebuild_template, redownload=redownload)
    image.boot_template_image()


# @cli.command()
# def run_kmod_sample():
#     print("Running Sample Kernel Module Test")

#     run_kmod_test()

# @cli.command()
# # Path to config JSON
# @click.option('--configpath', type=click.STRING, required=True)
# @click.option('--run_name', type=click.STRING, required=False, default=None)
# @click.option('--no_launch', is_flag=True, default=False)
# def run_test_batch(configpath, run_name, no_launch):
# 	print("Running test batch")
# 	print("Config Path:", configpath)


# 	controller = Controller(config_path=configpath, run_name=run_name)
# 	controller.run_batch(no_launch=no_launch)


# @cli.command()
# # Configpath 
# @click.option('--configpath', type=click.STRING, required=True)
# def teardown(configpath):
# 	print("Tearing down")
# 	print("Config Path:", configpath)

# 	controller = Controller(config_path=configpath)
# 	controller.teardown_workers()


# @cli.command()
# # Configpath
# @click.option('--configpath', type=click.STRING, required=True)
# def build_push_microwave(configpath):
# 	print("Downloading manifests")
# 	print("Config Path:", configpath)

# 	controller = Controller(config_path=configpath)
# 	controller.build_push_microwave()


# @cli.command()
# def create_single_worker():

if __name__ == "__main__":
	cli()