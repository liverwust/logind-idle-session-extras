from setuptools import setup

# https://packaging.python.org/en/latest/guides/making-a-pypi-friendly-readme/
# read the contents of your README file
from pathlib import Path
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="logind-idle-session-extras",
    version="0.0.2",
    description=("Refresh systemd-logind idle timeouts based on supplemental "
                 "user activity (e.g., VNC tunnel)"),
    long_description=long_description,
    long_description_content_type='text/markdown',
    author="Louis Wust",
    author_email="louiswust@fastmail.fm",
    url="https://github.com/liverwust/logind-idle-session-extras",
    packages=["logind_idle_session_extras"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6"
    ],
    license="MIT License",
    package_dir={"": "src"},
    python_requires=">= 3.6"
)
