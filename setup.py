from setuptools import setup, find_packages

setup(
    name='homely',
    description=('Automate the installation of your personal config files and'
                 ' favourite tools'),
    url='https://github.com/toomuchphp/homely/',
    author='Peter Hodge',
    license='MIT',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Topic :: Utilities',
    ],
    keywords='dotfiles environment configuration tools utilities automation',
    packages=find_packages(),
    install_requires=['simplejson', 'click', 'requests'],
    scripts=['bin/homely'],
    # automatic version number using setuptools_scm
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
    write_to='homely/__init__.py',
)
