#Requires AutoHotkey v2.0
#SingleInstance Force
SetTitleMatchMode "RegEx"

mode      := A_Args.Length >= 1 ? A_Args[1] : "nofocus"   ; focus|nofocus
target    := A_Args.Length >= 2 ? A_Args[2] : ""          ; "hwnd:12345" or title (unused if nofocus)
replyPath := A_Args.Length >= 3 ? A_Args[3] : ""
strategy  := A_Args.Length >= 4 ? A_Args[4] : "type"      ; type|paste|auto

text := ""
if FileExist(replyPath) {
    text := FileRead(replyPath, "UTF-8")
}

if (mode = "focus" && target != "") {
    try {
        if (SubStr(target,1,5) = "hwnd:") {
            hwnd := Integer(SubStr(target,6))
            ahkId := "ahk_id " . Format("0x{:X}", hwnd)
            WinActivate ahkId
            WinWaitActive ahkId,, 1.5
        } else {
            if WinExist(target) {
                WinActivate target
                WinWaitActive target,, 1.5
            }
        }
    } catch as e {
        ; swallow and keep going (we'll just type at current cursor)
    }
}

Sleep 60

if (strategy = "paste") {
    cb := ClipboardAll()
    try {
        A_Clipboard := ""
        A_Clipboard := text
        ClipWait 1.5
        Send "^v"
    } finally {
        Sleep 100
        A_Clipboard := cb
    }
} else if (strategy = "type") {
    SendText text
} else {
    ; auto: try paste, then type as fallback
    cb := ClipboardAll()
    try {
        A_Clipboard := ""
        A_Clipboard := text
        ClipWait 1
        Send "^v"
        Sleep 120
        ; Uncomment if paste often fails for you:
        ; SendText text
    } finally {
        Sleep 100
        A_Clipboard := cb
    }
}
