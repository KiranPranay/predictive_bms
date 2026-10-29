# Documents

| File | What it is |
| --- | --- |
| [wiring.md](wiring.md) | How to build the prototype from modules on perfboard, without a PCB: every connection, every part value, the board layout |
| [firmware.md](firmware.md) | How the firmware and the supervisor core work, how each part maps to the architecture, the console commands, the telemetry formats, and every value the architecture does not set |
| [bring-up.md](bring-up.md) | What to do with the firmware and the tools at each build gate, 0 to 12 |
| [simulator.md](simulator.md) | The simulated pack, the 29 test scenarios, what they show, and what they found |
| [gate-records.md](gate-records.md) | Record sheets to fill in and sign at each gate |
| [architecture/](architecture/) | The project's technical documents, copied from the bms-moosi repository |

## The architecture documents

The files in [architecture/](architecture/) are copies of the bms-moosi repository's `docs/`
folder at commit `0efe68e` (27 October 2026):

- `current-architecture.md` and `.svg`: revision 2.2, the build authority. Every engineering
  value in the firmware comes from it.
- `safe-build-sequence.md`: Gates 0 to 12 with their pass and stop criteria.
- `bom.csv` and `costing.csv`: the parts and their costs.

Do not edit the copies here. The bms-moosi repository holds the original: change it there
first, copy the files again, then update `firmware/components/bms_core/include/bms/config.h`
and run all the tests.
