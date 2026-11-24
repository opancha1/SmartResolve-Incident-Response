import atexit
import os
import tempfile

# Keep API tests from adding synthetic records to the application's real demo DB.
_test_db_dir=tempfile.TemporaryDirectory(prefix="smartresolve-tests-")
os.environ.setdefault("SMARTRESOLVE_DATABASE_URL",f"sqlite:///{_test_db_dir.name}/smartresolve.db")
os.environ.setdefault("SMARTRESOLVE_DEMO_ENABLED", "1")
atexit.register(_test_db_dir.cleanup)
