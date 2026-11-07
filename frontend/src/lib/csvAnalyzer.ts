export interface AnalyzedRecord {
  id: string;
  text: string;
  product: string;
  source: string;
  timestamp: string;
  sentiment: "positive" | "neutral" | "negative";
  theme: string;
  qualityScore: number;
  piiDetected: boolean;
  piiTypes: string[];
}

export interface CSVAnalysisResult {
  filename: string;
  totalRecords: number;
  validRecords: number;
  duplicateRecords: number;
  avgLength: number;
  sentimentDistribution: {
    positive: number;
    neutral: number;
    negative: number;
    positivePercent: number;
    neutralPercent: number;
    negativePercent: number;
  };
  overallQualityScore: number;
  piiCount: number;
  themes: Array<{
    name: string;
    count: number;
    percentage: number;
    sentiment: "positive" | "neutral" | "negative";
  }>;
  insights: Array<{
    title: string;
    description: string;
    tone: "good" | "warn" | "bad";
  }>;
  records: AnalyzedRecord[];
}

// Simple RFC 4180 CSV parser
export function parseCSV(csvText: string): string[][] {
  const rows: string[][] = [];
  let currentRow: string[] = [];
  let currentField = "";
  let insideQuotes = false;

  for (let i = 0; i < csvText.length; i++) {
    const char = csvText[i];
    const nextChar = csvText[i + 1];

    if (char === '"') {
      if (insideQuotes && nextChar === '"') {
        currentField += '"';
        i++; // skip escaped quote
      } else {
        insideQuotes = !insideQuotes;
      }
    } else if (char === "," && !insideQuotes) {
      currentRow.push(currentField.trim());
      currentField = "";
    } else if ((char === "\r" || char === "\n") && !insideQuotes) {
      if (char === "\r" && nextChar === "\n") i++; // handle CRLF
      currentRow.push(currentField.trim());
      if (currentRow.some((field) => field.length > 0)) {
        rows.push(currentRow);
      }
      currentRow = [];
      currentField = "";
    } else {
      currentField += char;
    }
  }

  if (currentField.length > 0 || currentRow.length > 0) {
    currentRow.push(currentField.trim());
    if (currentRow.some((field) => field.length > 0)) {
      rows.push(currentRow);
    }
  }

  return rows;
}

const positiveWords = [
  "love", "great", "excellent", "good", "fast", "faster", "smooth", "helpful", "amazing",
  "awesome", "best", "easy", "clean", "appreciate", "like", "wonderful", "solved", "improved",
  "fantastic", "intuitive", "reliable", "perfect", "favorite", "speed"
];

const negativeWords = [
  "fail", "fails", "failed", "broken", "slow", "error", "bug", "crash", "stuck", "freeze",
  "poor", "bad", "terrible", "horrible", "hate", "issue", "problem", "difficult", "confusing",
  "unresponsive", "timeout", "expensive", "charged twice", "wrong", "annoying", "frustrated", "delay"
];

const themeKeywords: Record<string, string[]> = {
  "Performance & Latency": ["slow", "speed", "fast", "latency", "load", "loading", "freeze", "lag", "timeout", "delay"],
  "Payments & Billing": ["bill", "billing", "charge", "charged", "stripe", "payment", "invoice", "refund", "card", "subscription", "price"],
  "UI & Usability": ["ui", "design", "layout", "button", "color", "dark mode", "font", "confusing", "intuitive", "navigation", "menu"],
  "Search & Filtering": ["search", "filter", "query", "find", "results", "sort", "lookup", "filter"],
  "Integrations & Export": ["export", "csv", "json", "api", "webhook", "download", "sync", "integration", "connect"],
  "Account & Authentication": ["login", "signin", "auth", "password", "2fa", "signup", "access", "account", "logout"],
};

