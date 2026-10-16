import json
import re
from pathlib import Path, PurePosixPath

def extract_wikilinks(content: str) -> list[str]:
    """Extract all wikilink targets from content.
    
    Matches both [[target]] and ![[target]] (embeds).
    Returns list of raw targets (before # and |).
    """
    pattern = r'!?\[\[([^\]]+?)(?:#[^\]]*?)?(?:\|[^\]]*?)?\]\]'
    return re.findall(pattern, content)

def extract_markdown_links(content: str) -> list[str]:
    """Extract local markdown link targets.
    
    Matches [text](target) but NOT external URLs (http://, https://, mailto:).
    Returns list of raw target paths.
    """
    pattern = r'(?<!!)\[([^\]]*)\]\(([^)]+)\)'
    matches = re.findall(pattern, content)
    
    links = []
    for _, target in matches:
        if not target.startswith(('http://', 'https://', 'mailto:')):
            links.append(target)
    return links

def extract_canvas_links(content: str) -> list[str]:
    """Extract local file references from an Obsidian .canvas JSON file.
    
    Extracts:
    1. Node 'file' references (e.g., "file": "3_Assets/image.png" or "file": "Note.md")
    2. Wikilinks [[...]] and markdown links [...] inside 'text' nodes or raw JSON content.
    """
    links: list[str] = []
    try:
        data = json.loads(content)
        if isinstance(data, dict) and "nodes" in data and isinstance(data["nodes"], list):
            for node in data["nodes"]:
                if isinstance(node, dict):
                    # 1. File nodes: {"type": "file", "file": "path/to/file"}
                    f = node.get("file")
                    if isinstance(f, str) and f:
                        if f not in links:
                            links.append(f)
                    # 2. Text nodes: {"type": "text", "text": "..."}
                    text = node.get("text")
                    if isinstance(text, str) and text:
                        for w in extract_wikilinks(text):
                            if w not in links:
                                links.append(w)
                        for m in extract_markdown_links(text):
                            if m not in links:
                                links.append(m)
    except Exception:
        pass

    # Regex fallback for "file": "..." patterns in JSON
    for match in re.finditer(r'"file"\s*:\s*"([^"]+)"', content):
        val = match.group(1).strip()
        if val and val not in links:
            links.append(val)

    # Extract any raw wikilinks or markdown links in canvas content
    for w in extract_wikilinks(content):
        if w not in links:
            links.append(w)
    for m in extract_markdown_links(content):
        if m not in links:
            links.append(m)

    return links

def extract_all_links(content: str, filename: str = "") -> list[str]:
    """Extract all local file references from content (Markdown, Excalidraw, or Canvas JSON)."""
    if filename.endswith('.canvas') or (content.lstrip().startswith('{') and '"nodes"' in content):
        return extract_canvas_links(content)
    
    links = extract_wikilinks(content) + extract_markdown_links(content)
    
    # Check if content has JSON file node pattern (e.g. embedded JSON in excalidraw/canvas)
    if '"file"' in content:
        for match in re.finditer(r'"file"\s*:\s*"([^"]+)"', content):
            val = match.group(1).strip()
            if val and val not in links:
                links.append(val)
                
    return links
