from setuptools import find_packages, setup

setup(
    name='homely',
    description=('Automate the installation of your personal config files and'
                 ' favourite tools using Python. https://homely.readthedocs.io/'),
    url='https://homely.readthedocs.io/',
    author='Peter Hodge',
    license='MIT',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Topic :: Utilities',
    ],
    keywords='dotfiles environment configuration tools utilities automation',
    packages=['homely'] + ['homely.{}'.format(p)
                           for p in find_packages('homely')],
    install_requires=['simplejson', 'click', 'requests', 'python-daemon'],
    entry_points={
        'console_scripts': ['homely=homely._cli:main'],
    },
    # automatic version number using setuptools_scm
    setup_requires=['setuptools_scm'],
    use_scm_version={
        "write_to": 'homely/__init__.py',
    },
)
