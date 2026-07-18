import logging

from django.shortcuts import render
from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .models import CodeReview
from .serializers import (
    CodeReviewCreateSerializer,
    CodeReviewListSerializer,
    CodeReviewSerializer,
)
from .services import AIReviewError, review_code

logger = logging.getLogger(__name__)


class IndexView(TemplateView):
    """The paste-code page — a single-page UI backed by the REST API below."""

    template_name = "reviewer/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["recent_reviews"] = CodeReview.objects.all()[:8]
        return context


class ReviewThrottle(AnonRateThrottle):
    scope = "anon"


class CodeReviewCreateView(APIView):
    """
    POST /api/reviews/
    Body: {"title": str?, "language": str, "source_code": str}

    Runs the snippet through the AI review engine synchronously and returns
    the persisted, structured review. Kept synchronous for simplicity — a
    real production version would push this to a Celery task and poll/stream
    the result, exactly like the async pattern used in the RAG project.
    """

    throttle_classes = [ReviewThrottle]

    def post(self, request):
        serializer = CodeReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        review = CodeReview.objects.create(
            user=request.user if request.user.is_authenticated else None,
            title=data.get("title", ""),
            language=data["language"],
            source_code=data["source_code"],
            status=CodeReview.Status.PENDING,
        )

        try:
            result = review_code(data["source_code"], data["language"])
        except AIReviewError as exc:
            review.status = CodeReview.Status.FAILED
            review.error_message = str(exc)
            review.save(update_fields=["status", "error_message", "updated_at"])
            logger.warning("AI review failed for %s: %s", review.id, exc)
            return Response(
                {"detail": str(exc), "review_id": str(review.id)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        review.status = CodeReview.Status.COMPLETE
        review.summary = result.get("summary", "")
        review.overall_score = result.get("overall_score")
        review.issues = result.get("issues", [])
        review.suggested_refactor = result.get("suggested_refactor", "")
        review.ai_model = result.get("_raw_model", "")
        review.ai_raw_response = result
        review.save()

        return Response(CodeReviewSerializer(review).data, status=status.HTTP_201_CREATED)


class CodeReviewDetailView(RetrieveAPIView):
    """GET /api/reviews/<uuid:pk>/"""

    queryset = CodeReview.objects.all()
    serializer_class = CodeReviewSerializer
    lookup_field = "pk"


class CodeReviewListView(ListAPIView):
    """GET /api/reviews/ — recent review history, newest first."""

    queryset = CodeReview.objects.all()[:50]
    serializer_class = CodeReviewListSerializer
