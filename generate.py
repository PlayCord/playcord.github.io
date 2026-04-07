#!/usr/bin/env python3
"""
Simple static site generator for the PlayCord demo page.

Usage: python3 generate.py [content.json] [template]

Defaults: content.json, index.template.html -> write to index.html
"""
import json
import sys
from string import Template
from pathlib import Path


def load_json(path: Path):
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def render_top_buttons(buttons):
    # Use the same visual structure as the template's buttons
    out = []
    for b in buttons:
        btn = f'''<button onclick="location.href='{b.get('href','#')}'" class="flex items-center justify-center gap-2 bg-[#5865F2] text-white px-10 py-3.5 shadow-lg shadow-[#5865F2]/20 hover:-translate-y-1 hover:shadow-xl hover:bg-[#4752c4] transition-all duration-200">{b.get('text')}</button>'''
        # Basic alternative style if button requests white bg
        if b.get('style') == 'white':
            btn = f'''<button onclick="location.href='{b.get('href','#')}'" class="flex items-center justify-center gap-2 bg-white text-slate-700 border border-slate-200 px-10 py-3.5 shadow-sm hover:-translate-y-1 hover:shadow-md hover:border-slate-300 transition-all duration-200">{b.get('text')}</button>'''
        out.append(btn)
    return '\n        '.join(out)


def render_description(paragraphs):
    return '\n        '.join(f'<p>\n            {p}\n        </p>' for p in paragraphs)


def render_explore(items):
    out = []
    for it in items:
        subtitle_html = f"<span class=\"text-xs text-slate-500\">{it.get('subtitle')}</span>" if it.get('subtitle') else ''
        btn = f'''<button onclick="location.href='{it.get('href','#')}'" class="group bg-white border border-slate-200 flex-1 py-4 px-6 shadow-sm hover:shadow-md hover:border-[#5865F2]/50 transition-all duration-200 flex items-center justify-between">\n                <div class=\"flex flex-col text-left\">\n                    <span class=\"text-slate-700 group-hover:text-[#5865F2] transition-colors\">{it.get('title')}</span>\n                    {subtitle_html}\n                </div>\n                <svg class=\"text-slate-400 group-hover:text-[#5865F2] transition-colors\" xmlns=\"http://www.w3.org/2000/svg\" width=\"18\" height=\"18\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M5 12h14\"/><path d=\"m12 5 7 7-7 7\"/></svg>\n            </button>'''
        out.append(btn)
    return '\n            '.join(out)


def main():
    content_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('content.json')
    template_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('index.template.html')
    out_path = Path('index.html')

    if not content_path.exists():
        print(f'Content file not found: {content_path}')
        sys.exit(1)
    if not template_path.exists():
        print(f'Template file not found: {template_path}')
        sys.exit(1)

    content = load_json(content_path)

    tpl_text = template_path.read_text(encoding='utf-8')

    # Substitute simple $placeholders
    subs = {
        'TITLE': content.get('title', ''),
        'VERSION': content.get('version', ''),
        'SUBTITLE': content.get('subtitle', ''),
        'PFP': content.get('pfp', 'pfp.jpg')
    }

    rendered = Template(tpl_text).safe_substitute(subs)

    # Inject generated HTML for sections
    rendered = rendered.replace('<!--INJECT:TOP_BUTTONS-->', render_top_buttons(content.get('top_buttons', [])))
    rendered = rendered.replace('<!--INJECT:DESCRIPTION-->', render_description(content.get('description', [])))
    rendered = rendered.replace('<!--INJECT:EXPLORE_ITEMS-->', render_explore(content.get('explore', [])))

    # Backup existing index.html if present
    if out_path.exists():
        out_path.with_suffix('.html.bak').write_text(out_path.read_text(encoding='utf-8'), encoding='utf-8')

    out_path.write_text(rendered, encoding='utf-8')
    print(f'Wrote {out_path} (from {content_path} + {template_path})')


if __name__ == '__main__':
    main()

