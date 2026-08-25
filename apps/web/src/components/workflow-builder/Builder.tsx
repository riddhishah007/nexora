"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type Edge,
  type Node,
  Handle,
  Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Check, Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch, getToken, type Workflow } from "@/lib/api";
import { useWorkflowStream, type StepRunStatus } from "@/lib/useWorkflowStream";
import { cn } from "@/lib/utils";

type AgentType = "search-agent" | "rag-agent" | "pdf-agent" | "coding-agent" | "research-agent" | "data-agent" | "writer-agent";

const AGENTS: { id: AgentType; label: string; color: string; desc: string }[] = [
  { id: "search-agent", label: "Search", color: "bg-sky-500", desc: "web search + fetch" },
  { id: "rag-agent", label: "RAG", color: "bg-violet-500", desc: "pgvector grounded" },
  { id: "pdf-agent", label: "PDF", color: "bg-amber-500", desc: "parse + summarize" },
  { id: "coding-agent", label: "Code", color: "bg-emerald-500", desc: "generate + sandbox" },
  { id: "research-agent", label: "Research", color: "bg-orange-500", desc: "sub-questions + cross-check" },
  { id: "data-agent", label: "Data", color: "bg-cyan-500", desc: "CSV/Excel + trends" },
  { id: "writer-agent", label: "Writer", color: "bg-pink-500", desc: "report generation" },
];

type AgentNodeData = {
  agent_id: AgentType;
  instruction: string;
  label: string;
  runStatus?: StepRunStatus;
};

