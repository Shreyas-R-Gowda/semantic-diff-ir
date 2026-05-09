import {
  Activity,
  BarChart3,
  Braces,
  CheckCircle2,
  Code2,
  GitCompareArrows,
  Loader2,
  Play,
  RotateCcw,
  Search,
  Server,
  TriangleAlert
} from "lucide-react";
import type React from "react";
import { useEffect, useMemo, useRef, useState } from "react";

type Example = {
  id: string;
  project: string;
  commit_description: string;
  old_ir: string;
  new_ir: string;
  expected_kinds: string[];
};

type Change = {
  kind: string;
  description: string;
  severity: string;
  details: string;
};

type BlockDiff = {
  old_label: string | null;
  new_label: string | null;
  status: string;
  similarity: number;
  added_instrs: string[];
  removed_instrs: string[];
};

type FunctionReport = {
  old_name: string;
  new_name: string;
  status: string;
  match_confidence: number;
  match_reason: string;
  metrics: Record<string, number>;
  changes: Change[];
  block_diffs: BlockDiff[];
};

type DiffResponse = {
  report: {
    summary: {
      total_functions: number;
      changed: number;
      added: number;
      removed: number;
      modified: number;
    };
    functions: FunctionReport[];
  };
  text: string;
};

type BenchmarkResponse = {
  summary: {
    passed: number;
    total: number;
    average_f1: number;
  };
  cases: Array<{
    id: string;
    project: string;
    passed: boolean;
    expected_kinds: string[];
    found_kinds: string[];
  }>;
};

const fallbackOldIr = `define i32 @compute(i32 %x) {
entry:
  %r = call i32 @helper(i32 %x)
  ret i32 %r
}
`;

const fallbackNewIr = `define i32 @compute(i32 %x) {
entry:
  %r = mul i32 %x, %x
  ret i32 %r
}
`;

function CFGGraph({ blockDiffs, funcName }: {
  blockDiffs: BlockDiff[];
  funcName: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open || !containerRef.current || blockDiffs.length === 0) return;

    import("cytoscape").then(({ default: cytoscape }) => {
      const nodes = blockDiffs.map((bd) => {
        const label = bd.new_label || bd.old_label || "?";
        let color = "#FFFFFF";
        let borderColor = "#D8DEE9";
        let textColor = "#1F1F1F";

        if (bd.status === "added") {
          color = "#E6F7EE"; borderColor = "#00A651"; textColor = "#00652F";
        } else if (bd.status === "removed") {
          color = "#FFF0F0"; borderColor = "#D0021B"; textColor = "#A00000";
        } else if (bd.similarity < 1.0) {
          color = "#FFF8E6"; borderColor = "#F5A623"; textColor = "#B06000";
        } else {
          color = "#EBF7FD"; borderColor = "#0096D6"; textColor = "#003087";
        }

        const infoLines = [];
        if (bd.status === "added")   infoLines.push("+ ADDED");
        if (bd.status === "removed") infoLines.push("- REMOVED");
        if (bd.status === "matched" && bd.similarity < 1.0)
          infoLines.push(`~${Math.round(bd.similarity * 100)}% similar`);
        if (bd.added_instrs.length)
          infoLines.push(`+[${bd.added_instrs.slice(0,3).join(", ")}]`);
        if (bd.removed_instrs.length)
          infoLines.push(`-[${bd.removed_instrs.slice(0,3).join(", ")}]`);

        return {
          data: {
            id: label,
            label: label + (infoLines.length ? "\n" + infoLines.join("\n") : ""),
            color,
            borderColor,
            textColor,
          }
        };
      });

      const edges = blockDiffs
        .filter((bd) => bd.old_label && bd.new_label && bd.old_label !== bd.new_label)
        .map((bd) => ({
          data: {
            id: `${bd.old_label}->${bd.new_label}`,
            source: bd.old_label!,
            target: bd.new_label!,
          }
        }));

      const cy = cytoscape({
        container: containerRef.current,
        elements: { nodes, edges },
        style: [
          {
            selector: "node",
            style: {
              label: "data(label)",
              "text-valign": "center",
              "text-halign": "center",
              "white-space": "pre",
              "font-family": "SF Mono, Fira Code, monospace",
              "font-size": "10px",
              "background-color": "data(color)",
              "border-color": "data(borderColor)",
              "border-width": 2,
              color: "data(textColor)",
              "text-wrap": "wrap",
              width: "label",
              height: "label",
              padding: "10px",
              shape: "roundrectangle",
            },
          },
          {
            selector: "edge",
            style: {
              width: 1.5,
              "line-color": "#D8DEE9",
              "target-arrow-color": "#D8DEE9",
              "target-arrow-shape": "triangle",
              "curve-style": "bezier",
            },
          },
        ] as any,
        layout: { name: "breadthfirst", directed: true, padding: 20 },
        userZoomingEnabled: true,
        userPanningEnabled: true,
      });

      return () => cy.destroy();
    });
  }, [open, blockDiffs]);

  if (blockDiffs.length === 0) return null;

  return (
    <div style={{ marginTop: "14px" }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          background: open ? "#003087" : "#0096D6",
          color: "#fff",
          border: "none",
          borderRadius: "6px",
          padding: "7px 14px",
          fontSize: "12px",
          fontWeight: 600,
          cursor: "pointer",
          marginBottom: open ? "10px" : 0,
        }}
      >
        {open ? "▲ Hide CFG Graph" : "▼ View CFG Graph"}
      </button>

      {open && (
        <div style={{ border: "1.5px solid #D8DEE9", borderRadius: "8px", overflow: "hidden" }}>
          <div
            style={{
              background: "#EBF7FD",
              borderBottom: "1px solid #D8DEE9",
              padding: "6px 14px",
              fontSize: "11px",
              fontWeight: 700,
              letterSpacing: "0.5px",
              textTransform: "uppercase",
              color: "#003087",
              display: "flex",
              gap: "16px",
              alignItems: "center",
            }}
          >
            <span>CFG Diff — {funcName}</span>
            <span style={{ color: "#00652F" }}>■ Added</span>
            <span style={{ color: "#B06000" }}>■ Modified</span>
            <span style={{ color: "#A00000" }}>■ Removed</span>
            <span style={{ color: "#003087" }}>■ Unchanged</span>
          </div>
          <div
            ref={containerRef}
            style={{ width: "100%", height: "320px", background: "#F5F7FA" }}
          />
        </div>
      )}
    </div>
  );
}

