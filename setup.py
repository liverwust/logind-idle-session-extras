"""Standard setup.py for setuptools"""

from pathlib import Path
from setuptools import setup

# https://packaging.python.org/en/latest/guides/making-a-pypi-friendly-readme/
# read the contents of your README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="stop-idle-sessions",
    version="0.9.0",
    description=("Stop idle `systemd-logind` sessions to prevent interactive "
                 "access from unattended terminals. E.g., a laptop left "
                 "unlocked in a coffee shop, with an SSH session into an "
                 "internal network resource."),
    long_description=long_description,
    long_description_content_type='text/markdown',
    author="Louis Wust",
    author_email="louiswust@fastmail.fm",
    url="https://github.com/liverwust/stop-idle-sessions",
    packages=["stop_idle_sessions"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: No Input/Output (Daemon)",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.9",
        "Topic :: Security",
        "Topic :: System :: Shells",
        "Topic :: System :: System Shells",
        "Topic :: System :: Systems Administration",
        "Topic :: Terminals",
        "Topic :: Utilities"
    ],
    license="MIT License",
    package_dir={"": "src"},
    # These minimum versions are derived from RHEL8
    install_requires=[
        "PyGObject >= 3.28.3",
        "psutil >= 5.4.3",
        "python-xlib >= 0.33"
    ],
    python_requires=">= 3.6"
)
