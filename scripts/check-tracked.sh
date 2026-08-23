#!/usr/bin/env sh
# Fail if git is ignoring a source file.
#
# `.gitignore` here is a combined Python/Node template, and an unanchored rule
# from one language's build output can silently swallow another's source. That
# happened: `lib/` from the Python packaging block matched `frontend/src/lib/`,
# ten files every screen imports, so a fresh clone would not compile — and
# nothing said so, because ignored files never show up in `git status`.
#
#   sh scripts/check-tracked.sh
set -eu

cd "$(dirname "$0")/.."

# Directories whose contents are genuinely build output or dependencies.
EXCLUDE='(^|/)(node_modules|\.venv|\.git|dist|build|__pycache__|\.pytest_cache|\.ruff_cache|\.mypy_cache|\.shots|qc/data)/'

found=$(git ls-files --others --ignored --exclude-standard \
  | grep -Ev "$EXCLUDE" \
  | grep -E '\.(ts|tsx|js|jsx|mjs|cjs|py|css|scss|html|sql|ya?ml)$' || true)

if [ -n "$found" ]; then
  echo "Source files are being ignored by .gitignore:"
  echo "$found" | sed 's/^/  /'
  echo
  echo "Each line is a file a teammate would not get on clone."
  echo "Find the rule with: git check-ignore -v <path>"
  exit 1
fi

echo "check-tracked: no source file is ignored"
