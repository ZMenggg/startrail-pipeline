import unittest
import tempfile
from pathlib import Path
from tests.conftest import test_logger
from startrail_pipeline.commands.init_ import cmd_init, DIRS


class TestInit(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def _make_args(self, project, force=False):
        class Args:
            pass
        args = Args()
        args.project = project
        args.force = force
        args.verbose = 0
        return args

    def test_init_creates_directories_and_config(self):
        project = self.tmp / "testproj"
        args = self._make_args(project)
        cmd_init(args, test_logger())
        self.assertTrue(project.exists())
        for d in DIRS:
            self.assertTrue((project / d).is_dir(), f"Missing dir: {d}")
        self.assertTrue((project / "project.toml").exists())

    def test_init_is_idempotent(self):
        project = self.tmp / "idem"
        args = self._make_args(project)
        cmd_init(args, test_logger())
        cmd_init(args, test_logger())
        self.assertTrue(project.exists())
        for d in DIRS:
            self.assertTrue((project / d).is_dir())

    def test_init_does_not_overwrite_existing_config(self):
        project = self.tmp / "noclobber"
        project.mkdir(parents=True)
        (project / "project.toml").write_text("existing = true")
        args = self._make_args(project)
        cmd_init(args, test_logger())
        content = (project / "project.toml").read_text()
        self.assertIn("existing", content)


if __name__ == "__main__":
    unittest.main()
