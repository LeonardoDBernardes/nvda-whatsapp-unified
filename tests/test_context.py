"""Deteccao de contexto: so o endereco web.whatsapp.com decide; titulo nao conta."""

import pytest
from fakes import FakeApp, Node, Page, focus
from controlTypes import Role, State

from globalPlugins.whatsAppUnified import context


@pytest.mark.parametrize(
	"url,expected",
	[
		("https://web.whatsapp.com/", True),
		("https://web.whatsapp.com/send?phone=1", True),
		("web.whatsapp.com", True),
		("https://whatsapp.com/", False),  # site institucional
		("https://faq.whatsapp.com/", False),
		("https://www.whatsapp.com/download", False),
		("https://api.whatsapp.com/send?phone=1", False),
		("https://www.example.com/", False),
		("https://whatsapp.com.evil.example/", False),
		("https://evilwhatsapp.com/", False),
		("https://example.com/?next=web.whatsapp.com", False),
		("https://user@web.whatsapp.com:443/", True),
		("about:blank", None),
		("", None),
		(None, None),
		("uia:AutomationId-7", None),
		("12345", None),
	],
)
def test_url_is_whatsapp(url, expected):
	assert context.url_is_whatsapp(url) is expected


def test_web_whatsapp_page_is_web_context():
	page = Page()
	focus(page.composer)
	assert context.raw_context(page.msg_rows[0]) == "web"
	assert context.wa_context(page.composer) == "web"


def test_other_site_is_no_context_even_with_whatsapp_in_the_title():
	page = Page(url="https://www.example.com/", title="WhatsApp clone - Google Chrome")
	focus(page.composer)
	assert context.raw_context(page.msg_rows[0]) is None
	assert context.wa_context(page.composer) is None


def test_uia_identifier_never_falls_back_to_the_window_title():
	"""Sem endereco utilizavel NAO se adivinha pelo titulo (isso disparava varreduras)."""
	page = Page(url="uia:AutomationId-7", title="(3) WhatsApp - Microsoft Edge")
	focus(page.composer)
	assert context.raw_context(page.msg_rows[0]) is None
	assert context.wa_context(page.composer) is None


def test_institutional_and_faq_pages_are_no_context():
	for url in ("https://faq.whatsapp.com/", "https://www.whatsapp.com/", "https://whatsapp.com/"):
		page = Page(url=url)
		focus(page.composer)
		assert context.raw_context(page.msg_rows[0]) is None, url
		assert context.wa_context(page.composer) is None, url


def test_desktop_app_module_is_app_context():
	app = FakeApp("whatsapp.root", isWhatsAppUnified=True)
	obj = Node(Role.TABLEROW, "x", app=app)
	focus(obj)
	assert context.raw_context(obj) == "app"
	builtin = Node(Role.TABLEROW, "x", app=FakeApp("whatsapp.root"))
	focus(builtin)
	assert context.raw_context(builtin) == "app"


def test_unrelated_application_is_no_context():
	obj = Node(Role.TABLEROW, "x", app=FakeApp("notepad"))
	focus(obj)
	assert context.raw_context(obj) is None
	assert context.raw_context(Node(Role.TABLEROW, "x")) is None


def test_scope_is_respected():
	from globalPlugins.whatsAppUnified import settings
	import config

	page = Page()
	focus(page.composer)
	section = config.conf[settings.CONFIG_SECTION]
	section["scope"] = "desktop"
	assert context.wa_context(page.msg_rows[0]) is None
	section["scope"] = "web"
	assert context.wa_context(page.msg_rows[0]) == "web"
	app = Node(Role.TABLEROW, "x", app=FakeApp("whatsapp.root", isWhatsAppUnified=True))
	focus(app)
	section["scope"] = "web"
	assert context.wa_context(app) is None
	section["scope"] = "both"
	assert context.wa_context(app) == "app"


def test_verdict_is_per_document_not_global():
	whats = Page()
	other = Page(url="https://www.example.com/")
	focus(whats.composer)
	assert context.raw_context(whats.msg_rows[0]) == "web"
	assert context.raw_context(other.msg_rows[0]) is None  # outra janela/documento
	assert context.raw_context(whats.msg_rows[1]) == "web"
	focus(other.composer)
	assert context.raw_context(whats.msg_rows[0]) is None  # o foco saiu do WhatsApp
	assert context.raw_context(other.msg_rows[0]) is None


def test_context_follows_focus_events_and_is_none_before_any_event():
	whats = Page()
	other = Page(url="https://www.example.com/")
	assert context.active() is None
	focus(whats.composer, event=False)  # o NVDA moveu o foco, o evento ainda nao chegou
	assert context.active() is None and context.raw_context(whats.composer) is None
	focus(whats.composer)
	assert context.active() == "web" and context.wa_context() == "web"
	focus(other.composer)
	assert context.active() is None and context.wa_context() is None


def test_stale_context_is_ignored_when_the_nvda_focus_moved_on():
	"""Foco novo ainda sem evento: o contexto antigo nao vale para ele."""
	whats = Page()
	focus(whats.composer)
	assert context.wa_context() == "web"
	focus(whats.msg_rows[0], event=False)
	assert context.wa_context() is None and context.raw_context(whats.msg_rows[0]) is None


