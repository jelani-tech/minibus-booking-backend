import os
import unittest


class BackendApiTestCase(unittest.TestCase):
    database_url = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://user:password@localhost:5432/minibus_db",
    )

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("DATABASE_URL", cls.database_url)
        os.environ.setdefault("AUTO_UPGRADE_DB", "false")
        os.environ.setdefault("LEGACY_SCHEMA_BOOTSTRAP", "false")

        from app import create_app

        cls.app = create_app()
        cls.app.config.update(TESTING=True)
        cls.client = cls.app.test_client()

