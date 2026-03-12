# Step 2: Figure Extraction

This step extracts figures from PDFs using PDFFigures2 and crops them using PyMuPDF.

## Prerequisites

### 1. PDFFigures2 (already installed)
- Java + sbt installed
- `pdffigures2` repository cloned

### 2. PyMuPDF (for cropping)

**Install PyMuPDF in your Anaconda environment:**

```powershell
# Activate your conda environment
conda activate knowledgebase

# Install PyMuPDF
pip install PyMuPDF
```

**Verify installation:**

```powershell
python -c "import fitz; print(fitz.__doc__)"
```

You should see PyMuPDF documentation. If you get an error, make sure you're in the `knowledgebase` environment.

## Usage

### Step 2a: Extract figure metadata (already done)

```powershell
python step2_figures\extract_figures.py D:\environment\knowledgebase -o D:\environment\knowledgebase\figures_output --pdffigures2-dir D:\environment\pdffigures2
```

This creates:
- `figures_output/figuresRulerelements.json` - figure metadata with coordinates
- `figures_output/pdffigures2_stats.json` - statistics

### Step 2b: Crop figures from PDF

**Single paper:**
```powershell
python step2_figures\crop_figures.py `
  D:\environment\knowledgebase\Rulerelements.pdf `
  D:\environment\knowledgebase\figures_output\figuresRulerelements.json `
  -o D:\environment\knowledgebase\figures_output\cropped_figures `
  --dpi 300 `
  --format png
```

**Multiple papers (batch):** pass directories instead of files. The script matches each PDF to `figures{stem}.json` in the figures directory and creates a **separate output folder per paper** under `-o`:

```powershell
python step2_figures\crop_figures.py `
  D:\environment\knowledgebase `
  D:\environment\knowledgebase\figures_output `
  -o D:\environment\knowledgebase\cropped_figures `
  --dpi 300 `
  --format png
```

- Input 1: directory containing your PDFs (e.g. `Rulerelements.pdf`, `reconstitution of chromatin domains.pdf`)
- Input 2: directory containing PDFFigures2 JSONs (e.g. `figuresRulerelements.json`, `figuresreconstitution of chromatin domains.json`)
- Output: `cropped_figures/Rulerelements/`, `cropped_figures/reconstitution of chromatin domains/`, etc.

**Options:**
- `--dpi`: Resolution (default: 300). Higher = better quality but larger files.
- `--format`: Output format: `png`, `jpg`, or `jpeg` (default: `png`)

**Output (single):** e.g. `Rulerelements_page02_figure1.png`, `Rulerelements_page04_figure2.png`, etc.  
**Output (batch):** one subfolder per paper; inside each, same naming as above.

## Troubleshooting

**"PyMuPDF not installed" error:**
- Make sure you activated the conda environment: `conda activate knowledgebase`
- Verify: `pip list | findstr PyMuPDF`

**"Invalid page" errors:**
- Run `correct_pdffigures2_pages.py` on the JSON first so page numbers are 1-based (real page).
- The crop script expects 1-based page numbers in the JSON and converts to 0-based for PyMuPDF.
