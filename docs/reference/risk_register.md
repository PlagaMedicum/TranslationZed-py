# Active Risk Register

This register changes how contributors should modify or verify specific modules. It is not a
backlog, complexity scoreboard, or archive of completed refactors.

The machine-checked source is `risk_register.json`.

## Usage

- Read an entry before changing the named module.
- Preserve its constraints and run the listed focused tests.
- Add an entry only when the risk materially changes implementation or verification choices.
- Keep evidence and closure criteria concrete enough to guide a future refactor.
- Remove an entry when the risk is resolved and its durable lesson is protected by tests, code,
  architecture documentation, or the decision ledger.

The docs gate validates the register and touched-module triage checks that newly detected
high-risk modules are represented here.
