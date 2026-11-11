from django.apps import AppConfig


class LegalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'legal'

    def ready(self):
        from . import checks  # noqa: F401  (registers the deploy checks)
