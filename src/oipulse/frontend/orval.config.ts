import { defineConfig } from 'orval'

// Step 0.5 — typed client + TanStack Query hooks generated from the live
// FastAPI OpenAPI schema. Regenerate with `npm run gen:api` after the backend
// adds/changes an endpoint. The schema snapshot lives at ./openapi.json
// (refresh it with: python -c "import json,main; print(json.dumps(main.app.openapi()))" > frontend/openapi.json).
//
// Output is a single generated file consumed by src/api. It is gitignored —
// generated, never hand-edited.
export default defineConfig({
  oipulse: {
    input: {
      target: './openapi.json',
    },
    output: {
      mode: 'single',
      target: './src/api/generated.ts',
      client: 'react-query',
      httpClient: 'fetch',
      baseUrl: '/api',
      override: {
        query: {
          useQuery: true,
          signal: true,
        },
      },
      prettier: false,
    },
  },
})
