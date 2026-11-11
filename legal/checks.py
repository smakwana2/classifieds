from django.conf import settings
from django.core.checks import Warning, register


@register('legal', deploy=True)
def operator_details_configured(app_configs, **kwargs):
    """The privacy policy and terms must name who runs the site and how to reach them
    (CalOPPA, CCPA and the DMCA all require a working contact)."""
    missing = [name for name in ('SITE_OPERATOR', 'SITE_CONTACT_EMAIL', 'DMCA_AGENT')
               if not getattr(settings, name, '')]
    if missing:
        return [Warning(
            f'{", ".join(missing)} not set: the Privacy Policy and Terms of Use show placeholders.',
            hint='Set DJANGO_SITE_OPERATOR, DJANGO_SITE_CONTACT_EMAIL and DJANGO_DMCA_AGENT '
                 '(see docs/compliance.md).',
            id='legal.W001',
        )]
    return []
