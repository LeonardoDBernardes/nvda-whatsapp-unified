"""Isolamento: fora do WhatsApp (e fora do WhatsApp Web confirmado) o add-on nao faz NADA.

Relato do Leo com a 2.0.0: "ele esta influenciando outras janelas". Aqui se simulam
sequencias de foco em outros programas e se afirma, para cada gancho global, que nada
muda: nenhuma sobreposicao, nenhum adiamento de fala, nenhuma fala alterada, nenhum
script devolvido pelo getScript, nenhuma escrita em ``reportPassThrough.last``, nenhuma
linha de diagnostico e nenhuma chamada ao navegador (COM dos objetos falsos).

A unica leitura permitida num navegador e a do ENDERECO do documento em foco (uma por
evento de foco): ``accValue``. Nenhuma caminhada por pai/filhos/vizinhos.
"""

import api
import browseMode
import core
import inputCore
import logHandler
import pytest
import speech
from controlTypes import OutputReason, Role
from fakes import ComLog, FakeApp, Gesture, Node, Page, apply_overlays, chat_row, message_row
from NVDAObjects.IAccessible.chromium import ChromeVBuf

from globalPlugins.whatsAppUnified import GlobalPlugin, context, diag, filters, overlays, recovery, webmode
from globalPlugins.whatsAppUnified.webmode import WhatsAppChromeVBuf

class Boom(BaseException):
	"""Nao herda de Exception: os try/except do add-on nao conseguem engoli-la."""


OUR_KEYS = ("alt+1", "alt+2", "alt+d", "shift+alt+c", "control+shift+e", "nvda+shift+h")
MESSAGE_KEYS = ("enter", "alt+p", "control+s", "shift+enter", "control+shift+enter", "control+r", "alt+enter", "alt+c", "control+c")

# So a leitura do endereco do documento em foco (1 por evento de foco) e permitida.
URL_READ = {"accValue", "IAccessibleObject"}


@pytest.fixture
def plugin():
	p = GlobalPlugin()
	yield p
	p.terminate()


def deliver(plugin, obj, apps=("web", "app")):
	"""Um foco COMPLETO como o NVDA o entrega: cria o objeto, move o foco, dispara o evento.

	Devolve (classes escolhidas, chamadas ao navegador, vezes que o nextHandler rodou).
	"""
	ComLog.start()
	chosen = []
	for ctx in apps:
		chosen.extend(apply_overlays(obj, {ctx}))
	api.setFocusObject(obj)  # a troca de foco do NVDA (nao e o add-on)
	delivered = []
	ComLog.stop()
	ComLog.start()
	plugin.event_gainFocus(obj, lambda: delivered.append(True))
	calls = ComLog.stop()
	return chosen, calls, delivered


def assert_nothing_done(plugin, obj, chosen, calls, delivered, allow_url_read=False):
	"""A lista de afirmacoes de isolamento (item 6)."""
	assert chosen == [], "sobreposicao aplicada fora do WhatsApp"
	assert delivered == [True], "o evento de foco nao seguiu intacto"
	assert core.pending == [], "adiamento de fala agendado"
	assert "reportFocus" not in vars(obj), "reportFocus foi trocado"
	assert context.active() is None and context.wa_context() is None and context.raw_context(obj) is None
	allowed = URL_READ if allow_url_read else set()
	assert set(calls) <= allowed, calls
	assert calls.count("accValue") <= 1, calls
	# fala
	for text in ("+55 11 91234-5678: oi", "Talvez Maria", "Para mais opções, pressione a seta para a direita."):
		sequence = [text, "outro"]
		assert filters.on_speech_sequence(sequence) is sequence
	# teclas
	for key in OUR_KEYS + MESSAGE_KEYS:
		assert plugin.getScript(Gesture(key)) is None, key
	for handler in inputCore.decide_handleRawKey.handlers:
		assert handler(vkCode=0x09, pressed=True) is True
	assert recovery._State.last_key == 0 and recovery._State.last_key_at == 0.0
	# modo foco e diagnostico
	assert browseMode.reportPassThrough.writes == []
	assert [line for line in logHandler.log.lines if line.startswith(diag.PREFIX)] == []
	assert speech.spoken == []


def other_program(name, role=Role.EDITABLETEXT, title="x"):
	return Node(role, title, app=FakeApp(name), hwnd=next_hwnd())


_hwnd = [5000]


def next_hwnd():
	_hwnd[0] += 1
	return _hwnd[0]


