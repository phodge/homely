from setuptools import setup, find_packages

setup(
    name='homely',
    version='dev',
    packages=find_packages(),
    include_package_data=True,
    install_requires=['simplejson', 'click'],
    entry_points='''
        [console_scripts]
        homely=homely._scripts.homely:main
    ''',
)
