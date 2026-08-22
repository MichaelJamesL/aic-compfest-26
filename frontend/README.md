# frontend

React + TypeScript + Tailwind v4. The UI for the AI Maintenance Coordinator.

```bash
npm install
npm run dev      # :5173 — proxies /api /config /health to localhost:8000
npm run test     # vitest
npm run build    # tsc -b && vite build
```

The backend must be running on :8000:

```bash
cd ../backend && uvicorn app.main:app --port 8000
```

## Where things live

| Path | What |
| --- | --- |
| `src/index.css` | The design tokens. **Every colour in the app is defined here and nowhere else.** |
| `src/api/types.ts` | Wire types, transcribed from `docs/API.md` |
| `src/api/client.ts` | fetch wrapper: identity headers, error envelope, Indonesian error copy |
| `src/lib/` | formatting, severity→token mapping, CSV parsing, health breakdown |
| `src/ui/` | presentational primitives, built from `docs/design/VISUAL_LANGUAGE.md` §7 |
| `src/shell/` | the two-tone shell: nav rail, header, engine-status card |
| `src/screens/` | one file per screen in `docs/design/SCREENS.md` |

## Before changing anything visual

Read [`docs/design/VISUAL_LANGUAGE.md`](../docs/design/VISUAL_LANGUAGE.md).
It is derived from `docs/ref/ui-ref.jpg` and its §9 banned-pattern list is not
advisory. Run the §11 self-check before committing UI.

No component library, by decision — see
[`docs/requirements/FRONTEND.md`](../docs/requirements/FRONTEND.md). Do not add
shadcn/ui, MUI, or Chakra: their defaults are exactly the look being avoided.