function highlightIR(line: string): React.ReactNode {
  // Tokenize and colorize one line of LLVM IR
  if (line.trim() === "" || line.trim() === "}") {
    return <span style={{ color: "#E6EDF3" }}>{line}</span>;
  }
  // Comment lines
  if (line.trim().startsWith(";")) {
    return <span style={{ color: "#8B949E", fontStyle: "italic" }}>{line}</span>;
  }
  // Block labels (e.g. "entry:", "loop:", "bb0:")
  if (/^[\w.$]+:\s*$/.test(line.trim())) {
    return <span style={{ color: "#79C0FF", fontWeight: 700 }}>{line}</span>;
  }
  // Function define/declare lines
  if (/^\s*(define|declare)\b/.test(line)) {
    return (
      <span>
        {line.split(/\b(define|declare|@[\w.$]+)\b/).map((part, i) => {
          if (/^(define|declare)$/.test(part))
            return <span key={i} style={{ color: "#FF7B72", fontWeight: 700 }}>{part}</span>;
          if (/^@[\w.$]+$/.test(part))
            return <span key={i} style={{ color: "#D2A8FF" }}>{part}</span>;
          return <span key={i} style={{ color: "#E6EDF3" }}>{part}</span>;
        })}
      </span>
    );
  }
  // Instruction lines
  const opcodes = [
    "load","store","alloca","getelementptr","br","ret","switch",
    "call","tail call","add","sub","mul","sdiv","udiv","fadd","fsub",
    "fmul","fdiv","shl","lshr","ashr","and","or","xor","icmp","fcmp",
    "phi","select","trunc","zext","sext","bitcast","ptrtoint","inttoptr",
    "extractelement","insertelement","shufflevector","extractvalue",
    "insertvalue","atomicrmw","cmpxchg","unreachable","invoke","resume",
  ];
  const opcodePattern = new RegExp(`\\b(${opcodes.join("|")})\\b`);
  const parts = line.split(/((%[\w.$]+)|(@[\w.$]+)|(<[\d\s]*x\s*\w+>)|(i\d+\b)|(\b\d+\b))/g);
  const isInstrLine = /^\s+/.test(line) && !/^\s+;/.test(line);

  return (
    <span>
      {parts.map((part, i) => {
        if (!part) return null;
        if (isInstrLine && opcodePattern.test(part) && !/^[%@]/.test(part))
          return <span key={i} style={{ color: "#FF7B72", fontWeight: 600 }}>{part}</span>;
        if (/^%[\w.$]+$/.test(part))
          return <span key={i} style={{ color: "#79C0FF" }}>{part}</span>;
        if (/^@[\w.$]+$/.test(part))
          return <span key={i} style={{ color: "#D2A8FF" }}>{part}</span>;
        if (/^<[\d\s]*x\s*\w+>$/.test(part))
          return <span key={i} style={{ color: "#FFA657", fontWeight: 600 }}>{part}</span>;
        if (/^i\d+$/.test(part))
          return <span key={i} style={{ color: "#56D364" }}>{part}</span>;
        if (/^\d+$/.test(part))
          return <span key={i} style={{ color: "#F2CC60" }}>{part}</span>;
        return <span key={i} style={{ color: "#E6EDF3" }}>{part}</span>;
      })}
    </span>
  );
}

