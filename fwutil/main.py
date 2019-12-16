#!/usr/bin/env python
#
# main.py
#
# Command-line utility for interacting with platform components within SONiC
#

try:
    import os
    import click
    import urllib
    import tempfile
    from lib import PlatformDataProvider, ComponentStatusProvider, ComponentUpdateProvider
    from lib import SquashFs, URL, Logger
except ImportError as e:
    raise ImportError("%s - required module not found" % str(e))

# ========================= Constants ==========================================

VERSION = '1.0.0.0'

SYSLOG_IDENTIFIER = "fwutil"

CHASSIS_NAME_CTX_KEY = "chassis_name"
MODULE_NAME_CTX_KEY = "module_name"
COMPONENT_CTX_KEY = "component"
COMPONENT_PATH_CTX_KEY = "component_path"
URL_CTX_KEY = "url"

TAB = "    "
FW_SUFFIX = ".fw"
PATH_SEPARATOR = "/"
IMAGE_NEXT = "next"
HELP = "?"


#IMAGE_CURRENT = "current"
#IMAGE_NEXT = "next"

STATUS_SUCCESS = "success"
STATUS_FAILURE = "failure"

EXIT_SUCCESS = 0
EXIT_FAILURE = 1

ROOT_UID = 0

# ========================= Variables ==========================================

pdp = PlatformDataProvider()
logger = Logger(SYSLOG_IDENTIFIER)

# ========================= Helper functions ===================================

def log_fw_action_start(action, component, firmware):
    caption = "Firmware {} started".format(action)
    template = "{}: component={}, firmware={}"

    logger.log_info(
        template.format(
            caption,
            component,
            firmware
        )
    )

def log_fw_action_end(action, component, firmware, status, exception=None):
    caption = "Firmware {} ended".format(action)

    status_template = "{}: component={}, firmware={}, status={}"
    exception_template = "{}: component={}, firmware={}, status={}, exception={}"

    if status:
        logger.log_info(
            status_template.format(
                caption,
                component,
                firmware,
                STATUS_SUCCESS
            )
        )
    else:
        if exception is None:
            logger.log_error(
                status_template.format(
                    caption,
                    component,
                    firmware,
                    STATUS_FAILURE
                )
            )
        else:
            logger.log_error(
                exception_template.format(
                    caption,
                    component,
                    firmware,
                    STATUS_FAILURE,
                    str(exception)
                )
            )

def log_fw_install_start(component, firmware):
    action = "install"

    log_fw_action_start(action, component, firmware)

def log_fw_install_end(component, firmware, status, exception=None):
    action = "install"

    log_fw_action_end(action, component, firmware, status, exception)

def log_fw_download_start(component, firmware):
    action = "download"

    log_fw_action_start(action, component, firmware)

def log_fw_download_end(component, firmware, status, exception=None):
    action = "download"

    log_fw_action_end(action, component, firmware, status, exception)

def cli_show_help(ctx):
    click.echo(ctx.get_help())
    ctx.exit(EXIT_SUCCESS)

#def cli_show_help(ctx):

def cli_abort(ctx, e):
    click.echo("Error: " + str(e) + ". Aborting...")
    ctx.abort()

# ========================= CLI commands and groups ============================

# 'fwutil' command main entrypoint
@click.group()
@click.pass_context
def cli(ctx):
    """fwutil - Command line utility for managing platform components"""

    if os.geteuid() != ROOT_UID:
        click.echo("Error: Root privileges are required. Aborting...")
        ctx.abort()

    ctx.ensure_object(dict)

# 'install' group
@cli.group()
@click.pass_context
def install(ctx):
    """Install platform firmware"""
    ctx.obj[COMPONENT_PATH_CTX_KEY] = [ ]

# 'chassis' subgroup
@click.group()
@click.pass_context
def chassis(ctx):
    """Install chassis firmware"""
    ctx.obj[CHASSIS_NAME_CTX_KEY] = pdp.chassis.get_name()
    ctx.obj[COMPONENT_PATH_CTX_KEY].append(pdp.chassis.get_name())

def validate_module(ctx, param, value):
    if value == HELP:
        cli_show_help(ctx)

    if not pdp.is_modular_chassis():
        ctx.fail("Unsupported platform: non modular chassis.")

    if value not in pdp.module_component_map:
        ctx.fail("Invalid value for \"{}\": Module \"{}\" does not exist.".format(param.metavar, value))

    return value

# 'module' subgroup
@click.group()
@click.argument('module_name', metavar='<module_name>', callback=validate_module)
@click.pass_context
def module(ctx, module_name):
    """Install module firmware"""
    ctx.obj[MODULE_NAME_CTX_KEY] = module_name
    ctx.obj[COMPONENT_PATH_CTX_KEY].append(pdp.chassis.get_name())
    ctx.obj[COMPONENT_PATH_CTX_KEY].append(module_name)

def validate_component(ctx, param, value):
    if value == HELP:
        cli_show_help(ctx)

    if CHASSIS_NAME_CTX_KEY in ctx.obj:
        chassis_name = ctx.obj[CHASSIS_NAME_CTX_KEY]
        if value in pdp.chassis_component_map[chassis_name]:
            ctx.obj[COMPONENT_CTX_KEY] = pdp.chassis_component_map[chassis_name][value]
            return value

    if MODULE_NAME_CTX_KEY in ctx.obj:
        module_name = ctx.obj[MODULE_NAME_CTX_KEY]
        if value in pdp.module_component_map[module_name]:
            ctx.obj[COMPONENT_CTX_KEY] = pdp.module_component_map[module_name][value]
            return value

    ctx.fail("Invalid value for \"{}\": Component \"{}\" does not exist.".format(param.metavar, value))

