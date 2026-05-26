import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ZAxis, Cell } from "recharts";

export type KeywordBubblePoint = {
  keyword: string;
  date: string;
  article_count: number;
  zscore: number;
  spike_level: "normal" | "alert" | "danger";
  growth_rate: number;
};

type KeywordBubbleChartProps = {
  data: KeywordBubblePoint[];
  onBubbleClick: (point: KeywordBubblePoint) => void;
};

const levelColors: Record<KeywordBubblePoint["spike_level"], string> = {
  normal: "#16a34a",
  alert: "#f59e0b",
  danger: "#dc2626",
};

export function KeywordBubbleChart({ data, onBubbleClick }: KeywordBubbleChartProps) {
  const keywords = Array.from(new Set(data.map((item) => item.keyword)));
  const chartData = data.map((item) => ({
    ...item,
    x: new Date(item.date).getTime(),
    y: keywords.indexOf(item.keyword),
    z: Math.max(Math.sqrt(item.article_count) * 12, 24),
  }));

  return (
    <ResponsiveContainer width="100%" height={420}>
      <ScatterChart margin={{ top: 20, right: 24, left: 24, bottom: 36 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          type="number"
          dataKey="x"
          name="Ngay"
          domain={["dataMin", "dataMax"]}
          tickFormatter={(value) => new Date(value).toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" })}
          stroke="hsl(var(--muted-foreground))"
          tick={{ fontSize: 12 }}
        />
        <YAxis
          type="number"
          dataKey="y"
          name="Tu khoa"
          tickFormatter={(value) => keywords[value] || ""}
          domain={[-1, Math.max(keywords.length, 1)]}
          width={140}
          stroke="hsl(var(--muted-foreground))"
          tick={{ fontSize: 12 }}
        />
        <ZAxis type="number" dataKey="z" range={[32, 360]} />
        <Tooltip
          cursor={{ strokeDasharray: "3 3" }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const point = payload[0].payload as KeywordBubblePoint;
            return (
              <div className="rounded-lg border bg-card p-3 text-sm shadow-md">
                <div className="font-medium text-foreground">{point.keyword}</div>
                <div className="text-muted-foreground">{new Date(point.date).toLocaleDateString("vi-VN")}</div>
                <div className="mt-2 space-y-1">
                  <div>{point.article_count} bai bao</div>
                  <div>Z-score: {point.zscore.toFixed(2)}</div>
                  <div>Muc: {point.spike_level}</div>
                </div>
              </div>
            );
          }}
        />
        <Scatter
          data={chartData}
          onClick={(point) => onBubbleClick(point as KeywordBubblePoint)}
          className="cursor-pointer"
        >
          {chartData.map((entry, index) => (
            <Cell key={`bubble-${index}`} fill={levelColors[entry.spike_level]} fillOpacity={0.76} />
          ))}
        </Scatter>
      </ScatterChart>
    </ResponsiveContainer>
  );
}
