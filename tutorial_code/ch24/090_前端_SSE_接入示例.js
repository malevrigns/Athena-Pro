// ① 创建任务
const res = await fetch("/v1/research", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify({question: "调研 2026 年 AI Agent 框架"}),
});
const {task_id, stream_url} = await res.json();

// ② 订阅 SSE 流
const source = new EventSource(stream_url);

source.addEventListener("node_update", (e) => {
  const {node, summary} = JSON.parse(e.data);
  console.log(`[${node}]`, summary);
});

source.addEventListener("token", (e) => {
  const {content} = JSON.parse(e.data);
  appendToReport(content);              // 打字机效果
});

source.addEventListener("done", (e) => {
  const {final_report} = JSON.parse(e.data);
  showFinalReport(final_report);
  source.close();
});

source.addEventListener("error", (e) => {
  console.error("SSE error", e);
});