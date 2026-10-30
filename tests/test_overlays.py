"""Quais classes de sobreposicao cada objeto recebe."""

from controlTypes import Role
from fakes import FakeApp, Node, Page, apply_overlays

from globalPlugins.whatsAppUnified import overlays
from globalPlugins.whatsAppUnified.webmode import WhatsAppWebDocument


def kinds(page):
	return (
		[getattr(r, "wa_kind", None) for r in page.chat_rows],
		[getattr(r, "wa_kind", None) for r in page.msg_rows],
	)


def test_chat_rows_and_message_rows_get_their_overlays():
	page = Page().overlay_all()
	assert all(isinstance(r, overlays.ChatListRow) for r in page.chat_rows)
	assert all(isinstance(r, overlays.MessageRow) for r in page.msg_rows)
	assert kinds(page) == (["chat"] * 3, ["message"] * 3)


def test_chat_cell_gets_the_chat_overlay_and_no_scripts():
	page = Page()
	cell = page.chat_rows[0].firstChild
	apply_overlays(cell, {"web"})
	assert isinstance(cell, overlays.ChatListRow)
	assert not isinstance(cell, overlays.MessageRow)


def test_other_objects_get_nothing():
	page = Page()
	for obj in (page.call_button, page.composer, page.msg_list, page.chat_list):
		assert apply_overlays(obj, {"web"}) == []


def test_row_in_other_site_gets_nothing():
	page = Page(url="https://www.example.com/")
	assert apply_overlays(page.msg_rows[0], {"web"}) == []
	assert apply_overlays(page.chat_rows[0], {"web"}) == []


def test_row_without_composer_is_not_a_message_row():
	page = Page()
	page.main.remove(page.composer)
	assert apply_overlays(page.msg_rows[0], {"web"}) == []


def test_web_context_not_requested_gives_nothing():
	page = Page()
	assert apply_overlays(page.msg_rows[0], {"app"}) == []
	assert apply_overlays(page.msg_rows[0], set()) == []


def test_scope_desktop_blocks_web_overlays():
	import config
	from globalPlugins.whatsAppUnified import settings

	config.conf[settings.CONFIG_SECTION]["scope"] = "desktop"
	page = Page()
	assert apply_overlays(page.msg_rows[0], {"web"}) == []
	assert apply_overlays(page.doc, {"web"}) == [overlays.chromium.Document]


def test_document_gets_the_pinned_buffer_overlay_only_for_whatsapp():
	assert isinstance(Page().doc, WhatsAppWebDocument) is False
	page = Page()
	apply_overlays(page.doc, {"web"})
	assert isinstance(page.doc, WhatsAppWebDocument)
	other = Page(url="https://www.example.com/")
	apply_overlays(other.doc, {"web"})
	assert not isinstance(other.doc, WhatsAppWebDocument)


def test_app_side_host_pane_and_rows():
	app = FakeApp("whatsapp.root", isWhatsAppUnified=True)
	pane = Node(Role.PANE, "", app=app)
	pane.windowClassName = overlays.HOST_PANE_CLASS
	assert apply_overlays(pane, {"app"}) == [overlays.HostPane]
	assert apply_overlays(pane, {"web"}) == []


def test_selection_popup_overlay():
	import oleacc

	page = Page()
	popup = Node(Role.POPUPMENU, "")
	popup.IAccessibleRole = oleacc.ROLE_SYSTEM_MENUPOPUP
	popup._app = page.app
	page.main.add(popup)
	assert apply_overlays(popup, {"web"}) == [overlays.SelectionPopup]


def test_selection_popup_does_not_steal_focus_from_the_text_field():
	from fakes import focus
	import oleacc

	page = Page()
	popup = Node(Role.POPUPMENU, "")
	popup.IAccessibleRole = oleacc.ROLE_SYSTEM_MENUPOPUP
	page.main.add(popup)
	apply_overlays(popup, {"web"})
	focus(page.composer)
	popup.windowHandle = page.composer.windowHandle
	assert popup.shouldAllowIAccessibleMenuStartEvent is False
	popup.states.add(overlays.State.FOCUSED)
	assert popup.shouldAllowIAccessibleMenuStartEvent is True


def test_host_pane_returns_focus_to_the_page_element():
	import winUser
	from NVDAObjects import IAccessible as acc
	from fakes import focus

	page = Page()
	focus(page.composer)
	overlays.note_page_focus(page.composer)
	pane = Node(Role.PANE, "", app=FakeApp("whatsapp.root", isWhatsAppUnified=True))
	pane.windowClassName = overlays.HOST_PANE_CLASS
	apply_overlays(pane, {"app"})
	assert pane.focusRedirect is page.composer
	assert winUser.isWindow(page.composer.windowHandle)
	assert acc.events == {}
