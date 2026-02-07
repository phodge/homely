#!/usr/bin/env bash
fail() { local z="$?"; echo -e "\033[01;31m[$(date +'%H:%M:%S%P')] FAIL[$z]: $@\033[0m" >&2; exit 1; }
win() { echo -e "\033[01;32m[$(date +'%H:%M:%S%P')] $@\033[0m" >&2; }
say() { echo -e "\033[01;35m[$(date +'%H:%M:%S%P')] $@\033[0m" >&2; }

exit_usage() {
    echo "Usage: $0 { 3.10 | 3.11 | ... | ALL }" >&2
    exit 2
}

try_tests() {
    version=$1
    shift
    say "Testing under python $version"
    docker build $build_opts --build-arg=PYTHON_VERSION=$version -f test/tests.Dockerfile . || fail "Containerised testing failed"
}

if [ "$#" -lt 1 ]; then
    exit_usage
fi

build_opts=""
targets=""

for arg in "$@"; do
	case "$arg" in
		--pull)
			build_opts="--pull"
			;;
		3.1*)
			targets="$targets $arg"
			;;
		ALL)
			targets="3.10 3.11 3.12 3.13 3.14"
			;;
		*)
            exit_usage
			;;
	esac
done

for target in $targets; do
    try_tests "$target"
done

win "All tests succeeded"