# 'component' subgroup
@click.group()
@click.argument('component_name', metavar='<component_name>', callback=validate_component)
@click.pass_context
def component(ctx, component_name):
    """Install component firmware"""
    ctx.obj[COMPONENT_PATH_CTX_KEY].append(component_name)

def install_fw(ctx, fw_path):
    component = ctx.obj[COMPONENT_CTX_KEY]
    component_path = PATH_SEPARATOR.join(ctx.obj[COMPONENT_PATH_CTX_KEY])

    status = False

    try:
        click.echo("Installing firmware:")
        click.echo(TAB + fw_path)
        log_fw_install_start(component_path, fw_path)
        status = component.install_firmware(fw_path)
        #raise RuntimeError("Something bad happend during FW install...")
        log_fw_install_end(component_path, fw_path, status)
    except Exception as e:
        log_fw_install_end(component_path, fw_path, status, e)
        cli_abort(ctx, e)

    if not status:
        click.echo("Error: Firmware install failed.")
        ctx.exit(EXIT_FAILURE)

def download_fw(ctx, url):
    fw_path_tmp = None

    with tempfile.NamedTemporaryFile(suffix=FW_SUFFIX, delete=True) as file_tmp:
        fw_path_tmp = file_tmp.name

    component_path = PATH_SEPARATOR.join(ctx.obj[COMPONENT_PATH_CTX_KEY])

    try:
        click.echo("Downloading firmware:")
        log_fw_download_start(component_path, str(url))
        filename, headers = url.retrieve(fw_path_tmp)
        log_fw_download_end(component_path, str(url), True)
    except Exception as e:
        log_fw_download_end(component_path, str(url), False, str(e))
        cli_abort(ctx, e)

    return fw_path_tmp

def validate_fw(ctx, param, value):
    if value == HELP:
        cli_show_help(ctx)

    url = URL(value)

    if not url.is_url():
        path = click.Path(exists=True)
        path.convert(value, param, ctx)
    else:
        ctx.obj[URL_CTX_KEY] = url

    return value

# 'fw' subcommand
@component.command()
@click.option('-y', '--yes', 'yes', is_flag=True, help="Assume \"yes\" as answer to all prompts and run non-interactively")
@click.argument('fw_path', metavar='<fw_path>', callback=validate_fw)
@click.pass_context
def fw(ctx, yes, fw_path):
    """Install firmware from local binary or URL"""
    if not yes:
        click.confirm("New firmware will be installed, continue?", abort=True)

    url = None

    if URL_CTX_KEY in ctx.obj:
        url = ctx.obj[URL_CTX_KEY]
        fw_path = download_fw(ctx, url)

    try:
        install_fw(ctx, fw_path)
    finally:
        if url is not None and os.path.exists(fw_path):
            os.remove(fw_path)

def validate_image(ctx, param, value):
    #value = "test "
    return value






#    if not status:
#        click.echo("Error: Firmware install failed.")
#        ctx.exit(EXIT_FAILURE)




#def cli_abort(ctx, e):
#    click.echo("Error: " + str(e) + ". Aborting...")
#    ctx.abort()

# 'update' subgroup
@cli.group(invoke_without_command=True)
@click.option('-y', '--yes', 'yes', is_flag=True, show_default=True, help="Assume \"yes\" as answer to all prompts and run non-interactively")
@click.option('-f', '--force', 'force', is_flag=True, show_default=True, help="Install firmware regardless the current version")
@click.option('-i', '--image', 'image', type=click.Choice(["current", "next"]), default="current", show_default=True, callback=validate_image, help="Update firmware using current/next image")
@click.pass_context
def update(ctx, yes, force, image):
    """Update platform firmware"""
    aborted = False

    try:
        squashfs = None

        try:
            cup = None

            if image == IMAGE_NEXT:
                squashfs = SquashFs()
                fs_path = squashfs.mount_next_image_fs()
                cup = ComponentUpdateProvider(fs_path)
            else:
                cup = ComponentUpdateProvider()

            click.echo(cup.get_status(force))

            if not yes:
                click.confirm("New firmware will be installed, continue?", abort=True)

            result = cup.update_firmware(force)

            click.echo()
            click.echo("Summary:")
            click.echo()

            click.echo(result)
        except click.Abort:
            aborted = True
        except Exception as e:
            aborted = True
            click.echo("Error: " + str(e) + ". Aborting...")

        if image == IMAGE_NEXT and squashfs is not None:
            squashfs.umount_next_image_fs()
    except Exception as e:
        cli_abort(ctx, e)

    if aborted:
        ctx.abort()

# 'show' subgroup
@cli.group()
def show():
    """Display platform info"""
    pass

# 'status' subcommand
@show.command()
def status():
    """Show platform components status"""
    csp = ComponentStatusProvider()
    click.echo(csp.get_status())

# 'version' subcommand
@show.command()
def version():
    """Show utility version"""
    click.echo("fwutil version {0}".format(VERSION))

install.add_command(chassis)
install.add_command(module)

chassis.add_command(component)
module.add_command(component)

if __name__ == '__main__':
    cli()
