README UNDER CONSTRUCTION

# Manuscripts---a writing appliance for students

## About

## Dependencies

- Python 3.9+
- prompt_toolkit
- libreoffice
- pandoc
- cage
- foot
- cups
- cups-client
- lpr
- python
- prompt_toolkit
- fonts-jetbrains-mono
- ttf-mscorefonts-installer

## First-time use

```bash
git clone https://github.com/charleskcisco/manuscripts.git
chmod +x setup.sh run.sh
./setup.sh     # creates venv, installs prompt_toolkit and other dependencies
./run.sh       # launches journal
```

## Specifics
Manuscripts has a few views, each of which offers distinct features.

- Manuscripts opens into the Projects view, which contains a searchable list of all of your projects. From there, you can either perform various operations on your projects (rename, pin to the top of the list, etc, on which more below), open a project in the editor view, or share exported project .pdf, .docx, or .md files (again, on which more below).
- Once you enter the Editor view, you may edit your document (surprise again) using the ever-flexible the markdown syntax. You can also use ctrl+p to open a command palette, from which you can access a host of features.
- Finally, in the Exports view, you may view projects you have exported and either print them or share them via a companion app running on your (or your instructor's) PC.

Let me talk about these Surfaces and their features in more detail (organized from least to most interesting, for whimsy's sake).

### Projects view

<img width="800" height="480" alt="manuscripts-20260228-142007" src="https://github.com/user-attachments/assets/e2fa5435-c00c-4049-b275-ee8a27633cb2" />

#### Pin

#### Rename

#### Duplicate

#### Delete

#### New

#### Shut down (ctrl+s *from the Projects screen*)
Manuscripts is designed to be the writerdeck OS, if you want to think about it with that metaphor in mind, and you miight spend all of your time with this device in this app. I wanted you to be able to shut down without exiting to CLI, so I set up a double press of ctrl+s to do the job. (*N*.*b*., this only works if you have auto-login set up on your device, because all it does is run 'sudo shutdown now'. 

#### Go to exports 

### Editor view

<img width="800" height="480" alt="manuscripts-20260228-142026" src="https://github.com/user-attachments/assets/f56942d7-2381-40bb-991e-039ea3a3c704" />

#### Keybindings guide (ctrl+g)---the epitome of boring, as most essential things are
This opens a panel on the right that serves as a guide for the keybindings below. It can stay open as you edit as a reference if needed.

<img width="800" height="480" alt="manuscripts-20260228-142109" src="https://github.com/user-attachments/assets/d6225041-0613-47a3-824c-fdf2c5cd5394" />

#### Copy (ctrl+c)/Cut (ctrl+x)/Paste (ctrl+v)/Undo (ctrl+z)/Redo (ctrl+y)
These work as you'd expect them to do.

#### Bold (ctrl+b) and italicize (ctrl+i)
Markdown is a plain text language that handles **bold**, *italics*, ***or a combination of the pair*** via enclosing words in asterisks. These bindings just place the appropriate number thereof around the word in which your cursor is currently resting or around your selection.

#### Go to top (ctrl+up) or bottom (ctrl+down)
By design, Journal places your cursor on the first line after any frontmatter. These bindings can move it either to the very top of the document or (probably more usefully) to its last line, so you can pick up where you left off.

#### Invoke command palette

<img width="800" height="480" alt="manuscripts-20260228-142032" src="https://github.com/user-attachments/assets/a6bf8ddf-37dc-4c2d-b6de-463b9ab68ef4" />


#### Toggle word and paragraph count (ctrl+w)
Word counts are a necessary evil, but they can prompt some really poor behavior from bad writers who need to hit them. Sometimes, though, it's helpful to measure the number of rounded, complete, coherent sets of thought you've produced. The paragraph count is your tool for that latter, more noble goal. You can also toggle this off, if you're the sort of writer who wants to work without the measurements in your face.

#### Find and/or replace (ctrl+f)
Manuscripts offers a relatively robust find and replace feature. Ctrl+f summons a panel in which you may type a particular word. At that point, you have a choice. Enter will send you into the editor pane and highlight the term you sought. You can cycle through results with ctrl+k (next) and ctrl+j (previous), and you can return to the find panel with ctrl+f, from which you can then also replace that word you sought or replace every instance of it in your document.

<img width="800" height="480" alt="manuscripts-20260228-142044" src="https://github.com/user-attachments/assets/5c8ab3b1-538c-4187-873c-0b10fcd99017" />


#### Spell check (palette only)

<img width="800" height="480" alt="manuscripts-20260228-142056" src="https://github.com/user-attachments/assets/27d1c786-0aff-4c74-9255-8e96082e630f" />

#### Return to Projects (esc)
If you press escape (twice to prevent accidental activation), you'll return to the Projects screen.

#### Insert blank footnote (ctrl+n)
The next two features are related. First, ctrl+n offers a quick and frictionless way to insert an inline markdown footnote (the correct kind of markdown footnote; do not @ me). Once you've done that, though, the real magic begins. 

#### Source management (ctrl+o)
Manuscripts has a built-in citation manager that will open a modal where you may enter and manage works on a per project basis (though you can also import citations from other projects as well). The types of sources supported at present are books, book sections, articles, and websites.

<img width="800" height="480" alt="manuscripts-20260228-142127" src="https://github.com/user-attachments/assets/51067aba-6ebb-4ac8-9575-9422c633e8a4" />

<img width="800" height="480" alt="manuscripts-20260228-142132" src="https://github.com/user-attachments/assets/19358271-a25f-43b1-8439-56efd0d49d9b" />

#### Search for and insert citation (ctrl+r)
This will open a pop-up from which you can fuzzy search your project's sources and insert a full footnote citation.

<img width="800" height="480" alt="manuscripts-20260228-142155" src="https://github.com/user-attachments/assets/c302be8b-0dfb-4e6e-a2be-c8b03d6729f6" />

<img width="800" height="480" alt="manuscripts-20260228-142158" src="https://github.com/user-attachments/assets/9777e23c-ed0c-4c74-8119-f1541ead27ae" />

#### Insert bibliography (palette only)

#### Insert frontmatter (palette only)
This will insert at the top of the document the frontmatter relevant to the export function. I reckon title, author, instructor, and date are pretty self-explanatory, or will be once you understand how this feature works. Style accepts one of two case sensitive inputs: "chicago" and "mla". Spacing, likewise, accepts "single" or "double". You can also add your own frontmatter elements, the most relevant of which might be "bibliography", "csl", and "tags". Now to talk about the final feature in this section.

##### Example

```yaml
---
title: "My Essay"
author: "First Last"
instructor: "Prof. Name"
date: "2026-02-13"
spacing: double
style: chicago
bibliography: /home/username/documents/sources/library.bib
csl: /home/username/documents/sources/chicago.csl 
---
```

- **spacing**: `single`, `double`
- **style**: `chicago` (Turabian cover page) or `mla` (MLA header)
- **bibliography**: path to `.bib` file (enables `--citeproc` during export)
- **csl**: path to `.*csl` file

#### Export (palette only)
This feature uses pandoc and libreoffice in the background to produce a .pdf formatted for submission in academic contexts. Pulling from the frontmatter, pandoc shapes your .md into a .docx formatted according to either Chicago style (with a title page containing your title, author, instructor, and date and page numbers centered in the footer with the final word of the author field appended to the front) or MLA (with a header on the first page according to MLA standards and page numbers on the top right). These can be either single- or double-spaced. Then, if you selected the .pdf output, it will use libreoffice to headlessly convert the .docx into a .pdf. You can either print or share these outputs from the exports screen.

<img width="800" height="480" alt="manuscripts-20260228-142034" src="https://github.com/user-attachments/assets/4f384f4b-a83a-4be2-9756-85f80e8832d2" />

### Exports view

<img width="800" height="480" alt="manuscripts-20260228-142013" src="https://github.com/user-attachments/assets/83295ced-4761-45eb-affe-ccf7b25f52c4" />

<img width="800" height="480" alt="manuscripts-20260228-142015" src="https://github.com/user-attachments/assets/2801a450-518c-447f-8019-1ad09c9d6e1a" />

### Keyboard shortcuts in short

#### Projects

| Key | Action              |
| --- | ------------------- |
| n   | New entry           |
| r   | Rename entry        |
| d   | Delete entry        |
| c   | Duplicate entry     |
| e   | Toggle exports view |
| /   | Focus search        |
| Ctrl+S (x2) | Shut down        |

#### Editor

| Key      | Action                               |
| -------- | ------------------------------------ |
| Ctrl+B   | Bold                                 |
| Ctrl+F   | Find/Replace                         |
| Ctrl+G   | Toggle keybindings panel             |
| Ctrl+I   | Italic                               |
| Ctrl+N   | Insert blank footnote (`^[]`)        |
| Ctrl+O   | Citation manager                     |
| Ctrl+P   | Command palette                      |
| Ctrl+R   | Insert citation                      |
| Ctrl+S   | Save                                 |
| Ctrl+W   | Toggle word/paragraph count          |
| Esc (x2) | Return to file browser               |
