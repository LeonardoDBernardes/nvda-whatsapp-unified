"""Stub de api: foco e area de transferencia controlados pelo teste."""

_focus = None
_ancestors = []
_foreground = None
clipboard = []


def reset():
	global _focus, _ancestors, _foreground
	_focus = None
	_ancestors = []
	_foreground = None
	clipboard.clear()


def setFocusObject(obj, ancestors=None):
	global _focus, _ancestors
	_focus = obj
	if ancestors is not None:
		_ancestors = list(ancestors)
	else:
		chain = []
		parent = getattr(obj, "parent", None)
		while parent is not None:
			chain.append(parent)
			parent = getattr(parent, "parent", None)
		_ancestors = list(reversed(chain))
	return True


def getFocusObject():
	return _focus


def getFocusAncestors():
	return list(_ancestors)


def setForegroundObject(obj):
	global _foreground
	_foreground = obj


def getForegroundObject():
	return _foreground or _focus


def copyToClip(text, notify=False):
	clipboard.append(text)
	return True
