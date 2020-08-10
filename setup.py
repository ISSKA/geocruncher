from setuptools import setup, find_packages

from runner_test import PyTest

setup(
    name='geocruncher',
    version='0.3.1',
    description='A bridge between Gmlib and VK',
    packages=find_packages(exclude=['doc']),
    python_requires='>=3',
    install_requires=['numpy'],
    tests_require=['pytest'],
    cmdclass = {'test': PyTest},
#    scripts=['GeoCruncher/main.py']
    entry_points='''
        [console_scripts]
        geocruncher=geocruncher.main:main
    ''',
)
