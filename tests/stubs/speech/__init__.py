spoken = []


def reset():
	spoken.clear()


def speakObject(obj, reason=None, **kwargs):
	spoken.append(("object", obj, reason))
