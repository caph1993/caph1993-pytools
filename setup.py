from setuptools import setup
'''
To upload:
python3 setup.py check
python3 setup.py sdist
twine upload dist/*
'''

setup(
    name='caph1993-pytools',
    version='0.1.4',
    description='Python toolbox of Carlos Pinzón',
    url='https://github.com/caph1993/caph1993-pytools',
    author='Carlos Pinzón',
    author_email='caph1993@gmail.com',
    license='MIT',
    packages=[
        'cp93storage',
        'cp93functools',
    ],
    install_requires=[],
    classifiers=[
        'Development Status :: 1 - Planning',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
)