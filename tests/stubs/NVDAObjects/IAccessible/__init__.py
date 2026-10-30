from NVDAObjects import NVDAObject

events = {}


class IAccessible(NVDAObject):
	def _get_shouldAllowIAccessibleMenuStartEvent(self):
		return True


def getNVDAObjectFromEvent(hwnd, objectID, childID):
	return events.get((hwnd, objectID, childID))
