# -*- coding: UTF-8 -*-
"""
WhatsApp Unified — plugin global.
Registra o executável e painel de configurações.
"""

import re

import globalPluginHandler
import appModuleHandler
import addonHandler
import config
import gui
import wx
from gui.settingsDialogs import SettingsPanel, NVDASettingsDialog
import api
import controlTypes
import speech
import ui
import winUser
import time
from scriptHandler import script
from NVDAObjects.IAccessible import IAccessible
from NVDAObjects.IAccessible.ia2Web import Ia2Web

addonHandler.initTranslation()

CONFIG_SECTION = "whatsAppUnified"
SPEC = {
    "filterPhoneNumbers":   "boolean(default=True)",
    "filterChatList":       "boolean(default=False)",
    "filterMessageList":    "boolean(default=True)",
    "filterUsageHints":     "boolean(default=True)",
    "filterTalvez":         "boolean(default=True)",
    "autoFocusMode":        "boolean(default=True)",
    "disableFocusLock":     "boolean(default=False)",
    "scope":                "string(default='both')",
}

# Mesmas expressões usadas pelo módulo do aplicativo, para o WhatsApp Web não
# ficar sem os filtros (o README registrava "as opções aparecem mas não fazem
# nada no Web"). A frase real da dica em português começa com "Para acessar o
# menu" e não estava em nenhuma lista antes.
_HINT_RE = re.compile(
    r"(Para acessar o menu|Para acessar as opções|Para mais opções|"
    r"To access the menu|For more options|"
    r"Para acceder al menú|Para más opciones|"
    r"Pour accéder au menu|Pour plus|"
    r"Um weitere Optionen|Für weitere|"
    r"Per accedere al menù|Per altre|"
    r"Untuk membuka menu|Untuk opsi|"
    r"Untuk mengakses menu|Para lebih|"
    r"Daha fazla|Voor meer|"
    r"Для получения|Để biết|สำหรับ|その他|更多选项|अधिक|추가 옵션)",
    re.IGNORECASE,
)
_PHONE_RE = re.compile(r"\+\d[()\d\s-]{8,15}(?=[^\d]|$|\s)")

SCOPE_CHOICES = [
    ("desktop", _("Apenas aplicativo (Desktop)")),
    ("web",     _("Apenas WhatsApp Web (navegador)")),
    ("both",    _("Ambos")),
]


# ─── Navegação virtual do menu de contexto da mensagem (WhatsApp Web) ─────────
# Mesma técnica segura do Desktop (chooseNVDAObjectOverlayClasses, herdada do
# whatsAppEnhancer) — nunca reivindica tecla global, só rotula o objeto quando
# o papel bate (MENUITEM) E a página confirmada é WhatsApp Web de verdade (via
# URL). Contorna o bug documentado do NVDA (#7836) com botões que abrem menu:
# a primeira seta funciona, as seguintes escorregam sozinhas pro modo de
# navegação. Como Desktop e Web carregam a mesma página (WhatsApp Desktop
# embute o web.whatsapp.com dentro do WebView2 desde dez/2025), os papéis e
# nomes de classe encontrados num lado valem no outro.
class MessageMenuItemNav(Ia2Web):
    """Cada item de texto do menu de contexto da mensagem (Responder,
    Encaminhar, Apagar etc. — papel MENUITEM) ganha essa classe ao receber
    foco de verdade. Seta cima/baixo anda pro item irmão seguinte/anterior
    com setFocus real; Enter ativa. Como só existe pra objetos MENUITEM
    dentro do WhatsApp Web, nunca interfere em outro site."""

    def _siblings(self):
        try:
            parent = self.parent
            if not parent:
                return []
            items = []
            child = parent.firstChild
            while child:
                if getattr(child, "role", None) == controlTypes.Role.MENUITEM:
                    items.append(child)
                child = child.next
            return items
        except Exception:
            return []

    def script_menuNext(self, gesture):
        items = self._siblings()
        if not items:
            gesture.send()
            return
        try:
            idx = items.index(self)
        except ValueError:
            idx = -1
        if idx + 1 < len(items):
            items[idx + 1].setFocus()

    def script_menuPrev(self, gesture):
        items = self._siblings()
        if not items:
            gesture.send()
            return
        try:
            idx = items.index(self)
        except ValueError:
            idx = 0
        if idx - 1 >= 0:
            items[idx - 1].setFocus()

    def script_activate(self, gesture):
        try:
            self.doAction()
        except Exception:
            gesture.send()

    __gestures = {
        "kb:downArrow": "menuNext",
        "kb:upArrow": "menuPrev",
        "kb:enter": "activate",
    }


