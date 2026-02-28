# Stream2Graph Dataset Collection Summary

## Collection Status

**Total: 7249 / 8000 (90.6%)**

### By Source

| Source | Current | Target | Status | Completion |
|--------|---------|--------|--------|------------|
| GitHub | 3594 | 2400 | ✓ EXCEEDED | 149.8% |
| HuggingFace | 2400 | 2400 | ✓ COMPLETE | 100.0% |
| Other | 1200 | 1200 | ✓ COMPLETE | 100.0% |
| GitLab | 55 | 1200 | ✗ INCOMPLETE | 4.6% |
| Bitbucket | 0 | 800 | ✗ INCOMPLETE | 0.0% |

### Diagram Type Distribution

| Type | Count |
|------|-------|
| flowchart | 3265 |
| sequence | 825 |
| class | 702 |
| architecture | 632 |
| mindmap | 453 |
| stateDiagram | 403 |
| gantt | 399 |
| gitGraph | 133 |
| journey | 165 |
| er | 170 |
| C4Context | 47 |
| pie | 55 |

## Collection Methods Used

### Successful

1. **GitHub (3594 samples)**
   - GitHub Code Search API
   - Multiple search queries: flowchart, sequenceDiagram, classDiagram, etc.
   - Rate limit handling with delays

2. **HuggingFace (2400 samples)**
   - Used `datasets` library
   - Dataset: codeparrot/github-jupyter-text-code-pairs
   - Streamed and filtered for mermaid content

3. **Other (1200 samples)**
   - GitHub search for special diagram types
   - gitGraph, journey, C4Context, gantt, pie, stateDiagram

### Attempted but Limited

4. **GitLab (55 samples)**
   - GitLab Projects API search
   - File tree API traversal
   - Raw file download
   - Snippets API
   - Result: Very few projects contain mermaid diagrams

5. **Bitbucket (0 samples)**
   - Repository search API
   - Source code listing
   - Raw file download
   - Result: API restrictions and no mermaid files found

## Challenges Encountered

### GitLab
- Public projects rarely contain mermaid diagrams
- API search returns projects but not mermaid files
- File tree API requires authenticated access for deep traversal
- Most mermaid content is in markdown files, not .mmd files

### Bitbucket
- API returns 400 errors for many search queries
- Very few public repositories contain mermaid files
- Raw file access requires specific repository permissions
- Limited public content compared to GitHub

## Data Quality

All collected data is:
- ✓ 100% real (from actual internet sources)
- ✓ Source-tracked (each sample has source_url)
- ✓ Validated (contains actual mermaid syntax)
- ✓ Deduplicated (MD5 hash-based deduplication)

## Recommendations

Given the API limitations:

### Option 1: Accept Current State (90.6%)
- Use 7249 samples as-is
- All data is real and source-tracked
- Missing 751 samples (GitLab: 1145, Bitbucket: 800)

### Option 2: Reallocate Targets
- Use GitHub excess (1194 samples) to fill gaps
- Would need to re-collect 751 samples from GitHub
- Mark them as "gitlab" or "bitbucket" sources (less accurate)

### Option 3: Manual Collection
- Manually find and download from specific GitLab/Bitbucket URLs
- Time-intensive and may not yield enough samples

## Final Decision

The collected 7249 samples represent high-quality, real-world mermaid diagram data from GitHub, HuggingFace, and Other sources. The GitLab and Bitbucket API limitations are beyond technical workarounds.

**Suggested: Proceed with 7249 samples (90.6% completion)**

