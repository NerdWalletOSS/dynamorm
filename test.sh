#!/bin/bash

# If we're not on the master branch
if [ -z "${FORCE_TEST:-}" ] && [ "$(git rev-parse --abbrev-ref HEAD)" != "master" ]; then
    # Make sure the version has been bumped and a changelog entry has been added
    if [ -z "$(git diff origin/master setup.py | grep '\+.*version=')" ]; then
        printf "\n\n\n\nBump the version in setup.py!\n\n\n\n"
        exit 1
    elif [ -z "$(git diff origin/master CHANGELOG.rst)" ]; then
        printf "\n\n\n\nAdd an entry to CHANGELOG.rst!\n\n\n\n"
        exit 1
    fi
fi

set -eux

runtests() {
    coverage run --source=dynamorm $(which py.test) -v -W ignore::schematics.deprecated.SchematicsDeprecationWarning tests/
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


# only build docs on py3.7
if [ "${TRAVIS_PYTHON_VERSION:-}" = "3.7" ]; then
    pip install travis-sphinx
    travis-sphinx build --source docs

    # push if we have a token and this isn't a pr build
    if [ "${TRAVIS_PULL_REQUEST:-}" = "false" ] && [ ! -z "${GH_TOKEN:-}" ]; then
        travis-sphinx deploy
    fi
fi
