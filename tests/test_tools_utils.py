import pytest

from demetra.settings import SEARCH
from demetra.tools.utils import resolve_limit


class TestResolveLimit:
    def test_defaults_when_absent(self):
        assert resolve_limit({}) == SEARCH["default_limit"]

    def test_accepts_a_numeric_string(self):
        assert resolve_limit({"limit": "7"}) == 7

    @pytest.mark.parametrize("bad", [None, "abc", [], {}, object()])
    def test_falls_back_on_unusable_values(self, bad):
        assert resolve_limit({"limit": bad}) == SEARCH["default_limit"]

    @pytest.mark.parametrize("value", [0, -5, -100])
    def test_clamps_below_one(self, value):
        assert resolve_limit({"limit": value}) == 1

    def test_clamps_above_maximum(self):
        assert resolve_limit({"limit": 10_000}) == SEARCH["max_results"]

    def test_passes_through_a_valid_value(self):
        assert resolve_limit({"limit": 12}) == 12
