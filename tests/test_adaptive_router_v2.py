from orchestration.adaptive_router_v2 import (
    AdaptiveRouterV2,
    QueryFeatureExtractor,
    RoutingTrainingExample,
)


def test_untrained_router_v2_falls_back_to_v1():
    router = AdaptiveRouterV2()

    decision = router.route_from_features(
        "relation",
        0.35,
        QueryFeatureExtractor().features("relation query", "relation", 0.35),
    )

    assert decision.selected_route == "graph"
    assert decision.confidence == 0.5
    assert "fallback to V1" in decision.reason


def test_router_v2_learns_from_labeled_examples():
    router = AdaptiveRouterV2(epochs=500, learning_rate=0.3)
    router.fit(
        [
            RoutingTrainingExample(
                query="simple fact",
                query_type="fact",
                complexity_score=0.15,
                best_route="vector",
            ),
            RoutingTrainingExample(
                query="entity relation",
                query_type="relation",
                complexity_score=0.35,
                best_route="graph",
            ),
            RoutingTrainingExample(
                query="compare two items",
                query_type="comparison",
                complexity_score=0.60,
                best_route="graph",
            ),
            RoutingTrainingExample(
                query="plain definition",
                query_type="fact",
                complexity_score=0.20,
                best_route="vector",
            ),
        ]
    )

    extractor = QueryFeatureExtractor()
    graph_decision = router.route_from_features(
        "relation",
        0.35,
        extractor.features("entity relation", "relation", 0.35),
    )
    vector_decision = router.route_from_features(
        "fact",
        0.15,
        extractor.features("simple fact", "fact", 0.15),
    )

    assert graph_decision.selected_route == "graph"
    assert graph_decision.confidence is not None
    assert graph_decision.confidence > 0.5
    assert vector_decision.selected_route == "vector"
    assert vector_decision.confidence is not None
    assert vector_decision.confidence > 0.5


def test_router_v2_can_save_and_load(tmp_path):
    router = AdaptiveRouterV2(epochs=200, learning_rate=0.3)
    router.fit(
        [
            RoutingTrainingExample(
                query="simple fact",
                query_type="fact",
                complexity_score=0.15,
                best_route="vector",
            ),
            RoutingTrainingExample(
                query="entity relation",
                query_type="relation",
                complexity_score=0.35,
                best_route="graph",
            ),
        ]
    )

    model_path = tmp_path / "models" / "router_v2.json"
    router.save(model_path)
    loaded = AdaptiveRouterV2.load(model_path)

    assert loaded.is_trained
    assert loaded.to_dict()["feature_names"] == router.to_dict()["feature_names"]
    assert loaded.route_from_features(
        "relation",
        0.35,
        QueryFeatureExtractor().features("entity relation", "relation", 0.35),
    ).selected_route == "graph"
