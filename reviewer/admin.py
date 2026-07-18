from django.contrib import admin

from .models import CodeReview


@admin.register(CodeReview)
class CodeReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "language", "status", "overall_score", "created_at")
    list_filter = ("language", "status")
    search_fields = ("title", "source_code")
    readonly_fields = ("id", "created_at", "updated_at", "ai_raw_response")
