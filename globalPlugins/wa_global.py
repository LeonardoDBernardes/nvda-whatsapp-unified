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
import weakref
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
# Endereço de site de verdade (ex.: web.whatsapp.com). Serve para separar
# "o buffer aponta outro site" de "o buffer não tem endereço utilizável" —
# no segundo caso o título da janela ainda vale como reserva.
_SITE_RE = re.compile(r"^(?:[a-z0-9-]+\.)+[a-z]{2,}$", re.IGNORECASE)

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

    # ── WhatsApp Web — foco e live region sem delay ───────────────────────────

    _BROWSER_EXES = frozenset({
        "chrome", "msedge", "firefox", "opera", "brave", "vivaldi", "iexplore"
    })

    # Cache: estado WhatsApp Web e controle de throttle para live regions
    _in_whatsapp_web = False
    _last_lr_text    = ""
    _last_lr_time    = 0.0
    _LR_MIN_INTERVAL = 0.35  # segundos mínimos entre anúncios de live region

    # TreeInterceptor cujo modo foco já foi ajustado por este plugin (referência
    # fraca: o NVDA descarta o TI ao fechar/recarregar a página). Serve para
    # ajustar UMA vez por documento, em vez de brigar a cada troca de foco.
    _focus_mode_ti = None

    def _document_site(self, ti):
        """Devolve o domínio do documento do buffer (ex.: 'web.whatsapp.com'),
        ou None quando o identificador não é um endereço utilizável. Não dá
        para exigir sempre uma URL: em elementos UIA o identificador do buffer
        às vezes é outra coisa, e era aí que a checagem por título era a única
        saída (regressão da lista de conversas, 12-13/08/2026)."""
        if ti is None:
            return None
        try:
            url = (getattr(ti, "documentConstantIdentifier", None)
                   or getattr(ti, "documentUrl", None))
            if not url:
                return None
            site = str(url).strip().lower()
            if "://" in site:
                site = site.split("://", 1)[1]
            site = site.split("/", 1)[0].split("?", 1)[0]
            if site.count(":") == 1:  # endereço com porta
                site = site.split(":", 1)[0]
            if not _SITE_RE.match(site):
                return None
            return site
        except Exception:
            return None

    def _check_whatsapp_web(self, obj):
        """Verifica se obj está num browser com WhatsApp Web aberto de verdade.
        Confere o endereço do documento do buffer quando ele é um endereço de
        verdade — mais preciso que o título da janela. Se o endereço aponta
        OUTRO site, a resposta é não (senão uma pesquisa no Google com
        'whatsapp' no título ativaria o modo foco naquela página). Só quando
        o buffer não tem endereço utilizável é que o título serve de reserva,
        que é o caso dos elementos UIA que quebraram a lista de conversas em
        12-13/08/2026."""
        scope = config.conf.get(CONFIG_SECTION, {}).get("scope", "desktop")
        if scope == "desktop":
            return False
        try:
            appName = obj.appModule.appName.lower().replace(".exe", "")
            if appName not in self._BROWSER_EXES:
                return False
            site = self._document_site(getattr(obj, "treeInterceptor", None))
            if site is not None:
                return site == "whatsapp.com" or site.endswith(".whatsapp.com")
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
        site = self._document_site(getattr(obj, "treeInterceptor", None))
        if site is not None:
            return site == "whatsapp.com" or site.endswith(".whatsapp.com")
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

    # Modo foco no WhatsApp Web: ajustado UMA vez por documento, ANTES de o
    # NVDA processar o foco.
    #
    # Por que assim (achado S512, 22/10/2026, relato do Leo: "fica dando o
    # barulho do NVDA como se eu estivesse usando insert+espaço"): antes este
    # evento chamava nextHandler() primeiro e só depois forçava
    # ti.passThrough = True a cada troca de foco. Nesse meio-tempo o NVDA já
    # tinha decidido o modo pelo item focado e anunciava a troca com o som de
    # modo foco/navegação; a força posterior deixava o estado "sujo" e o som
    # voltava na troca seguinte — um bipe a cada item, junto com o texto do
    # modo de navegação (a lentidão relatada). Ajustando antes do
    # nextHandler, o NVDA já calcula o foco no modo certo e o anúncio não se
    # repete. Não se mexe mais no TI depois disso: se o usuário puser modo de
    # navegação com NVDA+Espaço, a escolha dele vale até recarregar a página.
    #
    # _disableAutoPassThrough é atributo PRIVADO de propósito: o setter
    # público chama _focusLastFocusableObject() e puxaria o foco do usuário.
    def event_gainFocus(self, obj, nextHandler):
        """Mantém o cache do WhatsApp Web e, ao entrar num documento dele,
        deixa o modo foco ligado uma única vez — antes do NVDA tratar o foco."""
        was_in_web = self._in_whatsapp_web
        self._in_whatsapp_web = self._check_whatsapp_web(obj)
        if not self._in_whatsapp_web:
            if was_in_web:
                # Saiu do WhatsApp Web: esquece o documento anterior.
                self._focus_mode_ti = None
            return nextHandler()

        c = config.conf.get(CONFIG_SECTION, {})
        if c.get("autoFocusMode", True) and not c.get("disableFocusLock", False):
            try:
                ti = getattr(obj, "treeInterceptor", None)
                tracked = self._focus_mode_ti
                if (
                    ti is not None
                    and hasattr(ti, "passThrough")
                    and (tracked is None or tracked() is not ti)
                ):
                    ti.passThrough = True
                    ti._disableAutoPassThrough = True
                    # Marca só DEPOIS de dar certo. Achado real (S342r/14-08):
                    # mexer no TI aqui às vezes esbarra num objeto de revisão
                    # ainda não pronto e o ajuste falha; se o cache fosse
                    # marcado antes, aquele documento nunca receberia o modo
                    # foco e o bipe voltaria até recarregar a página.
                    self._focus_mode_ti = weakref.ref(ti)
            except Exception:
                # A próxima troca de foco tenta de novo, e o nextHandler é
                # chamado de todo jeito.
                pass
        nextHandler()

    # Nota (S512, 23/10/2026): NÃO há mais script NVDA+Espaço neste plugin
    # global. Ele existia só para alternar o modo no WhatsApp Web, mas um
    # script de plugin global tem prioridade sobre o comando do próprio NVDA
    # (scriptHandler._yieldObjectsForFindScript: plugins antes de
    # globalCommands) — e o "gesture.send()" do fallback engolia o
    # NVDA+Espaço em TODO o sistema, mandando Insert+Espaço ao programa em vez
    # de alternar browse/foco. Sem o script, quem responde é o comando nativo,
    # que já funciona no WhatsApp Web e em qualquer página.

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
