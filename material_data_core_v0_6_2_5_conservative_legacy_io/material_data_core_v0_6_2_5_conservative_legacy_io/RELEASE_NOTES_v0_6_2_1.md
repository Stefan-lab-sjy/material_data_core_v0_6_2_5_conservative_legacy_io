# v0.6.2.1 Windows test cleanup hotfix

This hotfix keeps all v0.6.2 data schemas and classification rules unchanged.

Fixed two Windows-only test cleanup failures caused by using `sqlite3.Connection` as a context manager. That context manager commits/rolls back a transaction but does not close the database handle, so `TemporaryDirectory` could not remove `catalog.db` on Windows (WinError 32). The tests now wrap these connections with `contextlib.closing`, guaranteeing the handle is closed before temporary-directory cleanup.

Classification version remains `0.6.2` because no semantic rule changed.
