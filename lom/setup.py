from setuptools import setup, find_packages

VERSION = 1.0

setup(
    name='lom',
    description='AWADA LoraWan Solution',
    license='https://awada.ru/',
    author='Pavel Danilov',
    author_email='Danilov@throne-bms.com',
    url='https://kiwi.throne.systems/index.php/Tron/Iot/Solution/Lom',
    version=VERSION,
    packages=find_packages(),
    # entry_points={
    #     'console_scripts':
    #         [
    #             'dali_manager = spread_core.dali_manager:run',
    #             'lighting_equipment = spread_core.lighting_equipment:run',
    #             'mercury_manager = spread_core.mercury_manager:run',
    #             'tcp_adapter = spread_core.tcp_adapter:run',
    #             'project_adapter = spread_core.project_adapter:run',
    #             'scheduler = spread_core.schedule_launcher:run',
    #             'scripter = spread_core.script_launcher:run'
    #         ]
    # }
)
