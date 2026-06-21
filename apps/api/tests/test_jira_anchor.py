import pytest

from app.sub_agents.jira_anchor import JiraAnchor, cosine_similarity
from app.sub_agents.schema_pruner import InProcessTTLCache


def test_cosine_similarity_prefers_identical_vector() -> None:
    assert cosine_similarity([1, 0], [1, 0]) > cosine_similarity([1, 0], [0, 1])


@pytest.mark.asyncio
async def test_grounding_ranks_candidate_and_reuses_cache() -> None:
    cache = InProcessTTLCache()
    anchor = JiraAnchor(cache=cache)

    first = await anchor.ground("component", "backend", ["frontend", "backend", "mobile"])
    second = await anchor.ground("component", "backend", ["frontend", "backend", "mobile"])

    assert first.best_value == "backend"
    assert second is first
