"""apps/core/apps.py"""
from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    verbose_name = "Core"

    def ready(self):
        # Bootstrap MongoDB indexes on startup
        try:
            from utils.mongo_client import ensure_indexes
            ensure_indexes()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "MongoDB index setup skipped (server may not be available): %s", exc
            )
