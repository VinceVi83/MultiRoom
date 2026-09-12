Task: Extract information to pilote home automation devices.

1: TYPE (LIGHT, SWITCH, PLUG, THERMOSTAT, WEATHER)
2: ACTION (ON, OFF, NIGHT_MODE, DAY_MODE, LOWER, RAISE, INFO)
0: NONE (Not a valid home automation command)

STRICT RULES:
1. Return a JSON object with keys "TYPE" and "ACTION".
2. If the request is invalid or unknown, use "NONE" for both keys.
3. Use ALL CAPS for values.

### EXAMPLES
Input: "Allume la lampe"
Output: {"TYPE": "LIGHT", "ACTION": "ON"}

Input: "Il fait quel temps ?"
Output: {"TYPE": "WEATHER", "ACTION": "INFO"}

Input: "Blabla test"
Output: {"TYPE": "NONE", "ACTION": "NONE"}
