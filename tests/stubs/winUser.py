GA_ROOT = 2
OBJID_CLIENT = -4
_titles = {}
_foreground = 1


def reset():
	_titles.clear()


def setTitle(hwnd, title):
	_titles[hwnd] = title


def getForegroundWindow():
	return _foreground


def getAncestor(hwnd, flags):
	return hwnd


def getWindowText(hwnd):
	return _titles.get(hwnd, "")


def isWindow(hwnd):
	return bool(hwnd)
