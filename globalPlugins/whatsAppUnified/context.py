# -*- coding: UTF-8 -*-
"""Onde estamos? Aplicativo do WhatsApp, WhatsApp Web ou outra coisa.

``wa_context(obj)`` devolve "app", "web" ou None. Respeita a opção "escopo".

Regras de desempenho (isto roda na thread principal do NVDA e na criação de
TODO objeto de navegador):
- o WhatsApp Web só é reconhecido pelo ENDEREÇO do documento (web.whatsapp.com).
  O título da janela NÃO é usado: ele deixava qualquer aba chamada "WhatsApp"
  disparar varreduras;
- o contexto do foco é calculado UMA vez por evento de foco (``update_focus``,
  chamado pelo plugin global) e guardado; todo gancho global começa por
  ``active()`` e sai sem COM quando o foco não está no WhatsApp. NÃO há
  veredito por janela (abas e a interface do navegador compartilham janelas);
- a classificação de linhas é guardada por contêiner.
"""

import re
import time
import weakref

import api

from . import diag, settings
from .tree import (
	ROW_ROLES,
	CELL_ROLES,
	Role,
	State,
	ancestors,
	is_chat_list_container,
	is_inner_focus,
	row_ancestor,
	safe_parent,
	safe_role,
	safe_states,
)

# O NVDA grava o nome do executável em minúsculas e sem ".exe": o
# WhatsApp.Root.exe vira "whatsapp.root" (appModuleHandler.getAppNameFromProcessID).
APP_NAME = "whatsapp.root"

# Único endereço tratado como WhatsApp Web (não vale faq., www. nem o site institucional).
WEB_HOST = "web.whatsapp.com"

BROWSER_APPS = frozenset(
	("chrome", "msedge", "firefox", "brave", "opera", "vivaldi", "chromium", "iexplore"),
)

# Endereço de site de verdade. Separa "o documento aponta outro site" de
# "o documento não tem endereço utilizável".
_SITE_RE = re.compile(r"^(?:[a-z0-9-]+\.)+[a-z]{2,}$", re.IGNORECASE)


def host_of(url):
	"""Domínio de um endereço, ou None se o texto não for um endereço utilizável."""
	if not url:
		return None
	try:
		site = str(url).strip().lower()
		if "://" in site:
			site = site.split("://", 1)[1]
		site = site.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
		if "@" in site:
			site = site.rsplit("@", 1)[1]
		if site.count(":") == 1:  # porta
			site = site.split(":", 1)[0]
		if not _SITE_RE.match(site):
			return None
		return site
	except Exception:
		return None


def is_whatsapp_host(host):
	return host == WEB_HOST


def url_is_whatsapp(url):
	"""True/False se o endereço é utilizável; None se não der para decidir pelo endereço."""
	host = host_of(url)
	if host is None:
		return None
	return is_whatsapp_host(host)


def document_url(doc):
	"""Endereço de um documento web: de um tree interceptor ou de um objeto IAccessible."""
	for attr in ("documentConstantIdentifier", "documentURL"):
		try:
			value = getattr(doc, attr, None)
		except Exception:
			value = None
		if value:
			return value
	try:
		return doc.IAccessibleObject.accValue(0)
	except Exception:
		return None


def find_document(obj, limit=6):
	"""O objeto de papel DOCUMENT que contém ``obj`` (ou o próprio), ou None.

	Se ``obj`` é o foco, usa a cadeia de ancestrais do foco que o NVDA já tem
	(nenhuma chamada ao WhatsApp). Senão sobe poucos pais (``limit`` pequeno).
	"""
	if safe_role(obj) == Role.DOCUMENT:
		return obj
	try:
		focus = api.getFocusObject()
	except Exception:
		focus = None
	if focus is not None and obj is focus:
		try:
			chain = list(api.getFocusAncestors())
		except Exception:
			chain = []
		for parent in reversed(chain):
			if safe_role(parent) == Role.DOCUMENT:
				return parent
		return None
	for parent in ancestors(obj, limit):
		if safe_role(parent) == Role.DOCUMENT:
			return parent
	return None


# ─── onde está o foco? (calculado UMA vez por evento de foco) ────────────────

# Por tree interceptor (referência fraca): (endereço, veredito). Vale só
# enquanto o endereço é o mesmo: se o buffer navegar para outro site, recalcula.
_ti_cache = weakref.WeakKeyDictionary()


