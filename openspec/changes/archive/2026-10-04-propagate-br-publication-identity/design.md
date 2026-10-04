## Context
The predecessor introduces stable BR presentation identities backed by existing parent/child linkage. The publication lifecycle already proves exact task or shared candidate identity and private-lineage mapping.

## Decisions
Reuse the predecessor helper and validated provenance. New linked task branches include a normalized readable BR child identity plus change slug; keep worktree/change identity compatible with existing transactional admission and resume existing registered branches. Unlinked/direct technical tasks remain supported. Child PR titles use [BR-N/Tn]; shared titles use [BR-N] and their safe identity block lists included children. Apply the block idempotently, including existing exact-head PR retries, while preserving user-authored descriptions and GitHub merge policy. Never build public text from private parent prose or exact references. Shared manifests may expose validated safe BR identity without exposing private sources or replacing exact opaque technical mapping.

## Risks and Mitigations
Branch-name changes affect transactions/admission and recovery: derive centrally, preserve existing registered branch identities and test rollback/resume. Shared draft PR grows over time: repair title/block as children are appended, preserve the same branch/PR, and reject conflicting identities. Publication may use project-owned harness APIs: retain compatibility, portable helper contracts and project-specific publication behavior; do not overwrite project-owned taxonomy or instructions. Test fresh renders and upgrades.

## Verification
Exercise child publication, shared draft growth and final merge, exact-head retries, user titles/body preservation, legacy/unlinked branches, project harness compatibility and privacy guard. Independent review and truthful semantic receipt are required.

## Implementation details
New child branches use `agent/br-N-tM-<change>` through the predecessor identity helper; worktree paths and transaction filenames remain keyed by change. Existing transaction branches and registered worktree branches remain authoritative after exact canonical source validation. Receipt discovery reads the registered branch rather than reconstructing its spelling. Shared candidate branch names, opaque lineage and canonical manifest paths retain their existing ownership contract, including generation recovery; additive `work_identity` fields carry presentation only and do not select a branch or manifest path.

Public presentation is derived from reciprocal canonical Requirement/child claims and compared with committed provenance. Shared identities are read from each exact child head's archived provenance and verified against current canonical claims before publication. Legacy provenance without a token may use a validated canonical claim; unlinked tasks remain unchanged. A standard `<!-- dev-platform:br-identity -->` block is replaced in place, and only a leading BR title prefix is repaired. Exact-head retries read the existing PR title/body and preserve their user-authored remainder. Manifest path ownership is validated independently of generation branch naming.

The contained executor supplies implementation and synthetic evidence only. Supervisor review, host checks, semantic receipt, archive, retrospective and publication remain separate completion gates.

Project-owned start helpers may predate the optional `branch_name` keyword.
Unlinked tasks and recorded legacy branches remain callable through that older
signature. A fresh linked child must stop before branch creation if the helper
cannot accept its validated BR branch; the operator must update the owning
project's helper contract rather than silently creating a branch without BR.
Platform-owned helpers consume the keyword. Shared publication supplies safe
presentation through the existing title/body CLI contract, preserving project
publisher ownership.

Readable-identity helpers are loaded only by linked/shared publication paths.
Minimal legacy and unlinked lifecycle installations retain their existing
publication behavior without a new eager module dependency. Linked paths still
require the helper and fail closed when its proof cannot be performed.

After potentially long checks, shared orchestration revalidates canonical BR
claims against the exact archived child heads before supplying public text to
the publisher. A change from the pre-check identity set stops publication.
