from dataclasses import asdict
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from orchestration.context import build_context
from orchestration.explainability import build_explanation
from orchestration.service import QueryService


def build_query_service() -> QueryService:
    """Build the real query service for Stage 2."""
    from orchestration.stage1 import build_stage1_query_service

    return build_stage1_query_service()


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
    """Stage 2 Web Demo."""

    return """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>非遗智谱：AP-ICH-GraphRAG</title>

      <style>
        * {
          box-sizing: border-box;
        }

        body {
          margin: 0;
          font-family: "Microsoft YaHei", "PingFang SC", Arial, sans-serif;
          background: #f5f7fa;
          color: #1f2937;
        }

        .container {
          width: 94%;
          max-width: 1400px;
          margin: 24px auto 40px;
        }

        .header,
        .query-box,
        .card {
          background: #fff;
          border: 1px solid #e8ebef;
          border-radius: 14px;
          box-shadow: 0 3px 14px rgba(0, 0, 0, .07);
        }

        .header {
          padding: 24px 30px;
          margin-bottom: 18px;
        }

        .header h1 {
          margin: 0 0 7px;
          font-size: 28px;
        }

        .header p {
          margin: 0;
          color: #6b7280;
          font-size: 14px;
        }

        .query-box {
          padding: 18px 22px;
          margin-bottom: 18px;
        }

        .query-row {
          display: flex;
          gap: 12px;
        }

        #question {
          flex: 1;
          padding: 13px 15px;
          border: 1px solid #d1d5db;
          border-radius: 9px;
          font-size: 16px;
          outline: none;
        }

        #question:focus {
          border-color: #6b7280;
          box-shadow: 0 0 0 3px rgba(107, 114, 128, .12);
        }

        button {
          padding: 12px 28px;
          border: 0;
          border-radius: 9px;
          background: #1f2937;
          color: #fff;
          cursor: pointer;
          font-size: 15px;
          font-weight: 600;
        }

        button:hover {
          opacity: .88;
        }

        button:disabled {
          opacity: .55;
          cursor: not-allowed;
        }

        .main-grid {
          display: grid;
          grid-template-columns: minmax(0, 1fr) minmax(430px, 1.08fr);
          gap: 18px;
          align-items: stretch;
        }

        .left-panel,
        .right-panel {
          display: flex;
          flex-direction: column;
          gap: 18px;
          min-width: 0;
        }

        .card {
          padding: 20px 22px;
        }

        .card h2 {
          margin: 0 0 14px;
          font-size: 18px;
        }

        .answer-card {
          min-height: 170px;
        }

        .answer {
          white-space: pre-wrap;
          line-height: 1.75;
          font-size: 16px;
          color: #374151;
        }

        .retrieval-summary {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 10px;
        }

        .info-item {
          background: #f8fafc;
          border-radius: 9px;
          padding: 11px 13px;
          border: 1px solid #edf0f3;
        }

        .info-label {
          color: #6b7280;
          font-size: 12px;
          margin-bottom: 4px;
        }

        .info-value {
          font-size: 14px;
          font-weight: 600;
          word-break: break-word;
        }

        .evidence-item,
        .source-item,
        .path-item {
          background: #f8fafc;
          border: 1px solid #edf0f3;
          border-radius: 9px;
          padding: 11px 13px;
          margin-bottom: 9px;
          line-height: 1.55;
          font-size: 14px;
          word-break: break-word;
        }

        .evidence-item:last-child,
        .source-item:last-child,
        .path-item:last-child {
          margin-bottom: 0;
        }

        .graph-card {
          flex: 1;
          min-height: 590px;
          display: flex;
          flex-direction: column;
        }

        .graph-title-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 10px;
        }

        .graph-status {
          color: #6b7280;
          font-size: 12px;
        }

        #graphCanvas {
          position: relative;
          flex: 1;
          min-height: 500px;
          border-radius: 12px;
          background:
            radial-gradient(
              circle at 1px 1px,
              #e5e7eb 1px,
              transparent 1px
            );
          background-size: 22px 22px;
          border: 1px solid #edf0f3;
          overflow: hidden;
        }

        #graphSvg {
          position: absolute;
          inset: 0;
          width: 100%;
          height: 100%;
        }

        .graph-edge {
          stroke: #9ca3af;
          stroke-width: 1.7;
        }

        .graph-edge-label {
          font-size: 11px;
          fill: #6b7280;
        }

        .graph-node circle {
          fill: #fff;
          stroke: #4b5563;
          stroke-width: 2;
        }

        .graph-node text {
          font-size: 12px;
          fill: #1f2937;
          text-anchor: middle;
          dominant-baseline: middle;
        }

        .empty {
          color: #9ca3af;
          text-align: center;
          padding: 35px 10px;
        }

        .error {
          color: #b00020;
        }

        @media (max-width: 980px) {
          .main-grid {
            grid-template-columns: 1fr;
          }

          .graph-card {
            min-height: 500px;
          }

          #graphCanvas {
            min-height: 430px;
          }
        }

        @media (max-width: 620px) {
          .query-row {
            flex-direction: column;
          }

          button {
            width: 100%;
          }

          .retrieval-summary {
            grid-template-columns: 1fr;
          }
        }
      </style>
    </head>

    <body>
      <div class="container">

        <div class="header">
          <h1>非遗智谱：AP-ICH-GraphRAG</h1>
          <p>
            中国非物质文化遗产知识图谱增强检索系统 · Stage 2 Demo
          </p>
        </div>

        <div class="query-box">
          <div class="query-row">
            <input
              id="question"
              placeholder="请输入关于非物质文化遗产的问题"
              onkeydown="if(event.key==='Enter') query()"
            >
            <button id="queryButton" onclick="query()">
              查询
            </button>
          </div>
        </div>

        <div class="main-grid">

          <div class="left-panel">

            <div class="card answer-card">
              <h2>智能回答</h2>
              <div id="answer" class="answer">
                等待查询...
              </div>
            </div>

            <div class="card">
              <h2>检索信息</h2>

              <div id="retrieval" class="retrieval-summary">

                <div class="info-item">
                  <div class="info-label">查询类型</div>
                  <div class="info-value">—</div>
                </div>

                <div class="info-item">
                  <div class="info-label">Retriever</div>
                  <div class="info-value">—</div>
                </div>

                <div class="info-item">
                  <div class="info-label">复杂度</div>
                  <div class="info-value">—</div>
                </div>

                <div class="info-item">
                  <div class="info-label">路由原因</div>
                  <div class="info-value">—</div>
                </div>

                <div class="info-item">
                  <div class="info-label">Evidence 数量</div>
                  <div class="info-value">—</div>
                </div>

                <div class="info-item">
                  <div class="info-label">Path 数量</div>
                  <div class="info-value">—</div>
                </div>

                <div class="info-item">
                  <div class="info-label">Source 数量</div>
                  <div class="info-value">—</div>
                </div>

                <div class="info-item">
                  <div class="info-label">查询耗时</div>
                  <div class="info-value">—</div>
                </div>

              </div>
            </div>

            <div class="card">
              <h2>Evidence 检索证据</h2>
              <div id="evidence">
                <div class="empty">等待查询...</div>
              </div>
            </div>

            <div class="card">
              <h2>关系路径</h2>
              <div id="paths">
                <div class="empty">等待查询...</div>
              </div>
            </div>

            <div class="card">
              <h2>来源</h2>
              <div id="sources">
                <div class="empty">等待查询...</div>
              </div>
            </div>

          </div>

          <div class="right-panel">

            <div class="card graph-card">

              <div class="graph-title-row">
                <h2>知识图谱</h2>
                <span id="graphStatus" class="graph-status">
                  等待查询
                </span>
              </div>

              <div id="graphCanvas">
                <svg id="graphSvg"></svg>

                <div id="graphEmpty" class="empty">
                  查询后将在这里展示知识图谱节点与关系
                </div>
              </div>

            </div>

          </div>

        </div>
      </div>

      <script>

        function escapeHtml(value) {
          const div = document.createElement("div");
          div.textContent = value == null ? "" : String(value);
          return div.innerHTML;
        }


        function renderRetrieval(data) {

          const timing = data.timing || {};

          document.getElementById("retrieval").innerHTML = `

            <div class="info-item">
              <div class="info-label">查询类型</div>
              <div class="info-value">
                ${escapeHtml(data.query_type || "—")}
              </div>
            </div>

            <div class="info-item">
              <div class="info-label">Retriever</div>
              <div class="info-value">
                ${escapeHtml(data.selected_route || "—")}
              </div>
            </div>

            <div class="info-item">
              <div class="info-label">复杂度</div>
              <div class="info-value">
                ${escapeHtml(data.complexity_score ?? "—")}
              </div>
            </div>

            <div class="info-item">
              <div class="info-label">路由原因</div>
              <div class="info-value">
                ${escapeHtml(data.route_reason || "—")}
              </div>
            </div>

            <div class="info-item">
              <div class="info-label">Evidence 数量</div>
              <div class="info-value">
                ${escapeHtml(data.evidences?.length ?? 0)}
              </div>
            </div>

            <div class="info-item">
              <div class="info-label">Path 数量</div>
              <div class="info-value">
                ${escapeHtml(data.paths?.length ?? 0)}
              </div>
            </div>

            <div class="info-item">
              <div class="info-label">Source 数量</div>
              <div class="info-value">
                ${escapeHtml(data.sources?.length ?? 0)}
              </div>
            </div>

            <div class="info-item">
              <div class="info-label">查询耗时</div>
              <div class="info-value">
                ${
                  escapeHtml(
                    timing.total_ms != null
                      ? Number(timing.total_ms).toFixed(1) + " ms"
                      : "—"
                  )
                }
              </div>
            </div>
          `;
        }


        function renderList(id, items, cls, formatter) {

          const el = document.getElementById(id);

          if (!items || items.length === 0) {
            el.innerHTML = '<div class="empty">暂无数据</div>';
            return;
          }

          el.innerHTML = items
            .map((item, i) => {
              return `<div class="${cls}">${formatter(item, i)}</div>`;
            })
            .join("");
        }


        function getNodeId(node) {

          return String(
            node.node_id || node.id || ""
          ).trim();
        }


        /*
         * 判断节点是否应该在前端图谱中隐藏。
         *
         * 1. ihchina_xxxxx 是内部数据 ID
         * 2. 非遗实体是无法解析名称时产生的占位节点
         */
        function isHiddenNode(node) {

          const label = String(
            node.label || ""
          ).trim();

          if (!label) {
            return true;
          }

          if (/^ihchina_[a-zA-Z0-9]+$/.test(label)) {
            return true;
          }

          if (label === "非遗实体") {
            return true;
          }

          return false;
        }


        function getDisplayLabel(node) {

          const label = String(
            node.label || ""
          ).trim();

          if (isHiddenNode(node)) {
            return "";
          }

          return label;
        }


        function getDisplayRelation(relation) {

          const map = {
            "BELONGS_TO": "属于",
            "LOCATED_IN": "位于",
            "RELATED_TO": "相关"
          };

          return map[relation] || relation || "";
        }


        function renderGraph(nodes, edges) {

          const canvas =
            document.getElementById("graphCanvas");

          const svg =
            document.getElementById("graphSvg");

          const empty =
            document.getElementById("graphEmpty");

          const status =
            document.getElementById("graphStatus");


          while (svg.firstChild) {
            svg.removeChild(svg.firstChild);
          }


          /*
           * 先过滤掉：
           * - ihchina_xxxxx
           * - 非遗实体
           * - 空名称节点
           */
          const visibleNodes = (nodes || []).filter(
            node => !isHiddenNode(node)
          );


          /*
           * 只保留两个端点都存在的关系。
           *
           * 这样隐藏 ihchina 节点后，
           * 不会出现一条线指向不存在的节点。
           */
          const visibleNodeIds = new Set(
            visibleNodes.map(node => getNodeId(node))
          );


          const visibleEdges = (edges || []).filter(edge => {

            const sourceId =
              String(edge.source || "").trim();

            const targetId =
              String(edge.target || "").trim();

            return (
              visibleNodeIds.has(sourceId) &&
              visibleNodeIds.has(targetId)
            );
          });


          if (visibleNodes.length === 0) {

            empty.style.display = "block";
            status.textContent = "暂无可显示图谱";

            return;
          }


          empty.style.display = "none";

          status.textContent =
            `${visibleNodes.length} 个节点 · ` +
            `${visibleEdges.length} 条关系`;


          const width =
            canvas.clientWidth;

          const height =
            canvas.clientHeight;

          const cx =
            width / 2;

          const cy =
            height / 2;

          const r =
            Math.min(width, height) * .34;

          const positions = {};


          /*
           * 1. 给可见节点建立位置
           */
          visibleNodes.forEach((node, i) => {

            const nodeId =
              getNodeId(node);

            if (!nodeId) {
              return;
            }

            const a =
              -Math.PI / 2 +
              2 * Math.PI * i / visibleNodes.length;

            positions[nodeId] = {
              x: cx + r * Math.cos(a),
              y: cy + r * Math.sin(a)
            };
          });


          /*
           * 2. 绘制关系
           */
          visibleEdges.forEach(edge => {

            const sourceId =
              String(edge.source || "").trim();

            const targetId =
              String(edge.target || "").trim();

            const s =
              positions[sourceId];

            const t =
              positions[targetId];

            if (!s || !t) {
              return;
            }


            const line =
              document.createElementNS(
                "http://www.w3.org/2000/svg",
                "line"
              );

            line.setAttribute("x1", s.x);
            line.setAttribute("y1", s.y);
            line.setAttribute("x2", t.x);
            line.setAttribute("y2", t.y);
            line.setAttribute(
              "class",
              "graph-edge"
            );

            svg.appendChild(line);


            const label =
              document.createElementNS(
                "http://www.w3.org/2000/svg",
                "text"
              );

            label.setAttribute(
              "x",
              (s.x + t.x) / 2
            );

            label.setAttribute(
              "y",
              (s.y + t.y) / 2 - 5
            );

            label.setAttribute(
              "class",
              "graph-edge-label"
            );

            label.textContent =
              getDisplayRelation(edge.relation);

            svg.appendChild(label);
          });


          /*
           * 3. 绘制节点
           */
          visibleNodes.forEach(node => {

            const nodeId =
              getNodeId(node);

            const displayLabel =
              getDisplayLabel(node);

            if (!displayLabel) {
              return;
            }

            const p =
              positions[nodeId];

            if (!p) {
              return;
            }


            const g =
              document.createElementNS(
                "http://www.w3.org/2000/svg",
                "g"
              );

            g.setAttribute(
              "class",
              "graph-node"
            );


            const circle =
              document.createElementNS(
                "http://www.w3.org/2000/svg",
                "circle"
              );

            circle.setAttribute(
              "cx",
              p.x
            );

            circle.setAttribute(
              "cy",
              p.y
            );

            circle.setAttribute(
              "r",
              30
            );

            g.appendChild(circle);


            const text =
              document.createElementNS(
                "http://www.w3.org/2000/svg",
                "text"
              );

            text.setAttribute(
              "x",
              p.x
            );

            text.setAttribute(
              "y",
              p.y
            );

            text.textContent =
              displayLabel;

            g.appendChild(text);

            svg.appendChild(g);
          });
        }


        function formatRelationPath(path) {

          if (
            !Array.isArray(path) ||
            path.length === 0
          ) {
            return "";
          }


          if (
            path.length >= 3 &&
            path.length % 2 === 1 &&
            path.every(
              item => typeof item === "string"
            )
          ) {

            const parts = [];

            for (
              let i = 0;
              i < path.length - 2;
              i += 2
            ) {

              if (i === 0) {
                parts.push(path[i]);
              }

              parts.push(
                "--[" +
                getDisplayRelation(path[i + 1]) +
                "]-->"
              );

              parts.push(path[i + 2]);
            }

            return parts.join(" ");
          }


          return path.join(" → ");
        }


        async function query() {

          const question =
            document
              .getElementById("question")
              .value
              .trim();

          const button =
            document.getElementById(
              "queryButton"
            );


          if (!question) {
            alert("请输入问题");
            return;
          }


          button.disabled = true;
          button.textContent = "查询中...";

          document.getElementById(
            "answer"
          ).textContent = "正在查询...";

          document.getElementById(
            "graphStatus"
          ).textContent = "正在生成图谱...";


          try {

            const response =
              await fetch(
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


            /*
             * 智能回答
             */
            document.getElementById(
              "answer"
            ).textContent =
              data.answer || "暂无回答";


            /*
             * 检索信息
             */
            renderRetrieval(data);


            /*
             * Evidence
             */
            renderList(
              "evidence",
              data.evidences,
              "evidence-item",
              item => {

                if (typeof item === "string") {
                  return escapeHtml(item);
                }


                const content =
                  item.content ||
                  item.text ||
                  "";

                const source =
                  item.source_url ||
                  item.source ||
                  "";

                const method =
                  item.retrieval_method ||
                  "—";

                const score =
                  item.score != null
                    ? Number(item.score).toFixed(4)
                    : "—";


                const path =
                  Array.isArray(
                    item.relation_path
                  )
                    ? formatRelationPath(
                        item.relation_path
                      )
                    : (
                        item.relation_path ||
                        ""
                      );


                return `
                  <div style="font-weight:600;margin-bottom:6px">
                    Evidence ${escapeHtml(
                      item.index ?? ""
                    )}
                  </div>

                  <div style="margin-bottom:6px">
                    ${escapeHtml(content)}
                  </div>

                  <div style="color:#6b7280;font-size:12px">
                    检索方式：
                    ${escapeHtml(method)}
                    · 相关性分数：
                    ${escapeHtml(score)}
                  </div>

                  ${
                    path
                      ? `
                        <div style="
                          margin-top:6px;
                          color:#6b7280;
                          font-size:12px
                        ">
                          关系路径：
                          ${escapeHtml(path)}
                        </div>
                      `
                      : ""
                  }

                  ${
                    source
                      ? `
                        <div style="
                          margin-top:6px;
                          color:#6b7280;
                          font-size:12px
                        ">
                          来源：
                          ${escapeHtml(source)}
                        </div>
                      `
                      : ""
                  }
                `;
              }
            );


            /*
             * Relation Paths
             */
            renderList(
              "paths",
              data.paths,
              "path-item",
              item => {

                if (typeof item === "string") {
                  return escapeHtml(item);
                }


                if (
                  Array.isArray(
                    item.relation_path
                  )
                ) {

                  return escapeHtml(
                    formatRelationPath(
                      item.relation_path
                    )
                  );
                }


                if (item.path) {
                  return escapeHtml(
                    item.path
                  );
                }


                return escapeHtml(
                  JSON.stringify(item)
                );
              }
            );


            /*
             * Sources
             */
            renderList(
              "sources",
              data.sources,
              "source-item",
              item => {

                if (typeof item === "string") {
                  return escapeHtml(item);
                }

                return escapeHtml(
                  JSON.stringify(item)
                );
              }
            );


            /*
             * Knowledge Graph
             */
            renderGraph(
              data.graph_nodes,
              data.graph_edges
            );

          } catch (error) {

            document.getElementById(
              "answer"
            ).innerHTML =
              '<span class="error">' +
              '查询失败：' +
              escapeHtml(error.message) +
              '</span>';

            document.getElementById(
              "graphStatus"
            ).textContent =
              "查询失败";

          } finally {

            button.disabled = false;
            button.textContent = "查询";
          }
        }

      </script>
    </body>
    </html>
    """


@app.post("/query")
def query(request: QueryRequest):

    response = query_service.query(
        request.question
    )

    result = asdict(response)

    result["explanation"] = build_explanation(
        response
    )

    return result


@app.post("/graph", response_model=GraphResponse)
def graph(request: QueryRequest):
    """返回当前问题对应知识图谱子图。"""

    response = query_service.query(
        request.question
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


@app.post("/source", response_model=SourceResponse)
def source(request: QueryRequest):
    """返回当前问题来源。"""

    response = query_service.query(
        request.question
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