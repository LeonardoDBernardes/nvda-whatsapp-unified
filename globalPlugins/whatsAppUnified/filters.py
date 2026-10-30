# -*- coding: UTF-8 -*-
"""Filtros de fala do WhatsApp (telefones, dicas de uso, "Talvez").

Entram pelo ponto de extensão ``speech.extensions.filter_speechSequence`` do
NVDA, sem trocar nenhuma função do NVDA (a troca de ``speech.speak`` da 1.x
deixava a fala morta ao sair quando outro add-on fazia o mesmo). Só mexem na
fala quando o foco está numa LINHA do WhatsApp (conversa ou mensagem) e as
opções são lidas ao vivo, a cada frase.

REGRA: um filtro nunca pode mudar o sentido de uma mensagem. Por isso:
- só se mexe no NOME da linha em foco (o texto que o NVDA fala como nome);
  o eco de digitação, o campo de texto e qualquer outra fala passam intactos;
- "Talvez" só no começo do nome de uma conversa, ou do remetente de uma
  mensagem (o que vem antes dos dois-pontos), nunca no corpo;
- telefone: na lista de conversas, onde estiver; nas mensagens, só como
  remetente (o prefixo antes dos dois-pontos), nunca no corpo;
- dicas de uso: só frases completas conhecidas (começo + palavra de tecla ou
  menu): um item de fala que seja a frase inteira, ou a última frase do nome
  de uma conversa. Nunca dentro do texto de uma mensagem;
- quebras de linha são preservadas.
"""

import re

import api

from . import settings
from .context import wa_context
from .tree import safe_name

PHONE = r"\+\d[()\d\s-]{8,15}"
PHONE_RE = re.compile(PHONE + r"(?=[^\d]|$|\s)")
# Remetente de mensagem de grupo que é só um número: "+55 11 91234-5678: texto".
SENDER_PHONE_RE = re.compile(r"^(\s*)" + PHONE + r"(?=\s*:)\s*:?[ \t]*")
# "Talvez João: texto" (mensagem) e "Talvez João" (conversa).
TALVEZ_CHAT_RE = re.compile(r"^(\s*)Talvez\s+", re.IGNORECASE)
TALVEZ_SENDER_RE = re.compile(r"^(\s*)Talvez\s+(?=[^:\n]{1,80}:)", re.IGNORECASE)

# Dicas de uso do WhatsApp: a frase inteira, do começo conhecido até o ponto
# final (ou o fim do texto). Só vale se também falar de tecla ou menu.
_HINT_START = (
	r"Para acessar (?:o menu|as op[cç][õo]es)|Para mais op[cç][õo]es|"
	r"To access the (?:context )?menu|For more options|"
	r"Para acceder al men[úu]|Para m[aá]s opciones|"
	r"Pour acc[éÉe]der au menu|Pour plus d.options|"
	r"Um auf das Men[üu] zuzugreifen|F[üu]r weitere Optionen|"
	r"Per accedere al men[uù]|Per altre opzioni"
)
USAGE_HINT_RE = re.compile(r"(?:" + _HINT_START + r")[^.\n]{0,160}(?:\.|(?=\n)|$)", re.IGNORECASE)
HINT_KEYWORD_RE = re.compile(
	r"(arrow|seta|flecha|fl[eè]che|pfeil|freccia|menu|men[úu]|context|contexto|tecla|key|press|pression|tasto|taste)",
	re.IGNORECASE,
)
_SPACES_RE = re.compile(r"[ \t]{2,}")


# Dica no FIM do nome: precisa começar uma frase (início, quebra de linha ou
# depois de ponto) e ir até o fim do texto.
TRAILING_HINT_RE = re.compile(
	r"(?:(?<=^)|(?<=\n)|(?<=[.!?] ))(?:" + _HINT_START + r")[^.\n]{0,160}\.?\s*$",
	re.IGNORECASE,
)


def _remove_trailing_hint(text):
	match = TRAILING_HINT_RE.search(text)
	if match and HINT_KEYWORD_RE.search(match.group(0)):
		return text[: match.start()]
	return text


def _tidy(text):
	"""Arruma só espaços repetidos e as pontas; preserva quebras de linha."""
	text = _SPACES_RE.sub(" ", text)
	return text.strip(" \t")


def filter_text(text, kind):
	"""Filtra o NOME de uma linha. ``kind``: 'chat' ou 'message' (outro valor: não mexe)."""
	if not text or kind not in ("chat", "message"):
		return text
	original = text
	# Dica no fim do nome: só em conversa. O texto de uma mensagem é do usuário.
	if kind == "chat" and settings.get("filterUsageHints"):
		text = _remove_trailing_hint(text)
	if kind == "chat":
		if settings.get("filterChatList"):
			text = PHONE_RE.sub("", text)
		if settings.get("filterTalvez"):
			text = TALVEZ_CHAT_RE.sub(r"\1", text)
	else:
		if settings.get("filterMessageList"):
			text = SENDER_PHONE_RE.sub(r"\1", text)
		if settings.get("filterTalvez"):
			text = TALVEZ_SENDER_RE.sub(r"\1", text)
	if text != original:
		text = _tidy(text)
	return text


def filter_item(item, kind, name):
	"""Filtra um item de fala. Só o nome da linha em foco (ou uma dica inteira) é tocado."""
	stripped = item.strip()
	if name and stripped == name.strip():
		return filter_text(item, kind)
	if settings.get("filterUsageHints"):
		# Dica solta (por exemplo a descrição do objeto): só se o item for a frase inteira.
		match = USAGE_HINT_RE.fullmatch(stripped)
		if match and HINT_KEYWORD_RE.search(stripped):
			return ""
	return item


def on_speech_sequence(speechSequence):
	"""Handler de ``filter_speechSequence``: devolve a sequência filtrada."""
	try:
		if not any(isinstance(item, str) for item in speechSequence):
			return speechSequence
		focus = api.getFocusObject()
		if focus is None:
			return speechSequence
		# O tipo vem da classe de sobreposição do objeto em foco. Sem tipo
		# (campo de digitação, botão...) nada é filtrado.
		kind = getattr(focus, "wa_kind", None)
		if kind not in ("chat", "message") or wa_context(focus) is None:
			return speechSequence
		name = safe_name(focus)
		result = []
		changed = False
		for item in speechSequence:
			if isinstance(item, str):
				new = filter_item(item, kind, name)
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
