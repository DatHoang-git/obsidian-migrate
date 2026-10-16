from pathlib import Path

class VaultScanner:
    def __init__(self, vault_path: Path):
        self.vault_path = vault_path.resolve()

    def scan(self) -> list[Path]:
        files = []
        for p in self.vault_path.rglob('*'):
            if not p.is_file():
                continue
            
            parts = p.relative_to(self.vault_path).parts
            if '.obsidian' in parts or '.git' in parts:
                continue
                
            if any(part.startswith('.') for part in parts[:-1]):
                continue
                
            files.append(p)
        return files
