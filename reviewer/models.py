import uuid

from django.conf import settings
from django.db import models


class LanguageChoices(models.TextChoices):
    PYTHON = "python", "Python"
    JAVASCRIPT = "javascript", "JavaScript"
    TYPESCRIPT = "typescript", "TypeScript"
    JAVA = "java", "Java"
    C = "c", "C"
    CPP = "cpp", "C++"
    GO = "go", "Go"
    RUBY = "ruby", "Ruby"
    PHP = "php", "PHP"
    CSHARP = "csharp", "C#"
    OTHER = "other", "Other / Auto-detect"


class SeverityChoices(models.TextChoices):
    CRITICAL = "critical", "Critical"
    HIGH = "high", "High"
    MEDIUM = "medium", "Medium"
    LOW = "low", "Low"
    INFO = "info", "Info"


class CodeReview(models.Model):
    """
    One submitted code snippet plus the AI's structured review of it.
    The raw model response is kept in `ai_raw_response` for auditability;
    `issues` holds the parsed, structured list actually rendered in the UI.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="code_reviews",
        null=True,
        blank=True,
        help_text="Null for anonymous/demo submissions.",
    )

    title = models.CharField(max_length=120, blank=True)
    language = models.CharField(max_length=20, choices=LanguageChoices.choices, default=LanguageChoices.PYTHON)
    source_code = models.TextField()

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    summary = models.TextField(blank=True)
    overall_score = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Overall code quality score, 0-100, from the AI review."
    )
    issues = models.JSONField(default=list, blank=True)
    suggested_refactor = models.TextField(blank=True)

    ai_model = models.CharField(max_length=60, blank=True)
    ai_raw_response = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["language"]),
        ]

    def __str__(self):
        return self.title or f"{self.get_language_display()} review ({self.id})"

    @property
    def issue_count_by_severity(self):
        counts = {choice.value: 0 for choice in SeverityChoices}
        for issue in self.issues:
            severity = issue.get("severity", "info")
            counts[severity] = counts.get(severity, 0) + 1
        return counts
