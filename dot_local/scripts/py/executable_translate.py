#!/usr/bin/env python3
import sys
import urllib.request
import urllib.parse
import json

def translate_lingva(text, target, source="auto"):
    encoded_text = urllib.parse.quote(text)
    url = f"https://lingva.ml/api/v1/{source}/{target}/{encoded_text}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=5) as response:
        data = json.loads(response.read().decode('utf-8'))
        return data.get("translation")

def translate_mymemory(text, target, source="autodetect"):
    langpair = f"{source}|{target}"
    encoded_text = urllib.parse.quote(text)
    url = f"https://api.mymemory.translated.net/get?q={encoded_text}&langpair={langpair}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=5) as response:
        data = json.loads(response.read().decode('utf-8'))
        translated_text = data.get("responseData", {}).get("translatedText")
        if translated_text:
            return translated_text
        raise ValueError("No translation returned from MyMemory")

def translate(text, target, source="auto"):
    # Try Lingva first
    try:
        return translate_lingva(text, target, source)
    except Exception as e:
        # Fallback to MyMemory
        try:
            mymemory_source = "autodetect" if source == "auto" else source
            return translate_mymemory(text, target, mymemory_source)
        except Exception as e2:
            return f"Translation failed. Lingva error: {e}. MyMemory error: {e2}"

def main():
    args = sys.argv[1:]
    
    if len(args) == 0:
        # Interactive mode
        print("=== Translator (To English) ===")
        text = input("Enter text to translate: ").strip()
        if not text:
            print("Error: Text cannot be empty.")
            sys.exit(1)
        target = "en"
        source = "auto"
    else:
        # Command line arguments mode
        text = args[0]
        target = args[1] if len(args) > 1 else "en"
        source = args[2] if len(args) > 2 else "auto"

    print(f"\nTranslating: '{text}'")
    print(f"Languages:   {source} -> {target}")
    print("----------------------------------------")
    
    result = translate(text, target, source)
    
    print(f"Result:      {result}")
    print("----------------------------------------")

if __name__ == "__main__":
    main()
