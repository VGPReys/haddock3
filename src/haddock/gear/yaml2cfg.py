"""
Parse data from HADDOCK3 to YAML and YAML to HADDOCK3 and related.

Accross this file you will see references to "yaml" as variables and
function names. In these cases, we always mean the HADDOCK3 YAML
configuration files which have specific keys.
"""
import os
from collections.abc import Mapping

from haddock.libs.libio import read_from_yaml


def yaml2cfg_text(ymlcfg, module):
    """
    Convert HADDOCK3 YAML config to HADDOCK3 user config text.

    Adds commentaries with help strings.

    Parameters
    ----------
    ymlcfg : dict
        The dictionary representing the HADDOCK3 config file.

    module : str
        The module to which the config belongs to.

    expert_levels : list-list
        A list with the expert levels to consider. Defaults to all.
    """
    new_config = []
    new_config.append(f"[{module}]")

    new_config.append(_yaml2cfg_text(ymlcfg, module))

    return os.linesep.join(new_config) + os.linesep


def _yaml2cfg_text(ycfg, module):
    """
    Convert HADDOCK3 YAML config to HADDOCK3 user config text.

    Does not consider expert levels.
    See :func:`yaml2cfg_text_with_explevels` instead.

    Parameters
    ----------
    ycfg : dict
        The dictionary representing the HADDOCK3 YAML configuration.
        This configuration should NOT have the expertise levels. It
        expectes the first level of keys to be the parameter name.
    """
    params = []

    for param_name, param in ycfg.items():

        # "default" is not in param when the key points to a subdictionary
        # of parameters.
        if isinstance(param, Mapping) and "default" not in param:

            params.append("")  # give extra space
            curr_module = f"{module}.{param_name}"
            params.append(f"[{curr_module}]")
            params.append(_yaml2cfg_text(param, module=curr_module))

        elif isinstance(param, Mapping):

            comment = []
            for _comment, cvalue in param.items():
                if _comment in ("default", "explevel", "short", "long", "type"):
                    continue

                if not cvalue:
                    continue

                comment.append(f"${_comment} {cvalue}")

            params.append("{} = {!r}  # {}".format(
                param_name,
                param["default"],
                " / ".join(comment),
                ))

            if param["type"] == "list":
                params.append(os.linesep)

        else:
            # ignore some other parameters that are defined for sections.
            continue

    return os.linesep.join(params)


def read_from_yaml_config(cfg_file):
    """Read config from yaml by collapsing the expert levels."""
    ycfg = read_from_yaml(cfg_file)
    # there's no need to make a deep copy here, a shallow copy suffices.
    cfg = {}
    cfg.update(flat_yaml_cfg(ycfg))
    return cfg


def flat_yaml_cfg(cfg):
    """Flat a yaml config."""
    new = {}
    for param, values in cfg.items():
        try:
            new_value = values["default"]
        except KeyError:
            new_value = flat_yaml_cfg(values)
        except TypeError:
            # happens when values is a string for example,
            # addresses `explevel` in `mol*` topoaa.
            continue

        new[param] = new_value
    return new
