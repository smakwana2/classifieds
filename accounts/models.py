from django.conf import settings
from django.db import models


class TermsAcceptance(models.Model):
    """Proof that a user agreed to the Terms of Use (and confirmed their age) at signup."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='terms_acceptances', on_delete=models.CASCADE)
    version = models.CharField(max_length=20)  # legal.policy.TERMS_VERSION at the time
    accepted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-accepted_at']
        constraints = [models.UniqueConstraint(fields=['user', 'version'], name='one_acceptance_per_terms_version')]

    def __str__(self):
        return f'{self.user} accepted terms {self.version}'
