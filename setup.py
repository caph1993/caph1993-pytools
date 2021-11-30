from setuptools import setup, find_packages
from cp93pytools import VERSION
'''
For submitting to PyPi: python3 sumbit.py
'''

setup(
    name='caph1993-pytools',
    version=VERSION,
    description='Python toolbox of Carlos Pinzón',
    url='https://github.com/caph1993/caph1993-pytools',
    author='Carlos Pinzón',
    author_email='caph1993@gmail.com',
    license='MIT',
    packages=find_packages(),
    install_requires=[
        'typing-extensions',
    ],
    classifiers=[
        'Development Status :: 1 - Planning',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
)