function DiffViewer({ oldIr, newIr, onChange }: {
  oldIr: string;
  newIr: string;
  onChange: (side: "old" | "new", value: string) => void;
}) {
  const [editMode, setEditMode] = useState(false);

  const oldLines = oldIr.split("\n");
  const newLines = newIr.split("\n");

  // Simple line-level diff: mark lines added/removed/changed
  const maxLen = Math.max(oldLines.length, newLines.length);
  const diffOld: Array<{ line: string; status: "same" | "removed" | "changed" }> = [];
  const diffNew: Array<{ line: string; status: "same" | "added" | "changed" }> = [];

  for (let i = 0; i < maxLen; i++) {
    const o = oldLines[i] ?? "";
    const n = newLines[i] ?? "";
    if (o === n) {
      diffOld.push({ line: o, status: "same" });
      diffNew.push({ line: n, status: "same" });
    } else if (o === "" && n !== "") {
      diffOld.push({ line: "", status: "same" });
      diffNew.push({ line: n, status: "added" });
    } else if (n === "" && o !== "") {
      diffOld.push({ line: o, status: "removed" });
      diffNew.push({ line: "", status: "same" });
    } else {
      diffOld.push({ line: o, status: "removed" });
      diffNew.push({ line: n, status: "added" });
    }
  }

  const lineStyle = (status: string): React.CSSProperties => {
    if (status === "removed") return {
      background: "rgba(208,2,27,0.18)",
      borderLeft: "3px solid #D0021B",
      paddingLeft: "9px",
      display: "flex",
      alignItems: "flex-start",
      minHeight: "20px",
    };
    if (status === "added") return {
      background: "rgba(0,166,81,0.18)",
      borderLeft: "3px solid #00A651",
      paddingLeft: "9px",
      display: "flex",
      alignItems: "flex-start",
      minHeight: "20px",
    };
    return {
      paddingLeft: "12px",
      display: "flex",
      alignItems: "flex-start",
      minHeight: "20px",
    };
  };

  const paneStyle: React.CSSProperties = {
    flex: 1,
    background: "#0D1117",
    overflow: "auto",
    fontFamily: '"SF Mono","Fira Code","Consolas",monospace',
    fontSize: "12.5px",
    lineHeight: "1.6",
  };

  const labelStyle: React.CSSProperties = {
    padding: "6px 14px",
    fontSize: "11px",
    fontWeight: 700,
    letterSpacing: "0.8px",
    textTransform: "uppercase",
    borderBottom: "1px solid #30363D",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
  };

  if (editMode) {
    return (
      <div style={{ display: "flex", flexDirection: "column", flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center",
          justifyContent: "flex-end", padding: "6px 14px",
          background: "#0D1117", borderBottom: "1px solid #30363D" }}>
          <button onClick={() => setEditMode(false)} style={{
            background: "#0096D6", color: "#fff", border: "none",
            borderRadius: "6px", padding: "4px 12px", fontSize: "12px",
            fontWeight: 600, cursor: "pointer"
          }}>
            ← Back to Diff View
          </button>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr",
          gap: "1px", background: "#30363D", flex: 1 }}>
          {(["old", "new"] as const).map((side) => (
            <div key={side} style={{ display: "flex", flexDirection: "column",
              background: "#0D1117" }}>
              <div style={{ ...labelStyle, color: side === "old" ? "#FF7B72" : "#56D364",
                background: "#161B22" }}>
                {side === "old" ? "OLD IR" : "NEW IR"}
              </div>
              <textarea
                value={side === "old" ? oldIr : newIr}
                onChange={(e) => onChange(side, e.target.value)}
                style={{
                  flex: 1, background: "#0D1117", color: "#E6EDF3",
                  border: "none", outline: "none", resize: "none",
                  fontFamily: '"SF Mono","Fira Code","Consolas",monospace',
                  fontSize: "12.5px", lineHeight: "1.6",
                  padding: "12px 14px", minHeight: "220px",
                }}
              />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1 }}>
      <div style={{ display: "flex", alignItems: "center",
        justifyContent: "flex-end", padding: "6px 14px",
        background: "#0D1117", borderBottom: "1px solid #30363D",
        gap: "14px" }}>
        <span style={{ fontSize: "11px", color: "#8B949E", display: "flex", gap: "12px" }}>
          <span style={{ color: "#56D364" }}>■ Added</span>
          <span style={{ color: "#D0021B" }}>■ Removed</span>
          <span style={{ color: "#8B949E" }}>■ Unchanged</span>
        </span>
        <button onClick={() => setEditMode(true)} style={{
          background: "transparent", color: "#8B949E",
          border: "1px solid #30363D", borderRadius: "6px",
          padding: "4px 12px", fontSize: "12px",
          fontWeight: 500, cursor: "pointer"
        }}>
          ✎ Edit IR
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr",
        gap: "1px", background: "#30363D", flex: 1 }}>

        {/* Old IR pane */}
        <div style={paneStyle}>
          <div style={{ ...labelStyle, color: "#FF7B72", background: "#161B22" }}>
            OLD IR
            <span style={{ color: "#8B949E", fontWeight: 400,
              textTransform: "none", letterSpacing: 0 }}>
              {oldLines.length} lines
            </span>
          </div>
          <div style={{ padding: "8px 0" }}>
            {diffOld.map((entry, i) => (
              <div key={i} style={lineStyle(entry.status)}>
                <span style={{ color: "#484F58", fontSize: "11px",
                  minWidth: "32px", userSelect: "none",
                  paddingRight: "12px", textAlign: "right" }}>
                  {i + 1}
                </span>
                <span style={{ flex: 1, whiteSpace: "pre" }}>
                  {entry.status === "removed" && (
                    <span style={{ color: "#D0021B", marginRight: "6px" }}>−</span>
                  )}
                  {highlightIR(entry.line)}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* New IR pane */}
        <div style={paneStyle}>
          <div style={{ ...labelStyle, color: "#56D364", background: "#161B22" }}>
            NEW IR
            <span style={{ color: "#8B949E", fontWeight: 400,
              textTransform: "none", letterSpacing: 0 }}>
              {newLines.length} lines
            </span>
          </div>
          <div style={{ padding: "8px 0" }}>
            {diffNew.map((entry, i) => (
              <div key={i} style={lineStyle(entry.status)}>
                <span style={{ color: "#484F58", fontSize: "11px",
                  minWidth: "32px", userSelect: "none",
                  paddingRight: "12px", textAlign: "right" }}>
                  {i + 1}
                </span>
                <span style={{ flex: 1, whiteSpace: "pre" }}>
                  {entry.status === "added" && (
                    <span style={{ color: "#00A651", marginRight: "6px" }}>+</span>
                  )}
                  {highlightIR(entry.line)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function computeImpactScore(changes: Change[]): number {
  let score = 0;
  let perfCount = 0;
  let warnCount = 0;
  let infoCount = 0;
  for (const c of changes) {
    if (c.severity === "perf" && perfCount < 2) { score += 25; perfCount++; }
    else if (c.severity === "warn" && warnCount < 2) { score += 15; warnCount++; }
    else if (c.severity === "info" && infoCount < 4) { score += 5;  infoCount++; }
  }
  return Math.min(score, 100);
}

function getScoreColor(score: number): string {
  if (score <= 20) return "#00A651";
  if (score <= 50) return "#F5A623";
  if (score <= 80) return "#E8620A";
  return "#D0021B";
}

function getScoreLabel(score: number): string {
  if (score <= 20) return "LOW";
  if (score <= 50) return "MEDIUM";
  if (score <= 80) return "HIGH";
  return "CRITICAL";
}

function ImpactScore({ changes }: { changes: Change[] }) {
  if (changes.length === 0) return null;

  const score = computeImpactScore(changes);
  const color = getScoreColor(score);
  const label = getScoreLabel(score);

  return (
    <div style={{
      margin: "14px 0",
      padding: "14px 16px",
      background: "#F5F7FA",
      border: `1.5px solid ${color}22`,
      borderRadius: "8px",
    }}>
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        marginBottom: "8px",
      }}>
        <span style={{
          fontSize: "11px",
          fontWeight: 700,
          letterSpacing: "0.8px",
          textTransform: "uppercase",
          color: "#5A6472",
        }}>
          Performance Impact Score
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{
            fontSize: "11px",
            fontWeight: 800,
            letterSpacing: "1px",
            textTransform: "uppercase",
            color: color,
            background: `${color}18`,
            border: `1px solid ${color}44`,
            padding: "2px 10px",
            borderRadius: "4px",
          }}>
            {label}
          </span>
          <span style={{
            fontSize: "24px",
            fontWeight: 800,
            color: color,
            lineHeight: 1,
          }}>
            {score}
            <span style={{ fontSize: "13px", fontWeight: 500,
              color: "#5A6472" }}>/100</span>
          </span>
        </div>
      </div>

      {/* Progress bar */}
      <div style={{
        height: "8px",
        background: "#E0E6ED",
        borderRadius: "4px",
        overflow: "hidden",
      }}>
        <div style={{
          height: "100%",
          width: `${score}%`,
          background: `linear-gradient(90deg, ${color}99, ${color})`,
          borderRadius: "4px",
          transition: "width 0.6s ease",
        }} />
      </div>

      {/* Breakdown */}
      <div style={{
        display: "flex",
        gap: "16px",
        marginTop: "8px",
        fontSize: "11px",
        color: "#5A6472",
      }}>
        {["perf", "warn", "info"].map((sev) => {
          const count = changes.filter(c => c.severity === sev).length;
          if (count === 0) return null;
          const sevColor = sev === "perf" ? "#0096D6"
            : sev === "warn" ? "#F5A623" : "#00A651";
          return (
            <span key={sev} style={{ display: "flex", alignItems: "center", gap: "4px" }}>
              <span style={{
                width: "8px", height: "8px",
                borderRadius: "2px",
                background: sevColor,
                display: "inline-block",
              }} />
              {count} {sev.toUpperCase()}
            </span>
          );
        })}
      </div>
    </div>
  );
}

function useAnimatedNumber(target: number, duration = 600): number {
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    if (target === 0) { setCurrent(0); return; }
    const start = performance.now();
    const startVal = 0;

    function step(now: number) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      setCurrent(Math.round(startVal + eased * (target - startVal)));
      if (progress < 1) requestAnimationFrame(step);
    }

    requestAnimationFrame(step);
  }, [target, duration]);

  return current;
}

