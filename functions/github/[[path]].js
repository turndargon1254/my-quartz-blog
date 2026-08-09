// Cloudflare Pages Functions: /github/* -> 转发到 api.github.com/*
// 无需独立 Worker 或路由绑定，随 Pages 站点一起自动部署。
// 前端直接从同域的 /github/... 调用即可（无 CORS、无路由冲突）。
//
// 可选：在 Pages 项目 Settings -> Functions -> Variables 添加 GITHUB_TOKEN secret，
// 前端设置里就可以不放 token（更安全）。否则使用浏览器传来的 X-GitHub-Token 头。

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);

  const relPath = url.pathname.replace(/^\/github\//, "");
  const target = new URL("https://api.github.com/" + relPath + url.search);

  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders() });
  }

  const headers = new Headers();
  headers.set("Host", "api.github.com");
  headers.set("Accept", "application/vnd.github+json");
  headers.set("User-Agent", "quartz-pages-functions");
  headers.set("X-GitHub-Api-Version", "2022-11-28");

  const token = env.GITHUB_TOKEN || request.headers.get("X-GitHub-Token");
  if (!token) {
    return new Response(JSON.stringify({ ok: false, error: "缺少 GitHub token" }), {
      status: 401,
      headers: { "Content-Type": "application/json", ...corsHeaders() },
    });
  }
  headers.set("Authorization", "Bearer " + token);

  let body = null;
  if (["POST", "PUT", "PATCH", "DELETE"].includes(request.method)) {
    body = await request.text();
  }

  const upstream = await fetch(target.toString(), {
    method: request.method,
    headers,
    body,
  });

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: mergeCors(upstream.headers),
  });
}

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-GitHub-Token, X-GitHub-Api-Version",
    "Access-Control-Max-Age": "86400",
  };
}

function mergeCors(srcHeaders) {
  const out = new Headers(srcHeaders);
  Object.entries(corsHeaders()).forEach(([k, v]) => out.set(k, v));
  return out;
}