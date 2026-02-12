#!/usr/bin/env python3
"""
Manuscripts — A writing appliance for students.

A Markdown editor with integrated source management, Chicago citation
insertion, and PDF export.  Built on Textual.

Designed for write-decks running on Raspberry Pi, but works anywhere
Python 3.9+ and a modern terminal are available.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable, Optional

from textual import on, work
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.command import DiscoveryHit, Hit, Hits, Provider
from textual.containers import Horizontal, ScrollableContainer, Vertical, VerticalScroll
from textual.reactive import reactive, var
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Input,
    Label,
    ListItem,
    ListView,
    OptionList,
    Static,
    TextArea,
)
from textual.widgets.option_list import Option
from textual.widgets.text_area import TextAreaTheme

from rich.style import Style

# ════════════════════════════════════════════════════════════════════════
#  Data Models
# ════════════════════════════════════════════════════════════════════════


@dataclass
class Source:
    """A bibliographic source with simplified metadata."""

    id: str
    source_type: str  # book | book_section | article | website
    author: str
    title: str
    year: str
    # Book
    publisher: str = ""
    city: str = ""
    # Article
    journal: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    # Book section (chapter in edited book)
    book_title: str = ""
    editor: str = ""
    # Website
    url: str = ""
    access_date: str = ""
    site_name: str = ""

    # ── Citation formatting (Chicago / Turabian) ──────────────────────

    def to_citekey(self) -> str:
        last = self.author.split(",")[0].split()[-1].lower() if self.author else "unknown"
        return re.sub(r"[^a-z]", "", last) + self.year

    def to_chicago_footnote(self, page: str = "") -> str:
        a = self._author_first()
        if self.source_type == "book":
            c = f"{a}, *{self.title}*"
            if self.publisher:
                c += f" ({self.publisher}, {self.year})"
            elif self.year:
                c += f" ({self.year})"
            if page:
                c += f", {page}"
            return c + "."
        if self.source_type == "article":
            c = f'{a}, "{self.title}," *{self.journal}*'
            if self.volume:
                c += f" {self.volume}"
                if self.issue:
                    c += f", no. {self.issue}"
            if self.year:
                c += f" ({self.year})"
            if self.pages:
                c += f": {self.pages}"
            elif page:
                c += f": {page}"
            return c + "."
        if self.source_type == "book_section":
            c = f'{a}, "{self.title}," in *{self.book_title}*'
            if self.editor:
                c += f", ed. {self.editor}"
            if self.publisher:
                c += f" ({self.publisher}, {self.year})"
            elif self.year:
                c += f" ({self.year})"
            if self.pages:
                c += f", {self.pages}"
            elif page:
                c += f", {page}"
            return c + "."
        if self.source_type == "website":
            c = f'{a}, "{self.title},"'
            if self.site_name:
                c += f" *{self.site_name}*,"
            if self.access_date:
                c += f" accessed {self.access_date},"
            if self.url:
                c += f" {self.url}"
            return c.rstrip(",") + "."
        return f"{a}, *{self.title}* ({self.year})."

    def to_chicago_bibliography(self) -> str:
        a = self._author_last()
        if self.source_type == "book":
            c = f"{a}. *{self.title}*."
            if self.publisher:
                c += f" {self.publisher}, {self.year}."
            elif self.year:
                c += f" {self.year}."
            return c
        if self.source_type == "article":
            c = f'{a}. "{self.title}." *{self.journal}*'
            if self.volume:
                c += f" {self.volume}"
                if self.issue:
                    c += f", no. {self.issue}"
            if self.year:
                c += f" ({self.year})"
            if self.pages:
                c += f": {self.pages}"
            return c + "."
        if self.source_type == "book_section":
            c = f'{a}. "{self.title}." In *{self.book_title}*'
            if self.editor:
                c += f", edited by {self.editor}"
            if self.pages:
                c += f", {self.pages}"
            c += "."
            if self.publisher:
                c += f" {self.publisher}, {self.year}."
            elif self.year:
                c += f" {self.year}."
            return c
        if self.source_type == "website":
            c = f'{a}. "{self.title}."'
            if self.site_name:
                c += f" *{self.site_name}*."
            if self.access_date:
                c += f" Accessed {self.access_date}."
            if self.url:
                c += f" {self.url}."
            return c
        return f"{a}. *{self.title}*. {self.year}."

    # ── helpers ────────────────────────────────────────────────────────

    def _author_first(self) -> str:
        """First Last (for footnotes)."""
        if not self.author:
            return ""
        if "," in self.author:
            last, first = self.author.split(",", 1)
            return f"{first.strip()} {last.strip()}"
        return self.author

    def _author_last(self) -> str:
        """Last, First (for bibliography)."""
        if not self.author:
            return ""
        if "," not in self.author:
            parts = self.author.rsplit(" ", 1)
            if len(parts) == 2:
                return f"{parts[1]}, {parts[0]}"
        return self.author


@dataclass
class Project:
    """A writing project."""

    id: str
    name: str
    created: str
    modified: str
    content: str = ""
    sources: list = field(default_factory=list)

    def get_sources(self) -> list[Source]:
        out: list[Source] = []
        for s in self.sources:
            try:
                out.append(Source(**s))
            except TypeError:
                continue
        return out

    def add_source(self, source: Source) -> None:
        self.sources.append(asdict(source))

    def remove_source(self, source_id: str) -> None:
        self.sources = [s for s in self.sources if s.get("id") != source_id]


# ════════════════════════════════════════════════════════════════════════
#  Storage
# ════════════════════════════════════════════════════════════════════════


class Storage:
    def __init__(self, base: Path) -> None:
        self.base = base
        self.projects_dir = base / "projects"
        self.exports_dir = base / "exports"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)

    def list_projects(self) -> list[Project]:
        projects: list[Project] = []
        for p in self.projects_dir.glob("*.json"):
            try:
                with open(p) as f:
                    projects.append(Project(**json.load(f)))
            except (json.JSONDecodeError, TypeError, KeyError):
                continue
        return sorted(projects, key=lambda x: x.modified, reverse=True)

    def save_project(self, project: Project) -> None:
        project.modified = datetime.now().isoformat()
        with open(self.projects_dir / f"{project.id}.json", "w") as f:
            json.dump(asdict(project), f, indent=2)

    def load_project(self, pid: str) -> Optional[Project]:
        path = self.projects_dir / f"{pid}.json"
        if path.exists():
            with open(path) as f:
                return Project(**json.load(f))
        return None

    def delete_project(self, pid: str) -> None:
        path = self.projects_dir / f"{pid}.json"
        if path.exists():
            path.unlink()

    def create_project(self, name: str) -> Project:
        pid = datetime.now().strftime("%Y%m%d_%H%M%S")
        now = datetime.now().isoformat()
        p = Project(id=pid, name=name, created=now, modified=now)
        self.save_project(p)
        return p


# ════════════════════════════════════════════════════════════════════════
#  PDF Export Helpers
# ════════════════════════════════════════════════════════════════════════

_REFS_DIR = Path(__file__).resolve().parent / "refs"
_DEFAULT_SPACING = "double"


def parse_yaml_frontmatter(content: str) -> dict:
    """Extract key:value pairs from YAML frontmatter fenced by ---."""
    m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return {}
    yaml: dict[str, str] = {}
    for line in m.group(1).split("\n"):
        idx = line.find(":")
        if idx > 0:
            key = line[:idx].strip()
            val = line[idx + 1 :].strip()
            # Strip surrounding quotes
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            yaml[key] = val
    return yaml


def resolve_reference_doc(yaml: dict) -> Optional[Path]:
    """Return path to the reference .docx for pandoc, or None."""
    if not _REFS_DIR.is_dir():
        return None
    # Explicit spacing: field
    if yaml.get("spacing"):
        p = _REFS_DIR / (yaml["spacing"] + ".docx")
        if p.exists():
            return p
    # Default
    p = _REFS_DIR / (_DEFAULT_SPACING + ".docx")
    if p.exists():
        return p
    # Any .docx
    for p in sorted(_REFS_DIR.glob("*.docx")):
        return p
    return None


def detect_pandoc() -> Optional[str]:
    """Find the pandoc binary."""
    found = shutil.which("pandoc")
    if found:
        return found
    for p in [
        "/usr/local/bin/pandoc",
        "/opt/homebrew/bin/pandoc",
        "/usr/bin/pandoc",
        "/snap/bin/pandoc",
    ]:
        if os.path.isfile(p):
            return p
    return None


def detect_libreoffice() -> Optional[str]:
    """Find the LibreOffice/soffice binary."""
    if sys.platform == "darwin":
        candidates = [
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
            "/usr/local/bin/soffice",
        ]
    else:
        candidates = [
            "/usr/bin/libreoffice",
            "/usr/bin/soffice",
            "/usr/local/bin/libreoffice",
            "/snap/bin/libreoffice",
        ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return shutil.which("libreoffice") or shutil.which("soffice")


# ── Lua filter generators ─────────────────────────────────────────────


def _lua_bib_entry_xml() -> str:
    """Lua snippet: convert a Para block to a hanging-indent OpenXML raw block.

    Walks each inline element so that Emph (italic) and Strong (bold)
    formatting survive into the OpenXML output – fixing the bug where
    ``pandoc.utils.stringify`` stripped all markup from bibliography entries.
    """
    return """
local function escape_xml(s)
  s = s:gsub("&", "&amp;")
  s = s:gsub("<", "&lt;")
  s = s:gsub(">", "&gt;")
  return s
end

