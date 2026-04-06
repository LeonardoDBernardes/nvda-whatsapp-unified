# -*- coding: UTF-8 -*-
"""
WhatsApp Unified — módulo para WhatsApp Desktop (WebView2).
Unificação de whatsAppEnhancer (mrido1) e whatsAppNG (Nuno Costa).

Atalhos herdados do whatsAppNG:
  Alt+1              — Lista de conversas
  Alt+2              — Lista de mensagens
  Alt+D              — Campo de digitação
  Enter              — Tocar mensagem de voz ou vídeo
  Shift+Enter        — Menu de contexto da mensagem
  Ctrl+C             — Copiar mensagem
  Ctrl+R             — Ler mensagem completa (expande "ler mais")
  Alt+Enter          — Abrir mensagem em modo de navegação
  Ctrl+Shift+Enter   — Reagir à mensagem
  NVDA+Shift+H       — Alternar filtro de dicas de uso

Atalhos herdados do whatsAppEnhancer:
  Alt+C              — Abrir mensagem em janela de texto
  Shift+Alt+C        — Menu de chamada
  NVDA+Setas         — Revisar o último texto falado
  Ctrl+Shift+E       — Alternar filtro de números de telefone
  NVDA+Space         — Alternar modo de navegação
  NVDA+Shift+I       — Inspecionar elemento (desenvolvimento)
"""

import appModuleHandler
import api
import ui
import speech
import config
import re
import wx
import controlTypes
import treeInterceptorHandler
import addonHandler
from scriptHandler import script

addonHandler.initTranslation()

CONFIG_SECTION = "whatsAppUnified"
SPEC = {
    "scope":              "string(default='both')",   # 'desktop', 'web', 'both'
    "filterMessageList":  "boolean(default=True)",
    "filterChatList":     "boolean(default=False)",
    "filterUsageHints":   "boolean(default=True)",
    "filterTalvez":       "boolean(default=True)",
    "autoFocusMode":      "boolean(default=True)",
}

PHONE_RE = re.compile(r"\+\d[()\d\s-]{8,15}(?=[^\d]|$|\s)")
TALVEZ_RE = re.compile(r"\bTalvez\b\s*", re.IGNORECASE)
DURATION_RE = re.compile(r"\b\d+:\d{2}\b")
USAGE_HINT_RE = re.compile(
    r"(For more options|Para mais opções|Para más opciones|Pour plus|"
    r"Für weitere|Per altre|Untuk opsi|Para lebih|Daha fazla|Voor meer|"
    r"Для получения|Để biết|สำหรับ|その他|更多选项|अधिक|추가 옵션)",
    re.IGNORECASE,
)


def _role(obj):
    try:
        role = getattr(obj, "role", None)
        if isinstance(role, int):
            return role
        if hasattr(role, "value"):
            return role.value
        return role
    except Exception:
        return None


# ─── Utilitários ──────────────────────────────────────────────────────────────
def _collect(root, condition, max_items=50):
    if not root:
        return []
    results = []
    queue = [root]
    visited = 0
    while queue and visited < max_items:
        obj = queue.pop(0)
        visited += 1
        try:
            if condition(obj):
                results.append(obj)
            child = obj.firstChild
            while child:
                queue.append(child)
                child = child.next
        except Exception:
            continue
    return results


def _collect_texts(obj, min_length=20):
    texts = []
    try:
        if _role(obj) == controlTypes.Role.STATICTEXT:
            name = (getattr(obj, "name", "") or "").strip()
            if name and not name.startswith("00:") and len(name) > min_length:
                texts.append(name)
        val = str(getattr(obj, "value", "") or "").strip()
        if len(val) > min_length:
            texts.append(val)
        for child in getattr(obj, "children", []):
            texts.extend(_collect_texts(child, min_length))
    except Exception:
        pass
    return texts


def _find_buttons(obj):
    btns = []
    if _role(obj) == controlTypes.Role.BUTTON:
        btns.append(obj)
    for child in getattr(obj, "children", []):
        btns.extend(_find_buttons(child))
    return btns


