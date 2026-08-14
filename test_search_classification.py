import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import llm_service
from app.services.search_service import local_expansion_search


def completion(payload):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
    )


class SearchClassificationTests(unittest.TestCase):
    def setUp(self):
        llm_service._match_cache.clear()

    @patch("app.services.llm_service.create_chat_completion")
    @patch("app.services.search_service.vector_search")
    def test_separates_answers_and_related_results(self, vector_search, create_completion):
        vector_search.return_value = [
            {
                "questionText": "A direct answer",
                "video_link": "https://www.youtube.com/watch?v=one&t=10s",
            },
            {
                "questionText": "A related question",
                "video_link": "https://www.youtube.com/watch?v=two&t=20s",
            },
        ]
        create_completion.return_value = completion({
            "answer_indices": [1],
            "related_indices": [2, 1],
        })

        result = llm_service.match_question_with_llm("test query", top_n=3)

        self.assertEqual(["A direct answer"], [item["question"] for item in result["answers"]])
        self.assertEqual(["A related question"], [item["question"] for item in result["related"]])
        self.assertEqual("00:00:10", result["answers"][0]["timestamp"])
        self.assertIn("total_ms", result["timings"])

    def test_local_fallback_retrieves_new_karma_eval(self):
        results = local_expansion_search("What does Advaita say about Karma?", top_n=20)
        questions = [item["questionText"] for item in results]
        self.assertIn("We are told we are one consciousness.\u00a0 Where does Karma come in?", questions)

    @patch("app.services.llm_service.create_chat_completion")
    @patch("app.services.search_service.vector_search")
    def test_upvote_matches_use_same_judge_and_only_direct_results(
        self, vector_search, create_completion
    ):
        vector_search.return_value = [
            {"questionText": "Same underlying request", "voteUp": 4},
            {"questionText": "Merely related request", "voteUp": 20},
        ]
        create_completion.return_value = completion({
            "answer_indices": [1],
            "related_indices": [2],
        })

        results = llm_service.find_similar_questions_for_upvote("user question", 5)

        self.assertEqual(
            [{"question": "Same underlying request", "upvotes": 4}],
            results,
        )
        vector_search.assert_called_once_with(
            "user question", top_n=20, require_video_link=False
        )


if __name__ == "__main__":
    unittest.main()
