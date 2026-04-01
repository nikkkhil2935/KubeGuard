export type Pod = {
  name: string;
  phase: string;
  ready: boolean;
  restarts: number;
  reason: string;
  service: string;
};

export type Summary = {
  total: number;
  running: number;
  crashed: number;
  restarts: number;
  request_rate_min: number;
  crash_counter: number;
  alerts_firing: number;
  timestamp: string;
};

export type SummaryPayload = {
  pods: Pod[];
  summary: Summary;
};

export type IntegrationsStatus = {
  prometheus_up: boolean;
  grafana_up: boolean;
  discord_configured: boolean;
  slack_app_configured: boolean;
  slack_runtime_configured: boolean;
  prometheus_url: string;
  grafana_url: string;
};

export type PodHealth = "healthy" | "degraded" | "failed";
