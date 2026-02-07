#!/usr/bin/env bash
pyproject_version=$(grep '^version =' pyproject.toml)
importable_version=$(grep '^version =' homely/__init__.py)
if [ "$pyproject_version" != "$importable_version" ]; then
	echo "ERROR: version mismatch"                   >&2
	echo "  pyproject.toml:     $pyproject_version"  >&2
	echo "  homely/__init__.py: $importable_version" >&2
	exit 2
fi

uv_lock_segment=$(pcregrep -M "\[\[package]]\nname = \"homely\"\nversion = " uv.lock)
uv_lock_version=$(echo "$uv_lock_segment" | grep '^version = ')

if [ "$pyproject_version" != "$uv_lock_version" ]; then
	echo "ERROR: version mismatch"                   >&2
	echo "  pyproject.toml:     $pyproject_version"  >&2
	echo "  uv.lock:            $uv_lock_version" >&2
	exit 2
fi