@pytest.mark.parametrize("program", ["notepad", "explorer", "windowsterminal", "olk", "msedgewebview2", "code", "outlook"])
def test_other_programs_are_untouched(plugin, program):
	"""Bloco de Notas, Explorador, Terminal, Outlook (WebView2)...: nada."""
	for role in (Role.EDITABLETEXT, Role.TABLEROW, Role.TABLECELL, Role.LIST, Role.BUTTON):
		obj = other_program(program, role)
		chosen, calls, delivered = deliver(plugin, obj)
		assert_nothing_done(plugin, obj, chosen, calls, delivered)
		assert calls == [], "chamada ao navegador/COM em programa que nao e navegador"


def test_row_shaped_objects_in_other_programs_are_never_classified(plugin, monkeypatch):
	"""Uma lista com linhas no Explorador nao pode disparar classificacao nem varredura."""
	def boom(*args, **kwargs):
		raise Boom("o add-on mexeu em objeto de outro programa")

	for name in ("classify_container", "row_kind", "web_overlay_allowed", "find_document", "find_composer"):
		monkeypatch.setattr(context if hasattr(context, name) else overlays, name, boom, raising=False)
	monkeypatch.setattr(overlays, "row_kind", boom)
	monkeypatch.setattr(overlays, "web_overlay_allowed", boom)
	list_ = Node(Role.TABLE, "Arquivos", app=FakeApp("explorer"), hwnd=next_hwnd())
	row = list_.add(chat_row("a.txt"))
	row2 = list_.add(message_row("b.txt"))
	for obj in (list_, row, row2, row.firstChild):
		chosen, calls, delivered = deliver(plugin, obj)
		assert_nothing_done(plugin, obj, chosen, calls, delivered)


def test_chrome_on_google_with_and_without_a_buffer(plugin):
	for with_buffer in (False, True):
		page = Page(url="https://www.google.com/search?q=web.whatsapp.com")
		if with_buffer:
			page.attach(ChromeVBuf(page.doc))
		for obj in (page.composer, page.msg_rows[0], page.chat_rows[0], page.chat_rows[0].firstChild, page.call_button):
			chosen, calls, delivered = deliver(plugin, obj)
			assert_nothing_done(plugin, obj, chosen, calls, delivered, allow_url_read=True)


def test_edge_on_google_is_untouched(plugin):
	page = Page(url="https://www.google.com/", app_name="msedge")
	for obj in (page.composer, page.msg_rows[0]):
		chosen, calls, delivered = deliver(plugin, obj)
		assert_nothing_done(plugin, obj, chosen, calls, delivered, allow_url_read=True)


def test_chrome_address_bar_and_tabs_cost_nothing(plugin):
	"""A interface do navegador (sem documento): nem uma chamada, nem uma leitura de endereco."""
	chrome = FakeApp("chrome")
	for title in ("Barra de endereço e de pesquisa", "Nova guia", "Menu do Chrome"):
		obj = Node(Role.EDITABLETEXT, title, app=chrome, hwnd=next_hwnd())
		chosen, calls, delivered = deliver(plugin, obj)
		assert_nothing_done(plugin, obj, chosen, calls, delivered)
		assert calls == [], calls


def test_unconfirmed_address_means_nothing(plugin):
	for url in (None, "about:blank", "uia:AutomationId-7", "https://faq.whatsapp.com/", "https://www.whatsapp.com/"):
		page = Page(url=url, title="WhatsApp - Google Chrome")
		for obj in (page.composer, page.msg_rows[0]):
			chosen, calls, delivered = deliver(plugin, obj)
			assert_nothing_done(plugin, obj, chosen, calls, delivered, allow_url_read=True)


# ─── outra aba logo depois do WhatsApp Web ───────────────────────────────────

def enter_whatsapp(plugin, last_before=False):
	whats = Page()
	ti = WhatsAppChromeVBuf(whats.doc)
	whats.attach(ti)
	whats.overlay_all()  # (confirma o contexto no foco do campo)
	browseMode.reportPassThrough._last = last_before
	browseMode.reportPassThrough.writes.clear()
	api.setFocusObject(whats.msg_rows[0])
	plugin.event_gainFocus(whats.msg_rows[0], lambda: None)
	ti.event_treeInterceptor_gainFocus()
	ti.event_gainFocus(whats.msg_rows[0], lambda: None)
	assert context.active() == "web" and ti.passThrough is True
	return whats, ti


