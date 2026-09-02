import re
from typing import List, Dict

class TextSanitizer:
    @staticmethod
    def apply_regex_rules(text: str, rules: List[Dict]) -> str:
        """
        Applies a list of regex rules to text.
        Each rule is a dict containing 'pattern', 'replacement', and optionally 'action' ('replace', 'blank', 'extract').
        """
        if not text:
            return ""

        result = text
        for rule in rules:
            pattern = rule.get('pattern')
            action = rule.get('action', 'replace')
            replacement = rule.get('replacement', '')

            if not pattern:
                continue

            try:
                regex = re.compile(pattern, re.IGNORECASE)

                if action == 'blank':
                    result = regex.sub('', result)
                elif action == 'replace':
                    result = regex.sub(replacement, result)
                elif action == 'extract':
                    match = regex.search(result)
                    if match:
                        # Extract the first matching group or the whole match
                        result = match.group(1) if match.groups() else match.group(0)
            except Exception as e:
                # Log error in real app
                pass

        return result.strip()

    @staticmethod
    def apply_blacklists(text: str, blacklisted_words: List[str]) -> str:
        """
        Removes all blacklisted words from the text.
        """
        if not text:
            return ""

        result = text
        for word in blacklisted_words:
            # simple string replacement (could also be whole word regex)
            # using regex for whole word replacement to be safe
            pattern = r'\b' + re.escape(word) + r'\b'
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)

            # fallback to direct replace if needed
            result = result.replace(word, '')

        return result.strip()

    @staticmethod
    def format_filename(original_name: str, prefix: str = "", suffix: str = "", rules: List[Dict] = None, blacklists: List[str] = None) -> str:
        """
        Formats the filename according to prefix, suffix, regex rules, and blacklists.
        """
        if not original_name:
            return "file"

        name_parts = original_name.rsplit('.', 1)
        base_name = name_parts[0]
        ext = f".{name_parts[1]}" if len(name_parts) > 1 else ""

        # Apply rules
        if rules:
            base_name = TextSanitizer.apply_regex_rules(base_name, rules)

        if blacklists:
            base_name = TextSanitizer.apply_blacklists(base_name, blacklists)

        # Apply prefix and suffix
        final_name = f"{prefix}{base_name}{suffix}{ext}"

        # Clean up double spaces or tricky chars
        final_name = re.sub(r'\s+', ' ', final_name).strip()

        return final_name
