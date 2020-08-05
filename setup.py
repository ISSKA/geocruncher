from setuptools import setup, find_packages

setup(
    name='geocruncher',
    version='0.3.1',
    description='A bridge between Gmlib and VK',
    packages=find_packages(exclude=['doc']),
    python_requires='>=3',
    setup_requires=['pytest-runner'],
    install_requires=['numpy'],
    tests_require=['pytest'],
    #scripts=['GeoCruncher/main.py']
    entry_points='''
        [console_scripts]
        geocruncher=geocruncher.main:main
    ''',
)
