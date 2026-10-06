# ATI Frontend

Frontend prototype for the Multi-Agent Research System. It uses Next.js 14, React 18 and Tailwind CSS. The current UI supports a basic task creation/detail flow; target product flows, API expectations and implementation gaps are documented in the [SRS](../docs/requirements/SRS.md) and [System Design](../docs/architecture/system-design.md).

## Run locally

From this directory:

```bash
npm install
npm run dev
```

Run the backend separately from the repository root as described in the [main README](../README.md). The UI/backend integration is still a development prototype; verify each flow end-to-end before treating it as complete.

## Available scripts

| Command | Purpose |
|---|---|
| `npm run dev` | Start the Next.js development server |
| `npm run build` | Build the frontend |
| `npm run start` | Serve a production build |
| `npm run lint` | Run the configured Next.js lint command |

## Project documentation

Start at the [project documentation index](../docs/README.md). The root README describes the verified baseline and quick-start setup; the SRS and architecture docs describe target requirements and design.