def ti_verdict(ti):
	"""True/False pelo endereço atual do documento do buffer; None se indisponível."""
	try:
		ident = ti.documentConstantIdentifier
	except Exception:
		return None
	if not ident:
		return None
	try:
		cached = _ti_cache.get(ti)
	except TypeError:
		cached = None
	if cached is not None and cached[0] == ident:
		return cached[1]
	verdict = url_is_whatsapp(ident)
	if verdict is not None:
		try:
			_ti_cache[ti] = (ident, verdict)
		except TypeError:
			pass
	return verdict


class _Focus:
	"""O contexto do foco ATUAL. Só ``update_focus`` (evento de foco) escreve aqui.

	Nunca há veredito por janela: duas abas do Chrome, a barra de endereço e as
	abas do navegador compartilham janelas, e um veredito por janela faria
	outras páginas parecerem WhatsApp. O veredito é do DOCUMENTO em foco.
	"""

	kind = None  # "app", "web" ou None (sem olhar o escopo)
	hwnd = 0  # janela do objeto que confirmou o contexto
	obj = None  # o objeto de foco que confirmou (referência forte, solta no próximo foco)


def active():
	"""Contexto do último evento de foco ("app", "web" ou None). Sem COM, sem api.

	É a PRIMEIRA linha de todo gancho global: fora do WhatsApp (ou do WhatsApp
	Web confirmado pelo endereço) devolve None e o gancho sai.
	"""
	return _Focus.kind


def app_name_of(obj):
	try:
		return (obj.appModule.appName or "").lower()
	except Exception:
		return ""


def _is_app(obj):
	try:
		module = obj.appModule
	except Exception:
		return False
	if module is None:
		return False
	if getattr(module, "isWhatsAppUnified", False):
		return True
	return (getattr(module, "appName", "") or "").lower() == APP_NAME


def _confirm_web(obj):
	"""O foco (``obj``) está num documento cujo ENDEREÇO é web.whatsapp.com?

	Uma leitura de endereço por evento de foco: o buffer (tree interceptor) que o
	NVDA já resolveu para o foco, ou, sem buffer, o documento da cadeia de
	ancestrais do foco (que o NVDA já tem pronta). Barra de endereço, abas e
	menus do navegador não têm documento: custo zero e resposta "não".
	"""
	try:
		holder = obj.treeInterceptor
	except Exception:
		holder = None
	if holder is not None:
		verdict = ti_verdict(holder)
		if verdict is not None:
			return verdict
	doc = find_document(obj)
	if doc is not None:
		return bool(url_is_whatsapp(document_url(doc)))
	return False


def update_focus(obj):
	"""Chamado PELO plugin global em todo evento de foco: decide o contexto UMA vez.

	Devolve "app", "web" ou None. Programa que não é o WhatsApp nem um navegador:
	só o nome do aplicativo é lido (sem COM) e o contexto é zerado.
	"""
	kind = None
	hwnd = 0
	try:
		if _is_app(obj):
			kind = "app"
		elif app_name_of(obj) in BROWSER_APPS and _confirm_web(obj):
			kind = "web"
		if kind is not None:
			hwnd = obj.windowHandle
	except Exception:
		kind = None
	_Focus.kind = kind
	_Focus.hwnd = hwnd
	_Focus.obj = obj if kind is not None else None
	return kind


def forget_focus():
	_Focus.kind = None
	_Focus.hwnd = 0
	_Focus.obj = None


def forget_web():
	_ti_cache.clear()
	forget_focus()


def web_overlay_allowed(obj):
	"""Criação de objeto de navegador: o foco confirmado é WhatsApp Web e o objeto é da mesma janela?

	Comparação barata (nenhuma chamada ao navegador): o evento de foco já
	confirmou o endereço; aqui só se compara a janela do objeto com a do foco.
	"""
	if _Focus.kind != "web":
		return False
	try:
		if api.getFocusObject() is not _Focus.obj:
			return False
		return obj.windowHandle == _Focus.hwnd
	except Exception:
		return False