def _find_slider(obj):
    try:
        r = _role(obj)
        if r in (controlTypes.Role.SLIDER, controlTypes.Role.PROGRESSBAR):
            return obj
        for child in getattr(obj, "children", []):
            result = _find_slider(child)
            if result:
                return result
    except Exception:
        pass
    return None


def _collect_buttons_until(obj, stop_obj):
    buttons = []
    if obj is stop_obj:
        return buttons, True
    if _role(obj) == controlTypes.Role.BUTTON:
        buttons.append(obj)
    for child in getattr(obj, "children", []):
        child_btns, found = _collect_buttons_until(child, stop_obj)
        buttons.extend(child_btns)
        if found:
            return buttons, True
    return buttons, False


def _find_collapsed(obj):
    try:
        if _role(obj) == controlTypes.Role.BUTTON and 512 in getattr(obj, "states", set()):
            return obj
        for child in getattr(obj, "children", []):
            result = _find_collapsed(child)
            if result:
                return result
    except Exception:
        pass
    return None


def _find_first_button(obj):
    if _role(obj) == controlTypes.Role.BUTTON:
        return obj
    for child in getattr(obj, "children", []):
        result = _find_first_button(child)
        if result:
            return result
    return None


# ─── App Module ────────────────────────────────────────────────────────────────
class AppModule(appModuleHandler.AppModule):

    disableBrowseModeByDefault = True
    scriptCategory = _("WhatsApp Unificado")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mainWindow = None
        self._chats_cache = None
        self._message_list_cache = None
        self._composer_cache = None
        self._electron_container = None
        self._composer_path = None
        self._toggling = False
        self._cfg = {}
        self._load_config()
        # Revisão de texto (herdado do whatsAppEnhancer)
        self._last_spoken_text = ""
        self._last_spoken_lines = []
        self._review_cursor = 0
        self._review_line_index = 0
        self._is_reviewing = False
        self._original_speak = None
        self._patch_speech()
        # Auto focus mode (herdado do whatsAppNG)
        treeInterceptorHandler.post_browseModeStateChange.register(
            self._on_browse_mode_change)

    def terminate(self):
        self._unpatch_speech()
        try:
            treeInterceptorHandler.post_browseModeStateChange.unregister(
                self._on_browse_mode_change)
        except Exception:
            pass
        super().terminate()

    def _load_config(self):
        if CONFIG_SECTION not in config.conf:
            config.conf[CONFIG_SECTION] = {}
        config.conf.spec[CONFIG_SECTION] = SPEC
        section = config.conf.get(CONFIG_SECTION, {})
        self._cfg["scope"] = section.get("scope", "both")
        bool_keys = {
            "filterMessageList": True,
            "filterChatList": False,
            "filterUsageHints": True,
            "filterTalvez": True,
            "autoFocusMode": True,
        }
        for k, dv in bool_keys.items():
            raw = section.get(k)
            if raw is None:
                self._cfg[k] = dv
            elif isinstance(raw, bool):
                self._cfg[k] = raw
            else:
                self._cfg[k] = str(raw).lower() == "true"

    # ── Browse mode ─────────────────────────────────────────────────────────────
    def _on_browse_mode_change(self, **kwargs):
        if not self._cfg.get("autoFocusMode", True):
            return
        try:
            focus = api.getFocusObject()
            app = getattr(focus, "appModule", None)
            if app and getattr(app, "processID", None) == self.processID:
                ti = getattr(focus, "treeInterceptor", None)
                if ti:
                    ti.passThrough = True
        except Exception:
            pass

    def event_gainFocus(self, obj, nextHandler):
        if not self.mainWindow or not getattr(self.mainWindow, "windowHandle", None):
            curr = obj
            while curr:
                if curr.role == controlTypes.Role.WINDOW:
                    self.mainWindow = curr
                    break
                curr = curr.parent
        if self._cfg.get("autoFocusMode", True):
            ti = getattr(obj, "treeInterceptor", None)
            if ti:
                ti.passThrough = True

        nextHandler()

    # ── Filtros de objetos ───────────────────────────────────────────────────────
    def event_NVDAObject_init(self, obj):
        if self._toggling:
            return
        try:
            app = getattr(obj, "appModule", None)
            if not (app and getattr(app, "processID", None) == self.processID):
                return
        except Exception:
            return
        if not obj.name:
            return

        name = obj.name
        obj_role = _role(obj)

        # Filtrar dicas de uso
        if self._cfg.get("filterUsageHints", True) and obj_role == 86:
            if not self._has_table_ancestor(obj) and USAGE_HINT_RE.search(name):
                hint_kw = re.search(
                    r"(arrow|seta|flecha|menu|context|contexto|ok\b)", name, re.I)
                if hint_kw:
                    name = USAGE_HINT_RE.split(name)[0].strip()
                    obj.name = re.sub(r"\s{2,}", " ", name).strip()
                    obj.role = controlTypes.Role.UNKNOWN
                    return

        # Remover duplicatas na lista de conversas
        if obj_role == 86 and self._has_table_ancestor(obj):
            obj.name = " "
            obj.role = controlTypes.Role.UNKNOWN
            return

        if len(name) < 12 and not name.startswith("Talvez "):
            return

        has_plus = "+" in name
        starts_talvez = name.startswith("Talvez ")
        if not has_plus and not starts_talvez:
            return

        filter_chat = self._cfg.get("filterChatList", False)
        filter_msg = self._cfg.get("filterMessageList", True)
        if not filter_chat and not filter_msg and not starts_talvez:
            return

        try:
            if obj_role == 86:
                if self._has_table_ancestor(obj):
                    if filter_chat:
                        obj.name = PHONE_RE.sub("", name)
                else:
                    if filter_msg:
                        obj.name = PHONE_RE.sub("", name)
                if starts_talvez and self._cfg.get("filterTalvez", True):
                    n = obj.name
                    obj.name = n[7:] if n.startswith("Talvez ") else n
            elif obj_role == 29:
                if filter_chat:
                    obj.name = PHONE_RE.sub("", name)
            if obj.name != name:
                obj.name = re.sub(r"\s{2,}", " ", obj.name).strip()
        except Exception:
            pass

    # ── Speech patching (herdado do whatsAppEnhancer) ────────────────────────────
    def _patch_speech(self):
        try:
            self._original_speak = speech.speech.speak
            speech.speech.speak = self._on_speak
        except Exception:
            try:
                self._original_speak = speech.speak
            except Exception:
                pass

    def _unpatch_speech(self):
        if self._original_speak:
            try:
                speech.speech.speak = self._original_speak
            except Exception:
                try:
                    speech.speak = self._original_speak
                except Exception:
                    pass

    def _on_speak(self, sequence, *args, **kwargs):
        if self._original_speak:
            self._original_speak(sequence, *args, **kwargs)
        if not self._is_reviewing:
            texts = [s for s in sequence if isinstance(s, str)]
            full = " ".join(texts)
            if full.strip():
                self._last_spoken_text = full
                self._last_spoken_lines = [l for l in texts if l.strip()]
                self._review_cursor = 0
                self._review_line_index = 0

    # ── Ajudantes ────────────────────────────────────────────────────────────────
    def _has_table_ancestor(self, obj):
        table_role = getattr(controlTypes.Role, "TABLE", None)
        curr = obj
        for _ in range(3):
            try:
                curr = curr.parent
                if curr is None:
                    return False
                if getattr(curr, "role", None) == table_role:
                    return True
            except Exception:
                break
        return False

    def _is_message_list(self):
        try:
            focus = api.getFocusObject()
            r = _role(focus)
            if r != 86 and r != controlTypes.Role.UNKNOWN:
                return False
            return not self._has_table_ancestor(focus)
        except Exception:
            return False

    def _is_video_message(self, parent):
        try:
            for child in getattr(parent, "children", []):
                for btn in _find_buttons(child):
                    if DURATION_RE.search(getattr(btn, "name", "") or ""):
                        return True
        except Exception:
            pass
        return False

    def _get_message_text(self, expand=True):
        if not self._is_message_list():
            return None, _("Não está na lista de mensagens")
        focus = api.getFocusObject()
        parent = getattr(focus, "parent", None)
        if not parent:
            return None, _("Mensagem não encontrada")
        siblings = getattr(parent, "children", []) or []
        parts = []
        for s in siblings:
            parts.extend(_collect_texts(s, 20))
        existing = " ".join(parts)
        if len(existing) > 800 or not expand:
            return (existing, None) if existing else (None, _("Texto não encontrado"))
        for s in siblings:
            collapsed = _find_collapsed(s)
            if collapsed:
                all_btns, _ = _collect_buttons_until(s, collapsed)
                focusable = [b for b in all_btns if 16777216 in getattr(b, "states", set())]
                btn = (focusable[1] if len(focusable) >= 2
                       else focusable[0] if focusable else None)
                if not btn:
                    continue
                btn.doAction()
                wx.CallLater(120, lambda: None)
                new_parts = []
                try:
                    for sib in getattr(parent, "children", []):
                        new_parts.extend(_collect_texts(sib, 20))
                except Exception:
                    pass
                full = "\r\n".join(new_parts)
                return (full, None) if full and len(full) > 300 else (None, _("Texto não encontrado"))
        return (existing, None) if existing else (None, _("Texto não encontrado"))

    def _get_electron_container(self):
        if self._electron_container:
            try:
                _ = self._electron_container.children
                return self._electron_container
            except Exception:
                self._electron_container = None
        try:
            fg = api.getForegroundObject()
            if fg:
                obj = fg
                for i in [0, 0, 0, 0, 3]:
                    children = getattr(obj, "children", []) or []
                    if i < len(children):
                        obj = children[i]
                    else:
                        return None
                self._electron_container = obj
                return obj
        except Exception:
            pass
        return None

    # ── Navegação (herdado do whatsAppNG) ─────────────────────────────────────────
    @script(description=_("Ir para lista de conversas"), gesture="kb:alt+1")
    def script_goToConversationList(self, gesture):
        self._toggling = True
        try:
            if self._chats_cache:
                try:
                    t = self._chats_cache
                    target = (t.firstChild if t.role == controlTypes.Role.LIST
                              and t.firstChild else t)
                    target.setFocus()
                    api.setNavigatorObject(target)
                    return
                except Exception:
                    self._chats_cache = None
            root = self.mainWindow or api.getForegroundObject()
            if not root:
                return
            for aid in ("ChatList", "Navigation", "ChatSearch"):
                from NVDAObjects.UIA import UIA
                import UIAHandler
                uia = getattr(root, "UIAElement", None)
                if uia:
                    try:
                        cond = UIAHandler.handler.clientObject.CreatePropertyCondition(
                            UIAHandler.UIA_AutomationIdPropertyId, aid)
                        els = uia.FindAll(UIAHandler.TreeScope_Descendants, cond)
                        if els.Length > 0:
                            found = UIA(UIAElement=els.GetElement(0))
                            self._chats_cache = found
                            target = (found.firstChild if found.role == controlTypes.Role.LIST
                                      and found.firstChild else found)
                            target.setFocus()
                            api.setNavigatorObject(target)
                            return
                    except Exception:
                        pass
            lists = _collect(root, lambda o: o.role == controlTypes.Role.LIST)
            candidates = [l for l in lists
                          if l.location and l.location.left < 450 and l.location.width < 500]
            if candidates:
                t = candidates[0]
                self._chats_cache = t
                item = t.firstChild or t
                item.setFocus()
                api.setNavigatorObject(item)
        except Exception:
            ui.message(_("Lista de conversas não encontrada"))
        finally:
            self._toggling = False

    @script(description=_("Ir para lista de mensagens"), gesture="kb:alt+2")
    def script_goToMessageList(self, gesture):
        self._toggling = True
        try:
            if self._message_list_cache:
                try:
                    t = self._message_list_cache
                    target = (t.lastChild if t.role == controlTypes.Role.LIST
                              and t.lastChild else t)
                    target.setFocus()
                    api.setNavigatorObject(target)
                    return
                except Exception:
                    self._message_list_cache = None
            root = self.mainWindow or api.getForegroundObject()
            if not root:
                return
            for aid in ("MessagesList", "Conversation", "MessageList"):
                from NVDAObjects.UIA import UIA
                import UIAHandler
                uia = getattr(root, "UIAElement", None)
                if uia:
                    try:
                        cond = UIAHandler.handler.clientObject.CreatePropertyCondition(
                            UIAHandler.UIA_AutomationIdPropertyId, aid)
                        els = uia.FindAll(UIAHandler.TreeScope_Descendants, cond)
                        if els.Length > 0:
                            found = UIA(UIAElement=els.GetElement(0))
                            self._message_list_cache = found
                            target = (found.lastChild if found.role == controlTypes.Role.LIST
                                      and found.lastChild else found)
                            target.setFocus()
                            api.setNavigatorObject(target)
                            return
                    except Exception:
                        pass
            lists = _collect(root, lambda o: o.role == controlTypes.Role.LIST)
            for l in lists:
                fc = l.firstChild
                if fc and "focusable-list-item" in getattr(
                        fc, "IA2Attributes", {}).get("class", ""):
                    self._message_list_cache = l
                    target = l.lastChild or l
                    target.setFocus()
                    api.setNavigatorObject(target)
                    return
            ui.message(_("Lista de mensagens não encontrada"))
        except Exception:
            ui.message(_("Lista de mensagens não encontrada"))
        finally:
            self._toggling = False

    @script(description=_("Ir para campo de digitação"), gesture="kb:alt+d")
    def script_focusComposer(self, gesture):
        self._toggling = True
        try:
            focus = api.getFocusObject()
            ti = getattr(focus, "treeInterceptor", None)
            if not ti:
                ui.message(_("Campo de digitação não encontrado"))
                return
            orig = ti.passThrough
            ti.passThrough = False
            container = self._get_electron_container()
            if self._composer_path and container:
                try:
                    obj = container
                    for i in self._composer_path:
                        children = getattr(obj, "children", []) or []
                        obj = children[i]
                    obj.setFocus()
                    ti.passThrough = True
                    return
                except Exception:
                    self._composer_path = None
            paths = []
            if container:
                paths.append((container, [5, 0, 3, 0, 0, 0, 2, 0]))
            paths.append((ti.rootNVDAObject, [0, 0, 0, 0, 3, 5, 0, 3, 0, 0, 0, 2, 0]))
            for root, path_indices in paths:
                try:
                    obj = root
                    for i in path_indices:
                        children = getattr(obj, "children", []) or []
                        obj = children[i]
                    obj.setFocus()
                    if root is container:
                        self._composer_path = path_indices
                    ti.passThrough = True
                    return
                except Exception:
                    continue
            edits = _collect(
                ti.rootNVDAObject,
                lambda o: o.role == controlTypes.Role.EDITABLETEXT)
            for e in edits:
                if "fd365im1" in getattr(e, "IA2Attributes", {}).get("class", ""):
                    e.setFocus()
                    ti.passThrough = True
                    return
            if edits:
                edits[-1].setFocus()
                ti.passThrough = True
                return
            ui.message(_("Campo de digitação não encontrado"))
            ti.passThrough = orig
        except Exception:
            ui.message(_("Campo de digitação não encontrado"))
        finally:
            self._toggling = False

    # ── Ações em mensagens ───────────────────────────────────────────────────────
    @script(description=_("Tocar mensagem de voz ou vídeo"), gesture="kb:enter")
    def script_playAudio(self, gesture):
        if not self._is_message_list():
            gesture.send()
            return
        try:
            focus = api.getFocusObject()
            parent = getattr(focus, "parent", None)
            if not parent:
                gesture.send()
                return
            if self._is_video_message(parent):
                for child in getattr(parent, "children", []):
                    btn = _find_first_button(child)
                    if btn:
                        btn.doAction()
                        return
            for sibling in getattr(parent, "children", []) or []:
                slider = _find_slider(sibling)
                if slider:
                    all_btns, _ = _collect_buttons_until(sibling, slider)
                    if all_btns:
                        all_btns[-1].doAction()
                        return
            gesture.send()
        except Exception:
            gesture.send()

    @script(description=_("Menu de contexto da mensagem"), gesture="kb:shift+enter")
    def script_contextMenu(self, gesture):
        if not self._is_message_list():
            gesture.send()
            return
        try:
            focus = api.getFocusObject()
            if focus.role == controlTypes.Role.EDITABLETEXT:
                gesture.send()
                return
            parent = getattr(focus, "parent", None)
            if not parent:
                ui.message(_("Menu não encontrado"))
                return
            for sibling in getattr(parent, "children", []) or []:
                btns = _find_buttons(sibling)
                if not btns:
                    continue
                for btn in btns:
                    if 512 in getattr(btn, "states", set()):
                        btn.doAction()
                        return
                btns[-1].doAction()
                return
            ui.message(_("Menu não encontrado"))
        except Exception:
            ui.message(_("Menu não encontrado"))

    @script(description=_("Copiar mensagem"), gesture="kb:control+c")
    def script_copyMessage(self, gesture):
        if not self._is_message_list():
            gesture.send()
            return
        try:
            focus = api.getFocusObject()
            name = getattr(focus, "name", "") or ""
            if not name:
                gesture.send()
                return
            text, _ = self._get_message_text(expand=False)
            if text:
                api.copyToClip(text)
                ui.message(_("Copiado"))
                return
            api.copyToClip(name.strip())
            ui.message(_("Copiado"))
        except Exception:
            gesture.send()

    @script(description=_("Ler mensagem completa"), gesture="kb:control+r")
    def script_readCompleteMessage(self, gesture):
        if not self._is_message_list():
            gesture.send()
            return
        focus = api.getFocusObject()
        if "…" not in (getattr(focus, "name", "") or ""):
            ui.message(_("Mensagem não está cortada"))
            return
        parent = getattr(focus, "parent", None)
        if not parent:
            ui.message(_("Mensagem não encontrada"))
            return
        siblings = getattr(parent, "children", []) or []
        parts = []
        for s in siblings:
            parts.extend(_collect_texts(s, 20))
        existing = " ".join(parts)
        if len(existing) > 800:
            ui.message(existing)
            return
        for s in siblings:
            collapsed = _find_collapsed(s)
            if collapsed:
                all_btns, _ = _collect_buttons_until(s, collapsed)
                focusable = [b for b in all_btns
                             if 16777216 in getattr(b, "states", set())]
                btn = (focusable[1] if len(focusable) >= 2
                       else focusable[0] if focusable else None)
                if not btn:
                    continue
                btn.doAction()
                msg_parent = parent
                def _speak_after():
                    new_parts = []
                    try:
                        for sib in getattr(msg_parent, "children", []):
                            new_parts.extend(_collect_texts(sib, 20))
                    except Exception:
                        pass
                    full = "\r\n".join(new_parts)
                    speech.cancelSpeech()
                    ui.message(full if full and len(full) > 300 else _("Texto não encontrado"))
                wx.CallLater(150, _speak_after)
                return
        ui.message(_("Texto não encontrado"))

    @script(description=_("Abrir mensagem em modo de navegação"), gesture="kb:alt+enter")
    def script_readCompleteMessageBrowse(self, gesture):
        if not self._is_message_list():
            gesture.send()
            return
        text, error = self._get_message_text(expand=True)
        if not error and text:
            ui.browseableMessage(text)
            return
        focus = api.getFocusObject()
        parent = getattr(focus, "parent", None)
        if parent:
            parts = []
            for s in getattr(parent, "children", []) or []:
                parts.extend(_collect_texts(s, 20))
            if parts:
                ui.browseableMessage(" ".join(parts))
                return
        name = (getattr(focus, "name", "") or "").strip()
        if name:
            ui.browseableMessage(name)
        else:
            gesture.send()

    @script(description=_("Reagir à mensagem"), gesture="kb:control+shift+enter")
    def script_reactMessage(self, gesture):
        if not self._is_message_list():
            gesture.send()
            return
        try:
            focus = api.getFocusObject()
            parent = getattr(focus, "parent", None)
            if not parent:
                gesture.send()
                return
            for sibling in getattr(parent, "children", []) or []:
                all_btns = _find_buttons(sibling)
                for i, btn in enumerate(all_btns):
                    if 512 in getattr(btn, "states", set()):
                        if i + 1 < len(all_btns):
                            all_btns[i + 1].doAction()
                            return
            gesture.send()
        except Exception:
            gesture.send()

    @script(description=_("Abrir mensagem em janela de texto"), gesture="kb:alt+c")
    def script_showTextWindow(self, gesture):
        obj = api.getFocusObject()
        text = getattr(obj, "name", "") or ""
        if self._is_message_list():
            t, _ = self._get_message_text(expand=True)
            if t:
                text = t
        if text.strip():
            from .wa_ui import TextWindow
            TextWindow(text.strip(), _("Mensagem"))
        else:
            gesture.send()

    @script(description=_("Abrir menu de chamada"), gesture="kb:shift+alt+c")
    def script_openCallMenu(self, gesture):
        if api.getFocusObject().role == controlTypes.Role.EDITABLETEXT:
            gesture.send()
            return
        cache = getattr(self, "_call_menu_btn_cache", None)
        if cache:
            try:
                cache.doAction()
                return
            except Exception:
                self._call_menu_btn_cache = None
        root = self.mainWindow or api.getForegroundObject()
        results = _collect(root, lambda o:
            o.role == controlTypes.Role.BUTTON and
            "xjb2p0i" in getattr(o, "IA2Attributes", {}).get("class", "") and
            "xk390pu" in getattr(o, "IA2Attributes", {}).get("class", ""),
            max_items=500)
        if results:
            self._call_menu_btn_cache = results[0]
            results[0].doAction()
        else:
            gesture.send()

    # ── Revisão de texto (herdado do whatsAppEnhancer) ────────────────────────────
    @script(description=_("Revisar caractere anterior"), gesture="kb:NVDA+leftArrow")
    def script_reviewPrevChar(self, gesture):
        if not self._last_spoken_text:
            return
        self._is_reviewing = True
        try:
            self._review_cursor = max(0, self._review_cursor - 1)
            speech.speak([self._last_spoken_text[self._review_cursor]])
        finally:
            self._is_reviewing = False

    @script(description=_("Revisar próximo caractere"), gesture="kb:NVDA+rightArrow")
    def script_reviewNextChar(self, gesture):
        if not self._last_spoken_text:
            return
        self._is_reviewing = True
        try:
            self._review_cursor = min(len(self._last_spoken_text) - 1,
                                      self._review_cursor + 1)
            speech.speak([self._last_spoken_text[self._review_cursor]])
        finally:
            self._is_reviewing = False

    @script(description=_("Revisar palavra anterior"), gesture="kb:NVDA+control+leftArrow")
    def script_reviewPrevWord(self, gesture):
        if not self._last_spoken_text:
            return
        self._is_reviewing = True
        try:
            t = self._last_spoken_text
            cur = self._review_cursor - 1
            while cur >= 0 and t[cur].isspace():
                cur -= 1
            end = cur + 1
            while cur >= 0 and not t[cur].isspace():
                cur -= 1
            self._review_cursor = max(0, cur + 1)
            speech.speak([t[self._review_cursor:end]])
        finally:
            self._is_reviewing = False

    @script(description=_("Revisar próxima palavra"), gesture="kb:NVDA+control+rightArrow")
    def script_reviewNextWord(self, gesture):
        if not self._last_spoken_text:
            return
        self._is_reviewing = True
        try:
            t = self._last_spoken_text
            cur = self._review_cursor
            while cur < len(t) and not t[cur].isspace():
                cur += 1
            while cur < len(t) and t[cur].isspace():
                cur += 1
            self._review_cursor = cur
            end = cur
            while end < len(t) and not t[end].isspace():
                end += 1
            speech.speak([t[cur:end]])
        finally:
            self._is_reviewing = False

    @script(description=_("Revisar linha anterior"), gesture="kb:NVDA+upArrow")
    def script_reviewPrevLine(self, gesture):
        if not self._last_spoken_lines:
            return
        self._is_reviewing = True
        try:
            self._review_line_index = max(0, self._review_line_index - 1)
            speech.speak([self._last_spoken_lines[self._review_line_index]])
        finally:
            self._is_reviewing = False

    @script(description=_("Revisar próxima linha"), gesture="kb:NVDA+downArrow")
    def script_reviewNextLine(self, gesture):
        if not self._last_spoken_lines:
            return
        self._is_reviewing = True
        try:
            self._review_line_index = min(len(self._last_spoken_lines) - 1,
                                          self._review_line_index + 1)
            speech.speak([self._last_spoken_lines[self._review_line_index]])
        finally:
            self._is_reviewing = False

    # ── Filtros alternáveis ──────────────────────────────────────────────────────
    @script(description=_("Alternar filtro de números de telefone"), gesture="kb:control+shift+e")
    def script_togglePhoneFilter(self, gesture):
        self._cfg["filterMessageList"] = not self._cfg["filterMessageList"]
        config.conf[CONFIG_SECTION]["filterMessageList"] = self._cfg["filterMessageList"]
        config.conf.save()
        state = _("ativado") if self._cfg["filterMessageList"] else _("desativado")
        ui.message(_("Filtro de telefone {state}").format(state=state))

    @script(description=_("Alternar filtro de dicas de uso"), gesture="kb:NVDA+shift+h")
    def script_toggleHintsFilter(self, gesture):
        self._cfg["filterUsageHints"] = not self._cfg["filterUsageHints"]
        config.conf[CONFIG_SECTION]["filterUsageHints"] = self._cfg["filterUsageHints"]
        config.conf.save()
        state = _("ativado") if self._cfg["filterUsageHints"] else _("desativado")
        ui.message(_("Filtro de dicas {state}").format(state=state))

    # ── Proteção contra chamadas acidentais ─────────────────────────────────────
    # Palavras-chave que identificam botões de chamada no cabeçalho
    _CALL_BTN_RE = re.compile(
        r"(chamada|call|ligar|áudio call|audio call|vídeo|video\s*call)",
        re.IGNORECASE,
    )

    def _is_conv_list_item(self, obj):
        """Retorna True se o objeto é um item da lista de conversas (painel esquerdo)."""
        try:
            r = _role(obj)
            return r in (86, 29, controlTypes.Role.UNKNOWN) and self._has_table_ancestor(obj)
        except Exception:
            return False

    @script(description=_("Navegar esquerda (protegido)"), gesture="kb:leftArrow")
    def script_safeLeftArrow(self, gesture):
        """
        Na lista de conversas: redireciona para seta cima (conversa anterior)
        para evitar entrar nos sub-elementos inline (botões de chamada, etc.).
        No histórico e outros contextos: passa normalmente — as setas navegam
        reações, controles de áudio, arquivos e links dentro das mensagens.
        """
        try:
            if self._is_conv_list_item(api.getFocusObject()):
                import keyboardHandler
                keyboardHandler.KeyboardInputGesture.fromName("upArrow").send()
                return
        except Exception:
            pass
        self._arrow_came_from_msg = True
        gesture.send()

    @script(description=_("Navegar direita (protegido)"), gesture="kb:rightArrow")
    def script_safeRightArrow(self, gesture):
        """
        Na lista de conversas: redireciona para seta baixo (próxima conversa)
        para evitar entrar nos sub-elementos inline (botões de chamada, etc.).
        No histórico e outros contextos: passa normalmente.
        """
        try:
            if self._is_conv_list_item(api.getFocusObject()):
                import keyboardHandler
                keyboardHandler.KeyboardInputGesture.fromName("downArrow").send()
                return
        except Exception:
            pass
        self._arrow_came_from_msg = True
        gesture.send()

    # ── Modo de navegação ────────────────────────────────────────────────────────
    @script(description=_("Alternar modo de navegação"), gesture="kb:NVDA+space")
    def script_toggleBrowseMode(self, gesture):
        obj = api.getFocusObject()
        ti = getattr(obj, "treeInterceptor", None)
        if ti:
            ti.passThrough = not ti.passThrough
            state = _("Modo foco") if ti.passThrough else _("Modo de navegação")
            ui.message(state)
        else:
            gesture.send()

    # ── Inspetor ────────────────────────────────────────────────────────────────
    @script(description=_("Inspecionar elemento"), gesture="kb:NVDA+shift+i")
    def script_inspector(self, gesture):
        obj = api.getFocusObject()
        loc = obj.location
        loc_str = (
            f"E:{loc.left} T:{loc.top} L:{loc.width} A:{loc.height}"
            if loc else "sem posição")
        cls = getattr(obj, "IA2Attributes", {}).get("class", "")[:40]
        role = controlTypes.roleLabels.get(obj.role, str(obj.role))
        ui.message(f"Papel:{role} | {loc_str} | Nome:'{(obj.name or '')[:50]}' | Classe:{cls}")
