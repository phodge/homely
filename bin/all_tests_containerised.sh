#!/usr/bin/env bash
fail() { local z="$?"; echo -e "\033[01;31m[$(date +'%H:%M:%S%P')] FAIL[$z]: $@\033[0m" >&2; exit 1; }
win() { echo -e "\033[01;32m[$(date +'%H:%M:%S%P')] $@\033[0m" >&2; }
say() { echo -e "\033[01;35m[$(date +'%H:%M:%S%P')] $@\033[0m" >&2; }

try_tests() {
    version=$1
    shift
    say "Testing under python $version"
    docker build --pull --build-arg=PYTHON_VERSION=$version -f test/tests.Dockerfile . || fail "Containerised testing failed"
}

try_tests 3.6
try_tests 3.7
try_tests 3.8
try_tests 3.9
try_tests 3.10

win "All tests succeeded"
