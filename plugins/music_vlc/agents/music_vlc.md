Task: Classify the input command into one of these 3 CATEGORY:

MUSIC (Info about current music or VLC/Playback control ONLY: stop, pause, next, volume. 'relance la music', 'stop la music', 'passe la music', 'Remets la musique', 'baisse le son')
DISCOVER (General requests to start playback: 'balance ' 'mets de la musique', 'mets du son', 'joue quelque chose')
NONE (Not related to media playback)

STRICT RULES:
1. Return a JSON object with the key "CATEGORY".
2. Be extremely literal

Constraint: Return ONLY valid JSON: {"CATEGORY": "VALUE"}

Example: {"CATEGORY": "MUSIC"}
