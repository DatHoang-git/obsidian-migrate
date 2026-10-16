"""Comprehensive test suite for obsidian-migrate.

Covers: seed detection, category normalization, wikilink extraction,
link extraction, link resolution, strict 1-hop traversal, and
filesystem safety.
"""

import hashlib
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure package is importable when running from repo root.
sys.path.insert(0, str(Path(__file__).parent.parent))

from obsidian_migrate.frontmatter import FrontmatterParser
from obsidian_migrate.category import normalize_category, extract_wikilink_target, is_class_seed
from obsidian_migrate.links import extract_wikilinks, extract_markdown_links
from obsidian_migrate.resolver import LinkResolver, ResolveResult
from obsidian_migrate.scanner import VaultScanner
from obsidian_migrate.migrator import Migrator
from obsidian_migrate.cli import validate_paths


# ─────────────────────────── helpers ──────────────────────────────

class VaultTestBase(unittest.TestCase):
    """Mixin providing a helper to create temporary vault structures."""

    def _create_vault(self, structure: dict, base: Path | None = None) -> Path:
        """Create a temporary vault from *structure*.

        Keys are relative paths; values are ``str`` (text) or ``bytes``.
        A fresh tempdir is created if *base* is None.
        """
        if base is None:
            td = tempfile.mkdtemp()
            base = Path(td)
            self.addCleanup(lambda d=td: shutil.rmtree(d, ignore_errors=True))
        for rel, content in structure.items():
            fp = base / rel
            fp.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                fp.write_bytes(content)
            else:
                fp.write_text(content, encoding='utf-8')
        return base

    def _dest_dir(self) -> Path:
        """Return a fresh temporary directory suitable as a migration dest."""
        td = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(td, ignore_errors=True))
        return Path(td)


# ─────────────────── 1. Seed detection ────────────────────────────

class TestSeedDetection(unittest.TestCase):
    """Tests 1–13: is_class_seed on various frontmatter dicts."""

    # ── positives ──

    def test_single_category_wikilink(self):
        self.assertTrue(is_class_seed({'category': '[[Class]]'}))

    def test_multi_category(self):
        self.assertTrue(is_class_seed({'category': ['[[Class]]', '[[NLP]]']}))

    def test_class_later_in_list(self):
        self.assertTrue(is_class_seed({'category': ['[[NLP]]', '[[Class]]']}))

    def test_category_with_alias(self):
        self.assertTrue(is_class_seed({'category': '[[Class|My Class]]'}))

    def test_category_with_heading(self):
        self.assertTrue(is_class_seed({'category': '[[Class#Section]]'}))

    def test_category_with_path(self):
        """[[7_Categories/Class]] should match via basename."""
        self.assertTrue(is_class_seed({'category': '[[7_Categories/Class]]'}))

    # ── negatives ──

    def test_no_class_category(self):
        self.assertFalse(is_class_seed({'category': '[[Lab]]'}))

    def test_missing_category(self):
        self.assertFalse(is_class_seed({'tags': ['note']}))

    def test_null_category(self):
        self.assertFalse(is_class_seed({'category': None}))

    def test_unrelated_text(self):
        self.assertFalse(is_class_seed({'category': 'just a string'}))

    def test_classification_not_matched(self):
        self.assertFalse(is_class_seed({'category': '[[Classification]]'}))

    def test_computer_class_not_matched(self):
        self.assertFalse(is_class_seed({'category': '[[Computer Class]]'}))

    def test_class_notes_not_matched(self):
        self.assertFalse(is_class_seed({'category': '[[Class Notes]]'}))

    def test_none_frontmatter(self):
        self.assertFalse(is_class_seed(None))

    def test_empty_frontmatter(self):
        self.assertFalse(is_class_seed({}))


# ────────────── 2. Category normalization ─────────────────────────

class TestCategoryNormalization(unittest.TestCase):

    def test_none_value(self):
        self.assertEqual(normalize_category(None), [])

    def test_string_value(self):
        self.assertEqual(normalize_category('[[Class]]'), ['[[Class]]'])

    def test_list_value(self):
        self.assertEqual(
            normalize_category(['[[Class]]', '[[NLP]]']),
            ['[[Class]]', '[[NLP]]'],
        )

    def test_int_value(self):
        self.assertEqual(normalize_category(42), [])

    def test_mixed_list_filters_nonstrings(self):
        self.assertEqual(normalize_category([42, '[[Class]]']), ['[[Class]]'])


# ────────────── 3. Wikilink target extraction ─────────────────────

