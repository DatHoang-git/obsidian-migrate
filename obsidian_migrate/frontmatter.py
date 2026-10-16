import yaml

class FrontmatterParser:
    @staticmethod
    def parse(content: str) -> dict | None:
        if not content.startswith('---\n'):
            return None
        
        parts = content.split('---\n', 2)
        if len(parts) < 3:
            return None
            
        yaml_content = parts[1]
        try:
            parsed = yaml.safe_load(yaml_content)
            if isinstance(parsed, dict):
                return parsed
            return None
        except yaml.YAMLError:
            return None