local function inlines_to_openxml(inlines)
  local runs = {}
  for _, inl in ipairs(inlines) do
    if inl.t == "Emph" then
      local txt = escape_xml(pandoc.utils.stringify(inl))
      table.insert(runs, string.format(
        '<w:r><w:rPr><w:i/><w:iCs/></w:rPr><w:t xml:space="preserve">%s</w:t></w:r>', txt))
    elseif inl.t == "Strong" then
      local txt = escape_xml(pandoc.utils.stringify(inl))
      table.insert(runs, string.format(
        '<w:r><w:rPr><w:b/><w:bCs/></w:rPr><w:t xml:space="preserve">%s</w:t></w:r>', txt))
    elseif inl.t == "Str" then
      table.insert(runs, string.format(
        '<w:r><w:t xml:space="preserve">%s</w:t></w:r>', escape_xml(inl.text)))
    elseif inl.t == "Space" then
      table.insert(runs, '<w:r><w:t xml:space="preserve"> </w:t></w:r>')
    elseif inl.t == "SoftBreak" or inl.t == "LineBreak" then
      table.insert(runs, '<w:r><w:t xml:space="preserve"> </w:t></w:r>')
    elseif inl.t == "Link" then
      local txt = escape_xml(pandoc.utils.stringify(inl))
      table.insert(runs, string.format(
        '<w:r><w:t xml:space="preserve">%s</w:t></w:r>', txt))
    else
      local txt = escape_xml(pandoc.utils.stringify(inl))
      if txt ~= "" then
        table.insert(runs, string.format(
          '<w:r><w:t xml:space="preserve">%s</w:t></w:r>', txt))
      end
    end
  end
  return table.concat(runs)
end

local function bib_entry_block(block)
  local runs_xml = inlines_to_openxml(block.content)
  return pandoc.RawBlock('openxml', string.format([[
<w:p>
  <w:pPr>
    <w:spacing w:after="0" w:line="480" w:lineRule="auto"/>
    <w:ind w:left="720" w:hanging="720"/>
  </w:pPr>
  %s
</w:p>]], runs_xml))
end

local function is_bib_heading(block)
  if block.t ~= "Header" then return false end
  local text = pandoc.utils.stringify(block)
  return text:match("Bibliography") or text:match("References") or text:match("Works Cited")
end
"""


def _lua_basic_filter() -> str:
    """Page break before Bibliography heading + hanging indent for entries."""
    return _lua_bib_entry_xml() + """
function Pandoc(doc)
  local new_blocks = {}
  local in_bib = false
  for i, block in ipairs(doc.blocks) do
    if is_bib_heading(block) then
      in_bib = true
      table.insert(new_blocks, pandoc.RawBlock('openxml', string.format([[
<w:p>
  <w:pPr>
    <w:pStyle w:val="Heading%d"/>
    <w:pageBreakBefore/>
  </w:pPr>
  <w:r>
    <w:t>%s</w:t>
  </w:r>
</w:p>]], block.level, pandoc.utils.stringify(block))))
    elseif in_bib and block.t == "Header" then
      in_bib = false
      table.insert(new_blocks, block)
    elseif in_bib and block.t == "Para" then
      table.insert(new_blocks, bib_entry_block(block))
    else
      table.insert(new_blocks, block)
    end
  end
  doc.blocks = new_blocks
  return doc
end"""


def _lua_coverpage_filter(yaml: dict) -> str:
    """Turabian-style cover page via OpenXML raw blocks."""
    title = yaml.get("title", "").replace('"', '\\"')
    author = yaml.get("author", "").replace('"', '\\"')
    course = yaml.get("course", "").replace('"', '\\"')
    instructor = yaml.get("instructor", "").replace('"', '\\"')
    date = yaml.get("date", "").replace('"', '\\"')

    return _lua_bib_entry_xml() + f"""-- Cover page format (Turabian style)
local meta_title = "{title}"
local meta_author = "{author}"
local meta_course = "{course}"
local meta_instructor = "{instructor}"
local meta_date = "{date}"

local function format_date(date_str)
  local months = {{
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
  }}
  local year, month, day = date_str:match("(%d+)-(%d+)-(%d+)")
  if year and month and day then
    local month_name = months[tonumber(month)]
    if month_name then
      return string.format("%s %d, %s", month_name, tonumber(day), year)
    end
  end
  return date_str
end

function Meta(meta)
  if meta.title and meta_title == "" then
    meta_title = pandoc.utils.stringify(meta.title)
  end
  if meta.author and meta_author == "" then
    meta_author = pandoc.utils.stringify(meta.author)
  end
  if meta.course and meta_course == "" then
    meta_course = pandoc.utils.stringify(meta.course)
  end
  if meta.instructor and meta_instructor == "" then
    meta_instructor = pandoc.utils.stringify(meta.instructor)
  end
  if meta.date and meta_date == "" then
    meta_date = pandoc.utils.stringify(meta.date)
  end
  meta.author = nil
  meta.date = nil
  meta.title = nil
  meta.course = nil
  meta.instructor = nil
  return meta
end

