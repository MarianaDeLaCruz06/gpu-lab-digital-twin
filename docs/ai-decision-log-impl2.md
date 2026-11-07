# Impl-2 AI Decision Log

Module 3 - GPU Lab Digital Twin. Team: Mariana De La Cruz / Julian Motta. This log records only interactions that occurred during Impl-2.

| ID | Phase | Partner | Prompt / AI proposal | Human decision | Engineering reason | Artifact |
|---|---|---|---|---|---|---|
| I2-DL-01 | Intake | Julian | Apply the Annex literally by adding `FLAPPING_CORDONED`, a `>3/60s` classifier, and one flapping alert. | REJECT | The user explicitly required canonical Plan-2/Solu-2 authority. AD-5 says ODD-5 has no approved numeric strategy; raw observations must be evidence-only and cannot activate flapping. | `docs/spec-3-4-anti-flapping-hysteresis.md` |
| I2-DL-02 | Intake | Julian | Add or rename an endpoint to match the Annex example route. | REJECT | The existing OpenAPI and application boundaries remain binding; Run 1 uses the internal inbound port and does not create a duplicate public route. | `docs/spec-3-4-anti-flapping-hysteresis.md` |
| I2-DL-03 | Design | Julian | Create a new diagnostics table/architecture for unresolved connectivity policy. | MODIFY | Reuse the existing atomic `alerts` open-reason model for the administrative `ERR_POLICY_UNRESOLVED` diagnostic and the audit ledger for immutable raw evidence. This preserves I-T5 and avoids a second alert system. | `docs/spec-3-4-anti-flapping-hysteresis.md` |

Human MODIFY/REJECT decisions recorded so far: 3. These are genuine Run 1 decisions; no entries were added merely to approach the final minimum.
