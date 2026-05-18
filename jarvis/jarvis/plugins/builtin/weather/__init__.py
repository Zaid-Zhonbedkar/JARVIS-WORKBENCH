"""
JARVIS Builtin Plugin: Weather
Intercepts weather queries and returns current weather via wttr.in
"""

import httpx
from plugins.plugin_manager import JarvisPlugin


class WeatherPlugin(JarvisPlugin):
    name = "weather"
    description = "Handles weather queries using wttr.in (no API key needed)"
    version = "1.0.0"

    TRIGGERS = ["weather", "temperature", "forecast", "rain", "sunny", "cold", "hot outside"]

    def on_command(self, text: str) -> str | None:
        t = text.lower()
        if not any(trigger in t for trigger in self.TRIGGERS):
            return None

        # Extract location from command
        location = self._extract_location(text) or "auto"
        return self._fetch_weather(location)

    def _extract_location(self, text: str) -> str | None:
        keywords = ["in ", "for ", "at "]
        t = text.lower()
        for kw in keywords:
            idx = t.find(kw)
            if idx != -1:
                remainder = text[idx + len(kw):].strip()
                # Take first 2-3 words as location
                words = remainder.split()[:3]
                if words:
                    return "+".join(words)
        return None

    def _fetch_weather(self, location: str) -> str:
        try:
            r = httpx.get(
                f"https://wttr.in/{location}?format=3",
                timeout=5,
                headers={"User-Agent": "JARVIS/1.0"},
            )
            return r.text.strip()
        except Exception as e:
            return f"Weather unavailable: {e}"
