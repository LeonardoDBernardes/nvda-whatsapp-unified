# -*- coding: UTF-8 -*-
"""WhatsApp Unificado 2.0: módulo fino para o WhatsApp Desktop (WebView2).

O NVDA 2026.2 já mapeia o aplicativo (WhatsApp.Root.exe e o msedgewebview2 que
ele hospeda) para este módulo e já desliga o modo de navegação nele
(``disableBrowseModeByDefault``). Tudo que este add-on faz está no pacote
``globalPlugins/whatsAppUnified``; aqui só se escolhem as classes de
sobreposição das linhas do aplicativo.

Não há mais registro de executáveis, nem troca de funções de fala, nem script
próprio de NVDA+Espaço, nem atalhos de revisão: o NVDA faz isso nativamente.
"""

import appModuleHandler
from logHandler import log

# A partir do NVDA 2026.2 existe o módulo nativo do WhatsApp. Herdamos dele para
# não anular nada do que o NVDA já faz; em NVDA mais antigo a base é a comum.
try:
	from nvdaBuiltin.appModules.whatsapp_root import AppModule as _BaseAppModule
except Exception:
	_BaseAppModule = appModuleHandler.AppModule


_load_failed = False


def _overlays():
	"""O módulo de sobreposições do pacote, importado NO MOMENTO DA CHAMADA.

	Importar no topo deixaria este módulo com uma cópia velha do pacote depois
	de NVDA+Ctrl+F3 (a recarga apaga ``globalPlugins*`` de ``sys.modules`` e
	reimporta; o módulo do aplicativo continuaria usando o antigo).
	"""
	global _load_failed
	try:
		from globalPlugins.whatsAppUnified import overlays

		return overlays
	except Exception:
		if not _load_failed:  # uma vez só: isto roda para todo objeto
			_load_failed = True
			log.error("WhatsApp Unificado: não foi possível carregar o pacote do plugin global", exc_info=True)
		return None


class AppModule(_BaseAppModule):
	#: Marca este módulo como "do WhatsApp" para ``context.raw_context``.
	isWhatsAppUnified = True
	disableBrowseModeByDefault = True

	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		super().chooseNVDAObjectOverlayClasses(obj, clsList)
		overlays = _overlays()
		if overlays is not None:
			overlays.choose_overlay_classes(obj, clsList, {"app"})
