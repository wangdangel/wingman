import os, json, time

def slugify(name: str):
    return "".join(c for c in name if c.isalnum() or c in ("-","_"," ")).strip().replace(" ","_").lower()

def ensure_person_folder(base_dir, name):
    slug = slugify(name or "unknown")
    folder = os.path.join(base_dir, slug)
    os.makedirs(folder, exist_ok=True)
    return folder

def save_profile(folder, bio_text=None, traits=None, screenshot_img=None):
    if bio_text:
        with open(os.path.join(folder, "profile.txt"), "w", encoding="utf-8") as f:
            f.write(bio_text)
    if traits is not None:
        with open(os.path.join(folder, "profile.json"), "w", encoding="utf-8") as f:
            json.dump(traits, f, ensure_ascii=False, indent=2)
    if screenshot_img is not None:
        path = os.path.join(folder, "profile.png")
        screenshot_img.save(path)
        return path
    return None

def save_chat_history(folder, text):
    ts = time.strftime("%Y%m%d-%H%M%S")
    with open(os.path.join(folder, f"chat_{ts}.md"), "w", encoding="utf-8") as f:
        f.write(text)
