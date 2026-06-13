import yaml
import os

MAPPING_FILE = "backend/data/sic_to_sector.yaml"

class SectorMapper:
    def __init__(self):
        self.mapping = {}
        if os.path.exists(MAPPING_FILE):
            with open(MAPPING_FILE, 'r') as f:
                data = yaml.safe_load(f)
                if data and 'mapping' in data:
                    self.mapping = data['mapping']
                    
    def get_sector(self, sic_code: str) -> str:
        if not sic_code:
            return "Unclassified"
            
        try:
            sic_int = int(sic_code)
        except ValueError:
            return "Unclassified"
            
        for key, sector in self.mapping.items():
            parts = key.split('-')
            if len(parts) == 2:
                start, end = int(parts[0]), int(parts[1])
                if start <= sic_int <= end:
                    return sector
                    
        return "Unclassified"
