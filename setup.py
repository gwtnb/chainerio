# -*- coding: utf-8

import os
from setuptools import setup
from setuptools import find_packages

package_data = []

proj_dir = os.path.dirname(__file__)
templates = os.path.join(proj_dir, 'resources', 'templates')

for root, dirs, names in os.walk(templates):
    for fname in names:
        abspath = os.path.join(root, fname)
        relpath = os.path.relpath(proj_dir, abspath)
        package_data.append(relpath)
        print(relpath)

here = os.path.abspath(os.path.dirname(__file__))
# Get __version__ variable
exec(open(os.path.join(here, 'chainerio', 'version.py')).read())

with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
        long_description = f.read()

setup(
    name='chainerio',
    version=__version__,
    description='Chainer IO library',
    author='Tianqi Xu, Kota Uenishi',
    author_email='tianqi@preferred.jp, kota@preferred.jp',
    url='http://github.com/chainer/chainerio',
    classifiers=[
        'Development Status :: 3 - Alpha',

        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Operating System :: POSIX :: Linux',

        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',

        'Topic :: System :: Filesystems',
    ],
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=find_packages(),
    package_data={'chainerio' : package_data},
    extras_require={'test':['pytest', 'flake8', 'autopep8']},
    python_requires=">=3.5.3",
    install_requires=['krbticket', 'pyarrow'],
    include_package_data=True,
    zip_safe=False,

    keywords='filesystem hdfs chainer development',
)
