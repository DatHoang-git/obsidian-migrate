import re
from typing import Any

def normalize_category(value: Any) -> list[str]:
    """Normalize the category frontmatter value into a list of strings.
    
    Handles:
    - None -> []
    - str -> [str]
    - list -> list (filtering non-strings)
    - anything else -> []
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []

def extract_wikilink_target(value: str) -> str | None:
    """Extract the note target from an Obsidian wikilink string.
    
    Examples:
        '[[Class]]' -> 'Class'
        '[[Class|Display Name]]' -> 'Class'
        '[[Class#Heading]]' -> 'Class'
        '[[Class#Heading|Display Name]]' -> 'Class'
        '[[folder/Note]]' -> 'folder/Note'
        'not a wikilink' -> None
    
    Uses regex: r'\[\[([^\]\|#]+)'
    Strips the target path to get just the note target.
    For category matching, we want the FULL path/name before # and |.
    """
    match = re.search(r'\[\[([^\]\|#]+)', value)
    if match:
        return match.group(1).strip()
    return None

def is_class_seed(frontmatter: dict | None) -> bool:
    """Check if the frontmatter indicates a Class seed note.
    
    A note is a seed if its 'category' property contains a wikilink
    whose target is exactly 'Class' (not substring).
    
    Handles:
    - category: "[[Class]]"
    - category: ["[[Class]]", "[[Other]]"]
    - category: "[[Class|Display]]" -> target is 'Class' -> True
    - category: "[[Class#Heading]]" -> target is 'Class' -> True
    - category: "[[Classification]]" -> target is 'Classification' -> False
    - category: "[[Computer Class]]" -> target is 'Computer Class' -> False
    - Missing/null category -> False
    
    The target comparison is:
        extract path, take basename (split on '/'), compare == 'Class'
    """
    if not frontmatter:
        return False
        
    categories = normalize_category(frontmatter.get('category'))
    for cat in categories:
        target = extract_wikilink_target(cat)
        if target:
            # Extract basename (last component)
            basename = target.split('/')[-1]
            if basename == 'Class':
                return True
                
    return False
