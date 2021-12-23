"""HADDOCK3 modules."""
import contextlib
import os
import shutil
from abc import ABC, abstractmethod
from functools import partial
from pathlib import Path

from haddock import log as log
from haddock import toppar_path as global_toppar
from haddock.core.defaults import MODULE_IO_FILE
from haddock.core.exceptions import StepError
from haddock.gear.config_reader import read_config
from haddock.libs.libhpc import HPCScheduler
from haddock.libs.libontology import ModuleIO
from haddock.libs.libparallel import Scheduler
from haddock.libs.libutil import recursive_dict_update


modules_folder = Path(__file__).resolve().parent

_folder_match_regex = '[a-zA-Z]*/'
modules_category = {
    module.name: category.name
    for category in modules_folder.glob(_folder_match_regex)
    for module in category.glob(_folder_match_regex)
    }
"""Indexes each module in its specific category. Keys are Paths to the module,
values are their categories. Categories are the modules parent folders."""


general_parameters_affecting_modules = {
    'cns_exec',
    'concat',
    'mode',
    'ncores',
    'queue',
    'queue_limit',
    'relative_envvars',
    }
"""These parameters are general parameters that may be applicable to modules
specifically. Therefore, they should be considered as part of the "default"
module's parameters. Usually, this set is used to filter parameters during
the run prepraration phase. See, `gear.prepare_run`."""


