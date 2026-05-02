#!/usr/bin/env bash
pyproject_version=$(grep '^version =' pyproject.toml)
importable_version=$(grep '^version =' homely/__init__.py)
if [ "$pyproject_version" != "$importable_version" ]; then
	echo "ERROR: version mismatch"                   >&2
	echo "  pyproject.toml:     $pyproject_version"  >&2
	echo "  homely/__init__.py: $importable_version" >&2
	exit 2
fi

expected_version="$1"
shift

if [ -n "$expected_version" ]; then
	echo '----------'
	cat homely/__init__.py
	echo '----------'
	grep "^version = \"$expected_version\"" homely/__init__.py
	echo $?
	echo '----------'
	if ! grep "^version = \"$expected_version\"" homely/__init__.py >/dev/null; then
		echo "ERROR: expected 'version = \"$expected_version\"' in homely/__init__.py" >&2
		exit 3
	else
		echo "OK: version in homely/__init__.py matches expected version '$expected_version'"
	fi
fi