function Pandoc(doc)
  local new_blocks = {{}}

  if meta_title and meta_title ~= "" then
    table.insert(new_blocks, pandoc.RawBlock('openxml', string.format([[
<w:p>
  <w:pPr>
    <w:spacing w:before="2400" w:after="0" w:line="480" w:lineRule="auto"/>
    <w:jc w:val="center"/>
  </w:pPr>
  <w:r>
    <w:t>%s</w:t>
  </w:r>
</w:p>]], meta_title)))
  end

  local gap_before_author = 4320
  local first_info = true

  if meta_author and meta_author ~= "" then
    local spacing_before = first_info and gap_before_author or 0
    first_info = false
    table.insert(new_blocks, pandoc.RawBlock('openxml', string.format([[
<w:p>
  <w:pPr>
    <w:spacing w:before="%d" w:after="0" w:line="480" w:lineRule="auto"/>
    <w:jc w:val="center"/>
  </w:pPr>
  <w:r>
    <w:t>%s</w:t>
  </w:r>
</w:p>]], spacing_before, meta_author)))
  end

  if meta_course and meta_course ~= "" then
    local spacing_before = first_info and gap_before_author or 0
    first_info = false
    table.insert(new_blocks, pandoc.RawBlock('openxml', string.format([[
<w:p>
  <w:pPr>
    <w:spacing w:before="%d" w:after="0" w:line="480" w:lineRule="auto"/>
    <w:jc w:val="center"/>
  </w:pPr>
  <w:r>
    <w:t>%s</w:t>
  </w:r>
</w:p>]], spacing_before, meta_course)))
  end

  if meta_instructor and meta_instructor ~= "" then
    local spacing_before = first_info and gap_before_author or 0
    first_info = false
    table.insert(new_blocks, pandoc.RawBlock('openxml', string.format([[
<w:p>
  <w:pPr>
    <w:spacing w:before="%d" w:after="0" w:line="480" w:lineRule="auto"/>
    <w:jc w:val="center"/>
  </w:pPr>
  <w:r>
    <w:t>%s</w:t>
  </w:r>
</w:p>]], spacing_before, meta_instructor)))
  end

  if meta_date and meta_date ~= "" then
    local formatted_date = format_date(meta_date)
    local spacing_before = first_info and gap_before_author or 0
    first_info = false
    table.insert(new_blocks, pandoc.RawBlock('openxml', string.format([[
<w:p>
  <w:pPr>
    <w:spacing w:before="%d" w:after="0" w:line="480" w:lineRule="auto"/>
    <w:jc w:val="center"/>
  </w:pPr>
  <w:r>
    <w:t>%s</w:t>
  </w:r>
</w:p>]], spacing_before, formatted_date)))
  end

  local page_break_inserted = false
  local in_bib = false
  for i, block in ipairs(doc.blocks) do
    if is_bib_heading(block) then
      in_bib = true
      if not page_break_inserted then
        page_break_inserted = true
      end
      table.insert(new_blocks, pandoc.RawBlock('openxml', string.format([[
<w:p>
  <w:pPr>
    <w:pStyle w:val="Heading%d"/>
    <w:pageBreakBefore/>
  </w:pPr>
  <w:r>
    <w:t>%s</w:t>
  </w:r>
</w:p>]], block.level, pandoc.utils.stringify(block))))
    elseif in_bib and block.t == "Header" then
      in_bib = false
      table.insert(new_blocks, block)
    elseif in_bib and block.t == "Para" then
      table.insert(new_blocks, bib_entry_block(block))
    else
      if not page_break_inserted then
        if block.t == "Header" or
           (block.t == "Para" and #block.content > 0) or
           block.t == "CodeBlock" or
           block.t == "BulletList" or
           block.t == "OrderedList" or
           block.t == "Table" or
           block.t == "BlockQuote" or
           block.t == "RawBlock" then
          table.insert(new_blocks, pandoc.RawBlock('openxml', [[
<w:p>
  <w:pPr>
    <w:pageBreakBefore/>
  </w:pPr>
</w:p>]]))
          page_break_inserted = true
        end
      end
      table.insert(new_blocks, block)
    end
  end

  if not page_break_inserted then
    table.insert(new_blocks, pandoc.RawBlock('openxml', [[
<w:p>
  <w:pPr>
    <w:pageBreakBefore/>
  </w:pPr>
</w:p>]]))
  end

  doc.blocks = new_blocks
  return doc
end"""


def _lua_header_filter(yaml: dict) -> str:
    """MLA-style header block via OpenXML raw blocks."""
    title = yaml.get("title", "").replace('"', '\\"')
    author = yaml.get("author", "").replace('"', '\\"')
    course = yaml.get("course", "").replace('"', '\\"')
    instructor = yaml.get("instructor", "").replace('"', '\\"')
    date = yaml.get("date", "").replace('"', '\\"')

    return _lua_bib_entry_xml() + f"""-- MLA Header format
local meta_title = "{title}"
local meta_author = "{author}"
local meta_course = "{course}"
local meta_instructor = "{instructor}"
local meta_date = "{date}"

local function format_date(date_str)
  local months = {{
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
  }}
  local year, month, day = date_str:match("(%d+)-(%d+)-(%d+)")
  if year and month and day then
    local month_name = months[tonumber(month)]
    if month_name then
      return string.format("%d %s %s", tonumber(day), month_name, year)
    end
  end
  return date_str
end

function Meta(meta)
  if meta.title and meta_title == "" then
    meta_title = pandoc.utils.stringify(meta.title)
  end
  if meta.author and meta_author == "" then
    meta_author = pandoc.utils.stringify(meta.author)
  end
  if meta.course and meta_course == "" then
    meta_course = pandoc.utils.stringify(meta.course)
  end
  if meta.instructor and meta_instructor == "" then
    meta_instructor = pandoc.utils.stringify(meta.instructor)
  end
  if meta.date and meta_date == "" then
    meta_date = pandoc.utils.stringify(meta.date)
  end
  meta.author = nil
  meta.date = nil
  meta.title = nil
  meta.course = nil
  meta.instructor = nil
  return meta
end

function Pandoc(doc)
  local new_blocks = {{}}

  if meta_author and meta_author ~= "" then
    table.insert(new_blocks, pandoc.RawBlock('openxml', string.format([[
<w:p>
  <w:pPr>
    <w:spacing w:after="0" w:line="480" w:lineRule="auto"/>
  </w:pPr>
  <w:r>
    <w:t>%s</w:t>
  </w:r>
</w:p>]], meta_author)))
  end

  if meta_instructor and meta_instructor ~= "" then
    table.insert(new_blocks, pandoc.RawBlock('openxml', string.format([[
<w:p>
  <w:pPr>
    <w:spacing w:after="0" w:line="480" w:lineRule="auto"/>
  </w:pPr>
  <w:r>
    <w:t>%s</w:t>
  </w:r>
</w:p>]], meta_instructor)))
  end

  if meta_course and meta_course ~= "" then
    table.insert(new_blocks, pandoc.RawBlock('openxml', string.format([[
<w:p>
  <w:pPr>
    <w:spacing w:after="0" w:line="480" w:lineRule="auto"/>
  </w:pPr>
  <w:r>
    <w:t>%s</w:t>
  </w:r>
</w:p>]], meta_course)))
  end

  if meta_date and meta_date ~= "" then
    local formatted_date = format_date(meta_date)
    table.insert(new_blocks, pandoc.RawBlock('openxml', string.format([[
<w:p>
  <w:pPr>
    <w:spacing w:after="0" w:line="480" w:lineRule="auto"/>
  </w:pPr>
  <w:r>
    <w:t>%s</w:t>
  </w:r>
</w:p>]], formatted_date)))
  end

  if meta_title and meta_title ~= "" then
    table.insert(new_blocks, pandoc.RawBlock('openxml', string.format([[
<w:p>
  <w:pPr>
    <w:spacing w:after="0" w:line="480" w:lineRule="auto"/>
    <w:jc w:val="center"/>
  </w:pPr>
  <w:r>
    <w:t>%s</w:t>
  </w:r>
</w:p>]], meta_title)))
  end

  local in_bib = false
  for i, block in ipairs(doc.blocks) do
    if is_bib_heading(block) then
      in_bib = true
      table.insert(new_blocks, pandoc.RawBlock('openxml', string.format([[
<w:p>
  <w:pPr>
    <w:pStyle w:val="Heading%d"/>
    <w:pageBreakBefore/>
  </w:pPr>
  <w:r>
    <w:t>%s</w:t>
  </w:r>
</w:p>]], block.level, pandoc.utils.stringify(block))))
    elseif in_bib and block.t == "Header" then
      in_bib = false
      table.insert(new_blocks, block)
    elseif in_bib and block.t == "Para" then
      table.insert(new_blocks, bib_entry_block(block))
    else
      table.insert(new_blocks, block)
    end
  end

  doc.blocks = new_blocks
  return doc
end"""


def _generate_lua_filter(yaml: dict) -> str:
    """Dispatch to the right Lua filter based on style: field."""
    fmt = yaml.get("style", "")
    if fmt == "chicago":
        return _lua_coverpage_filter(yaml)
    if fmt == "mla":
        return _lua_header_filter(yaml)
    return _lua_basic_filter()


# ── DOCX post-processing ──────────────────────────────────────────────

_EMPTY_HEADER_XML = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:p>
    <w:pPr>
      <w:pStyle w:val="Header"/>
    </w:pPr>
  </w:p>
</w:hdr>"""

_EMPTY_FOOTER_XML = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:p>
    <w:pPr>
      <w:pStyle w:val="Footer"/>
    </w:pPr>
  </w:p>
</w:ftr>"""


def _postprocess_docx(docx_path: str, yaml: dict) -> None:
    """Strip headers/footers and replace {{LASTNAME}} in DOCX zip."""
    fmt = yaml.get("style", "")
    strip_headers = fmt != "mla"  # strip for chicago or blank
    strip_footers = fmt == "mla"  # strip only for mla format

    # Determine lastname replacement
    author = yaml.get("author", "")
    lastname = yaml.get("lastname", "")
    if not lastname and author:
        lastname = author.split()[-1] if author.split() else ""

    buf = io.BytesIO()
    with zipfile.ZipFile(docx_path, "r") as zin:
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                is_header = re.match(r"word/header\d*\.xml", item.filename)
                is_footer = re.match(r"word/footer\d*\.xml", item.filename)

                if strip_headers and is_header:
                    data = _EMPTY_HEADER_XML
                elif strip_footers and is_footer:
                    data = _EMPTY_FOOTER_XML
                elif is_header or is_footer:
                    # Replace {{LASTNAME}} placeholder
                    text = data.decode("utf-8")
                    if lastname:
                        text = text.replace("{{LASTNAME}} ", lastname + " ")
                        text = text.replace("{{LASTNAME}}", lastname)
                    else:
                        text = text.replace("{{LASTNAME}} ", "")
                        text = text.replace("{{LASTNAME}}", "")
                    data = text.encode("utf-8")
                zout.writestr(item, data)

    with open(docx_path, "wb") as f:
        f.write(buf.getvalue())


# ════════════════════════════════════════════════════════════════════════
#  Helper: fuzzy filter
# ════════════════════════════════════════════════════════════════════════


def fuzzy_filter(sources: list[Source], query: str) -> list[Source]:
    if not query:
        return list(sources)
    q = query.lower()
    scored: list[tuple[float, Source]] = []
    for s in sources:
        hay = f"{s.author} {s.title} {s.year}".lower()
        if q in hay:
            scored.append((100.0, s))
        else:
            ratio = SequenceMatcher(None, q, hay).ratio() * 100
            if ratio > 30:
                scored.append((ratio, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored]


def fuzzy_filter_projects(projects: list[Project], query: str) -> list[Project]:
    if not query:
        return list(projects)
    q = query.lower()
    scored: list[tuple[float, Project]] = []
    for p in projects:
        hay = p.name.lower()
        if q in hay:
            scored.append((100.0, p))
        else:
            ratio = SequenceMatcher(None, q, hay).ratio() * 100
            if ratio > 30:
                scored.append((ratio, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored]


# ════════════════════════════════════════════════════════════════════════
#  Source‑type field definitions
# ════════════════════════════════════════════════════════════════════════

SOURCE_TYPES = ["book", "book_section", "article", "website"]

SOURCE_FIELDS: dict[str, list[tuple[str, str]]] = {
    "book": [
        ("author", "Author (Last, First)"),
        ("title", "Title"),
        ("year", "Year"),
        ("publisher", "Publisher"),
    ],
    "book_section": [
        ("author", "Author (Last, First)"),
        ("title", "Chapter Title"),
        ("book_title", "Book Title"),
        ("editor", "Editor"),
        ("year", "Year"),
        ("publisher", "Publisher"),
        ("pages", "Pages"),
    ],
    "article": [
        ("author", "Author (Last, First)"),
        ("title", "Title"),
        ("year", "Year"),
        ("journal", "Journal"),
        ("volume", "Volume"),
        ("issue", "Issue"),
        ("pages", "Pages"),
    ],
    "website": [
        ("author", "Author (Last, First)"),
        ("title", "Title"),
        ("year", "Year"),
        ("site_name", "Website Name"),
        ("url", "URL"),
        ("access_date", "Access Date"),
    ],
}


# ════════════════════════════════════════════════════════════════════════
#  Screens
# ════════════════════════════════════════════════════════════════════════


# ── Projects ──────────────────────────────────────────────────────────


class ProjectsScreen(Screen):
    """Landing screen: list of manuscripts + exports toggle."""

    BINDINGS = [
        Binding("n", "new_project", "New manuscript"),
        Binding("d", "delete_project", "Delete"),
        Binding("e", "toggle_exports", "Exports"),
        Binding("q", "quit", "Quit", show=False),
    ]

    DEFAULT_CSS = """
    #projects-view {
        height: 1fr;
    }
    #exports-view {
        height: 1fr;
        display: none;
    }
    #exports-title {
        color: #e0e0e0;
        padding: 1 2;
    }
    #export-file-list {
        margin: 1 2;
        height: 1fr;
    }
    #projects-hints {
        dock: bottom;
        height: 1;
        color: #777;
        padding: 0 2;
    }
    #project-search {
        margin: 0 2;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._showing_exports = False
        self._export_paths: list[Path] = []
        self._all_projects: list[Project] = []
        self._filtered_projects: list[Project] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="projects-view"):
            yield Static("Manuscripts", id="projects-title")
            yield Input(placeholder="Search manuscripts...", id="project-search")
            yield OptionList(id="project-list")
            yield Static("(n) New  (d) Delete  (e) Exports", id="projects-hints")
        with Vertical(id="exports-view"):
            yield Static("Exports", id="exports-title")
            yield OptionList(id="export-file-list")

    def on_mount(self) -> None:
        self._load_all_projects()
        self._refresh_list()

    def _load_all_projects(self) -> None:
        """Read projects from disk into cache."""
        app: ManuscriptsApp = self.app  # type: ignore[assignment]
        self._all_projects = app.storage.list_projects()
        app.projects = self._all_projects

    def _refresh_list(self, filter_query: str = "") -> None:
        ol: OptionList = self.query_one("#project-list", OptionList)
        ol.clear_options()
        self._filtered_projects = fuzzy_filter_projects(self._all_projects, filter_query)
        for p in self._filtered_projects:
            try:
                mod = datetime.fromisoformat(p.modified).strftime("%b %d, %Y")
            except (ValueError, TypeError):
                mod = ""
            ol.add_option(Option(f"{p.name}  ({mod})", id=p.id))
        if not self._all_projects:
            ol.add_option(Option("  No manuscripts yet — press n to create one.", id="__empty__"))
        elif not self._filtered_projects:
            ol.add_option(Option("  No matching manuscripts.", id="__empty__"))

    def _refresh_exports(self) -> None:
        ol: OptionList = self.query_one("#export-file-list", OptionList)
        ol.clear_options()
        app: ManuscriptsApp = self.app  # type: ignore[assignment]
        export_dir = app.storage.exports_dir
        files: list[Path] = []
        for ext in ("*.pdf", "*.docx", "*.md"):
            files.extend(export_dir.glob(ext))
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        self._export_paths = files
        if not files:
            ol.add_option(Option("  No exports yet.", id="__empty__"))
        else:
            for f in files:
                try:
                    mod = datetime.fromtimestamp(f.stat().st_mtime).strftime("%b %d, %Y %H:%M")
                except (ValueError, OSError):
                    mod = ""
                size_kb = f.stat().st_size // 1024
                ol.add_option(Option(f"{f.name}  ({mod}, {size_kb} KB)", id=str(f)))

    @on(Input.Changed, "#project-search")
    def _search_changed(self, event: Input.Changed) -> None:
        self._refresh_list(filter_query=event.value)

    def on_key(self, event) -> None:
        """Down arrow in search input moves focus to the project list."""
        if event.key == "down":
            focused = self.app.focused
            search_input = self.query_one("#project-search", Input)
            if focused is search_input:
                ol = self.query_one("#project-list", OptionList)
                ol.focus()
                event.prevent_default()

    @on(OptionList.OptionSelected, "#project-list")
    def open_project(self, event: OptionList.OptionSelected) -> None:
        if event.option_id == "__empty__":
            return
        app: ManuscriptsApp = self.app  # type: ignore[assignment]
        project = app.storage.load_project(event.option_id)
        if project:
            app.push_screen(EditorScreen(project))

    @on(OptionList.OptionSelected, "#export-file-list")
    def open_export(self, event: OptionList.OptionSelected) -> None:
        if event.option_id == "__empty__":
            return
        self._open_file(Path(event.option_id))

    def _open_file(self, path: Path) -> None:
        """Open a file with the system viewer, or print if PDF."""
        if path.suffix.lower() == ".pdf":
            printers = self._detect_printers()
            if printers:
                self.app.push_screen(PrinterPickerModal(printers, path))
                return
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            self.notify(f"Could not open file: {exc}", severity="error")

    @staticmethod
    def _detect_printers() -> list[str]:
        """Return list of available printer names via lpstat."""
        try:
            result = subprocess.run(
                ["lpstat", "-a"], capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0 or not result.stdout.strip():
                return []
            printers: list[str] = []
            for line in result.stdout.strip().splitlines():
                name = line.split()[0] if line.split() else ""
                if name:
                    printers.append(name)
            return printers
        except Exception:
            return []

    def action_new_project(self) -> None:
        if self._showing_exports:
            return
        self.app.push_screen(NewProjectModal(), callback=self._on_project_created)

    def _on_project_created(self, name: str | None) -> None:
        if name:
            app: ManuscriptsApp = self.app  # type: ignore[assignment]
            project = app.storage.create_project(name)
            app.push_screen(EditorScreen(project))

    def action_delete_project(self) -> None:
        if self._showing_exports:
            return
        ol: OptionList = self.query_one("#project-list", OptionList)
        idx = ol.highlighted
        if idx is not None and idx < len(self._filtered_projects):
            project = self._filtered_projects[idx]
            self.app.push_screen(
                ConfirmModal(f"Delete '{project.name}'?"),
                callback=lambda ok: self._do_delete(ok, project.id),
            )

    def _do_delete(self, ok: bool, pid: str) -> None:
        if ok:
            app: ManuscriptsApp = self.app  # type: ignore[assignment]
            app.storage.delete_project(pid)
            self._load_all_projects()
            query = self.query_one("#project-search", Input).value
            self._refresh_list(filter_query=query)
            self.notify("Manuscript deleted.")

    def action_toggle_exports(self) -> None:
        pv = self.query_one("#projects-view")
        ev = self.query_one("#exports-view")
        self._showing_exports = not self._showing_exports
        if self._showing_exports:
            pv.styles.display = "none"
            ev.styles.display = "block"
            self._refresh_exports()
            self.query_one("#export-file-list", OptionList).focus()
        else:
            ev.styles.display = "none"
            pv.styles.display = "block"
            self.query_one("#project-list", OptionList).focus()

    def action_quit(self) -> None:
        self.app.exit()


# ── New‑project modal ─────────────────────────────────────────────────


class NewProjectModal(ModalScreen[str | None]):
    """Prompt for a project name."""

    DEFAULT_CSS = """
    NewProjectModal {
        align: center middle;
    }
    #new-project-box {
        width: 60%;
        max-width: 60;
        height: auto;
        max-height: 12;
        border: solid #666;
        background: $surface;
        padding: 1 2;
    }
    #new-project-box Label {
        margin-bottom: 1;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def compose(self) -> ComposeResult:
        with Vertical(id="new-project-box"):
            yield Label("New Manuscript")
            yield Input(placeholder="Manuscript name…", id="project-name-input")
            with Horizontal():
                yield Button("Create", id="btn-create")
                yield Button("Cancel", id="btn-cancel")

    def on_mount(self) -> None:
        self.query_one("#project-name-input", Input).focus()

    @on(Button.Pressed, "#btn-create")
    def _create(self, event: Button.Pressed) -> None:
        val = self.query_one("#project-name-input", Input).value.strip()
        self.dismiss(val if val else None)

    @on(Button.Pressed, "#btn-cancel")
    def _cancel(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    @on(Input.Submitted, "#project-name-input")
    def _submit(self, event: Input.Submitted) -> None:
        val = event.value.strip()
        self.dismiss(val if val else None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── Confirm modal ─────────────────────────────────────────────────────


class ConfirmModal(ModalScreen[bool]):
    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }
    #confirm-box {
        width: 60%;
        max-width: 60;
        height: auto;
        max-height: 10;
        border: solid #666;
        background: $surface;
        padding: 1 2;
    }
    #confirm-box Label {
        margin-bottom: 1;
    }
    """
    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, question: str) -> None:
        super().__init__()
        self.question = question

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Label(self.question)
            with Horizontal():
                yield Button("Yes", variant="error", id="btn-yes")
                yield Button("No", id="btn-no")

    def on_mount(self) -> None:
        self.query_one("#btn-no", Button).focus()

    @on(Button.Pressed, "#btn-yes")
    def _yes(self, event: Button.Pressed) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#btn-no")
    def _no(self, event: Button.Pressed) -> None:
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)


