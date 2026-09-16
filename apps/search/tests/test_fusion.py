from apps.search.ranking import reciprocal_rank_fusion


def test_dual_hit_beats_a_single_hit_at_the_same_position():
    results = reciprocal_rank_fusion([1, 2], [2, 3])

    assert [result.paper_id for result in results] == [2, 1, 3]
    assert results[0].methods == ("keyword", "semantic")


def test_single_method_hits_survive():
    results = reciprocal_rank_fusion([1], [2])

    assert {result.paper_id for result in results} == {1, 2}


def test_ties_use_paper_id_as_a_deterministic_tiebreak():
    results = reciprocal_rank_fusion([2], [1])

    assert [result.paper_id for result in results] == [1, 2]


def test_empty_keyword_ids_preserve_semantic_results():
    results = reciprocal_rank_fusion([], [3, 2, 1])

    assert [result.paper_id for result in results] == [3, 2, 1]


def test_empty_semantic_ids_preserve_keyword_results():
    results = reciprocal_rank_fusion([3, 2, 1], [])

    assert [result.paper_id for result in results] == [3, 2, 1]


def test_two_empty_lists_return_no_results():
    assert reciprocal_rank_fusion([], []) == []


def test_a_top_ranked_single_hit_outranks_a_mid_list_agreement():
    """Guards the measured RRF_K, which no other test would notice drifting.

    At the canonical k=60 the paper both rankings merely agreed on mid-list scores
    0.0258 against 0.0164 for each ranking's own first pick, which is exactly the
    demotion observed on this corpus. At the shipped k the first picks stay on top.
    """
    keyword_ids = [101, *range(102, 115), 50, *range(116, 121)]
    semantic_ids = [*range(201, 220), 50]

    results = reciprocal_rank_fusion(keyword_ids, semantic_ids)

    assert len(keyword_ids) == len(semantic_ids) == 20
    assert [result.paper_id for result in results[:2]] == [101, 201]
