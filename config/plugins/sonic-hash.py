"""
This CLI plugin was auto-generated by using 'sonic-cli-gen' utility
"""

import click
import utilities_common.cli as clicommon
from sonic_py_common import logger


HASH_FIELD_LIST = [
    "IN_PORT",
    "DST_MAC",
    "SRC_MAC",
    "ETHERTYPE",
    "VLAN_ID",
    "IP_PROTOCOL",
    "DST_IP",
    "SRC_IP",
    "L4_DST_PORT",
    "L4_SRC_PORT",
    "INNER_DST_MAC",
    "INNER_SRC_MAC",
    "INNER_ETHERTYPE",
    "INNER_IP_PROTOCOL",
    "INNER_DST_IP",
    "INNER_SRC_IP",
    "INNER_L4_DST_PORT",
    "INNER_L4_SRC_PORT"
]


log = logger.Logger()
log.set_min_log_priority_info()

#
# Hash validators -----------------------------------------------------------------------------------------------------
#

def hash_field_validator(ctx, param, value):
    """
    Check if hash field arg is valid
    Args:
        ctx: click context
        param: click parameter context
        value: value of parameter
    Returns:
        str: validated parameter
    """

    for hash_field in value:
        click.Choice(HASH_FIELD_LIST).convert(hash_field, param, ctx)

    return list(value)

#
# Hash DB interface ---------------------------------------------------------------------------------------------------
#

def update_entry_validated(db, table, key, data, create_if_not_exists=False):
    """ Update entry in table and validate configuration.
    If attribute value in data is None, the attribute is deleted.

    Args:
        db (swsscommon.ConfigDBConnector): Config DB connector obect.
        table (str): Table name to add new entry to.
        key (Union[str, Tuple]): Key name in the table.
        data (Dict): Entry data.
        create_if_not_exists (bool):
            In case entry does not exists already a new entry
            is not created if this flag is set to False and
            creates a new entry if flag is set to True.
    Raises:
        Exception: when cfg does not satisfy YANG schema.
    """

    cfg = db.get_config()
    cfg.setdefault(table, {})

    if not data:
        raise click.ClickException(f"No field/values to update {key}")

    if create_if_not_exists:
        cfg[table].setdefault(key, {})

    if key not in cfg[table]:
        raise click.ClickException(f"{key} does not exist")

    entry_changed = False
    for attr, value in data.items():
        if value == cfg[table][key].get(attr):
            continue
        entry_changed = True
        if value is None:
            cfg[table][key].pop(attr, None)
        else:
            cfg[table][key][attr] = value

    if not entry_changed:
        return

    db.set_entry(table, key, cfg[table][key])

#
# Hash CLI ------------------------------------------------------------------------------------------------------------
#

@click.group(
    name="switch-hash",
    cls=clicommon.AliasedGroup
)
def SWITCH_HASH():
    """ Configure switch hash feature """

    pass


@SWITCH_HASH.group(
    name="global",
    cls=clicommon.AliasedGroup
)
@clicommon.pass_db
def SWITCH_HASH_GLOBAL(db):
    """ Configure switch hash global """

    pass


@SWITCH_HASH_GLOBAL.command(
    name="ecmp-hash"
)
@click.argument(
    "ecmp-hash",
    nargs=-1,
    required=True,
    callback=hash_field_validator,
)
@clicommon.pass_db
def SWITCH_HASH_GLOBAL_ecmp_hash(db, ecmp_hash):
    """ Hash fields for hashing packets going through ECMP """

    ctx = click.get_current_context()

    table = "SWITCH_HASH"
    key = "GLOBAL"
    data = {
        "ecmp_hash": ecmp_hash,
    }

    try:
        update_entry_validated(db.cfgdb, table, key, data, create_if_not_exists=True)
        log.log_notice("Configured switch global ECMP hash: {}".format(", ".join(ecmp_hash)))
    except Exception as e:
        log.log_error("Failed to configure switch global ECMP hash: {}".format(str(e)))
        ctx.fail(str(e))


@SWITCH_HASH_GLOBAL.command(
    name="lag-hash"
)
@click.argument(
    "lag-hash",
    nargs=-1,
    required=True,
    callback=hash_field_validator,
)
@clicommon.pass_db
def SWITCH_HASH_GLOBAL_lag_hash(db, lag_hash):
    """ Hash fields for hashing packets going through LAG """

    ctx = click.get_current_context()

    table = "SWITCH_HASH"
    key = "GLOBAL"
    data = {
        "lag_hash": lag_hash,
    }

    try:
        update_entry_validated(db.cfgdb, table, key, data, create_if_not_exists=True)
        log.log_notice("Configured switch global LAG hash: {}".format(", ".join(lag_hash)))
    except Exception as err:
        log.log_error("Failed to configure switch global LAG hash: {}".format(str(err)))
        ctx.fail(str(err))


def register(cli):
    """ Register new CLI nodes in root CLI.

    Args:
        cli: Root CLI node.
    Raises:
        Exception: when root CLI already has a command
                   we are trying to register.
    """
    cli_node = SWITCH_HASH
    if cli_node.name in cli.commands:
        raise Exception(f"{cli_node.name} already exists in CLI")
    cli.add_command(SWITCH_HASH)