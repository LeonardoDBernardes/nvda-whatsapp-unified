# WhatsApp Unified 2.0.0 — WhatsApp accessibility for NVDA

NVDA add-on for **WhatsApp Desktop** (the Microsoft Store app, which uses WebView2) and for **WhatsApp Web** (Chrome, Edge, Brave and other Chromium-based browsers).

- Tested on NVDA 2026.2. Works from NVDA 2026.1 on.
- GPL-2 license (`COPYING` file).
- The shortcuts only apply while focus is in WhatsApp. In any other program, or on any other website, every key is left untouched for NVDA and for the program.

## What the add-on does

1. Shortcuts to jump to the chat list, to the last message and to the composer.
2. Per-message actions: play audio and video, pause, change speed, copy, read the full message, react and open the menu.
3. Speech filters: phone numbers, usage hints ("For more options...") and the "Maybe" prefix before names.
4. WhatsApp Web: NVDA stays in **focus mode the whole time, with no focus/browse mode switch sound** (explained below).
5. Focus recovery: when WhatsApp drops focus (for example, when the focused chat row leaves the screen), the add-on returns focus to the chat or message you were on.
6. A fix for the pop-up that steals focus when you select text in the app's composer (defect nvda#19772).

## Keys

### Anywhere in WhatsApp (app and Web)

| Key | What it does |
|---|---|
| Alt+1 | Go to the chat list (to the selected chat; if none, to the first one). |
| Alt+2 | Go to the message list (to the last message). |
| Alt+D | Go to the composer. **In Chrome and Edge, while focus is in WhatsApp Web, this key replaces the browser's "go to address bar"**; use Ctrl+L, which keeps working. In any other site or program, Alt+D belongs to the browser. |
| Shift+Alt+C | Open the call menu (the call button in the chat header). If it is not found, says "Call button not found". |
| Ctrl+Shift+E | Turn the phone number filter in messages on or off. |
| NVDA+Shift+H | Turn the usage hints filter on or off. |
| (no key) | **Inspect WhatsApp element**: speaks the role, name, states and address of the focused object. To use it, assign a key in NVDA → Preferences → Input gestures → WhatsApp Unified. |

### On a message (focus on a message of the open chat)

| Key | What it does |
|---|---|
| Enter | Plays or pauses the voice message or video. If the message has no player, Enter goes to WhatsApp as usual. |
| Alt+P | Pauses or resumes the audio. Only acts on a message with a player. In the composer (for example while recording audio) the key goes straight to WhatsApp. |
| Ctrl+S | Changes the audio speed. Only acts on a message with a player. |
| Shift+Enter | Message menu. If the menu button is not found, sends the Applications key. |
| Ctrl+Shift+Enter | React to the message. If the button is not found, says "Reaction button not found". |
| Ctrl+R | Reads the full message. If the text is cut ("... Read more"), it clicks "Read more", waits for the text to grow (checks every 60 ms, up to about 1.3 s) and speaks it. |
| Alt+Enter | The same, but opens the text in an NVDA browseable window (titled "Message"). |
| Alt+C | The same, but opens the text in a plain text window. |
| Ctrl+C | Copies the message text and says "Copied". With no text, **or if you selected a piece of text**, the key goes to WhatsApp. |

No other key is taken. In particular, **NVDA+Space** and **Esc** remain NVDA's and WhatsApp's own (see the focus mode section).

NVDA+Shift+H was checked against the NVDA 2026.2 commands and is free. NVDA+Shift+I is no longer used: in NVDA 2026.2 it is the magnifier color filter.

## Options

NVDA → Preferences → Settings → **WhatsApp Unified**. They take effect immediately, without restarting NVDA.

