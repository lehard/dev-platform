# Proposal: Guard Requirement target lifecycle

## Why

Backlog routing currently proves where to file a Requirement, but not that its target can execute and deliver through the managed lifecycle. An unsupported operator repository can therefore leave a Requirement in pre-authoring while work is delivered separately and manually closed.

## What changes

Establish a target-owned support check for Requirement intake and execution. A supported target has the required managed configuration, entrypoints and publication path; an operator-managed downstream target must carry its explicit opt-in. The connected GitHub adapter checks the equivalent committed evidence or explicit operator route. Terminal reconciliation rechecks support and authoritative delivery evidence.

## Success evidence

Unsupported targets fail early with a precise supported route; configured managed and operator-managed downstream targets proceed; no Requirement reaches Done without its managed terminal path.
