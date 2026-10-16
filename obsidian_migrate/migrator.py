from dataclasses import dataclass, field
from pathlib import Path
import shutil
import sys

from .scanner import VaultScanner
from .frontmatter import FrontmatterParser
from .category import normalize_category, extract_wikilink_target, is_class_seed
from .links import extract_all_links
from .resolver import LinkResolver, ResolveResult

@dataclass
class UnresolvedLink:
    source: str  # relative path of the source file
    link: str    # the raw link target

@dataclass 
class AmbiguousLink:
    source: str
    link: str
    candidates: list[str]

@dataclass
class MigrationPlan:
    vault_path: Path
    dest_path: Path
    seeds: list[Path]                    # absolute paths
    markdown_deps: list[Path]            # absolute paths (non-seed markdown deps)
    asset_deps: list[Path]               # absolute paths (non-md file deps)
    all_selected: list[Path]             # union, deduplicated, sorted
    unresolved: list[UnresolvedLink]
    ambiguous: list[AmbiguousLink]

class Migrator:
    def __init__(self, vault_path: Path, dest_path: Path, verbose: bool = False):
        self.vault_path = vault_path.resolve()
        self.dest_path = dest_path.resolve()
        self.verbose = verbose
    
    def plan(self) -> MigrationPlan:
        """Compute the migration plan without writing anything."""
        # 1. Scan vault
        scanner = VaultScanner(self.vault_path)
        all_files = scanner.scan()
        
        if self.verbose:
            print(f"Scanned {len(all_files)} files in vault.", file=sys.stderr)
        
        # 2. Build resolver
        resolver = LinkResolver(self.vault_path, all_files)
        
        # 3. Find primary Class seeds (category: [[Class]])
        primary_seeds: list[Path] = []
        for f in all_files:
            if f.suffix != '.md':
                continue
            try:
                content = f.read_text(encoding='utf-8', errors='replace')
            except Exception:
                continue
            fm = FrontmatterParser.parse(content)
            if is_class_seed(fm):
                primary_seeds.append(f)

        # Collect stems and filenames of primary seeds
        seed_targets: set[str] = {"Class"}
        for s in primary_seeds:
            seed_targets.add(s.stem)
            seed_targets.add(s.name)

        # Find all notes in vault that link to ANY primary seed (inbound / subject links)
        seeds: list[Path] = list(primary_seeds)
        seed_set: set[Path] = set(primary_seeds)

        for f in all_files:
            if f.suffix != '.md' or f in seed_set:
                continue
            try:
                content = f.read_text(encoding='utf-8', errors='replace')
            except Exception:
                continue

            links = extract_all_links(content, filename=f.name)
            fm = FrontmatterParser.parse(content)
            if fm:
                for key in ('category', 'subject'):
                    val = fm.get(key)
                    if val:
                        for norm in normalize_category(val):
                            target = extract_wikilink_target(norm)
                            if target:
                                links.append(target)

            is_class_related = False
            for l in links:
                target = extract_wikilink_target(l) or l
                target_stem = target.split('/')[-1].replace('.md', '')
                if target_stem in seed_targets or target in seed_targets:
                    is_class_related = True
                    break

            if is_class_related:
                seeds.append(f)
                seed_set.add(f)

        if self.verbose:
            print(f"Found {len(primary_seeds)} primary seeds and {len(seeds) - len(primary_seeds)} subject/inbound Class notes.", file=sys.stderr)
        
        # 4. For each seed, extract DIRECT (1-hop) dependencies
        selected: set[Path] = set(seeds)
        unresolved: list[UnresolvedLink] = []
        ambiguous: list[AmbiguousLink] = []
        
        visited_visuals: set[Path] = set()

        def add_with_visual_deps(file_path: Path):
            """If file_path is a composite visual file (.canvas, .excalidraw, .excalidraw.md),
            extract its internal embedded elements/pasted images so the drawing renders completely.
            """
            if file_path in visited_visuals:
                return
            visited_visuals.add(file_path)

            name_lower = file_path.name.lower()
            is_visual = (
                name_lower.endswith('.canvas') or
                name_lower.endswith('.excalidraw.md') or
                name_lower.endswith('.excalidraw')
            )
            if not is_visual:
                return

            try:
                comp_content = file_path.read_text(encoding='utf-8', errors='replace')
                comp_links = extract_all_links(comp_content, filename=file_path.name)
                for target in comp_links:
                    res = resolver.resolve(target, source_file=file_path)
                    if res.resolved:
                        try:
                            res.resolved.relative_to(self.vault_path)
                            selected.add(res.resolved)
                            add_with_visual_deps(res.resolved)
                        except ValueError:
                            pass
            except Exception:
                pass

        # First expand visual deps for any SEED notes that are visual files
        for seed in seeds:
            add_with_visual_deps(seed)

        # Extract 1-hop dependencies for seeds
        for seed in seeds:
            try:
                content = seed.read_text(encoding='utf-8', errors='replace')
            except Exception:
                continue
            
            links = extract_all_links(content, filename=seed.name)
            
            for link_target in links:
                result = resolver.resolve(link_target, source_file=seed)
                
                if result.resolved:
                    try:
                        result.resolved.relative_to(self.vault_path)
                        selected.add(result.resolved)
                        add_with_visual_deps(result.resolved)
                    except ValueError:
                        pass  # outside vault, skip
                elif result.ambiguous:
                    rel_source = str(seed.relative_to(self.vault_path))
                    ambiguous.append(AmbiguousLink(
                        source=rel_source,
                        link=link_target,
                        candidates=[str(c.relative_to(self.vault_path)) for c in result.candidates]
                    ))
                else:
                    rel_source = str(seed.relative_to(self.vault_path))
                    unresolved.append(UnresolvedLink(
                        source=rel_source,
                        link=link_target
                    ))
        
        # 5. Separate into categories
        all_sorted = sorted(selected, key=lambda p: str(p.relative_to(self.vault_path)))
        
        md_deps = [f for f in all_sorted if f.suffix == '.md' and f not in seed_set]
        asset_deps = [f for f in all_sorted if f.suffix != '.md' and f not in seed_set]
        
        return MigrationPlan(
            vault_path=self.vault_path,
            dest_path=self.dest_path,
            seeds=sorted(seeds, key=lambda p: str(p.relative_to(self.vault_path))),
            markdown_deps=md_deps,
            asset_deps=asset_deps,
            all_selected=all_sorted,
            unresolved=unresolved,
            ambiguous=ambiguous,
        )
    
    def execute(self, plan: MigrationPlan) -> int:
        """Execute the migration plan. Returns number of files copied."""
        copied = 0
        for src in plan.all_selected:
            rel = src.relative_to(self.vault_path)
            dst = self.dest_path / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
            copied += 1
            if self.verbose:
                print(f"  COPY: {rel}", file=sys.stderr)
        return copied