class WhatsAppUnifiedSettings(SettingsPanel):
    title = _("WhatsApp Unificado")

    def makeSettings(self, settingsSizer):
        helper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
        c = config.conf.get(CONFIG_SECTION, {})

        # Escopo
        scope_labels = [label for _, label in SCOPE_CHOICES]
        self.scope = helper.addLabeledControl(
            _("Aplicar para:"),
            wx.Choice,
            choices=scope_labels,
        )
        current_scope = c.get("scope", "both")
        scope_keys = [key for key, _ in SCOPE_CHOICES]
        idx = scope_keys.index(current_scope) if current_scope in scope_keys else 0
        self.scope.SetSelection(idx)

        self.filterPhoneNumbers = helper.addItem(wx.CheckBox(
            self, label=_("Filtrar números de telefone nas mensagens")))
        self.filterPhoneNumbers.SetValue(bool(c.get("filterMessageList", True)))

        self.filterChatList = helper.addItem(wx.CheckBox(
            self, label=_("Filtrar números de telefone na lista de conversas")))
        self.filterChatList.SetValue(bool(c.get("filterChatList", False)))

        self.filterUsageHints = helper.addItem(wx.CheckBox(
            self, label=_("Silenciar dicas de uso ('Para mais opções...')")))
        self.filterUsageHints.SetValue(bool(c.get("filterUsageHints", True)))

        self.filterTalvez = helper.addItem(wx.CheckBox(
            self, label=_("Remover 'Talvez' antes de nomes de contato")))
        self.filterTalvez.SetValue(bool(c.get("filterTalvez", True)))

        self.autoFocusMode = helper.addItem(wx.CheckBox(
            self, label=_("Manter modo foco automaticamente (recomendado)")))
        self.autoFocusMode.SetValue(bool(c.get("autoFocusMode", True)))

        self.disableFocusLock = helper.addItem(wx.CheckBox(
            self, label=_("Desativar completamente o modo foco automático "
                           "(não recomendado — só pra depuração)")))
        self.disableFocusLock.SetValue(bool(c.get("disableFocusLock", False)))

    def onSave(self):
        c = config.conf[CONFIG_SECTION]
        scope_keys = [key for key, _ in SCOPE_CHOICES]
        c["scope"]           = scope_keys[self.scope.GetSelection()]
        c["filterMessageList"] = self.filterPhoneNumbers.IsChecked()
        c["filterChatList"]    = self.filterChatList.IsChecked()
        c["filterUsageHints"]  = self.filterUsageHints.IsChecked()
        c["filterTalvez"]      = self.filterTalvez.IsChecked()
        c["autoFocusMode"]     = self.autoFocusMode.IsChecked()
        c["disableFocusLock"]  = self.disableFocusLock.IsChecked()
        config.conf.save()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

    scriptCategory = _("WhatsApp Unificado")

    def __init__(self):
        super().__init__()
        config.conf.spec[CONFIG_SECTION] = SPEC
        if CONFIG_SECTION not in config.conf:
            config.conf[CONFIG_SECTION] = {}
        # O NVDA guarda o nome do executável em minúsculas: "WhatsApp.Root.exe"
        # vira "whatsapp.root". Com maiúsculas o registro nunca casava.
        appModuleHandler.registerExecutableWithAppModule("whatsapp", "whatsapp_root")
        appModuleHandler.registerExecutableWithAppModule("whatsapp.root", "whatsapp_root")
        NVDASettingsDialog.categoryClasses.append(WhatsAppUnifiedSettings)

    def terminate(self):
        appModuleHandler.unregisterExecutable("whatsapp")
        appModuleHandler.unregisterExecutable("whatsapp.root")
        if WhatsAppUnifiedSettings in NVDASettingsDialog.categoryClasses:
            NVDASettingsDialog.categoryClasses.remove(WhatsAppUnifiedSettings)
        super().terminate()

    def chooseNVDAObjectOverlayClasses(self, obj, clsList):
        # Reconfirma a identidade da página NA HORA (não usa o cache
        # _in_whatsapp_web, que pode ainda não ter sido atualizado pro objeto
        # atual nesse ponto do ciclo do NVDA) — só rotula item de menu (papel
        # MENUITEM) quando a checagem de URL bate com WhatsApp Web de verdade.
        # MessageMenuItemNav herda de Ia2Web (família IAccessible/IA2) — só
        # pode ser aplicada quando o próprio Chrome expôs esse item via IA2.
        # Achado real (S342r/14-08): às vezes o Chrome expõe o mesmo menu via
        # UIA em vez de IA2 (classe tipo "ChromiumUIAMenuItemUIA" no clsList)
        # — misturar as duas famílias gera um objeto quebrado, sem atributos
        # básicos (event_objectID/IAccessibleChildID), travando o event pump
        # do NVDA repetidamente. Só aplica se já existir base IAccessible.
        try:
            if (obj.role == controlTypes.Role.MENUITEM
                    and any(issubclass(c, IAccessible) for c in clsList)
                    and self._check_whatsapp_web(obj)):
                clsList.insert(0, MessageMenuItemNav)
        except Exception:
            pass

    def _has_message_list_ancestor(self, obj):
        """Mesma convenção do Desktop: a linha de mensagem tem a classe
        'focusable-list-item' em algum ancestral próximo."""
        curr = obj
        for _ in range(7):
            try:
                cls = getattr(curr, "IA2Attributes", {}).get("class", "")
                if "focusable-list-item" in cls:
                    return True
                curr = curr.parent
                if curr is None:
                    return False
            except Exception:
                return False
        return False

    # ── WhatsApp Web — foco e live region sem delay ───────────────────────────

    _BROWSER_EXES = frozenset({
        "chrome", "msedge", "firefox", "opera", "brave", "vivaldi", "iexplore"
    })

    # Cache: estado WhatsApp Web e controle de throttle para live regions
    _in_whatsapp_web = False
    _last_lr_text    = ""
    _last_lr_time    = 0.0
    _LR_MIN_INTERVAL = 0.35  # segundos mínimos entre anúncios de live region

    def _check_whatsapp_web(self, obj):
        """Verifica se obj está num browser com WhatsApp Web aberto de verdade.
        Confere a URL real do documento (treeInterceptor.documentConstantIdentifier)
        quando disponível — mais preciso que título de janela, que bate por
        coincidência (qualquer página com 'whatsapp' no título ativaria as
        mudanças à toa). MAS a URL só conta como resposta positiva — se não
        bater (ou nem existir, algo comum pra elementos que usam UIA em vez
        de IA2, onde esse identificador às vezes não é uma URL de verdade),
        cai pro título como reserva, em vez de desistir ali. Foi a falta
        dessa reserva que quebrou o reforço de modo foco especificamente na
        lista de conversas/mensagens (12-13/08/2026)."""
        scope = config.conf.get(CONFIG_SECTION, {}).get("scope", "desktop")
        if scope == "desktop":
            return False
        try:
            appName = obj.appModule.appName.lower().replace(".exe", "")
            if appName not in self._BROWSER_EXES:
                return False
            ti = getattr(obj, "treeInterceptor", None)
            if ti:
                url = (getattr(ti, "documentConstantIdentifier", None)
                       or getattr(ti, "documentUrl", None))
                if url and "web.whatsapp.com" in str(url).lower():
                    return True
            hwnd = winUser.getForegroundWindow()
            title = winUser.getWindowText(hwnd).lower()
            return "whatsapp" in title
        except Exception:
            return False

    # ── Filtros do WhatsApp Web ───────────────────────────────────────────────
    # Antes existiam só no módulo do aplicativo; no navegador as opções
    # apareciam nas configurações e não faziam nada.

    def _looks_like_whatsapp_web(self, obj):
        """Checagem para o evento de criação de objeto: usa o cache do foco e,
        quando ele ainda não foi preenchido, confere o endereço do documento
        ou o título da janela em primeiro plano."""
        scope = config.conf.get(CONFIG_SECTION, {}).get("scope", "both")
        if scope == "desktop":
            return False
        if self._in_whatsapp_web:
            return True
        try:
            ti = getattr(obj, "treeInterceptor", None)
            url = (getattr(ti, "documentConstantIdentifier", None)
                   or getattr(ti, "documentUrl", None)) if ti else None
            if url and "web.whatsapp.com" in str(url).lower():
                return True
        except Exception:
            pass
        try:
            return "whatsapp" in winUser.getWindowText(
                winUser.getForegroundWindow()).lower()
        except Exception:
            return False

    def _list_kind(self, obj):
        """Diz se o objeto está na lista de conversas ou na de mensagens pelo
        rótulo acessível dela ('Lista de conversas', 'Mensagens' etc.).
        Devolve 'chat', 'message' ou None."""
        curr = obj
        for _ in range(10):
            try:
                name = (curr.name or "").lower()
            except Exception:
                name = ""
            if re.search(r"conversa|conversation|\bchats?\b", name):
                return "chat"
            if re.search(r"mensage|message", name):
                return "message"
            try:
                curr = curr.parent
            except Exception:
                return None
            if curr is None:
                return None
        return None

    def event_NVDAObject_init(self, obj):
        """Aplica no WhatsApp Web os mesmos filtros do aplicativo: dica de uso,
        'Talvez' e números de telefone."""
        try:
            app_name = obj.appModule.appName.lower().replace(".exe", "")
        except Exception:
            return
        if app_name not in self._BROWSER_EXES:
            return
        if not self._looks_like_whatsapp_web(obj):
            return
        try:
            name = obj.name
        except Exception:
            return
        if not name:
            return
        c = config.conf.get(CONFIG_SECTION, {})
        role = getattr(obj, "role", None)
        new = name

        # Dica de uso longa ("Para acessar o menu e encontrar mais opções...").
        if c.get("filterUsageHints", True):
            m = _HINT_RE.search(new)
            if m and (m.start() == 0 or role in (
                    86, 29, controlTypes.Role.UNKNOWN)):
                new = new[:m.start()]

        # "Talvez" antes do nome do contato (número não salvo na agenda).
        if c.get("filterTalvez", True):
            stripped = new.lstrip()
            if stripped.startswith("Talvez "):
                new = stripped[7:]

        # Números de telefone, separados por lista.
        if _PHONE_RE.search(new):
            kind = self._list_kind(obj)
            if ((kind == "chat" and c.get("filterChatList", False))
                    or (kind == "message"
                        and c.get("filterMessageList", True))):
                new = _PHONE_RE.sub("", new)

        if new != name:
            try:
                obj.name = re.sub(r"\s{2,}", " ", new).strip()
            except Exception:
                pass

    # Modo foco automático em duas velocidades, dependendo de ONDE o foco está:
    # - Andar ENTRE itens de lista (conversas OU mensagens, role 86/29/UNKNOWN
    #   — SECTION/TABLECELL) OU entre os botões inline de UMA mensagem
    #   (reagir, responder, encaminhar, "...", tocar áudio, link — qualquer
    #   BUTTON com ancestral 'focusable-list-item', mesma convenção que o
    #   Desktop já usa pra achar a linha de mensagem): tudo isso é tratado
    #   pelo próprio JavaScript do WhatsApp (mesma página nos dois lados —
    #   Desktop também carrega web.whatsapp.com), então precisa ficar SEMPRE
    #   em modo foco pra as setas chegarem cruas na página — reforça a cada
    #   troca de foco. O Desktop não precisa de código nenhum pra isso além
    #   de manter o modo foco ligado (nenhuma navegação própria) — é
    #   exatamente esse comportamento que o Web replica aqui.
    # - Item DENTRO de um submenu que abriu por cima (papel MENUITEM, sem
    #   ancestral de mensagem): só força modo foco ao ENTRAR no WhatsApp Web
    #   vindo de outro lugar, nunca de forma reativa depois disso — pra não
    #   brigar com o Escape nativo do NVDA nem com NVDA+Espaço enquanto o
    #   usuário explora (isso causava "Enter e depois Esc" pra abrir
    #   submenus, e travava Ctrl+setas). Esses itens já têm navegação própria
    #   segura via MessageMenuItemNav (ver classe acima).
    def event_gainFocus(self, obj, nextHandler):
        """Atualiza cache e força modo foco ao chegar no WhatsApp Web, ao
        andar entre itens de lista (conversas/mensagens) ou entre botões
        inline de uma mensagem."""
        nextHandler()
        was_in_web = self._in_whatsapp_web
        self._in_whatsapp_web = self._check_whatsapp_web(obj)
        if not self._in_whatsapp_web:
            return
        entering_fresh = not was_in_web
        obj_role = getattr(obj, "role", None)
        is_list_item = obj_role in (86, 29) or obj_role == controlTypes.Role.UNKNOWN
        is_inline_msg_button = (
            obj_role == controlTypes.Role.BUTTON
            and self._has_message_list_ancestor(obj)
        )
        if entering_fresh or is_list_item or is_inline_msg_button:
            c = config.conf.get(CONFIG_SECTION, {})
            if c.get("autoFocusMode", True) and not c.get("disableFocusLock", False):
                ti = getattr(obj, "treeInterceptor", None)
                if ti and hasattr(ti, "passThrough"):
                    try:
                        ti.passThrough = True
                    except Exception:
                        # Achado real (S342r/14-08): setar passThrough aqui
                        # dentro do próprio evento de foco às vezes esbarra
                        # num objeto de revisão ainda não pronto (NoneType
                        # sem makeTextInfo) e derruba o evento inteiro,
                        # cortando o resto do processamento daquele foco no
                        # meio. Como isso é reforçado a cada troca de foco
                        # (comentário acima), ignorar aqui e deixar a próxima
                        # troca de foco tentar de novo é seguro.
                        pass

    @script(description=_("Alternar modo de navegação (WhatsApp Web)"), gesture="kb:NVDA+space")
    def script_toggleBrowseModeWeb(self, gesture):
        """Alterna manualmente o modo de navegação/foco no WhatsApp Web.
        Fora do WhatsApp Web: replica o atalho padrão do NVDA."""
        if not self._in_whatsapp_web:
            gesture.send()
            return
        try:
            obj = api.getFocusObject()
            ti = getattr(obj, "treeInterceptor", None)
            if ti and hasattr(ti, "passThrough"):
                try:
                    import globalCommands
                    core_toggle = getattr(
                        globalCommands.commands, "script_toggleVirtualBufferPassThrough", None)
                except Exception:
                    core_toggle = None
                if core_toggle:
                    # Usa o comando nativo do NVDA (sincroniza cursor de
                    # revisão e anuncia o modo corretamente).
                    core_toggle(gesture)
                else:
                    ti.passThrough = not ti.passThrough
                    state = _("Modo foco") if ti.passThrough else _("Modo de navegação")
                    ui.message(state)
                return
        except Exception:
            pass
        gesture.send()

    @script(description=_("Inspecionar elemento (WhatsApp Web)"), gesture="kb:NVDA+shift+i")
    def script_inspectorWeb(self, gesture):
        """Fala papel, posição, nome, classe e estados do elemento focado —
        mesmo formato do inspetor do Desktop, pra comparar os dois lados."""
        if not self._in_whatsapp_web:
            gesture.send()
            return
        try:
            obj = api.getFocusObject()
            loc = obj.location
            loc_str = (
                f"E:{loc.left} T:{loc.top} L:{loc.width} A:{loc.height}"
                if loc else "sem posição")
            cls = getattr(obj, "IA2Attributes", {}).get("class", "")[:60]
            role = getattr(obj.role, "displayString", str(obj.role))
            states = ", ".join(
                getattr(s, "displayString", str(s))
                for s in getattr(obj, "states", set()))
            ui.message(
                f"Papel:{role} | {loc_str} | Nome:'{(obj.name or '')[:50]}' | "
                f"Classe:{cls} | Estados:{states}")
        except Exception:
            gesture.send()

    def event_liveRegionChange(self, obj, nextHandler):
        """Anuncia live regions do WhatsApp Web imediatamente, sem o delay polite.
        Throttling e deduplicação evitam saturar o NVDA com atualizações rápidas."""
        if not self._in_whatsapp_web:
            return nextHandler()
        text = (obj.name or obj.description or "").strip()
        if not text:
            return
        now = time.monotonic()
        # Descarta: mesmo texto repetido OU intervalo menor que o mínimo
        if text == self._last_lr_text and (now - self._last_lr_time) < self._LR_MIN_INTERVAL:
            return
        self._last_lr_text = text
        self._last_lr_time = now
        ui.message(text)
        # Não chama nextHandler: evita o anúncio duplicado com delay de 500ms