def test_other_tab_right_after_whatsapp_web_gets_nothing(plugin):
	"""Mesma janela do Chrome (as abas dividem o hwnd): a outra aba NAO herda nada."""
	whats, ti = enter_whatsapp(plugin, last_before=False)
	other_doc = Node(Role.DOCUMENT, "Google", hwnd=whats.doc.windowHandle, app=whats.app)
	other_doc.IAccessibleObject = type(whats.doc.IAccessibleObject)("https://www.google.com/")
	field = other_doc.add(Node(Role.EDITABLETEXT, "Pesquisar"))
	row_like = other_doc.add(message_row("Resultado"))
	other_ti = ChromeVBuf(other_doc)
	for node in (other_doc, field, row_like):
		node.treeInterceptor = other_ti
	for child in row_like._children:
		child.treeInterceptor = other_ti
	assert field.windowHandle == whats.composer.windowHandle  # a mesma janela
	browseMode.reportPassThrough.writes.clear()
	logHandler.log.lines.clear()
	for obj in (field, row_like):
		chosen, calls, delivered = deliver(plugin, obj)
		assert chosen == [] and delivered == [True] and core.pending == []
		assert "reportFocus" not in vars(obj)
		assert set(calls) <= URL_READ and calls.count("accValue") <= 1
		assert context.active() is None
		sequence = ["Talvez Maria", "+55 11 91234-5678: oi"]
		assert filters.on_speech_sequence(sequence) is sequence
		for key in OUR_KEYS + MESSAGE_KEYS:
			assert plugin.getScript(Gesture(key)) is None, key
		assert not isinstance(obj, overlays.MessageRow)
	# a unica escrita fora do WhatsApp: DEVOLVE o ultimo modo de antes de entrar (uma vez)
	assert browseMode.reportPassThrough.writes == [False]
	assert browseMode.reportPassThrough.last is False


def test_leaving_whatsapp_for_a_browse_mode_tab_is_as_native(plugin):
	"""Sem o add-on: aba de navegacao -> aba de navegacao nao toca nada. Com ele, igual."""
	whats, ti = enter_whatsapp(plugin, last_before=False)
	other = Page(url="https://www.example.com/")
	other_ti = ChromeVBuf(other.doc)
	other.attach(other_ti)
	api.setFocusObject(other.msg_rows[0])
	plugin.event_gainFocus(other.msg_rows[0], lambda: None)
	browseMode.sounds.clear()
	other_ti.event_treeInterceptor_gainFocus()
	other_ti.event_gainFocus(other.msg_rows[0], lambda: None)
	assert browseMode.sounds == []  # o ".last" voltou a ser o de antes (navegacao)


def test_no_write_to_last_when_whatsapp_was_never_entered(plugin):
	other = Page(url="https://www.example.com/")
	ti = ChromeVBuf(other.doc)
	other.attach(ti)
	for obj in (other.msg_rows[0], other.composer, other.msg_rows[1]):
		deliver(plugin, obj)
		ti.event_gainFocus(obj, lambda: None)
	assert browseMode.reportPassThrough.writes == []


def test_pinned_buffer_writes_only_while_it_is_the_focused_buffer(plugin):
	"""Um buffer do WhatsApp em segundo plano nao mexe no .last do documento da frente."""
	whats = Page()
	ti = WhatsAppChromeVBuf(whats.doc)
	whats.attach(ti)
	other = Page(url="https://www.example.com/")
	other_ti = ChromeVBuf(other.doc)
	other.attach(other_ti)
	api.setFocusObject(other.msg_rows[0])  # a frente e a outra aba
	browseMode.reportPassThrough.writes.clear()
	ti.shouldPassThrough(whats.composer, OutputReason.FOCUS)
	ti._wa_sync_last()
	assert browseMode.reportPassThrough.writes == []


# ─── provas por gancho global ────────────────────────────────────────────────

def test_hook_filter_speech_sequence_exits_on_the_first_line(monkeypatch):
	monkeypatch.setattr(filters.api, "getFocusObject", lambda: (_ for _ in ()).throw(Boom("api no filtro")))
	sequence = ["Talvez Maria"]
	assert filters.on_speech_sequence(sequence) is sequence


def test_hook_raw_key_exits_on_the_first_line():
	assert recovery.on_raw_key(vkCode=0x1B, pressed=True) is True
	assert recovery._State.last_key == 0


def test_hook_get_script_exits_without_asking_anyone(plugin, monkeypatch):
	import globalPluginHandler

	monkeypatch.setattr(globalPluginHandler.GlobalPlugin, "getScript", lambda self, g: (_ for _ in ()).throw(Boom("super")))
	assert plugin.getScript(Gesture("alt+1")) is None