class TestWikilinkExtraction(unittest.TestCase):

    def test_simple(self):
        self.assertEqual(extract_wikilink_target('[[Class]]'), 'Class')

    def test_alias(self):
        self.assertEqual(extract_wikilink_target('[[Class|Display]]'), 'Class')

    def test_heading(self):
        self.assertEqual(extract_wikilink_target('[[Class#Heading]]'), 'Class')

    def test_heading_and_alias(self):
        self.assertEqual(extract_wikilink_target('[[Class#Heading|Display]]'), 'Class')

    def test_path(self):
        self.assertEqual(extract_wikilink_target('[[folder/Note]]'), 'folder/Note')

    def test_not_a_wikilink(self):
        self.assertIsNone(extract_wikilink_target('just text'))


# ────────────── 4. Link extraction from content ───────────────────

class TestLinkExtraction(unittest.TestCase):

    def test_wikilink_in_content(self):
        self.assertEqual(extract_wikilinks('Here is a [[NoteA]] link.'), ['NoteA'])

    def test_embed_in_content(self):
        self.assertIn('image.png', extract_wikilinks('![[image.png]]'))

    def test_multiple_wikilinks(self):
        content = '[[A]] text [[B]] more [[C]]'
        result = extract_wikilinks(content)
        self.assertEqual(result, ['A', 'B', 'C'])

    def test_wikilink_with_alias(self):
        result = extract_wikilinks('See [[Note|displayed text]].')
        self.assertEqual(result, ['Note'])

    def test_wikilink_with_heading(self):
        result = extract_wikilinks('See [[Note#Heading]].')
        self.assertEqual(result, ['Note'])

    def test_markdown_link(self):
        result = extract_markdown_links('[text](path/to/file.md)')
        self.assertEqual(result, ['path/to/file.md'])

    def test_markdown_link_external_excluded(self):
        result = extract_markdown_links('[text](https://example.com)')
        self.assertEqual(result, [])

    def test_markdown_link_mailto_excluded(self):
        result = extract_markdown_links('[text](mailto:a@b.com)')
        self.assertEqual(result, [])

    def test_canvas_links_extraction(self):
        from obsidian_migrate.links import extract_all_links
        content = '''{
            "nodes": [
                {"id": "1", "type": "file", "file": "3_Assets/Pasted image 2026.png"},
                {"id": "2", "type": "text", "text": "See [[NoteA]] and ![[image.png]]"}
            ]
        }'''
        links = extract_all_links(content, filename="test.canvas")
        self.assertIn("3_Assets/Pasted image 2026.png", links)
        self.assertIn("NoteA", links)
        self.assertIn("image.png", links)


# ─────────────── 5. Link resolver ─────────────────────────────────

class TestLinkResolver(VaultTestBase):

    def setUp(self):
        self.vault_path = self._create_vault({
            'NoteA.md': '',
            'folder/NoteA.md': '',
            'folder/NoteB.md': '',
            'assets/image.png': b'PNG',
            'assets/something.excalidraw.md': '',
        })
        scanner = VaultScanner(self.vault_path)
        all_files = scanner.scan()
        self.resolver = LinkResolver(self.vault_path, all_files)
        self.source_file = self.vault_path / 'NoteA.md'

    # Test 29 — unique name resolves
    def test_resolve_simple(self):
        result = self.resolver.resolve('NoteB', self.source_file)
        self.assertIsNotNone(result.resolved)
        self.assertEqual(result.resolved, self.vault_path / 'folder' / 'NoteB.md')

    # Test 30 — with explicit .md extension
    def test_resolve_with_extension(self):
        result = self.resolver.resolve('NoteB.md', self.source_file)
        self.assertIsNotNone(result.resolved)
        self.assertEqual(result.resolved, self.vault_path / 'folder' / 'NoteB.md')

    # Test 31 — nested path
    def test_resolve_nested_path(self):
        result = self.resolver.resolve('folder/NoteA', self.source_file)
        self.assertIsNotNone(result.resolved)
        self.assertEqual(result.resolved, self.vault_path / 'folder' / 'NoteA.md')

    # Test 32 — ambiguous (NoteA.md exists in root and folder/)
    def test_resolve_ambiguous(self):
        result = self.resolver.resolve('NoteA', self.source_file)
        self.assertTrue(result.ambiguous)
        self.assertIsNone(result.resolved)
        self.assertEqual(len(result.candidates), 2)

    # Test 33 — unresolved
    def test_resolve_unresolved(self):
        result = self.resolver.resolve('NonExistent', self.source_file)
        self.assertIsNone(result.resolved)
        self.assertFalse(result.ambiguous)

    # Test 34 — excalidraw
    def test_resolve_excalidraw(self):
        result = self.resolver.resolve('something.excalidraw', self.source_file)
        self.assertIsNotNone(result.resolved)
        self.assertEqual(result.resolved, self.vault_path / 'assets' / 'something.excalidraw.md')

    # Test 35 — image asset
    def test_resolve_image(self):
        result = self.resolver.resolve('image.png', self.source_file)
        self.assertIsNotNone(result.resolved)
        self.assertEqual(result.resolved, self.vault_path / 'assets' / 'image.png')


