# Repository Guidelines

## Project Structure & Module Organization
The repository is a curated set of Microchip PolarFire FPGA reference manuals in PDF format stored at the top level for quick access. Keep official vendor documentation in the root, and place any derivative notes, errata, or design examples in new folders such as `notes/` or `designs/` to avoid mixing them with pristine vendor assets. Track large ancillary assets (schematics, timing diagrams) inside clearly named subdirectories so future contributors can locate them without scanning every PDF.

## Build, Test, and Development Commands
There is no traditional build system; focus on validating documents. Use `pdfinfo <file.pdf>` to confirm metadata before committing new revisions and `md5sum <file.pdf>` to detect accidental corruption after transfers. When creating supplemental Markdown material, run `markdownlint docs/*.md` (if installed) to keep prose consistent.

## Coding Style & Naming Conventions
Name PDFs using the original Microchip titles with underscores (e.g., `PolarFire_FPGA_Memory_Controller_User_Guide_VB.pdf`) so upstream updates can be diffed easily. Reserve camelCase or kebab-case for auxiliary scripts. For Markdown or text assets, apply 80-character soft wraps, use level-one heading for document titles, and sentence-style capitalization for subordinate headings. Avoid embedding binaries inside Markdown; link via relative paths instead.

## Testing Guidelines
Before adding or replacing a PDF, compare versions with `diff-pdf --output-diff` or `pdfcmp` when available to verify the update is intentional. If you extract figures or tables, document the source page numbers in an accompanying README. For scripts that process the PDFs, add smoke tests under `tests/` that operate on sample pages to ensure tooling keeps working as new documents arrive.

## Commit & Pull Request Guidelines
Write commits that describe the document and action, e.g., `docs: add transceiver user guide VB edition`. Group multiple related manuals in a single pull request and include a short change log listing filenames and release revisions. Link to any internal ticket or vendor release note that motivated the update, and attach a hash or diff summary so reviewers can verify authenticity without re-downloading the files.

## Security & Provenance Tips
Only ingest files from trusted Microchip sources. Verify digital signatures or checksums when provided, and capture download URLs in your pull request description to maintain provenance.
