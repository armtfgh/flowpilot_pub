# Data setup

The public source includes the pipeline, schemas, prompts, generic inventory inputs, software fixtures and documentation figures. It does not include the manuscript's research-literature PDFs, complete extracted corpus, stored embedding index, handbook-derived rule collection, raw laboratory data or benchmark campaign outputs.

The populated interface at `?demo=1` can be explored without those resources. A live research workflow should use deliberately configured data rather than assume that the demo or source checkout reproduces the manuscript environment.

## Starting without earlier user data

A fresh installation contains no saved runs, uploaded documents, inventory profiles, experimental feedback or research records. The optional demo is a fictional software example with no measured outcomes. It neither reads backend history nor restores browser drafts.

Normal operation saves the user's own work under `FLOWPILOT_HOME`. To start a separate workspace on a machine that already runs FlowPilot, set this variable to a new, empty directory before launching the app. Also unset `FLOWPILOT_INVENTORY_PROFILE_DIR` if it points to an older profile collection. Existing directories are not deleted or silently imported from another project. The publication interface uses separate browser-draft keys from earlier development versions.

## Literature records

Supply structured JSON records that you have permission to use. The record schemas are defined in [`flowpilot_translate/schemas.py`](../flowpilot_translate/schemas.py); extraction-format normalization is implemented in [`flowpilot_translate/vector_store.py`](../flowpilot_translate/vector_store.py).

The index command imports JSON files from the directory you provide into the runtime's canonical `data/records/` directory, then indexes that corpus:

```bash
flowpilot index /path/to/records
```

The command retains your originals and rejects conflicting filenames before copying files or making provider calls. Indexing may generate record summaries and calls the configured embedding model. It requires the corresponding provider configuration and is not an offline import of precomputed vectors. Keep the original records and their source provenance alongside your research archive.

The runtime home is `~/.flowpilot` by default, configurable with `FLOWPILOT_HOME`. Use `flowpilot check` to inspect the active paths and resource availability.

### Migrating an existing workspace

Back up your existing data first. Copy your user-owned JSON records into `data/records/` and the complete existing Chroma directory into `data/chroma_db/` under the selected `FLOWPILOT_HOME`. Preserve the embedding model, dimensions and summary-generation configuration used by that index; the query embedding configuration must match its stored vectors.

When the default `flowpilot_records` and `flowpilot_pairs` collections are absent, the loader can read existing `flora_records` and `flora_pairs` collections automatically. Custom names can be selected with `FLOWPILOT_COLLECTION_NAME` and `FLOWPILOT_PAIRS_COLLECTION_NAME`. Copying an index does not re-embed its contents. Running `flowpilot index` invokes the configured indexing models, so use it only when you intend to index records again.

## Engineering rules

`flowpilot_fundamentals` supports a structured engineering-rule collection. Its schema is in [`flowpilot_fundamentals/schemas.py`](../flowpilot_fundamentals/schemas.py), and the loader is [`flowpilot_fundamentals/knowledge_store.py`](../flowpilot_fundamentals/knowledge_store.py).

The research rule collection contains material derived from external handbooks and is not distributed here. Supply a compatible collection with appropriate rights and provenance at `$FLOWPILOT_HOME/data/rules.json` (by default, `~/.flowpilot/data/rules.json`). Missing rules change the knowledge available to the pipeline; a run without them is not the manuscript configuration.

## Laboratory inventory

Start with [`examples/lab_inventory.json`](../examples/lab_inventory.json), a generic software example. Replace its illustrative equipment, capacities and ratings with verified information for your own setup. The workspace can import, inspect and edit inventory profiles.

Inventory covers pumps, reactors, tubing, pressure controllers, mixers and other accessories. Constraints must describe the actual assembly: a nominal reactor volume alone does not establish temperature, pressure, material or connection compatibility.

You can select an explicit inventory for command-line translation:

```bash
flowpilot translate --file examples/batch_protocol.txt \
  --inventory examples/lab_inventory.json \
  --output result.json
```

This command performs a live model-assisted design after configuration. Neither the example protocol nor its inventory is a validated experimental procedure.

## Historical research material

Archived campaign settings, frozen inputs and raw outcomes belong in a separately versioned research-data deposit. They should not be overlaid onto the current runtime as though they were the current source release. See [reproducibility](reproducibility.md) for those boundaries.
