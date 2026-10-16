# Synthetic test fixtures

These files contain authored software-test inputs. They are not laboratory
inventories, experimental records, saved model runs, or operating instructions.
Equipment names and capabilities are invented. Numerical values exercise
specific bounds, arithmetic, and allocation rules; they do not report measured
chemical performance.

| Fixture | Behavior exercised |
| --- | --- |
| `synthetic_realizer_cases.json` | Feed ratios, pressure settings, gas identity, staged flow, and stationary catalysts |
| `synthetic_connected_inventory.json` | Distinct pumps, gas controllers, reactors, and lights for a connected process |
| `synthetic_disposition_cases.json` | Paired available/unavailable equipment capabilities |
| `synthetic_inventory_limits.json` | Discrete reactor sizes and constrained engineering searches |
| `synthetic_photo_gas.json` | Reproducible two-stage gas/light candidate generation and lifecycle invariants |
| `council_response_shapes.json` | Minimal JSON response-shape parser cases |
| `diagram_stage0_topologies.json` | Minimal diagram layouts and a blocked empty graph |

Chemical names in test cases identify parser or material-handling behavior.
They do not establish a working chemical protocol. No fixtures are loaded as
application history, inventory profiles, or a literature corpus.

Diagram layout coordinates are authored from simple volume/flow identities: a
4 mL liquid reactor at 0.2 mL/min has a 20 minute residence time; the gas layout
uses 6 mL divided by 0.6 mL/min at inlet/STP for a 10 minute apparent time; the
two-stage layout sums 4/0.2 and 8/0.4 for 40 minutes. These are rendering inputs,
not reported operating results.
