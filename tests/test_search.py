import pytest

from demetra.tools import search


FIELDS = (
    search.Field(weight=10.0, length_norm=0.0),
    search.Field(weight=5.0, length_norm=0.0),
    search.Field(weight=1.0, length_norm=0.75),
)


def _document(title: str = "", metadata: str = "", body: str = ""):
    """Build a per-field token count tuple aligned to ``FIELDS``."""
    return (
        search.count_field(text=title),
        search.count_field(text=metadata),
        search.count_field(text=body),
    )


def _score(document, documents, terms) -> float:
    """Score one document against a corpus built from the other documents."""
    stats = search.build_stats(fields=FIELDS, documents=documents)
    return search.score_document(fields=FIELDS, document=document, stats=stats, terms=terms)


class TestTokenize:
    def test_lowercases_and_drops_stop_words(self):
        assert search.tokenize(query="Why is The MCP server down?") == ["mcp", "server", "down"]

    def test_keeps_dotted_and_dashed_terms(self):
        assert search.tokenize(query="mcp_server.py on-list_tools") == ["mcp_server.py", "on-list_tools"]

    def test_empty_query_yields_no_terms(self):
        assert search.tokenize(query="   ") == []


class TestCountField:
    def test_counts_whole_tokens_only(self):
        counts = search.count_field(text="logging pipeline logs")
        assert counts.counts == {"logging": 1, "pipeline": 1, "logs": 1}
        assert counts.length == 3

    def test_length_matches_filtered_token_count(self):
        counts = search.count_field(text="the quick brown fox")
        assert counts.length == 3
        assert "the" not in counts.counts


class TestBuildStats:
    def test_term_counted_once_per_document_across_fields(self):
        documents = [_document(title="shared", body="shared"), _document(body="shared")]
        stats = search.build_stats(fields=FIELDS, documents=documents)

        assert stats.document_count == 2
        assert stats.document_frequency["shared"] == 2

    def test_average_lengths_per_field(self):
        documents = [_document(body="one two"), _document(body="one two three four")]
        stats = search.build_stats(fields=FIELDS, documents=documents)

        assert stats.average_lengths[2] == pytest.approx(3.0)
        assert stats.average_lengths[0] == pytest.approx(0.0)

    def test_empty_corpus_reports_zero_statistics(self):
        stats = search.build_stats(fields=FIELDS, documents=[])

        assert stats.document_count == 0
        assert stats.average_lengths == (0.0, 0.0, 0.0)
        assert stats.document_frequency == {}


class TestInverseDocumentFrequency:
    def test_rare_term_outweighs_common_term(self):
        rare = search.inverse_document_frequency(document_frequency=1, document_count=10)
        common = search.inverse_document_frequency(document_frequency=9, document_count=10)

        assert rare > common

    def test_stays_positive_for_term_in_every_document(self):
        assert search.inverse_document_frequency(document_frequency=10, document_count=10) > 0


class TestScoreDocument:
    def test_boosted_field_outranks_body(self):
        in_title = _document(title="mcp server")
        in_body = _document(body="mcp server")
        documents = [in_title, in_body]

        assert _score(in_title, documents, ["mcp"]) > _score(in_body, documents, ["mcp"])

    def test_partial_word_does_not_match(self):
        document = _document(body="logging pipeline")
        documents = [_document(body="logging pipeline"), _document(body="unrelated")]

        assert _score(document, documents, ["log"]) == 0.0
        assert _score(document, documents, ["logging"]) > 0.0

    def test_unmatched_term_scores_zero(self):
        document = _document(body="logging pipeline")

        assert _score(document, [document], ["zephyr"]) == 0.0

    def test_empty_corpus_scores_zero(self):
        stats = search.build_stats(fields=FIELDS, documents=[])
        document = _document(body="logging pipeline")

        assert search.score_document(fields=FIELDS, document=document, stats=stats, terms=["logging"]) == 0.0

    def test_rare_term_outweighs_common_term(self):
        common_hits = [_document(body="logger")] * 9
        rare_hit = _document(body="zephyr")
        documents = [*common_hits, rare_hit]

        assert _score(rare_hit, documents, ["zephyr"]) > _score(common_hits[0], documents, ["logger"])

    def test_repeated_terms_saturate(self):
        once = _document(body="topic filler")
        many = _document(body=" ".join(["topic"] * 50) + " filler")
        documents = [once, many]

        score_once = _score(once, documents, ["topic"])
        score_many = _score(many, documents, ["topic"])

        assert score_many > score_once
        assert score_many < 3 * score_once

    def test_longer_document_penalised(self):
        short = _document(body="topic")
        long_document = _document(body="topic " + " ".join(["filler"] * 50))
        documents = [short, long_document]

        assert _score(short, documents, ["topic"]) > _score(long_document, documents, ["topic"])

    def test_disabled_length_norm_ignores_document_length(self):
        fields = (search.Field(weight=1.0, length_norm=0.0),)
        short = (search.count_field(text="topic"),)
        long_document = (search.count_field(text="topic " + " ".join(["filler"] * 50)),)
        stats = search.build_stats(fields=fields, documents=[short, long_document])

        assert search.score_document(
            fields=fields, document=short, stats=stats, terms=["topic"]
        ) == search.score_document(fields=fields, document=long_document, stats=stats, terms=["topic"])

    def test_repeated_query_terms_counted_once(self):
        document = _document(body="topic filler")
        documents = [document, _document(body="unrelated")]

        assert _score(document, documents, ["topic", "topic"]) == _score(document, documents, ["topic"])


class TestLineHits:
    def test_matches_whole_tokens_only(self):
        assert search.line_hits(line="logging pipeline", terms=["log"]) == 0
        assert search.line_hits(line="logging pipeline", terms=["logging"]) == 1

    def test_counts_each_term_once(self):
        assert search.line_hits(line="topic topic topic", terms=["topic"]) == 1

    def test_no_match_returns_zero(self):
        assert search.line_hits(line="logging pipeline", terms=["zephyr"]) == 0
