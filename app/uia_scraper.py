import uiautomation as uia

PHONE_TITLES = ["Phone Link", "Link to Windows", "Your Phone"]

def get_phone_window(timeout=0.8):
    # Try name regex first
    w = uia.WindowControl(searchDepth=8, NameRegex="(Phone Link|Link to Windows|Your Phone)")
    if w.Exists(timeout, 0):
        return w
    # Fallback: scan top-level windows
    root = uia.GetRootControl()
    for win in root.GetChildren():
        try:
            name = (win.Name or "")
        except Exception:
            continue
        if isinstance(win, uia.WindowControl) and any(t in name for t in PHONE_TITLES):
            return win
    return None

def _iter_descendants(ctrl, depth=0, max_depth=5):
    """Breadth-ish traversal using GetChildren() (FindAll doesn't exist in this lib)."""
    if depth > max_depth or ctrl is None:
        return
    try:
        children = ctrl.GetChildren()
    except Exception:
        return
    for ch in children:
        yield ch
        yield from _iter_descendants(ch, depth + 1, max_depth)

def _collect_text(ctrl, max_depth=5):
    lines = []
    for node in _iter_descendants(ctrl, max_depth=max_depth):
        try:
            if isinstance(node, uia.TextControl):
                s = (node.Name or "").strip()
                if s:
                    lines.append(s)
        except Exception:
            continue
    return lines

def read_chat_text():
    """Try to find a container with lots of TextControls (the thread area)."""
    w = get_phone_window()
    if not w:
        return None

    # Candidate containers we expect to hold the conversation
    candidates = []
    for node in _iter_descendants(w, max_depth=4):
        if isinstance(node, (uia.ListControl, uia.PaneControl, uia.GroupControl)):
            candidates.append(node)

    # Score candidates by how many text nodes they contain
    best_text = None
    best_score = -1
    for c in candidates:
        lines = _collect_text(c, max_depth=2)
        score = len(lines)
        if score > best_score:
            best_score = score
            best_text = lines

    if best_text and best_score >= 8:
        return "\n".join(best_text)
    return None

def read_profile_text():
    """Heuristic: find a smaller/denser text block likely to be the profile/bio area."""
    w = get_phone_window()
    if not w:
        return None

    blocks = []
    for node in _iter_descendants(w, max_depth=3):
        if isinstance(node, (uia.PaneControl, uia.GroupControl)):
            lines = _collect_text(node, max_depth=1)
            if 5 <= len(lines) <= 200:
                text = "\n".join(lines)
                # crude filters to avoid entire chat threads
                if len(text) < 3000:
                    blocks.append((len(lines), text))

    # Pick the smallest “reasonable” block (more likely profile)
    if blocks:
        blocks.sort(key=lambda t: t[0])
        return blocks[0][1]
    return None
