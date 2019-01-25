import os
import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()


setuptools.setup(
    name="qdevd",
    version="0.0.1",
    author="Kushal Das",
    author_email="mail@kushaldas.in",
    description="Device manager for Qubes APP vms.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="GPLv3+",
    url="https://github.com/kushaldas/qdevd",
    packages=["pyqdevd",],
    classifiers=(
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
    ),
    entry_points={
        'console_scripts': [
            'qdevd = pyqdevd:main',
        ],
    },
)