"""
assessment_defs.py
চিফ কমপ্লেইন্ট ক্যাটাগরি এবং প্রতিটার জন্য নির্দিষ্ট প্রাথমিক মূল্যায়ন (assessment) টেস্ট-লিস্ট।
tplan (ট্রিটমেন্ট প্ল্যান) ফ্লো-তে রোগী বাছাইয়ের পর এই লিস্ট অনুযায়ী এক-এক করে
বাটন/টেক্সট প্রশ্ন পাঠানো হয় — bot.py-এর generic queue-engine এটা ব্যবহার করে।

প্রতিটা টেস্ট একটা dict:
  key     -> শীটে সেভ হওয়া ছোট নাম (ইউনিক, ইংরেজি/সংখ্যা)
  label   -> টেলিগ্রামে যা দেখানো হবে
  type    -> "buttons" অথবা "text"
  options -> শুধু "buttons" টাইপে লাগবে
  info    -> (ঐচ্ছিক) normal range / কীভাবে মাপবে/করবে — "ℹ️" বাটনে popup হিসেবে দেখানো হয়
             (Telegram popup-এর ক্যারেক্টার লিমিট আছে, তাই সংক্ষিপ্ত রাখা হয়েছে)
"""

MMT_OPTIONS = ["0", "1", "2", "3", "4", "5"]
DERMATOME_OPTIONS = ["Normal", "Reduced", "Absent"]
REFLEX_OPTIONS = ["Normal", "Diminished", "Absent", "Exaggerated"]
YESNO_OPTIONS = ["Yes", "No"]
POSNEG_OPTIONS = ["+ve", "-ve"]
VAS_OPTIONS = [str(n) for n in range(0, 11)]

MMT_SCALE_INFO = (
    "MMT (Oxford) Scale: 0=নড়াচড়া নেই, 1=flicker, 2=gravity বাদে full ROM, "
    "3=gravity বিরুদ্ধে full ROM, 4=কিছু resistance-এ full ROM, 5=normal strength"
)

DERMATOME_AREA = {
    "L4": "হাঁটুর মধ্যভাগ/শিন", "L5": "পায়ের উপরিভাগ/বৃদ্ধাঙ্গুলি",
    "S1": "পায়ের বাইরের দিক/তলা",
    "C5": "কাঁধের বাইরের দিক", "C6": "বৃদ্ধাঙ্গুলি", "C7": "মধ্যমা আঙুল",
}

REFLEX_SEGMENT = {"Knee Jerk": "L3-L4", "Ankle Jerk": "S1-S2"}


def _mmt(key, label):
    return {"key": key, "label": f"MMT — {label}", "type": "buttons",
            "options": MMT_OPTIONS, "info": MMT_SCALE_INFO}


def _dermatome(key, label):
    area = DERMATOME_AREA.get(label, "")
    info = f"Dermatome {label}: sensation চেক করো {area} অংশে" if area else None
    return {"key": key, "label": f"Dermatome — {label}", "type": "buttons",
            "options": DERMATOME_OPTIONS, "info": info}


def _reflex(key, label):
    seg = REFLEX_SEGMENT.get(label, "")
    info = f"{label}: nerve root {seg}। ট্যাপ করো tendon-এ, প্রতিক্রিয়া দেখো" if seg else None
    return {"key": key, "label": f"Reflex — {label}", "type": "buttons",
            "options": REFLEX_OPTIONS, "info": info}


def _posneg(key, label, info=None):
    return {"key": key, "label": label, "type": "buttons", "options": POSNEG_OPTIONS, "info": info}


def _text(key, label, info=None):
    return {"key": key, "label": label, "type": "text", "info": info}


PAIN_VAS = {
    "key": "Pain_VAS", "label": "ব্যথার মাত্রা (Pain VAS, 0-10)", "type": "buttons",
    "options": VAS_OPTIONS, "info": "0=ব্যথা নেই, 10=সবচেয়ে বেশি ব্যথা কল্পনাযোগ্য",
}


