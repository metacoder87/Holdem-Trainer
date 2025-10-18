"""
Setup script for PyHoldem Pro.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README file
readme_file = Path(__file__).parent / "README.md"
if readme_file.exists():
    long_description = readme_file.read_text(encoding="utf-8")
else:
    long_description = "PyHoldem Pro - Terminal Texas Hold'em Poker Game"

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
if requirements_file.exists():
    requirements = requirements_file.read_text().strip().split('\n')
    requirements = [req for req in requirements if req and not req.startswith('#')]
else:
    requirements = [
        "pytest>=7.4.0",
        "pytest-cov>=4.1.0", 
        "colorama>=0.4.6",
        "rich>=13.4.2",
        "click>=8.1.6",
        "jsonschema>=4.18.4"
    ]

setup(
    name="pyholdem-pro",
    version="1.0.0",
    author="PyHoldem Pro Development Team",
    author_email="dev@pyholdem-pro.com",
    description="A comprehensive terminal-based Texas Hold'em Poker game",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/pyholdem-pro/pyholdem-pro",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Games/Entertainment",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9", 
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
        "Environment :: Console",
        "Natural Language :: English",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.4.0",
        ],
        "test": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.11.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "pyholdem-pro=main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["data/*.json"],
    },
    keywords="poker texas holdem game terminal console ai statistics",
    project_urls={
        "Bug Reports": "https://github.com/pyholdem-pro/pyholdem-pro/issues",
        "Source": "https://github.com/pyholdem-pro/pyholdem-pro",
        "Documentation": "https://pyholdem-pro.readthedocs.io/",
    },
)
