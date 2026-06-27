import re
import logging

logger = logging.getLogger('app')

def generate_commands(user_text: str, ai_text: str) -> list[str]:
    """
    Analyzes user query and AI response to generate a list of robot commands.
    
    Supported commands:
    - SPEAK_START, SPEAK_STOP
    - EYE_LEFT, EYE_RIGHT, EYE_UP, EYE_DOWN, EYE_CENTER, BLINK
    - HEAD_LEFT, HEAD_RIGHT, HEAD_CENTER, HEAD_NOD, HEAD_SHAKE
    - IDLE
    """
    commands = []
    
    # Standardize inputs
    user_clean = user_text.lower().strip() if user_text else ""
    ai_clean = ai_text.lower().strip() if ai_text else ""
    
    # 1. Parse Eye Movement triggers in User query (e.g. commands to the robot)
    if "look left" in user_clean or "eyes left" in user_clean:
        commands.append("EYE_LEFT")
    elif "look right" in user_clean or "eyes right" in user_clean:
        commands.append("EYE_RIGHT")
    elif "look up" in user_clean or "eyes up" in user_clean:
        commands.append("EYE_UP")
    elif "look down" in user_clean or "eyes down" in user_clean:
        commands.append("EYE_DOWN")
    elif "center eyes" in user_clean or "look center" in user_clean:
        commands.append("EYE_CENTER")
        
    # 2. Parse Head Movement triggers in User query
    if "turn head left" in user_clean or "head left" in user_clean:
        commands.append("HEAD_LEFT")
    elif "turn head right" in user_clean or "head right" in user_clean:
        commands.append("HEAD_RIGHT")
    elif "center head" in user_clean or "head center" in user_clean or "look straight" in user_clean:
        commands.append("HEAD_CENTER")
        
    # 3. Parse gestural reactions based on semantic keys in User or AI response
    nod_patterns = [
        r"\bnod\b", r"\bagree\b", r"\byes\b", r"\bindeed\b", r"\bsure\b", r"\bcorrect\b", r"\bhan\b"
    ]
    shake_patterns = [
        r"\bshake\b", r"\bdisagree\b", r"\bno\b", r"\bcannot\b", r"\bnot\b", r"\bnever\b", r"\bna\b"
    ]
    blink_patterns = [
        r"\bblink\b", r"\bwink\b", r"\bsurprise\b", r"\bwow\b"
    ]
    
    if any(re.search(pat, user_clean) for pat in nod_patterns) or \
       any(re.search(pat, ai_clean) for pat in nod_patterns):
        commands.append("HEAD_NOD")
        
    if any(re.search(pat, user_clean) for pat in shake_patterns) or \
       any(re.search(pat, ai_clean) for pat in shake_patterns):
        commands.append("HEAD_SHAKE")
        
    if any(re.search(pat, user_clean) for pat in blink_patterns) or \
       any(re.search(pat, ai_clean) for pat in blink_patterns):
        commands.append("BLINK")

    # 4. Form final sequence: Wrap inside speak markers if speaking
    final_commands = []
    if ai_text:
        final_commands.append("SPEAK_START")
        # Remove duplicate movement commands while maintaining order
        seen = set()
        for cmd in commands:
            if cmd not in seen:
                final_commands.append(cmd)
                seen.add(cmd)
        final_commands.append("SPEAK_STOP")
    else:
        final_commands.append("IDLE")
        
    logger.info(f"Generated command sequence: {final_commands}")
    return final_commands

def get_movement_flags(commands: list[str]) -> dict:
    """
    Translates a sequence of movement commands into boolean switches
    defining whether mouth, eye, and head motors should activate.
    """
    # Mouth is active if we are speaking
    mouth_active = "SPEAK_START" in commands or "SPEAK_STOP" in commands
    
    # Eye is active if explicit eye movement commands or blinks are requested
    eye_active = any(cmd in commands for cmd in ["EYE_LEFT", "EYE_RIGHT", "EYE_UP", "EYE_DOWN", "BLINK"])
    
    # Head is active if explicit head movements are requested
    head_active = any(cmd in commands for cmd in ["HEAD_LEFT", "HEAD_RIGHT", "HEAD_NOD", "HEAD_SHAKE"])
    
    # Default to True if speaking to keep the robot dynamic during responses
    if mouth_active:
        if not eye_active:
            # Keep eyes active while speaking by default (enables blinking/looking)
            eye_active = True
        if not head_active:
            # Keep head active while speaking by default (enables idle rotation/nodding)
            head_active = True
            
    return {
        "mouth": mouth_active,
        "eye": eye_active,
        "head": head_active
    }