async function exportToPDF(
  result: DiffResponse,
  oldLabel: string,
  newLabel: string
) {
  const { jsPDF } = await import("jspdf");
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });

  const pageW = 210;
  const pageH = 297;
  const margin = 16;
  const contentW = pageW - margin * 2;
  let y = 0;

  // ── Colors ────────────────────────────────────────────────────
  const HP_BLUE      = [0,   150, 214] as const;
  const HP_DARK_BLUE = [0,    48, 135] as const;
  const AMBER        = [245, 166,  35] as const;
  const GREEN        = [0,   166,  81] as const;
  const RED          = [208,   2,  27] as const;
  const LIGHT_GRAY   = [245, 247, 250] as const;
  const MID_GRAY     = [90,  100, 114] as const;
  const DARK         = [31,   31,  31] as const;

  function setColor(rgb: readonly [number,number,number], fill=true) {
    if (fill) doc.setFillColor(...rgb);
    else doc.setDrawColor(...rgb);
    doc.setTextColor(...rgb);
  }

  function addPageIfNeeded(needed = 20) {
    if (y + needed > pageH - 20) {
      doc.addPage();
      y = 20;
    }
  }

  // ── HP Header ─────────────────────────────────────────────────
  doc.setFillColor(...HP_DARK_BLUE);
  doc.rect(0, 0, pageW, 22, "F");
  doc.setFillColor(...HP_BLUE);
  doc.rect(0, 18, pageW, 4, "F");

  doc.setTextColor(255, 255, 255);
  doc.setFontSize(7);
  doc.setFont("helvetica", "bold");
  doc.text("HP ENTERPRISE  ·  COMPILER DESIGN", margin, 8);

  doc.setFontSize(13);
  doc.text("Semantic Diff Workbench", margin, 15);

  const dateStr = new Date().toLocaleDateString("en-US", {
    year: "numeric", month: "long", day: "numeric"
  });
  doc.setFontSize(7);
  doc.setFont("helvetica", "normal");
  doc.text(dateStr, pageW - margin, 8, { align: "right" });

  y = 30;

  // ── Title block ───────────────────────────────────────────────
  doc.setFontSize(14);
  doc.setFont("helvetica", "bold");
  setColor(HP_DARK_BLUE);
  doc.text("Semantic Diff Report", margin, y);
  y += 7;

  doc.setFontSize(8);
  doc.setFont("helvetica", "normal");
  setColor(MID_GRAY);
  doc.text(`Old: ${oldLabel}`, margin, y);
  y += 4.5;
  doc.text(`New: ${newLabel}`, margin, y);
  y += 8;

  // ── Summary table ─────────────────────────────────────────────
  const summary = result.report.summary;
  const summaryItems = [
    ["Total Functions", String(summary.total_functions)],
    ["Changed",         String(summary.changed)],
    ["Modified",        String(summary.modified)],
    ["Added",           String(summary.added)],
    ["Removed",         String(summary.removed)],
  ];

  doc.setFillColor(...LIGHT_GRAY);
  doc.rect(margin, y, contentW, 8, "F");
  doc.setFontSize(8);
  doc.setFont("helvetica", "bold");
  setColor(HP_DARK_BLUE);
  doc.text("SUMMARY", margin + 3, y + 5.5);
  y += 10;

  const colW = contentW / summaryItems.length;
  summaryItems.forEach(([label, val], i) => {
    const x = margin + i * colW;
    doc.setFillColor(255, 255, 255);
    doc.setDrawColor(...HP_BLUE);
    doc.setLineWidth(0.3);
    doc.rect(x, y, colW - 1, 14, "FD");

    doc.setFontSize(6);
    doc.setFont("helvetica", "normal");
    setColor(MID_GRAY);
    doc.text(label.toUpperCase(), x + 3, y + 5);

    doc.setFontSize(14);
    doc.setFont("helvetica", "bold");
    setColor(HP_DARK_BLUE);
    doc.text(val, x + 3, y + 12);
  });
  y += 20;

  // ── Functions ─────────────────────────────────────────────────
  for (const fn of result.report.functions) {
    if (fn.status === "unchanged") continue;
    addPageIfNeeded(30);

    // Function header bar
    const statusColor: readonly [number,number,number] =
      fn.status === "modified" ? AMBER :
      fn.status === "added"    ? GREEN : RED;

    doc.setFillColor(...HP_DARK_BLUE);
    doc.rect(margin, y, contentW, 9, "F");

    doc.setFontSize(9);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(255, 255, 255);
    doc.text(fn.new_name || fn.old_name, margin + 3, y + 6);

    // Status badge
    doc.setFillColor(...statusColor);
    doc.roundedRect(pageW - margin - 28, y + 1.5, 26, 6, 1, 1, "F");
    doc.setFontSize(6);
    doc.setFont("helvetica", "bold");
    doc.text(fn.status.toUpperCase(), pageW - margin - 15, y + 5.8, { align: "center" });

    y += 12;

    // Metrics row
    const metricItems = [
      ["Instr Delta",    String(fn.metrics.instr_delta >= 0
        ? `+${fn.metrics.instr_delta}` : fn.metrics.instr_delta)],
      ["Old Instrs",     String(fn.metrics.old_instr_count)],
      ["New Instrs",     String(fn.metrics.new_instr_count)],
      ["Critical Path",  String(fn.metrics.critical_path_delta >= 0
        ? `+${fn.metrics.critical_path_delta}` : fn.metrics.critical_path_delta)],
      ["Mem Deps Δ",     String(fn.metrics.new_mem_deps - fn.metrics.old_mem_deps)],
      ["Match",          `${Math.round(fn.match_confidence * 100)}%`],
    ];

    const mColW = contentW / metricItems.length;
    metricItems.forEach(([label, val], i) => {
      const x = margin + i * mColW;
      doc.setFillColor(...LIGHT_GRAY);
      doc.setDrawColor(...([216, 222, 233] as [number,number,number]));
      doc.setLineWidth(0.2);
      doc.rect(x, y, mColW - 0.5, 11, "FD");

      doc.setFontSize(5.5);
      doc.setFont("helvetica", "normal");
      setColor(MID_GRAY);
      doc.text(label.toUpperCase(), x + 2, y + 4);

      doc.setFontSize(9);
      doc.setFont("helvetica", "bold");
      setColor(DARK);
      doc.text(val, x + 2, y + 9.5);
    });
    y += 14;

    // Changes list
    for (const change of fn.changes) {
      addPageIfNeeded(14);

      const sevColor: readonly [number,number,number] =
        change.severity === "perf" ? HP_BLUE :
        change.severity === "warn" ? AMBER :
        change.severity === "info" ? GREEN  : RED;

      // Severity badge
      doc.setFillColor(...sevColor);
      doc.roundedRect(margin, y, 14, 5.5, 1, 1, "F");
      doc.setFontSize(5.5);
      doc.setFont("helvetica", "bold");
      doc.setTextColor(255, 255, 255);
      doc.text(change.severity.toUpperCase(), margin + 7, y + 4, { align: "center" });

      // Kind
      doc.setFontSize(8);
      doc.setFont("helvetica", "bold");
      setColor(DARK);
      doc.text(change.kind, margin + 16, y + 4);

      y += 7;

      // Description
      doc.setFontSize(7);
      doc.setFont("helvetica", "normal");
      setColor(MID_GRAY);
      const descLines = doc.splitTextToSize(change.description, contentW - 16);
      doc.text(descLines, margin + 16, y);
      y += descLines.length * 4;

      // Details
      if (change.details) {
        addPageIfNeeded(8);
        doc.setFontSize(6.5);
        doc.setFont("helvetica", "italic");
        setColor(HP_BLUE);
        const detailLines = doc.splitTextToSize(change.details, contentW - 16);
        doc.text(detailLines, margin + 16, y);
        y += detailLines.length * 3.5 + 2;
      }

      y += 2;
    }

    // Block diffs
    if (fn.block_diffs.length > 0) {
      addPageIfNeeded(10);
      doc.setFontSize(7);
      doc.setFont("helvetica", "bold");
      setColor(HP_DARK_BLUE);
      doc.text("Block-level changes:", margin, y);
      y += 5;

      for (const bd of fn.block_diffs) {
        addPageIfNeeded(7);
        const bdColor = bd.status === "added" ? GREEN
          : bd.status === "removed" ? RED : AMBER;
        const bdSymbol = bd.status === "added" ? "+"
          : bd.status === "removed" ? "−" : "~";
        const bdLabel = bd.new_label || bd.old_label || "?";
        const bdSim = bd.status === "matched"
          ? ` (${Math.round(bd.similarity * 100)}% similar)` : "";

        doc.setFontSize(7);
        doc.setFont("helvetica", "bold");
        setColor(bdColor);
        doc.text(`${bdSymbol} ${bdLabel}${bdSim}`, margin + 4, y);
        y += 4.5;

        if (bd.removed_instrs.length > 0) {
          doc.setFontSize(6);
          doc.setFont("helvetica", "normal");
          setColor(RED);
          doc.text(`  − ${bd.removed_instrs.slice(0,6).join(", ")}`, margin + 6, y);
          y += 3.5;
        }
        if (bd.added_instrs.length > 0) {
          doc.setFontSize(6);
          doc.setFont("helvetica", "normal");
          setColor(GREEN);
          doc.text(`  + ${bd.added_instrs.slice(0,6).join(", ")}`, margin + 6, y);
          y += 3.5;
        }
      }
    }

    y += 8;

    // Separator
    doc.setDrawColor(...HP_BLUE);
    doc.setLineWidth(0.3);
    doc.line(margin, y - 4, pageW - margin, y - 4);
  }

  // ── Footer on every page ──────────────────────────────────────
  const totalPages = doc.getNumberOfPages();
  for (let p = 1; p <= totalPages; p++) {
    doc.setPage(p);
    doc.setFillColor(...HP_DARK_BLUE);
    doc.rect(0, pageH - 10, pageW, 10, "F");
    doc.setFontSize(6);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(255, 255, 255);
    doc.text(
      "HP Inc.  ·  Semantic Diff for Compiler IR  ·  Compiler Design Project",
      pageW / 2, pageH - 4, { align: "center" }
    );
    doc.text(`Page ${p} / ${totalPages}`, pageW - margin, pageH - 4, { align: "right" });
  }

  // ── Save ──────────────────────────────────────────────────────
  const filename = `semantic-diff-${new Date().toISOString().slice(0,10)}.pdf`;
  doc.save(filename);
}

