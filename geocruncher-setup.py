from setuptools import setup, find_packages

from runner_test import PyTest

setup(
    name='geocruncher',
    version='0.4.0',
    description='A bridge between Gmlib and VK',
    packages=find_packages(include=['geocruncher']),
    python_requires='>=3.9',
    install_requires=['numpy'],
    tests_require=['pytest'],
    cmdclass={'test': PyTest},
    entry_points='''
        [console_scripts]
        geocruncher=geocruncher.main:main
    ''',
)
