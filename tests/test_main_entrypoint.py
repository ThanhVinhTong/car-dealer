import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class MainEntrypointTests(unittest.TestCase):
    def test_direct_script_resolves_app_package_imports(self):
        project_root = Path(__file__).resolve().parents[1]
        main_script = project_root / "app" / "main.py"
        import_only_code = (
            "import runpy; "
            f"runpy.run_path({str(main_script)!r}, run_name='entrypoint_import_test')"
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            result = subprocess.run(
                [sys.executable, "-I", "-c", import_only_code],
                cwd=temporary_directory,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
