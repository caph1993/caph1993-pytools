from setuptools import setup
'''
sh sumbit.sh
    rm dist/*
    python3 setup.py check
    python3 setup.py sdist
    twine upload dist/*
    pip3 install --upgrade caph1993-pytools
    pip3 install --upgrade caph1993-pytools
'''

setup(
    name='caph1993-pytools',
    version='0.1.18',
    description='Python toolbox of Carlos Pinzón',
    url='https://github.com/caph1993/caph1993-pytools',
    author='Carlos Pinzón',
    author_email='caph1993@gmail.com',
    license='MIT',
    packages=[
        'cp93pytools',
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