# ── Editor ────────────────────────────────────────────────────────────

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")


_MANUSCRIPTS_THEME = TextAreaTheme(
    name="manuscripts",
    base_style=Style(color="#e0e0e0", bgcolor="#2a2a2a"),
    cursor_style=Style(color="#2a2a2a", bgcolor="#e0e0e0"),
    cursor_line_style=Style(bgcolor="#333333"),
    selection_style=Style(bgcolor="#444444"),
    syntax_styles={
        "bold": Style(bold=True),
        "italic": Style(italic=True),
        "strikethrough": Style(strike=True),
        "inline_code": Style(color="#a0a0a0", bgcolor="#383838"),
        "heading": Style(bold=True, color="#e0af68"),
        "heading.marker": Style(color="#666666"),
        "link.label": Style(color="#7aa2f7"),
        "link.uri": Style(color="#666666"),
    },
)


class MarkdownTextArea(TextArea):
    """TextArea with combined heading + inline markdown highlighting.

    All inherited TextArea bindings are re-declared as ``system=True``
    so they stay functional but don't clutter the keybindings panel.
    The curated set on EditorScreen is what the user sees instead.
    """

    BINDINGS = [
        Binding(b.key, b.action, b.description, show=False, system=True)
        for b in list(TextArea.BINDINGS) + list(ScrollableContainer.BINDINGS)
    ]

    def _on_key(self, event) -> None:
        if event.key == "escape":
            return  # Let escape bubble up to the screen
        super()._on_key(event)

    def _build_highlight_map(self) -> None:
        super()._build_highlight_map()
        highlights = self._highlights
        for i, line in enumerate(self.text.splitlines()):
            m = _HEADING_RE.match(line)
            if m:
                marker_end = m.end(1)
                highlights[i].append((0, marker_end, "heading.marker"))
                highlights[i].append((marker_end + 1, len(line), "heading"))


class KeybindingsPanel(Static):
    """Custom keybindings panel with grouped sections."""

    DEFAULT_CSS = """
    KeybindingsPanel {
        dock: right;
        width: 26;
        height: 1fr;
        border-left: vkey $foreground 30%;
        padding: 1 1;
        overflow-y: auto;
    }
    """

    def render(self):
        from rich.table import Table
        from rich.text import Text

        key_style = "bold #e0af68"
        hdr_style = "underline"
        desc_style = ""

        tbl = Table(
            show_header=False, box=None, padding=(0, 1), expand=False
        )
        tbl.add_column(justify="right", style=key_style, no_wrap=True)
        tbl.add_column(style=desc_style)

        sections = [
            ("", [
                ("^M", "Manuscripts"),
                ("^O", "Sources"),
                ("^P", "Commands"),
                ("^Q", "Quit"),
                ("^S", "Save"),
            ]),
            ("", [
                ("^B", "Bold"),
                ("^I", "Italic"),
                ("^N", "Footnote"),
                ("^R", "Cite"),
                ("^Z", "Undo"),
                ("^Y", "Redo"),
            ]),
            ("", [
                ("^H", "This panel"),
            ]),
        ]

        for i, (title, bindings) in enumerate(sections):
            if i > 0:
                tbl.add_row("", "")
            if title:
                tbl.add_row("", Text(title, style=hdr_style))
            for key, desc in bindings:
                tbl.add_row(key, desc)

        return tbl


