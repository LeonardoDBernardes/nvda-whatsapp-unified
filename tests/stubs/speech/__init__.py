spoken = []


def reset():
	spoken.clear()


def cancelSpeech():
	spoken.append(("cancel",))


def speakObject(obj, reason=None, **kwargs):
	spoken.append(("object", obj, reason))


def speakText(text, *args, **kwargs):
	spoken.append(("text", text))


def speakSpelling(text, *args, **kwargs):
	spoken.append(("spelling", text))
