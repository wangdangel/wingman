import uiautomation as uia

PHONE_TITLES = ["Phone Link","Link to Windows","Your Phone"]

def get_phone_window(timeout=0.5):
    desktop = uia.GetRootControl()
    phone = desktop.WindowControl(searchDepth=2, NameRegex="(Phone Link|Link to Windows|Your Phone)")
    if phone.Exists(timeout, 0):
        return phone
    # broaden search
    for w in desktop.GetChildren():
        if w.ControlType == "WindowControl" and any(t in (w.Name or "") for t in PHONE_TITLES):
            return w
    return None

def read_text_from_descendants(ctrl, min_text=6):
    texts = ctrl.FindAll(3, lambda x: x.ControlType=="TextControl")
    # join visible names
    lines = []
    for t in texts:
        name = (t.Name or "").strip()
        if name:
            lines.append(name)
    if len(lines) >= min_text:
        return "\n".join(lines)
    return None

def read_chat_text():
    w = get_phone_window()
    if not w: return None
    # heuristically find a pane/list with lots of text
    candidates = w.FindAll(10, lambda c: c.ControlType in ("ListControl","PaneControl"))
    best = None
    for c in candidates:
        txt = read_text_from_descendants(c, min_text=8)
        if txt:
            return txt
    return None

def read_profile_text():
    # In Phone Link, profile may be a side pane; try scanning for dense text on left
    w = get_phone_window()
    if not w: return None
    panes = w.FindAll(10, lambda c: c.ControlType in ("PaneControl","GroupControl"))
    for p in panes:
        txt = read_text_from_descendants(p, min_text=5)
        if txt and len(txt) < 3000:
            # crude heuristic: shorter block likely profile/about info
            return txt
    return None
