#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

// Configuration from environment
// URL can include credentials: https://token@your-site.nightscout.com
// Or use API_SECRET separately
const NIGHTSCOUT_URL = process.env.NIGHTSCOUT_URL || "";
const NIGHTSCOUT_API_SECRET = process.env.NIGHTSCOUT_API_SECRET || "";

// Parse URL to handle credentials properly
function parseNightscoutUrl(urlStr) {
  try {
    const url = new URL(urlStr);
    const result = {
      baseUrl: `${url.protocol}//${url.host}`,
      username: url.username || "",
      password: url.password || "",
      apiSecret: NIGHTSCOUT_API_SECRET,
    };
    return result;
  } catch {
    return { baseUrl: urlStr, username: "", password: "", apiSecret: NIGHTSCOUT_API_SECRET };
  }
}

const { baseUrl, username, password, apiSecret } = parseNightscoutUrl(NIGHTSCOUT_URL);

// Helper to make API requests with pagination support
async function nightscoutFetch(endpoint, params = {}) {
  if (!baseUrl) {
    throw new Error("NIGHTSCOUT_URL environment variable is not set");
  }

  const url = new URL(endpoint, baseUrl);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      url.searchParams.append(key, String(value));
    }
  });

  const headers = {};
  
  // Use Basic Auth if username is provided (token-based auth)
  if (username) {
    const credentials = Buffer.from(`${username}:${password}`).toString("base64");
    headers["Authorization"] = `Basic ${credentials}`;
  }
  
  // Also add api-secret if provided
  if (apiSecret) {
    headers["api-secret"] = apiSecret;
  }

  const response = await fetch(url.toString(), { headers });

  if (!response.ok) {
    throw new Error(`Nightscout API error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

// Fetch all entries for a date range with automatic pagination
// Nightscout typically limits to ~10000 entries per request
// Uses bracket notation for find params (works better with some Nightscout servers)
async function fetchEntriesInRange(startTs, endTs, maxPerRequest = 10000) {
  const allEntries = [];
  let currentEnd = endTs;
  let iterations = 0;
  const maxIterations = 100; // Safety limit
  
  while (iterations < maxIterations) {
    iterations++;
    
    // Build URL with bracket notation for find
    const url = new URL("/api/v1/entries.json", baseUrl);
    url.searchParams.append("count", String(maxPerRequest));
    url.searchParams.append("find[date][$gte]", String(startTs));
    url.searchParams.append("find[date][$lt]", String(currentEnd));
    url.searchParams.append("find[type]", "sgv");
    
    const headers = {};
    if (username) {
      headers["Authorization"] = `Basic ${Buffer.from(`${username}:${password}`).toString("base64")}`;
    }
    if (apiSecret) {
      headers["api-secret"] = apiSecret;
    }
    
    const response = await fetch(url.toString(), { headers });
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const entries = await response.json();
    
    if (!entries || entries.length === 0) break;
    
    allEntries.push(...entries);
    
    // Find oldest entry in this batch
    const oldestDate = Math.min(...entries.map(e => e.date));
    
    // If we got fewer than requested or oldest is at/before start, we're done
    if (entries.length < maxPerRequest || oldestDate <= startTs) break;
    
    // Move window back for next batch
    currentEnd = oldestDate;
  }
  
  return allEntries;
}

// Direction arrow mapping
const DIRECTION_ARROWS = {
  DoubleUp: "⇈",
  SingleUp: "↑",
  FortyFiveUp: "↗",
  Flat: "→",
  FortyFiveDown: "↘",
  SingleDown: "↓",
  DoubleDown: "⇊",
  "NOT COMPUTABLE": "?",
  "RATE OUT OF RANGE": "⚠️",
};

// Convert mg/dL to mmol/L
function mgdlToMmol(mgdl) {
  return (mgdl / 18.0182).toFixed(1);
}

// Strict TIR range: 70-140 mg/dL (3.9-7.8 mmol/L)
const TIR_LOW = 70;   // 3.9 mmol/L
const TIR_HIGH = 140; // 7.8 mmol/L

// Calculate statistics for a set of SGV values
function calculateStats(sgvValues) {
  if (!sgvValues || sgvValues.length === 0) return null;
  
  const n = sgvValues.length;
  const avg = sgvValues.reduce((a, b) => a + b, 0) / n;
  const variance = sgvValues.reduce((acc, val) => acc + Math.pow(val - avg, 2), 0) / n;
  const stdDev = Math.sqrt(variance);
  const cv = avg > 0 ? (stdDev / avg) * 100 : 0;
  
  // Ranges in mg/dL (mmol/L equivalents in comments)
  const veryLow = sgvValues.filter(v => v < 54).length;           // <3.0 mmol/L
  const low = sgvValues.filter(v => v >= 54 && v < 70).length;    // 3.0-3.9 mmol/L
  const inRange = sgvValues.filter(v => v >= TIR_LOW && v <= TIR_HIGH).length;  // 3.9-7.8 mmol/L (strict)
  const aboveTarget = sgvValues.filter(v => v > 140 && v <= 180).length;  // 7.8-10.0 mmol/L
  const high = sgvValues.filter(v => v > 180 && v <= 250).length; // 10.0-13.9 mmol/L
  const veryHigh = sgvValues.filter(v => v > 250).length;         // >13.9 mmol/L
  
  return {
    count: n,
    avg: Math.round(avg * 10) / 10,
    avgMmol: mgdlToMmol(avg),
    stdDev: Math.round(stdDev * 10) / 10,
    cv: Math.round(cv * 10) / 10,
    min: Math.min(...sgvValues),
    max: Math.max(...sgvValues),
    tir: Math.round((inRange / n) * 1000) / 10,           // Strict TIR (3.9-7.8)
    veryLowPct: Math.round((veryLow / n) * 1000) / 10,    // <3.0
    lowPct: Math.round((low / n) * 1000) / 10,            // 3.0-3.9
    aboveTargetPct: Math.round((aboveTarget / n) * 1000) / 10, // 7.8-10.0
    highPct: Math.round((high / n) * 1000) / 10,          // 10.0-13.9
    veryHighPct: Math.round((veryHigh / n) * 1000) / 10,  // >13.9
    a1c: Math.round(((avg + 46.7) / 28.7) * 10) / 10,
  };
}

// Parse date string to timestamp
function parseDateToTimestamp(dateStr) {
  // Support formats: YYYY-MM-DD, YYYY-MM, or relative like "7d", "2w", "3m", "1y"
  const relativeMatch = dateStr.match(/^(\d+)([dwmy])$/i);
  if (relativeMatch) {
    const num = parseInt(relativeMatch[1]);
    const unit = relativeMatch[2].toLowerCase();
    const now = Date.now();
    const multipliers = { d: 86400000, w: 604800000, m: 2592000000, y: 31536000000 };
    return now - num * multipliers[unit];
  }
  
  // YYYY-MM format
  if (/^\d{4}-\d{2}$/.test(dateStr)) {
    return new Date(dateStr + "-01T00:00:00Z").getTime();
  }
  
  // YYYY-MM-DD format
  return new Date(dateStr + "T00:00:00Z").getTime();
}

// Create MCP server
const server = new McpServer({
  name: "nightscout",
  version: "1.0.0",
});

// Tool: Get current glucose reading
server.tool(
  "glucose_current",
  "Get the current blood glucose reading from Nightscout",
  {},
  async () => {
    const entries = await nightscoutFetch("/api/v1/entries.json", { count: 1 });
    
    if (!entries || entries.length === 0) {
      return { content: [{ type: "text", text: "No glucose readings available" }] };
    }

    const e = entries[0];
    const arrow = DIRECTION_ARROWS[e.direction] || e.direction;
    const date = new Date(e.date);
    const timeStr = date.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
    const dateStr = date.toLocaleDateString("ru-RU");
    
    const text = `🩸 Текущий сахар: ${e.sgv} mg/dL (${mgdlToMmol(e.sgv)} ммоль/л) ${arrow}
📅 Время: ${dateStr} ${timeStr}
📈 Изменение: ${e.delta >= 0 ? "+" : ""}${e.delta} mg/dL
📱 Устройство: ${e.device}`;

    return { content: [{ type: "text", text }] };
  }
);

// Tool: Get glucose history with flexible date range
server.tool(
  "glucose_history",
  "Get blood glucose history for a specified time period",
  {
    hours: z.number().min(1).max(720).default(6).describe("Number of hours of history (1-720, i.e. up to 30 days)"),
    count: z.number().min(1).max(1000).default(100).describe("Maximum readings to show in output"),
  },
  async ({ hours, count }) => {
    const now = Date.now();
    const startTs = now - hours * 60 * 60 * 1000;

    const entries = await fetchEntriesInRange(startTs, now);

    if (!entries || entries.length === 0) {
      return { content: [{ type: "text", text: `Нет данных за последние ${hours} часов` }] };
    }

    const sgvValues = entries.filter(e => e.sgv != null).map(e => e.sgv);
    const stats = calculateStats(sgvValues);

    let text = `📊 История сахара за ${hours} ч (${entries.length} измерений)

📈 Статистика:
• Средний: ${stats.avg} mg/dL (${stats.avgMmol} ммоль/л)
• Мин/Макс: ${stats.min}–${stats.max} mg/dL
• TIR (3.9-7.8 ммоль): ${stats.tir}%
• CV: ${stats.cv}%

📋 Последние измерения:`;

    entries.slice(0, Math.min(count, 15)).forEach(e => {
      const date = new Date(e.date);
      const timeStr = date.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
      const dateStr = date.toLocaleDateString("ru-RU");
      const arrow = DIRECTION_ARROWS[e.direction] || e.direction;
      text += `\n• ${dateStr} ${timeStr}: ${e.sgv} ${arrow} (${mgdlToMmol(e.sgv)} ммоль/л)`;
    });

    if (entries.length > 15) {
      text += `\n... и ещё ${entries.length - 15} измерений`;
    }

    return { content: [{ type: "text", text }] };
  }
);

// Tool: Analyze glucose for any date range
server.tool(
  "analyze",
  "Analyze glucose patterns for any date range. Supports dates (YYYY-MM-DD), months (YYYY-MM), or relative periods (7d, 2w, 3m, 1y)",
  {
    from: z.string().default("7d").describe("Start date: YYYY-MM-DD, YYYY-MM, or relative (7d, 2w, 3m, 1y)"),
    to: z.string().optional().describe("End date (optional, defaults to now): YYYY-MM-DD or YYYY-MM"),
    tirGoal: z.number().min(50).max(100).default(70).describe("TIR goal percentage"),
  },
  async ({ from, to, tirGoal }) => {
    const startTs = parseDateToTimestamp(from);
    const endTs = to ? parseDateToTimestamp(to) : Date.now();
    
    // Add end of day/month if needed
    let adjustedEndTs = endTs;
    if (to && /^\d{4}-\d{2}$/.test(to)) {
      // End of month
      const [year, month] = to.split("-").map(Number);
      adjustedEndTs = new Date(Date.UTC(year, month, 1)).getTime(); // First day of next month
    } else if (to && /^\d{4}-\d{2}-\d{2}$/.test(to)) {
      adjustedEndTs = endTs + 86400000; // End of day
    }

    const entries = await fetchEntriesInRange(startTs, adjustedEndTs);

    if (!entries || entries.length < 10) {
      return { content: [{ type: "text", text: "Недостаточно данных для анализа за указанный период" }] };
    }

    const sgvValues = entries.filter(e => e.sgv != null).map(e => e.sgv);
    const stats = calculateStats(sgvValues);
    
    const fromDate = new Date(startTs).toLocaleDateString("ru-RU");
    const toDate = new Date(adjustedEndTs).toLocaleDateString("ru-RU");
    const days = Math.round((adjustedEndTs - startTs) / 86400000);

    const tirStatus = stats.tir >= tirGoal ? "✅" : stats.tir >= 70 ? "⚠️" : "❌";
    const cvStatus = stats.cv <= 33 ? "✅" : stats.cv <= 36 ? "⚠️" : "❌";

    let text = `📊 Анализ гликемии: ${fromDate} — ${toDate} (${days} дней, ${stats.count.toLocaleString()} измерений)

📈 Основные показатели:
• Средний сахар: ${stats.avg} mg/dL (${stats.avgMmol} ммоль/л)
• Мин/Макс: ${stats.min}–${stats.max} mg/dL
• Стандартное отклонение: ${stats.stdDev} mg/dL
• Коэффициент вариации: ${stats.cv}% ${cvStatus}
• Расчётный HbA1c: ${stats.a1c}%

🎯 Время в диапазонах:
• 🔴 Тяжёлая гипо (<3.0): ${stats.veryLowPct}% (цель <1%)
• 🟠 Гипогликемия (3.0-3.9): ${stats.lowPct}% (цель <4%)
• 🟢 В цели (3.9-7.8): ${stats.tir}% ${tirStatus} (цель ≥${tirGoal}%)
• 🟡 Выше цели (7.8-10.0): ${stats.aboveTargetPct}%
• 🟠 Высокий (10.0-13.9): ${stats.highPct}%
• 🔴 Очень высокий (>13.9): ${stats.veryHighPct}% (цель <5%)

💡 Оценка:`;

    if (stats.tir >= tirGoal) {
      text += `\n• ✅ Цель TIR ${tirGoal}% достигнута!`;
    } else {
      text += `\n• ⚠️ До цели TIR ${tirGoal}%: ${(tirGoal - stats.tir).toFixed(1)}%`;
    }

    if (stats.cv <= 33) {
      text += "\n• ✅ Отличная стабильность гликемии";
    } else if (stats.cv <= 36) {
      text += "\n• 📊 Хорошая стабильность";
    } else {
      text += "\n• ⚠️ Высокая вариабельность";
    }

    if (stats.veryLowPct > 1) {
      text += `\n• ⚠️ Много тяжёлых гипогликемий (${stats.veryLowPct}%)`;
    }

    return { content: [{ type: "text", text }] };
  }
);

// Tool: Monthly breakdown analysis
server.tool(
  "analyze_monthly",
  "Analyze glucose data broken down by month. Great for yearly reviews.",
  {
    year: z.number().min(2015).max(2030).describe("Year to analyze"),
    fromMonth: z.number().min(1).max(12).default(1).describe("Starting month (1-12)"),
    toMonth: z.number().min(1).max(12).default(12).describe("Ending month (1-12)"),
    tirGoal: z.number().min(50).max(100).default(85).describe("TIR goal percentage"),
  },
  async ({ year, fromMonth, toMonth, tirGoal }) => {
    const monthNames = ["", "Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"];
    const results = [];
    
    let text = `📊 Анализ глюкозы за ${year} год (цель TIR: ${tirGoal}%)\n`;
    text += "═".repeat(90) + "\n";
    text += "Месяц │  TIR (3.9-7.8)   │ Средний ммоль  │    CV    │   A1c   │ Измерений\n";
    text += "─".repeat(90) + "\n";
    
    for (let month = fromMonth; month <= toMonth; month++) {
      const startDate = new Date(Date.UTC(year, month - 1, 1));
      const endDate = month === 12 
        ? new Date(Date.UTC(year + 1, 0, 1))
        : new Date(Date.UTC(year, month, 1));
      
      try {
        const entries = await fetchEntriesInRange(startDate.getTime(), endDate.getTime());
        const sgvValues = entries.filter(e => e.sgv != null).map(e => e.sgv);
        const stats = calculateStats(sgvValues);
        
        if (stats && stats.count > 0) {
          results.push({ month, stats });
          
          const tirEmoji = stats.tir >= tirGoal ? "✅" : stats.tir >= 70 ? "⚠️" : "❌";
          const cvEmoji = stats.cv <= 33 ? "✅" : stats.cv <= 36 ? "⚠️" : "❌";
          
          text += `${monthNames[month].padEnd(5)} │ ${stats.tir.toFixed(1).padStart(7)}% ${tirEmoji}     │ ${stats.avgMmol.padStart(5)} ммоль    │ ${stats.cv.toFixed(1).padStart(5)}% ${cvEmoji} │ ${stats.a1c.toFixed(1).padStart(5)}% │ ${stats.count.toLocaleString().padStart(9)}\n`;
        } else {
          text += `${monthNames[month].padEnd(5)} │ Нет данных\n`;
        }
      } catch (err) {
        text += `${monthNames[month].padEnd(5)} │ Ошибка: ${err.message.slice(0, 50)}\n`;
      }
    }
    
    text += "═".repeat(90) + "\n";
    
    if (results.length > 0) {
      // Annual averages
      const avgTir = results.reduce((sum, r) => sum + r.stats.tir, 0) / results.length;
      const avgCv = results.reduce((sum, r) => sum + r.stats.cv, 0) / results.length;
      const avgGlucose = results.reduce((sum, r) => sum + r.stats.avg, 0) / results.length;
      const avgA1c = results.reduce((sum, r) => sum + r.stats.a1c, 0) / results.length;
      const totalCount = results.reduce((sum, r) => sum + r.stats.count, 0);
      
      const tirGoalMet = avgTir >= tirGoal ? "✅ ЦЕЛЬ ДОСТИГНУТА" : `⚠️ До цели: ${(tirGoal - avgTir).toFixed(1)}%`;
      
      text += `\n📈 СВОДКА ЗА ПЕРИОД (${results.length} месяцев, ${totalCount.toLocaleString()} измерений)\n`;
      text += "─".repeat(70) + "\n";
      text += `🎯 Средний TIR (3.9-7.8): ${avgTir.toFixed(1)}% — ${tirGoalMet}\n`;
      text += `📊 Средняя глюкоза: ${mgdlToMmol(avgGlucose)} ммоль/л\n`;
      text += `📉 Средний CV: ${avgCv.toFixed(1)}% — ${avgCv <= 33 ? "✅ Стабильно" : avgCv <= 36 ? "📊 Норма" : "⚠️ Высокий"}\n`;
      text += `🩸 Расчётный HbA1c: ${avgA1c.toFixed(1)}%\n`;
      
      // Trends
      if (results.length >= 3) {
        text += `\n📈 ТРЕНДЫ (первые 3 мес. vs последние 3 мес.)\n`;
        text += "─".repeat(70) + "\n";
        
        const firstQ = results.slice(0, 3);
        const lastQ = results.slice(-3);
        
        const firstTir = firstQ.reduce((s, r) => s + r.stats.tir, 0) / firstQ.length;
        const lastTir = lastQ.reduce((s, r) => s + r.stats.tir, 0) / lastQ.length;
        const tirTrend = lastTir - firstTir;
        
        const firstCv = firstQ.reduce((s, r) => s + r.stats.cv, 0) / firstQ.length;
        const lastCv = lastQ.reduce((s, r) => s + r.stats.cv, 0) / lastQ.length;
        const cvTrend = lastCv - firstCv;
        
        const firstAvg = firstQ.reduce((s, r) => s + r.stats.avg, 0) / firstQ.length;
        const lastAvg = lastQ.reduce((s, r) => s + r.stats.avg, 0) / lastQ.length;
        const avgTrend = lastAvg - firstAvg;
        
        const tirArrow = tirTrend > 2 ? "📈 улучшение" : tirTrend < -2 ? "📉 ухудшение" : "➡️ стабильно";
        const cvArrow = cvTrend < -2 ? "📈 улучшение" : cvTrend > 2 ? "📉 ухудшение" : "➡️ стабильно";
        
        text += `TIR: ${firstTir.toFixed(1)}% → ${lastTir.toFixed(1)}% (${tirTrend >= 0 ? "+" : ""}${tirTrend.toFixed(1)}%) ${tirArrow}\n`;
        text += `CV:  ${firstCv.toFixed(1)}% → ${lastCv.toFixed(1)}% (${cvTrend >= 0 ? "+" : ""}${cvTrend.toFixed(1)}%) ${cvArrow}\n`;
        text += `Глюкоза: ${firstAvg.toFixed(0)} → ${lastAvg.toFixed(0)} mg/dL (${avgTrend >= 0 ? "+" : ""}${avgTrend.toFixed(0)})\n`;
      }
      
      // Best/worst months
      const bestTir = results.reduce((best, r) => r.stats.tir > best.stats.tir ? r : best);
      const worstTir = results.reduce((worst, r) => r.stats.tir < worst.stats.tir ? r : worst);
      const bestCv = results.reduce((best, r) => r.stats.cv < best.stats.cv ? r : best);
      
      text += `\n🏆 Лучший TIR: ${monthNames[bestTir.month]} — ${bestTir.stats.tir.toFixed(1)}%\n`;
      text += `📉 Худший TIR: ${monthNames[worstTir.month]} — ${worstTir.stats.tir.toFixed(1)}%\n`;
      text += `🎯 Самый стабильный: ${monthNames[bestCv.month]} — CV ${bestCv.stats.cv.toFixed(1)}%\n`;
      
      // Insights
      text += `\n💡 ИНСАЙТЫ\n`;
      text += "─".repeat(70) + "\n";
      
      const monthsAboveGoal = results.filter(r => r.stats.tir >= tirGoal).length;
      const monthsAbove70 = results.filter(r => r.stats.tir >= 70).length;
      
      text += `• Месяцев с TIR ≥${tirGoal}%: ${monthsAboveGoal}/${results.length}\n`;
      text += `• Месяцев с TIR ≥70%: ${monthsAbove70}/${results.length}\n`;
      
      const avgVeryLow = results.reduce((s, r) => s + r.stats.veryLowPct, 0) / results.length;
      const avgLow = results.reduce((s, r) => s + r.stats.lowPct, 0) / results.length;
      const avgVeryHigh = results.reduce((s, r) => s + r.stats.veryHighPct, 0) / results.length;
      
      if (avgVeryLow < 1 && avgLow < 4) {
        text += `• ✅ Гипогликемии под контролем (<54: ${avgVeryLow.toFixed(1)}%, 54-70: ${avgLow.toFixed(1)}%)\n`;
      } else {
        text += `• ⚠️ Внимание гипогликемиям (<54: ${avgVeryLow.toFixed(1)}%, 54-70: ${avgLow.toFixed(1)}%)\n`;
      }
      
      if (avgVeryHigh < 5) {
        text += `• ✅ Мало тяжёлых гипергликемий (>250: ${avgVeryHigh.toFixed(1)}%)\n`;
      } else {
        text += `• ⚠️ Есть тяжёлые гипергликемии (>250: ${avgVeryHigh.toFixed(1)}%)\n`;
      }
    }
    
    return { content: [{ type: "text", text }] };
  }
);

// Tool: Get treatments
server.tool(
  "treatments",
  "Get recent treatments (insulin doses, carbs, etc.)",
  {
    hours: z.number().min(1).max(168).default(24).describe("Hours of history (up to 7 days)"),
    count: z.number().min(1).max(200).default(50).describe("Maximum treatments to return"),
  },
  async ({ hours, count }) => {
    const now = Date.now();
    const startDate = now - hours * 60 * 60 * 1000;

    // Build URL with bracket notation for find
    const url = new URL("/api/v1/treatments.json", baseUrl);
    url.searchParams.append("count", String(count));
    url.searchParams.append("find[created_at][$gte]", new Date(startDate).toISOString());
    
    const headers = {};
    if (username) {
      headers["Authorization"] = `Basic ${Buffer.from(`${username}:${password}`).toString("base64")}`;
    }
    if (apiSecret) {
      headers["api-secret"] = apiSecret;
    }
    
    const response = await fetch(url.toString(), { headers });
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    const treatments = await response.json();

    if (!treatments || treatments.length === 0) {
      return { content: [{ type: "text", text: `Нет записей о лечении за последние ${hours} часов` }] };
    }

    let totalInsulin = 0;
    let totalCarbs = 0;
    let text = `💉 Записи о лечении за ${hours} ч:\n`;

    treatments.forEach(t => {
      const date = new Date(t.created_at);
      const timeStr = date.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
      const dateStr = date.toLocaleDateString("ru-RU");

      let line = `• ${dateStr} ${timeStr}: `;
      if (t.eventType) line += `[${t.eventType}] `;
      if (t.insulin) { line += `💉 ${t.insulin} ед `; totalInsulin += t.insulin; }
      if (t.carbs) { line += `🍞 ${t.carbs} г `; totalCarbs += t.carbs; }
      if (t.notes) line += `📝 ${t.notes}`;
      text += line + "\n";
    });

    text += `\n📊 Итого:`;
    if (totalInsulin > 0) text += ` 💉 ${totalInsulin.toFixed(1)} ед`;
    if (totalCarbs > 0) text += ` 🍞 ${totalCarbs} г`;

    return { content: [{ type: "text", text }] };
  }
);

// Tool: Get status
server.tool(
  "status",
  "Get Nightscout server status and settings",
  {},
  async () => {
    const status = await nightscoutFetch("/api/v1/status.json");

    let text = `⚙️ Статус Nightscout:
• Название: ${status.name || "N/A"}
• Версия: ${status.version || "N/A"}
• Сервер: ${status.serverTime || "N/A"}
• Единицы: ${status.settings?.units || "mg/dl"}`;

    if (status.settings?.thresholds) {
      const t = status.settings.thresholds;
      text += `\n\n🎯 Пороговые значения:
• Высокий: ${t.bgHigh} mg/dL
• Целевой верх: ${t.bgTargetTop} mg/dL
• Целевой низ: ${t.bgTargetBottom} mg/dL
• Низкий: ${t.bgLow} mg/dL`;
    }

    return { content: [{ type: "text", text }] };
  }
);

// Tool: Device status
server.tool(
  "devices",
  "Get status of connected devices (pump, CGM, phone)",
  {
    count: z.number().min(1).max(20).default(5).describe("Number of device status entries"),
  },
  async ({ count }) => {
    const devices = await nightscoutFetch("/api/v1/devicestatus.json", { count });

    if (!devices || devices.length === 0) {
      return { content: [{ type: "text", text: "Нет данных об устройствах" }] };
    }

    let text = "📱 Статус устройств:\n";

    devices.forEach(d => {
      const date = new Date(d.created_at);
      const timeStr = date.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
      text += `\n⏰ ${timeStr}:`;
      if (d.uploader) text += `\n  📱 Загрузчик: батарея ${d.uploader.battery}%`;
      if (d.pump) text += `\n  💉 Помпа: резервуар ${d.pump.reservoir}ед, батарея ${d.pump.battery?.percent || "?"}%`;
      if (d.device) text += `\n  📡 Устройство: ${d.device}`;
    });

    return { content: [{ type: "text", text }] };
  }
);

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Nightscout MCP server running...");
}

main().catch(console.error);
