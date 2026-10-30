# -*- coding: UTF-8 -*-
"""Filtros de fala do WhatsApp (telefones, dicas de uso, "Talvez").

Entram pelo ponto de extensão ``speech.extensions.filter_speechSequence`` do
NVDA, sem trocar nenhuma função do NVDA (a troca de ``speech.speak`` da 1.x
deixava a fala morta ao sair quando outro add-on fazia o mesmo). Só mexem na
fala quando o foco está no WhatsApp (aplicativo ou Web, conforme o escopo).
As opções são lidas ao vivo, a cada frase.
"""

import re

import api

from . import settings
from .context import wa_context

PHONE_RE = re.compile(r"\+\d[()\d\s-]{8,15}(?=[^\d]|$|\s)")
TALVEZ_RE = re.compile(r"^\s*Talvez\s+", re.IGNORECASE)
USAGE_HINT_RE = re.compile(
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
# Só é dica de uso se a frase também fala de setas/menu (evita cortar mensagens normais).
HINT_KEYWORD_RE = re.compile(r"(arrow|seta|flecha|menu|context|contexto|ok\b)", re.IGNORECASE)
_SPACES_RE = re.compile(r"\s{2,}")


def filter_text(text, kind):
	"""Aplica os filtros a uma frase. ``kind``: 'chat', 'message' ou None."""
	if not text:
		return text
	original = text
	if settings.get("filterUsageHints") and USAGE_HINT_RE.search(text) and HINT_KEYWORD_RE.search(text):
		text = USAGE_HINT_RE.split(text)[0].strip()
	if kind == "chat" and settings.get("filterChatList"):
		text = PHONE_RE.sub("", text)
	elif kind == "message" and settings.get("filterMessageList"):
		text = PHONE_RE.sub("", text)
	if settings.get("filterTalvez") and kind is not None:
		text = TALVEZ_RE.sub("", text)
	if text != original:
		text = _SPACES_RE.sub(" ", text).strip()
	return text


def on_speech_sequence(speechSequence):
	"""Handler de ``filter_speechSequence``: devolve a sequência filtrada."""
	try:
		if not any(isinstance(item, str) for item in speechSequence):
			return speechSequence
		focus = api.getFocusObject()
		if focus is None or wa_context(focus) is None:
			return speechSequence
		# O tipo vem da classe de sobreposição do objeto em foco (sem chamadas extras ao WhatsApp).
		kind = getattr(focus, "wa_kind", None)
		result = []
		changed = False
		for item in speechSequence:
			if isinstance(item, str):
				new = filter_text(item, kind)
				if new != item:
					changed = True
					if not new:
						continue
				result.append(new)
			else:
				result.append(item)
		return result if changed else speechSequence
	except Exception:
		return speechSequence
