; Wingman paste helper
; Usage: AutoHotkey.exe paste_ahk.ahk [focus|nofocus] [windowTitle]
#NoEnv
SendMode Input
SetWorkingDir %A_ScriptDir%

mode := (A_Args.Length() >= 1) ? A_Args[1] : "focus"
winTitle := (A_Args.Length() >= 2) ? A_Args[2] : "Phone Link"

; Read reply
FileRead, clip, %A_ScriptDir%\reply.txt
if (ErrorLevel) {
    MsgBox, 16, Wingman, Could not read reply.txt
    ExitApp
}

if (mode = "focus") {
    WinActivate, %winTitle%
    Sleep, 150
}

; Set clipboard and paste
ClipSaved := ClipboardAll
Clipboard := clip
Sleep, 60
Send, ^v
Sleep, 60
Clipboard := ClipSaved
ExitApp
