from rest_framework import serializers

from .models import CodeReview, LanguageChoices


class CodeReviewCreateSerializer(serializers.Serializer):
    """Validates the incoming paste-code request."""

    title = serializers.CharField(max_length=120, required=False, allow_blank=True)
    language = serializers.ChoiceField(choices=LanguageChoices.choices, default=LanguageChoices.PYTHON)
    source_code = serializers.CharField(
        max_length=20000,
        min_length=1,
        error_messages={
            "max_length": "Snippets are capped at 20,000 characters — please paste a smaller section.",
            "blank": "Paste some code before requesting a review.",
        },
    )

    def validate_source_code(self, value):
        if not value.strip():
            raise serializers.ValidationError("Paste some code before requesting a review.")
        return value


class IssueSerializer(serializers.Serializer):
    line = serializers.IntegerField(allow_null=True, required=False)
    severity = serializers.CharField()
    category = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()
    suggestion = serializers.CharField()


class CodeReviewSerializer(serializers.ModelSerializer):
    issues = IssueSerializer(many=True)
    language_display = serializers.CharField(source="get_language_display", read_only=True)
    issue_count_by_severity = serializers.ReadOnlyField()

    class Meta:
        model = CodeReview
        fields = [
            "id",
            "title",
            "language",
            "language_display",
            "source_code",
            "status",
            "summary",
            "overall_score",
            "issues",
            "issue_count_by_severity",
            "suggested_refactor",
            "ai_model",
            "error_message",
            "created_at",
        ]
        read_only_fields = fields


class CodeReviewListSerializer(serializers.ModelSerializer):
    """Lighter payload for history/list views — omits full source and issues."""

    language_display = serializers.CharField(source="get_language_display", read_only=True)

    class Meta:
        model = CodeReview
        fields = ["id", "title", "language", "language_display", "status", "overall_score", "created_at"]