| Option | Default | What it does |
|---|---|---|
| Apply to | Both | App only (Desktop), WhatsApp Web only (browser), or both. |
| Filter phone numbers in messages | Yes | Removes from speech the phone number that appears as the message **sender** ("+55 11 91234-5678: text"). The message body is never changed. |
| Filter phone numbers in the chat list | No | The same in the chat list. |
| Silence usage hints | Yes | Cuts only complete known sentences, such as "For more options, press the arrow...", at the end of a chat name. Never touches message text, what you type or the text field. |
| Remove "Maybe" before contact names | Yes | "Maybe John" becomes "John", only in the chat name or the message sender. Never inside a message's text. |
| Keep focus mode automatically on WhatsApp Web, with no mode switch sound | Yes | Turns on the part described in the next section. |
| Recover focus when WhatsApp loses it | Yes | Turns on focus recovery. |

The old `disableFocusLock` option (1.x) was merged into "Keep focus mode automatically". If it was on in your `nvda.ini`, 2.0 honors that until you save the new panel.

## WhatsApp Web: stable focus mode, no mode switch sound

### The problem

On WhatsApp Web, NVDA played the "focus mode" / "browse mode" sound at every focus change, as if you were pressing NVDA+Space all the time.

### The cause (checked in the NVDA 2026.2 source code)

1. At every focus, the browser buffer asks NVDA whether the object wants focus mode (`shouldPassThrough`). The answer changes from object to object: the composer and table cells ask for focus mode; rows and buttons ask for browse mode.
2. NVDA plays the sound when the new mode differs from the **last announced mode**, which is kept in a **global** variable (`browseMode.reportPassThrough.last`). Going from a chat to the composer and back changes the mode twice: two sounds. Entering WhatsApp from another tab also plays one, because the global variable belongs to the other tab.

### What the add-on does

A buffer class of its own (`WhatsAppChromeVBuf`, derived from the Chromium one) is used **only in documents whose address is `web.whatsapp.com`** (help pages such as `faq.whatsapp.com` and the corporate site are not affected). The window title is never used to decide: with no confirmed address the add-on does nothing:

1. It is **born in focus mode** and pins that mode. For any WhatsApp object it always gives the same answer. With no varying answer there is no mode switch, so no sound.
2. It syncs NVDA's global variable at birth, when it gets focus and at every focus. Entering WhatsApp from another tab is also **silent** (zero sounds).
3. **Navigating to another site in the same tab releases the pin** (silently), and going back to WhatsApp pins it again. Turning off the "Keep focus mode automatically..." option takes effect at once, without reloading the page.
4. NVDA itself uses the same mechanism in Internet Explorer (MSHTML) and Excel.

### What stays native

- **NVDA+Space** remains NVDA's and **plays the sound**, because it is your deliberate choice. If you leave focus mode, the add-on respects it: rows and buttons do not pull focus mode back; only the composer does, as NVDA already does. Pressing NVDA+Space again returns to the pinned focus mode.
- **Esc** goes to WhatsApp (closes the chat, cancels a reply) instead of leaving focus mode and playing the sound.
- **Other sites** are never affected: the add-on's buffer is only used when the address is WhatsApp's.

### Limits

- Applies to Chromium with IAccessible2, which is NVDA's default. If you turned on UIA for Chromium browsers (see "Troubleshooting"), this mechanism does not run.
- Leaving WhatsApp for a page in browse mode may play **one** sound: it is NVDA's normal sound when the mode changes between documents.

## Focus recovery

WhatsApp mounts and unmounts rows as you scroll (the lists are virtualized). When the focused row is unmounted, focus falls to the list container, the page body or the document, and the screen reader says something like "grid", "document" or nothing.

1. The add-on remembers the last chat or message that had focus.
2. If focus falls to one of those places and **you did not press** a key that takes focus away on purpose (Esc, Tab, Enter, F6, Windows), it does **not** speak the container right away. It waits 200 ms. A recent **mouse click** (or a pressed button) also counts as legitimate movement: in that case the add-on recovers nothing and the focus is spoken normally.
3. If focus is still there, it returns focus to the remembered row. If that row was unmounted, it uses the selected row of the same list, then the closest one by position, then the first. NVDA speaks the row normally.
4. If it finds nothing, it speaks the original focus. At most **one recovery per second**: it never loops.

It also helps with this: after Alt+Tab, messages lose their names in WhatsApp; the add-on reads the text of the message parts when the name comes back empty.

