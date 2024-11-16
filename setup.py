from setuptools import setup

setup(
    name="logind-idle-session-extras",
    version="0.0.1",
    description=("Refresh systemd-logind idle timeouts based on supplemental"
                 "user activity (e.g., VNC tunnel)"),
    author="Louis Wust",
    author_email="louiswust@fastmail.fm",
    url="https://github.com/liverwust/logind-idle-session-extras",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6"
    ],
    license="MIT License",
    python_requires=">= 3.6"
)
