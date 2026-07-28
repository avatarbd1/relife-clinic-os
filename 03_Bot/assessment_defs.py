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
"""

MMT_OPTIONS = ["0", "1", "2", "3", "4", "5"]
DERMATOME_OPTIONS = ["Normal", "Reduced", "Absent"]
REFLEX_OPTIONS = ["Normal", "Diminished", "Absent", "Exaggerated"]
YESNO_OPTIONS = ["Yes", "No"]
POSNEG_OPTIONS = ["+ve", "-ve"]
VAS_OPTIONS = [str(n) for n in range(0, 11)]


def _mmt(key, label):
    return {"key": key, "label": f"MMT — {label}", "type": "buttons", "options": MMT_OPTIONS}


def _dermatome(key, label):
    return {"key": key, "label": f"Dermatome — {label}", "type": "buttons", "options": DERMATOME_OPTIONS}


def _reflex(key, label):
    return {"key": key, "label": f"Reflex — {label}", "type": "buttons", "options": REFLEX_OPTIONS}


def _posneg(key, label):
    return {"key": key, "label": label, "type": "buttons", "options": POSNEG_OPTIONS}


def _text(key, label):
    return {"key": key, "label": label, "type": "text"}


PAIN_VAS = {"key": "Pain_VAS", "label": "ব্যথার মাত্রা (Pain VAS, 0-10)", "type": "buttons", "options": VAS_OPTIONS}


ASSESSMENT_CATEGORIES = {
    "lbp": {
        "label": "🦴 Low Back Pain / PLID / Sciatica",
        "tests": [
            _text("SLR", "SLR — পাশ ও ডিগ্রি লেখো (যেমন: Right 40°)"),
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
            _text("Lumbar_ROM", "Lumbar ROM লেখো"),
            PAIN_VAS,
        ],
    },
    "neck": {
        "label": "🧠 Neck Pain / Cervical Radiculopathy",
        "tests": [
            _posneg("Spurling", "Spurling's Test"),
            _mmt("MMT_ShoulderAbd", "Shoulder Abduction"),
            _mmt("MMT_ElbowFlex", "Elbow Flexion"),
            _mmt("MMT_ElbowExt", "Elbow Extension"),
            _mmt("MMT_WristExt", "Wrist Extension"),
            _dermatome("Dermatome_C5", "C5"),
            _dermatome("Dermatome_C6", "C6"),
            _dermatome("Dermatome_C7", "C7"),
            _text("Cervical_ROM", "Cervical ROM লেখো"),
            PAIN_VAS,
        ],
    },
    "shoulder": {
        "label": "💪 Shoulder (Frozen/Rotator Cuff)",
        "tests": [
            _text("ROM_Flexion", "ROM — Flexion লেখো"),
            _text("ROM_Abduction", "ROM — Abduction লেখো"),
            _text("ROM_IR", "ROM — Internal Rotation লেখো"),
            _text("ROM_ER", "ROM — External Rotation লেখো"),
            _posneg("Neers", "Neer's Test"),
            _posneg("Hawkins", "Hawkins-Kennedy Test"),
            _posneg("EmptyCan", "Empty Can Test"),
            _mmt("MMT_Supraspinatus", "Supraspinatus"),
            _mmt("MMT_Deltoid", "Deltoid"),
            PAIN_VAS,
        ],
    },
    "knee": {
        "label": "🦵 Knee (OA/Ligament/Post-op)",
        "tests": [
            _text("ROM_Flexion", "ROM — Flexion লেখো"),
            _text("ROM_Extension", "ROM — Extension লেখো"),
            _posneg("Lachman", "Lachman Test"),
            _posneg("McMurray", "McMurray Test"),
            _posneg("ValgusVarus", "Valgus/Varus Stress Test"),
            _mmt("MMT_Quad", "Quadriceps"),
            _mmt("MMT_Hamstring", "Hamstring"),
            {"key": "Swelling", "label": "Swelling আছে কি?", "type": "buttons", "options": YESNO_OPTIONS},
            PAIN_VAS,
        ],
    },
    "neuro": {
        "label": "🧑‍⚕️ Stroke / Neuro",
        "tests": [
            {"key": "Tone", "label": "Tone (Modified Ashworth)", "type": "buttons",
             "options": ["0", "1", "1+", "2", "3", "4"]},
            _mmt("MMT_UpperLimb", "Upper Limb (Affected Side)"),
            _mmt("MMT_LowerLimb", "Lower Limb (Affected Side)"),
            {"key": "Balance", "label": "Balance Status", "type": "buttons",
             "options": ["Good", "Fair", "Poor"]},
            {"key": "Functional_Mobility", "label": "Functional Mobility", "type": "buttons",
             "options": ["Independent", "Assisted", "Dependent"]},
        ],
    },
    "postop": {
        "label": "🩹 Post-Fracture / Post-Op Ortho",
        "tests": [
            _text("ROM", "ROM লেখো"),
            {"key": "Swelling", "label": "Swelling আছে কি?", "type": "buttons", "options": YESNO_OPTIONS},
            {"key": "WeightBearing", "label": "Weight-Bearing Status", "type": "buttons",
             "options": ["Full", "Partial", "Non"]},
            PAIN_VAS,
        ],
    },
    "general": {
        "label": "📋 General / Others",
        "tests": [
            _text("ChiefComplaint", "Chief Complaint লেখো"),
            _text("ROM", "ROM (আক্রান্ত জয়েন্ট) লেখো"),
            PAIN_VAS,
        ],
    },
}

CATEGORY_ORDER = ["lbp", "neck", "shoulder", "knee", "neuro", "postop", "general"]