const RUN_STYLES: Record<Exclude<StepRunStatus, "pending">, { border: string; badge: string }> = {
  selected: { border: "border-amber-500/60", badge: "bg-amber-500/10 text-amber-600 dark:text-amber-400" },
  running: { border: "border-primary ring-2 ring-primary/30", badge: "bg-primary/10 text-primary" },
  done: { border: "border-emerald-500/60 bg-emerald-500/5", badge: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" },
  failed: { border: "border-destructive/70 bg-destructive/5", badge: "bg-destructive/10 text-destructive" },
};

function AgentNode({ data, selected }: { data: AgentNodeData; selected?: boolean }) {
  const agent = AGENTS.find((a) => a.id === data.agent_id) || AGENTS[0];
  const st = data.runStatus && data.runStatus !== "pending" ? RUN_STYLES[data.runStatus] : null;
  return (
    <div
      className={cn(
        "min-w-[180px] rounded-lg border bg-card px-3 py-2 shadow-sm transition-colors",
        st ? st.border : selected ? "border-primary ring-1 ring-primary/30" : "border-border"
      )}
    >
      <Handle type="target" position={Position.Top} className="!bg-muted-foreground" />
      <div className="flex items-center gap-2">
        <span className={cn("h-2 w-2 rounded-full", agent.color)} />
        <span className="font-mono text-xs font-medium">{data.label || agent.label}</span>
        {data.runStatus === "running" && <Loader2 className="h-3 w-3 shrink-0 animate-spin text-primary" />}
        {data.runStatus === "done" && <Check className="h-3 w-3 shrink-0 text-emerald-500" />}
        {data.runStatus === "failed" && <X className="h-3 w-3 shrink-0 text-destructive" />}
        <span className="ml-auto rounded bg-muted px-1 py-0.5 font-mono text-[10px]">{data.agent_id}</span>
      </div>
      <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{data.instruction || "— no instruction —"}</p>
      {st && (
        <span className={cn("mt-1 inline-block rounded px-1 py-0.5 font-mono text-[10px]", st.badge)}>{data.runStatus}</span>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-muted-foreground" />
    </div>
  );
}

const nodeTypes = { agent: AgentNode };

export function Builder() {
  const router = useRouter();
  const params = useSearchParams();
  const templateId = params.get("template");
  const workflowId = params.get("workflow");

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [name, setName] = React.useState("My Workflow");
  const [saving, setSaving] = React.useState(false);
  const [executing, setExecuting] = React.useState(false);
  const [message, setMessage] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<Workflow | null>(null);
  const [runWfId, setRunWfId] = React.useState<string | null>(null);
  const seqToNodeRef = React.useRef<Record<number, string>>({});
  const firedForRef = React.useRef<string | null>(null);

  const stream = useWorkflowStream(runWfId, executing);

  // paint live per-step status onto nodes
  React.useEffect(() => {
    setNodes((nds) =>
      nds.map((n) => {
        const seq = Number(Object.entries(seqToNodeRef.current).find(([, id]) => id === n.id)?.[0]);
        const st = seq !== undefined && Number.isFinite(seq) ? stream.stepStatus[seq] : undefined;
        const current = (n.data as AgentNodeData).runStatus;
        if (st === current) return n;
        return { ...n, data: { ...n.data, runStatus: st } };
      })
    );
  }, [stream.stepStatus, setNodes]);

  const selectedNode = React.useMemo(() => nodes.find((n) => n.id === selectedId), [nodes, selectedId]);

  // auth guard
  React.useEffect(() => {
    if (!getToken()) router.push("/login");
  }, [router]);

  // load template or existing workflow
  React.useEffect(() => {
    if (workflowId) {
      apiFetch<Workflow>(`/workflows/${workflowId}`)
        .then((wf) => {
          setName(wf.name);
          if (wf.definition && typeof wf.definition === "object" && "nodes" in (wf.definition as Record<string, unknown>)) {
            const def = wf.definition as { nodes: Node[]; edges: Edge[] };
            setNodes(def.nodes as Node[]);
            setEdges(def.edges as Edge[]);
          } else {
            // fallback: reconstruct from steps
            const nds: Node[] = wf.steps.map((s, idx) => ({
              id: `node-${idx}`,
              type: "agent",
              position: { x: 80 + (idx % 3) * 220, y: 80 + Math.floor(idx / 3) * 140 },
              data: { agent_id: s.agent_id as AgentType, instruction: s.instruction, label: AGENTS.find((a) => a.id === s.agent_id)?.label || s.agent_id },
            }));
            const eds: Edge[] = wf.steps.flatMap((s) =>
              (s.depends_on || []).map((dep) => ({
                id: `edge-${dep}-${s.seq}`,
                source: `node-${dep}`,
                target: `node-${s.seq}`,
                animated: true,
              }))
            );
            setNodes(nds);
            setEdges(eds);
          }
        })
        .catch((e) => setError(e instanceof Error ? e.message : String(e)));
      return;
    }
    if (templateId) {
      apiFetch<{ steps: { agent_id: string; instruction: string; depends_on: number[] }[] }[]>("/workflows/templates")
        .then((all) => {
          const tmpl = (all as unknown as { id: string; steps: { agent_id: string; instruction: string; depends_on: number[] }[] }[]).find((t) => t.id === templateId);
          if (!tmpl) return;
          const nds: Node[] = tmpl.steps.map((s, idx) => ({
            id: `node-${idx}`,
            type: "agent",
            position: { x: 80 + idx * 220, y: 120 },
            data: { agent_id: s.agent_id as AgentType, instruction: s.instruction, label: AGENTS.find((a) => a.id === s.agent_id)?.label || s.agent_id },
          }));
          const eds: Edge[] = tmpl.steps.flatMap((s) =>
            (s.depends_on || []).map((dep) => ({
              id: `edge-${dep}-${nds.findIndex((_, i) => i === s.depends_on[0])}`,
              source: `node-${dep}`,
              target: `node-${tmpl.steps.indexOf(s)}`,
              animated: true,
            }))
          );
          // fix edges for template (depends_on is seq)
          const fixedEds: Edge[] = tmpl.steps.flatMap((s, idx) =>
            (s.depends_on || []).map((dep) => ({
              id: `edge-${dep}-${idx}`,
              source: `node-${dep}`,
              target: `node-${idx}`,
              animated: true,
            }))
          );
          setNodes(nds);
          setEdges(fixedEds);
          const tmplName = (tmpl as unknown as { name: string }).name;
          if (tmplName) setName(tmplName);
        })
        .catch(() => {});
    }
  }, [templateId, workflowId, setNodes, setEdges]);

  const onConnect = React.useCallback((params: Connection) => setEdges((eds) => addEdge({ ...params, animated: true }, eds)), [setEdges]);

  const onDragStart = (event: React.DragEvent, agentId: AgentType) => {
    event.dataTransfer.setData("application/reactflow", agentId);
    event.dataTransfer.effectAllowed = "move";
  };

  const onDrop = React.useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const agentId = event.dataTransfer.getData("application/reactflow") as AgentType;
      if (!agentId) return;
      const bounds = (event.target as HTMLElement).getBoundingClientRect();
      const position = { x: event.clientX - bounds.left - 90, y: event.clientY - bounds.top - 40 };
      const id = `node-${Date.now()}`;
      const agent = AGENTS.find((a) => a.id === agentId)!;
      const newNode: Node = {
        id,
        type: "agent",
        position,
        data: { agent_id: agentId, instruction: "", label: agent.label },
      };
      setNodes((nds) => [...nds, newNode]);
    },
    [setNodes]
  );

  const onDragOver = React.useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  function updateSelectedInstruction(value: string) {
    if (!selectedId) return;
    setNodes((nds) =>
      nds.map((n) => (n.id === selectedId ? { ...n, data: { ...n.data, instruction: value } } : n))
    );
  }

  function updateSelectedAgent(agentId: AgentType) {
    if (!selectedId) return;
    const agent = AGENTS.find((a) => a.id === agentId)!;
    setNodes((nds) =>
      nds.map((n) => (n.id === selectedId ? { ...n, data: { ...n.data, agent_id: agentId, label: agent.label } } : n))
    );
  }

  // Convert nodes/edges to steps for API
  function toSteps() {
    // assign seq by topological order - simple: sort by y then x
    const sorted = [...nodes].sort((a, b) => a.position.y - b.position.y || a.position.x - b.position.x);
    const idToSeq = new Map<string, number>();
    sorted.forEach((n, idx) => idToSeq.set(n.id, idx));
    const steps = sorted.map((n, idx) => {
      const incoming = edges.filter((e) => e.target === n.id).map((e) => idToSeq.get(e.source)!).filter((v) => v !== undefined);
      return {
        agent_id: (n.data as { agent_id: string }).agent_id,
        instruction: (n.data as { instruction: string }).instruction || `Step ${idx} via ${ (n.data as { agent_id: string }).agent_id}`,
        depends_on: incoming.sort((a, b) => a - b),
      };
    });
    return { steps, sorted, idToSeq };
  }

  async function onSave() {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      if (nodes.length === 0) throw new Error("Add at least one agent node");
      const { steps } = toSteps();
      // validate instructions
      for (let i = 0; i < steps.length; i++) {
        if (!steps[i].instruction.trim()) throw new Error(`Step ${i} instruction is empty`);
      }
      const payload = { name, steps, definition: { nodes, edges } };
      if (workflowId) {
        // For MVP, create new workflow even when editing (simpler than PATCH)
        const res = await apiFetch<{ id: string }>("/workflows", { method: "POST", body: JSON.stringify(payload) });
        setMessage(`Saved as new workflow ${res.id.slice(0, 8)}`);
        router.push(`/workflows/builder?workflow=${res.id}`);
      } else {
        const res = await apiFetch<{ id: string }>("/workflows", { method: "POST", body: JSON.stringify(payload) });
        setMessage(`Saved workflow ${res.id.slice(0, 8)}`);
        router.push(`/workflows/builder?workflow=${res.id}`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  function fireExecute(wfId: string) {
    apiFetch<Workflow>(`/workflows/${wfId}/execute`, { method: "POST" })
      .then((res) => {
        setResult(res);
        setMessage(`Executed ${wfId.slice(0, 8)}: ${res.status} — ${res.steps.filter((s) => s.status === "done").length}/${res.steps.length} steps done`);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setExecuting(false));
  }

  // once the live stream is connected, kick off the actual run
  React.useEffect(() => {
    if (!stream.connected || !runWfId || firedForRef.current === runWfId) return;
    firedForRef.current = runWfId;
    setMessage(`Live — executing workflow ${runWfId.slice(0, 8)}`);
    fireExecute(runWfId);
  }, [stream.connected, runWfId]);

  // fallback: if the stream never connects, run anyway after 3s
  React.useEffect(() => {
    if (!executing || !runWfId || firedForRef.current === runWfId) return;
    const t = setTimeout(() => {
      if (firedForRef.current !== runWfId) {
        firedForRef.current = runWfId;
        fireExecute(runWfId);
      }
    }, 3000);
    return () => clearTimeout(t);
  }, [executing, runWfId]);

  // when the stream signals completion, pull the final persisted result
  React.useEffect(() => {
    if (!stream.finalReady || !runWfId) return;
    apiFetch<Workflow>(`/workflows/${runWfId}`)
      .then((res) => setResult(res))
      .catch(() => {});
  }, [stream.finalReady, runWfId]);

  async function onExecute() {
    if (nodes.length === 0) {
      setError("Add at least one agent node");
      return;
    }
    for (const n of nodes) {
      if (!(String((n.data as AgentNodeData).instruction || "").trim())) {
        setError("Every node needs an instruction before running");
        return;
      }
    }
    setError(null);
    setMessage(null);
    setResult(null);
    setExecuting(true);
    try {
      // Run = save a fresh workflow, then stream its execution live.
      // seq mapping comes from the same topological order used in the payload.
      const { steps, sorted } = toSteps();
      const payload = { name, steps, definition: { nodes, edges } };
      const created = await apiFetch<{ id: string }>("/workflows", { method: "POST", body: JSON.stringify(payload) });
      const map: Record<number, string> = {};
      sorted.forEach((n, idx) => {
        map[idx] = n.id;
      });
      seqToNodeRef.current = map;
      // reset node statuses
      setNodes((nds) => nds.map((n) => ({ ...n, data: { ...n.data, runStatus: undefined } })));
      firedForRef.current = null;
      setRunWfId(created.id);
      setMessage(`Connecting to live stream… (${created.id.slice(0, 8)})`);
    } catch (e) {
      setExecuting(false);
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex items-center gap-3 border-b border-border bg-card/50 px-4 py-2">
        <Input value={name} onChange={(e) => setName(e.target.value)} className="max-w-xs" placeholder="Workflow name" />
        <span className="font-mono text-xs text-muted-foreground">{nodes.length} nodes · {edges.length} edges</span>
        <div className="ml-auto flex items-center gap-2">
          {executing && (
            <span className="flex items-center gap-1.5 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
              <span className={cn("h-1.5 w-1.5 rounded-full", stream.connected ? "animate-pulse bg-emerald-500" : "bg-muted-foreground")} />
              {stream.connected ? "LIVE" : "CONNECTING"}
              {stream.workflowStatus && <span className="font-mono">· {stream.workflowStatus}</span>}
            </span>
          )}
          <Button variant="outline" size="sm" onClick={onSave} disabled={saving || executing}>
            {saving ? "Saving…" : "Save"}
          </Button>
          <Button size="sm" onClick={onExecute} disabled={executing}>
            {executing ? "Running…" : "Run"}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => { setNodes([]); setEdges([]); setResult(null); setMessage(null); setError(null); setExecuting(false); setRunWfId(null); seqToNodeRef.current = {}; firedForRef.current = null; }}>
            Clear
          </Button>
        </div>
      </header>

      {message && <div className="border-b border-emerald-500/20 bg-emerald-500/10 px-4 py-1 text-xs text-emerald-700 dark:text-emerald-400">{message}</div>}
      {error && <div className="border-b border-destructive/30 bg-destructive/10 px-4 py-1 text-xs text-destructive">{error}</div>}

      <div className="flex flex-1 overflow-hidden">
        {/* Palette */}
        <aside className="w-56 shrink-0 overflow-y-auto border-r border-border bg-card/30 p-3">
          <p className="mb-2 text-xs font-medium">Agents</p>
          <div className="flex flex-col gap-2">
            {AGENTS.map((a) => (
              <div
                key={a.id}
                draggable
                onDragStart={(e) => onDragStart(e, a.id)}
                className="cursor-grab rounded-md border border-border bg-background p-2 text-xs hover:border-primary/40 active:cursor-grabbing"
              >
                <div className="flex items-center gap-2">
                  <span className={`h-2 w-2 rounded-full ${a.color}`} />
                  <span className="font-medium">{a.label}</span>
                </div>
                <p className="mt-1 text-[11px] text-muted-foreground">{a.desc}</p>
                <p className="font-mono text-[10px] text-muted-foreground/70">{a.id}</p>
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs font-medium">Tips</p>
          <ul className="mt-1 list-disc pl-4 text-xs text-muted-foreground">
            <li>Drag agents onto canvas</li>
            <li>Connect handles to set dependencies</li>
            <li>Select a node to edit instruction</li>
            <li>Save before Run</li>
          </ul>
        </aside>

        {/* Canvas */}
        <div className="flex-1" onDrop={onDrop} onDragOver={onDragOver}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_, node) => setSelectedId(node.id)}
            onPaneClick={() => setSelectedId(null)}
            nodeTypes={nodeTypes}
            fitView
            className="bg-background"
          >
            <Background gap={16} />
            <Controls />
            <MiniMap className="!bg-card" />
          </ReactFlow>
        </div>

        {/* Inspector */}
        <aside className="w-72 shrink-0 overflow-y-auto border-l border-border bg-card/30 p-3">
          <p className="mb-2 text-xs font-medium">Inspector</p>
          {!selectedNode ? (
            <p className="text-xs text-muted-foreground">Select a node to edit its instruction.</p>
          ) : (
            <div className="flex flex-col gap-3">
              <div>
                <label className="text-xs font-medium">Agent</label>
                <select
                  value={(selectedNode.data as { agent_id: string }).agent_id}
                  onChange={(e) => updateSelectedAgent(e.target.value as AgentType)}
                  className="mt-1 w-full rounded-md border border-input bg-background px-2 py-1.5 text-xs"
                >
                  {AGENTS.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.label} — {a.id}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium">Instruction</label>
                <textarea
                  value={(selectedNode.data as { instruction: string }).instruction}
                  onChange={(e) => updateSelectedInstruction(e.target.value)}
                  placeholder="What should this agent do?"
                  rows={6}
                  className="mt-1 w-full rounded-md border border-input bg-background px-2 py-1.5 text-xs"
                />
              </div>
              <Button variant="outline" size="sm" onClick={() => setNodes((nds) => nds.filter((n) => n.id !== selectedId))}>
                Remove node
              </Button>
              <p className="font-mono text-xs text-muted-foreground">id: {selectedNode.id}</p>
            </div>
          )}

          {(executing || stream.events.length > 0) && (
            <div className="mt-4">
              <p className="flex items-center gap-1.5 text-xs font-medium">
                <span
                  className={cn(
                    "h-1.5 w-1.5 rounded-full",
                    stream.connected ? "animate-pulse bg-emerald-500" : executing ? "bg-amber-500" : "bg-muted-foreground"
                  )}
                />
                Live activity
                {stream.error && <span className="ml-auto font-mono text-[10px] text-muted-foreground">{stream.error}</span>}
              </p>
              <ul className="mt-1 max-h-44 space-y-0.5 overflow-y-auto font-mono text-[10px] text-muted-foreground">
                {[...stream.events]
                  .reverse()
                  .slice(0, 30)
                  .map((ev, i) => (
                    <li key={`${i}-${ev.type}`} className="truncate">
                      <span className="text-primary/70">{ev.type}</span>
                      {typeof ev.data?.seq === "number" && ` #${ev.data.seq}`}
                      {typeof ev.data?.agent_id === "string" && ` ${ev.data.agent_id}`}
                      {typeof ev.data?.status === "string" && ` → ${ev.data.status}`}
                    </li>
                  ))}
              </ul>
            </div>
          )}

          {result && (
            <Card className="mt-4">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs">Last run: {result.status}</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                {result.steps.map((s) => (
                  <div key={s.seq} className={`rounded border p-2 text-xs ${s.status === "done" ? "border-emerald-500/30 bg-emerald-500/5" : s.status === "failed" ? "border-destructive/30 bg-destructive/5" : "border-border"}`}>
                    <p className="font-mono font-medium">
                      {s.seq}: {s.agent_id} — {s.status}
                    </p>
                    <p className="mt-1 line-clamp-3 text-muted-foreground">{String(s.output?.answer || JSON.stringify(s.output) || "").slice(0, 180)}</p>
                  </div>
                ))}
                {result.definition && typeof result.definition === "object" && "synthesis" in (result.definition as Record<string, unknown>) && (
                  <div className="rounded bg-primary/5 p-2 text-xs">
                    <p className="font-medium">Synthesis</p>
                    <p className="mt-1 text-muted-foreground">{String((result.definition as { synthesis: string }).synthesis).slice(0, 400)}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </aside>
      </div>
    </div>
  );
}
