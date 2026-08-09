// Cloudflare Worker 代理：把 /github/* 转发到 api.github.com/*（避免浏览器直连被网络拦截）
//
// 部署步骤（在 Cloudflare 控制台）：
//   1. 打开 https://dash.cloudflare.com → Workers & Pages → 创建 → Worker → 粘贴本文件 → 部署
//   2. 为该 Worker 添加一个路由：域名 https://www.chryit.xyz 的路径 /github/*（Custom Domains 或 Routes）
//   3. 完成。编辑器设置里填 API 代理 = https://www.chryit.xyz 即可。
//
// 可选：若不想把 token 存在浏览器，可在 Worker 环境变量/Secrets 里设置 GITHUB_TOKEN，
// 此时前端设置里可以留空 token，代理会用该 secret 代替。

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // 只处理 /github/* 路径
    if (!url.pathname.startsWith("/github/")) {
      return new Response("Not Found", { status: 404 });
    }

    // 处理浏览器跨域预检请求（OPTIONS）
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders() });
    }

    // /github/<repo-rest> -> https://api.github.com/<repo-rest>
    const apiPath = url.pathname.slice("/github".length) + url.search;
    const target = new URL("https://api.github.com" + apiPath);

    const headers = new Headers();
    headers.set("Host", "api.github.com");
    headers.set("Accept", "application/vnd.github+json");
    headers.set("User-Agent", "quartz-editor-worker");
    headers.set("X-GitHub-Api-Version", "2022-11-28");

    // 鉴权：优先用 Worker 环境变量 GITHUB_TOKEN，否则用浏览器传来的 X-GitHub-Token
    const token = env.GITHUB_TOKEN || request.headers.get("X-GitHub-Token");
    if (!token) {
      return new Response("No GitHub token provided", { status: 401 });
    }
    headers.set("Authorization", "Bearer " + token);

    const method = request.method;
    let body = null;
    if (method === "POST" || method === "PUT" || method === "DELETE" || method === "PATCH") {
      body = await request.text();
    }

    const upstreamRes = await fetch(target.toString(), {
      method,
      headers,
      body,
    });

    const responseHeaders = new Headers(upstreamRes.headers);
    // 允许页面跨域读取
    Object.entries(corsHeaders()).forEach(([k, v]) => responseHeaders.set(k, v));

    return new Response(upstreamRes.body, {
      status: upstreamRes.status,
      statusText: upstreamRes.statusText,
      headers: responseHeaders,
    });
  },
}

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-GitHub-Token, X-GitHub-Api-Version",
    "Access-Control-Max-Age": "86400",
  };
}