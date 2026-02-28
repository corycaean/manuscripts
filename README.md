README UNDER CONSTRUCTION

# Manuscripts---a writing appliance for students

## About
I designed Manuscripts for high school students. As a student myself, and now as a teacher, the aspect of writing that has puzzled me the most is the relative lack of  talk about the tools that constrain the process. No one, I think, ranks Microsoft Word as a well-designed tool (and I personally hate it [as much as Charlie Stross does](https://www.antipope.org/charlie/blog-static/2013/10/why-microsoft-word-must-die.html)). The tools that ape its design---Google Docs, Apple Pages, LibreOffice---fare little better. The what-you-see-is-what-you-get text editor exists in a perpetual and probably inevitable state of bland badness. The reason is simple: their interfaces are complex, confusing, and ultimately not aimed at document *composition* so much as document *design*.

There's a place for that, but the longer I teach the more I am persuaded that the classroom is not that place. My job as a teacher is to convey the skills I have: research and formatting, yes, but also brainstorming, organization, prose construction and revision, citation; or, in the language of antiquity and the middle ages: invention, arrangement, and style. If I can teach kids those skills, and so to write and write well, those skills are transferable into any software.

Until now, one of the most significant hurdles to teaching those skills has been the tools that my students want to use. They insist that they have to learn Google Docs, Microsoft Word, and the like "as preparation for the future", and they grow frustrated when teachers insist that their problem is not an inability to use those tools to their fullest extent but their inability to write. Now especially, with the advent of the integration of the large language model, the what-you-see-is-what-you-get text editor has added document *production* (as distinct from *composition*) to *design*. Ironically, its aim has become to allow users to churn out beautifully designed and grammatically correct documents in whose creation they had almost no agency.

Thus, Manuscripts was born. Designed to facilitate the transmission of the skills of invention, arrangement, and style, it is barebones in the best way. It depends upon Markdown, the plaintext syntax that offers everything needed for digital composition in a lightweight, portable format. Using my own training in research and composition, I designed a lightweight citation manager that teaches students to rely on sources without overwhelming them. Finally, Manuscripts has an export pipeline dependent on open source and free software that gives students the properly, academically formatted .pdf they need without wasting their time formatting. Since they don't have to bear the cognitive load of *design*, they can focus their energy on *composition*.

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
- fonts-jetbrains-mono
- ttf-mscorefonts-installer

## First-time use

```bash
git clone https://github.com/charleskcisco/manuscripts.git
chmod +x setup.sh run.sh
./setup.sh     # creates venv, installs prompt_toolkit and other dependencies
./run.sh       # launches manuscripts
```

## Specifics
Manuscripts has a few views, each of which offers distinct features.

- Manuscripts opens into the Projects view, which contains a searchable list of all projects. From there, students can either perform various operations on their projects (rename, pin to the top of the list, etc, on which more below), open a project in the editor view, or share exported project .pdf, .docx, or .md files (again, on which more below).
- Once the student enters the Editor view, he or she may edit documents using the ever-flexible the markdown syntax. They may also use ctrl+p to summon a command palette, from which they can access a host of features.
- Finally, in the Exports view, students may view projects they have exported and either print them or share them via a companion app running on their (or their instructor's) PC.

Let me talk about these surfaces and their features in more detail.

### Projects view

<img width="800" height="480" alt="manuscripts-20260228-142007" src="https://github.com/user-attachments/assets/e2fa5435-c00c-4049-b275-ee8a27633cb2" />

#### Search
At first, this isn't useful, but a fuzzy search that allows students to find old projects seems to me an essential addition. If they use Manuscripts over a number of years and classes, this becomes invaluable.

#### Pin
This feature allows students to pin favorite or current projects to the top of their lists, for quick access and editing.

#### Shut down (ctrl+s *from the Projects screen*)
Manuscripts is designed to be the writerdeck OS, if you want to think about it with that metaphor in mind. Students might spend all of their time with this device in this app. For simplicity's sake, I wanted them to be able to shut down without exiting to CLI, so I set up a double press of ctrl+s to do the job. (*N*.*b*., this only works if they have auto-login set up on their device, because all it does is run 'sudo shutdown now'. 

#### (Go to) Exports 
This sends the student to the Exports view, on which more below.

### Editor view

<img width="800" height="480" alt="manuscripts-20260228-142026" src="https://github.com/user-attachments/assets/f56942d7-2381-40bb-991e-039ea3a3c704" />

#### Invoke command palette
The first and most important feature of the Editor view is the command palette, pictured below:

<img width="800" height="480" alt="manuscripts-20260228-142032" src="https://github.com/user-attachments/assets/a6bf8ddf-37dc-4c2d-b6de-463b9ab68ef4" />

From the command palette, students can perform a number of functions and document manipulations.

#### Keybindings guide (ctrl+g)---the epitome of boring, as most essential things are
This opens a panel on the right that serves as a guide for the app keybindings. It can stay open as one edits as a reference if needed.

<img width="800" height="480" alt="manuscripts-20260228-142109" src="https://github.com/user-attachments/assets/d6225041-0613-47a3-824c-fdf2c5cd5394" />

#### Copy (ctrl+c)/Cut (ctrl+x)/Paste (ctrl+v)/Undo (ctrl+z)/Redo (ctrl+y)
These work as expected, but their implementation is worth mentioning explicitly.

#### Bold (ctrl+b) and italicize (ctrl+i)
Markdown is a plain text language that handles **bold**, *italics*, ***or a combination of the pair*** via enclosing words in asterisks. These bindings just place the appropriate number thereof around the word in which your cursor is currently resting or around your selection.

#### Go to top (ctrl+up) or bottom (ctrl+down)
By design, Manuscripts places the cursor on the first line after any frontmatter. These bindings can move it either to the very top of the document or (probably more usefully) to its last line, so students can pick up where they left off.

#### Toggle word and paragraph count (ctrl+w)
Word counts are perhaps a necessary evil, but they can prompt some really poor behavior from bad writers who need to hit them. Sometimes, therefore, it's helpful to measure the number of rounded, complete, coherent sets of thought produced. The paragraph count is the tool for that latter goal. The user may also toggle either off, to focus on writing without reliance on metrics.

#### Find and/or replace (ctrl+f)
Manuscripts offers a relatively robust find and replace feature. Ctrl+f summons a panel in which the user may type a particular word. At that point, he or she has a choice. Enter will move focus into the editor pane and highlight the term sought. Students can cycle through results with ctrl+k (next) and ctrl+j (previous), or they can return to the find panel with ctrl+f, from which they can then also replace that search term or replace every instance of it in the document.

<img width="800" height="480" alt="manuscripts-20260228-142044" src="https://github.com/user-attachments/assets/5c8ab3b1-538c-4187-873c-0b10fcd99017" />


#### Spell check (palette only)
Using aspell, students can check their document for misspelled words. It follows the logic of the find/replace dialogue; when triggered, it scans the whole document and runs through misspellings one at a time, highlighting them in red, suggesting replacements, and offering options to skip or add to dictionary.

<img width="800" height="480" alt="manuscripts-20260228-142056" src="https://github.com/user-attachments/assets/27d1c786-0aff-4c74-9255-8e96082e630f" />

#### Return to Projects (esc)
Pressing escape (twice to prevent accidental activation) returns the user to the Projects screen.

#### Insert blank footnote (ctrl+n)
The next three features are related. First, ctrl+n offers a quick and frictionless way to insert an inline markdown footnote.

#### Source management (ctrl+o)
Manuscripts has a built-in citation manager that will open a modal where students may enter and manage works on a per project basis (though you can also import citations from other projects as well). The types of sources supported at present are books, book sections, articles, and websites.

<img width="800" height="480" alt="manuscripts-20260228-142127" src="https://github.com/user-attachments/assets/51067aba-6ebb-4ac8-9575-9422c633e8a4" />

<img width="800" height="480" alt="manuscripts-20260228-142132" src="https://github.com/user-attachments/assets/19358271-a25f-43b1-8439-56efd0d49d9b" />

#### Search for and insert citation (ctrl+r)
This will open a pop-up from which students can fuzzy search their projects' sources and insert a full footnote citation.

<img width="800" height="480" alt="manuscripts-20260228-142155" src="https://github.com/user-attachments/assets/c302be8b-0dfb-4e6e-a2be-c8b03d6729f6" />

<img width="800" height="480" alt="manuscripts-20260228-142158" src="https://github.com/user-attachments/assets/9777e23c-ed0c-4c74-8119-f1541ead27ae" />

#### Insert bibliography (palette only)
This option, which can be triggered from the palette, inserts a bibliography of all of the projects's sources.

#### Insert frontmatter (palette only)
This will insert at the top of the document the frontmatter relevant to the export function. I reckon title, author, instructor, and date are pretty self-explanatory. Style accepts one of two case sensitive inputs: "chicago" and "mla". Spacing, likewise, accepts "single" or "double". You can also add your own frontmatter elements, the most relevant of which might be "bibliography", "csl", and "tags". Now to talk about the final feature in this section.

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
This feature uses Pandoc and LibreOffice in the background to produce a .pdf formatted for submission in academic contexts. Pulling from the frontmatter, pandoc shapes the .md into a .docx formatted according to either Chicago style (with a title page containing the title, author, instructor, and date and page numbers centered in the footer with the final word of the author field appended to the front) or MLA (with a header on the first page according to MLA standards and page numbers on the top right). These can be either single- or double-spaced. Then, if the student selected the .pdf output, it will use LibreOffice to headlessly convert the .docx into a .pdf. Users can either print or share these outputs from the exports screen.

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
| Ctrl+Down | Go to bottom of document            |
| Ctrl+F   | Find/Replace                         |
| Ctrl+G   | Toggle keybindings panel             |
| Ctrl+I   | Italic                               |
| Ctrl+N   | Insert blank footnote (`^[]`)        |
| Ctrl+O   | Citation manager                     |
| Ctrl+P   | Command palette                      |
| Ctrl+R   | Insert citation                      |
| Ctrl+S   | Save                                 |
| Ctrl+Up  | Go to top of document                |
| Ctrl+W   | Toggle word/paragraph count          |
| Esc (x2) | Return to file browser               |
