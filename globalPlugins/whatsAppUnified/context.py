# -*- coding: UTF-8 -*-
"""Onde estamos? Aplicativo do WhatsApp, WhatsApp Web ou outra coisa.

``wa_context(obj)`` devolve "app", "web" ou None. Respeita a opção "escopo".
Não existe um booleano global que vaze para outras abas: o veredito do Web é
guardado por documento (referência fraca) e conferido pelo endereço do documento.
"""

import re
import time
import weakref

import api
import winUser

from . import settings
from .tree import (
	ROW_ROLES,
	CELL_ROLES,
	Role,
	ancestors,
	chat_list_of,
	find_composer,
	safe_parent,
	safe_role,
)

# O NVDA grava o nome do executável em minúsculas e sem ".exe": o
# WhatsApp.Root.exe vira "whatsapp.root" (appModuleHandler.getAppNameFromProcessID).
APP_NAME = "whatsapp.root"

BROWSER_APPS = frozenset(
	("chrome", "msedge", "firefox", "brave", "opera", "vivaldi", "chromium", "iexplore"),
)

# Endereço de site de verdade (ex.: web.whatsapp.com). Separa "o documento
# aponta outro site" de "o documento não tem endereço utilizável".
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
	return host == "whatsapp.com" or (host is not None and host.endswith(".whatsapp.com"))


def _window_title_has_whatsapp():
	try:
		return "whatsapp" in winUser.getWindowText(winUser.getForegroundWindow()).lower()
	except Exception:
		return False


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


def find_document(obj, limit=40):
	"""O objeto de papel DOCUMENT que contém ``obj`` (ou o próprio), ou None."""
	if safe_role(obj) == Role.DOCUMENT:
		return obj
	for parent in ancestors(obj, limit):
		if safe_role(parent) == Role.DOCUMENT:
			return parent
	return None


# Veredito por documento (referência fraca). Se o objeto não aceitar
# referência fraca, simplesmente não guarda.
_web_cache = weakref.WeakKeyDictionary()


def _is_web_whatsapp(obj):
	holder = None
	try:
		holder = getattr(obj, "treeInterceptor", None)
	except Exception:
		holder = None
	if holder is not None and getattr(holder, "_wa_verdict", None) is not None:
		return holder._wa_verdict
	doc = holder if holder is not None and hasattr(holder, "rootNVDAObject") else find_document(obj)
	if doc is None:
		return _window_title_has_whatsapp()
	try:
		cached = _web_cache.get(doc)
	except TypeError:
		cached = None
	if cached is not None:
		return cached
	verdict = url_is_whatsapp(document_url(doc))
	if verdict is None:
		# Sem endereço utilizável (por exemplo identificador de buffer UIA):
		# o título da janela é a reserva. Não guarda, pode melhorar depois.
		return _window_title_has_whatsapp()
	try:
		_web_cache[doc] = verdict
	except TypeError:
		pass
	return verdict


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
			return "web" if _is_web_whatsapp(obj) else None
		except Exception:
			return None
	return None


def wa_context(obj):
	""""app", "web" ou None, já respeitando a opção de escopo."""
	kind = raw_context(obj)
	if kind and not settings.scope_allows(kind):
		return None
	return kind


def web_title_hint(obj):
	"""Pista barata: o título da janela de topo do objeto fala de WhatsApp?

	Serve só para decidir se vale olhar a estrutura de um objeto recém-criado;
	quem age de verdade confere o endereço do documento (``wa_context``).
	"""
	try:
		top = winUser.getAncestor(obj.windowHandle, winUser.GA_ROOT)
		return "whatsapp" in winUser.getWindowText(top or obj.windowHandle).lower()
	except Exception:
		return False


def is_web_document(obj):
	"""Um documento de navegador (objeto raiz) que é o WhatsApp Web?

	Não toca em ``obj.treeInterceptor`` (o objeto ainda está sendo criado quando
	isto roda). Endereço primeiro; título da janela só sem endereço utilizável.
	"""
	if app_name_of(obj) not in BROWSER_APPS:
		return False
	verdict = url_is_whatsapp(document_url(obj))
	if verdict is None:
		return web_title_hint(obj)
	return verdict


# ─── Que tipo de linha é este objeto? ────────────────────────────────────────

_kind_cache = {}
_KIND_TTL = 3.0
_KIND_MAX = 128


def _obj_key(obj):
	try:
		return (obj.windowHandle, obj.IA2UniqueID)
	except Exception:
		try:
			return (obj.windowHandle, tuple(obj.location or ()))
		except Exception:
			return id(obj)


def _in_conversation(container):
	"""A lista ``container`` está dentro do painel da conversa (tem o campo de digitação por perto)?"""
	key = _obj_key(container)
	now = time.monotonic()
	hit = _kind_cache.get(key)
	if hit is not None and now - hit[0] < _KIND_TTL:
		return hit[1]
	result = False
	for parent in ancestors(container, 10):
		if find_composer(parent, budget=400) is not None:
			result = True
			break
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
	if role in ROW_ROLES or role in CELL_ROLES:
		if chat_list_of(obj) is not None:
			return "chat"
	if role in ROW_ROLES:
		parent = safe_parent(obj)
		if parent is not None and _in_conversation(parent):
			return "message"
	return None


def forget_kinds():
	_kind_cache.clear()


def in_whatsapp_foreground():
	"""O foco atual está no WhatsApp (app ou web, conforme o escopo)?"""
	try:
		return wa_context(api.getFocusObject()) is not None
	except Exception:
		return False
