# 📄 Markdown to PDF Converter Action

> Disclaimer: This documentation was generated with Google Gemini, but manually validated.

An asynchronous, cloud-native GitHub Action that converts Markdown documents into beautifully styled, corporate-ready PDFs using WeasyPrint.

This action is entirely containerized, meaning it requires zero system-level dependencies or setup in the consuming repositories. It supports custom CSS, corporate logo injection, LaTeX/MathJax rendering, and automated page formatting.

## ✨ Features

- Zero Configuration: Runs completely standalone via Docker; no Python or Node.js environment setup required in your workflows.
- Asynchronous Architecture: Built on asyncio and aiohttp for non-blocking I/O and rapid asset fetching.
- Advanced Formatting: Natively supports tables, code highlighting (via Pygments), blockquotes, and intelligent page breaks.
- Math Support: Automatically detects inline $ and block $$ LaTeX equations and renders them via CodeCogs.
- Corporate Branding: Inject custom CSS stylesheets and a base64-encoded corporate logo directly into the PDF header.

## 🚀 Usage

To use this action in any repository within the organization, reference the action in your `.github/workflows/` YAML file.

### Basic Example

This workflow will automatically generate a PDF from the repository's `README.md` and commit it to the `docs/` folder whenever changes are pushed to the main branch.

`.github/workflows/generate-docs.yml`:

```yml
name: Generate Documentation PDF

on:
  push:
    branches:
      - main
  paths:
    - 'README.md'

  permissions:
  contents: write

  jobs:
    build-pdf:
      runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Create Docs Directory
        run: mkdir -p docs

      - name: Convert README to PDF
        uses: IsraTech-Software/markdown-to-pdf-action@v1
        with:
          input_file: 'README.md'
          output_file: 'docs/README.pdf'

      - name: Commit Generated PDF
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"
          git add docs/README.pdf
      
          if ! git diff-index --quiet HEAD docs/README.pdf; then
            git commit -m "docs: auto-generate PDF from README"
            git push
          else
            echo "No changes detected. Skipping commit."
          fi
```

### Advanced Example (With Styling)

If you have a corporate stylesheet or logo stored within the consuming repository, you can pass them as optional inputs.

```yml
- name: Convert README to PDF (Styled)
  uses: your-org-name/markdown-to-pdf-action@v1
  with:
    input_file: 'docs/SPECIFICATION.md'
    output_file: 'docs/releases/SPECIFICATION_v2.pdf'
    logo_file: '.github/assets/company-logo.png'
    css_file: '.github/assets/pdf-theme.css'
```

## ⚙️ Inputs

| Input | Description | Required | Default |
| - | - | - | - |
| `input_file` | Path to the source Markdown file (relative to repository root). | **Yes** | `README.md` |
| `output_file` | Path where the PDF should be saved (relative to repository root). | **Yes** | `docs/README.pdf` |
| `logo_file` | Path to a custom image file (PNG/JPG) to overlay as a top-right watermark/logo. | No | `""` |
| `css_file` | Path to a custom CSS stylesheet to override default typography and margins. | No | `""` |

## 🏗️ Local Development & Testing

If you are modifying the Action's core logic (`generator.py`) and wish to test it locally before pushing a new release tag:

1. Build the Docker Image: 
   ```bash
   docker build -t md-to-pdf-action .
   ```
2. Run the Container against a local file:
	- Mount your current directory to the container so it can read your local Markdown files and write the PDF back to your machine: 
	```bash
	docker run --rm -v $(pwd):/workspace md-to-pdf-action -i /workspace/test.md -o /workspace/output.pdf
	```

## 📝 Extended Syntax

The script allows additional LaTeX-Like syntax:

1. Page Breaks: Insert `\newpage` anywhere in your Markdown to force the PDF renderer to start a new page.
2. MathJax: Use $$ \int_0^\infty x^2 dx $$ for centered block equations, or $E=mc^2$ for inline equations.
3. Table Alignment: Due to WeasyPrint behavior, standard markdown table alignments can sometimes drift. The generator specifically parses `\c` (Center Text) and `\r` (Right Align Text) tokens inside table cells to force Center and Right alignment, respectively.
4. Newlines (html `<br>`) can be inserted using `\n`.
