#!/bin/bash

# If we're not on the master branch
if [ "$(git rev-parse --abbrev-ref HEAD)" != "master" ]; then
    # Make sure the version has been bumped and a changelog entry has been added
    if [ -z "$(git diff origin/master setup.py | grep '\+.*version=')" ]; then
        printf "\n\n\n\nBump the version in setup.py!\n\n\n\n"
        exit 1
    elif [ -z "$(git diff origin/master CHANGELOG.md)" ]; then
        printf "\n\n\n\nAdd an entry to CHANGELOG.rst!\n\n\n\n"
        exit 1
    fi
fi

# Run our tests
./test.sh

# only build docs on py3.7
if [ "${TRAVIS_PYTHON_VERSION:-}" = "3.7" ]; then
    pip install travis-sphinx
    travis-sphinx build --source docs

    # push if we have a token and this isn't a pr build
    if [ "${TRAVIS_PULL_REQUEST:-}" = "false" ] && [ ! -z "${GH_TOKEN:-}" ]; then
        travis-sphinx deploy
    fi
fi
