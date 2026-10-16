# Reproducibility and release scope

This repository is the portable software source for FlowPilot. It separates reusable implementation from private working files and historical research campaigns.

## What the source release supports

- Inspecting the pipeline, prompts, schemas and deterministic calculations.
- Running the web interface and its illustrative demonstration.
- Testing software behavior with the included focused fixtures.
- Configuring model providers and supplying your own literature, rules and laboratory inventory for new designs.

The public source does not by itself reproduce the manuscript's complete model-and-data environment. The historical corpus, embeddings, rule prose, benchmark generations, judge assessments and laboratory records are not bundled.

## Test fixtures and demonstration data

The included fixtures are synthetic or anonymized computational inputs retained to test specific software behavior, such as schema handling, inventory constraints, topology and final-design consistency. They are not new laboratory data, a historical benchmark release or an experimental validation set. Chemistry names or numerical conditions in a fixture do not imply that an experiment was performed or that its outcome was measured.

The example protocol is a fictional input, and the web demonstration uses illustrative interface data. These examples help exercise the software; they do not substitute for a configured research corpus or establish the performance of the complete pipeline.

## Current software and historical campaigns

The accompanying manuscript is **Agentic design of continuous flow processes with chemical knowledge and laboratory constraints** (2026). Its comparisons used frozen campaign inputs, selected model versions and campaign-specific configuration. Current source code may include later fixes and portability changes.

Re-running today's software with today's provider responses is a new experiment. It should not be described as a bit-for-bit reproduction of a historical campaign, even when the protocol text and model name match. Archived tables should be verified against the precise selected records and scoring procedure for their campaign.

The manuscript's primary comparison, separate model comparisons, module ablations and later development benchmarks have different cohorts. Keep those cohorts separate when analyzing archived research data. Computational candidates, grouped laboratory operating points and independent experimental repeats are also different units of observation.

## Recording a new study

Preserve the source revision, dependency versions, model identifiers, provider or local-serving configuration, prompts, input protocol, researcher answers, inventory and knowledge-resource versions. Keep the raw result and its canonical final design together with the council record, calculation traces and diagram artifacts.

Record measured outcomes separately from predictions and assumptions. A generated proposal passing the software's checks does not establish yield, selectivity, physical operating performance or permission to operate equipment.

## Documentation figures

The architecture figure is unchanged manuscript artwork. Interface screenshots and demonstration data are identified separately in [image provenance](images/README.md). Their presence does not add the underlying research campaigns to this source release.

No publication or research-data DOI is claimed in this release. [CITATION.cff](../CITATION.cff) records the confirmed authors and manuscript title without assigning journal or publication metadata.
