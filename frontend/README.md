# KubeGuard Next.js Frontend

This app is an advanced frontend for the existing KubeGuard live backend (`dashboard/live_server.py`).

## Features

- Next.js App Router with TypeScript
- Live telemetry UI for pods and cluster KPIs
- WebSocket realtime stream support
- Proxy API routes for:
  - `/api/summary`
  - `/api/status`
  - `/api/trigger-crash`
  - `/api/test-discord`
  - `/api/test-slack`
- Integrated Slack/Discord test actions
- Prometheus and Grafana quick links

## Run

1. Start your existing backend dashboard server on port `9001`:

```bash
python dashboard/live_server.py
```

2. Install frontend dependencies:

```bash
cd frontend
npm install
```

3. Start the frontend:

```bash
npm run dev
```

4. Open:

- Frontend: `http://localhost:3000`
- Backend API source: `http://localhost:9001`

## Environment

Copy `.env.example` to `.env.local` if you need custom backend URLs:

```bash
KG_BACKEND_URL=http://localhost:9001
NEXT_PUBLIC_KG_WS_URL=ws://localhost:9001/ws
NEXT_PUBLIC_KG_WS_PORT=9001
```

`KG_BACKEND_URL` is used by Next.js API route proxies.