# ─────────────── 6. Strict 1-hop enforcement ──────────────────────

class TestStrictOneHop(VaultTestBase):

    def _plan(self, structure: dict):
        vault = self._create_vault(structure)
        dest = self._dest_dir()
        m = Migrator(vault, dest)
        return m.plan(), vault

    # Test 36 — ClassA → B → C: only ClassA and B
    def test_one_hop_only(self):
        plan, v = self._plan({
            'ClassA.md': '---\ncategory: "[[Class]]"\n---\n[[B]]',
            'B.md': 'Content linking to [[C]]',
            'C.md': 'Independent node',
        })
        self.assertIn(v / 'ClassA.md', plan.all_selected)
        self.assertIn(v / 'B.md', plan.all_selected)
        self.assertNotIn(v / 'C.md', plan.all_selected)

    # Test 37 — ClassA → A → B → C: only ClassA and A
    def test_deep_chain_excluded(self):
        plan, v = self._plan({
            'ClassA.md': '---\ncategory: "[[Class]]"\n---\n[[A]]',
            'A.md': '[[B]]',
            'B.md': '[[C]]',
            'C.md': 'End',
        })
        self.assertIn(v / 'ClassA.md', plan.all_selected)
        self.assertIn(v / 'A.md', plan.all_selected)
        self.assertNotIn(v / 'B.md', plan.all_selected)
        self.assertNotIn(v / 'C.md', plan.all_selected)

    # Test 38 — dependency's own attachment NOT copied
    def test_dependency_attachment_not_copied(self):
        plan, v = self._plan({
            'ClassA.md': '---\ncategory: "[[Class]]"\n---\n[[NoteB]]',
            'NoteB.md': '![[image.png]]',
            'image.png': b'fake img',
        })
        self.assertIn(v / 'ClassA.md', plan.all_selected)
        self.assertIn(v / 'NoteB.md', plan.all_selected)
        self.assertNotIn(v / 'image.png', plan.all_selected)

    # Test 39 — seed's own asset IS copied
    def test_seed_direct_asset(self):
        plan, v = self._plan({
            'ClassA.md': '---\ncategory: "[[Class]]"\n---\n![[image.png]]',
            'image.png': b'fake img',
        })
        self.assertIn(v / 'ClassA.md', plan.all_selected)
        self.assertIn(v / 'image.png', plan.all_selected)

    # Test 40 — multiple seeds, overlapping deps, no duplicates
    def test_multiple_seeds_independent(self):
        plan, v = self._plan({
            'Class1.md': '---\ncategory: "[[Class]]"\n---\n[[Common]]',
            'Class2.md': '---\ncategory: "[[Class]]"\n---\n[[Common]]',
            'Common.md': 'Shared resource',
        })
        self.assertEqual(len(plan.all_selected), 3)
        self.assertIn(v / 'Class1.md', plan.all_selected)
        self.assertIn(v / 'Class2.md', plan.all_selected)
        self.assertIn(v / 'Common.md', plan.all_selected)

    # Test 41 — cycle ClassA → B → ClassA: no crash
    def test_cycle_handling(self):
        plan, v = self._plan({
            'ClassA.md': '---\ncategory: "[[Class]]"\n---\n[[B]]',
            'B.md': '[[ClassA]]',
        })
        self.assertEqual(len(plan.all_selected), 2)
        self.assertIn(v / 'ClassA.md', plan.all_selected)
        self.assertIn(v / 'B.md', plan.all_selected)

    def test_canvas_embedded_assets_copied(self):
        plan, v = self._plan({
            'ClassA.md': '---\ncategory: "[[Class]]"\n---\n![[board.canvas]]',
            'board.canvas': '{"nodes":[{"type":"file","file":"3_Assets/pasted.png"}]}',
            '3_Assets/pasted.png': b'PNG',
        })
        self.assertIn(v / 'ClassA.md', plan.all_selected)
        self.assertIn(v / 'board.canvas', plan.all_selected)
        self.assertIn(v / '3_Assets' / 'pasted.png', plan.all_selected)

    def test_excalidraw_embedded_assets_copied(self):
        plan, v = self._plan({
            'ClassA.md': '---\ncategory: "[[Class]]"\n---\n[[drawing.excalidraw]]',
            'drawing.excalidraw.md': '# Embedded files\nkey: [[Pasted Image 123.png]]',
            'Pasted Image 123.png': b'PNG',
        })
        self.assertIn(v / 'ClassA.md', plan.all_selected)
        self.assertIn(v / 'drawing.excalidraw.md', plan.all_selected)
        self.assertIn(v / 'Pasted Image 123.png', plan.all_selected)


