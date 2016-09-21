#!/usr/bin/env bash
fail() {
    echo "$@" >&2
    exit 1
}

tag="$1"
shift
test -n "$tag" || fail "USAGE: $0 TAG"

# make sure there is nothing in git status that could get in the way
test -n "$(git st -s)" && fail "A clean checkout is required"

git tag "$tag" -m "Tagged $tag" || fail "Couldn't create tag $tag"
python setup.py sdist bdist_wheel || fail "Build failed"
twine upload dist/homely-$tag{.tar.gz,-py*} || fail "Twine upload failed"
