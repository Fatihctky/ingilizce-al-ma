#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
English Study App — QUIZ + SRS + VOICE + TRANSLATE + CONVERSATION (B1)
v5.1 — Edge TTS iyileştirme:
 - edge_tts.list_voices() ile mevcut Türkçe/İngilizce Neural sesleri otomatik seç
 - Birden fazla ses adı dener; hiçbiri çalışmazsa sessiz düşer
 - mp3 çalma için playsound başarısızsa os.startfile ile aç
"""

from __future__ import annotations
import json, os, random, re, tempfile, asyncio
from datetime import date, timedelta, datetime
from typing import Optional

DATA_FILE = "vocab_en_tr.json"
USER_DATA = "conversation_data.json"
INTERVALS = [0, 1, 2, 4, 7, 15, 30]

# ---------- Edge TTS ----------
EDGE_OK = False
EDGE_TR_VOICE = None
EDGE_EN_VOICE = None
try:
    import edge_tts
    EDGE_OK = True

    async def _pick_edge_voices():
        global EDGE_TR_VOICE, EDGE_EN_VOICE
        try:
            voices = await edge_tts.list_voices()  # returns list of dicts
            # Türkçe için uygun ilk voice
            tr = [v for v in voices if str(v.get('Locale','')).lower().startswith('tr-')]
            en = [v for v in voices if str(v.get('Locale','')).lower().startswith('en-')]
            EDGE_TR_VOICE = (tr[0]['ShortName'] if tr else "tr-TR-SedaNeural")
            EDGE_EN_VOICE = (en[0]['ShortName'] if en else "en-US-AriaNeural")
        except Exception:
            EDGE_TR_VOICE = "tr-TR-SedaNeural"
            EDGE_EN_VOICE = "en-US-AriaNeural"

    # pick voices now (synchronously)
    try:
        asyncio.run(_pick_edge_voices())
    except Exception:
        EDGE_TR_VOICE = "tr-TR-SedaNeural"
        EDGE_EN_VOICE = "en-US-AriaNeural"

    def _play_mp3(path: str):
        # Önce playsound
        try:
            import playsound
            playsound.playsound(path, block=True)
            return
        except Exception:
            pass
        # Windows'ta varsayılan oynatıcı
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except Exception:
            print(f"(Ses dosyasını manuel çalabilirsiniz: {path})")

    async def edge_tts_say(text: str, voice_candidates):
        """voice_candidates bir liste olabilir: sırayla dener"""
        last_err = None
        for voice in voice_candidates:
            fn = tempfile.mktemp(suffix=".mp3")
            try:
                comm = edge_tts.Communicate(text, voice=voice)
                await comm.save(fn)
                _play_mp3(fn)
                return True
            except Exception as e:
                last_err = e
            finally:
                try:
                    os.remove(fn)
                except Exception:
                    pass
        if last_err:
            print(f"(Edge TTS hatası: {last_err})")
        return False

except Exception:
    EDGE_OK = False

# ---------- pyttsx3 (yerel) ----------
TTS_AVAILABLE = False
engine = None
try:
    import pyttsx3
    engine = pyttsx3.init()
    engine.setProperty('rate', 160)
    TTS_AVAILABLE = True
except Exception:
    TTS_AVAILABLE = False

def detect_voice_id(lang: str) -> Optional[str]:
    if not TTS_AVAILABLE:
        return None
    short = "tr" if lang.startswith("tr") else "en"
    try:
        for v in engine.getProperty('voices'):
            name = (getattr(v, 'name', '') or '').lower()
            vid  = (getattr(v, 'id',   '') or '').lower()
            langs = ",".join([str(l).lower() for l in (getattr(v, 'languages', []) or [])])
            haystack = " ".join([name, vid, langs])
            if short == "tr":
                if any(k in haystack for k in ["tr-tr", "tr_tr", " turkish", " turk", "tts_turkish", "tr_"]):
                    return v.id
            else:
                if any(k in haystack for k in ["en-us", "en_gb", "english", "en_"]):
                    return v.id
    except Exception:
        pass
    return None

_voice_cache = {"tr": None, "en": None}

def set_pyttsx3_voice(lang: str) -> bool:
    if not TTS_AVAILABLE:
        return False
    short = "tr" if lang.startswith("tr") else "en"
    vid = _voice_cache.get(short) or detect_voice_id(short)
    if not vid:
        return False
    try:
        engine.setProperty('voice', vid)
        _voice_cache[short] = vid
        return True
    except Exception:
        return False

def speak(text: str, lang: str = "en"):
    short = "tr" if lang.startswith("tr") else "en"
    # 1) yerel ses
    if TTS_AVAILABLE and set_pyttsx3_voice(lang):
        try:
            engine.say(text)
            engine.runAndWait()
            return
        except Exception:
            pass
    # 2) edge-tts
    if EDGE_OK:
        voices = [EDGE_TR_VOICE, "tr-TR-AhmetNeural", "tr-TR-SedaNeural"] if short=="tr" else \
                 [EDGE_EN_VOICE, "en-US-AriaNeural", "en-GB-LibbyNeural"]
        try:
            asyncio.run(edge_tts_say(text, voices))
            return
        except Exception as e:
            print(f"(Edge TTS çalışmadı: {e})")
    print("(Uyarı: TTS çalıştırılamadı.)")

# ---------- STT ----------
STT_AVAILABLE = False
try:
    import speech_recognition as sr
    recognizer = sr.Recognizer()
    STT_AVAILABLE = True
except Exception:
    STT_AVAILABLE = False

def listen(lang: str = "en-US", timeout: float = 6.0, phrase_time_limit: float = 45.0) -> Optional[str]:
    if not STT_AVAILABLE:
        return None
    try:
        with sr.Microphone() as source:
            print("🎙️ Dinliyorum... (maks 45 sn)")
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        text = recognizer.recognize_google(audio, language=lang)
        print("📝 Algılanan:", text)
        return text
    except Exception as e:
        print(f"(Ses algılanamadı: {e})")
        return None

# ---------- Çeviri ----------
def translate_text(text: str, dest: str = "tr") -> str:
    try:
        from googletrans import Translator
        tr = Translator()
        res = tr.translate(text, dest=dest)
        return res.text
    except Exception:
        pass
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source="auto", target=dest).translate(text)
    except Exception as e:
        return f"(Çeviri yapılamadı: {e})"

def extract_translate_query(text: str) -> Optional[str]:
    t = text.strip()
    m = re.search(r"(?i)\bbu ne demek[: ]+(.*)", t)
    if m: return m.group(1).strip()
    m = re.search(r"(?i)\bçevir[: ]+(.*)", t)
    if m: return m.group(1).strip()
    m = re.search(r"(?i)\btranslate[: ]+(.*)", t)
    if m: return m.group(1).strip()
    return None

# ---------- Sözlük / veri ----------
B1_DEFAULTS = [
    ("achieve", "başarmak;erişmek"), ("afford", "gücü yetmek"), ("allow", "izin vermek"),
    ("although", "olmasına rağmen"), ("announce", "duyurmak;ilan etmek"),
    ("apply", "başvurmak;uygulamak"), ("arrange", "düzenlemek;ayarlamak"),
    ("attend", "katılmak;devam etmek"), ("avoid", "kaçınmak"), ("compare", "karşılaştırmak"),
    ("complain", "şikayet etmek"), ("consider", "düşünmek;göz önünde bulundurmak"),
    ("contain", "içermek"), ("continue", "devam etmek"), ("contribute", "katkıda bulunmak"),
    ("decision", "karar"), ("decrease", "azalmak;azaltmak"), ("deliver", "teslim etmek"),
    ("depend", "bağlı olmak"), ("describe", "tanımlamak;betimlemek"), ("develop", "geliştirmek"),
    ("efficient", "verimli"), ("environment", "çevre"), ("experience", "deneyim"),
    ("explain", "açıklamak"), ("improve", "iyileştirmek"), ("include", "içermek"),
    ("increase", "artmak;artırmak"), ("introduce", "tanıtmak;tanıştırmak"),
    ("involve", "içermek;dahil etmek"), ("manage", "yönetmek;başarmak"),
    ("organize", "düzenlemek"), ("participate", "katılmak"), ("perform", "sergilemek"),
    ("prefer", "tercih etmek"), ("produce", "üretmek"), ("promise", "söz vermek"),
    ("protect", "korumak"), ("purpose", "amaç"), ("quality", "kalite"),
    ("reduce", "azaltmak"), ("relationship", "ilişki"), ("remove", "kaldırmak"),
    ("reply", "yanıtlamak;yanıt"), ("require", "gerektirmek;istemek"),
    ("respect", "saygı göstermek;saygı"), ("result", "sonuç"), ("rule", "kural;yönetmek"),
    ("satisfy", "tatmin etmek"), ("solution", "çözüm"), ("support", "destek;desteklemek"),
    ("tradition", "gelenek"), ("transport", "taşımak;ulaştırma"), ("various", "çeşitli"),
    ("willing", "istekli")
]

def load_data():
    today = date.today().isoformat()
    if not os.path.exists(DATA_FILE):
        cards = [{"en": en, "tr": tr, "box": 0, "next": today, "stats": {"correct": 0, "wrong": 0}}
                 for en, tr in B1_DEFAULTS]
        save_data({"cards": cards})
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_users():
    if not os.path.exists(USER_DATA):
        with open(USER_DATA, "w", encoding="utf-8") as f:
            json.dump({"users": {}, "vocab": []}, f, ensure_ascii=False, indent=2)
    with open(USER_DATA, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(u):
    with open(USER_DATA, "w", encoding="utf-8") as f:
        json.dump(u, f, ensure_ascii=False, indent=2)

# ---------- Yardımcılar ----------
_punct_re = re.compile(r"[^\w\sçğıöşüÇĞİÖŞÜ/-]")
def normalize(s: str) -> str:
    s = s.strip().lower()
    s = _punct_re.sub("", s)
    s = re.sub(r"\s+", " ", s)
    return s

def matches(user: str, correct: str) -> bool:
    import difflib
    u = normalize(user)
    variants = [normalize(x) for x in re.split(r"[;/]", correct)]
    if u in variants:
        return True
    best = max(difflib.SequenceMatcher(None, u, v).ratio() for v in variants) if variants else 0
    return best >= 0.80

def due_cards(cards):
    today = date.today().isoformat()
    return [c for c in cards if c["next"] <= today]

def schedule(card, is_correct: bool):
    i = max(0, min(card.get("box", 0), len(INTERVALS) - 1))
    if is_correct:
        i = min(i + 1, len(INTERVALS) - 1); card["stats"]["correct"] += 1
    else:
        i = max(i - 1, 0); card["stats"]["wrong"] += 1
    card["box"] = i
    ndays = INTERVALS[i]
    card["next"] = (date.today() + timedelta(days=ndays)).isoformat()

def input_int(prompt, low, high):
    while True:
        try:
            v = int(input(prompt))
            if low <= v <= high:
                return v
        except Exception:
            pass
        print(f"Lütfen {low}-{high} arasında bir sayı girin.")

def add_word(data):
    en = input("İngilizce: ").strip()
    tr = input("Türkçe (alternatifleri ; ile ayır): ").strip()
    data["cards"].append({"en": en, "tr": tr, "box": 0, "next": date.today().isoformat(),
                          "stats": {"correct": 0, "wrong": 0}})
    save_data(data); print(f'✓ Eklendi: "{en}" ↔ "{tr}"')

def show_stats(data):
    cards = data["cards"]; total = len(cards); due = len(due_cards(cards))
    corr = sum(c["stats"]["correct"] for c in cards)
    wrong = sum(c["stats"]["wrong"] for c in cards)
    by_box = {}
    for c in cards: by_box[c["box"]] = by_box.get(c["box"], 0) + 1
    total_attempts = corr + wrong
    acc = (corr / total_attempts * 100) if total_attempts else 0.0
    print("\n--- İstatistikler ---")
    print(f"Toplam kart: {total} | Bugün due: {due}")
    print("Kutu dağılımı:", ", ".join(f"Box {k}:{v}" for k,v in sorted(by_box.items())) or "—")
    print(f"Toplam doğruluk: {acc:.1f}%  (Doğru: {corr}, Yanlış: {wrong})\n")

# ---------- Quiz (Metin) ----------
def ask_type(card, mode="mix"):
    if mode == "en2tr":
        q, a, label = card["en"], card["tr"], "(EN→TR)"
    elif mode == "tr2en":
        q, a, label = card["tr"], card["en"], "(TR→EN)"
    else:
        if random.random() < 0.5:
            q, a, label = card["en"], card["tr"], "(EN→TR)"
        else:
            q, a, label = card["tr"], card["en"], "(TR→EN)"
    print(f"{label}  Soru: {q}")
    ans = input("Cevap (boş=bilmiyorum): ")
    if not ans.strip():
        print(f"↳ Doğru: {a}"); schedule(card, False); return False
    ok = matches(ans, a)
    print("✓ Doğru!" if ok else f"✗ Yanlış. Doğrusu: {a}")
    schedule(card, ok); return ok

def ask_mcq(card, pool, mode="mix", k=4):
    others = [c for c in pool if c is not card]; random.shuffle(others)
    if mode == "en2tr":
        q, a = card["en"], card["tr"]; distractors=[c["tr"] for c in others[:k-1]]; label="(EN→TR)"
    elif mode == "tr2en":
        q, a = card["tr"], card["en"]; distractors=[c["en"] for c in others[:k-1]]; label="(TR→EN)"
    else:
        if random.random() < 0.5:
            q, a = card["en"], card["tr"]; distractors=[c["tr"] for c in others[:k-1]]; label="(EN→TR)"
        else:
            q, a = card["tr"], card["en"]; distractors=[c["en"] for c in others[:k-1]]; label="(TR→EN)"
    opts = distractors + [a]; random.shuffle(opts)
    print(f"{label}  Soru: {q}")
    for i,opt in enumerate(opts,1): print(f"  {i}) {opt}")
    ch = input(f"Seçimin (1-{len(opts)}) / Enter=bilmiyorum: ").strip()
    if not ch:
        print(f"↳ Doğru: {a}"); schedule(card, False); return False
    try:
        idx = int(ch) - 1; ok = matches(opts[idx], a)
    except Exception:
        ok = False
    print("✓ Doğru!" if ok else f"✗ Yanlış. Doğrusu: {a}")
    schedule(card, ok); return ok

# ---------- Quiz (Sesli) ----------
def ask_type_voice(card, mode="mix", tr_voice=False):
    if mode == "en2tr":
        q, a, label, speak_lang = card["en"], card["tr"], "(EN→TR)", "en"
    elif mode == "tr2en":
        q, a, label, speak_lang = card["tr"], card["en"], "(TR→EN)", "tr"
    else:
        if random.random() < 0.5:
            q, a, label, speak_lang = card["en"], card["tr"], "(EN→TR)", "en"
        else:
            q, a, label, speak_lang = card["tr"], card["en"], "(TR→EN)", "tr"
    print(f"{label}  Soru: {q}")
    tr_show = translate_text(q, dest="tr") if speak_lang=="en" else translate_text(q, dest="en")
    print("↳ Yardımcı çeviri:", tr_show)
    speak(q, lang=speak_lang)
    if tr_voice:
        speak(tr_show, lang="tr" if speak_lang=="en" else "en")
    ans = listen(lang="en-US" if label=="(EN→TR)" else "tr-TR") or input("Cevap (boş=bilmiyorum): ")
    ans = ans.strip()
    if not ans:
        print(f"↳ Doğru: {a}"); schedule(card, False); return False
    qtext = extract_translate_query(ans)
    if qtext:
        dest = "en" if re.search(r"[ğüşöçıİĞÜŞÖÇ]", qtext) else "tr"
        translated = translate_text(qtext, dest=dest)
        print("Çeviri:", translated); speak(translated, "tr" if dest=="tr" else "en")
        add = input("Sözlüğe ekleyeyim mi? (y/n): ").lower().strip()
        if add == "y":
            d = load_data()
            if dest == "tr": en, tr = qtext, translated
            else: en, tr = translated, qtext
            d["cards"].append({"en": en, "tr": tr, "box": 0,
                               "next": date.today().isoformat(),
                               "stats": {"correct": 0, "wrong": 0}})
            save_data(d); print("✓ Sözlüğe kaydedildi.")
        schedule(card, False); return False
    ok = matches(ans, a)
    print("✓ Doğru!" if ok else f"✗ Yanlış. Doğrusu: {a}")
    schedule(card, ok); return ok

def ask_mcq_voice(card, pool, mode="mix", k=4, tr_voice=False):
    others = [c for c in pool if c is not card]; random.shuffle(others)
    if mode == "en2tr":
        q, a = card["en"], card["tr"]; distractors=[c["tr"] for c in others[:k-1]]; label="(EN→TR)"; sl="en"
    elif mode == "tr2en":
        q, a = card["tr"], card["en"]; distractors=[c["en"] for c in others[:k-1]]; label="(TR→EN)"; sl="tr"
    else:
        if random.random() < 0.5:
            q, a, sl, label = card["en"], card["tr"], "en", "(EN→TR)"
        else:
            q, a, sl, label = card["tr"], card["en"], "tr", "(TR→EN)"
        distractors = [ (c["tr"] if sl=="en" else c["en"]) for c in others[:k-1] ]
    opts = distractors + [a]; random.shuffle(opts)
    print(f"{label}  Soru: {q}")
    tr_show = translate_text(q, dest="tr" if sl=="en" else "en")
    print("↳ Yardımcı çeviri:", tr_show)
    speak(q, lang=sl)
    if tr_voice:
        speak(tr_show, lang="tr" if sl=="en" else "en")
    for i,opt in enumerate(opts,1): print(f"  {i}) {opt}")
    heard = listen(lang="tr-TR", phrase_time_limit=3.0)
    if heard:
        m = re.search(r"\b(1|2|3|4|bir|iki|üç|üc|uc|dört|dort)\b", heard.lower())
        mapping = {"bir":"1","iki":"2","üç":"3","üc":"3","uc":"3","dört":"4","dort":"4"}
        choice = mapping.get(m.group(1), m.group(1)) if m else None
    else:
        choice = None
    if not choice:
        choice = input(f"Seçimin (1-{len(opts)}) / Enter=bilmiyorum: ").strip()
    if not choice:
        print(f"↳ Doğru: {a}"); schedule(card, False); return False
    try:
        idx = int(choice)-1; ok = matches(opts[idx], a)
    except Exception:
        ok = False
    print("✓ Doğru!" if ok else f"✗ Yanlış. Doğrusu: {a}")
    schedule(card, ok); return ok

# ---------- Study flows ----------
def study_text(data):
    cards = data["cards"]
    if not cards: print("Önce kelime ekleyin."); return
    print("\n--- Çalışma (Metin) ---")
    print("1) EN→TR   2) TR→EN   3) Karışık")
    mode = {1:"en2tr",2:"tr2en",3:"mix"}[input_int("Seçim: ",1,3)]
    print("1) Yazmalı   2) Çoktan seçmeli (MCQ)")
    style = {1:"type",2:"mcq"}[input_int("Seçim: ",1,2)]
    due = due_cards(cards) or cards[:]; random.shuffle(due)
    total=len(due); correct=0
    for i,card in enumerate(due,1):
        print(f"\n[{i}/{total}] {'-'*40}")
        ok = ask_type(card, mode) if style=="type" else ask_mcq(card, cards, mode, 4)
        correct += int(ok); save_data(data)
    print(f"\nOturum bitti. Doğru: {correct}/{total}")
    show_stats(data)

def study_voice(data):
    cards = data["cards"]
    if not cards: print("Önce kelime ekleyin."); return
    print("\n--- Çalışma (Sesli) ---")
    print("1) EN→TR   2) TR→EN   3) Karışık")
    mode = {1:"en2tr",2:"tr2en",3:"mix"}[input_int("Seçim: ",1,3)]
    tr_voice = input("Sorular Türkçe de okunsun mu? (e/h): ").strip().lower().startswith("e")
    print("1) Yazmalı benzeri  2) Çoktan seçmeli (sesle numara seçimi destekli)")
    style = {1:"type",2:"mcq"}[input_int("Seçim: ",1,2)]
    due = due_cards(cards) or cards[:]; random.shuffle(due)
    total=len(due); correct=0
    for i,card in enumerate(due,1):
        print(f"\n[{i}/{total}] {'-'*40}")
        if style=="type":
            ok = ask_type_voice(card, mode, tr_voice=tr_voice)
        else:
            ok = ask_mcq_voice(card, cards, mode, 4, tr_voice=tr_voice)
        correct += int(ok); save_data(data)
    print(f"\nOturum bitti. Doğru: {correct}/{total}")
    show_stats(data)

# ---------- Konuşma (B1) ----------
QUESTIONS_B1 = [
    "What do you usually do on weekends?",
    "Tell me about a hobby you enjoy and why you like it.",
    "Describe a place in your city that you recommend visiting.",
    "What are the advantages and disadvantages of online learning?",
    "What is a personal goal you want to achieve this year, and how will you do it?",
    "Do you prefer reading books or watching movies? Explain your choice.",
    "Tell me about a challenge you faced and how you solved it.",
]

def input_int(prompt, low, high):
    while True:
        try:
            v = int(input(prompt))
            if low <= v <= high:
                return v
        except Exception:
            pass
        print(f"Lütfen {low}-{high} arasında bir sayı girin.")

def user_rec(users, name):
    u = users["users"].get(name.lower())
    if not u:
        u = {"name": name, "sessions": 0, "turns": 0, "words": 0, "last_seen": None}
        users["users"][name.lower()] = u
    return u

def load_users():
    if not os.path.exists(USER_DATA):
        with open(USER_DATA, "w", encoding="utf-8") as f:
            json.dump({"users": {}, "vocab": []}, f, ensure_ascii=False, indent=2)
    with open(USER_DATA, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(u):
    with open(USER_DATA, "w", encoding="utf-8") as f:
        json.dump(u, f, ensure_ascii=False, indent=2)

def show_two_stats(users, name, session):
    u = user_rec(users, name)
    print("\n--- Oturum İstatistikleri ---")
    print(f"Sorulan soru : {session['questions']}")
    print(f"Yanıt sayısı : {session['answers']}")
    print(f"Toplam kelime: {session['words']}")
    avg = session['words']/max(1,session['answers'])
    print(f"Ort. kelime/yanıt: {avg:.1f}")
    print("\n--- Tüm Zamanlar (", u['name'], ") ---", sep="")
    print(f"Toplam oturum : {u['sessions']}")
    print(f"Toplam sıra   : {u['turns']}")
    print(f"Toplam kelime : {u['words']}")
    avg2 = u['words']/max(1,u['turns'])
    print(f"Ort. kelime/yanıt: {avg2:.1f}")
    print(f"Son görüldüğü: {u['last_seen']}")

def conversation_b1(username: str):
    users = load_users()
    u = user_rec(users, username)
    u["sessions"] += 1
    u["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    save_users(users)

    greet = f"Hi {username}! We'll practice speaking. I'll also show Turkish translations."
    print("🤖:", greet); speak(greet, "en")

    session = {"questions":0,"answers":0,"words":0}
    print("Komutlar: quit | istatistikleri göster | add: en = tr | bu ne demek/çevir/translate ...")

    while True:
        q = random.choice(QUESTIONS_B1)
        tr_q = translate_text(q, dest="tr")
        print("\n🤖 Question:", q, "\n↳ Türkçe:", tr_q)
        speak(q, "en"); speak(tr_q, "tr")
        session["questions"] += 1

        user = listen("en-US", phrase_time_limit=45.0) or input("Cevabınız: ")
        user_s = user.strip()
        print("🧑:", user_s if user_s else "(boş)")

        low = user_s.lower()
        if low in ("quit","exit","q"):
            bye = "Great job today. See you next time!"
            print("🤖:", bye); speak(bye, "en"); break
        if low in ("istatistikleri göster","show stats","stats"):
            show_two_stats(users, username, session); continue
        if low.startswith("add:"):
            m = re.match(r"add:\s*(.+?)\s*=\s*(.+)", user_s, flags=re.I)
            if m:
                vocab = load_data()
                vocab["cards"].append({"en": m.group(1).strip(), "tr": m.group(2).strip(),
                                       "box":0,"next":date.today().isoformat(),
                                       "stats":{"correct":0,"wrong":0}})
                save_data(vocab); print("✓ Eklendi.")
            else:
                print("Biçim: add: english = türkçe")
            continue
        qtext = extract_translate_query(user_s)
        if qtext:
            dest = "en" if re.search(r"[ğüşöçıİĞÜŞÖÇ]", qtext) else "tr"
            translated = translate_text(qtext, dest=dest)
            print("Çeviri:", translated); speak(translated, "tr" if dest=="tr" else "en")
            continue

        wc = len(user_s.split())
        session["answers"] += 1; session["words"] += wc
        u["turns"] += 1; u["words"] += wc; save_users(users)

        fb = "Daha fazla detay ekleyebilirsin." if wc<8 else ("Güzel ve anlaşılır." if wc<20 else "Harika, detaylı!")
        print("🤖:", fb); speak(fb, "tr")

# ---------- Reset ----------
def reset_progress(data):
    for c in data["cards"]:
        c["box"] = 0
        c["next"] = date.today().isoformat()
        c["stats"] = {"correct": 0, "wrong": 0}
    save_data(data); print("✓ İlerleme sıfırlandı.")

# ---------- Main ----------
def main():
    print("="*74)
    print(" İngilizce Çalışma — Quiz + SRS + Ses + Çeviri + Konuşma (B1) ")
    print("="*74)

    username = input("Lütfen adınızı yazın: ").strip() or "guest"
    if username.lower() == "sude":
        msg = ("Hoş geldiniz Sude Hanım. Fatih size çok aşık; sizi çok seviyor. "
               "Beraber mutlu ve huzurlu olmanız için çalışıyor.")
        print("🤖:", msg); speak(msg, "tr")

    data = load_data()
    while True:
        print("\nMenü:")
        print("1) Çalış (Metin)")
        print("2) Çalış (Sesli)")
        print("3) Kelime ekle")
        print("4) İstatistikleri göster")
        print("5) B1 Karşılıklı Konuşma (Sesli)")
        print("6) İlerlemeyi sıfırla")
        print("0) Çıkış")
        ch = input("Seçimin: ").strip()
        if ch == "1": study_text(data)
        elif ch == "2": study_voice(data)
        elif ch == "3": add_word(data)
        elif ch == "4": show_stats(data)
        elif ch == "5": conversation_b1(username)
        elif ch == "6": reset_progress(data)
        elif ch == "0":
            print("Görüşürüz!"); break
        else:
            print("Geçersiz seçim.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nÇıkılıyor...")