export function analyzeFeedbackCSV(csvText: string, filename: string): CSVAnalysisResult {
  const rawRows = parseCSV(csvText);

  if (rawRows.length < 2) {
    throw new Error("CSV file must contain at least a header row and one record.");
  }

  const headers = rawRows[0].map((h) => h.toLowerCase().replace(/[\s_-]+/g, ""));
  const dataRows = rawRows.slice(1);

  // Column index identification
  const findColIndex = (candidates: string[]): number => {
    return headers.findIndex((h) => candidates.some((cand) => h.includes(cand)));
  };

  const textColIndex = findColIndex(["feedbacktext", "feedback", "text", "comment", "review", "message", "body", "note"]);
  const productColIndex = findColIndex(["product", "app", "category", "module", "service"]);
  const sourceColIndex = findColIndex(["source", "channel", "origin", "platform"]);
  const timeColIndex = findColIndex(["timestamp", "date", "createdat", "time"]);
  const idColIndex = findColIndex(["id", "feedbackid", "uuid", "key"]);

  const actualTextCol = textColIndex >= 0 ? textColIndex : 0;

  const seenTexts = new Set<string>();
  let duplicates = 0;
  let totalLength = 0;
  let positiveCount = 0;
  let neutralCount = 0;
  let negativeCount = 0;
  let piiTotal = 0;

  const themeCounts: Record<string, { count: number; pos: number; neg: number }> = {};
  Object.keys(themeKeywords).forEach((k) => {
    themeCounts[k] = { count: 0, pos: 0, neg: 0 };
  });
  themeCounts["General Feedback"] = { count: 0, pos: 0, neg: 0 };

  const analyzedRecords: AnalyzedRecord[] = [];

  const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
  const phoneRegex = /\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b/g;

  dataRows.forEach((row, index) => {
    const rawText = (row[actualTextCol] || "").trim();
    if (!rawText) return;

    if (seenTexts.has(rawText.toLowerCase())) {
      duplicates++;
    } else {
      seenTexts.add(rawText.toLowerCase());
    }

    totalLength += rawText.length;

    // Sentiment detection
    const lower = rawText.toLowerCase();
    let posScore = 0;
    let negScore = 0;
    positiveWords.forEach((word) => {
      if (lower.includes(word)) posScore++;
    });
    negativeWords.forEach((word) => {
      if (lower.includes(word)) negScore++;
    });

    let sentiment: "positive" | "neutral" | "negative" = "neutral";
    if (posScore > negScore) sentiment = "positive";
    else if (negScore > posScore) sentiment = "negative";

    if (sentiment === "positive") positiveCount++;
    else if (sentiment === "negative") negativeCount++;
    else neutralCount++;

    // PII Detection
    const piiTypes: string[] = [];
    if (emailRegex.test(rawText)) piiTypes.push("email");
    if (phoneRegex.test(rawText)) piiTypes.push("phone");
    if (piiTypes.length > 0) piiTotal++;

    // Theme identification
    let matchedTheme = "General Feedback";
    for (const [themeName, keywords] of Object.entries(themeKeywords)) {
      if (keywords.some((kw) => lower.includes(kw))) {
        matchedTheme = themeName;
        break;
      }
    }

    themeCounts[matchedTheme].count++;
    if (sentiment === "positive") themeCounts[matchedTheme].pos++;
    if (sentiment === "negative") themeCounts[matchedTheme].neg++;

    // Quality calculation (length, punctuation, absence of pure noise)
    let score = 0.85;
    if (rawText.length > 40) score += 0.08;
    if (rawText.length < 15) score -= 0.15;
    if (piiTypes.length > 0) score -= 0.05;
    const qualityScore = Math.min(0.99, Math.max(0.4, Number(score.toFixed(2))));

    analyzedRecords.push({
      id: (idColIndex >= 0 && row[idColIndex]) || `fb-${index + 101}`,
      text: rawText,
      product: (productColIndex >= 0 && row[productColIndex]) || "General",
      source: (sourceColIndex >= 0 && row[sourceColIndex]) || "upload",
      timestamp: (timeColIndex >= 0 && row[timeColIndex]) || new Date().toISOString(),
      sentiment,
      theme: matchedTheme,
      qualityScore,
      piiDetected: piiTypes.length > 0,
      piiTypes,
    });
  });

  const validCount = analyzedRecords.length;
  const posPct = validCount > 0 ? Math.round((positiveCount / validCount) * 100) : 0;
  const negPct = validCount > 0 ? Math.round((negativeCount / validCount) * 100) : 0;
  const neuPct = validCount > 0 ? 100 - posPct - negPct : 0;

  // Process top themes
  const processedThemes = Object.entries(themeCounts)
    .filter(([_, data]) => data.count > 0)
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 5)
    .map(([name, data]) => ({
      name,
      count: data.count,
      percentage: Math.round((data.count / validCount) * 100),
      sentiment: data.pos >= data.neg ? ("positive" as const) : ("negative" as const),
    }));

  // Generate automated insights
  const insights: CSVAnalysisResult["insights"] = [];

  if (negPct > 30) {
    insights.push({
      title: "Elevated Negative Sentiment",
      description: `${negPct}% of customer feedback contains negative friction. Primary clusters center around ${processedThemes[0]?.name || "core features"}.`,
      tone: "bad",
    });
  } else if (posPct > 50) {
    insights.push({
      title: "Strong Positive Sentiment",
      description: `${posPct}% of feedback is favorable, reflecting high user satisfaction across analyzed touchpoints.`,
      tone: "good",
    });
  }

  if (processedThemes.length > 0) {
    const topTheme = processedThemes[0];
    insights.push({
      title: `Dominant Driver: ${topTheme.name}`,
      description: `${topTheme.name} accounts for ${topTheme.count} records (${topTheme.percentage}% of uploaded volume).`,
      tone: topTheme.sentiment === "positive" ? "good" : "warn",
    });
  }

  if (piiTotal > 0) {
    insights.push({
      title: `PII Detected in ${piiTotal} Records`,
      description: `Personal identifiers (emails/phone numbers) were detected in ${piiTotal} records and will be redacted during batch cleaning.`,
      tone: "warn",
    });
  }

  return {
    filename,
    totalRecords: rawRows.length - 1,
    validRecords: validCount,
    duplicateRecords: duplicates,
    avgLength: validCount > 0 ? Math.round(totalLength / validCount) : 0,
    sentimentDistribution: {
      positive: positiveCount,
      neutral: neutralCount,
      negative: negativeCount,
      positivePercent: posPct,
      neutralPercent: neuPct,
      negativePercent: negPct,
    },
    overallQualityScore: validCount > 0 ? Number((analyzedRecords.reduce((acc, r) => acc + r.qualityScore, 0) / validCount).toFixed(2)) : 0.85,
    piiCount: piiTotal,
    themes: processedThemes,
    insights,
    records: analyzedRecords,
  };
}
