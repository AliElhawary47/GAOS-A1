#!/usr/bin/env python3
"""Convert HLSR and LLSR markdown to professional HTML."""

import re
from pathlib import Path

def read_file(path):
    with open(path, 'r') as f:
        return f.read()

def create_html_header(title, doc_id):
    """Create the HTML header."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', 'Helvetica Neue', sans-serif; line-height: 1.6; color: #333; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 900px; margin: 0 auto; background: white; padding: 60px; box-shadow: 0 0 20px rgba(0,0,0,0.1); line-height: 1.8; }}
        .header {{ border-bottom: 4px solid #2c3e50; padding-bottom: 30px; margin-bottom: 40px; }}
        .header h1 {{ font-size: 2.5em; color: #2c3e50; margin-bottom: 10px; font-weight: 700; }}
        .metadata {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 20px; font-size: 0.95em; color: #666; }}
        .metadata-item {{ padding: 8px 0; }}
        .metadata-label {{ font-weight: 600; color: #2c3e50; }}
        .toc {{ background: #ecf0f1; padding: 25px; border-radius: 5px; margin-bottom: 40px; border-left: 4px solid #3498db; }}
        .toc h2 {{ color: #2c3e50; margin-bottom: 15px; font-size: 1.3em; }}
        .toc ul {{ list-style: none; padding-left: 0; }}
        .toc li {{ margin-bottom: 8px; }}
        .toc a {{ color: #3498db; text-decoration: none; font-weight: 500; }}
        .toc a:hover {{ text-decoration: underline; }}
        h2 {{ color: #2c3e50; font-size: 1.8em; margin-top: 40px; margin-bottom: 20px; border-bottom: 2px solid #ecf0f1; padding-bottom: 10px; }}
        h3 {{ color: #34495e; font-size: 1.4em; margin-top: 30px; margin-bottom: 15px; }}
        h4 {{ color: #34495e; font-size: 1.1em; margin-top: 20px; margin-bottom: 10px; font-weight: 600; }}
        p {{ margin-bottom: 15px; text-align: justify; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ background: #2c3e50; color: white; padding: 12px; text-align: left; font-weight: 600; }}
        td {{ border: 1px solid #ddd; padding: 10px 12px; }}
        tr:nth-child(even) {{ background: #f9f9f9; }}
        tr:hover {{ background: #f0f0f0; }}
        code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-family: 'Courier New', monospace; font-size: 0.95em; color: #c7254e; }}
        pre {{ background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 5px; overflow-x: auto; margin: 20px 0; font-family: 'Courier New', monospace; font-size: 0.9em; }}
        pre code {{ background: none; color: inherit; padding: 0; }}
        ul, ol {{ margin-left: 20px; margin-bottom: 15px; }}
        li {{ margin-bottom: 8px; }}
        blockquote {{ border-left: 4px solid #3498db; padding-left: 15px; margin-left: 0; margin-bottom: 15px; color: #555; font-style: italic; }}
        .footer {{ margin-top: 50px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; color: #999; font-size: 0.9em; }}
        @media print {{ body {{ padding: 0; background: white; }} .container {{ box-shadow: none; max-width: 100%; }} }}
        @page {{ margin: 2cm; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
            <div class="metadata">
                <div class="metadata-item"><span class="metadata-label">Document ID:</span> {doc_id}</div>
                <div class="metadata-item"><span class="metadata-label">Product:</span> Ghost Assistant Operating System (GAOS™)</div>
                <div class="metadata-item"><span class="metadata-label">Vendor:</span> Aether Frameworks Ltd</div>
                <div class="metadata-item"><span class="metadata-label">Status:</span> Released</div>
                <div class="metadata-item"><span class="metadata-label">Date:</span> 2026-06-09</div>
                <div class="metadata-item"><span class="metadata-label">Revision:</span> 2.0</div>
            </div>
        </div>
        <div class="content">
'''

def convert_markdown_to_html(md_content):
    """Convert markdown to HTML."""
    # Escape HTML special characters first
    md_content = md_content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    md_content = md_content.replace('&amp;lt;', '&lt;').replace('&amp;gt;', '&gt;')

    # Process inline formatting
    md_content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', md_content)
    md_content = re.sub(r'__(.+?)__', r'<strong>\1</strong>', md_content)
    md_content = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'<em>\1</em>', md_content)
    md_content = re.sub(r'`([^`]+?)`', r'<code>\1</code>', md_content)
    md_content = re.sub(r'\[([^\]]+?)\]\(([^)]+?)\)', r'<a href="\2">\1</a>', md_content)

    lines = md_content.split('\n')
    html = []
    i = 0
    in_table = False
    in_code = False
    table_header_done = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Code blocks
        if stripped.startswith('```'):
            if not in_code:
                html.append('<pre><code>')
                in_code = True
            else:
                html.append('</code></pre>')
                in_code = False
            i += 1
            continue

        if in_code:
            html.append(line)
            i += 1
            continue

        # Skip empty lines between sections
        if not stripped:
            i += 1
            continue

        # Headers
        if stripped.startswith('# '):
            # Skip main title
            i += 1
            continue
        elif stripped.startswith('## '):
            title = stripped[3:].strip()
            html.append(f'<h2>{title}</h2>')
        elif stripped.startswith('### '):
            title = stripped[4:].strip()
            html.append(f'<h3>{title}</h3>')
        elif stripped.startswith('#### '):
            title = stripped[5:].strip()
            html.append(f'<h4>{title}</h4>')

        # Horizontal rules
        elif stripped.startswith('---'):
            html.append('<hr style="margin: 30px 0; border: none; border-top: 1px solid #ddd;">')

        # Tables
        elif '|' in stripped:
            if not in_table:
                html.append('<table>')
                in_table = True
                table_header_done = False

            if not table_header_done and '---' not in stripped:
                cells = [c.strip() for c in line.split('|')[1:-1]]
                html.append('<tr>')
                for cell in cells:
                    html.append(f'<th>{cell}</th>')
                html.append('</tr>')
                table_header_done = True
            elif '---' not in stripped:
                cells = [c.strip() for c in line.split('|')[1:-1]]
                html.append('<tr>')
                for cell in cells:
                    html.append(f'<td>{cell}</td>')
                html.append('</tr>')
        elif in_table:
            html.append('</table>')
            in_table = False

        # Blockquotes
        elif stripped.startswith('> '):
            html.append(f'<blockquote>{stripped[2:]}</blockquote>')

        # Lists
        elif stripped.startswith('- ') or stripped.startswith('* '):
            indent = len(line) - len(line.lstrip())
            item = stripped[2:].strip()
            html.append(f'<ul style="margin-left: {indent}px;"><li>{item}</li></ul>')

        # Regular paragraphs
        else:
            if stripped:
                html.append(f'<p>{stripped}</p>')

        i += 1

    if in_table:
        html.append('</table>')

    return '\n'.join(html)

def write_html(md_path, title, doc_id):
    """Convert markdown file to HTML."""
    md_content = read_file(md_path)

    html_header = create_html_header(title, doc_id)
    html_content = convert_markdown_to_html(md_content)
    html_footer = '''
        </div>
        <div class="footer">
            <p>© 2026 Aether Frameworks Ltd. All rights reserved.</p>
        </div>
    </div>
</body>
</html>'''

    full_html = html_header + html_content + html_footer

    output_path = md_path.replace('.md', '.html')
    with open(output_path, 'w') as f:
        f.write(full_html)

    return output_path

# Convert both files
hlsr_out = write_html('/home/user/GAOS/docs/HLSR.md', 'GAOS™ High-Level System Requirements — v3.3', 'GAOS-HLSR-3.3')
print(f"✓ Created {hlsr_out}")

llsr_out = write_html('/home/user/GAOS/docs/LLSR.md', 'GAOS™ Low-Level System Requirements — v3.3', 'GAOS-LLSR-3.3')
print(f"✓ Created {llsr_out}")

print("\n✓ Both documents are ready!")
print("  - HLSR.html: Professional HTML version of HLSR")
print("  - LLSR.html: Professional HTML version of LLSR")
print("\nYou can now:")
print("  1. Open in a browser and print to PDF")
print("  2. Import into Google Docs (File → Open → Upload)")
print("  3. Copy/paste the content into Google Docs")
