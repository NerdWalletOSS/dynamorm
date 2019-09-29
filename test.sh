#!/bin/bash

set -eux

runtests() {
    extra_args=""
    case "$SERIALIZATION_PKG" in
    *schematics*)
        extra_args="-W ignore::schematics.deprecated.SchematicsDeprecationWarning"
        ;;
    esac
    coverage run --source=dynamorm $(which py.test) -v ${extra_args} tests/
}

pip install codecov pytest pytest-mock

if [ ! -z "${SERIALIZATION_PKG:-}" ]; then
    pip install -e .
    pip install "${SERIALIZATION_PKG}"
    runtests
else
    for pkg in marshmallow schematics; do
        export SERIALIZATION_PKG="${pkg}"
        pip install -e .[${pkg}]
        runtests
    done
fi
