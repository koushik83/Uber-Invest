export default {
  async fetch(request, env) {
    // CORS headers — only allow your GitHub Pages site
    const corsHeaders = {
      "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN,
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };

    // Handle preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405, headers: corsHeaders });
    }

    try {
      const { query } = await request.json();

      if (!query || typeof query !== "string") {
        return Response.json({ error: "Missing query" }, { status: 400, headers: corsHeaders });
      }

      // Call Anthropic API with the secret key
      const resp = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-api-key": env.ANTHROPIC_API_KEY,
          "anthropic-version": "2023-06-01",
        },
        body: JSON.stringify({
          model: "claude-sonnet-4-20250514",
          max_tokens: 1000,
          tools: [{ type: "web_search_20250305", name: "web_search" }],
          messages: [{
            role: "user",
            content: `Search for "${query}" and return ONLY a JSON object: {"price": <number or null>, "news": ["headline1", "headline2"]}. Latest INR share price + 1-2 recent headlines. ONLY valid JSON, no markdown.`,
          }],
        }),
      });

      const data = await resp.json();

      if (data.error) {
        return Response.json({ price: null, news: [data.error.message || "API error"] }, { headers: corsHeaders });
      }

      // Extract the JSON from Claude's response
      const textBlocks = data.content?.filter((b) => b.type === "text").map((b) => b.text).join("");
      if (textBlocks) {
        const clean = textBlocks.replace(/```json|```/g, "").trim();
        const jsonMatch = clean.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
          return Response.json(JSON.parse(jsonMatch[0]), { headers: corsHeaders });
        }
      }

      return Response.json({ price: null, news: [] }, { headers: corsHeaders });
    } catch (e) {
      return Response.json({ price: null, news: [e.message] }, { status: 500, headers: corsHeaders });
    }
  },
};
