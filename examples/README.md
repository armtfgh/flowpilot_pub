# Example inputs

These are **illustrative software inputs**, not experimental records or validated operating instructions. They contain no measured yield, conversion or optimization result.

| File | Purpose |
| --- | --- |
| [`batch_protocol.txt`](batch_protocol.txt) | A fictional batch-protocol example showing the facts supplied to intake |
| [`lab_inventory.json`](lab_inventory.json) | Generic equipment in the supported inventory schema |

The protocol uses a familiar condensation to demonstrate species, amounts, solvent, temperature and duration. Its numerical values were authored as a software example. The inventory uses generic equipment descriptions and illustrative limits; it does not describe a particular laboratory or certify any instrument's rating.

After configuring providers and knowledge resources:

```bash
flowpilot translate --file examples/batch_protocol.txt \
  --inventory examples/lab_inventory.json \
  --output result.json
```

This invokes a live design and can incur provider charges. To inspect the interface without making a design call, start the web app and open `http://localhost:8510/?demo=1`.

For your own protocol, replace the example with observed facts, state missing information explicitly and provide your real equipment constraints. Keep later experimental measurements distinct from the original input and model-generated predictions.
