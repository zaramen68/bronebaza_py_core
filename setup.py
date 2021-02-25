import os
from os.path import join, dirname

from setuptools import setup, find_packages

from version import VERSION

lib_folder = os.path.dirname(os.path.realpath(__file__))
requirementPath = lib_folder + '/requirements.txt'
install_requires = []
if os.path.isfile(requirementPath):
    with open(requirementPath) as f:
        install_requires = f.read().splitlines()

setup(
    name='spread',
    description='AWADA Light Logic',
    license='https://awada.ru/',
    author='Pavel Danilov',
    author_email='Danilov@throne-bms.com',
    url='https://kiwi.throne.systems/index.php/Tron/Iot',
    version=VERSION,
    install_requires=install_requires,
    packages=find_packages(),
    long_description=open(join(dirname(__file__), 'README.md')).read(),
    entry_points={
        'console_scripts':
            [
                'dali_manager = spread_core.dali_manager:run',
                'lighting_equipment = spread_core.lighting_equipment:run',
                'mercury_manager = spread_core.mercury_manager:run',
                'tcp_adapter = spread_core.tcp_adapter:run',
                'project_adapter = spread_core.project_adapter:run',
                'scheduler = spread_core.schedule_launcher:run',
                'scripter = spread_core.script_launcher:run',
                'lom_manager = spread_core.lom_manager:run'
            ]
    }
)
