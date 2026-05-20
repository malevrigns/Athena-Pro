const ws = new WebSocket("wss://athena.example.com/v1/ws");

ws.onopen = () => {
  ws.send(JSON.stringify({type: "subscribe", task_id: taskId}));
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  switch (msg.type) {
    case "token":       appendToken(msg.content); break;
    case "node_update": markNodeDone(msg.node);   break;
    case "done":        showFinalReport(msg.final_report); break;
    case "interrupt_ack": showToast("已停止"); break;
  }
};

// 用户点了"停止"按钮
function onStopClick() {
  ws.send(JSON.stringify({type: "interrupt", task_id: taskId}));
}