"""Instala os stubs do NVDA antes de importar o add-on e zera o estado a cada teste."""

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for path in (os.path.join(HERE, "stubs"), HERE, ROOT):
	if path not in sys.path:
		sys.path.insert(0, path)

import addonHandler  # noqa: E402

addonHandler.initTranslation()


@pytest.fixture(autouse=True)
def clean_state():
	import api
	import browseMode
	import config
	import core
	import inputCore
	import keyboardHandler
	import speech
	import ui
	import winUser
	from speech.extensions import filter_speechSequence

	api.reset()
	core.reset()
	ui.reset()
	speech.reset()
	winUser.reset()
	browseMode.reset()
	config.conf.reset()
	keyboardHandler.sent.clear()
	inputCore.decide_handleRawKey.handlers.clear()
	filter_speechSequence.handlers.clear()
	from globalPlugins.whatsAppUnified import context, recovery, settings

	settings.register_config()
	config.conf[settings.CONFIG_SECTION].update(settings.DEFAULTS)
	recovery.reset()
	context.forget_kinds()
	context._web_cache.clear()
	yield