## What changed in 2.0 and why

2.0 is a rewrite of the core, made after analyzing the 1.4.1 code against the NVDA 2026.2 source, other WhatsApp add-ons and the current WhatsApp (29/10/2026).

1. **No key is swallowed.** In 1.4 the global plugin's scripts called `gesture.send()` when "it was not for them", which swallowed NVDA commands system-wide (NVDA+Space, NVDA+Shift+I). Now each script decides in `getScript` and returns "nothing" outside WhatsApp, and the key follows its normal path.
2. **Stable, silent focus mode on the Web** (section above). It replaces the 1.4.1 workaround, which still played sound.
3. **The Web filters now work.** Since 1.3 they lived in the global plugin, which never receives the event that triggered them. Now the filters enter through NVDA's `filter_speechSequence` extension point, apply in the app and on the Web, and only act while focus is in WhatsApp.
4. **Alt+D works in the app.** In the app NVDA turns browse mode off, so no buffer exists; 1.x required one. Now every search walks the objects from the document root.
5. **"Copied" is spoken again** on Ctrl+C (a variable name error erased the translation function).
6. **WhatsApp parts are found by role, name and structure**, never by CSS class name, fixed identifier or fixed path. WhatsApp changes those on the server without notice.
7. **Focus recovery**, new (section above).
8. **Selection pop-up** that steals focus in the app's composer (nvda#19772): idea from Eyalson's add-on.
9. **Structure**: the code lives in the `globalPlugins/whatsAppUnified/` package; the app module (`appModules/whatsapp_root.py`) is thin and inherits NVDA's built-in module. The text module (Alt+C window) was moved into the package.
10. **Automated tests** (pytest, with a simulated NVDA) and a checker that verifies, against the NVDA 2026.2 source, every API used.

## What was removed and what NVDA does instead

| Removed in 2.0 | Why | Instead |
|---|---|---|
| Own Up and Down arrows and Ctrl+Enter in the app, and own menu navigation (`MessageMenuItemNav`, `_MenuNavBase`) | The menu base class was never initialized on overlay objects, raised errors and swallowed the arrows in menus. Focus mode already hands the arrows to WhatsApp. | WhatsApp's own arrows, in focus mode. |
| "Safe" Left and Right arrows | They hid the caret announcement in text fields. | WhatsApp and text field arrows, undisturbed. |
| Own NVDA+Space script | It swallowed the NVDA command system-wide. | **Native NVDA+Space** (toggles focus and browse mode). |
| NVDA+arrow "review last spoken text" | They shadowed NVDA's native review. | NVDA's review cursor (for example, desktop layout: Numpad 7, 8 and 9 for lines; 4, 5 and 6 for words; 1, 2 and 3 for characters). |
| NVDA+Shift+I as the inspector shortcut | It shadowed the NVDA 2026.2 magnifier color filter. | The inspector remains, with no key. Assign one in Input gestures. |
| Replacing NVDA's speech function | Fragile: if another add-on did the same, speech died on exit. | The `speech.extensions.filter_speechSequence` extension point. |
| Own `event_liveRegionChange` | It swallowed page announcements and lost the "assertive" priority. | NVDA's native live region handling. |
| Registering the WhatsApp executable | NVDA 2026.2 already maps `WhatsApp.Root.exe` by itself. | NVDA's built-in `whatsapp_root` module (the add-on inherits from it). |
| "Remove duplicates" | It could erase list content. | Nothing. |
| Fixed paths, automation identifiers and CSS classes | Obsolete; WhatsApp changes them on the server. | Search by role, name and structure. |
| `disableFocusLock` option | It duplicated the new option. | "Keep focus mode automatically...". |

## Troubleshooting

### NVDA freezes on WhatsApp Web with new Chrome or Edge (nvda#20846)

With Chromium 153 or newer, WhatsApp Web can freeze NVDA (Windows errors 1775 and 1816 in the log). **The add-on cannot fix this**: the fault is between NVDA and the browser.

