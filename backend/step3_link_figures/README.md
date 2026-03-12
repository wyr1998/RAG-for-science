# Step 3: Link cropped figures to chunks

Adds `figure_paths` (paths to cropped PDFFigures2 images) to each chunk based on `figure_refs`.

## Usage

**Single paper** — cropped figures are in a folder named after the paper:

```powershell
python step3_link_figures\link_figures_to_chunks.py `
  Rulerelements_grobid_output\Rulerelements_chunks.json `
  D:\environment\knowledgebase\figures_output\cropped_figures\Rulerelements `
  -o Rulerelements_grobid_output\Rulerelements_chunks_linked.json
```

**Batch layout** — cropped figures are in a parent folder with one subfolder per paper:

```powershell
python step3_link_figures\link_figures_to_chunks.py `
  Rulerelements_grobid_output\Rulerelements_chunks.json `
  D:\environment\knowledgebase\figures_output\cropped_figures `
  --paper Rulerelements `
  -o Rulerelements_grobid_output\Rulerelements_chunks_linked.json
```

## Output

Each chunk gets a `figure_paths` field: list of paths (relative to `figures_dir`) to image files for that chunk’s `figure_refs`. Paths match crop naming: `*figure1.png`, `*figure2.png`, etc.