def raw_context(obj=None):
	"""Contexto sem olhar o escopo: "app", "web" ou None.

	``obj`` None ou o próprio foco: devolve o contexto do foco. Outro objeto: só
	vale se for do mesmo programa e da mesma janela que o foco confirmado.
	"""
	kind = _Focus.kind
	if kind is None:
		return None
	try:
		focus = api.getFocusObject()
		if focus is not _Focus.obj:
			return None
		if obj is None or obj is focus:
			return kind
		if kind == "app":
			return "app" if _is_app(obj) else None
		return "web" if (app_name_of(obj) in BROWSER_APPS and obj.windowHandle == _Focus.hwnd) else None
	except Exception:
		return None


def wa_context(obj=None):
	""""app", "web" ou None, já respeitando a opção de escopo."""
	kind = raw_context(obj)
	if kind and not settings.scope_allows(kind):
		return None
	return kind


def is_web_document(doc):
	"""O objeto raiz de um documento de navegador é o WhatsApp Web (endereço confirmado)?

	Só o endereço decide. Sem endereço utilizável a resposta é não, nunca uma
	adivinhação pelo título da janela.
	"""
	if app_name_of(doc) not in BROWSER_APPS:
		return False
	return bool(url_is_whatsapp(document_url(doc)))


# ─── Que tipo de linha é este objeto? ────────────────────────────────────────

_kind_cache = {}
_KIND_TTL = 10.0
_KIND_MAX = 128
# Até quantos níveis acima da linha procurar a lista de conversas ou o painel das mensagens.
_KIND_LEVELS = 7


def _obj_key(obj):
	try:
		return (obj.windowHandle, obj.IA2UniqueID)
	except Exception:
		try:
			return (obj.windowHandle, tuple(obj.location or ()))
		except Exception:
			return id(obj)


def _is_message_pane(node):
	"""Painel das mensagens: contêiner FOCÁVEL acima da linha, que não é a lista de conversas.

	Código da página, 29/10/2026 (WAWebConversationMsgs): as mensagens ficam
	dentro de um div focável (``conversation-panel-messages``, tabIndex 0); a
	lista de conversas é uma grade com nome ("Lista de conversas"), testada
	antes em cada nível. A 2.0.2 procurava o campo de digitação em volta da
	lista: 400 a 600 ms por mensagem no log do Leo (30/10) e nem sempre achava.
	"""
	role = safe_role(node)
	if role in ROW_ROLES or role == Role.DOCUMENT:
		return False
	return State.FOCUSABLE in safe_states(node)


def classify_container(container):
	"""'chat' | 'message' | None para o contêiner de linhas (guardado por contêiner).

	Só sobe pelos pais (poucas chamadas): lista de conversas pelo nome, senão
	o painel focável das mensagens. Para no documento.
	"""
	key = _obj_key(container)
	now = time.monotonic()
	hit = _kind_cache.get(key)
	if hit is not None and now - hit[0] < _KIND_TTL:
		return hit[1]
	result = None
	node = container
	for _level in range(_KIND_LEVELS):
		if node is None or safe_role(node) == Role.DOCUMENT:
			break
		if is_chat_list_container(node):
			result = "chat"
			break
		if _is_message_pane(node):
			result = "message"
			break
		node = safe_parent(node)
	if len(_kind_cache) >= _KIND_MAX:
		_kind_cache.clear()
	_kind_cache[key] = (now, result)
	diag.act("linha", "tipo=%s niveis=%d" % (result, _level + 1), key="linha:%s" % result)
	return result


def row_kind(obj):
	"""'chat' | 'message' | None para linhas, células e o div focável de uma linha.

	- linha ou célula dentro de uma lista de conversas (nome acessível) = 'chat';
	- linha fora dela e dentro do painel da conversa = 'message';
	- div focável (SECTION) dentro de uma linha: o tipo da linha. É ESTE o objeto
	  que recebe o foco quando se anda pelas conversas e mensagens.
	"""
	role = safe_role(obj)
	if is_inner_focus(obj):
		row = row_ancestor(obj)
		if row is None:
			return None
		container = safe_parent(row)
		if container is None:
			return None
		return classify_container(container)
	if role in CELL_ROLES:
		row = safe_parent(obj)
		container = safe_parent(row) if row is not None and safe_role(row) in ROW_ROLES else row
		if container is None:
			return None
		return "chat" if classify_container(container) == "chat" else None
	if role in ROW_ROLES:
		container = safe_parent(obj)
		if container is None:
			return None
		return classify_container(container)
	return None


def forget_kinds():
	_kind_cache.clear()
