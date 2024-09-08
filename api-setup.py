from setuptools import setup, find_packages

setup(
    name='api',
    version='1.0.0',
    description='The Geocruncher API layer',
    packages=find_packages(include=['api']),
    python_requires='>=3.9',
    entry_points='''
        [console_scripts]
        api=api.api:main
    ''',
)
