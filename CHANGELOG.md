# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.9.3 - 2024-12-16

* Fix "X11 connection rejected because of wrong authentication." due to
  attempting to interrogate X11 forwarding proxies without authentication.

## 0.9.2 - 2024-12-06

* Respect x11vnc relays (to X.org) in addition to Xvnc servers.
* Handle alphanumeric IPv6 addresses and also wildcard addresses properly.

## `0.9.1` - 2024-12-05

- Fix debug logging, to allow writing to a file when using syslog.
* Allow parsing of ss output containing numeric states like FIN-WAIT-2.
* Bump classifier from Alpha to Beta for PyPI tracking.
* Add CHANGELOG and add a configuration section to the README.

## `0.9.0` - 2024-12-02

* Cut a beta-quality release for a recorded demo, and initial RPM packaging.
