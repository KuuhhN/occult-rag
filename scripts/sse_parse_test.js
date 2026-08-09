// 模拟前端 SSE 解析逻辑，喂入与后端实际输出相同的 SSE 数据
// 运行: node scripts/sse_parse_test.js
// 用 tail -n +1 管道到 node --check 也可以做语法验证

// 模拟浏览器 fetch 收到的流（SSE 规范允许 \r\n 或 \n，此处用 CRLF 场景验证兼容性）
const chunk1 = 'event: sources\r\ndata: [{"content":"test1","source":"a.md"}]\r\n\r\nevent: token\r\ndata: 炼\r\n\r\nevent: token\r\ndata: 金\r\n\r\n';
const chunk2 = 'event: token\r\ndata: 术\r\n\r\nevent: token\r\ndata: 是\r\n\r\n';
const chunk3 = 'event: token\r\ndata: 什么\r\n\r\nevent: done\r\ndata: {"answer":"炼金术是什么","conversation_id":"abc123"}\r\n\r\n';

// 前端 page.tsx 的解析逻辑（原样复刻）
let buffer = "";
let fullAnswer = "";
let lastEvent = "";
const events = [];

function processLines(lines) {
  for (const line of lines) {
    if (line.startsWith("event: ")) {
      lastEvent = line.slice(7);
      continue;
    }
    if (!line.startsWith("data: ")) continue;
    const data = line.slice(6);
    if (lastEvent === "sources") {
      try {
        const json = JSON.parse(data);
        if (Array.isArray(json)) events.push({ type: "sources", data: json });
      } catch {}
    } else if (lastEvent === "token") {
      fullAnswer += data;
      events.push({ type: "token", data });
    } else if (lastEvent === "done") {
      try {
        const json = JSON.parse(data);
        events.push({ type: "done", data: json });
      } catch {}
    } else if (lastEvent === "error") {
      events.push({ type: "error", data });
    }
  }
}

// 模拟流式读取（前端修复后：split(/\r?\n/) 兼容 CRLF）
for (const chunk of [chunk1, chunk2, chunk3]) {
  buffer += chunk;
  const lines = buffer.split(/\r?\n/);
  buffer = lines.pop() || "";
  processLines(lines);
}
// 处理残留（同样兼容 CRLF）
if (buffer.trim()) {
  processLines(buffer.split(/\r?\n/));
}

console.log("解析结果:");
console.log("  sources 事件:", events.filter(e => e.type === "sources").length);
console.log("  token 事件:", events.filter(e => e.type === "token").length);
console.log("  done 事件:", events.filter(e => e.type === "done").length);
console.log("  完整回答:", JSON.stringify(fullAnswer));
console.log("  conversation_id:", events.find(e => e.type === "done")?.data?.conversation_id);

// 断言
const ok = events.filter(e => e.type === "token").length === 5
  && fullAnswer === "炼金术是什么"
  && events.find(e => e.type === "done")?.data?.conversation_id === "abc123";
console.log(ok ? "\n✅ 解析逻辑正常" : "\n❌ 解析逻辑有 bug");
process.exit(ok ? 0 : 1);
