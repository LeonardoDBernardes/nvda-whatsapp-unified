GA_ROOT = 2
OBJID_CLIENT = -4
_titles = {}
_foreground = 1


def reset():
	_titles.clear()
	_buttons_down.clear()


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

VK_LBUTTON = 1
VK_RBUTTON = 2
VK_MBUTTON = 4
_buttons_down = set()


def getAsyncKeyState(vk):
	return 0x8000 if vk in _buttons_down else 0
