def script(description="", gesture=None, gestures=None, category=None, **kwargs):
	def decorator(func):
		found = list(gestures or [])
		if gesture:
			found.append(gesture)
		func.wa_gestures = tuple(g.lower() for g in found)
		func.wa_description = description
		return func

	return decorator
