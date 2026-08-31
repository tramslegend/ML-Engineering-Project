"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Funnel,
  FunnelChart,
  LabelList,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  RadialBar,
  RadialBarChart,
  ResponsiveContainer,
  Sankey,
  Scatter,
  ScatterChart,
  Tooltip,
  Treemap,
  XAxis,
  YAxis,
} from "recharts";
import { ChartDataPoint, ChartType } from "@/lib/api";

const PALETTE = ["#B8892B", "#1F6B57", "#5C3F80", "#9AA3B2", "#7C4A3A", "#3E6B8A", "#A0522D", "#4B6043"];

const tooltipStyle = {
  borderRadius: 8,
  border: "1px solid #E4DCC8",
  fontSize: 12,
  fontFamily: "var(--font-public-sans)",
};

const catAxis = { tick: { fontSize: 11, fill: "#5A5240" }, angle: -20, textAnchor: "end" as const, height: 50, interval: 0 };

function Heatmap({ data }: { data: ChartDataPoint[] }) {
  const rows = Array.from(new Set(data.map((d) => d.row ?? "")));
  const cols = Array.from(new Set(data.map((d) => d.col ?? "")));
  const max = Math.max(...data.map((d) => d.value ?? 0), 1);
  const lookup = new Map(data.map((d) => [`${d.row}|${d.col}`, d.value ?? 0]));

  return (
    <div className="flex h-full w-full items-center justify-center overflow-auto p-2">
      <table className="border-collapse text-[11px]">
        <thead>
          <tr>
            <th className="p-1" />
            {cols.map((c) => (
              <th key={c} className="whitespace-nowrap p-1 font-medium text-bpr-ink2/60">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r}>
              <th className="whitespace-nowrap p-1 text-right font-medium text-bpr-ink2/60">{r}</th>
              {cols.map((c) => {
                const v = lookup.get(`${r}|${c}`) ?? 0;
                const intensity = v / max;
                return (
                  <td
                    key={c}
                    title={`${r} × ${c}: ${v}`}
                    className="h-8 w-8 border border-bpr-parchment text-center"
                    style={{
                      backgroundColor: `rgba(184,137,43,${0.12 + intensity * 0.78})`,
                      color: intensity > 0.55 ? "#fff" : "#2b2113",
                    }}
                  >
                    {v || ""}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function WordCloud({ data }: { data: ChartDataPoint[] }) {
  const values = data.map((d) => d.value ?? 0);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const scale = (v: number) => (max === min ? 20 : 13 + ((v - min) / (max - min)) * 28);

  return (
    <div className="flex h-full w-full flex-wrap items-center justify-center gap-x-3 gap-y-1 overflow-auto p-4">
      {data.map((d, i) => (
        <span
          key={d.label ?? i}
          style={{ fontSize: scale(d.value ?? 0), color: PALETTE[i % PALETTE.length], lineHeight: 1 }}
          className="font-display font-medium"
          title={`${d.label}: ${d.value}`}
        >
          {d.label}
        </span>
      ))}
    </div>
  );
}

export default function AnalysisChart({ chartType, data }: { chartType: ChartType; data: ChartDataPoint[] }) {
  if (chartType === "heatmap") return <Heatmap data={data} />;
  if (chartType === "wordcloud") return <WordCloud data={data} />;

  if (chartType === "pie") {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="label" innerRadius={44} outerRadius={80} paddingAngle={2}>
            {data.map((d, i) => (
              <Cell key={d.label ?? i} fill={PALETTE[i % PALETTE.length]} stroke="none" />
            ))}
          </Pie>
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Tooltip contentStyle={tooltipStyle} />
        </PieChart>
      </ResponsiveContainer>
    );
  }

  if (chartType === "line") {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E4DCC8" vertical={false} />
          <XAxis dataKey="label" {...catAxis} />
          <YAxis tick={{ fontSize: 11, fill: "#5A5240" }} />
          <Tooltip contentStyle={tooltipStyle} />
          <Line type="monotone" dataKey="value" stroke="#B8892B" strokeWidth={2.5} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  if (chartType === "area") {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E4DCC8" vertical={false} />
          <XAxis dataKey="label" {...catAxis} />
          <YAxis tick={{ fontSize: 11, fill: "#5A5240" }} />
          <Tooltip contentStyle={tooltipStyle} />
          <Area type="monotone" dataKey="value" stroke="#B8892B" fill="#B8892B" fillOpacity={0.25} />
        </AreaChart>
      </ResponsiveContainer>
    );
  }

  if (chartType === "radar") {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} outerRadius="72%">
          <PolarGrid stroke="#E4DCC8" />
          <PolarAngleAxis dataKey="label" tick={{ fontSize: 10, fill: "#5A5240" }} />
          <PolarRadiusAxis tick={{ fontSize: 10, fill: "#5A5240" }} />
          <Radar dataKey="value" stroke="#B8892B" fill="#B8892B" fillOpacity={0.35} />
          <Tooltip contentStyle={tooltipStyle} />
        </RadarChart>
      </ResponsiveContainer>
    );
  }

  if (chartType === "treemap") {
    const treeData = data.map((d) => ({ name: d.label, size: d.value }));
    return (
      <ResponsiveContainer width="100%" height="100%">
        <Treemap data={treeData} dataKey="size" nameKey="name" stroke="#fff" fill="#B8892B">
          {treeData.map((d, i) => (
            <Cell key={d.name ?? i} fill={PALETTE[i % PALETTE.length]} />
          ))}
        </Treemap>
      </ResponsiveContainer>
    );
  }

  if (chartType === "funnel") {
    const funnelData = [...data]
      .sort((a, b) => (b.value ?? 0) - (a.value ?? 0))
      .map((d, i) => ({ name: d.label, value: d.value ?? 0, fill: PALETTE[i % PALETTE.length] }));
    return (
      <ResponsiveContainer width="100%" height="100%">
        <FunnelChart>
          <Tooltip contentStyle={tooltipStyle} />
          <Funnel dataKey="value" data={funnelData} isAnimationActive>
            <LabelList position="right" dataKey="name" fill="#2b2113" stroke="none" fontSize={11} />
          </Funnel>
        </FunnelChart>
      </ResponsiveContainer>
    );
  }

  if (chartType === "radialbar") {
    const radialData = data.map((d, i) => ({ name: d.label, value: d.value, fill: PALETTE[i % PALETTE.length] }));
    return (
      <ResponsiveContainer width="100%" height="100%">
        <RadialBarChart data={radialData} innerRadius="20%" outerRadius="90%" startAngle={180} endAngle={-180}>
          <RadialBar dataKey="value" background cornerRadius={4} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Tooltip contentStyle={tooltipStyle} />
        </RadialBarChart>
      </ResponsiveContainer>
    );
  }

  if (chartType === "scatter") {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E4DCC8" />
          <XAxis type="number" dataKey="x" name="x" tick={{ fontSize: 11, fill: "#5A5240" }} />
          <YAxis type="number" dataKey="y" name="y" tick={{ fontSize: 11, fill: "#5A5240" }} />
          <Tooltip contentStyle={tooltipStyle} cursor={{ strokeDasharray: "3 3" }} />
          <Scatter data={data} fill="#B8892B" />
        </ScatterChart>
      </ResponsiveContainer>
    );
  }

  if (chartType === "stackedbar") {
    const rows = Array.from(new Set(data.map((d) => d.row ?? "")));
    const cols = Array.from(new Set(data.map((d) => d.col ?? "")));
    const lookup = new Map(data.map((d) => [`${d.row}|${d.col}`, d.value ?? 0]));
    const wide = rows.map((r) => {
      const entry: Record<string, string | number> = { row: r };
      cols.forEach((c) => {
        entry[c] = lookup.get(`${r}|${c}`) ?? 0;
      });
      return entry;
    });
    return (
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={wide} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E4DCC8" vertical={false} />
          <XAxis dataKey="row" {...catAxis} />
          <YAxis tick={{ fontSize: 11, fill: "#5A5240" }} />
          <Tooltip contentStyle={tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {cols.map((c, i) => (
            <Bar key={c} dataKey={c} stackId="a" fill={PALETTE[i % PALETTE.length]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    );
  }

  if (chartType === "sankey") {
    const nodeNames = Array.from(new Set(data.flatMap((d) => [d.row ?? "", d.col ?? ""])));
    const nodeIndex = new Map(nodeNames.map((n, i) => [n, i]));
    const sankeyData = {
      nodes: nodeNames.map((name) => ({ name })),
      links: data.map((d) => ({
        source: nodeIndex.get(d.row ?? "") ?? 0,
        target: nodeIndex.get(d.col ?? "") ?? 0,
        value: d.value ?? 0,
      })),
    };
    return (
      <ResponsiveContainer width="100%" height="100%">
        <Sankey data={sankeyData} node={{ stroke: "#B8892B", fill: "#B8892B" }} link={{ stroke: "#E4DCC8" }} nodePadding={20}>
          <Tooltip contentStyle={tooltipStyle} />
        </Sankey>
      </ResponsiveContainer>
    );
  }

  // default: bar
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#E4DCC8" vertical={false} />
        <XAxis dataKey="label" {...catAxis} />
        <YAxis tick={{ fontSize: 11, fill: "#5A5240" }} />
        <Tooltip contentStyle={tooltipStyle} />
        <Bar dataKey="value" fill="#B8892B" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
