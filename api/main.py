from dataclasses import asdict
import os
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from orchestration.context import build_context
from orchestration.explainability import build_explanation
from orchestration.service import QueryService


def build_query_service() -> QueryService:
    """Use the real Stage 1 pipeline when D dependencies are available."""
    if os.getenv("KG_G5_STAGE1_REAL") != "1":
        return QueryService()

    try:
        from orchestration.stage1 import build_stage1_query_service

        return build_stage1_query_service()
    except Exception as exc:
        print(f"[WARN] Stage 1 real pipeline unavailable: {exc}")
        return QueryService()


app = FastAPI(
    title="AP-ICH-GraphRAG",
    description="非遗智谱：AP-ICH-GraphRAG",
    version="1.0.0",
)


class QueryRequest(BaseModel):
    question: str


class GraphNodeResponse(BaseModel):
    id: str
    label: str
    properties: Dict[str, Any] = {}


class GraphEdgeResponse(BaseModel):
    source: str
    target: str
    relation: str
    properties: Dict[str, Any] = {}


class GraphResponse(BaseModel):
    nodes: List[GraphNodeResponse]
    edges: List[GraphEdgeResponse]


class SourceResponse(BaseModel):
    sources: List[str]


query_service = build_query_service()


@app.get("/", response_class=HTMLResponse)
def root():
    """Stage 1 Web Demo."""

    return """
    <!DOCTYPE html>
    <html lang="zh-CN">

    <head>
        <meta charset="UTF-8">
        <meta name="viewport"
              content="width=device-width, initial-scale=1.0">

        <title>非遗智谱：AP-ICH-GraphRAG</title>

        <style>
            * {
                box-sizing: border-box;
            }

            body {
                margin: 0;
                padding: 0;
                font-family:
                    "Microsoft YaHei",
                    "PingFang SC",
                    Arial,
                    sans-serif;

                background: #f4f6f8;
                color: #222;
            }

            .container {
                width: 90%;
                max-width: 1100px;
                margin: 30px auto;
            }

            .header {
                background: white;
                padding: 28px;
                border-radius: 12px;
                margin-bottom: 20px;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
            }

            .header h1 {
                margin: 0 0 8px 0;
            }

            .header p {
                margin: 0;
                color: #666;
            }

            .query-box {
                background: white;
                padding: 20px;
                border-radius: 12px;
                margin-bottom: 20px;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
            }

            .query-row {
                display: flex;
                gap: 10px;
            }

            #question {
                flex: 1;
                padding: 13px;
                border: 1px solid #ccc;
                border-radius: 6px;
                font-size: 16px;
            }

            button {
                padding: 12px 24px;
                border: none;
                border-radius: 6px;
                background: #333;
                color: white;
                cursor: pointer;
                font-size: 16px;
            }

            button:hover {
                opacity: 0.85;
            }

            .card {
                background: white;
                padding: 22px;
                border-radius: 12px;
                margin-bottom: 20px;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
            }

            .card h2 {
                margin-top: 0;
            }

            pre {
                white-space: pre-wrap;
                word-break: break-word;
                background: #f6f7f8;
                padding: 15px;
                border-radius: 6px;
                overflow-x: auto;
            }

            .node {
                display: inline-block;
                padding: 8px 14px;
                margin: 5px;
                border: 1px solid #999;
                border-radius: 20px;
                background: #fafafa;
            }

            .edge {
                margin: 10px 5px;
                padding: 8px;
                background: #f6f7f8;
                border-radius: 5px;
            }

            .loading {
                color: #777;
            }

            .error {
                color: #b00020;
            }
        </style>
    </head>

    <body>

        <div class="container">

            <div class="header">
                <h1>非遗智谱：AP-ICH-GraphRAG</h1>
                <p>
                    中国非物质文化遗产知识图谱增强检索系统 · Stage 1 Demo
                </p>
            </div>


            <div class="query-box">

                <div class="query-row">

                    <input
                        id="question"
                        value="什么是蜀绣？"
                        placeholder="请输入关于非物质文化遗产的问题"
                    >

                    <button onclick="query()">
                        查询
                    </button>

                </div>

            </div>


            <div class="card">

                <h2>回答</h2>

                <pre id="answer">
等待查询...
                </pre>

            </div>


            <div class="card">

                <h2>检索信息</h2>

                <pre id="retrieval">
等待查询...
                </pre>

            </div>


            <div class="card">

                <h2>Evidence 检索证据</h2>

                <pre id="evidence">
等待查询...
                </pre>

            </div>


            <div class="card">

                <h2>关系路径</h2>

                <pre id="paths">
等待查询...
                </pre>

            </div>


            <div class="card">

                <h2>知识图谱子图</h2>

                <div id="graph">
                    等待查询...
                </div>

            </div>


            <div class="card">

                <h2>来源</h2>

                <pre id="sources">
等待查询...
                </pre>

            </div>

        </div>


        <script>

            async function query() {

                const question =
                    document.getElementById("question").value.trim();

                if (!question) {
                    alert("请输入问题");
                    return;
                }

                document.getElementById("answer").textContent =
                    "正在查询...";

                document.getElementById("retrieval").textContent =
                    "正在检索...";

                try {

                    const response = await fetch(
                        "/query",
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body: JSON.stringify({
                                question: question
                            })
                        }
                    );


                    if (!response.ok) {
                        throw new Error(
                            "HTTP " + response.status
                        );
                    }


                    const data =
                        await response.json();


                    // Answer

                    document.getElementById(
                        "answer"
                    ).textContent = data.answer;


                    // Retrieval

                    document.getElementById(
                        "retrieval"
                    ).textContent =
                        JSON.stringify(
                            {
                                query_type:
                                    data.query_type,

                                complexity_score:
                                    data.complexity_score,

                                selected_route:
                                    data.selected_route,

                                route_reason:
                                    data.route_reason,

                                timing:
                                    data.timing
                            },
                            null,
                            2
                        );


                    // Evidence

                    document.getElementById(
                        "evidence"
                    ).textContent =
                        JSON.stringify(
                            data.evidences,
                            null,
                            2
                        );


                    // Paths

                    document.getElementById(
                        "paths"
                    ).textContent =
                        JSON.stringify(
                            data.paths,
                            null,
                            2
                        );


                    // Graph

                    const graph =
                        document.getElementById(
                            "graph"
                        );

                    graph.innerHTML = "";


                    if (
                        data.graph_nodes &&
                        data.graph_nodes.length > 0
                    ) {

                        const nodeTitle =
                            document.createElement("h3");

                        nodeTitle.textContent =
                            "节点";

                        graph.appendChild(nodeTitle);


                        data.graph_nodes.forEach(
                            node => {

                                const div =
                                    document.createElement(
                                        "div"
                                    );

                                div.className =
                                    "node";

                                div.textContent =
                                    node.label;

                                graph.appendChild(
                                    div
                                );
                            }
                        );

                    } else {

                        graph.textContent =
                            "暂无图谱节点";

                    }


                    if (
                        data.graph_edges &&
                        data.graph_edges.length > 0
                    ) {

                        const edgeTitle =
                            document.createElement("h3");

                        edgeTitle.textContent =
                            "关系";

                        graph.appendChild(
                            edgeTitle
                        );


                        data.graph_edges.forEach(
                            edge => {

                                const div =
                                    document.createElement(
                                        "div"
                                    );

                                div.className =
                                    "edge";

                                div.textContent =
                                    `${edge.source} `
                                    + `--${edge.relation}--> `
                                    + `${edge.target}`;

                                graph.appendChild(
                                    div
                                );

                            }
                        );

                    }

                    // Sources

                    document.getElementById(
                        "sources"
                    ).textContent =
                        JSON.stringify(
                            data.sources,
                            null,
                            2
                        );

                } catch (error) {

                    document.getElementById(
                        "answer"
                    ).textContent =
                        "查询失败：" + error.message;

                    document.getElementById(
                        "retrieval"
                    ).textContent =
                        "";

                }

            }

        </script>

    </body>

    </html>
    """


