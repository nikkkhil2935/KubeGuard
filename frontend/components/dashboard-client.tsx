"use client";

import clsx from "clsx";
import {
  Activity,
  AlertTriangle,
  Bell,
  Gauge,
  HeartPulse,
  PlugZap,
  RefreshCw,
  Rocket,
  Search,
  SendHorizontal,
  ShieldAlert,
  ShieldCheck,
  Slack,
  Wifi,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";import { io, Socket } from "socket.io-client";import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { IntegrationsStatus, Pod, PodHealth, SummaryPayload } from "@/lib/types";

type TimelineKind = "info" | "good" | "warning" | "critical";

type TimelineEntry = {
  id: string;
  kind: TimelineKind;
  message: string;
  time: string;
};

type HistoryPoint = {
  timeLabel: string;
  requestRate: number;
  restarts: number;
  crashes: number;
  alerts: number;
};

const MAX_TIMELINE = 120;
const MAX_HISTORY = 50;

function getPodHealth(pod: Pod): PodHealth {
  if (pod.reason) {
    return "failed";
  }

  if (pod.ready) {
    return "healthy";
  }

  return "degraded";
}

function podStateLabel(pod: Pod): string {
  if (pod.reason) {
    return pod.reason;
  }

  if (pod.ready) {
    return "Running";
  }

  return pod.phase;
}

function shortPodName(name: string): string {
  if (name.length <= 22) {
    return name;
  }

  return `${name.slice(0, 14)}...${name.slice(-6)}`;
}

function buildSocketIoUrl(): string {
  if (typeof window === "undefined") {
    return "";
  }

  // Check for explicit WebSocket URL (recommended for production)
  const explicit = process.env.NEXT_PUBLIC_KG_WS_URL;
  if (explicit) {
    return explicit;
  }

  // Fallback: build URL from current host and configured port
  const protocol = window.location.protocol === "https:" ? "https" : "http";    
  const host = window.location.hostname || "localhost";
  const port = process.env.NEXT_PUBLIC_KG_WS_PORT || "9001";
  return `${protocol}://${host}:${port}`;
}

function createId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function DashboardClient() {
  const [payload, setPayload] = useState<SummaryPayload | null>(null);
  const [integrations, setIntegrations] = useState<IntegrationsStatus | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [wsState, setWsState] = useState<"connecting" | "connected" | "disconnected">("connecting");
  const [searchTerm, setSearchTerm] = useState("");
  const [podFilter, setPodFilter] = useState<"all" | PodHealth>("all");
  const [lastUpdate, setLastUpdate] = useState<string>("--");
  const [actionLoading, setActionLoading] = useState<"crash" | "discord" | "slack" | null>(null);
  const [errorBanner, setErrorBanner] = useState<string>("");

  const previousPodsRef = useRef<Map<string, Pod>>(new Map());
  const initializedRef = useRef(false);
  const socketRef = useRef<Socket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const latestErrorAtRef = useRef<number>(0);

  const addTimeline = useCallback((kind: TimelineKind, message: string) => {
    const entry: TimelineEntry = {
      id: createId(),
      kind,
      message,
      time: new Date().toLocaleTimeString(),
    };

    setTimeline((previous) => [entry, ...previous].slice(0, MAX_TIMELINE));
  }, []);

  const ingestPayload = useCallback(
    (incoming: SummaryPayload, source: "poll" | "socket") => {
      setPayload(incoming);
      setLastUpdate(new Date(incoming.summary.timestamp).toLocaleTimeString());

      setHistory((previous) => {
        const timeLabel = new Date(incoming.summary.timestamp).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });

        const nextPoint: HistoryPoint = {
          timeLabel,
          requestRate: incoming.summary.request_rate_min,
          restarts: incoming.summary.restarts,
          crashes: incoming.summary.crash_counter,
          alerts: incoming.summary.alerts_firing,
        };

        return [...previous, nextPoint].slice(-MAX_HISTORY);
      });

      const currentPods = new Map(incoming.pods.map((pod) => [pod.name, pod]));

      if (!initializedRef.current) {
        previousPodsRef.current = currentPods;
        initializedRef.current = true;
        if (source === "socket") {
          addTimeline("good", "Realtime socket stream established.");
        }
        return;
      }

      incoming.pods.forEach((pod) => {
        const oldPod = previousPodsRef.current.get(pod.name);
        if (!oldPod) {
          addTimeline("info", `Pod discovered: ${pod.name}`);
          return;
        }

        if ((oldPod.reason || "") !== (pod.reason || "")) {
          if (pod.reason) {
            addTimeline("critical", `Crash detected: ${pod.name} (${pod.reason})`);
          } else {
            addTimeline("good", `Recovery detected: ${pod.name}`);
          }
        }

        if (oldPod.restarts !== pod.restarts && pod.restarts > oldPod.restarts) {
          addTimeline("warning", `Restart count changed: ${pod.name} (${oldPod.restarts} -> ${pod.restarts})`);
        }
      });

      previousPodsRef.current.forEach((_, podName) => {
        if (!currentPods.has(podName)) {
          addTimeline("warning", `Pod removed from fleet: ${podName}`);
        }
      });

      previousPodsRef.current = currentPods;
    },
    [addTimeline],
  );

  const refreshSummary = useCallback(async () => {
    try {
      const response = await fetch("/api/summary", { cache: "no-store" });
      const data = (await response.json()) as SummaryPayload | { detail?: string; error?: string };

      if (!response.ok) {
        const errorText = "detail" in data && data.detail ? data.detail : "error" in data && data.error ? data.error : "Summary request failed";
        throw new Error(errorText);
      }

      ingestPayload(data as SummaryPayload, "poll");
      setErrorBanner("");
    } catch (error) {
      const now = Date.now();
      if (now - latestErrorAtRef.current > 12000) {
        addTimeline("warning", `Summary polling issue: ${error instanceof Error ? error.message : String(error)}`);
        latestErrorAtRef.current = now;
      }
      setErrorBanner("Backend data stream degraded. Retrying automatically.");
    }
  }, [addTimeline, ingestPayload]);

  const refreshIntegrations = useCallback(async () => {
    try {
      const response = await fetch("/api/status", { cache: "no-store" });
      const data = (await response.json()) as IntegrationsStatus;
      if (!response.ok) {
        throw new Error("Integration status unavailable");
      }
      setIntegrations(data);
    } catch {
      // Keep latest status on intermittent failures.
    }
  }, []);

  const executeAction = useCallback(
    async (action: "crash" | "discord" | "slack") => {
      const endpointMap = {
        crash: "/api/trigger-crash",
        discord: "/api/test-discord",
        slack: "/api/test-slack",
      } as const;

      const labelMap = {
        crash: "Crash action",
        discord: "Discord test",
        slack: "Slack test",
      } as const;

      setActionLoading(action);
      try {
        const response = await fetch(endpointMap[action], { method: "POST" });
        const data = (await response.json()) as { message?: string; detail?: string; error?: string };

        if (!response.ok) {
          const reason = data.detail || data.error || `${labelMap[action]} failed`;
          throw new Error(reason);
        }

        addTimeline("good", data.message || `${labelMap[action]} completed.`);
      } catch (error) {
        addTimeline("critical", `${labelMap[action]} failed: ${error instanceof Error ? error.message : String(error)}`);
      } finally {
        setActionLoading(null);
      }
    },
    [addTimeline],
  );

  useEffect(() => {
    void refreshSummary();
    void refreshIntegrations();

    const summaryTimer = window.setInterval(() => {
      void refreshSummary();
    }, 7000);

    const statusTimer = window.setInterval(() => {
      void refreshIntegrations();
    }, 15000);

    return () => {
      window.clearInterval(summaryTimer);
      window.clearInterval(statusTimer);
    };
  }, [refreshIntegrations, refreshSummary]);

  useEffect(() => {
    let disposed = false;    const connect = () => {
      if (disposed) {
        return;
      }

      setWsState("connecting");
      const socket = io(buildSocketIoUrl(), {
        reconnectionDelay: 1000,
        reconnectionDelayMax: 12000,
      });
      socketRef.current = socket;

      socket.on("connect", () => {
        if (disposed) {
          socket.disconnect();
          return;
        }
        reconnectAttemptsRef.current = 0;
        setWsState("connected");
      });

      socket.on("metrics", (data: SummaryPayload) => {
        try {
          ingestPayload(data, "socket");
        } catch {
        }
      });

      socket.on("log", (data: { level: TimelineKind, message: string }) => {
        addTimeline(data.level, data.message);
      });

      socket.on("disconnect", () => {
        if (disposed) {
          return;
        }
        setWsState("disconnected");
      });
    };

    connect();

    return () => {
      disposed = true;
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
    };
  }, [ingestPayload]);

  const pods = useMemo(() => payload?.pods ?? [], [payload]);
  const summary = payload?.summary;

  const filteredPods = useMemo(() => {
    return pods.filter((pod) => {
      const health = getPodHealth(pod);
      const filterMatch = podFilter === "all" || health === podFilter;
      const searchMatch = pod.name.toLowerCase().includes(searchTerm.toLowerCase());
      return filterMatch && searchMatch;
    });
  }, [podFilter, pods, searchTerm]);

  const restartLeaderboard = useMemo(() => {
    return [...pods]
      .sort((a, b) => b.restarts - a.restarts)
      .slice(0, 8)
      .map((pod) => ({
        name: shortPodName(pod.name),
        restarts: pod.restarts,
      }));
  }, [pods]);

  const serviceBreakdown = useMemo(() => {
    const serviceMap = new Map<string, number>();
    for (const pod of pods) {
      const key = pod.service || "unknown";
      serviceMap.set(key, (serviceMap.get(key) || 0) + 1);
    }

    return Array.from(serviceMap.entries())
      .map(([service, count]) => ({ service, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [pods]);

  const availability = summary && summary.total > 0 ? Math.round((summary.running / summary.total) * 100) : 0;
  const failedPods = pods.filter((pod) => getPodHealth(pod) === "failed").length;

  const wsClassName = clsx("kg-pill", {
    "kg-pill-good": wsState === "connected",
    "kg-pill-warning": wsState === "connecting",
    "kg-pill-bad": wsState === "disconnected",
  });

  const kpis = [
    {
      label: "Availability",
      value: `${availability}%`,
      hint: `${summary?.running ?? 0}/${summary?.total ?? 0} pods healthy`,
      icon: HeartPulse,
      tone: availability >= 95 ? "good" : availability >= 80 ? "warning" : "bad",
    },
    {
      label: "Request Rate",
      value: `${(summary?.request_rate_min || 0).toFixed(1)}`,
      hint: "requests / minute",
      icon: Activity,
      tone: "neutral",
    },
    {
      label: "Crash Counter",
      value: `${Math.round(summary?.crash_counter || 0)}`,
      hint: `${failedPods} pods currently failed`,
      icon: ShieldAlert,
      tone: failedPods > 0 ? "bad" : "good",
    },
    {
      label: "Restarts",
      value: `${Math.round(summary?.restarts || 0)}`,
      hint: "fleet cumulative restarts",
      icon: RefreshCw,
      tone: summary && summary.restarts > 5 ? "warning" : "neutral",
    },
    {
      label: "Firing Alerts",
      value: `${Math.round(summary?.alerts_firing || 0)}`,
      hint: "active Prometheus rules",
      icon: Bell,
      tone: summary && summary.alerts_firing > 0 ? "warning" : "good",
    },
    {
      label: "Pod Fleet",
      value: `${summary?.total || 0}`,
      hint: "pods under observation",
      icon: Gauge,
      tone: "neutral",
    },
  ] as const;

  return (
    <div className="kg-page">
      <div className="kg-shell">
        <header className="kg-header">
          <div>
            <p className="kg-kicker">KUBEGUARD NEXT FRONTEND</p>
            <h1 className="kg-title">Command Center</h1>
            <p className="kg-subtitle">
              Advanced light-theme control plane for pod health, alert channels, and self-healing telemetry.
            </p>
          </div>
          <div className="kg-header-meta">
            <span className={wsClassName}>
              <Wifi size={14} strokeWidth={1.5} />
              WebSocket: {wsState}
            </span>
            <span className="kg-pill kg-pill-neutral">Last update: {lastUpdate}</span>
            <span className="kg-pill kg-pill-neutral">Namespace: kubeguard</span>
          </div>
        </header>

        {errorBanner && <div className="kg-banner">{errorBanner}</div>}

        <main className="kg-layout">
          <section className="kg-main">
            <article className="kg-panel">
              <div className="kg-panel-head">
                <h2>Realtime Health Overview</h2>
                <p>Live metrics from Prometheus and Kubernetes control loops.</p>
              </div>
              <div className="kg-kpi-grid">
                {kpis.map((kpi, index) => (
                  <div key={kpi.label} className={clsx("kg-kpi", `kg-kpi-${kpi.tone}`)} style={{ animationDelay: `${index * 80}ms` }}>
                    <div className="kg-kpi-top">
                      <span className="kg-kpi-label">{kpi.label}</span>
                      <kpi.icon size={16} strokeWidth={1.5} />
                    </div>
                    <p className="kg-kpi-value">{kpi.value}</p>
                    <span className="kg-kpi-hint">{kpi.hint}</span>
                  </div>
                ))}
              </div>
            </article>

            <article className="kg-panel">
              <div className="kg-panel-head">
                <h2>Traffic and Failure Trends</h2>
                <p>Track request pressure and restart hotspots.</p>
              </div>
              <div className="kg-chart-grid">
                <div className="kg-chart-card">
                  <h3>Request Rate Timeline</h3>
                  <ResponsiveContainer width="100%" height={240}>
                    <LineChart data={history}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(15, 23, 42, 0.08)" />
                        <XAxis dataKey="timeLabel" tick={{ fontSize: 11 }} />
                        <YAxis tick={{ fontSize: 11 }} />
                        <Tooltip />
                        <Line type="monotone" dataKey="requestRate" stroke="#4F46E5" strokeWidth={2.5} dot={false} />
                        <Line type="monotone" dataKey="alerts" stroke="#EF4444" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                <div className="kg-chart-card">
                  <h3>Top Restarting Pods</h3>
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={restartLeaderboard}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(15, 23, 42, 0.08)" />
                      <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Bar dataKey="restarts" fill="#4F46E5" radius={[6, 6, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </article>

            <article className="kg-panel">
              <div className="kg-panel-head">
                <h2>Pod Fleet Detail</h2>
                <p>{filteredPods.length} pods shown after filtering.</p>
              </div>
              <div className="kg-filters">
                <div className="kg-input-wrap">
                  <Search size={14} strokeWidth={1.5} />
                  <input
                    value={searchTerm}
                    onChange={(event) => setSearchTerm(event.target.value)}
                    placeholder="Search pods"
                    aria-label="Search pods"
                  />
                </div>

                <div className="kg-segment" role="tablist" aria-label="Pod health filter">
                  {(["all", "healthy", "degraded", "failed"] as const).map((option) => (
                    <button
                      key={option}
                      type="button"
                      className={clsx({ active: podFilter === option })}
                      onClick={() => setPodFilter(option)}
                    >
                      {option}
                    </button>
                  ))}
                </div>
              </div>

              <div className="kg-pod-grid">
                {filteredPods.map((pod, index) => {
                  const health = getPodHealth(pod);
                  return (
                    <article key={pod.name} className={clsx("kg-pod", `kg-pod-${health}`)} style={{ animationDelay: `${index * 60}ms` }}>
                      <div className="kg-pod-top">
                        <h3 title={pod.name}>{shortPodName(pod.name)}</h3>
                        <span className={clsx("kg-tag", `kg-tag-${health}`)}>{health}</span>
                      </div>
                      <p className="kg-pod-status">{podStateLabel(pod)}</p>
                      <p className="kg-pod-meta">Service: {pod.service}</p>
                      <p className="kg-pod-meta">Phase: {pod.phase}</p>
                      <div className="kg-restart-row">
                        <span>Restarts</span>
                        <strong>{pod.restarts}</strong>
                      </div>
                      <div className="kg-restart-bar">
                        <span style={{ width: `${Math.min((pod.restarts / 8) * 100, 100)}%` }} />
                      </div>
                    </article>
                  );
                })}
              </div>
            </article>

            <article className="kg-panel">
              <div className="kg-panel-head">
                <h2>Service Distribution</h2>
                <p>How workload is spread across microservices.</p>
              </div>
              <div className="kg-service-grid">
                {serviceBreakdown.map((service) => (
                  <div key={service.service} className="kg-service-item">
                    <span>{service.service}</span>
                    <strong>{service.count}</strong>
                  </div>
                ))}
              </div>
            </article>

            <article className="kg-panel">
              <div className="kg-panel-head">
                <h2>Operations Timeline</h2>
                <p>Live backend events and Kubernetes control loops.</p>
              </div>
              <div className="kg-timeline">
                {timeline.length === 0 && <p className="kg-empty">No timeline events yet.</p>}
                {timeline.map((event) => (
                  <div key={event.id} className={clsx("kg-event", `kg-event-${event.kind}`)}>
                    <div className="kg-event-icon">
                      {event.kind === "good" && <ShieldCheck size={14} strokeWidth={1.5} />}
                      {event.kind === "critical" && <AlertTriangle size={14} strokeWidth={1.5} />}
                      {event.kind === "warning" && <Bell size={14} strokeWidth={1.5} />}
                      {event.kind === "info" && <PlugZap size={14} strokeWidth={1.5} />}
                    </div>
                    <div>
                      <p>{event.message}</p>
                      <span>{event.time}</span>
                    </div>
                  </div>
                ))}
              </div>
            </article>
          </section>

          <aside className="kg-side">
            <article className="kg-panel">
              <div className="kg-panel-head">
                <h2>Integrations</h2>
                <p>Slack, Discord, Prometheus, and Grafana readiness.</p>
              </div>
              <div className="kg-integration-list">
                <IntegrationRow
                  icon={<Activity size={14} strokeWidth={1.5} />}
                  label="Prometheus"
                  healthy={Boolean(integrations?.prometheus_up)}
                />
                <IntegrationRow icon={<Gauge size={14} strokeWidth={1.5} />} label="Grafana" healthy={Boolean(integrations?.grafana_up)} />
                <IntegrationRow
                  icon={<SendHorizontal size={14} strokeWidth={1.5} />}
                  label="Discord"
                  healthy={Boolean(integrations?.discord_configured)}
                />
                <IntegrationRow
                  icon={<Slack size={14} strokeWidth={1.5} />}
                  label="Slack Runtime"
                  healthy={Boolean(integrations?.slack_runtime_configured || integrations?.slack_app_configured)}
                />
              </div>

              <div className="kg-action-grid">
                <button
                  type="button"
                  onClick={() => void executeAction("crash")}
                  className="danger"
                  disabled={actionLoading !== null}
                >
                  <Rocket size={14} strokeWidth={1.5} />
                  {actionLoading === "crash" ? "Triggering" : "Trigger Crash"}
                </button>
                <button
                  type="button"
                  onClick={() => void executeAction("discord")}
                  disabled={actionLoading !== null}
                >
                  <SendHorizontal size={14} strokeWidth={1.5} />
                  {actionLoading === "discord" ? "Sending" : "Test Discord"}
                </button>
                <button
                  type="button"
                  onClick={() => void executeAction("slack")}
                  disabled={actionLoading !== null}
                >
                  <Slack size={14} strokeWidth={1.5} />
                  {actionLoading === "slack" ? "Sending" : "Test Slack"}
                </button>
              </div>

              <div className="kg-link-row">
                <a href={integrations?.grafana_url || "#"} target="_blank" rel="noreferrer" className="secondary">
                  Open Grafana
                </a>
                <a href={integrations?.prometheus_url || "#"} target="_blank" rel="noreferrer" className="secondary">
                  Open Prometheus
                </a>
              </div>
            </article>

            <article className="kg-panel">
              <div className="kg-panel-head">
                <h2>Signal Summary</h2>
                <p>Fast glance of current cluster pressure.</p>
              </div>

              <ul className="kg-signal-list">
                <li>
                  <span>
                    <ShieldCheck size={14} strokeWidth={1.5} /> Healthy Pods
                  </span>
                  <strong>{pods.filter((pod) => getPodHealth(pod) === "healthy").length}</strong>
                </li>
                <li>
                  <span>
                    <AlertTriangle size={14} strokeWidth={1.5} /> Failed Pods
                  </span>
                  <strong>{pods.filter((pod) => getPodHealth(pod) === "failed").length}</strong>
                </li>
                <li>
                  <span>
                    <PlugZap size={14} strokeWidth={1.5} /> Degraded Pods
                  </span>
                  <strong>{pods.filter((pod) => getPodHealth(pod) === "degraded").length}</strong>
                </li>
                <li>
                  <span>
                    <ShieldAlert size={14} strokeWidth={1.5} /> Crash Score
                  </span>
                  <strong>{Math.round(summary?.crash_counter || 0)}</strong>
                </li>
              </ul>
            </article>
          </aside>
        </main>
      </div>
    </div>
  );
}

function IntegrationRow({
  icon,
  label,
  healthy,
}: {
  icon: React.ReactNode;
  label: string;
  healthy: boolean;
}) {
  return (
    <div className="kg-integration-row">
      <span>
        {icon}
        {label}
      </span>
      <strong className={healthy ? "ok" : "down"}>{healthy ? " online" : " offline"}</strong>
    </div>
  );
}
