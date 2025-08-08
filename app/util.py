import yaml, os

def load_config(path='config.yaml'):
    if not os.path.exists(path):
        raise FileNotFoundError("config.yaml not found")
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def save_config(cfg, path='config.yaml'):
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
