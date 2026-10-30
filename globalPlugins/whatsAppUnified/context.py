# -*- coding: UTF-8 -*-
"""Onde estamos? Aplicativo do WhatsApp, WhatsApp Web ou outra coisa.

``wa_context(obj)`` devolve "app", "web" ou None. Respeita a opção "escopo".

Regras de desempenho (isto roda na thread principal do NVDA e na criação de
TODO objeto de navegador):
- o WhatsApp Web só é reconhecido pelo ENDEREÇO do documento (web.whatsapp.com).
  O título da janela NÃO é usado: ele deixava qualquer aba chamada "WhatsApp"
  disparar varreduras;
- o veredito é guardado por tree interceptor (conferindo se o endereço mudou) e
  por janela (hwnd) com validade curta, então objetos criados em seguida custam
  uma consulta a dicionário;
- a classificação de linhas é guardada por contêiner.
"""

import re
import time
import weakref

import api

from . import settings
from .tree import (
	ROW_ROLES,
	CELL_ROLES,
	Role,
	ancestors,
	find_composer,
	is_chat_list_container,
	new_deadline,
	safe_parent,
	safe_role,
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


# ─── veredito do WhatsApp Web ────────────────────────────────────────────────

# Por tree interceptor (referência fraca): (endereço, veredito). Vale só
# enquanto o endereço é o mesmo: se o buffer navegar para outro site, recalcula.
_ti_cache = weakref.WeakKeyDictionary()
# Por janela (hwnd): (instante, veredito, conhecido). Validade curta.
_hwnd_cache = {}
_HWND_TTL_KNOWN = 2.0
_HWND_TTL_UNKNOWN = 0.5
_HWND_MAX = 64


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


def _remember_hwnd(hwnd, verdict, known=True):
	if len(_hwnd_cache) >= _HWND_MAX:
		_hwnd_cache.clear()
	_hwnd_cache[hwnd] = (time.monotonic(), verdict, known)


def _compute_web_verdict(obj):
	"""(veredito, conhecido) sem usar o cache por janela."""
	try:
		holder = obj.treeInterceptor
	except Exception:
		holder = None
	if holder is not None:
		verdict = ti_verdict(holder)
		if verdict is not None:
			return verdict, True
	doc = find_document(obj)
	if doc is not None:
		verdict = url_is_whatsapp(document_url(doc))
		if verdict is not None:
			return verdict, True
	return False, False


def web_verdict(obj):
	"""O objeto de navegador está no WhatsApp Web (endereço confirmado)?"""
	try:
		hwnd = obj.windowHandle
	except Exception:
		hwnd = 0
	hit = _hwnd_cache.get(hwnd) if hwnd else None
	if hit is not None:
		ttl = _HWND_TTL_KNOWN if hit[2] else _HWND_TTL_UNKNOWN
		if time.monotonic() - hit[0] < ttl:
			return hit[1]
	verdict, known = _compute_web_verdict(obj)
	if hwnd:
		_remember_hwnd(hwnd, verdict, known)
	return verdict


def forget_web():
	_ti_cache.clear()
	_hwnd_cache.clear()


def app_name_of(obj):
	try:
		return (obj.appModule.appName or "").lower()
	except Exception:
		return ""


def raw_context(obj):
	"""Contexto sem olhar o escopo: "app", "web" ou None."""
	try:
		module = obj.appModule
	except Exception:
		return None
	if module is None:
		return None
	if getattr(module, "isWhatsAppUnified", False):
		return "app"
	name = app_name_of(obj)
	if name == APP_NAME:
		return "app"
	if name in BROWSER_APPS:
		try:
			return "web" if web_verdict(obj) else None
		except Exception:
			return None
	return None


def wa_context(obj):
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
	verdict = url_is_whatsapp(document_url(doc))
	if verdict is not None:
		try:
			_remember_hwnd(doc.windowHandle, verdict)
		except Exception:
			pass
	return bool(verdict)


# ─── Que tipo de linha é este objeto? ────────────────────────────────────────

_kind_cache = {}
_KIND_TTL = 10.0
_KIND_MAX = 128
_CONVERSATION_SECONDS = 0.15


def _obj_key(obj):
	try:
		return (obj.windowHandle, obj.IA2UniqueID)
	except Exception:
		try:
			return (obj.windowHandle, tuple(obj.location or ()))
		except Exception:
			return id(obj)


def _in_conversation(container):
	"""A lista ``container`` está dentro do painel da conversa (tem o campo de digitação por perto)?

	Sobe poucos níveis e procura o campo com orçamento pequeno, todos os níveis
	dividindo um prazo curto.
	"""
	deadline = new_deadline(_CONVERSATION_SECONDS)
	for parent in ancestors(container, 5):
		if time.monotonic() > deadline:
			return False
		if find_composer(parent, budget=300, deadline=deadline) is not None:
			return True
	return False


def classify_container(container):
	"""'chat' | 'message' | None para o contêiner de linhas (guardado por contêiner)."""
	key = _obj_key(container)
	now = time.monotonic()
	hit = _kind_cache.get(key)
	if hit is not None and now - hit[0] < _KIND_TTL:
		return hit[1]
	result = None
	node = container
	for _level in range(7):
		if node is None:
			break
		if is_chat_list_container(node):
			result = "chat"
			break
		node = safe_parent(node)
	if result is None and _in_conversation(container):
		result = "message"
	if len(_kind_cache) >= _KIND_MAX:
		_kind_cache.clear()
	_kind_cache[key] = (now, result)
	return result


def row_kind(obj):
	"""'chat' | 'message' | None para linhas e células do WhatsApp.

	- linha ou célula dentro de uma lista de conversas (nome acessível) = 'chat';
	- linha fora dela e dentro do painel da conversa = 'message'.
	"""
	role = safe_role(obj)
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


def in_whatsapp_foreground():
	"""O foco atual está no WhatsApp (app ou web, conforme o escopo)?"""
	try:
		return wa_context(api.getFocusObject()) is not None
	except Exception:
		return False
