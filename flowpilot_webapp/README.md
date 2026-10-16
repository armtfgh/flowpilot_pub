# FlowPilot workspace

The React workspace calls the shared Python design pipeline through FastAPI. It provides structured intake, inventory profiles, asynchronous designs, saved results, diagrams, and experimental refinement.

From the repository root, with Python 3.11+ and Node.js 22.12+ installed:

```bash
./flowpilot_webapp/run_dev.sh
```

Open <http://127.0.0.1:8510>. The `?demo=1` view uses illustrative data and makes no model calls. The launcher creates an isolated virtual environment, installs the web extra, installs frontend packages from the lockfile, and builds the client. Model credentials and Graphviz installation are described in the [project README](../README.md).

User inventories, knowledge indexes, and generated results live under `~/.flowpilot` by default. Set `FLOWPILOT_HOME` before launch to use another directory. Existing environment variables take precedence over `.env` settings. The server binds to loopback unless `FLOWPILOT_HOST` is set explicitly.

For frontend development, run `npm run dev` in `flowpilot_webapp/frontend`; its API proxy uses the backend at port 8510.

## Windows desktop build

On Windows with Python 3.11, Node.js 22.12+, and Graphviz installed:

```powershell
powershell -ExecutionPolicy Bypass -File flowpilot_webapp\build_windows.ps1
```

The output is `flowpilot_webapp/release/FlowPilot-Windows-x64.zip`. Extract it and launch `FlowPilot.exe`. The bundle contains application assets and the example inventory; private corpora, saved runs, uploaded documents, and user inventories are excluded. Configure credentials in the environment or in `.env` beside the executable. User state still lives in `FLOWPILOT_HOME`.

Desktop bundles must be built and verified on Windows. The included workflow creates a downloadable build artifact when run manually.

## Browser checks

With a local backend running, run `npm run test:e2e` from the frontend directory. Core tests use synthetic inventories and mocked model availability; they do not generate designs or call model providers. Archive integration cases are skipped unless their `FLOWPILOT_*_RUN_ID` or `FLOWPILOT_SCIENTIFIC_RUN` variables point to a local saved run. The inventory-rebinding case also needs `FLOWPILOT_UPDATED_PROFILE_ID`. No research archives are bundled with the source.
