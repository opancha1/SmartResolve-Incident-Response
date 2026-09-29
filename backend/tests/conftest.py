import atexit
import os
import tempfile

# Keep API tests from adding synthetic records to the application's real demo DB.
_test_db_dir=tempfile.TemporaryDirectory(prefix="smartresolve-tests-")
os.environ.setdefault("SMARTRESOLVE_DATABASE_URL",f"sqlite:///{_test_db_dir.name}/smartresolve.db")
atexit.register(_test_db_dir.cleanup)
