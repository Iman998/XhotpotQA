# Security policy

Never put API tokens in source files, notebooks, configs, command history, or issue text.
The code reads credentials only from environment variables. If a credential is exposed,
revoke it immediately, rotate it, and scan the full Git history before publishing.

The repository includes a conservative working-tree scan that reports only file, line, and
credential type (never the matched value):

```bash
python -m xhotpotqa.security.secret_scan .
```

This check runs in pre-commit and CI. It does not replace a full-history scan before a public
release; rewritten or deleted commits must be checked separately and any exposed credential
must still be revoked.

Report security issues privately to `iman_barati@comp.iust.ac.ir`.
