class QueryAnalyzer:
    """基于可解释规则的 Query Analyzer V0。"""

    COMPARISON_CUES = (
        "区别", "不同", "异同", "比较", "相比",
        "共同点", "相同点", "差异",
    )

    RELATION_CUES = (
        "关系", "联系", "关联", "有什么关系",
        "有什么联系", "如何影响",
    )

    CONSTRAINT_CUES = (
        "哪些", "列出", "筛选", "同时满足",
        "并且", "且", "属于",
    )

    def analyze(self, query: str) -> str:
        """返回查询类型：fact/relation/comparison/constraint。"""
        query = query.strip()

        if any(cue in query for cue in self.COMPARISON_CUES):
            return "comparison"

        if any(cue in query for cue in self.RELATION_CUES):
            return "relation"

        if any(cue in query for cue in self.CONSTRAINT_CUES):
            return "constraint"

        return "fact"