# ─────────────── 7. Filesystem safety ─────────────────────────────

class TestFilesystem(VaultTestBase):

    # Test 42 — directory structure preserved
    def test_preserve_directory_structure(self):
        vault = self._create_vault({
            'ClassA.md': '---\ncategory: "[[Class]]"\n---\n[[nested/B]]',
            'nested/B.md': 'Hello',
        })
        dest = self._dest_dir()
        m = Migrator(vault, dest)
        m.execute(m.plan())
        self.assertTrue((dest / 'ClassA.md').exists())
        self.assertTrue((dest / 'nested' / 'B.md').exists())

    # Test 43 — file contents identical
    def test_preserve_file_contents(self):
        vault = self._create_vault({
            'ClassA.md': '---\ncategory: "[[Class]]"\n---\n[[B]]',
            'B.md': 'Exact content here ☺',
        })
        dest = self._dest_dir()
        m = Migrator(vault, dest)
        m.execute(m.plan())
        self.assertEqual(
            (dest / 'B.md').read_text(encoding='utf-8'),
            'Exact content here ☺',
        )

    # Test 44 — source untouched
    def test_source_untouched(self):
        vault = self._create_vault({
            'ClassA.md': '---\ncategory: "[[Class]]"\n---\n[[B]]',
            'B.md': 'Content',
        })
        h_class = hashlib.sha256((vault / 'ClassA.md').read_bytes()).hexdigest()
        h_b = hashlib.sha256((vault / 'B.md').read_bytes()).hexdigest()

        dest = self._dest_dir()
        m = Migrator(vault, dest)
        m.execute(m.plan())

        self.assertEqual(hashlib.sha256((vault / 'ClassA.md').read_bytes()).hexdigest(), h_class)
        self.assertEqual(hashlib.sha256((vault / 'B.md').read_bytes()).hexdigest(), h_b)

    # Test 45 — dry-run: no files created
    def test_dry_run_no_files(self):
        vault = self._create_vault({
            'ClassA.md': '---\ncategory: "[[Class]]"\n---\n[[B]]',
            'B.md': 'Content',
        })
        dest = self._dest_dir()
        # Remove the dest so we can verify it's not re-created
        shutil.rmtree(str(dest))
        m = Migrator(vault, dest)
        _plan = m.plan()
        # plan() itself must not create anything
        self.assertFalse(dest.exists())

    # Test 46 — non-empty destination rejected without --force
    def test_nonempty_destination_rejected(self):
        vault = self._create_vault({'dummy.md': 'x'})
        dest = self._dest_dir()
        (dest / 'old_file.txt').write_text('exist')

        with self.assertRaises(ValueError):
            validate_paths(vault, dest, force=False)

        # With force, should pass
        validate_paths(vault, dest, force=True)

    # Test 47 — destination inside source rejected
    def test_destination_inside_source_rejected(self):
        vault = self._create_vault({'dummy.md': 'x'})
        dest = vault / 'subdir'
        dest.mkdir()

        with self.assertRaises(ValueError):
            validate_paths(vault, dest, force=False)

    # Test 48 — .obsidian excluded from scan
    def test_obsidian_dir_excluded_by_default(self):
        vault = self._create_vault({
            '.obsidian/workspace': 'content',
            'ClassA.md': 'note',
        })
        scanner = VaultScanner(vault)
        files = scanner.scan()
        names = {f.name for f in files}
        self.assertNotIn('workspace', names)
        self.assertIn('ClassA.md', names)


# ─────────────── 8. Frontmatter parser ────────────────────────────

class TestFrontmatterParser(unittest.TestCase):

    def test_parse_standard(self):
        content = '---\ncategory: "[[Class]]"\n---\nBody text'
        fm = FrontmatterParser.parse(content)
        self.assertIsNotNone(fm)
        self.assertEqual(fm['category'], '[[Class]]')

    def test_parse_list(self):
        content = '---\ncategory:\n  - "[[Class]]"\n  - "[[NLP]]"\n---\nBody'
        fm = FrontmatterParser.parse(content)
        self.assertEqual(fm['category'], ['[[Class]]', '[[NLP]]'])

    def test_no_frontmatter(self):
        self.assertIsNone(FrontmatterParser.parse('No frontmatter here'))

    def test_empty_frontmatter(self):
        fm = FrontmatterParser.parse('---\n---\nBody')
        # yaml.safe_load('') returns None, so parse returns None
        self.assertIsNone(fm)

    def test_malformed_yaml(self):
        content = '---\n: invalid: yaml: [[\n---\nBody'
        self.assertIsNone(FrontmatterParser.parse(content))


if __name__ == '__main__':
    unittest.main()
