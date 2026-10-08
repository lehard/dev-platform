## ADDED Requirements

### Requirement: Explorer is a build-time view of canonical repository sources

The platform SHALL provide a repository-owned build entrypoint that generates a static Explorer from an allowlisted set of git-tracked canonical sources. Explanatory content SHALL be rendered from referenced source files and headings; the only Explorer-owned content SHALL be structure (element identity, title, hierarchy, order, relations and source references).

#### Scenario: Clean build
- **WHEN** the build runs in a git checkout whose map and sources are valid
- **THEN** it writes an index page and one page per map element and per enumerated collection item
- **AND** each page's explanation is rendered from its referenced sources

#### Scenario: Referenced source or heading is missing
- **WHEN** an element references a file or heading that does not exist, is not git-tracked, or is excluded by the public-distribution policy
- **THEN** the build fails non-zero naming the element and source and writes no output

#### Scenario: New capability or decision is added
- **WHEN** a new OpenSpec capability, optional capability descriptor or decision record matching a declared collection is added
- **THEN** it appears in the next build without editing the Explorer map

#### Scenario: Unsupported content construct
- **WHEN** an included excerpt contains a Markdown construct the renderer does not support
- **THEN** the build fails naming the file and line instead of dropping or mis-rendering it

### Requirement: Explorer pages provide navigation beside content and stable direct links

Each element page SHALL show a persistent navigation tree beside the selected element's content, its place in the hierarchy, related elements and links to its sources at the built commit. Each element SHALL have a stable relative URL that works without JavaScript and under a project-site subpath.

#### Scenario: Reader opens an element by direct link
- **WHEN** a reader opens the URL of an element page
- **THEN** the page shows the navigation tree with that element selected, its explanation, parent chain, related elements and source links

#### Scenario: Site is served under a subpath
- **WHEN** the generated site is served from a path prefix
- **THEN** all internal links and assets resolve because they are relative

### Requirement: Explorer output is deterministic, versioned and publicly safe

The build SHALL produce identical output for identical inputs, SHALL stamp pages with the platform VERSION and source commit, and SHALL scan generated output with the public-distribution owner-reference and secret rules before writing anything.

#### Scenario: Rebuild from the same commit
- **WHEN** the build runs twice on the same commit
- **THEN** the two outputs are byte-identical

#### Scenario: Prohibited operator state in an included source
- **WHEN** an included source contains a prohibited owner/project reference or secret pattern
- **THEN** the build fails with the bounded path and reason and writes no output

#### Scenario: Outside a git checkout
- **WHEN** the build runs where git cannot report tracked files or the commit
- **THEN** it fails explicitly rather than reading the filesystem directly

### Requirement: Explorer is platform-owned and not distributed to projects

The Explorer map, build entrypoint, assets and generated output SHALL live outside the Copier template subdirectory, and a rendered new project SHALL NOT contain any Explorer artifact.

#### Scenario: New project is rendered
- **WHEN** a project is rendered from the template
- **THEN** it contains no Explorer map, build script, assets or generated site

#### Scenario: Explorer file is moved under the template
- **WHEN** a change places an Explorer artifact under the distributed template
- **THEN** the downstream-boundary contract test fails
