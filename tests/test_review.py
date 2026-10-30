"""Focused regression checks; no model downloads, GPU or generated answers required."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx

from app.config import Settings, require_loopback_url
from app.llm import LocalLlamaClient, LocalModelError
from app.prompting import PromptTooLong, fit_prompt
from app.retrieval import IndexValidationError, Retriever, build_index
from app.service import AssistantService
from training.train_lora import AssistantOnlyCollator, encode_example, tokenize_split


ROOT = Path(__file__).resolve().parents[1]


class TinyEmbedder:
    def token_count(self, text):
        return len(text.split())

    def passage_embed(self, passages, batch_size=16):
        return iter([[1.0, 0.0], [0.8, 0.2], [0.0, 1.0]][:len(passages)])

    def query_embed(self, question):
        return iter([[1.0, 0.0]])


class ReviewTests(unittest.TestCase):
    def test_retrieval_input_and_cache_errors_have_actionable_http_status(self):
        from fastapi import HTTPException
        from app.main import ChatRequest, create_app
        from app.retrieval import RetrievalInputError, RetrievalUnavailable

        for error, status in (
            (RetrievalInputError("The question exceeds the embedding token limit."), 422),
            (RetrievalUnavailable("The cached embedding model could not be loaded."), 503),
        ):
            def fail(*args, **kwargs):
                raise error
            service = SimpleNamespace(ask=fail, model=SimpleNamespace(ready=lambda: True))
            app = create_app(ROOT / "config.json", service_override=service)
            app.state.service = service
            endpoint = next(route.endpoint for route in app.routes if getattr(route, "path", None) == "/api/chat")
            # Invoke the real route synchronously; the restricted test environment
            # cannot reliably wake Starlette/AnyIO's cross-thread test portal.
            with self.subTest(error=type(error).__name__), self.assertRaises(HTTPException) as caught:
                endpoint(ChatRequest(question="Question"), SimpleNamespace(app=app))
            self.assertEqual(caught.exception.status_code, status)
            self.assertEqual(caught.exception.detail, str(error))

    def test_remote_generation_addresses_are_rejected(self):
        for value in (
            "https://127.0.0.1:8081", "http://example.com:8081",
            "http://localhost:8081", "http://127.0.0.1:8081/external",
            "http://user:password@127.0.0.1:8081", "http://127.0.0.1:8081?target=remote",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                require_loopback_url(value)
        self.assertEqual(require_loopback_url("http://127.0.0.1:8081/"), "http://127.0.0.1:8081")

    def test_model_redirect_is_not_followed(self):
        calls = []
        def redirect(request):
            calls.append(str(request.url))
            return httpx.Response(307, headers={"Location": "https://example.com/generate"})
        model = LocalLlamaClient("http://127.0.0.1:8081")
        original = model.client
        model.client = httpx.Client(
            base_url=model.base_url, transport=httpx.MockTransport(redirect),
            follow_redirects=original.follow_redirects,
        )
        original.close()
        try:
            with self.assertRaises(LocalModelError):
                model.count_tokens([{"role": "user", "content": "Question"}])
            self.assertEqual(calls, ["http://127.0.0.1:8081/apply-template"])
        finally:
            model.close()

    def test_prompt_budget_drops_only_whole_low_ranked_passages(self):
        contexts = [{"context_id": f"KB-{index}", "text": "Complete evidence " * 10} for index in range(3)]
        received = []
        def server_count(messages):
            received.append(messages)
            return 1000 + 200 * messages[-1]["content"].count("Evidence type:")
        messages, selected, count = fit_prompt(
            "System", "Question", contexts, audience="all", count_tokens=server_count,
            context_size=1600, max_new_tokens=100,
        )
        self.assertEqual(selected, contexts[:2])
        self.assertEqual(count, 1400)
        self.assertEqual(len(received), 2)
        for context in selected:
            self.assertIn(context["text"], messages[-1]["content"])
        self.assertNotIn("[KB-2]", messages[-1]["content"])
        self.assertEqual(len(contexts), 3)

    def test_oversized_single_passage_is_rejected_without_generation(self):
        with self.assertRaises(PromptTooLong):
            fit_prompt("System", "Question", [{"context_id": "KB-1", "text": "Full source"}],
                       audience="all", count_tokens=lambda messages: 2000,
                       context_size=2048, max_new_tokens=192)

    def test_unknown_citation_is_flagged_and_source_metadata_survives(self):
        evidence = json.loads((ROOT / "data/rag_corpus_en.jsonl").read_text().splitlines()[0])
        evidence["score"] = 0.9
        retriever = SimpleNamespace(search=lambda *args, **kwargs: [copy.deepcopy(evidence)])
        model = SimpleNamespace(
            count_tokens=lambda messages: 300,
            complete=lambda *args, **kwargs: {
                "answer": f"An example answer [{evidence['context_id']}] [KB-invented].",
                "finish_reason": "stop",
            },
        )
        service = AssistantService(Settings.load(ROOT / "config.json"), retriever, model)
        result = service.ask("Question")
        self.assertEqual(result["citation_status"]["unknown_context_ids"], ["KB-invented"])
        self.assertFalse(result["citation_status"]["all_citations_supplied"])
        self.assertTrue(any("unverified" in warning for warning in result["warnings"]))
        self.assertEqual(len(result["sources"]), 1)
        for key in ("source_ids", "source_urls", "source_snapshot_date", "applicability", "origin_locations", "verification_status"):
            self.assertEqual(result["sources"][0][key], evidence[key])

    def test_current_corpus_keeps_every_applicability_qualifier_in_prompt_text(self):
        for line in (ROOT / "data/rag_corpus_en.jsonl").read_text().splitlines():
            context = json.loads(line)
            with self.subTest(context=context["context_id"]):
                self.assertIn(context["applicability"], context["text"])

    def test_retrieval_filters_audience_preserves_metadata_and_rejects_stale_corpus(self):
        records = [
            {"context_id": "KB-applicant", "text": "Admissions source", "audience": "applicant"},
            {"context_id": "KB-shared", "text": "Shared source", "audience": "shared", "applicability": "2026 only", "source_ids": ["SRC-1"]},
            {"context_id": "KB-student", "text": "Student source", "audience": "current_student"},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            corpus = root / "corpus.jsonl"
            corpus.write_text("\n".join(json.dumps(row) for row in records), encoding="utf-8")
            build_index(corpus, root / "index", "test-model", root, embedder=TinyEmbedder())
            retriever = Retriever(corpus, root / "index", "test-model", root, embedder=TinyEmbedder())
            found = retriever.search("Question", audience="current_student", top_k=3)
            self.assertEqual([row["context_id"] for row in found], ["KB-shared", "KB-student"])
            self.assertEqual(found[0]["applicability"], "2026 only")
            found[0]["source_ids"].append("MUTATED")
            self.assertEqual(retriever.records[1]["source_ids"], ["SRC-1"])
            corpus.write_text(corpus.read_text() + "\n", encoding="utf-8")
            with self.assertRaises(IndexValidationError):
                Retriever(corpus, root / "index", "test-model", root, embedder=TinyEmbedder())

    def test_training_masks_prompt_and_rejects_wrong_template_prefix(self):
        row = {"id": "example", "messages": [{"role": "system"}, {"role": "user"}, {"role": "assistant"}]}
        tokenizer = SimpleNamespace(apply_chat_template=lambda messages, **kwargs: [1, 2, 3] if len(messages) == 2 else [1, 2, 3, 4, 5])
        encoded = encode_example(tokenizer, row)
        self.assertEqual(encoded["labels"], [-100, -100, -100, 4, 5])
        self.assertEqual(encoded["attention_mask"], [1] * 5)
        with self.assertRaises(ValueError):
            tokenize_split(tokenizer, [row], maximum=4, split="train")
        bad = SimpleNamespace(apply_chat_template=lambda messages, **kwargs: [1, 2, 3] if len(messages) == 2 else [1, 2, 99, 4, 5])
        with self.assertRaises(ValueError):
            encode_example(bad, row)

    def test_training_collator_preserves_loss_mask_and_masks_padding(self):
        features = [
            {"input_ids": [1, 2, 3], "attention_mask": [1, 1, 1], "labels": [-100, -100, 3]},
            {"input_ids": [1, 4], "attention_mask": [1, 1], "labels": [-100, 4]},
        ]
        # Tensor construction alone is substituted: the real padding/masking code runs.
        fake_torch = SimpleNamespace(tensor=lambda values, dtype: values, long="long")
        with patch.dict(sys.modules, {"torch": fake_torch}):
            result = AssistantOnlyCollator(pad_token_id=0)(features)
        self.assertEqual(result["labels"], [[-100, -100, 3], [-100, 4, -100]])
        self.assertEqual(result["attention_mask"], [[1, 1, 1], [1, 1, 0]])
        self.assertEqual(result["input_ids"][1], [1, 4, 0])


if __name__ == "__main__":
    unittest.main()
