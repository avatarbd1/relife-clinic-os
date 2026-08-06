"""
learning/tip_bank.py
Daily Learning Engine — টিপ ব্যাংক।

SHARED_TIPS: সব স্টাফ দেখতে পারে।
ROLE_TIPS: শুধু নির্দিষ্ট রোল (roles.Role) দেখতে পারে — Owner/Therapist/Receptionist/Manager।

V1 নোট: বর্তমানে ২টা ক্যাটেগরি (Patient Communication, Teamwork) আছে।
বাকি ক্যাটেগরি (Professional Behaviour, Infection Control, Clinic Cleanliness,
Documentation, Patient Safety, Ethics, Time Management, Machine Care) পরে একই
প্যাটার্নে SHARED_TIPS লিস্টে যোগ হবে — id নাম্বারিং চালিয়ে যেতে হবে (T021, T022, ...)।
"""

SHARED_TIPS = [
    # --- Patient Communication ---
    {"id": "T001", "category": "Patient Communication",
     "text": "রোগীর কথা মন দিয়ে শোনা তার চিকিৎসার প্রথম ধাপ — উত্তর দেওয়ার আগে পুরোটা শুনুন।"},
    {"id": "T002", "category": "Patient Communication",
     "text": "রোগীর সামনে সবসময় \"আপনি\" বলে সম্বোধন করুন, যতই পরিচিত হোক না কেন।"},
    {"id": "T003", "category": "Patient Communication",
     "text": "জটিল মেডিকেল শব্দ এড়িয়ে সহজ ভাষায় বুঝিয়ে বলুন, রোগী বুঝলে বিশ্বাস বাড়ে।"},
    {"id": "T004", "category": "Patient Communication",
     "text": "রোগী ব্যথার কথা বললে সেটাকে ছোট করে দেখবেন না — প্রথমে স্বীকার করুন, তারপর ব্যাখ্যা দিন।"},
    {"id": "T005", "category": "Patient Communication",
     "text": "প্রতিটা ভিজিটে অন্তত একবার জিজ্ঞেস করুন \"আজ কেমন লাগছে?\" — এটা যত্নের অনুভূতি দেয়।"},
    {"id": "T006", "category": "Patient Communication",
     "text": "চোখে চোখ রেখে কথা বলুন — ফোনের দিকে তাকিয়ে কথা বললে রোগী গুরুত্ব কম পাচ্ছে মনে করে।"},
    {"id": "T007", "category": "Patient Communication",
     "text": "রোগী রাগান্বিত হলে প্রথমে শান্তভাবে শুনুন, সাথে সাথে তর্ক করবেন না।"},
    {"id": "T008", "category": "Patient Communication",
     "text": "চিকিৎসার খরচ ও সময়কাল শুরুতেই স্পষ্ট করে বলুন, পরে যেন সারপ্রাইজ না হয়।"},
    {"id": "T009", "category": "Patient Communication",
     "text": "রোগীর প্রাইভেসি রক্ষা করুন — অন্য রোগীর সামনে কারো তথ্য বলবেন না।"},
    {"id": "T010", "category": "Patient Communication",
     "text": "চিকিৎসা শেষে সংক্ষেপে বলুন পরের ধাপে কী হবে — রোগী নিশ্চিন্ত থাকে।"},

    # --- Teamwork ---
    {"id": "T011", "category": "Teamwork",
     "text": "সহকর্মী ব্যস্ত থাকলে নিজে থেকে এগিয়ে সাহায্য করুন, বলার অপেক্ষা করবেন না।"},
    {"id": "T012", "category": "Teamwork",
     "text": "কাজ হস্তান্তরের সময় (হ্যান্ডওভার) মৌখিকভাবে বুঝিয়ে দিন, শুধু \"হয়ে গেছে\" বললে চলবে না।"},
    {"id": "T013", "category": "Teamwork",
     "text": "মতবিরোধ হলে রোগীর সামনে নয়, আড়ালে শান্তভাবে আলোচনা করুন।"},
    {"id": "T014", "category": "Teamwork",
     "text": "অন্যের কাজে ভুল দেখলে সরাসরি ও বিনয়ের সাথে বলুন, পেছনে আলোচনা না করে।"},
    {"id": "T015", "category": "Teamwork",
     "text": "প্রতিদিন কাজ শুরুর আগে নিজের ও দলের পরিকল্পনা একবার ঝালিয়ে নিন।"},
    {"id": "T016", "category": "Teamwork",
     "text": "কারো অনুপস্থিতিতে তার জরুরি কাজ কে সামলাবে তা আগে থেকেই ঠিক রাখুন।"},
    {"id": "T017", "category": "Teamwork",
     "text": "ছোট প্রশংসা করতে কার্পণ্য করবেন না — এতে দলের মনোবল বাড়ে।"},
    {"id": "T018", "category": "Teamwork",
     "text": "নিজের ভুল স্বীকার করতে দ্বিধা করবেন না, এতে বিশ্বাস তৈরি হয়।"},
    {"id": "T019", "category": "Teamwork",
     "text": "তথ্য শুধু মুখে না রেখে বটে/খাতায় লিখে রাখুন, যেন অন্যরাও দেখতে পারে।"},
    {"id": "T020", "category": "Teamwork",
     "text": "\"এটা আমার কাজ না\" না বলে বলুন — \"আমি দেখি কীভাবে সাহায্য করতে পারি।\""},
]

