from setuptools import setup, find_packages

setup(
    name='geocruncher',
    version='0.1.0',
    description='A bridge between Gmlib and VK',
    packages=find_packages(exclude=['doc']),
    python_requires='>=3',
    install_requires=['numpy']
)