export function App() {
  const [examples, setExamples] = useState<Example[]>([]);
  const [selectedExampleId, setSelectedExampleId] = useState("");
  const [oldIr, setOldIr] = useState(fallbackOldIr);
  const [newIr, setNewIr] = useState(fallbackNewIr);
  const [showUnchanged, setShowUnchanged] = useState(false);
  const [result, setResult] = useState<DiffResponse | null>(null);
  const [benchmark, setBenchmark] = useState<BenchmarkResponse | null>(null);
  const [view, setView] = useState<"report" | "json" | "terminal">("report");
  const [loading, setLoading] = useState(false);
  const [benchLoading, setBenchLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/examples")
      .then((res) => res.json())
      .then((data: Example[]) => {
        setExamples(data);
        if (data.length > 0) {
          setSelectedExampleId(data[0].id);
          setOldIr(data[0].old_ir);
          setNewIr(data[0].new_ir);
        }
      })
      .catch(() => {
        setError("API is unavailable. Start the FastAPI server on port 8000.");
      });
  }, []);

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        if (!loading) runDiff();
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [loading, runDiff]);

  const selectedExample = useMemo(
    () => examples.find((item) => item.id === selectedExampleId),
    [examples, selectedExampleId]
  );

  async function runDiff() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/diff", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          old_ir: oldIr,
          new_ir: newIr,
          old_label: selectedExample ? `${selectedExample.id}:old` : "old.ll",
          new_label: selectedExample ? `${selectedExample.id}:new` : "new.ll",
          show_unchanged: showUnchanged
        })
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Diff failed");
      }
      setResult(payload);
      setView("report");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Diff failed");
    } finally {
      setLoading(false);
    }
  }

  async function runBenchmark() {
    setBenchLoading(true);
    setError("");
    try {
      const response = await fetch("/api/benchmark");
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Benchmark failed");
      }
      setBenchmark(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Benchmark failed");
    } finally {
      setBenchLoading(false);
    }
  }

  function loadExample(id: string) {
    const example = examples.find((item) => item.id === id);
    setSelectedExampleId(id);
    if (example) {
      setOldIr(example.old_ir);
      setNewIr(example.new_ir);
      setResult(null);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <div className="eyebrow">
            <GitCompareArrows size={16} aria-hidden="true" />
            HP Enterprise · Compiler Design
          </div>
          <h1>Semantic Diff Workbench</h1>
        </div>
        <div className="status-strip">
          <span className="hp-badge">HP</span>
          <span className="status-pill">
            <Server size={16} aria-hidden="true" />
            FastAPI
          </span>
          <span className="status-pill">
            <Code2 size={16} aria-hidden="true" />
            LLVM IR
          </span>
        </div>
      </header>

      {error ? (
        <div className="error-banner" role="alert">
          <TriangleAlert size={18} aria-hidden="true" />
          {error}
        </div>
      ) : null}

      <section className="workspace-grid">
        <aside className="side-panel" aria-label="Examples and benchmark">
          <div className="panel-header">
            <h2>Cases</h2>
            <Search size={17} aria-hidden="true" />
          </div>
          <select
            className="select"
            value={selectedExampleId}
            onChange={(event) => loadExample(event.target.value)}
            aria-label="Benchmark case"
          >
            {examples.map((example) => (
              <option key={example.id} value={example.id}>
                {example.project} / {example.id}
              </option>
            ))}
          </select>

          {selectedExample ? (
            <div className="case-summary">
              <strong>{selectedExample.project}</strong>
              <p>{selectedExample.commit_description}</p>
              <div className="kind-list">
                {selectedExample.expected_kinds.map((kind) => (
                  <span key={kind}>{kind}</span>
                ))}
              </div>
            </div>
          ) : null}

          <button className="secondary-action" onClick={runBenchmark} disabled={benchLoading}>
            {benchLoading ? (
              <Loader2 size={17} className="spin" aria-hidden="true" />
            ) : (
              <BarChart3 size={17} aria-hidden="true" />
            )}
            Run benchmark
          </button>

          {benchmark ? (
            <div className="benchmark">
              <div className="scoreline">
                <CheckCircle2 size={18} aria-hidden="true" />
                <strong>
                  {benchmark.summary.passed}/{benchmark.summary.total}
                </strong>
                <span>{Math.round(benchmark.summary.average_f1 * 100)}% F1</span>
              </div>
              <div className="benchmark-list">
                {benchmark.cases.map((item) => (
                  <div key={item.id} className="benchmark-row">
                    <span className={item.passed ? "dot ok" : "dot bad"} />
                    <span>{item.id}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </aside>

        <section className="editor-region" aria-label="IR input">
          <div className="editor-toolbar">
            <label className="toggle">
              <input
                type="checkbox"
                checked={showUnchanged}
                onChange={(event) => setShowUnchanged(event.target.checked)}
              />
              Show unchanged
            </label>
            <div className="actions">
              <button
                className="icon-button"
                type="button"
                onClick={() => {
                  setOldIr(fallbackOldIr);
                  setNewIr(fallbackNewIr);
                  setResult(null);
                }}
                title="Reset IR"
                aria-label="Reset IR"
              >
                <RotateCcw size={18} aria-hidden="true" />
              </button>
              <button
                className="primary-action"
                onClick={runDiff}
                disabled={loading}
                title="Run semantic diff (Ctrl+Enter)"
              >
                {loading ? (
                  <Loader2 size={18} className="spin" aria-hidden="true" />
                ) : (
                  <Play size={18} aria-hidden="true" />
                )}
                Run diff
                <span style={{
                  fontSize: "10px",
                  opacity: 0.7,
                  marginLeft: "4px",
                  fontWeight: 400,
                }}>
                  ⌘↵
                </span>
              </button>
            </div>
          </div>

          <DiffViewer
            oldIr={oldIr}
            newIr={newIr}
            onChange={(side, value) => {
              if (side === "old") setOldIr(value);
              else setNewIr(value);
              setResult(null);
            }}
          />
        </section>
      </section>

      <section className="results-region" aria-label="Semantic diff results">
        <div className="results-header">
          <div>
            <div className="eyebrow">
              <Activity size={16} aria-hidden="true" />
              Report
            </div>
            <h2>Semantic changes</h2>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            {result && (
              <button
                onClick={() => exportToPDF(
                  result,
                  selectedExample ? `${selectedExample.id}:old` : "old.ll",
                  selectedExample ? `${selectedExample.id}:new` : "new.ll",
                )}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  background: "#003087",
                  color: "#fff",
                  border: "none",
                  borderRadius: "8px",
                  padding: "9px 16px",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: "pointer",
                  transition: "background 0.15s",
                }}
                onMouseEnter={e => (e.currentTarget.style.background = "#0096D6")}
                onMouseLeave={e => (e.currentTarget.style.background = "#003087")}
                title="Export report as PDF"
              >
                ↓ Export PDF
              </button>
            )}
            <div className="tabs" role="tablist" aria-label="Result view">
              <button
                className={view === "report" ? "active" : ""}
                onClick={() => setView("report")}
              >
                Report
              </button>
              <button
                className={view === "json" ? "active" : ""}
                onClick={() => setView("json")}
              >
                JSON
              </button>
              <button
                className={view === "terminal" ? "active" : ""}
                onClick={() => setView("terminal")}
              >
                Text
              </button>
            </div>
          </div>
        </div>

        {result ? (
          <>
            <Summary summary={result.report.summary} />
            {view === "report" ? <Report functions={result.report.functions} /> : null}
            {view === "json" ? (
              <pre className="code-output">{JSON.stringify(result.report, null, 2)}</pre>
            ) : null}
            {view === "terminal" ? <pre className="code-output">{stripAnsi(result.text)}</pre> : null}
          </>
        ) : (
          <div className="empty-state">
            <Braces size={28} aria-hidden="true" />
            <span>No report yet</span>
          </div>
        )}
      </section>
      <footer className="hp-footer">
        <strong>HP Inc.</strong> · Semantic Diff for Compiler IR ·
        Compiler Design Project · Built with LLVM, FastAPI, React
      </footer>
    </main>
  );
}

function Summary({ summary }: { summary: DiffResponse["report"]["summary"] }) {
  return (
    <div className="summary-grid">
      <Metric label="Changed"  value={summary.changed}          animate />
      <Metric label="Modified" value={summary.modified}         animate />
      <Metric label="Added"    value={summary.added}            animate />
      <Metric label="Removed"  value={summary.removed}          animate />
      <Metric label="Total"    value={summary.total_functions}  animate />
    </div>
  );
}

function Metric({ label, value, animate = false }: {
  label: string;
  value: number;
  animate?: boolean;
}) {
  const displayed = animate ? useAnimatedNumber(value) : value;
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{displayed}</strong>
    </div>
  );
}

function Report({ functions }: { functions: FunctionReport[] }) {
  if (functions.length === 0) {
    return (
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: "12px",
        padding: "20px 24px",
        background: "#E6F7EE",
        border: "1.5px solid #00A651",
        borderRadius: "8px",
        color: "#00652F",
        fontSize: "14px",
        fontWeight: 600,
      }}>
        <span style={{ fontSize: "20px" }}>✓</span>
        No semantic changes detected — IR behavior is identical.
      </div>
    );
  }

  return (
    <div className="function-list">
      {functions.map((fn) => (
        <article key={`${fn.old_name}:${fn.new_name}`} className="function-item">
          <div className="function-heading">
            <div>
              <span className={`status ${fn.status}`}>{fn.status}</span>
              <h3>{fn.new_name || fn.old_name}</h3>
            </div>
            <span className="match">
              {fn.match_reason} / {Math.round(fn.match_confidence * 100)}%
            </span>
          </div>

          <div className="metrics-row">
            <Metric label="Instr delta" value={fn.metrics.instr_delta} />
            <Metric label="Old instrs" value={fn.metrics.old_instr_count} />
            <Metric label="New instrs" value={fn.metrics.new_instr_count} />
            <Metric label="Critical path" value={fn.metrics.critical_path_delta} />
            <Metric label="Mem deps" value={fn.metrics.new_mem_deps - fn.metrics.old_mem_deps} />
          </div>

          <ImpactScore changes={fn.changes} />

          <div className="change-list">
            {fn.changes.map((change) => (
              <div key={`${fn.new_name}-${change.kind}-${change.description}`} className="change-row">
                <span className={`severity ${change.severity}`}>{change.severity}</span>
                <div>
                  <strong>{change.kind}</strong>
                  <p>{change.description}</p>
                  {change.details ? <small>{change.details}</small> : null}
                </div>
              </div>
            ))}
          </div>

          {fn.block_diffs.length > 0 ? (
            <div className="block-list">
              {fn.block_diffs.map((block) => (
                <span key={`${block.old_label}:${block.new_label}:${block.similarity}`}>
                  {block.old_label || "new"} {"->"} {block.new_label || "removed"} (
                  {Math.round(block.similarity * 100)}%)
                </span>
              ))}
            </div>
          ) : null}

          <CFGGraph
            blockDiffs={fn.block_diffs}
            funcName={fn.new_name || fn.old_name}
          />
        </article>
      ))}
    </div>
  );
}

function stripAnsi(value: string) {
  return value.replace(/\u001b\[[0-9;]*m/g, "");
}
