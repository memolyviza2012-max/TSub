# -*- coding: utf-8 -*-
"""
TSub - Subtitle Translation Studio
Specialized Subtitle Prompts, Context Guards, and Timing Constraints.
"""

DEFAULT_SUBTITLE_PROMPT = """You are a Master-Level English-to-Thai Video Game and Cinematic Subtitle Specialist.
Translate this subtitle line. Context ID: '{id}'. Duration: {duration}s.

CRITICAL SUBTITLE RULES:
1. Natural Dialogue: Translate into fluid, spoken Thai suited for subtitles (ภาษาพูดที่เป็นธรรมชาติ กระชับ ไม่เยิ่นเย้อ).
2. Subtitle Length & Timing: Keep the translation concise so viewers can read it in {duration} seconds. Max 2 lines.
3. Preserve HTML/Tags: Preserve all formatting tags like <i>...</i>, <b>...</b>, <font color="..."> exactly as they appear.
4. Output Format: Return ONLY the pure Thai translation. No quotation marks, no explanations, no markdown.

[GLOSSARY TO USE]

Original Subtitle:
{source_text}"""

DEFAULT_SUBTITLE_OPTIONS_PROMPT = """You are a Master-Level English-to-Thai Subtitle Specialist.
Translate this subtitle into 3 distinct cinematic styles:
1. Natural / Conversational (ภาษาพูดธรรมชาติ พอดีคำ)
2. Direct / Accurate (แปลตรงตามต้นฉบับ ชัดเจน)
3. Dynamic / Punchy (กระชับ ได้อารมณ์ คมคาย)

Context ID: '{id}'. Duration: {duration}s.
[GLOSSARY TO USE]

Return ONLY a valid JSON array of 3 strings: ["option1", "option2", "option3"]
Original Subtitle:
{source_text}"""

CINEMATIC_MODES = {
    "natural": "Translate into natural, conversational, contemporary Thai dialogue (บทพูดธรรมชาติ ไหลลื่น).",
    "gritty": "Translate into aggressive, raw, mature, or profane Thai dialogue suitable for a dark/gritty action game (ดุดัน หยาบคาย สัจนิยม).",
    "fantasy": "Translate using medieval, archaic, or fantasy Thai dialogue with appropriate pronouns (ย้อนยุค/แฟนตาซี ข้า-เจ้า-ท่าน).",
    "casual_slang": "Translate into modern youth slang, casual, or sarcastic tone (สแลง/กวนๆ เป็นกันเอง).",
    "formal": "Translate into highly formal, polite, or official documentary Thai (สุภาพ/ทางการ).",
    "poem": "Translate into rhythmic, rhyming Thai poetic verse (กลอน/บทกวี/คำสาบาน).",
    "robotic": "Translate into cold, systemic AI / automated announcement tone (ประกาศระบบ/หุ่นยนต์)."
}

def build_special_prompt(mode_key: str, item_id: str, duration: float, source_text: str, game_name: str = "") -> str:
    mode_desc = CINEMATIC_MODES.get(mode_key, CINEMATIC_MODES["natural"])
    game_ctx = f" for '{game_name}'" if game_name else ""
    return f"""You are a Master-Level English-to-Thai Subtitle Specialist{game_ctx}.
Tone Directive: {mode_desc}
Context ID: '{item_id}'. Duration: {duration}s.

CRITICAL SUBTITLE RULES:
1. Length: Keep the translation concise (max 2 lines) so it matches the {duration}s screen time.
2. Tags: Preserve all HTML tags (<i>, <b>, <font>) exactly as given.
3. Return ONLY the final Thai subtitle text. No markdown, no explanations, no quotes.

[GLOSSARY TO USE]

Original Subtitle:
{source_text}"""