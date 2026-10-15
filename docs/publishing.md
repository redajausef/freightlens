# Put the project on GitHub

Use the clean `freightlens-github.zip` delivery. Extract it first. The folder containing
`README.md`, `pyproject.toml`, `src/` and `.github/` is the repository root. Upload its
contents as source files; uploading only the ZIP will not display the project README.

The clean delivery includes code, tests, pinned development dependencies, CI, documentation,
screenshots and fictional sample PDFs. It excludes local `.env`, databases, caches and
external publisher PDF files. You do not need to include your key to share the project.

## Upload with Git

Create an empty GitHub repository named `freightlens` in your account. Keep it empty so
GitHub does not create a competing initial README. Then open a terminal in the extracted
project root:

```bash
git init
git add .
git status --short
git commit -m "Add FreightLens document review prototype"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/freightlens.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub username. Git may prompt for your identity and
GitHub authentication. Review `git status` before committing: `.env`, `data/` and `.venv/`
must not appear. Preserve the hidden `.github` directory so Actions can run.

After pushing, open the repository and check that the images render, then open **Actions**
to inspect the Python 3.11/3.14 checks. The recorded local test results are already included;
do not claim GitHub CI passed until that actual run succeeds.

## Upload in the browser

Alternatively, use your empty repository's **uploading an existing file** link and upload
the extracted project contents. Include `.github/workflows/ci.yml` and `.env.example`;
some file pickers hide files or folders beginning with a dot. Git is the more reliable
option for preserving the complete directory structure.

## Repository details

Suggested description:

> Python/FastAPI freight document review with Gemini extraction, source evidence,
> discrepancy checks and employee approval.

Suggested topics: `python`, `fastapi`, `gemini`, `document-processing`, `logistics`, `sqlite`.

For an application, link to the repository and the README's public PDF comparison. Be
ready to run the offline workflow, explain the extraction/validation boundary and make a
small code change. Describe Codex/ECC assistance and your own contribution accurately.

No repository license has been selected on your behalf. Third-party document provenance
is recorded separately in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
