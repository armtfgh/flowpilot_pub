# Configuration

Run `flowpilot check` before starting a live design. It reports local configuration and renderer availability without making model-provider calls.

## Credentials

Copy [`.env.example`](../.env.example) to `.env`, or set credentials in your process environment:

```dotenv
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key
```

The default chemistry and translation components use Anthropic models. OpenAI supplies embeddings and is also available as a council/model route. The required credentials depend on the routes you select; the presence of a local inference server does not by itself make every pipeline component local.

Existing environment variables take precedence. `FLOWPILOT_ENV_FILE` selects an explicit environment file; otherwise configuration is loaded from the working directory's `.env` and then the runtime home's `.env`. Environment files are ignored by Git.

Provider calls send the relevant protocol, evidence and prompt context to the selected provider and may incur charges. The interface demonstration at `?demo=1` does not generate a design or call an LLM.

## Runtime files

The default runtime home is `~/.flowpilot`. To keep an independent workspace:

```bash
export FLOWPILOT_HOME="$HOME/flowpilot-workspace"
flowpilot check
```

Use a separate runtime home for experiments that should not share indices or saved results. Keep generated data outside the source checkout; see [data setup](data_setup.md) for the resources needed by a live run.

| Location under the runtime home | Contents |
| --- | --- |
| `data/records/` | Structured literature records |
| `data/chroma_db/` | Persistent vector index |
| `data/rules.json` | User-supplied engineering-rule collection |
| `data/inventory_profiles/` | Saved inventory profiles |
| `outputs/` | Generated design and run artifacts |

`FLOWPILOT_INVENTORY_PROFILE_DIR` can select a separate profile directory. `flowpilot check --json` provides structured local diagnostics.

## Model selection

The web workspace exposes upstream chemistry and downstream/council routes. [`flowpilot_translate/model_catalog.py`](../flowpilot_translate/model_catalog.py) defines the supported route IDs. [`flowpilot_translate/config.py`](../flowpilot_translate/config.py) contains component models, retrieval settings, engineering thresholds and council settings.

For local routes, configure your own OpenAI-compatible inference endpoint and the model ID advertised by that server. A listed local route is not a bundled model or a guarantee that the server is running. Review component routing, embedding configuration and optional topology/output model calls when configuring a local workflow.

The environment template documents `FLOWPILOT_ENGINE_PROVIDER`, provider-specific engine models, `FLOWPILOT_SONNET_MODEL`, `FLOWPILOT_OPUS_MODEL`, `FLOWPILOT_EMBEDDING_MODEL` and local endpoint overrides. Set overrides before starting the server or CLI process.

The `evidence_first` translation policy treats predicted intensification as a screening hypothesis. `intensify` and `neutral` provide alternative policies for explicitly configured studies. Record the selected policy with exported research results.

## Rendering

The Python packages are installed by the project dependencies. The complete diagram renderer also needs the Graphviz `dot` executable and the Cairo native library on the host system. `flowpilot check` reports whether these are available.

## Optional interfaces

From a source checkout, the modern web interface uses:

```bash
python -m pip install -e ".[web]"
npm --prefix flowpilot_webapp/frontend ci
npm --prefix flowpilot_webapp/frontend run build
flowpilot serve --host 127.0.0.1 --port 8510
```

Node.js 22.12+ is needed to build the frontend. A wheel must be built after the frontend build to include its static assets.

The optional Streamlit interface uses:

```bash
python -m pip install -e ".[legacy-ui]"
streamlit run app.py
```

Desktop packaging dependencies are available through `.[desktop]`. A desktop build still requires configured providers and any data resources used by the selected workflow.