def test_is_web_document_checks_the_url_only():
	page = Page()
	assert context.is_web_document(page.doc) is True
	other = Page(url="https://www.example.com/", title="WhatsApp - Chrome")
	assert context.is_web_document(other.doc) is False
	no_url = Page(url=None, title="WhatsApp - Chrome")
	assert context.is_web_document(no_url.doc) is False
	faq = Page(url="https://faq.whatsapp.com/")
	assert context.is_web_document(faq.doc) is False
	not_browser = Page(app_name="notepad")
	assert context.is_web_document(not_browser.doc) is False


def test_title_or_unconfirmed_page_never_triggers_a_scan():
	"""Aba chamada 'WhatsApp' sem endereco confirmado: nenhuma caminhada pela arvore."""
	from globalPlugins.whatsAppUnified import overlays
	from fakes import apply_overlays

	page = Page(url="https://www.example.com/", title="WhatsApp - Google Chrome")
	row = page.msg_rows[0]
	touched = []
	original = context.classify_container
	context.classify_container = lambda container: touched.append(container) or original(container)
	try:
		apply_overlays(row, {"web"})
		apply_overlays(page.chat_rows[0], {"web"})
	finally:
		context.classify_container = original
	assert touched == []
	assert not isinstance(row, overlays.MessageRow)


def test_find_document_of_the_focus_uses_the_focus_ancestors_without_climbing(monkeypatch):
	import api

	page = Page()
	deep = page.msg_rows[0].lastChild
	api.setFocusObject(deep, ancestors=[page.doc, page.main, page.msg_list, page.msg_rows[0]])

	def boom(*args, **kwargs):
		raise AssertionError("subiu pelos pais do foco")

	monkeypatch.setattr(context, "ancestors", boom)
	assert context.find_document(deep) is page.doc


def test_find_document_of_other_objects_climbs_only_a_few_parents():
	page = Page()
	node = page.doc
	for _ in range(10):
		node = node.add(Node(Role.SECTION, "n"))
	assert context.find_document(node) is None  # fundo demais: nao varre a arvore toda
	assert context.find_document(page.msg_rows[0].lastChild) is page.doc


def test_there_is_no_per_window_verdict_two_tabs_in_one_window():
	"""Duas abas na MESMA janela: depois do WhatsApp, a outra aba nao herda o veredito."""
	from controlTypes import Role

	whats = Page()
	focus(whats.composer)
	assert context.wa_context() == "web"
	other_doc = Node(Role.DOCUMENT, "Outra aba", hwnd=whats.doc.windowHandle, app=whats.app)
	other_doc.IAccessibleObject = type(whats.doc.IAccessibleObject)("https://www.google.com/")
	other_field = other_doc.add(Node(Role.EDITABLETEXT, "Pesquisar"))
	focus(other_field)  # mesma janela (hwnd igual) do WhatsApp
	assert other_field.windowHandle == whats.composer.windowHandle
	assert context.raw_context() is None
	assert context.raw_context(other_field) is None
	assert context.raw_context(whats.msg_rows[0]) is None


def test_address_change_is_seen_at_the_next_focus_event():
	page = Page()
	focus(page.composer)
	assert context.raw_context(page.msg_rows[0]) == "web"
	page.doc.IAccessibleObject.url = "https://www.example.com/"
	focus(page.msg_rows[1])
	assert context.raw_context(page.msg_rows[1]) is None


def test_tree_interceptor_verdict_follows_the_document_address():
	from globalPlugins.whatsAppUnified.webmode import WhatsAppChromeVBuf

	page = Page()
	ti = WhatsAppChromeVBuf(page.doc)
	assert context.ti_verdict(ti) is True
	page.doc.IAccessibleObject.url = "https://faq.whatsapp.com/"
	assert context.ti_verdict(ti) is False
	page.doc.IAccessibleObject.url = "https://web.whatsapp.com/"
	assert context.ti_verdict(ti) is True


def test_row_kind_chat_message_other():
	page = Page()
	assert context.row_kind(page.chat_rows[0]) == "chat"
	assert context.row_kind(page.chat_rows[0].firstChild) == "chat"  # celula
	assert context.row_kind(page.msg_rows[0]) == "message"
	assert context.row_kind(page.call_button) is None
	assert context.row_kind(page.composer) is None


def test_row_without_focusable_pane_or_chat_list_is_not_classified():
	"""2.0.3: sem a lista de conversas e sem o painel focavel das mensagens, nao e linha do WhatsApp."""
	page = Page()
	page.msg_list.states.discard(State.FOCUSABLE)
	context.forget_kinds()
	assert context.row_kind(page.msg_rows[0]) is None


def test_message_row_is_known_by_its_focusable_pane_without_the_composer():
	"""2.0.3: o painel das mensagens (div focavel) basta; o campo de digitacao nao e procurado."""
	page = Page()
	page.main.remove(page.composer)
	context.forget_kinds()
	assert context.row_kind(page.msg_rows[0]) == "message"