# রোল কী roles.Role এর ভ্যালুর সাথে মিলতে হবে: "Owner" | "Therapist" | "Receptionist" | "Manager"
ROLE_TIPS = {
    "Owner": [
        {"id": "R001", "category": "Leadership",
         "text": "সিদ্ধান্ত নেওয়ার আগে দলের মতামত শুনুন, কিন্তু সিদ্ধান্ত নিজে নিন ও দায় নিন।"},
        {"id": "R002", "category": "Clinical Decision Making",
         "text": "জটিল কেসে দ্বিধা থাকলে দ্বিতীয়বার পরীক্ষা করুন, তাড়াহুড়া করবেন না।"},
        {"id": "R003", "category": "Staff Supervision",
         "text": "ভুল ধরিয়ে দেওয়ার সময় ব্যক্তিকে নয়, কাজকে সমালোচনা করুন।"},
        {"id": "R004", "category": "Conflict Resolution",
         "text": "দুই স্টাফের মধ্যে সমস্যা হলে দুজনের কথাই আলাদাভাবে শুনুন, একপাক্ষিক সিদ্ধান্ত নেবেন না।"},
        {"id": "R005", "category": "Daily Planning",
         "text": "দিনের শুরুতে ২ মিনিট সময় নিয়ে আজকের প্রায়োরিটি ঠিক করে নিন।"},
    ],
    "Therapist": [
        {"id": "R006", "category": "Exercise Demonstration",
         "text": "এক্সারসাইজ শুধু বলে নয়, নিজে করে দেখিয়ে দিন — রোগী চোখে দেখলে দ্রুত শেখে।"},
        {"id": "R007", "category": "Female Patient Privacy",
         "text": "প্রয়োজনে পর্দা/আলাদা ঘর ব্যবহার করুন, রোগীর স্বাচ্ছন্দ্য নিশ্চিত করুন।"},
        {"id": "R008", "category": "Treatment Quality",
         "text": "প্রতিটা সেশনে একই মান বজায় রাখুন, তাড়াহুড়া করে শর্টকাট নেবেন না।"},
        {"id": "R009", "category": "Progress Monitoring",
         "text": "প্রতি সপ্তাহে রোগীর অগ্রগতি লিখে রাখুন, শুধু মনে রাখবেন না।"},
        {"id": "R010", "category": "Documentation",
         "text": "ট্রিটমেন্ট নোট সেশনের সাথে সাথেই লিখে ফেলুন, দিন শেষে মনে করে লিখতে ভুল হয়।"},
    ],
    "Receptionist": [
        {"id": "R011", "category": "Patient Greeting",
         "text": "রোগী ঢোকার সাথে সাথে হাসিমুখে সালাম দিন, প্রথম impression গুরুত্বপূর্ণ।"},
        {"id": "R012", "category": "Queue Management",
         "text": "সিরিয়াল স্পষ্টভাবে বলুন — কনফিউশন হলে রোগী বিরক্ত হয়।"},
        {"id": "R013", "category": "Appointment Handling",
         "text": "অ্যাপয়েন্টমেন্ট দেওয়ার সময় তারিখ-সময় দুইবার নিশ্চিত করুন।"},
        {"id": "R014", "category": "Cash Collection",
         "text": "টাকা নেওয়ার সাথে সাথে রসিদ/এন্ট্রি করে ফেলুন, পরে করব ভাববেন না।"},
        {"id": "R015", "category": "Assistant Behaviour",
         "text": "থেরাপিস্টকে সাহায্য করার সময় রোগীর সামনে নিজে থেকে মেডিকেল পরামর্শ দেবেন না, শুধু সহযোগিতা করুন।"},
    ],
    "Manager": [
        {"id": "R016", "category": "Inventory",
         "text": "স্টক কমে গেলে সাথে সাথে নোট করুন, ফুরিয়ে যাওয়ার অপেক্ষা করবেন না।"},
        {"id": "R017", "category": "Equipment Handling",
         "text": "মেশিন ব্যবহারের পর যথাস্থানে গুছিয়ে রাখুন।"},
        {"id": "R018", "category": "Market Checklist",
         "text": "বাজারে যাওয়ার আগে তালিকা মিলিয়ে নিন, ফেরার পর আবার চেক করুন।"},
        {"id": "R019", "category": "Peak Hour Support",
         "text": "পিক আওয়ারে কাউকে জিজ্ঞেস না করে বুঝে সাহায্যে এগিয়ে যান।"},
        {"id": "R020", "category": "Chamber Maintenance",
         "text": "চেম্বার পরিষ্কার-পরিচ্ছন্নতা প্রতিদিনের রুটিন করুন, শুধু বিশেষ দিনে নয়।"},
    ],
}


def get_pool_for_role(role: str) -> list[dict]:
    """একজন স্টাফের জন্য পূর্ণ টিপ পুল রিটার্ন করে: শেয়ার্ড + তার রোলের নিজস্ব টিপ।"""
    pool = list(SHARED_TIPS)
    pool.extend(ROLE_TIPS.get(role, []))
    return pool


def get_tip_by_id(tip_id: str) -> dict | None:
    for tip in SHARED_TIPS:
        if tip["id"] == tip_id:
            return tip
    for role_tips in ROLE_TIPS.values():
        for tip in role_tips:
            if tip["id"] == tip_id:
                return tip
    return None
