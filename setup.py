from setuptools import setup

# https://packaging.python.org/en/latest/guides/making-a-pypi-friendly-readme/
# read the contents of your README file
from pathlib import Path
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="stop-idle-sessions",
    version="0.6.12",
    description=("Refresh systemd-logind idle timeouts based on supplemental "
                 "user activity (e.g., VNC tunnel)"),
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
    entry_points={
        'console_scripts': [
            'stop-idle-sessions = stop_idle_sessions.main:just_print'
        ]
    },
    python_requires=">= 3.6"
)
