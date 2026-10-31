"""2.0.12: relato do Leo de 31/10/2026 no WhatsApp Web.

"Quando abro o menu e vou seta para cima ele passa para reacoes. Ate isso tudo bem,
mas fica fazendo o som do NVDA+Espaco." Causa (codigo do NVDA, ia2Web): a barra de
reacoes fica num DIALOGO da pagina e todo dialogo ganha a classe de documento, com um
buffer PROPRIO em modo de navegacao, fora do controle do add-on. O log da 2.0.11 mostra
``modo=navegacao`` na barra sem troca de modo no buffer do WhatsApp. Agora o dialogo que
embrulha um menu nao cria buffer.
"""

import config
import logHandler
import pytest
from controlTypes import Role, State
from fakes import Node, Page, apply_overlays, focus, inner_row
from NVDAObjects.IAccessible import chromium

from globalPlugins.whatsAppUnified import GlobalPlugin, diag, settings
from globalPlugins.whatsAppUnified.webmode import WhatsAppChromeVBuf, WhatsAppMenuDialog

THUMBS_UP = "\U0001F44D"
HEART = "❤️"


@pytest.fixture
def plugin():
	p = GlobalPlugin()
	yield p
	p.terminate()


class DialogNode(Node, chromium.Document):
	"""Dialogo da pagina: o NVDA (ia2Web) lhe da a classe de documento; o Chromium o marca so de leitura."""

	IAccessibleRole = 18  # oleacc.ROLE_SYSTEM_DIALOG

	def __init__(self, children=(), hwnd=100):
		super().__init__(Role.DIALOG, "", states={State.READONLY}, children=children, hwnd=hwnd)


def lines(action):
	start = diag.PREFIX + " "
	return [line for line in logHandler.log.lines if line.startswith(start) and line[len(start):].split(" ")[0] == action]


def deliver(plugin, obj):
	focus(obj)

	def next_handler():
		obj.reportFocus()

	plugin.event_gainFocus(obj, next_handler)


def whatsapp_page(plugin):
	"""WhatsApp Web com o foco numa mensagem (o contexto do Web ja confirmado)."""
	page = Page(chats=0, messages=0)
	page.msg_rows = [inner_row("Fulano: mensagem %d" % i) for i in range(2)]
	for row in page.msg_rows:
		page.msg_list.add(row)
	ti = WhatsAppChromeVBuf(page.doc)
	page.attach(ti)
	deliver(plugin, page.msg_rows[0]._children[0])
	return page, ti


def reaction_dialog(page, names=(THUMBS_UP, HEART)):
	"""Barra de reacoes como na pagina: DIALOG > POPUPMENU > TOGGLEBUTTON."""
	hwnd = page.doc.windowHandle
	reactions = [Node(Role.TOGGLEBUTTON, n, states={State.FOCUSABLE}, hwnd=hwnd) for n in names]
	bar = Node(Role.POPUPMENU, "", children=reactions, hwnd=hwnd)
	dialog = DialogNode(children=[bar], hwnd=hwnd)
	page.doc.add(dialog)  # o dialogo fica dentro da pagina (portal no fim do documento)
	return dialog, bar, reactions


def test_the_reaction_dialog_creates_no_buffer_of_its_own(plugin):
	page, ti = whatsapp_page(plugin)
	dialog, bar, reactions = reaction_dialog(page)
	assert dialog.shouldCreateTreeInterceptor is True  # sem o add-on: buffer proprio (o som)
	apply_overlays(dialog, {"web"})
	assert isinstance(dialog, WhatsAppMenuDialog)
	assert dialog.shouldCreateTreeInterceptor is False
	assert lines("dialogo-sem-buffer")


def test_other_dialogs_keep_their_own_buffer(plugin):
	page, ti = whatsapp_page(plugin)
	hwnd = page.doc.windowHandle
	dialog = DialogNode(children=[Node(Role.BUTTON, "Cancelar", hwnd=hwnd), Node(Role.BUTTON, "Apagar", hwnd=hwnd)], hwnd=hwnd)
	page.doc.add(dialog)
	apply_overlays(dialog, {"web"})
	assert isinstance(dialog, WhatsAppMenuDialog)
	assert dialog.shouldCreateTreeInterceptor is True  # nativo


def test_without_the_focus_mode_option_the_dialog_is_native(plugin):
	page, ti = whatsapp_page(plugin)
	dialog, bar, reactions = reaction_dialog(page)
	apply_overlays(dialog, {"web"})
	config.conf[settings.CONFIG_SECTION]["autoFocusMode"] = False
	assert dialog.shouldCreateTreeInterceptor is True


def test_dialogs_of_other_sites_are_untouched(plugin):
	page = Page(url="https://www.example.com/")
	deliver(plugin, page.composer)
	dialog = DialogNode(children=[Node(Role.POPUPMENU, "", hwnd=page.doc.windowHandle)], hwnd=page.doc.windowHandle)
	page.doc.add(dialog)
	apply_overlays(dialog, {"web"})
	assert not isinstance(dialog, WhatsAppMenuDialog)
	assert dialog.shouldCreateTreeInterceptor is True


def test_the_web_document_still_gets_the_whatsapp_buffer(plugin):
	page, ti = whatsapp_page(plugin)
	doc = Page().doc
	apply_overlays(doc, {"web"})
	assert not isinstance(doc, WhatsAppMenuDialog)
	assert doc.treeInterceptorClass is WhatsAppChromeVBuf


def test_the_reaction_name_goes_to_the_log_as_codes_only(plugin):
	page, ti = whatsapp_page(plugin)
	dialog, bar, reactions = reaction_dialog(page)
	deliver(plugin, reactions[0])
	found = lines("reacao")
	assert found and "nome=U+1F44D" in found[-1]
	assert "papel=TOGGLEBUTTON" in found[-1]
	entered = lines("menu-entrou")
	assert entered and "buffer=" in entered[-1]


def test_names_with_letters_never_go_to_the_log():
	assert diag.symbols_of("Fulano") == "texto(6)"
	assert diag.symbols_of(HEART) == "U+2764 U+FE0F"
	assert diag.symbols_of("") == "vazio"
	assert diag.symbols_of(None) == "vazio"