class EditorScreen(Screen):
    """The main writing screen."""

    BINDINGS = [
        # Hide inherited Screen bindings from keybindings panel
        Binding("tab", "app.focus_next", "Focus Next", show=False, system=True),
        Binding("shift+tab", "app.focus_previous", "Focus Previous", show=False, system=True),
        # Functional keybindings (all system=True; display handled by KeybindingsPanel)
        Binding("ctrl+b", "bold", "Bold", system=True),
        Binding("ctrl+c", "noop", "Copy", system=True),
        Binding("ctrl+i", "italic", "Italic", system=True),
        Binding("ctrl+m", "close_project", "Return to manuscripts", system=True),
        Binding("ctrl+n", "footnote", "Insert blank footnote", system=True),
        Binding("ctrl+o", "sources", "Sources", system=True),
        Binding("ctrl+p", "command_palette", "Command Palette", system=True),
        Binding("ctrl+r", "cite", "Insert reference", system=True),
        Binding("ctrl+s", "save", "Save", system=True),
        Binding("ctrl+v", "noop", "Paste", system=True),
        Binding("ctrl+x", "noop", "Cut", system=True),
        Binding("ctrl+z", "noop", "Undo", system=True),
        Binding("ctrl+h", "toggle_help", "Keybindings", system=True),
        Binding("shift+arrows", "noop", "Select text", system=True),
    ]

    AUTO_SAVE_SECONDS = 30.0

    def __init__(self, project: Project) -> None:
        super().__init__()
        self.project = project
        self._dirty = False

    def compose(self) -> ComposeResult:
        yield MarkdownTextArea(
            self.project.content,
            id="editor",
            soft_wrap=True,
            show_line_numbers=False,
            tab_behavior="indent",
        )
        yield Static(self._status_text(), id="editor-status")

    def on_mount(self) -> None:
        ta = self.query_one("#editor", TextArea)
        self._register_markdown_language(ta)
        ta.focus()
        self.set_interval(self.AUTO_SAVE_SECONDS, self._auto_save)

    @staticmethod
    def _register_markdown_language(ta: TextArea) -> None:
        """Register markdown with the inline grammar for bold/italic highlighting."""
        ta.register_theme(_MANUSCRIPTS_THEME)
        ta.theme = "manuscripts"
        try:
            from tree_sitter import Language as TSLanguage
            from tree_sitter_markdown import inline_language
            lang = TSLanguage(inline_language())
            highlight_query = (
                "(strong_emphasis) @bold\n"
                "(emphasis) @italic\n"
                "(strikethrough) @strikethrough\n"
                "(code_span) @inline_code\n"
                "(inline_link (link_text) @link.label)\n"
                "(inline_link (link_destination) @link.uri)\n"
                "(shortcut_link (link_text) @link.label)\n"
                "(full_reference_link (link_text) @link.label)\n"
                "(full_reference_link (link_label) @link.label)\n"
                "(image (image_description) @link.label)\n"
                "(image (link_destination) @link.uri)\n"
            )
            ta.register_language("markdown_inline", lang, highlight_query)
            ta.language = "markdown_inline"
        except ImportError:
            pass

    def _status_text(self) -> str:
        text = self.query_one("#editor", TextArea).text if self.is_mounted else self.project.content
        wc = len(text.split()) if text.strip() else 0
        return f" {self.project.name}  {wc} words"

    @on(TextArea.Changed, "#editor")
    def _on_text_change(self, event: TextArea.Changed) -> None:
        self._dirty = True
        try:
            self.query_one("#editor-status", Static).update(self._status_text())
        except Exception:
            pass

    def _auto_save(self) -> None:
        if not self._dirty:
            return
        self._do_save(notify=False)

    def _do_save(self, notify: bool = True) -> None:
        app: ManuscriptsApp = self.app  # type: ignore[assignment]
        self.project.content = self.query_one("#editor", TextArea).text
        app.storage.save_project(self.project)
        self._dirty = False
        if notify:
            self.notify("Saved.")

    # ── actions ────────────────────────────────────────────────────────

    def action_noop(self) -> None:
        """No-op action for display-only bindings."""
        pass

    def action_toggle_help(self) -> None:
        """Toggle the keybindings panel."""
        existing = self.screen.query("KeybindingsPanel")
        if existing:
            existing.remove()
        else:
            self.screen.mount(KeybindingsPanel())

    def action_save(self) -> None:
        self._do_save()

    def action_close_project(self) -> None:
        self._do_save(notify=False)
        self.app.pop_screen()
        # Refresh the projects list if it's still there
        try:
            ps = self.app.query_one(ProjectsScreen)
            ps._load_all_projects()
            ps._refresh_list()
        except Exception:
            pass

    def action_bold(self) -> None:
        ta = self.query_one("#editor", TextArea)
        sel = ta.selected_text
        if sel:
            ta.replace(f"**{sel}**", *ta.selection)
        else:
            loc = ta.cursor_location
            ta.insert("****")
            # Move cursor between the asterisks
            row, col = ta.cursor_location
            ta.cursor_location = (row, col - 2)

    def action_italic(self) -> None:
        ta = self.query_one("#editor", TextArea)
        sel = ta.selected_text
        if sel:
            ta.replace(f"*{sel}*", *ta.selection)
        else:
            ta.insert("**")
            row, col = ta.cursor_location
            ta.cursor_location = (row, col - 1)

    def action_footnote(self) -> None:
        ta = self.query_one("#editor", TextArea)
        ta.insert("^[]")
        row, col = ta.cursor_location
        ta.cursor_location = (row, col - 1)

    def action_cite(self) -> None:
        sources = self.project.get_sources()
        if not sources:
            self.notify("No sources. Open Sources from the command palette (Ctrl+P) first.", severity="warning")
            return
        self.app.push_screen(
            CitePickerModal(sources),
            callback=self._insert_citation,
        )

    def _insert_citation(self, footnote_text: str | None) -> None:
        if footnote_text:
            ta = self.query_one("#editor", TextArea)
            ta.insert(footnote_text)
            self.notify("Citation inserted.")

    def action_bibliography(self) -> None:
        sources = self.project.get_sources()
        if not sources:
            self.notify("No sources. Open Sources from the command palette (Ctrl+P) first.", severity="warning")
            return
        sorted_sources = sorted(sources, key=lambda s: s.author.split()[-1] if s.author else "")
        lines = ["## Bibliography", ""]
        for s in sorted_sources:
            lines.append(s.to_chicago_bibliography())
            lines.append("")
        ta = self.query_one("#editor", TextArea)
        ta.insert("\n".join(lines))
        self.notify("Bibliography inserted.")

    def action_sources(self) -> None:
        self._do_save(notify=False)
        self.app.push_screen(
            SourcesModal(self.project),
            callback=self._on_sources_closed,
        )

    def _on_sources_closed(self, _result: None) -> None:
        # Reload project in case sources changed
        app: ManuscriptsApp = self.app  # type: ignore[assignment]
        reloaded = app.storage.load_project(self.project.id)
        if reloaded:
            self.project = reloaded

    def action_import_bib(self) -> None:
        self.app.push_screen(
            BibImportModal(),
            callback=self._on_bib_imported,
        )

    def _on_bib_imported(self, sources: list[Source] | None) -> None:
        if sources:
            for s in sources:
                self.project.add_source(s)
            app: ManuscriptsApp = self.app  # type: ignore[assignment]
            app.storage.save_project(self.project)
            self.notify(f"Imported {len(sources)} source(s).")

    # ── YAML frontmatter insertion ──────────────────────────────────

    _FRONTMATTER_PROPS = ["title", "author", "instructor", "date", "spacing", "style"]

    def action_insert_frontmatter(self) -> None:
        """Insert all missing YAML frontmatter properties at once."""
        ta = self.query_one("#editor", TextArea)
        text = ta.text
        m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        if m:
            existing = set()
            for line in m.group(1).split("\n"):
                idx = line.find(":")
                if idx > 0:
                    existing.add(line[:idx].strip())
            missing = [p for p in self._FRONTMATTER_PROPS if p not in existing]
            if not missing:
                self.notify("All frontmatter properties already present.", severity="warning")
                return
            new_lines = "\n".join(f"{p}: " for p in missing)
            end_pos = m.end(1)
            new_text = text[:end_pos] + "\n" + new_lines + text[end_pos:]
        else:
            block = "\n".join(f"{p}: " for p in self._FRONTMATTER_PROPS)
            new_text = f"---\n{block}\n---\n" + text
        ta.clear()
        ta.insert(new_text)
        self.notify("Frontmatter inserted.")

    # ── Export ───────────────────────────────────────────────────────

    def action_export_pdf(self) -> None:
        self._do_save(notify=False)
        self.app.push_screen(
            ExportFormatModal(),
            callback=self._on_export_format_chosen,
        )

    def _on_export_format_chosen(self, fmt: str | None) -> None:
        if fmt:
            self._run_export(fmt)

    @work(thread=True)
    def _run_export(self, export_format: str = "pdf") -> None:
        app: ManuscriptsApp = self.app  # type: ignore[assignment]
        export_dir = app.storage.exports_dir
        safe_name = re.sub(r'[^\w\s-]', '', self.project.name).strip().replace(' ', '_')[:50] or "export"

        # Markdown-only export — no external tools needed
        if export_format == "md":
            out = export_dir / f"{safe_name}.md"
            with open(out, "w") as f:
                f.write(self.project.content)
            self.app.call_from_thread(self.notify, f"Exported to {out}")
            return

        # 1. Parse YAML frontmatter
        yaml = parse_yaml_frontmatter(self.project.content)

        # 2. Detect external tools
        pandoc = detect_pandoc()
        if not pandoc:
            self.app.call_from_thread(
                self.notify,
                "Pandoc not found. Install pandoc for export.",
                severity="warning",
            )
            return

        if export_format == "pdf":
            libreoffice = detect_libreoffice()
            if not libreoffice:
                self.app.call_from_thread(
                    self.notify,
                    "LibreOffice not found. Install LibreOffice for PDF export.",
                    severity="warning",
                )
                return
        else:
            libreoffice = None

        # 3. Resolve reference doc
        ref_doc = resolve_reference_doc(yaml)
        if not ref_doc:
            self.app.call_from_thread(
                self.notify,
                "No reference .docx found in refs/ directory.",
                severity="error",
            )
            return

        # Temp file paths
        md_path = export_dir / f"{self.project.id}.md"
        lua_path = export_dir / f"{self.project.id}_filter.lua"
        docx_path = export_dir / f"{safe_name}.docx"
        pdf_path = export_dir / f"{safe_name}.pdf"

        try:
            # 4. Write content
            with open(md_path, "w") as f:
                f.write(self.project.content)

            # 5. Generate Lua filter
            lua_code = _generate_lua_filter(yaml)
            with open(lua_path, "w") as f:
                f.write(lua_code)

            # 6. Build pandoc command
            pandoc_args = [
                pandoc,
                str(md_path),
                "--standalone",
                f"--reference-doc={ref_doc}",
                f"--lua-filter={lua_path}",
            ]
            if "bibliography" in yaml:
                pandoc_args.append("--citeproc")
            pandoc_args.extend(["-o", str(docx_path)])

            if export_format == "pdf":
                self.app.call_from_thread(self.notify, "Converting to PDF…")
            else:
                self.app.call_from_thread(self.notify, "Converting to DOCX…")

            result = subprocess.run(
                pandoc_args, capture_output=True, text=True, timeout=60
            )
            if result.returncode != 0:
                self.app.call_from_thread(
                    self.notify,
                    f"Pandoc error: {result.stderr[:200]}",
                    severity="error",
                )
                return

            # 7. Post-process DOCX (non-fatal)
            try:
                _postprocess_docx(str(docx_path), yaml)
            except Exception:
                pass

            if export_format == "docx":
                self.app.call_from_thread(self.notify, f"Exported to {docx_path}")
                return

            # 8. Run LibreOffice (PDF only)
            lo_args = [
                libreoffice,
                "--headless",
                "--convert-to", "pdf",
                "--outdir", str(export_dir),
                str(docx_path),
            ]
            result = subprocess.run(
                lo_args, capture_output=True, text=True, timeout=60
            )
            if result.returncode != 0:
                self.app.call_from_thread(
                    self.notify,
                    f"LibreOffice error: {result.stderr[:200]}",
                    severity="error",
                )
                return

            self.app.call_from_thread(self.notify, f"Exported to {pdf_path}")

        except subprocess.TimeoutExpired:
            self.app.call_from_thread(
                self.notify, "Export timed out.", severity="error"
            )
        except Exception as exc:
            self.app.call_from_thread(
                self.notify,
                f"Export failed: {str(exc)[:200]}",
                severity="error",
            )
        finally:
            # Clean up intermediate files (keep the final output)
            cleanup = [md_path, lua_path]
            if export_format == "pdf":
                cleanup.append(docx_path)
            for p in cleanup:
                try:
                    if p.exists():
                        p.unlink()
                except OSError:
                    pass


