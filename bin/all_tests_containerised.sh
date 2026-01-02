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

case "$1" in
	3.1*)
		try_tests "$1";;
	ALL)
		try_tests 3.10
		try_tests 3.11
		try_tests 3.12
		;;
	*)
		echo "Usage: $0 { 3.10 | 3.11 | ... | ALL }" >&2
		exit 2
		;;
esac

win "All tests succeeded"