@app.post("/query")
def query(request: QueryRequest):
    """主问答接口。"""

    response = query_service.query(
        request.question
    )

    return asdict(response)


@app.get("/graph", response_model=GraphResponse)
def graph():
    """返回 Stage 1 示例知识图谱子图。"""

    response = query_service.query(
        "什么是蜀绣？"
    )

    return GraphResponse(
        nodes=[
            GraphNodeResponse(
                id=node.node_id,
                label=node.label,
                properties=node.properties,
            )
            for node in response.graph_nodes
        ],
        edges=[
            GraphEdgeResponse(
                source=edge.source,
                target=edge.target,
                relation=edge.relation,
                properties=edge.properties,
            )
            for edge in response.graph_edges
        ],
    )


@app.get("/source", response_model=SourceResponse)
def source():
    """返回当前示例查询的来源。"""

    response = query_service.query(
        "什么是蜀绣？"
    )

    return SourceResponse(
        sources=response.sources
    )


@app.post("/context")
def context(request: QueryRequest):
    """返回经过 Context Engineering 整理后的上下文。"""

    response = query_service.query(
        request.question
    )

    return {
        "query": request.question,
        "context": build_context(
            request.question,
            response.evidences,
        ),
    }


@app.post("/explanation")
def explanation(request: QueryRequest):
    """返回检索、证据、路径和图谱解释信息。"""

    response = query_service.query(
        request.question
    )

    return build_explanation(response)
