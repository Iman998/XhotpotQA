# Contributing

Thanks for improving XHotpotQA. Open an issue before a schema-changing pull request.
Keep one responsibility per module, add typed tests for every behavioral change, and run:

```bash
python -m xhotpotqa.security.secret_scan .
python -m ruff check .
python -m mypy
python -m pytest --cov=xhotpotqa --cov-branch --cov-fail-under=60
python -m build
```

Install the local hooks once with `pre-commit install --hook-type pre-commit --hook-type
pre-push`. The commit hook runs the secret scan, Ruff, and mypy; the pre-push hook also runs
pytest. CI repeats these checks on Python 3.10, 3.11, and 3.12.

Do not commit benchmark data, model weights, prediction dumps, credentials, or personal data.
Schema changes require a version bump and a migration note in `CHANGELOG.md`.