# ── Export format modal ───────────────────────────────────────────────


class ExportFormatModal(ModalScreen[str | None]):
    """Pick an export format: PDF, DOCX, or Markdown."""

    DEFAULT_CSS = """
    ExportFormatModal {
        align: center middle;
    }
    #export-box {
        width: 40;
        height: auto;
        max-height: 12;
        border: solid #666;
        background: $surface;
        padding: 1 2;
    }
    #export-box Label {
        margin-bottom: 1;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def compose(self) -> ComposeResult:
        with Vertical(id="export-box"):
            yield Label("Export as")
            yield OptionList(
                Option("PDF (.pdf)", id="pdf"),
                Option("Word (.docx)", id="docx"),
                Option("Markdown (.md)", id="md"),
                id="export-options",
            )

    def on_mount(self) -> None:
        self.query_one("#export-options", OptionList).focus()

    @on(OptionList.OptionSelected, "#export-options")
    def _select(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option_id)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── Printer picker modal ──────────────────────────────────────────────


class PrinterPickerModal(ModalScreen[str | None]):
    """Pick a printer from available system printers."""

    DEFAULT_CSS = """
    PrinterPickerModal {
        align: center middle;
    }
    #printer-box {
        width: 60%;
        max-width: 60;
        height: auto;
        max-height: 18;
        border: solid #666;
        background: $surface;
        padding: 1 2;
    }
    #printer-box Label {
        margin-bottom: 1;
    }
    #printer-list {
        height: auto;
        max-height: 10;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, printers: list[str], file_path: Path) -> None:
        super().__init__()
        self._printers = printers
        self._file_path = file_path

    def compose(self) -> ComposeResult:
        with Vertical(id="printer-box"):
            yield Label("Print to")
            ol = OptionList(id="printer-list")
            for p in self._printers:
                ol.add_option(Option(p, id=p))
            yield ol

    def on_mount(self) -> None:
        self.query_one("#printer-list", OptionList).focus()

    @on(OptionList.OptionSelected, "#printer-list")
    def _select(self, event: OptionList.OptionSelected) -> None:
        printer_name = event.option_id
        try:
            subprocess.Popen(["lp", "-d", printer_name, str(self._file_path)])
            self.notify(f"Sent to {printer_name}.")
        except Exception as exc:
            self.notify(f"Print failed: {exc}", severity="error")
        self.dismiss(printer_name)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── Citation picker modal ─────────────────────────────────────────────


