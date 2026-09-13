class ComplexityScorer:
    """Rule-based query complexity scorer for Stage 1 routing."""

    MULTI_ENTITY_CUES = ("和", "与", "及", "以及")
    COMPARISON_CUES = ("区别", "不同", "异同", "比较", "共同点", "差异")
    MULTI_HOP_CUES = (
        "之间",
        "为什么",
        "如何影响",
        "通过什么",
        "关联",
        "传承方式",
        "发展阶段",
        "社会功能",
        "主要内容",
    )
    MULTI_CONDITION_CUES = (
        "同时",
        "并且",
        "且",
        "既",
        "分别",
        "概括",
        "总结",
        "说明",
        "归纳",
        "结合材料",
        "根据正文",
    )

    def score(self, query: str) -> float:
        query = query.strip()
        score = 0.15

        if any(cue in query for cue in self.MULTI_ENTITY_CUES):
            score += 0.20

        if any(cue in query for cue in self.COMPARISON_CUES):
            score += 0.25

        if any(cue in query for cue in self.MULTI_HOP_CUES):
            score += 0.20

        if any(cue in query for cue in self.MULTI_CONDITION_CUES):
            score += 0.15

        if len(query) >= 30:
            score += 0.10

        return round(min(score, 1.0), 2)
