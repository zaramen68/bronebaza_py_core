import spread_core.bam.dali.managers
import spread_core.bam.dali.providers
import spread_core.bam.lom
import spread_core.bam.mercury
from spread_core.bam.engineries import Enginery
from spread_core.bam.managers import Manager
from spread_core.bam.providers import Provider
from spread_core.bam.subgineries import Subginery
from spread_core.errors.project_errors import ProjectError
from spread_core.tools import utils

_all = [
    spread_core.bam.dali.managers,
    spread_core.bam.dali.providers,
    spread_core.bam.lom,
    spread_core.bam.mercury
]


def generate_enginery(project_id, data, manager_data):
    def separator(subclass): return issubclass(subclass, Enginery) and subclass.__name__ == data['type']
    res = utils.get_subclass(Enginery, separator)

    if res:
        return res(project_id, data, manager_data)
    else:
        raise ProjectError('Unknown enginery type', data=data)


def generate_subginery(project_id, data):
    def separator(subclass): return issubclass(subclass, Subginery) and subclass.__name__ == data['type']
    res = utils.get_subclass(Subginery, separator)

    if res:
        return res(project_id, data)
    else:
        raise ProjectError('Unknown subginery type', data=data)


def generate_provider(data):
    def separator(subclass): return issubclass(subclass, Provider) and subclass.__name__ == data['type']
    res = utils.get_subclass(Provider, separator)

    if res:
        return res(data)
    else:
        raise ProjectError('Unknown provider type', data=data)


def generate_manager(p_id, _type, m_id):
    def separator(subclass): return issubclass(subclass, Manager) and subclass.__name__ == _type
    res = utils.get_subclass(Manager, separator)

    if res:
        return res(p_id, m_id)
    else:
        raise ProjectError('Unknown manager type', type=_type, id=m_id)
