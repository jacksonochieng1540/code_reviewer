from unittest.mock import MagicMock, patch

from django.urls import reverse
from rest_framework.test import APITestCase

from .models import CodeReview
from .services import AIReviewError, _extract_json


class ExtractJsonTests(APITestCase):
    def test_plain_json(self):
        self.assertEqual(_extract_json('{"a": 1}'), {"a": 1})

    def test_json_wrapped_in_markdown_fence(self):
        self.assertEqual(_extract_json('```json\n{"a": 1}\n```'), {"a": 1})

    def test_json_with_surrounding_prose(self):
        text = 'Here is the review:\n{"a": 1}\nHope that helps!'
        self.assertEqual(_extract_json(text), {"a": 1})


class CodeReviewCreateViewTests(APITestCase):
    def setUp(self):
        self.url = reverse("api:review-create")

    def test_rejects_blank_code(self):
        response = self.client.post(self.url, {"language": "python", "source_code": "   "})
        self.assertEqual(response.status_code, 400)

    @patch("reviewer.views.review_code")
    def test_successful_review_is_persisted(self, mock_review_code):
        mock_review_code.return_value = {
            "summary": "Looks fine but has one bug.",
            "overall_score": 72,
            "issues": [
                {
                    "line": 4,
                    "severity": "high",
                    "category": "bug",
                    "title": "Off-by-one in loop",
                    "description": "The loop iterates one time too many.",
                    "suggestion": "Use range(len(items)) instead of range(len(items) + 1).",
                }
            ],
            "suggested_refactor": "def f(items):\n    return items",
            "_raw_model": "claude-sonnet-4-5",
        }

        payload = {
            "title": "Loop helper",
            "language": "python",
            "source_code": "def f(items):\n    for i in range(len(items) + 1):\n        print(items[i])",
        }
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["overall_score"], 72)
        self.assertEqual(len(response.data["issues"]), 1)

        review = CodeReview.objects.get(pk=response.data["id"])
        self.assertEqual(review.status, CodeReview.Status.COMPLETE)
        self.assertEqual(review.ai_model, "claude-sonnet-4-5")

    @patch("reviewer.views.review_code")
    def test_ai_failure_marks_review_failed(self, mock_review_code):
        mock_review_code.side_effect = AIReviewError("provider timeout")

        payload = {"language": "python", "source_code": "print('hi')"}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 502)
        review = CodeReview.objects.get(pk=response.data["review_id"])
        self.assertEqual(review.status, CodeReview.Status.FAILED)
        self.assertIn("provider timeout", review.error_message)


class CodeReviewListViewTests(APITestCase):
    def test_list_returns_recent_reviews(self):
        CodeReview.objects.create(source_code="print(1)", language="python", status="complete", overall_score=90)
        CodeReview.objects.create(source_code="print(2)", language="python", status="complete", overall_score=80)

        response = self.client.get(reverse("api:review-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