class CitePickerModal(ModalScreen[str | None]):
    """Fuzzy‑search sources and pick one to insert as a footnote."""

    DEFAULT_CSS = """
    CitePickerModal {
        align: center middle;
    }
    #cite-box {
        width: 80%;
        max-width: 80;
        height: 70%;
        border: solid #666;
        background: $surface;
        padding: 1 2;
    }
    #cite-box Label {
        margin-bottom: 1;
    }
    #cite-results {
        height: 1fr;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, sources: list[Source]) -> None:
        super().__init__()
        self.all_sources = sources
        self.filtered: list[Source] = list(sources)

    def compose(self) -> ComposeResult:
        with Vertical(id="cite-box"):
            yield Label("Insert Citation")
            yield Input(placeholder="Search sources…", id="cite-search")
            yield OptionList(id="cite-results")

    def on_mount(self) -> None:
        self._update_results("")
        self.query_one("#cite-search", Input).focus()

    @on(Input.Changed, "#cite-search")
    def _search_changed(self, event: Input.Changed) -> None:
        self._update_results(event.value)

    def _update_results(self, query: str) -> None:
        self.filtered = fuzzy_filter(self.all_sources, query)
        ol: OptionList = self.query_one("#cite-results", OptionList)
        ol.clear_options()
        for s in self.filtered:
            ol.add_option(Option(f"{s.author} ({s.year}) — {s.title}", id=s.id))
        if self.filtered:
            ol.highlighted = 0

    def on_key(self, event) -> None:
        """Down arrow in search input moves focus to the option list."""
        if event.key == "down":
            focused = self.app.focused
            search_input = self.query_one("#cite-search", Input)
            if focused is search_input:
                ol = self.query_one("#cite-results", OptionList)
                ol.focus()
                event.prevent_default()

    @on(OptionList.OptionSelected, "#cite-results")
    def _select(self, event: OptionList.OptionSelected) -> None:
        # Find the source
        for s in self.filtered:
            if s.id == event.option_id:
                footnote = f"^[{s.to_chicago_footnote()}]"
                self.dismiss(footnote)
                return
        self.dismiss(None)

    @on(Input.Submitted, "#cite-search")
    def _submit_search(self, event: Input.Submitted) -> None:
        """Enter in search field picks the highlighted result (default to first)."""
        ol: OptionList = self.query_one("#cite-results", OptionList)
        idx = ol.highlighted
        if idx is None and self.filtered:
            idx = 0
        if idx is not None and idx < len(self.filtered):
            s = self.filtered[idx]
            self.dismiss(f"^[{s.to_chicago_footnote()}]")
            return
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── Sources modal ─────────────────────────────────────────────────────


class SourcesModal(ModalScreen[None]):
    """View / add / delete sources for a project."""

    DEFAULT_CSS = """
    SourcesModal {
        align: center middle;
    }
    #sources-box {
        width: 80%;
        max-width: 90;
        height: 80%;
        border: solid #666;
        background: $surface;
        padding: 1 2;
    }
    #sources-box Label {
        margin-bottom: 1;
    }
    #source-list {
        height: 1fr;
    }
    .sources-buttons {
        height: 3;
        dock: bottom;
    }
    .sources-buttons Button {
        margin-right: 1;
    }
    """

    BINDINGS = [
        Binding("a", "add_source", "Add"),
        Binding("d", "delete_source", "Delete"),
        Binding("i", "import_sources", "Import"),
        Binding("escape", "close", "Close", show=False),
    ]

    def __init__(self, project: Project) -> None:
        super().__init__()
        self.project = project

    def compose(self) -> ComposeResult:
        with Vertical(id="sources-box"):
            yield Label(f"Sources: {self.project.name}")
            yield OptionList(id="source-list")
            with Horizontal(classes="sources-buttons"):
                yield Button("Add [a]", id="btn-add")
                yield Button("Import [i]", id="btn-import")
                yield Button("Delete [d]", variant="error", id="btn-del")
                yield Button("Close [Esc]", id="btn-close")

    def on_mount(self) -> None:
        self._refresh_list()
        self.query_one("#btn-add", Button).focus()

    def _refresh_list(self) -> None:
        ol: OptionList = self.query_one("#source-list", OptionList)
        ol.clear_options()
        sources = self.project.get_sources()
        if not sources:
            ol.add_option(Option("  No sources yet — press a to add one.", id="__empty__"))
        else:
            for s in sources:
                ol.add_option(
                    Option(f"{s.author} ({s.year}) — {s.title}", id=s.id)
                )

    @on(Button.Pressed, "#btn-add")
    def _btn_add(self, event: Button.Pressed) -> None:
        self.action_add_source()

    @on(Button.Pressed, "#btn-del")
    def _btn_del(self, event: Button.Pressed) -> None:
        self.action_delete_source()

    @on(Button.Pressed, "#btn-import")
    def _btn_import(self, event: Button.Pressed) -> None:
        self.action_import_sources()

    @on(Button.Pressed, "#btn-close")
    def _btn_close(self, event: Button.Pressed) -> None:
        self.action_close()

    def action_add_source(self) -> None:
        self.app.push_screen(
            SourceFormModal(),
            callback=self._on_source_added,
        )

    def _on_source_added(self, source: Source | None) -> None:
        if source:
            self.project.add_source(source)
            app: ManuscriptsApp = self.app  # type: ignore[assignment]
            app.storage.save_project(self.project)
            self._refresh_list()
            self.notify(f"Added: {source.author}")

    def action_delete_source(self) -> None:
        ol: OptionList = self.query_one("#source-list", OptionList)
        idx = ol.highlighted
        sources = self.project.get_sources()
        if idx is not None and idx < len(sources):
            s = sources[idx]
            self.project.remove_source(s.id)
            app: ManuscriptsApp = self.app  # type: ignore[assignment]
            app.storage.save_project(self.project)
            self._refresh_list()
            self.notify("Source deleted.")

    def action_import_sources(self) -> None:
        app: ManuscriptsApp = self.app  # type: ignore[assignment]
        other_projects = [
            p for p in app.storage.list_projects() if p.id != self.project.id
        ]
        if not other_projects:
            self.notify("No other manuscripts to import from.", severity="warning")
            return
        self.app.push_screen(
            ImportSourcesModal(other_projects),
            callback=self._on_sources_imported,
        )

    def _on_sources_imported(self, sources: list[Source] | None) -> None:
        if not sources:
            return
        existing = self.project.get_sources()
        existing_keys = {(s.author, s.title, s.year) for s in existing}
        added = 0
        for s in sources:
            if (s.author, s.title, s.year) not in existing_keys:
                s.id = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + f"_{added}"
                self.project.add_source(s)
                existing_keys.add((s.author, s.title, s.year))
                added += 1
        app: ManuscriptsApp = self.app  # type: ignore[assignment]
        app.storage.save_project(self.project)
        self._refresh_list()
        skipped = len(sources) - added
        msg = f"Imported {added} source(s)."
        if skipped:
            msg += f" {skipped} duplicate(s) skipped."
        self.notify(msg)

    def action_close(self) -> None:
        self.dismiss(None)


# ── Source form modal ─────────────────────────────────────────────────


class SourceFormModal(ModalScreen[Source | None]):
    """Form for adding a new source.

    All three field sets are pre-built in compose() with unique IDs
    (e.g. field-book-author, field-article-author) to avoid the crash
    caused by dynamically destroying/recreating widgets with shared IDs.
    Only the active type's container is visible.
    """

    DEFAULT_CSS = """
    SourceFormModal {
        align: center middle;
    }
    #source-form-box {
        width: 90%;
        max-width: 100;
        height: 90%;
        border: solid #666;
        background: $surface;
        padding: 1 2;
    }
    #source-form-box Label {
        margin-bottom: 1;
    }
    #source-type-bar {
        height: 3;
        margin-bottom: 1;
    }
    #source-type-bar Button {
        margin-right: 1;
    }
    #source-fields {
        height: 1fr;
    }
    .book-field, .book_section-field, .article-field, .website-field {
        display: none;
    }
    .form-buttons {
        height: auto;
        margin-top: 1;
        display: none;
    }
    .form-buttons Button {
        margin-right: 1;
    }
    .field-label {
        margin-top: 1;
    }
    #tab-hint {
        display: none;
        color: #777;
        margin-top: 1;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self) -> None:
        super().__init__()
        self.current_type = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="source-form-box"):
            yield Label("Add Source")
            with Horizontal(id="source-type-bar"):
                yield Button("Book", id="btn-type-book")
                yield Button("Book Section", id="btn-type-book_section")
                yield Button("Article", id="btn-type-article")
                yield Button("Website", id="btn-type-website")
            with VerticalScroll(id="source-fields"):
                # All fields flat — no nested containers.
                # Visibility toggled per-type via CSS classes.
                for stype in SOURCE_TYPES:
                    for field_key, label in SOURCE_FIELDS[stype]:
                        yield Label(label, classes=f"field-label {stype}-field")
                        yield Input(placeholder=label, id=f"field-{stype}-{field_key}", classes=f"{stype}-field")
                yield Label("Tab \u2192 next field | Shift+Tab \u2192 previous", id="tab-hint")
            with Horizontal(classes="form-buttons"):
                yield Button("Save", id="btn-save")
                yield Button("Cancel", id="btn-form-cancel")

    def _switch_type(self, stype: str) -> None:
        self.current_type = stype
        # Update button variants
        for t in SOURCE_TYPES:
            btn = self.query_one(f"#btn-type-{t}", Button)
            btn.variant = "primary" if t == stype else "default"
        # Show the right fields, hide others
        for t in SOURCE_TYPES:
            for w in self.query(f".{t}-field"):
                w.styles.display = "block" if t == stype else "none"
        # Show form buttons and tab hint
        self.query_one(".form-buttons").styles.display = "block"
        self.query_one("#tab-hint").styles.display = "block"
        # Focus the first input
        first_input = self.query_one(f"#field-{stype}-{SOURCE_FIELDS[stype][0][0]}", Input)
        first_input.focus()

    @on(Button.Pressed, "#btn-type-book")
    def _type_book(self, event: Button.Pressed) -> None:
        self._switch_type("book")

    @on(Button.Pressed, "#btn-type-book_section")
    def _type_book_section(self, event: Button.Pressed) -> None:
        self._switch_type("book_section")

    @on(Button.Pressed, "#btn-type-article")
    def _type_article(self, event: Button.Pressed) -> None:
        self._switch_type("article")

    @on(Button.Pressed, "#btn-type-website")
    def _type_website(self, event: Button.Pressed) -> None:
        self._switch_type("website")

    @on(Button.Pressed, "#btn-save")
    def _save(self, event: Button.Pressed) -> None:
        self._do_save()

    @on(Button.Pressed, "#btn-form-cancel")
    def _cancel_btn(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def _do_save(self) -> None:
        if not self.current_type:
            self.notify("Please select a source type first.", severity="error")
            return
        try:
            data: dict[str, str] = {}
            for field_key, _ in SOURCE_FIELDS[self.current_type]:
                try:
                    inp = self.query_one(f"#field-{self.current_type}-{field_key}", Input)
                    data[field_key] = inp.value.strip()
                except Exception:
                    data[field_key] = ""

            if not data.get("author") or not data.get("title"):
                self.notify("Author and Title are required.", severity="error")
                return

            source = Source(
                id=datetime.now().strftime("%Y%m%d_%H%M%S_%f"),
                source_type=self.current_type,
                author=data.get("author", ""),
                title=data.get("title", ""),
                year=data.get("year", ""),
                publisher=data.get("publisher", ""),
                city=data.get("city", ""),
                journal=data.get("journal", ""),
                volume=data.get("volume", ""),
                issue=data.get("issue", ""),
                pages=data.get("pages", ""),
                book_title=data.get("book_title", ""),
                editor=data.get("editor", ""),
                url=data.get("url", ""),
                access_date=data.get("access_date", ""),
                site_name=data.get("site_name", ""),
            )
            self.dismiss(source)
        except Exception as exc:
            self.notify(f"Error saving source: {exc}", severity="error")

    def action_cancel(self) -> None:
        self.dismiss(None)


# ════════════════════════════════════════════════════════════════════════
#  BibTeX Import
# ════════════════════════════════════════════════════════════════════════


def parse_bibtex(text: str) -> list[Source]:
    """Parse BibTeX entries into Source objects.

    Handles @book{...}, @article{...}, @misc{...}, @online{...}, etc.
    """
    sources: list[Source] = []
    # Match @type{key, ... } entries (greedy within braces, balanced)
    entry_re = re.compile(r"@(\w+)\s*\{([^,]*),\s*(.*?)\}\s*(?=@|\Z)", re.DOTALL)
    field_re = re.compile(r"(\w+)\s*=\s*[{\"](.*?)[}\"]", re.DOTALL)

    type_map = {
        "book": "book",
        "inbook": "book_section",
        "incollection": "book_section",
        "article": "article",
        "inproceedings": "article",
        "conference": "article",
        "misc": "website",
        "online": "website",
        "electronic": "website",
    }

    for m in entry_re.finditer(text):
        bib_type = m.group(1).lower()
        body = m.group(3)
        fields: dict[str, str] = {}
        for fm in field_re.finditer(body):
            fields[fm.group(1).lower()] = fm.group(2).strip()

        stype = type_map.get(bib_type, "book")
        author = fields.get("author", "")
        title = fields.get("title", "")
        if not author and not title:
            continue

        sources.append(Source(
            id=datetime.now().strftime("%Y%m%d_%H%M%S_%f") + f"_{len(sources)}",
            source_type=stype,
            author=author,
            title=title,
            year=fields.get("year", ""),
            publisher=fields.get("publisher", ""),
            city=fields.get("address", ""),
            journal=fields.get("journal", fields.get("journaltitle", "")),
            volume=fields.get("volume", ""),
            issue=fields.get("number", ""),
            pages=fields.get("pages", ""),
            book_title=fields.get("booktitle", ""),
            editor=fields.get("editor", ""),
            url=fields.get("url", ""),
            access_date=fields.get("urldate", ""),
            site_name=fields.get("organization", fields.get("howpublished", "")),
        ))
    return sources


class BibImportModal(ModalScreen[list[Source] | None]):
    """Modal to import a .bib file."""

    DEFAULT_CSS = """
    BibImportModal {
        align: center middle;
    }
    #bib-import-box {
        width: 70%;
        max-width: 70;
        height: auto;
        max-height: 14;
        border: solid #666;
        background: $surface;
        padding: 1 2;
    }
    #bib-import-box Label {
        margin-bottom: 1;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def compose(self) -> ComposeResult:
        with Vertical(id="bib-import-box"):
            yield Label("Import .bib File")
            yield Input(placeholder="Path to .bib file…", id="bib-path-input")
            with Horizontal():
                yield Button("Import", id="btn-bib-import")
                yield Button("Cancel", id="btn-bib-cancel")

    def on_mount(self) -> None:
        self.query_one("#bib-path-input", Input).focus()

    @on(Button.Pressed, "#btn-bib-import")
    def _import(self, event: Button.Pressed) -> None:
        self._do_import()

    @on(Button.Pressed, "#btn-bib-cancel")
    def _cancel_btn(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    @on(Input.Submitted, "#bib-path-input")
    def _submit(self, event: Input.Submitted) -> None:
        self._do_import()

    def _do_import(self) -> None:
        path_str = self.query_one("#bib-path-input", Input).value.strip()
        if not path_str:
            self.notify("Please enter a file path.", severity="error")
            return
        p = Path(path_str).expanduser()
        if not p.exists():
            self.notify(f"File not found: {p}", severity="error")
            return
        try:
            text = p.read_text(encoding="utf-8")
        except Exception as exc:
            self.notify(f"Could not read file: {exc}", severity="error")
            return
        sources = parse_bibtex(text)
        if not sources:
            self.notify("No entries found in .bib file.", severity="warning")
            return
        self.dismiss(sources)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── Import sources from another project ───────────────────────────────


class ImportSourcesModal(ModalScreen[list[Source] | None]):
    """Two-phase modal: pick a project, then pick sources to import."""

    DEFAULT_CSS = """
    ImportSourcesModal {
        align: center middle;
    }
    #import-box {
        width: 80%;
        max-width: 90;
        height: 70%;
        border: solid #666;
        background: $surface;
        padding: 1 2;
    }
    #import-box Label {
        margin-bottom: 1;
    }
    #import-list {
        height: 1fr;
    }
    .import-buttons {
        height: 3;
        dock: bottom;
    }
    .import-buttons Button {
        margin-right: 1;
    }
    """

    BINDINGS = [Binding("escape", "go_back", "Back", show=False)]

    def __init__(self, projects: list[Project]) -> None:
        super().__init__()
        self._projects = projects
        self._phase = "projects"  # "projects" or "sources"
        self._selected_project: Project | None = None
        self._sources: list[Source] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="import-box"):
            yield Label("Import Sources — Select a manuscript", id="import-title")
            yield OptionList(id="import-list")
            with Horizontal(classes="import-buttons"):
                yield Button("Import All", id="btn-import-all")
                yield Button("Back", id="btn-import-back")

    def on_mount(self) -> None:
        self._show_projects()
        self.query_one("#btn-import-all", Button).styles.display = "none"

    def _show_projects(self) -> None:
        self._phase = "projects"
        self._selected_project = None
        self._sources = []
        self.query_one("#import-title", Label).update("Import Sources — Select a manuscript")
        self.query_one("#btn-import-all", Button).styles.display = "none"
        ol: OptionList = self.query_one("#import-list", OptionList)
        ol.clear_options()
        for p in self._projects:
            src_count = len(p.get_sources())
            ol.add_option(Option(f"{p.name}  ({src_count} sources)", id=p.id))
        ol.focus()

    def _show_sources(self, project: Project) -> None:
        self._phase = "sources"
        self._selected_project = project
        self._sources = project.get_sources()
        self.query_one("#import-title", Label).update(
            f"Import Sources — {project.name} (Enter to import one, or Import All)"
        )
        self.query_one("#btn-import-all", Button).styles.display = "block"
        ol: OptionList = self.query_one("#import-list", OptionList)
        ol.clear_options()
        if not self._sources:
            ol.add_option(Option("  No sources in this manuscript.", id="__empty__"))
        else:
            for s in self._sources:
                ol.add_option(
                    Option(f"{s.author} ({s.year}) — {s.title}", id=s.id)
                )
        ol.focus()

    @on(OptionList.OptionSelected, "#import-list")
    def _select(self, event: OptionList.OptionSelected) -> None:
        if event.option_id == "__empty__":
            return
        if self._phase == "projects":
            for p in self._projects:
                if p.id == event.option_id:
                    self._show_sources(p)
                    return
        elif self._phase == "sources":
            for s in self._sources:
                if s.id == event.option_id:
                    self.dismiss([s])
                    return

    @on(Button.Pressed, "#btn-import-all")
    def _import_all(self, event: Button.Pressed) -> None:
        if self._phase == "sources" and self._sources:
            self.dismiss(list(self._sources))

    @on(Button.Pressed, "#btn-import-back")
    def _back(self, event: Button.Pressed) -> None:
        self.action_go_back()

    def action_go_back(self) -> None:
        if self._phase == "sources":
            self._show_projects()
        else:
            self.dismiss(None)


# ════════════════════════════════════════════════════════════════════════
#  Command palette
# ════════════════════════════════════════════════════════════════════════


class ManuscriptsCommands(Provider):
    """Expose actions in the command palette for both screens."""

    def _get_commands(self, include_hidden: bool = False):
        """Return commands sorted alphabetically.

        ``include_hidden`` adds commands that should only appear via
        search (not in the initial discover list).
        """
        screen = self.screen
        commands: list[tuple[str, str, object]] = []

        if isinstance(screen, EditorScreen):
            commands = [
                ("Bibliography", "Insert bibliography from all sources", screen.action_bibliography),
                ("Export", "Export document", screen.action_export_pdf),
                ("Insert blank footnote (Ctrl+N)", "Insert footnote", screen.action_footnote),
                ("Insert frontmatter", "Add YAML frontmatter properties", screen.action_insert_frontmatter),
                ("Insert reference (Ctrl+R)", "Insert a reference", screen.action_cite),
                ("Keybindings (Ctrl+H)", "Show keybindings panel", screen.action_toggle_help),
                ("Return to manuscripts (Ctrl+M)", "Save and return to manuscripts", screen.action_close_project),
                ("Save (Ctrl+S)", "Save document", screen.action_save),
                ("Sources (Ctrl+O)", "Manage sources", screen.action_sources),
            ]
            if include_hidden:
                commands.append(
                    ("Import .bib file", "Import sources from a BibTeX file", screen.action_import_bib),
                )
        elif isinstance(screen, ProjectsScreen):
            commands = [
                ("Exports (e)", "Toggle exports view", screen.action_toggle_exports),
                ("New manuscript (n)", "Create a new manuscript", screen.action_new_project),
                ("Quit (q)", "Quit the application", screen.action_quit),
            ]

        commands.sort(key=lambda c: c[0].lower())
        return commands

    async def discover(self) -> Hits:
        for name, help_text, callback in self._get_commands(include_hidden=False):
            yield DiscoveryHit(name, callback, help=help_text)

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for name, help_text, callback in self._get_commands(include_hidden=True):
            score = matcher.match(name)
            if score > 0:
                yield Hit(score, matcher.highlight(name), callback, help=help_text)


# ════════════════════════════════════════════════════════════════════════
#  App
# ════════════════════════════════════════════════════════════════════════


class ManuscriptsApp(App):
    """Manuscripts — a writing appliance for students."""

    COMMANDS = App.COMMANDS | {ManuscriptsCommands}
    # Override App.BINDINGS so ctrl+q and the command palette don't leak
    # into the keybindings panel.  EditorScreen has its own ctrl+p binding.
    BINDINGS = [
        Binding("ctrl+p", "command_palette", "Command Palette", show=False, system=True),
        Binding("ctrl+q", "quit", "Quit", show=False, system=True),
    ]
    TITLE = "Manuscripts"
    CSS = """
    Screen {
        background: #2a2a2a;
    }
    SearchIcon {
        display: none;
    }
    Button {
        background: #555;
        color: #e0e0e0;
        border: tall #777;
        margin: 0 1;
    }
    Button:hover {
        background: #666;
    }
    Button:focus {
        background: #666;
        border: tall #999;
    }
    Button.-error {
        background: #8b3a3a;
    }
    #projects-title {
        color: #e0e0e0;
        padding: 1 2;
    }
    #project-list {
        margin: 1 2;
        height: 1fr;
    }
    #editor {
        height: 1fr;
        border: none;
        &:focus {
            border: none;
        }
    }
    #editor-status {
        dock: bottom;
        height: 1;
        background: #333333;
        color: #8a8a8a;
        padding: 0 2;
    }
    """

    def __init__(self, data_dir: Path) -> None:
        super().__init__()
        self.storage = Storage(data_dir)
        self.projects: list[Project] = []

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        """Suppress default system commands; ManuscriptsCommands handles everything."""
        return []

    def on_mount(self) -> None:
        self.push_screen(ProjectsScreen())


# ════════════════════════════════════════════════════════════════════════
#  Entry point
# ════════════════════════════════════════════════════════════════════════


def main() -> None:
    if os.environ.get("MANUSCRIPTS_DATA"):
        data_dir = Path(os.environ["MANUSCRIPTS_DATA"])
    else:
        data_dir = Path.home() / "Documents" / "Manuscripts"

    app = ManuscriptsApp(data_dir)
    app.run()


if __name__ == "__main__":
    main()
