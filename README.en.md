# WhatsApp Unified 2.0.9 — WhatsApp accessibility for NVDA

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
| Ctrl+Right arrow / Ctrl+Left arrow | Reads the message word by word (next / previous) without leaving it. Starts at the first word and stops at the last and the first. In browse mode NVDA's own Ctrl+arrows apply. |
| Ctrl+C | Copies the message text and says "Copied". With no text, **or if you selected a piece of text**, the key goes to WhatsApp. |

Inside a WhatsApp menu (message menu, reaction bar), in focus mode, up and down arrow walk the options and **Esc goes straight to WhatsApp** (closes the menu, no mode switch sound); see "What changed in 2.0.3". Outside menus, **Esc** goes to WhatsApp on the Web and in the app (since 2.0.9; on a message, for example, it returns to the chat list) and **NVDA+Space** remains NVDA's own (see the focus mode section).

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
| Message menu starts on the options (Reply, Copy), not on the reactions | Yes | When the message menu opens, focus goes straight to the first option (the add-on uses WhatsApp's own Tab). Up arrow on the first option goes to the reactions; down arrow on the reactions returns to the options. |
| Log add-on actions in the NVDA log (diagnostics) | Yes (in this test version) | Writes a line starting with `WhatsAppUnificado:` to the NVDA log (INFO level, open it with NVDA+F1) whenever the add-on acts: overlay applied, focus deferred or recovered, script run, speech filtered, focus mode pinned or released. At most one line per action every 2 seconds and 3000 lines per session. It never records message text, only the object's role and the text length. |

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
- **Esc** in focus mode goes to WhatsApp, as in the app (2.0.9): no sound and no browse mode. On a message it returns to the chat list. **Inside a WhatsApp menu** (message menu, reaction bar) the plugin takes Esc first (2.0.3); the habit Esc right after opening the menu ("Space then Esc") only repeats the option and the next one closes the menu (2.0.4). In 2.0.0 and 2.0.1 Esc also went to WhatsApp and broke that habit, because the menu handling did not exist yet; from 2.0.2 to 2.0.8 Esc outside menus was NVDA's (browse mode, with the sound). For browse mode, use NVDA+Space; there Esc is NVDA's.
- **Other sites** are never affected: the add-on's buffer is only used when the address is WhatsApp's.

### Limits

- Applies to Chromium with IAccessible2, which is NVDA's default. If you turned on UIA for Chromium browsers (see "Troubleshooting"), this mechanism does not run.
- Leaving WhatsApp for a page in browse mode may play **one** sound: it is NVDA's normal sound when the mode changes between documents.

## Focus recovery

WhatsApp mounts and unmounts rows as you scroll (the lists are virtualized). When the focused row is unmounted, focus falls to the list container, the page body or the document, and the screen reader says something like "grid", "document" or nothing.

1. The add-on remembers the last chat or message that had focus.
2. If focus falls to one of those places and **you did not press** a key that takes focus away on purpose (Esc, Tab, Enter, Space, F6, F10, Windows, Applications), it does **not** speak the container right away. It waits 200 ms. A recent **mouse click** (or a pressed button) also counts as legitimate movement: in that case the add-on recovers nothing and the focus is spoken normally.
3. If focus is still there, it returns focus to the remembered row. If that row was unmounted, it uses the selected row of the same list, then the closest one by position, then the first. NVDA speaks the row normally.
4. If it finds nothing, it speaks the original focus. At most **one recovery per second**: it never loops.

It also helps with this: after Alt+Tab, messages lose their names in WhatsApp; the add-on reads the text of the message parts when the name comes back empty.

## What changed in 2.0.9 (Esc on the Web like the app)

Leo's report (31/10/2026): on the Web, going back from a chat with Esc played NVDA's mode switch sound; pressing Esc again left the message history messed up and misaligned, and leaving to the chat list was broken too. The app was fine.

Why: in the app, Esc on a message goes to WhatsApp, which returns to the chat list. On the Web the add-on left that Esc to NVDA, which switched to browse mode (the sound); the next Esc, already in browse mode, went to the page.

1. **On the Web, Esc in focus mode goes to WhatsApp**, as in the app: no sound and no mode switch.
2. Esc inside the message menu is unchanged (the habit one repeats the option, the next one closes).
3. Browse mode is still on **NVDA+Space**; reading a message word by word no longer needs it (Ctrl+arrows, 2.0.7).
4. **The app does not change**: the change is only in the Web buffer.

## What changed in 2.0.8 (WhatsApp Web diagnostics)

Leo's report with 2.0.6 on the Web (31/10/2026): the message menu did not stop at the last option, going back played NVDA's mode switch sound, and after that the chat and the chat list were messed up. The NVDA log showed nothing of that test: the add-on's diagnostics had a 200-line limit per session and it had run out before.

1. The diagnostic limit is now **3000 lines** per NVDA session.
2. **Every mode switch on the Web** (focus or browse) writes a `modo-trocou` line, with where focus was and whether a menu was open.
3. An arrow inside a menu that stays with NVDA (browse mode or text field) writes a `menu-seta-do-nvda` line.
4. Entering and leaving the menu now say the program and the mode.

Nothing changes in use; it is for finding where the Web escapes.

## What changed in 2.0.7 (reading a message word by word)

Leo's report (31/10/2026): in 1.4, on a text message, holding Ctrl and using the side arrows read it word by word; in 2.0 that did not work, neither in the app nor on the Web.

Why: the app has no browse mode and the Web stays in focus mode on messages, so Ctrl+arrows went to WhatsApp, which does nothing with that key on a message (it only uses Ctrl+arrows on the audio player, for speed, and the player is another element).

1. **Ctrl+Right arrow** reads the next word of the message and **Ctrl+Left arrow** the previous one, in the app and on the Web. The first Ctrl+Right reads the first word; at the ends the word repeats and focus does not leave the message. A one-letter word is spelled.
2. Moving to another message starts again from the beginning.
3. **No conflict**: it only applies with focus on a message, in focus mode. In browse mode NVDA takes the key first (document word, as always). In the composer Ctrl+arrows stay the field's. A message without text: the key goes to WhatsApp.

## What changed in 2.0.6 (menu arrows belong to WhatsApp again)

Leo's report on 2.0.5 (30/10/2026): in the app, going down the message menu, on **Apagar** (Delete, one of the last options) focus went to the message below; on the Web, on **Denunciar** (Report). The menu should only close with Esc.

What the NVDA log showed: the menu closed **in the middle** of the options, never on the last one, about 300 to 400 milliseconds after the add-on moved focus to the next option on its own. 2.0.5 (stop at the last option) came from a wrong diagnosis and was **reverted**.

In WhatsApp's code, the options menu already moves with the arrows by itself and keeps focus inside. The add-on had taken the arrows in 2.0.2 because of the Esc that threw NVDA into browse mode, fixed in 2.0.3.

1. **Up and down arrows go to WhatsApp** inside the menu, the way WhatsApp was built to work with the keyboard.
2. **On the last option, down arrow stops** and repeats the option (no wrapping). On the first option, up arrow goes to the reaction bar, as before.
3. **Diagnostics**: the log says which option each arrow was on (e.g. `menu-seta baixo 9/11`). If the menu still closes by itself, it shows exactly where.

## What changed in 2.0.4 (habit Esc without a time limit)

Leo confirmed his way of working (30/10/2026): he opens the menu with **Space then Esc**, one key after the other; the **second Esc** closes the menu; with the menu closed, **one more Esc** goes back to the chat list. In 2.0.3 the first Esc only stayed in the menu if it came within 1.5 seconds, so someone pressing the keys calmly could have the menu closed right away.

1. The first Esc after the menu opens, before any arrow, **never** closes the menu, however long it takes: it only repeats the focused option.
2. The next Esc closes the menu (no sound). After an arrow, the first Esc already closes it.
3. With the menu closed, Esc is the usual one again.

## What changed in 2.0.3 (message menu no longer escapes, Esc without sound)

Leo's reports on 2.0.2 (30/10/2026): "walking the message menu with the arrows, it escapes to the message below or above", "on the Web, Space and Esc throw me to the reactions and one more Esc opens the menu" and "Esc in the menu makes the NVDA+Space sound". Both the app and the Web.

**The cause**, found in WhatsApp's 29/10 code and in NVDA 2026.2:

- From the keyboard, the message menu is **two** separate popups: the **reaction bar** (Like, Love, ... and "More reactions") and the **options menu** (Message info, Reply, Copy, ...). WhatsApp puts focus on the bar. WhatsApp's own path from the bar to the options is **Tab** (Shift+Tab back).
- **Esc** on a reaction never reached WhatsApp: NVDA used it to leave focus mode (the sound, the same as NVDA+Space). In browse mode the arrows walk the page, not the menu, and move into the messages above and below. That is what made the menu "escape".

**What 2.0.3 does:**

1. **Space opens straight on the options.** When focus lands on the reaction bar, the add-on sends WhatsApp's Tab and focus reaches the first option, without speaking the reaction. No Esc is needed after Space any more.
2. **Esc inside a WhatsApp menu goes to WhatsApp**: it closes the menu and returns to the message, **with no sound and no browse mode**, on the Web and in the app. (NVDA already does this for menu items on web pages; the add-on extends the rule to the reaction bar and the message menu.)
3. **"Space then Esc" habit**: an Esc right after the menu opens (before any arrow; no time limit since 2.0.4) does not close the menu; it repeats the focused option. The next Esc closes it.
4. **Arrows stay in the menu**: down and up walk only the options (since 2.0.6 WhatsApp itself moves; the add-on only stops at the last option). Up on the first option goes back to the reaction bar (Left and Right walk the reactions); down on the bar returns to the options. If focus ever lands on a menu in browse mode, the Web returns to focus mode by itself.
5. **Messages recognised without delay**: 2.0.2 searched for the message field to tell whether a row was a message, which cost 400 to 600 ms per message in Leo's log (and sometimes failed, leaving the message commands inactive). Now a few parent steps suffice: the chat list has a name, the message pane is the block that takes focus.
6. **Menu diagnostics**: with logging on, lines `menu-entrou` (with the role chain, never text), `menu-barra-para-opcoes`, `menu-seta`, `menu-esc`, `menu-esc-costume`, `menu-saiu` and `linha tipo=...` appear. If the menu still escapes, the log shows where and why.

## What changed in 2.0.2 (messages, message menu and Esc)

Leo's reports with 2.0.1 (30/10/2026) and what was found in WhatsApp's code of 29/10:

1. **Message commands work again.** NVDA's focus sits on a block inside the message row, not on the row; 2.0.x only recognized the row, so Ctrl+C, Shift+Enter, Ctrl+R and the others did nothing. Now the block is recognized and the commands look for the buttons in its row. The same applies to the chat list and to Alt+2.
2. **The message menu starts on Reply, not on the reactions.** WhatsApp added a reactions row at the top of the menu and, for keyboard users, focuses the first reaction. The add-on moves focus to the first option without speaking the reaction (new option, on by default).
3. **Arrows in the menu no longer slip to the message below.** Inside a menu, in focus mode, down and up arrow walk only the options (in 2.0.6 the arrows went back to WhatsApp; see "What changed in 2.0.6"). Up arrow on the first option goes to the reactions. If WhatsApp refuses focus on the option, the add-on speaks it and Enter activates it (as 1.4 did in the app). In browse mode and in text fields the arrows stay NVDA's.
4. **Native Esc again on the Web** (focus mode section).
5. **Space, the Applications key and F10 count as keys that move focus on purpose**: focus recovery no longer pulls focus back to the message while the menu opens (in the app Space had stopped opening the menu).
6. **Slowness diagnostics**: with the log on, whenever the add-on itself spends more than 100 ms (choosing classes, focus event, command, app host pane), the log shows a `lento ... N ms` line. This separates the add-on's delay from WhatsApp's, Chrome's or NVDA's.

## What changed in 2.0.1 (isolation)

Leo's report with 2.0.0: "it is influencing other windows". Cause and fix:

1. **No per-window verdict.** 2.0.0 remembered for 2 seconds that "this window is WhatsApp Web". In Chrome the tabs and the browser UI share windows, so other tabs looked like WhatsApp right after you left it. Now the context is computed **once per focus event**, from the address of the focused document (`web.whatsapp.com`), and applies to that focus only.
2. **Cheap, strict overlay choice.** For a browser object an overlay is chosen only if the current focus was already confirmed as WhatsApp Web and the object belongs to the same window. No browser call per object, on any site. The first object when entering WhatsApp (created before the focus event) gets its overlay in the focus event itself.
3. **Every global hook exits on its first line** when the focus is not in WhatsApp: speech (`filter_speechSequence`), keys (`decide_handleRawKey`, `getScript`), objects (`chooseNVDAObjectOverlayClasses`) and focus (`event_gainFocus`). Outside WhatsApp the add-on reads nothing but the program name.
4. **Focus mode and `reportPassThrough.last`.** The add-on writes it only with focus inside WhatsApp Web and, when leaving, gives back the value from before entering (once), so switching tabs sounds like plain NVDA. The buffer never pins the mode by assumption: with no confirmed address it is born released, and the document checks the address again when choosing the buffer.
5. **Diagnostics in the log** (new option, above), to show exactly when the add-on acts.

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
| Own Up and Down arrows and Ctrl+Enter in the app, and own menu navigation (`MessageMenuItemNav`, `_MenuNavBase`) | The menu base class was never initialized on overlay objects, raised errors and swallowed the arrows in menus. | 2.0.2 brings back a new, single menu navigation for app and Web (`menu.py`) that really moves focus and only speaks "from outside" when WhatsApp refuses focus. |
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

Turn off "Recover focus when WhatsApp loses it". It never acts right after Esc, Tab, Enter, Space, F6, F10, Windows, Applications or a mouse click, and at most once per second.

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
./build.sh                               # builds whatsAppUnified-2.0.9.nvda-addon
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

Current version: **2.0.9**.
