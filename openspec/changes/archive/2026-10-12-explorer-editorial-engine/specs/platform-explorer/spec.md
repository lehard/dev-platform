## MODIFIED Requirements

### Requirement: Explorer is a build-time view of canonical repository sources

The platform SHALL provide a repository-owned build entrypoint that generates a static Explorer from an allowlisted set of git-tracked canonical sources and one repository-owned editorial layer. The editorial layer SHALL hold one explanatory description per semantic node (overview, lifecycle stage, mechanism, mechanism part, cross-cutting topic, glossary term), written for the reader, and every node SHALL bind at least one canonical source section. The editorial layer SHALL NOT define normative rules; those remain in `AGENTS.md`, OpenSpec specifications and `docs/`. Engineering-source pages SHALL keep rendering explanations from referenced source files and headings.

#### Scenario: Clean build
- **WHEN** the build runs in a git checkout whose map, editorial nodes and sources are valid
- **THEN** it writes the overview, one page per lifecycle stage, mechanism, topic and engineering-source element, and a coverage page
- **AND** every top-level explanation comes from the editorial node and every engineering-source explanation from its referenced source

#### Scenario: Referenced source or heading is missing
- **WHEN** an editorial node or a map element references a file or heading that does not exist, is not git-tracked, or is excluded by the public-distribution policy
- **THEN** the build fails non-zero naming the node or element and the source and writes no output

#### Scenario: Editorial node is incomplete or unfinished
- **WHEN** an editorial node lacks a field required for its kind, references an unknown node, or contains an ellipsis, a truncated sentence or Markdown syntax in its text
- **THEN** the build fails non-zero naming the node and the field and writes no output

#### Scenario: Node is declared as an outline
- **WHEN** a node is explicitly declared as an outline and holds only its kind, title, definition, source bindings and structural relations (order, role, stage usage, children and, for a stage, its transitions)
- **THEN** the build renders it as an outline page with its definition, relations and a notice that its full explanation is pending
- **AND** the coverage page lists it as an outline

#### Scenario: New capability or decision is added
- **WHEN** a new OpenSpec capability, optional capability descriptor or decision record matching a declared collection is added
- **THEN** it appears among the engineering sources in the next build without editing the map or any editorial node

#### Scenario: Unsupported content construct
- **WHEN** an included source excerpt contains a Markdown construct the renderer does not support
- **THEN** the build fails naming the file and line instead of dropping or mis-rendering it

### Requirement: Explorer pages provide navigation beside content and stable direct links

Each page SHALL show a persistent, collapsible navigation tree with the current node selected beside a node panel that states the node's role, its place (breadcrumb), what comes into it, what happens in it, where its results go and who uses them, and its child nodes with complete short descriptions. Engineering sources SHALL be reachable from a node only through an explicit step. Each node SHALL have a stable relative URL that works without JavaScript and under a project-site subpath, and previously published lifecycle stage and engineering-source URLs SHALL keep resolving.

#### Scenario: Reader opens an element by direct link
- **WHEN** a reader opens the URL of an overview, stage, mechanism, topic or engineering-source page
- **THEN** the page shows the tree with that node selected and its ancestors expanded, the breadcrumb, the three zones of incoming, processing and outgoing links, and its child nodes

#### Scenario: Previously published link is opened
- **WHEN** a reader opens a lifecycle stage or engineering-source URL published before this change
- **THEN** the page exists at the same path

#### Scenario: Site is served under a subpath
- **WHEN** the generated site is served from a path prefix
- **THEN** all internal links and assets resolve because they are relative

#### Scenario: Page is viewed on a narrow screen
- **WHEN** a page is viewed at phone width
- **THEN** the tree, node panel and lifecycle schema adapt without horizontal page overflow

### Requirement: Explorer presents an ordered end-to-end lifecycle journey

The Explorer SHALL present the Dev Platform lifecycle as eight ordered stages from request and requirements through change design, routing, execution, verification and independent review, publication and integration, release and rollout, to feedback and improvement. Each stage SHALL declare typed transitions (main, conditional or return) with a reason, and the overview SHALL show them as one schema so that shortened paths, returns after review and the conditional release stage are visible as such. Each stage page SHALL state its purpose, inputs, action, outputs and their consumers, forks, conditional and error paths, an example and its mechanisms, from its editorial node.

#### Scenario: Reader follows the lifecycle
- **WHEN** a reader opens the overview
- **THEN** every stage is shown in order with a stable link, with main, conditional and return transitions distinguished
- **AND** each stage page offers previous and next stage navigation and links to its mechanisms

#### Scenario: Component page shows lifecycle usage
- **WHEN** a mechanism or component is used by one or more stages
- **THEN** its page lists those stages with links, derived from the stage nodes

#### Scenario: Stage definition is invalid
- **WHEN** a stage has a duplicate or non-contiguous order, a transition to an unknown stage, a transition without a reason, or an unresolved source
- **THEN** the build fails non-zero naming the stage and writes no output

#### Scenario: Lifecycle pages without scripting
- **WHEN** the lifecycle pages are opened without JavaScript or under a path prefix
- **THEN** the schema, stage content and navigation remain usable

## ADDED Requirements

### Requirement: Stale editorial explanations are visible but never block development

The platform SHALL record, for each editorial node, a digest of every bound canonical source section at its last editorial review, ignoring whitespace-only differences. When a bound section has changed since that review, the Explorer check SHALL report the node and section as a warning without failing, the published page SHALL mark the node as possibly outdated naming the changed section, and a single repository command SHALL refresh the review record of named nodes.

#### Scenario: Bound section changes in a pull request
- **WHEN** a change edits a canonical section bound to an editorial node and does not refresh its review record
- **THEN** the Explorer check and selected checks report the node and section as a warning
- **AND** no check fails because of it

#### Scenario: Stale node is published
- **WHEN** the site is built while a node's bound section differs from its review record
- **THEN** the node page shows a marker that its source changed after the last review, naming the section

#### Scenario: Explanation is reviewed
- **WHEN** an author updates the explanation if needed and runs the review command for the node
- **THEN** the review record matches the current sections and the warning and marker disappear