Workaround, still to be tested on your computer: NVDA → Preferences → Settings → Advanced → "Use UIA with Microsoft Edge and other Chromium based browsers when available", and choose "Yes". Caution: with UIA in Chromium the objects are no longer IAccessible, so **this add-on's message keys and stable focus mode do not work on the Web** (Alt+1, Alt+2, Alt+D and the speech filters keep working). To go back, choose "Default".

### The mode switch sound still plays

1. Check that the "Keep focus mode automatically..." option is on and the scope includes the Web.
2. Check that the UIA option for Chromium is on "Default" (above).
3. Check the address: it only applies to `web.whatsapp.com`.
4. If you pressed NVDA+Space on purpose, the sound is NVDA's and is expected.

### An add-on key does nothing

The message keys only act with focus **on a message** of the open chat. Enter, Alt+P and Ctrl+S only act on a message with a player. Use the inspector (assign a key) to see the role and name of the focused object, and the document address.

### After Alt+Tab messages have no name

That is WhatsApp: it strips message names until you use the keyboard again. The add-on reads the text of the message parts when the name is empty. Pressing an arrow once also restores the names.

### Focus recovery gets in the way

Turn off "Recover focus when WhatsApp loses it". It never acts right after Esc, Tab, Enter, F6, Windows or a mouse click, and at most once per second.

### My old `nvda.ini`

The `whatsAppUnified` section stays the same. Old keys are tolerated.

## For developers

```
whatsapp-unified/
├── manifest.ini
├── COPYING
├── appModules/whatsapp_root.py          thin app module (inherits NVDA's)
├── globalPlugins/whatsAppUnified/
│   ├── __init__.py    global plugin: commands, focus, class choice
│   ├── settings.py    options and panel
│   ├── context.py     where we are: app, Web or something else
│   ├── tree.py        walk objects and find list, messages, composer
│   ├── messagetext.py text, "Read more", player, buttons
│   ├── overlays.py    ChatListRow, MessageRow, selection pop-up, host pane
│   ├── webmode.py     Chromium buffer pinned in focus mode
│   ├── recovery.py    focus recovery
│   ├── filters.py     speech filters
│   └── textwindow.py  Alt+C text window
├── doc/               pt_BR and en (generated from README.md and README.en.md by build.sh)
├── tests/             pytest, NVDA stubs and check_nvda_api.py
└── build.sh           builds the .nvda-addon
```

```
python3 -m pytest tests                  # tests with a simulated NVDA
python3 tests/check_nvda_api.py          # checks every API against the NVDA 2026.2 source
./build.sh                               # builds whatsAppUnified-2.0.0.nvda-addon
```

The stubs in `tests/stubs/` faithfully reproduce the part of `browseMode.py` that decides the mode and plays the sound; the control test proves that, without the add-on, the sound plays over the same focus path.

## Credits and license

This add-on is **GPL version 2** (`COPYING` file). It was born from the union of two GPL-2 add-ons and uses ideas from two others:

1. **Nuno Costa (nunotfc)** — [WhatsAppNG](https://github.com/nunotfc/WhatsAppNG): origin of the navigation (Alt+1, Alt+2, Alt+D), copy, full message reading, reactions and the message menu.
2. **starkrush123 / mrido1** — [WhatsApp-Enhancer](https://github.com/starkrush123/WhatsApp-Enhancer): origin of the text window, the inspector and the number and hint filters.
3. **Eyalson** — [whatsapp-desktop-access](https://github.com/Eyalson/whatsapp-desktop-access) (GPL-2): the idea of the selection pop-up fix and the host pane (nvda#19772), rewritten here.
4. **muhammadGagah** — [whatsapp-web-plus](https://github.com/muhammadGagah/whatsapp-web-plus) (MIT license): the `recoverFocusAfterRemoval` idea (return focus when the focused row is removed), rewritten here for NVDA.
5. **Leo** — unification, app and Web scope, audio control, Portuguese documentation, the 2.0 rewrite.

The NVDA 2026.2 code (NV Access, GPL-2) was the reference for every API used.

Current version: **2.0.0**.
