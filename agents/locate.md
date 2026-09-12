Task: Extract the room name (location) from a home automation command.

Locations: REPLACE_LOCATIONS

Output Format:
{
"location": "Name of the room"
}

Rules:
1. Search for a mention of one of the Locations in the input text.
2. REPLACE_RULE_LOCATIONS
3. If NO location from the list is mentioned, you MUST return {"location": "Unknown"}.
4. If a location is found, return its exact name from the list.
5. Strictly return ONLY the JSON object.

Input: "Turn off the light" -> {"location": "Unknown"}
Input: "Turn on the kitchen" -> {"location": "Kitchen"}