class BaseHaddockModule(ABC):
    """HADDOCK3 module's base class."""

    def __init__(self, order, path, params, cns_script=""):
        """
        HADDOCK3 modules base class.

        Parameters
        ----------
        params : dict or path to HADDOCK3 configuration file
            A dictionary or a path to a HADDOCK3 configuration file
            containing the initial module parameters. Usually this is
            defined by the default params.
        """
        self.order = order
        self.path = path
        self.previous_io = self._load_previous_io()
        self.params = params

        if cns_script:
            self.cns_folder_path = cns_script.resolve().parent
            self.cns_protocol_path = cns_script
            self.toppar_path = global_toppar


        try:
            with open(self.cns_protocol_path) as input_handler:
                self.recipe_str = input_handler.read()
        except FileNotFoundError:
            _msg = f"Error while opening workflow {self.cns_protocol_path}"
            raise StepError(_msg)
        except AttributeError:
            # No CNS-like module
            pass

    @property
    def params(self):
        """Configuration parameters."""  # noqa: D401
        return self._params

    @params.setter
    def params(self, path_or_dict):
        if isinstance(path_or_dict, dict):
            self._params = path_or_dict
        else:
            try:
                self._params = read_config(path_or_dict)
            except FileNotFoundError as err:
                _msg = (
                    "Default configuration file not found: "
                    f"{str(path_or_dict)!r}"
                    )
                raise FileNotFoundError(_msg) from err
            except TypeError as err:
                _msg = (
                    "Argument does not satisfy condition, must be path or "
                    f"dict. {type(path_or_dict)} given."
                    )
                raise TypeError(_msg) from err

    def run(self, **params):
        """Execute the module."""
        log.info(f'Running [{self.name}] module')
        self.update_params(**params)
        self.params.setdefault('ncores', None)
        self.params.setdefault('cns_exec', None)
        self.params.setdefault('mode', None)
        self.params.setdefault('concat', None)
        self.params.setdefault('queue_limit', None)
        self.params.setdefault('relative_envvars', True)
        self.params.setdefault('self_contained', False)

        if getattr(self, 'toppar_path', False) and self.params['self_contained']:
            self.cns_folder_path = shutil.copytree(
                self.cns_folder_path,
                Path(self.path, self.cns_folder_path.name),
                )

            self.toppar_path = Path(global_toppar.name)
            if not self.toppar_path.exists():
                shutil.copytree(global_toppar, self.toppar_path)

        if getattr(self, "cns_protocol_path", False):
            self.envvars = self.default_envvars()
            if self.params['self_contained']:
                self.save_envvars(**self.envvars)
        self._run()
        log.info(f'Module [{self.name}] finished.')

    @classmethod
    @abstractmethod
    def confirm_installation(self):
        """
        Confirm the third-party software needed for the module is installed.

        HADDOCK3's own modules should just return.
        """
        return

    def finish_with_error(self, message=""):
        """Finish with error message."""
        if not message:
            message = "Module has failed"
        log.error(message)
        raise SystemExit

    def _load_previous_io(self):
        if self.order == 0:
            return ModuleIO()

        io = ModuleIO()
        previous_io = self.previous_path() / MODULE_IO_FILE
        if previous_io.is_file():
            io.load(previous_io)
        return io

    def previous_path(self):
        """Give the path from the previous calculation."""
        previous = sorted(list(self.path.resolve().parent.glob('[0-9][0-9]*/')))
        try:
            return previous[self.order - 1]
        except IndexError:
            return self.path

    def update_params(self, **parameters):
        """Update defaults parameters with run-specific parameters."""
        self.params = recursive_dict_update(self._params, parameters)

    def log(self, msg, level='info'):
        """
        Log a message with a common header.

        Currently the header is the [MODULE NAME] in square brackets.

        Parameters
        ----------
        msg : str
            The log message.

        level : str
            The level log: 'debug', 'info', ...
            Defaults to 'info'.
        """
        getattr(log, level)(f'[{self.name}] {msg}')

    def default_envvars(self, **envvars):
        """Return default env vars updated to `envvars` (if given)."""
        default_envvars = {
            "MODULE": self.cns_folder_path,
            "MODDIR": self.path,
            "TOPPAR": self.toppar_path,
            }

        default_envvars.update(envvars)
        print(default_envvars)

        return default_envvars

    def save_envvars(self, filename="envvars", **envvars):
        """Save envvars needed for CNS to a file in the module's folder."""
        #print(envvars.values())

        # there are so few variables, best to handle them by hand
        lines = (
            "#!/bin/bash",
            "# for debugging purposes source this file from within the ",
            "# module folder for example, from within '00_topoaa'",
            'SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )',
            "export MODULE=${SCRIPT_DIR}/cns",
            "export MODDIR=${SCRIPT_DIR}",
            "export TOPPAR=${SCRIPT_DIR}/../toppar",
            )



        #common_path = os.path.commonpath(list(envvars.values()))

        #envvars = {
        #    k: v.relative_to(common_path)
        #    for k, v in envvars.items()
        #    }

        #if relative:
        #    rel_path = '../' * len(envvars['MODDIR'].parents)

        #    envvars = {
        #        k: Path(rel_path, v) if k != 'MODDIR' else "$PWD"
        #        for k, v in envvars.items()
        #        }

        #    # SyntaxError: f-string expression part cannot include a backslash
        #    lines = (
        #        "export " + k + "=" + str(v)
        #        for k, v in envvars.items()
        #        )

        #else:
        #    lines = (
        #        "export " + k + "=${COMMON_PATH_FOR_HD3}/" + str(v)
        #        for k, v in envvars.items()
        #        )

        #banshee = "#!/bin/bash" + os.linesep
        #root = "export COMMON_PATH_FOR_HD3={}".format(common_path) + os.linesep
        fstr = os.linesep.join(lines)
        Path(self.path, filename).write_text(fstr)
        return


def get_engine(mode, params):
    """
    Create an engine to run the jobs.

    Parameters
    ----------
    mode : str
        The type of engine to create

    params : dict
        A dictionary containing parameters for the engine.
        `get_engine` will retrieve from `params` only those parameters
        needed and ignore the others.
    """
    # a bit of a factory pattern here
    # this might end up in another module but for now its fine here
    if mode == 'hpc':
        return partial(
            HPCScheduler,
            target_queue=params['queue'],
            queue_limit=params['queue_limit'],
            concat=params['concat'],
            )

    elif mode == 'local':
        return partial(
            Scheduler,
            ncores=params['ncores'],
            )

    else:
        available_engines = ('hpc', 'local')
        raise ValueError(
            f"Scheduler `mode` {mode!r} not recognized. "
            f"Available options are {', '.join(available_engines)}"
            )
