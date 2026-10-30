messages = []
browseable = []


def reset():
	messages.clear()
	browseable.clear()


def message(text, *args, **kwargs):
	messages.append(text)


def browseableMessage(message, title=None, isHtml=False):
	browseable.append((message, title))
