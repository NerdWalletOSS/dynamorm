#!/bin/bash

set -eux

SERIALIZATION_PKG=${SERIALIZATION_PKG:-marshmallow}
TRAVIS_PULL_REQUEST=${TRAVIS_PULL_REQUEST:-false}

pip install -e .
pip install codecov pytest pytest-mock
pip install ${SERIALIZATION_PKG}

SERIALIZATION_PKG=${SERIALIZATION_PKG} coverage run --source=dynamorm $(which py.test) -v tests/

if [ "${TRAVIS_PULL_REQUEST}" != "false" ]; then
    if [ -z "`git diff origin/master setup.py | grep '\+.*version='`" ]; then
        printf "\n\n\n\nBump version in setup.py!\n\n\n\n"
        exit 1
    fi
fi

# only build docs on py2.7
if [ "${TRAVIS_PYTHON_VERSION}" = "2.7" ]; then
    pip install travis-sphinx
    travis-sphinx --source=docs build

    # push if we have a token and this isn't a pr build
    [ "${TRAVIS_PULL_REQUEST}" = "false" ] && [ ! -z "${GH_TOKEN}" ] && travis-sphinx deploy
fi
