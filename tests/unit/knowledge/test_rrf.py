from innobrain.knowledge.retrieval import RankedChunk, reciprocal_rank_fusion


def test_rrf_combines_one_based_ranks_and_prefers_stronger_overlap() -> None:
    lexical = [RankedChunk("A"), RankedChunk("B"), RankedChunk("C")]
    dense = [RankedChunk("B"), RankedChunk("D"), RankedChunk("A")]

    result = reciprocal_rank_fusion(lexical, dense, k=60, limit=5)

    assert [item.chunk_id for item in result] == ["B", "A", "D", "C"]
    assert result[0].score == (1 / 61 + 1 / 62)
