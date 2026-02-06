# write.

A writing appliance for students. write. combines a Markdown editor, source management, and export in a single terminal application.

## Philosophy

Students shouldn't need to understand filesystems, BibTeX, or Zotero. They should think about **essays** and **sources**. write. provides:

- **Projects, not files** — students see "Gatsby Essay," not `~/Documents/english/essay1.md`
- **Simplified sources** — add a book by entering Author, Title, Year, Publisher. No BibTeX syntax.
- **One-key citations** — press `Ctrl+J`, search, press Enter. A Chicago-format footnote appears.
- **Integrated export** — open the command palette (`Ctrl+P`) and select Export.

## Requirements

- Python 3.9+
- Textual (and its dependencies: Rich, markdown-it-py, mdit-py-plugins, platformdirs)
- For PDF/DOCX export: Pandoc
- For PDF export: LibreOffice

### Option A: pip install (recommended)

```bash
pip install textual
```

Then just run `python3 write.py`.

### Option B: Vendored dependencies (no network needed)

Place these zip files in the project directory:

- `rich-master.zip` (from github.com/Textualize/rich)
- `mdit-py-plugins-master.zip` (from github.com/executablebooks/mdit-py-plugins)
- `textual-main.zip` (from github.com/Textualize/textual)

Then:

```bash
chmod +x setup.sh run.sh
./setup.sh     # unpacks into vendor/
./run.sh       # launches write.
```

## Usage

```bash
python3 write.py          # if textual is pip-installed
./run.sh                   # if using vendored dependencies
WRITE_DATA=~/essays ./run.sh   # custom data directory
```

Data is stored in `~/.write/` by default. Exports go to `~/Documents/`.

## Keyboard Shortcuts

### Editor

| Key       | Action                  |
|-----------|-------------------------|
| Ctrl+J    | Insert citation         |
| Ctrl+N    | Insert footnote (`^[]`) |
| Ctrl+B    | Bold (`**text**`)       |
| Ctrl+P    | Command palette         |

### Command Palette

Cite, Bibliography, Sources, Export, and Insert frontmatter properties (author, title, instructor, date, spacing, style).

## YAML Frontmatter

```yaml
---
title: "My Essay"
author: "First Last"
instructor: "Prof. Name"
date: "January 2026"
spacing: double
style: chicago
---
```

- **spacing**: `single`, `double`, `dg.single`, `dg.double`
- **style**: `chicago` (Turabian cover page) or `mla` (MLA header)

## Source Types

### Book
Author (Last, First), Title, Year, Publisher, City

### Article
Author (Last, First), Title, Year, Journal, Volume, Issue, Pages

### Website
Author (Last, First), Title, Year, Website Name, URL, Access Date

## Citation Format

Chicago/Turabian style:

**Footnote:** F. Scott Fitzgerald, *The Great Gatsby* (New York: Scribner, 1925), 42.

**Bibliography:** Fitzgerald, F. Scott. *The Great Gatsby*. New York: Scribner, 1925.

## Data Storage

Projects are stored as JSON files in `~/.write/projects/`. Each project contains its text content and source metadata. No external database required.

## Architecture

Built on [Textual](https://textual.textualize.io/), which provides:

- `TextArea` widget with undo/redo, word wrap, selection, clipboard
- `ModalScreen` for citation picker and source management
- `OptionList` for project and source browsing
- CSS-based styling
- Proper async event handling

The data layer (Source, Project, Storage) is framework-independent and can be tested without a terminal.

## License

MIT
