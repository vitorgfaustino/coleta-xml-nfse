import tempfile
import unittest
from pathlib import Path

from nfse import core


class RunLockTests(unittest.TestCase):
    def test_live_lock_blocks_second_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "run.lock"
            with core.RunLock(path):
                with self.assertRaises(core.NfseError):
                    core.RunLock(path).__enter__()
            self.assertFalse(path.exists())

    def test_dead_pid_is_recovered(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "run.lock"
            path.write_text("99999999 0\n", encoding="utf-8")
            with core.RunLock(path) as lock:
                self.assertTrue(lock.acquired)

    def test_garbage_lock_is_recovered(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "run.lock"
            path.write_text("not-a-pid\n", encoding="utf-8")
            with core.RunLock(path) as lock:
                self.assertTrue(lock.acquired)


if __name__ == "__main__":
    unittest.main()
