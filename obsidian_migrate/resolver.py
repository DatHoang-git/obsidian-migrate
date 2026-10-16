from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ResolveResult:
    resolved: Path | None = None
    ambiguous: bool = False
    candidates: list[Path] = field(default_factory=list)


class LinkResolver:
    """Resolves Obsidian wikilink targets to actual files in the vault."""

    def __init__(self, vault_path: Path, all_files: list[Path]):
        self.vault_path = vault_path
        self._build_index(all_files)

    def _build_index(self, all_files: list[Path]):
        """Build lookup indexes for file resolution.

        Indexes:
            _by_stem:    stem (no extension) -> [relative paths]
            _by_name:    full filename       -> [relative paths]
            _by_relpath: relative path str   -> relative Path (includes no-.md variant)
        """
        self._by_stem: dict[str, list[Path]] = {}
        self._by_name: dict[str, list[Path]] = {}
        self._by_relpath: dict[str, Path] = {}

        for abs_path in all_files:
            rel = abs_path.relative_to(self.vault_path)
            rel_str = str(rel)
            self._by_relpath[rel_str] = rel

            # Index by filename
            name = rel.name
            self._by_name.setdefault(name, []).append(rel)

            # Index by stem (filename without extension)
            stem = rel.stem
            self._by_stem.setdefault(stem, []).append(rel)

            # Also index by relative path without .md extension
            # BUT only if it wouldn't conflict with an existing full path
            if name.endswith('.md'):
                no_ext = str(rel)[:-3]  # remove .md
                if no_ext not in self._by_relpath:
                    self._by_relpath[no_ext] = rel

    def resolve(self, link_target: str, source_file: Path | None = None) -> ResolveResult:
        """Resolve a link target to a file in the vault.

        Resolution order:
        1. Exact relative path match (including no-.md shortcut for paths
           with directory components like 'folder/Note')
        2. Relative path + .md extension
        3. If source_file given, try relative to source's directory
        4. Filename / stem match across all files (with ambiguity detection)
        5. Excalidraw .excalidraw -> .excalidraw.md resolution
        """
        target = link_target.strip()
        if not target:
            return ResolveResult()

        has_path = '/' in target

        # 1. For targets with directory components (e.g. 'folder/Note'),
        #    use the exact relative-path index — the path itself disambiguates.
        if has_path:
            if target in self._by_relpath:
                return ResolveResult(resolved=self.vault_path / self._by_relpath[target])
            target_md = target + '.md'
            if target_md in self._by_relpath:
                return ResolveResult(resolved=self.vault_path / self._by_relpath[target_md])

        # 3. Try relative to source file's directory (only if path components specified, e.g. ../foo or folder/bar)
        if has_path and source_file is not None:
            source_dir = source_file.parent
            candidate = source_dir / target
            if candidate.exists() and candidate.is_file():
                try:
                    candidate.resolve().relative_to(self.vault_path.resolve())
                    return ResolveResult(resolved=candidate.resolve())
                except ValueError:
                    pass
            candidate_md = source_dir / (target + '.md')
            if candidate_md.exists() and candidate_md.is_file():
                try:
                    candidate_md.resolve().relative_to(self.vault_path.resolve())
                    return ResolveResult(resolved=candidate_md.resolve())
                except ValueError:
                    pass

        # 4. Try filename match (handles bare names like 'NoteB')
        target_path = Path(target)
        name = target_path.name

        # For names without path components, do stem-based lookup to detect ambiguity
        if '/' not in target:
            # Has an explicit non-.md extension (e.g. image.png)?
            if target_path.suffix and target_path.suffix != '.md':
                # Look by full filename
                if name in self._by_name:
                    matches = self._by_name[name]
                    if len(matches) == 1:
                        return ResolveResult(resolved=self.vault_path / matches[0])
                    return ResolveResult(
                        ambiguous=True,
                        candidates=[self.vault_path / m for m in matches]
                    )
            else:
                # No extension or .md extension — look by stem
                lookup_stem = target_path.stem if target_path.suffix == '.md' else name
                if lookup_stem in self._by_stem:
                    matches = self._by_stem[lookup_stem]
                    if len(matches) == 1:
                        return ResolveResult(resolved=self.vault_path / matches[0])
                    return ResolveResult(
                        ambiguous=True,
                        candidates=[self.vault_path / m for m in matches]
                    )

        # 5. For excalidraw links: [[something.excalidraw]] resolves to something.excalidraw.md
        if target.endswith('.excalidraw'):
            excalidraw_md = target + '.md'
            if excalidraw_md in self._by_relpath:
                return ResolveResult(resolved=self.vault_path / self._by_relpath[excalidraw_md])
            exc_name = Path(excalidraw_md).name
            if exc_name in self._by_name:
                matches = self._by_name[exc_name]
                if len(matches) == 1:
                    return ResolveResult(resolved=self.vault_path / matches[0])
                return ResolveResult(
                    ambiguous=True,
                    candidates=[self.vault_path / m for m in matches]
                )

        return ResolveResult()