def test_hook_choose_overlay_classes_exits_for_other_programs(plugin, monkeypatch):
	for name in ("row_kind", "web_overlay_allowed", "is_web_document"):
		monkeypatch.setattr(overlays, name, lambda *a, **k: (_ for _ in ()).throw(Boom("mexeu")))
	cls_list = []
	plugin.chooseNVDAObjectOverlayClasses(other_program("notepad", Role.TABLEROW), cls_list)
	assert cls_list == []
	# o modulo do aplicativo do WhatsApp tambem sai para objeto de outro programa
	overlays.choose_overlay_classes(other_program("notepad", Role.TABLEROW), cls_list, {"app"})
	assert cls_list == []


def test_hook_event_gain_focus_in_another_program_only_reads_the_program_name(plugin):
	obj = other_program("notepad")
	api.setFocusObject(obj)
	ComLog.start()
	delivered = []
	plugin.event_gainFocus(obj, lambda: delivered.append(1))
	assert ComLog.stop() == [] and delivered == [1]


# ─── a entrada no WhatsApp continua funcionando ──────────────────────────────

def test_whatsapp_web_still_works_after_the_isolation(plugin):
	whats, ti = enter_whatsapp(plugin)
	assert context.wa_context() == "web"
	assert plugin.getScript(Gesture("alt+d")) is not None
	row = whats.msg_rows[1]
	chosen = apply_overlays(row, {"web"})
	assert chosen == [overlays.MessageRow]


def test_first_focused_row_on_entry_gets_its_overlay(plugin):
	"""O objeto de foco da entrada nasce antes do contexto: o evento de foco o atualiza."""
	whats = Page()
	row = whats.msg_rows[0]
	assert apply_overlays(row, {"web"}) == []  # contexto ainda nao existe: sem sobreposicao
	api.setFocusObject(row)
	plugin.event_gainFocus(row, lambda: None)
	assert isinstance(row, overlays.MessageRow)
	assert row.getScript(Gesture("enter")) is not None


def test_first_focused_chat_row_on_entry_gets_its_overlay(plugin):
	whats = Page()
	row = whats.chat_rows[1]
	api.setFocusObject(row)
	plugin.event_gainFocus(row, lambda: None)
	assert isinstance(row, overlays.ChatListRow) and row.wa_kind == "chat"


def test_entry_upgrade_never_happens_in_other_sites_or_programs(plugin):
	other = Page(url="https://www.example.com/")
	row = other.msg_rows[0]
	api.setFocusObject(row)
	plugin.event_gainFocus(row, lambda: None)
	assert not isinstance(row, overlays.MessageRow) and getattr(row, "wa_kind", None) is None


# ─── buffer: nunca fixa por suposicao ────────────────────────────────────────

def test_document_overlay_rechecks_the_address_when_choosing_the_buffer():
	"""O mesmo objeto de documento navegou para o Google depois de a sobreposicao ser escolhida."""
	page = Page()
	api.setFocusObject(page.composer)
	apply_overlays(page.doc, {"web"})
	assert isinstance(page.doc, webmode.WhatsAppWebDocument)
	assert page.doc.treeInterceptorClass is WhatsAppChromeVBuf
	page.doc.IAccessibleObject.url = "https://www.google.com/"
	assert page.doc.treeInterceptorClass is ChromeVBuf


def test_buffer_of_a_non_whatsapp_address_is_born_unpinned():
	other = Page(url="https://www.google.com/")
	ti = WhatsAppChromeVBuf(other.doc)
	other.attach(ti)
	api.setFocusObject(other.composer)
	assert ti.passThrough is False and ti.disableAutoPassThrough is False
	ti.event_treeInterceptor_gainFocus()
	ti.event_gainFocus(other.composer, lambda: None)
	ti.shouldPassThrough(other.msg_rows[0], OutputReason.FOCUS)
	assert browseMode.reportPassThrough.writes == []


def test_buffer_without_any_readable_address_is_not_pinned():
	page = Page(url=None)
	ti = WhatsAppChromeVBuf(page.doc)
	assert ti.passThrough is False


def test_last_mode_is_given_back_only_if_the_addon_had_pinned(plugin):
	whats, ti = enter_whatsapp(plugin, last_before=True)  # vinha de uma aba em modo foco
	other = Page(url="https://www.example.com/")
	api.setFocusObject(other.composer)
	browseMode.reportPassThrough.writes.clear()
	plugin.event_gainFocus(other.composer, lambda: None)
	assert browseMode.reportPassThrough.writes == [True]
	plugin.event_gainFocus(other.composer, lambda: None)  # nao repete
	assert browseMode.reportPassThrough.writes == [True]