ASSESSMENT_CATEGORIES = {
    "lbp": {
        "label": "🦴 Low Back Pain / PLID / Sciatica",
        "tests": [
            _text("SLR", "SLR — পাশ ও ডিগ্রি লেখো (যেমন: Right 40°)",
                  "Normal: pain-free ~80-90°। 30-70°-এর মধ্যে ব্যথা হলে +ve (neural tension)"),
            _mmt("MMT_HipFlexor", "Hip Flexor"),
            _mmt("MMT_KneeExt", "Knee Extensor"),
            _mmt("MMT_AnkleDorsi", "Ankle Dorsiflexor"),
            _mmt("MMT_EHL", "EHL"),
            _mmt("MMT_AnklePlantar", "Ankle Plantarflexor"),
            _dermatome("Dermatome_L4", "L4"),
            _dermatome("Dermatome_L5", "L5"),
            _dermatome("Dermatome_S1", "S1"),
            _reflex("Reflex_Knee", "Knee Jerk"),
            _reflex("Reflex_Ankle", "Ankle Jerk"),
            _text("Lumbar_ROM", "Lumbar ROM লেখো",
                  "Normal: Flexion 40-60°, Extension 20-35°, Lateral flex 15-20°, Rotation 3-18°"),
            PAIN_VAS,
        ],
    },
    "neck": {
        "label": "🧠 Neck Pain / Cervical Radiculopathy",
        "tests": [
            _posneg("Spurling", "Spurling's Test",
                    "মাথা affected দিকে কাত+extension+axial compression। +ve হলে radicular pain reproduce হয়"),
            _mmt("MMT_ShoulderAbd", "Shoulder Abduction"),
            _mmt("MMT_ElbowFlex", "Elbow Flexion"),
            _mmt("MMT_ElbowExt", "Elbow Extension"),
            _mmt("MMT_WristExt", "Wrist Extension"),
            _dermatome("Dermatome_C5", "C5"),
            _dermatome("Dermatome_C6", "C6"),
            _dermatome("Dermatome_C7", "C7"),
            _text("Cervical_ROM", "Cervical ROM লেখো",
                  "Normal: Flexion 45-50°, Extension 55-60°, Lateral flex 40-45°, Rotation 70-90°"),
            PAIN_VAS,
        ],
    },
    "shoulder": {
        "label": "💪 Shoulder (Frozen/Rotator Cuff)",
        "tests": [
            _text("ROM_Flexion", "ROM — Flexion লেখো",
                  "Normal: 0-180°। Goniometer: acromion-এ axis, humerus বরাবর arm"),
            _text("ROM_Abduction", "ROM — Abduction লেখো",
                  "Normal: 0-180°। Goniometer: acromion-এ axis, coronal plane-এ measure"),
            _text("ROM_IR", "ROM — Internal Rotation লেখো",
                  "Normal: ~70°। 90° abduction position-এ measure করা সবচেয়ে নির্ভরযোগ্য"),
            _text("ROM_ER", "ROM — External Rotation লেখো",
                  "Normal: ~90°। কনুই ৯০° বাঁকা রেখে, শরীরের পাশে রেখে measure করো"),
            _posneg("Neers", "Neer's Test",
                    "Scapula স্থির রেখে shoulder পূর্ণ passive flexion করাও। +ve হলে ব্যথা = impingement"),
            _posneg("Hawkins", "Hawkins-Kennedy Test",
                    "কনুই ৯০°, shoulder ৯০° flex করে জোরে internal rotation করাও। +ve = impingement"),
            _posneg("EmptyCan", "Empty Can Test",
                    "৯০° abduction, ৩০° horizontal flex, thumb নিচে করে resist করাও। দুর্বলতা/ব্যথা = supraspinatus tear/impingement"),
            _mmt("MMT_Supraspinatus", "Supraspinatus"),
            _mmt("MMT_Deltoid", "Deltoid"),
            PAIN_VAS,
        ],
    },
    "knee": {
        "label": "🦵 Knee (OA/Ligament/Post-op)",
        "tests": [
            _text("ROM_Flexion", "ROM — Flexion লেখো", "Normal: 0-135°/150°"),
            _text("ROM_Extension", "ROM — Extension লেখো", "Normal: 0° (কারো কারো 5-10° hyperextension স্বাভাবিক)"),
            _posneg("Lachman", "Lachman Test",
                    "হাঁটু ২০-৩০° flex, femur স্থির রেখে tibia সামনে টানো। বেশি excursion/soft end-feel = ACL tear"),
            _posneg("McMurray", "McMurray Test",
                    "হাঁটু পূর্ণ flex করে tibia-তে rotation দিয়ে ধীরে extend করো। click/pain = meniscus tear"),
            _posneg("ValgusVarus", "Valgus/Varus Stress Test",
                    "হাঁটু ৩০° flex করে পাশ থেকে চাপ দাও। Valgus laxity=MCL, Varus laxity=LCL injury"),
            _mmt("MMT_Quad", "Quadriceps"),
            _mmt("MMT_Hamstring", "Hamstring"),
            {"key": "Swelling", "label": "Swelling আছে কি?", "type": "buttons", "options": YESNO_OPTIONS, "info": None},
            PAIN_VAS,
        ],
    },
    "neuro": {
        "label": "🧑‍⚕️ Stroke / Neuro",
        "tests": [
            {"key": "Tone", "label": "Tone (Modified Ashworth)", "type": "buttons",
             "options": ["0", "1", "1+", "2", "3", "4"],
             "info": "0=বৃদ্ধি নেই, 1=সামান্য catch, 1+=অর্ধেকের কম ROM-এ resistance, 2=বেশিরভাগ ROM-এ বৃদ্ধি, 3=passive movement কঠিন, 4=rigid"},
            _mmt("MMT_UpperLimb", "Upper Limb (Affected Side)"),
            _mmt("MMT_LowerLimb", "Lower Limb (Affected Side)"),
            {"key": "Balance", "label": "Balance Status", "type": "buttons",
             "options": ["Good", "Fair", "Poor"], "info": None},
            {"key": "Functional_Mobility", "label": "Functional Mobility", "type": "buttons",
             "options": ["Independent", "Assisted", "Dependent"], "info": None},
        ],
    },
    "postop": {
        "label": "🩹 Post-Fracture / Post-Op Ortho",
        "tests": [
            _text("ROM", "ROM লেখো", "সংশ্লিষ্ট জয়েন্টের normal range-এর সাথে তুলনা করো (surgeon protocol অনুযায়ী restriction থাকতে পারে)"),
            {"key": "Swelling", "label": "Swelling আছে কি?", "type": "buttons", "options": YESNO_OPTIONS, "info": None},
            {"key": "WeightBearing", "label": "Weight-Bearing Status", "type": "buttons",
             "options": ["Full", "Partial", "Non"], "info": None},
            PAIN_VAS,
        ],
    },
    "general": {
        "label": "📋 General / Others",
        "tests": [
            _text("ChiefComplaint", "Chief Complaint লেখো"),
            _text("ROM", "ROM (আক্রান্ত জয়েন্ট) লেখো", "সংশ্লিষ্ট জয়েন্টের normal range-এর সাথে তুলনা করো"),
            PAIN_VAS,
        ],
    },
}

CATEGORY_ORDER = ["lbp", "neck", "shoulder", "knee", "neuro", "postop", "general"]

# প্রতিটা টেস্টের key -> info, একবার বানিয়ে রাখা হলো যাতে bot.py সরাসরি lookup করতে পারে
TEST_INFO_BY_KEY = {
    test["key"]: test["info"]
    for cat in ASSESSMENT_CATEGORIES.values()
    for test in cat["tests"]
    if test.get("info")
}
